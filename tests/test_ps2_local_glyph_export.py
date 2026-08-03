import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mgs3_ps2_local_glyph_export import local_glyphs


class FakeRecord:
    block_start = 0
    font_data_offset = 4
    proc_offset = 8
    raw = b"HEAD" + struct.pack("<I", 0)


class Ps2LocalGlyphExportTests(unittest.TestCase):
    def test_empty_font_is_valid(self):
        self.assertEqual(local_glyphs(FakeRecord()), [])

    def test_rejects_mismatched_font_size(self):
        record = FakeRecord()
        record.raw = b"HEAD" + struct.pack("<I", 144) + b"x" * 144
        record.proc_offset = len(record.raw)
        self.assertEqual(local_glyphs(record), [b"x" * 144])


if __name__ == "__main__":
    unittest.main()
