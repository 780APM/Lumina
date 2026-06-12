from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from settings import DEFAULT_SETTINGS, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_invalid_values_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "accent": "not-a-color",
                        "viz_3d": "yes",
                        "viz_circular": 1,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(load_settings(path, legacy_path=None), DEFAULT_SETTINGS)

    def test_mutually_exclusive_visualizer_modes_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "accent": "#123ABC",
                        "viz_3d": True,
                        "viz_circular": True,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                load_settings(path, legacy_path=None),
                {"accent": "#123ABC", "viz_3d": True, "viz_circular": False},
            )

    def test_save_creates_directory_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "settings.json"
            expected = {
                "accent": "#abcdef",
                "viz_3d": False,
                "viz_circular": True,
            }

            self.assertTrue(save_settings(expected, path))
            self.assertEqual(load_settings(path, legacy_path=None), expected)
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
