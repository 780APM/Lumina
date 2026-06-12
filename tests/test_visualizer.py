from __future__ import annotations

import unittest

import numpy as np

from visualizer import Visualizer


class VisualizerTests(unittest.TestCase):
    def test_high_frequency_energy_reaches_high_bars(self) -> None:
        fft_size = 1024
        frequency_bin = 400
        samples = np.sin(
            2 * np.pi * frequency_bin * np.arange(fft_size) / fft_size
        ).astype(np.float32)
        visualizer = Visualizer(fft_size=fft_size, smooth=1)

        visualizer.push(samples)
        magnitudes = visualizer.get_magnitudes(24)

        self.assertEqual(magnitudes.shape, (24,))
        self.assertGreater(int(np.argmax(magnitudes)), 18)
        self.assertAlmostEqual(float(magnitudes.max()), 1.0, places=5)

    def test_short_silent_input_is_padded(self) -> None:
        visualizer = Visualizer(fft_size=32)
        visualizer.push(np.zeros(8, dtype=np.float32))
        np.testing.assert_allclose(visualizer.get_magnitudes(10), np.zeros(10))

    def test_invalid_dimensions_and_sizes_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Visualizer(fft_size=1)

        visualizer = Visualizer(fft_size=16)
        with self.assertRaises(ValueError):
            visualizer.push(np.zeros((8, 2), dtype=np.float32))
        with self.assertRaises(ValueError):
            visualizer.get_magnitudes(0)


if __name__ == "__main__":
    unittest.main()
