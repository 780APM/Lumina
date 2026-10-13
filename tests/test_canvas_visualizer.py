from types import SimpleNamespace
import tkinter as tk
import unittest

import numpy as np

from ui.canvas_visualizer import CanvasVisualizer


class CanvasVisualizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def test_shapes_are_reused_during_animation_resize_and_recolor(self) -> None:
        for circular, count in ((False, 48), (True, 72)):
            with self.subTest(circular=circular):
                canvas = CanvasVisualizer(self.root, count, circular=circular)
                try:
                    canvas._on_resize(SimpleNamespace(width=828, height=506))
                    ids = canvas.find_all()
                    self.assertEqual(len(ids), count * (2 if circular else 3))
                    initial = canvas.coords(canvas._bars[0])
                    for height in np.linspace(0, 1, 30):
                        values = np.full(count, height)
                        canvas.render(values, values)
                        self.assertEqual(canvas.find_all(), ids)
                    self.assertNotEqual(canvas.coords(canvas._bars[0]), initial)
                    canvas.set_palette([(1, 0, 0), (0, 0, 1)])
                    self.assertEqual(canvas.itemcget(canvas._bars[0], "fill"), "#0000ff")
                    before_resize = canvas.coords(canvas._bars[0])
                    canvas._on_resize(SimpleNamespace(width=414, height=253))
                    self.assertNotEqual(canvas.coords(canvas._bars[0]), before_resize)
                    self.assertEqual(canvas.find_all(), ids)
                    for item in ids:
                        coords = canvas.coords(item)
                        self.assertTrue(all(np.isfinite(coords)))
                        self.assertTrue(all(0 <= c <= 414 for c in coords[::2]))
                        self.assertTrue(all(0 <= c <= 253 for c in coords[1::2]))
                finally:
                    canvas.destroy()

    def test_invalid_shapes_are_rejected_and_nonfinite_values_are_safe(self) -> None:
        canvas = CanvasVisualizer(self.root, 3)
        try:
            canvas._on_resize(SimpleNamespace(width=828, height=506))
            with self.assertRaises(ValueError):
                canvas.render(np.zeros(4), np.zeros(3))
            canvas.render(np.array([np.nan, np.inf, -np.inf]), np.zeros(3))
            self.assertTrue(all(np.isfinite(canvas.coords(canvas._bars[1]))))
        finally:
            canvas.destroy()
