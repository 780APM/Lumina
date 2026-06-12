"""Audio playback and decoding via miniaudio. Exposes PCM for FFT."""

from __future__ import annotations

from dataclasses import dataclass
import sys
import threading
from pathlib import Path
from typing import Callable

import miniaudio
import numpy as np


SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg"}


@dataclass(frozen=True)
class AudioResult:
    """Structured result for load/playback operations."""

    ok: bool
    message: str = ""


class AudioEngine:
    """Load and play local audio with miniaudio while keeping PCM for visualization."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._data: np.ndarray | None = None
        self._mono: np.ndarray | None = None
        self._sr: int = 0
        self._channels: int = 2
        self._device: miniaudio.PlaybackDevice | None = None
        self._stream = None
        self._pos: int = 0
        self._playing = False
        self._ended = False
        self._volume: float = 1.0
        self._last_result = AudioResult(False, "No audio loaded")
        self._lock = threading.RLock()
        self._on_end: Callable[[], None] | None = None

    def open(self, path: str | Path) -> bool:
        """Load an audio file. Supports MP3, WAV, FLAC, and OGG."""
        return self.open_result(path).ok

    def open_result(self, path: str | Path) -> AudioResult:
        path = Path(path)
        if not path.is_file():
            self._clear_loaded()
            return self._set_result(False, f"File not found: {path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            self._clear_loaded()
            return self._set_result(False, f"Unsupported file type: {path.suffix or 'unknown'}")

        try:
            decoded = miniaudio.decode_file(
                str(path),
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=2,
            )
            samples = np.asarray(decoded.samples, dtype=np.float32)
            channels = int(decoded.nchannels or 2)
            if samples.size == 0:
                self._clear_loaded()
                return self._set_result(False, "The audio file did not contain playable samples")
            samples = samples.reshape(-1, channels)
            mono = samples.mean(axis=1).astype(np.float32, copy=False)
        except Exception as exc:
            self._clear_loaded()
            return self._set_result(False, f"Could not decode audio: {exc}")

        with self._lock:
            old_device = self._detach_device_locked()
            self._path = path
            self._data = samples
            self._mono = mono
            self._sr = int(decoded.sample_rate)
            self._channels = channels
            self._pos = 0
            self._ended = False
        self._close_device(old_device)
        return self._set_result(True, "")

    def play(self) -> bool:
        """Start or resume playback. Returns True only when playback starts."""
        with self._lock:
            if self._data is None or self._sr <= 0:
                self._set_result(False, "No audio loaded")
                return False
            if self._pos >= len(self._data):
                self._pos = 0
            old_device = self._device
            self._device = None
            self._stream = None
            self._playing = True
            self._ended = False
            stream = self._pcm_stream()
            self._stream = stream
            sample_rate = self._sr
            channels = self._channels

        self._close_device(old_device)
        next(stream)
        device: miniaudio.PlaybackDevice | None = None
        try:
            device = miniaudio.PlaybackDevice(
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=channels,
                sample_rate=sample_rate,
                backends=_preferred_backends(),
                app_name="Lumina",
            )
            device.start(stream)
        except Exception as exc:
            try:
                if device is not None:
                    device.close()
            except Exception:
                pass
            with self._lock:
                self._playing = False
                self._device = None
                self._stream = None
                self._set_result(False, f"Could not start playback: {exc}")
            return False

        close_started_device = False
        with self._lock:
            if self._stream is stream:
                self._device = device
            else:
                close_started_device = True
                self._set_result(False, "Playback was interrupted before it could start")
        if close_started_device:
            self._close_device(device)
            return False
        self._set_result(True, "")
        return True

    def pause(self) -> None:
        """Pause playback while keeping the current position."""
        with self._lock:
            device = self._detach_device_locked()
        self._close_device(device)

    def stop(self) -> None:
        """Stop playback and reset to the beginning."""
        with self._lock:
            self._pos = 0
            self._ended = False
            device = self._detach_device_locked()
        self._close_device(device)

    def seek(self, sec: float) -> None:
        """Seek to a position in seconds."""
        with self._lock:
            if self._data is None or self._sr <= 0:
                return
            self._pos = max(0, min(int(sec * self._sr), len(self._data)))
            self._ended = False

    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    def duration_sec(self) -> float:
        with self._lock:
            if self._data is None or self._sr <= 0:
                return 0.0
            return len(self._data) / self._sr

    def position_sec(self) -> float:
        with self._lock:
            if self._data is None or self._sr <= 0:
                return 0.0
            return self._pos / self._sr

    def set_position_callback(self, cb: Callable[[float, float], None] | None) -> None:
        """Retained for compatibility; UI should poll position on the main thread."""
        return None

    def set_end_callback(self, cb: Callable[[], None] | None) -> None:
        self._on_end = cb

    def consume_end_event(self) -> bool:
        """Return and clear the pending end-of-track event."""
        with self._lock:
            ended = self._ended
            if ended:
                self._ended = False
        return ended

    def get_pcm_chunk(self, length: int) -> np.ndarray | None:
        """Return `length` mono samples at current position for FFT without advancing."""
        if length <= 0:
            return None
        with self._lock:
            if self._mono is None:
                return None
            pos = self._pos
            end = min(pos + length, len(self._mono))
            chunk = self._mono[pos:end].copy()
            return chunk if len(chunk) else None

    def sample_rate(self) -> int:
        with self._lock:
            return self._sr

    def current_path(self) -> Path | None:
        with self._lock:
            return self._path

    def set_volume(self, vol: float) -> None:
        with self._lock:
            self._volume = max(0.0, min(1.0, float(vol)))

    def get_volume(self) -> float:
        with self._lock:
            return self._volume

    def last_error(self) -> str:
        return "" if self._last_result.ok else self._last_result.message

    def last_result(self) -> AudioResult:
        return self._last_result

    def _pcm_stream(self):
        required_frames = yield b""
        while True:
            with self._lock:
                data = self._data
                pos = self._pos
                vol = self._volume
                channels = self._channels
                playing = self._playing

            if data is None or not playing:
                break

            end = min(pos + int(required_frames), len(data))
            block = data[pos:end] * vol
            missing = int(required_frames) - len(block)
            if missing > 0:
                pad = np.zeros((missing, channels), dtype=np.float32)
                block = np.vstack((block, pad)) if len(block) else pad

            with self._lock:
                self._pos = end
                if end >= len(data):
                    self._playing = False
                    self._ended = True

            required_frames = yield block.astype(np.float32, copy=False)
            if end >= len(data):
                break

    def _detach_device_locked(self) -> miniaudio.PlaybackDevice | None:
        device = self._device
        self._device = None
        self._stream = None
        self._playing = False
        return device

    def _close_device(self, device: miniaudio.PlaybackDevice | None) -> None:
        if device is None:
            return
        try:
            device.stop()
        except Exception:
            pass
        try:
            device.close()
        except Exception:
            pass

    def _clear_loaded(self) -> None:
        with self._lock:
            device = self._detach_device_locked()
            self._path = None
            self._data = None
            self._mono = None
            self._sr = 0
            self._channels = 2
            self._pos = 0
            self._ended = False
        self._close_device(device)

    def _set_result(self, ok: bool, message: str = "") -> AudioResult:
        self._last_result = AudioResult(ok, message)
        return self._last_result


def _preferred_backends() -> list[miniaudio.Backend] | None:
    if sys.platform.startswith("linux"):
        return [miniaudio.Backend.PULSEAUDIO, miniaudio.Backend.ALSA, miniaudio.Backend.JACK]
    if sys.platform == "darwin":
        return [miniaudio.Backend.COREAUDIO]
    if sys.platform.startswith("win"):
        return [miniaudio.Backend.WASAPI, miniaudio.Backend.DSOUND, miniaudio.Backend.WINMM]
    return None
