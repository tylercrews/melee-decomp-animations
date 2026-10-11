import struct
from pathlib import Path
import unittest
import uuid

from tools.melee_anim.hsd import FormatError
from tools.melee_anim.texture import decode_image, write_png


class TextureTests(unittest.TestCase):
    def test_cmpr_subblocks_selectors_and_gamecube_blending(self):
        # First subblock selects endpoint0, endpoint1, blend2, blend3.
        first = struct.pack(">HH4B", 0xF800, 0x001F, *([0x1B] * 4))
        green = struct.pack(">HH4B", 0x07E0, 0, 0, 0, 0, 0)
        blue = struct.pack(">HH4B", 0x001F, 0, 0, 0, 0, 0)
        white = struct.pack(">HH4B", 0xFFFF, 0, 0, 0, 0, 0)
        rgba = decode_image(first + green + blue + white, 8, 8, 14)
        self.assertEqual(list(rgba[:16]), [255, 0, 0, 255, 0, 0, 255, 255,
                                         159, 0, 95, 255, 95, 0, 159, 255])
        self.assertEqual(rgba[4 * 4:5 * 4], bytes([0, 255, 0, 255]))
        self.assertEqual(rgba[4 * 8 * 4:4 * 8 * 4 + 4], bytes([0, 0, 255, 255]))
        self.assertEqual(rgba[(4 * 8 + 4) * 4:(4 * 8 + 5) * 4], bytes([255] * 4))

    def test_cmpr_transparent_color_retains_rgb(self):
        block = struct.pack(">HH4B", 0, 0xFFFF, *([255] * 4))
        rgba = decode_image(block * 4, 8, 8, 14)
        self.assertEqual(rgba[:4], bytes([127, 127, 127, 0]))

    def test_palette_tiling_crop_and_big_endian_rgb565(self):
        pixels = bytes(range(32))
        palette = b"".join(struct.pack(">H", 0xF800 if i % 2 == 0 else 0x07E0) for i in range(32))
        rgba = decode_image(pixels, 3, 2, 9, palette, 1)
        self.assertEqual(len(rgba), 24)
        self.assertEqual(rgba[:8], bytes([255, 0, 0, 255, 0, 255, 0, 255]))
        self.assertEqual(rgba[12:16], bytes([255, 0, 0, 255]))  # source index8

    def test_intensity_alpha_and_bounds(self):
        rgba = decode_image(bytes([0xAF]) * 32, 2, 1, 0)
        self.assertEqual(rgba, bytes([170] * 4 + [255] * 4))
        with self.assertRaises(FormatError):
            decode_image(bytes(31), 8, 8, 14)
        with self.assertRaises(FormatError):
            decode_image(bytes([1]) * 32, 8, 4, 9, bytes(2), 1)

    def test_png_roundtrip(self):
        from PIL import Image
        test_dir = Path("build/melee_anim/tests").resolve()
        test_dir.mkdir(parents=True, exist_ok=True)
        path = test_dir / f"pixel_{uuid.uuid4().hex}.png"
        try:
            write_png(path, 1, 1, bytes([10, 20, 30, 40]))
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 40))
        finally:
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
