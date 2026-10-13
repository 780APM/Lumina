"""Verify scrolling track text cannot resize the transport controls."""

import unittest

from ui.main_window import MainWindow


class PlayerLayoutTests(unittest.TestCase):
    def test_timeline_stays_fixed_as_long_titles_scroll(self) -> None:
        app = MainWindow()
        try:
            app.update_idletasks()
            for size in ("1200x800", "1000x700"):
                app.geometry(size)
                app.update_idletasks()
                baseline = (app.slider.winfo_rootx(), app.slider.winfo_width())
                title_width = app.np_title.winfo_width()
                rendered_titles = set()
                for title in ("W" * 35 + "i" * 35, "A long song title with very different letter widths " * 3):
                    app.np_title.set_text(title)
                    app.track_label.set_text(title)
                    for offset in range(60):
                        for label in (app.np_title, app.track_label):
                            label._offset = offset
                            label._render()
                        app.update_idletasks()
                        rendered_titles.add(app.np_title.cget("text"))
                        self.assertEqual(
                            (app.slider.winfo_rootx(), app.slider.winfo_width()), baseline
                        )
                        self.assertEqual(app.np_title.winfo_width(), title_width)
                self.assertGreater(len(rendered_titles), 1)
        finally:
            app._on_close()


if __name__ == "__main__":
    unittest.main()
