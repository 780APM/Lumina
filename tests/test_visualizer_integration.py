import unittest
from unittest.mock import patch

import numpy as np

from ui.main_window import CanvasVisualizer, FFT_SIZE, FigureCanvasTkAgg, MainWindow


class VisualizerIntegrationTests(unittest.TestCase):
    def test_2d_and_circular_ticks_do_not_construct_matplotlib_canvases(self) -> None:
        app = MainWindow()
        try:
            app.update_idletasks()
            with patch.object(FigureCanvasTkAgg, "__init__", side_effect=AssertionError("2D must not use TkAgg")):
                for circular in (False, True, False):
                    app._viz_circular = circular
                    app._viz_3d = False
                    app._create_visualizer()
                    app.update_idletasks()
                    self.assertIsInstance(app._canvas, CanvasVisualizer)
                    before = app._canvas.find_all()
                    signal = np.sin(np.arange(FFT_SIZE) * 0.1).astype(np.float32)
                    with patch.object(app.audio, "get_pcm_chunk", return_value=signal), patch.object(app, "winfo_viewable", return_value=True):
                        app._tick_viz()
                    self.assertFalse(app._viz_error_reported)
                    self.assertEqual(app._canvas.find_all(), before)
                    self.assertGreater(float(app._display_heights.max()), 0)
        finally:
            app._on_close()

    def test_minimized_window_skips_visualizer_work_and_keeps_resume_poll(self) -> None:
        app = MainWindow()
        try:
            with patch.object(app, "state", return_value="iconic"), patch.object(app.audio, "is_playing", return_value=True), patch.object(app.audio, "get_pcm_chunk") as read_pcm:
                app._tick_viz()
                read_pcm.assert_not_called()
                self.assertIsNotNone(app._viz_job)
                self.assertIsNone(app._last_viz_time)
        finally:
            app._on_close()
