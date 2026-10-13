"""Persistent Tk shapes for low-overhead spectrum animation."""

from __future__ import annotations

import math
import tkinter as tk
from typing import Sequence

import numpy as np


class CanvasVisualizer(tk.Canvas):
    """Create shapes once; only update coordinates and colors for each frame."""

    def __init__(self, master, n_bars: int, *, circular: bool = False,
                 background: str = "#121212", **kwargs) -> None:
        if n_bars <= 0:
            raise ValueError("n_bars must be positive")
        super().__init__(master, background=background, highlightthickness=0,
                         borderwidth=0, **kwargs)
        self.n_bars = n_bars
        self.circular = circular
        self._background_rgb = tuple(int(background[i:i + 2], 16) for i in (1, 3, 5))
        self._heights = np.zeros(n_bars, dtype=np.float32)
        self._peaks = np.zeros(n_bars, dtype=np.float32)
        self._palette = ["#1db954"] * 256
        self._reflection_palette = ["#173320"] * 256
        self._last_colors: list[int | None] = [None] * n_bars
        self._size = (1, 1)
        self._bars = []
        self._peak_items = []
        self._reflections = []
        create = self.create_polygon if circular else self.create_rectangle
        for _ in range(n_bars):
            self._bars.append(create(0, 0, 0, 0, fill=self._palette[0], outline=""))
            if not circular:
                self._reflections.append(self.create_rectangle(
                    0, 0, 0, 0, fill=self._reflection_palette[0], outline=""))
            self._peak_items.append(create(0, 0, 0, 0, fill="#ffffff", outline=""))
        # Unit rays are independent of canvas size and animation state.
        half_width = math.pi * 0.78 / n_bars
        self._rays = [
            ((math.sin(angle - half_width), -math.cos(angle - half_width)),
             (math.sin(angle + half_width), -math.cos(angle + half_width)))
            for angle in np.linspace(0, 2 * math.pi, n_bars, endpoint=False)
        ]
        self.bind("<Configure>", self._on_resize)

    def set_palette(self, colors: Sequence[Sequence[float]]) -> None:
        """Cache display colors and alpha-like reflection blends outside the tick."""
        if not len(colors):
            raise ValueError("palette must not be empty")
        def hex_color(rgb):
            return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in rgb)
        rgb = [tuple(round(float(c) * 255) for c in color[:3]) for color in colors]
        self._palette = [hex_color(color) for color in rgb]
        self._reflection_palette = [
            hex_color(tuple(0.2 * c + 0.8 * bg for c, bg in zip(color, self._background_rgb)))
            for color in rgb
        ]
        self._last_colors = [None] * self.n_bars
        self.render(self._heights, self._peaks)

    def _on_resize(self, event) -> None:
        self._size = (max(1, event.width), max(1, event.height))
        self.render(self._heights, self._peaks)

    def render(self, heights: np.ndarray, peaks: np.ndarray) -> None:
        heights = np.asarray(heights)
        peaks = np.asarray(peaks)
        if heights.shape != (self.n_bars,) or peaks.shape != (self.n_bars,):
            raise ValueError("one height and peak are required per bar")
        self._heights = np.clip(np.nan_to_num(heights), 0, 1)
        self._peaks = np.clip(np.nan_to_num(peaks), 0, 1)
        width, height = self._size
        if width <= 1 or height <= 1:
            return
        palette_size = len(self._palette) - 1
        margin = max(4, width * 0.035)
        spacing = max(1, (width - margin * 2) / self.n_bars)
        baseline = height * 0.76
        max_height = height * 0.67
        cx, cy = width / 2, height / 2
        radius = min(width, height) * 0.45
        inner = radius * 0.32
        radial_height = radius - inner
        for i, (h, peak) in enumerate(zip(self._heights, self._peaks)):
            color_index = min(palette_size, int(float(h) * 1.3 * palette_size))
            if self._last_colors[i] != color_index:
                self.itemconfigure(self._bars[i], fill=self._palette[color_index])
                if not self.circular:
                    self.itemconfigure(self._reflections[i], fill=self._reflection_palette[color_index])
                self._last_colors[i] = color_index
            if self.circular:
                left, right = self._rays[i]
                def polygon(r0, r1):
                    return (cx + left[0] * r0, cy + left[1] * r0,
                            cx + right[0] * r0, cy + right[1] * r0,
                            cx + right[0] * r1, cy + right[1] * r1,
                            cx + left[0] * r1, cy + left[1] * r1)
                top = inner + max(0.025, float(h)) * radial_height
                peak_radius = inner + max(0.03, float(peak)) * radial_height
                self.coords(self._bars[i], *polygon(inner, top))
                self.coords(self._peak_items[i], *polygon(peak_radius, peak_radius + max(1, radius * 0.012)))
            else:
                x0 = margin + (i + 0.11) * spacing
                x1 = x0 + spacing * 0.78
                bar_height = max(0.02, float(h)) * max_height
                peak_y = baseline - float(peak) * max_height
                self.coords(self._bars[i], x0, baseline - bar_height, x1, baseline)
                self.coords(self._reflections[i], x0, baseline + 3, x1, baseline + 3 + bar_height * 0.3)
                self.coords(self._peak_items[i], x0, peak_y - 2, x1, peak_y)
