"""Audio playback and decoding via miniaudio. Exposes PCM for FFT."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioEngine:
    """Load and play local audio (WAV, FLAC, OGG). Stream PCM for visualization."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._data: np.ndarray | None = None
        self._sr: int = 0
        self._stream: sd.OutputStream | None = None
        self._pos: int = 0
        self._playing = False
        self._volume: float = 1.0  # 0.0 to 1.0
        self._lock = threading.Lock()
        self._on_position: Callable[[float, float], None] | None = None  # current, duration

    def open(self, path: str | Path) -> bool:
        """Load file. Supports WAV, FLAC, OGG."""
        path = Path(path)
        if not path.is_file():
            return False
        try:
            data, sr = sf.read(path, dtype="float32")
            if data.ndim == 2:
                data = data.mean(axis=1)
            with self._lock:
                self._path = path
                self._data = data
                self._sr = int(sr)
                self._pos = 0
                self._stop_stream()
            return True
        except Exception:
            return False

    def _stop_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._playing = False

    def play(self) -> None:
        """Start playback."""
        with self._lock:
            if self._data is None or self._sr == 0:
                return
            self._stop_stream()
            self._playing = True
            chunk = 1024

            def callback(outdata, frames: int, time_info, status):
                if status:
                    outdata.fill(0)
                    return
                with self._lock:
                    data = self._data
                    sr = self._sr
                    vol = self._volume
                    pos = self._pos
                if data is None:
                    outdata.fill(0)
                    return
                end = min(pos + frames, len(data))
                n = end - pos
                if n > 0:
                    outdata[:n, 0] = data[pos:end] * vol
                if n < frames:
                    outdata[n:, 0] = 0
                new_pos = end
                with self._lock:
                    self._pos = new_pos
                if self._on_position and sr > 0:
                    cur = new_pos / sr
                    dur = len(data) / sr
                    self._on_position(cur, dur)

            self._stream = sd.OutputStream(
                samplerate=self._sr,
                channels=1,
                dtype="float32",
                blocksize=chunk,
                callback=callback,
            )
            self._stream.start()

    def pause(self) -> None:
        """Pause playback (keeps position)."""
        with self._lock:
            self._stop_stream()

    def stop(self) -> None:
        """Stop and reset to start."""
        with self._lock:
            self._pos = 0
            self._stop_stream()

    def seek(self, sec: float) -> None:
        """Seek to position in seconds. Instant - no stream restart needed."""
        with self._lock:
            if self._data is None or self._sr == 0:
                return
            self._pos = max(0, min(int(sec * self._sr), len(self._data)))

    def is_playing(self) -> bool:
        with self._lock:
            return self._playing

    def duration_sec(self) -> float:
        with self._lock:
            if self._data is None or self._sr == 0:
                return 0.0
            return len(self._data) / self._sr

    def position_sec(self) -> float:
        with self._lock:
            if self._data is None or self._sr == 0:
                return 0.0
            return self._pos / self._sr

    def set_position_callback(self, cb: Callable[[float, float], None] | None) -> None:
        """Called with (current_sec, duration_sec) during playback."""
        self._on_position = cb

    def get_pcm_chunk(self, length: int) -> np.ndarray | None:
        """Return `length` samples at current position for FFT (mono float32). Does not advance position."""
        with self._lock:
            if self._data is None:
                return None
            pos = self._pos
            end = min(pos + length, len(self._data))
            chunk = self._data[pos:end].copy()
            return chunk if len(chunk) else None

    def sample_rate(self) -> int:
        return self._sr

    def current_path(self) -> Path | None:
        return self._path

    def set_volume(self, vol: float) -> None:
        """Set volume (0.0 to 1.0)."""
        with self._lock:
            self._volume = max(0.0, min(1.0, vol))

    def get_volume(self) -> float:
        with self._lock:
            return self._volume
