from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from mgs3_ps2_font_sheet import GLYPH_SIZE, decode_glyph  # noqa: E402
from mgs3_ps2_korean_port import correspondence  # noqa: E402


class FakeRecord:
    def __init__(self, procedures: int, resources: int):
        self.proc_table = [0] * procedures
        self.resource_table_offset = 20
        self.string_resources_offset = 20 + resources * 4


class Ps2KoreanPortTests(unittest.TestCase):
    def test_ps2_glyph_is_24x24_two_bpp_msb_first(self):
        raw = bytearray(GLYPH_SIZE)
        raw[0] = 0b00_01_10_11
        image = decode_glyph(bytes(raw))
        self.assertEqual(image.size, (24, 24))
        self.assertEqual([image.getpixel((x, 0)) for x in range(4)], [0, 85, 170, 255])

    def test_correspondence_keeps_equal_length_variant_block(self):
        ps2 = [FakeRecord(0, 1), FakeRecord(1, 2), FakeRecord(2, 3), FakeRecord(3, 4)]
        reference = [FakeRecord(0, 1), FakeRecord(8, 20), FakeRecord(9, 21), FakeRecord(3, 4)]
        self.assertEqual(
            correspondence(ps2, reference),
            [
                (0, 0, "exact-structure"),
                (1, 1, "anchored-equal-length"),
                (2, 2, "anchored-equal-length"),
                (3, 3, "exact-structure"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
