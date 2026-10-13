import unittest

from PIL import Image

from branding import asset_path


class BrandingTests(unittest.TestCase):
    def test_icon_contains_windows_sizes_and_logo_preserves_transparency(self) -> None:
        with Image.open(asset_path("lumina.ico")) as icon:
            self.assertTrue({(n, n) for n in (16, 24, 32, 48, 64, 128, 256)} <= icon.ico.sizes())
        with Image.open(asset_path("lumina.png")) as logo:
            self.assertEqual(logo.mode, "RGBA")
            self.assertEqual(logo.getpixel((0, 0))[3], 0)
