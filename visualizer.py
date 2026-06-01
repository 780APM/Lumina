"""FFT-based spectrum for visualization (Winamp/WMP-style)."""

from __future__ import annotations

from collections import deque
from typing import Deque

import numpy as np


class Visualizer:
    """Compute magnitude spectrum from PCM chunks for reactive bars."""

    def __init__(self, fft_size: int = 1024, smooth: int = 4) -> None:
        self.fft_size = fft_size
        self.smooth = max(1, smooth)
        self._history: Deque[np.ndarray] = deque(maxlen=smooth)
        self._window = np.hanning(fft_size).astype(np.float32)

    def set_fft_size(self, n: int) -> None:
        self.fft_size = n
        self._window = np.hanning(n).astype(np.float32)
        self._history.clear()

    def push(self, samples: np.ndarray) -> None:
        """Feed mono float32 samples. Uses overlapping frames internally."""
        n = self.fft_size
        if len(samples) < n:
            padded = np.zeros(n, dtype=np.float32)
            padded[: len(samples)] = samples
            samples = padded
        for i in range(0, len(samples) - n + 1, n // 2):
            frame = samples[i : i + n] * self._window
            spec = np.abs(np.fft.rfft(frame))
            self._history.append(spec)
        if len(samples) >= n and not self._history:
            frame = samples[:n] * self._window
            spec = np.abs(np.fft.rfft(frame))
            self._history.append(spec)

    def get_magnitudes(self, n_bars: int) -> np.ndarray:
        """Return `n_bars` smoothed magnitude values (log-scaled, 0..1)."""
        if not self._history:
            return np.zeros(n_bars, dtype=np.float32)
        spec = np.mean(self._history, axis=0)
        n = len(spec)
        if n <= n_bars:
            out = np.zeros(n_bars, dtype=np.float32)
            out[:n] = spec.astype(np.float32)
            return self._normalize(out)
        # Average real log-spaced bands instead of sampling a few low bins.
        edges = np.logspace(np.log10(1), np.log10(n), n_bars + 1).astype(int)
        edges = np.maximum.accumulate(edges)
        vals = np.zeros(n_bars, dtype=np.float32)
        for i in range(n_bars):
            start = max(1, min(edges[i], n - 1))
            stop = max(start + 1, min(edges[i + 1], n))
            vals[i] = float(np.mean(spec[start:stop]))
        return self._normalize(vals)

    def _normalize(self, x: np.ndarray) -> np.ndarray:
        x = np.clip(x, 1e-8, None)
        x = np.log10(x + 1)
        m = x.max()
        if m > 0:
            x = x / m
        return np.clip(x, 0.0, 1.0).astype(np.float32)
