"""Streaming playback engine that keeps memory use independent of track length."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import sys
import threading

import miniaudio
import numpy as np

try:
    from Lumina.audio_engine import AudioResult, SUPPORTED_EXTENSIONS
except ModuleNotFoundError:  # Running directly from the source checkout.
    from audio_engine import AudioResult, SUPPORTED_EXTENSIONS


VISUALIZER_SAMPLES = 4096


@dataclass(frozen=True)
class StreamTrack:
    path: Path
    sample_rate: int
    duration: float
    channels: int = 2


class StreamingAudioEngine:
    """Play files with ``miniaudio.stream_file`` instead of full PCM decoding."""

    def __init__(self) -> None:
        self._track: StreamTrack | None = None
        self._device: miniaudio.PlaybackDevice | None = None
        self._stream = None
        self._stream_generation = 0
        self._position_frames = 0
        self._playing = False
        self._ended = False
        self._volume = 1.0
        self._last_result = AudioResult(False, "No audio loaded")
        self._cache: OrderedDict[Path, StreamTrack] = OrderedDict()
        self._visualizer_pcm = np.zeros(0, dtype=np.float32)
        self._lock = threading.RLock()
        self._inspect_lock = threading.Lock()

    def open(self, path: str | Path) -> bool:
        return self.open_result(path).ok

    def open_result(self, path: str | Path) -> AudioResult:
        path = self._normalise(path)
        result = self.preload(path)
        if not result.ok:
            self._clear_loaded()
            return result
        with self._lock:
            track = self._cache[path]
            old_device = self._detach_device_locked()
            self._track = track
            self._position_frames = 0
            self._ended = False
            self._visualizer_pcm = np.zeros(0, dtype=np.float32)
        self._close_device(old_device)
        return self._set_result(True)

    def preload(self, path: str | Path) -> AudioResult:
        path = self._normalise(path)
        if not path.is_file():
            return self._set_result(False, f"File not found: {path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return self._set_result(False, f"Unsupported file type: {path.suffix or 'unknown'}")
        with self._lock:
            if path in self._cache:
                self._cache.move_to_end(path)
                return self._set_result(True)
        # Metadata inspection is cheap and serialized so rapid selection cannot
        # create a burst of decoders and disk reads.
        with self._inspect_lock:
            with self._lock:
                if path in self._cache:
                    return self._set_result(True)
            try:
                info = miniaudio.get_file_info(str(path))
                track = StreamTrack(path, int(info.sample_rate), float(info.duration))
                if track.sample_rate <= 0 or track.duration <= 0:
                    raise ValueError("the file did not report playable audio")
            except Exception as exc:
                return self._set_result(False, f"Could not inspect audio: {exc}")
            with self._lock:
                self._cache[path] = track
                self._cache.move_to_end(path)
                while len(self._cache) > 64:
                    self._cache.popitem(last=False)
        return self._set_result(True)

    def is_cached(self, path: str | Path) -> bool:
        with self._lock:
            return self._normalise(path) in self._cache

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def play(self) -> bool:
        with self._lock:
            track = self._track
            if track is None:
                return self._set_result(False, "No audio loaded").ok
            if self._position_frames >= int(track.duration * track.sample_rate):
                self._position_frames = 0
            old_device = self._detach_device_locked()
            self._playing = True
            self._ended = False
            stream = self._pcm_stream(track, self._position_frames, self._stream_generation)
            self._stream = stream
        self._close_device(old_device)
        next(stream)
        device = None
        try:
            device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.FLOAT32, nchannels=track.channels,
                sample_rate=track.sample_rate, backends=_preferred_backends(), app_name="Lumina",
            )
            device.set_master_volume(self._volume)
            device.start(stream)
        except Exception as exc:
            self._close_device(device)
            with self._lock:
                self._playing = False
                self._stream = None
            return self._set_result(False, f"Could not start playback: {exc}").ok
        with self._lock:
            if self._stream is not stream:
                self._close_device(device)
                return False
            self._device = device
        return self._set_result(True).ok

    def pause(self) -> None:
        with self._lock:
            device = self._detach_device_locked()
        self._close_device(device)

    def stop(self) -> None:
        with self._lock:
            self._position_frames = 0
            self._ended = False
            device = self._detach_device_locked()
        self._close_device(device)

    def seek(self, sec: float) -> None:
        with self._lock:
            track = self._track
            if track is None:
                return
            self._position_frames = max(0, min(int(sec * track.sample_rate), int(track.duration * track.sample_rate)))
            was_playing = self._playing
            device = self._detach_device_locked() if was_playing else None
            self._ended = False
        self._close_device(device)
        if was_playing:
            self.play()

    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    def duration_sec(self) -> float:
        with self._lock:
            return self._track.duration if self._track else 0.0

    def position_sec(self) -> float:
        with self._lock:
            return self._position_frames / self._track.sample_rate if self._track else 0.0

    def get_pcm_chunk(self, length: int) -> np.ndarray | None:
        if length <= 0:
            return None
        with self._lock:
            return self._visualizer_pcm[-length:].copy() if len(self._visualizer_pcm) else None

    def sample_rate(self) -> int:
        with self._lock:
            return self._track.sample_rate if self._track else 0

    def current_path(self) -> Path | None:
        with self._lock:
            return self._track.path if self._track else None

    def set_volume(self, vol: float) -> None:
        with self._lock:
            self._volume = max(0.0, min(1.0, float(vol)))
            device = self._device
        if device is not None:
            device.set_master_volume(self._volume)

    def get_volume(self) -> float:
        with self._lock:
            return self._volume

    def consume_end_event(self) -> bool:
        with self._lock:
            ended, self._ended = self._ended, False
            return ended

    def last_error(self) -> str:
        with self._lock:
            return "" if self._last_result.ok else self._last_result.message

    def last_result(self) -> AudioResult:
        with self._lock:
            return self._last_result

    def _pcm_stream(self, track: StreamTrack, seek_frame: int, generation: int):
        requested = yield b""
        try:
            source = miniaudio.stream_file(
                str(track.path), output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=track.channels, sample_rate=track.sample_rate,
                seek_frame=seek_frame,
            )
            while True:
                raw = source.send(int(requested))
                block = np.asarray(raw, dtype=np.float32).reshape(-1, track.channels)
                if not len(block):
                    break
                mono = block.mean(axis=1, dtype=np.float32)
                with self._lock:
                    self._position_frames += len(block)
                    self._visualizer_pcm = np.concatenate((self._visualizer_pcm, mono))[-VISUALIZER_SAMPLES:]
                requested = yield block
        except StopIteration:
            # End of source is the normal completion signal from miniaudio.
            pass
        except Exception as exc:
            self._set_result(False, f"Playback stream failed: {exc}")
        finally:
            with self._lock:
                if generation != self._stream_generation:
                    return
                self._playing = False
                # Closing a device for pause, seek, or track selection is not
                # a playback-complete event.
                self._ended = self._position_frames >= int(
                    track.duration * track.sample_rate
                )

    def _detach_device_locked(self):
        device, self._device = self._device, None
        self._stream = None
        self._stream_generation += 1
        self._playing = False
        return device

    def _clear_loaded(self) -> None:
        with self._lock:
            device = self._detach_device_locked()
            self._track = None
            self._position_frames = 0
            self._ended = False
        self._close_device(device)

    def _set_result(self, ok: bool, message: str = "") -> AudioResult:
        self._last_result = AudioResult(ok, message)
        return self._last_result

    @staticmethod
    def _normalise(path: str | Path) -> Path:
        try:
            return Path(path).resolve()
        except OSError:
            return Path(path)

    @staticmethod
    def _close_device(device) -> None:
        if device is None:
            return
        for operation in (device.stop, device.close):
            try:
                operation()
            except Exception:
                pass


def _preferred_backends():
    if sys.platform.startswith("linux"):
        return [miniaudio.Backend.PULSEAUDIO, miniaudio.Backend.ALSA, miniaudio.Backend.JACK]
    if sys.platform == "darwin":
        return [miniaudio.Backend.COREAUDIO]
    if sys.platform.startswith("win"):
        return [miniaudio.Backend.WASAPI, miniaudio.Backend.DSOUND, miniaudio.Backend.WINMM]
    return None
