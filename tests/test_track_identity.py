from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ui.main_window import TrackInfo, _generated_cover, _infer_track_fields, _sidecar_cover


class TrackIdentityTests(unittest.TestCase):
    def test_artist_and_title_are_inferred_from_filename(self) -> None:
        title, artist = _infer_track_fields(
            Path("gotye - somebody that i used to know remix.mp3")
        )

        self.assertEqual(artist, "Gotye")
        self.assertEqual(title, "somebody that i used to know remix")

    def test_sidecar_cover_is_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            track = root / "track.mp3"
            cover = root / "cover.jpg"
            track.touch()
            cover.write_bytes(b"cover-bytes")

            self.assertEqual(_sidecar_cover(track), b"cover-bytes")

    def test_generated_cover_is_deterministic(self) -> None:
        info = TrackInfo(
            path=Path("track.mp3"),
            title="A Very Long Track Name",
            artist="Example Artist",
            album="",
        )

        first = _generated_cover(info, "#1db954")
        second = _generated_cover(info, "#1db954")

        self.assertEqual(first.size, (144, 144))
        self.assertEqual(first.tobytes(), second.tobytes())


if __name__ == "__main__":
    unittest.main()
