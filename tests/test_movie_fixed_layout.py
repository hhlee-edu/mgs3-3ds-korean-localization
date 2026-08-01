import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_movie_tool import (  # noqa: E402
    MovieError,
    Record,
    Subtitle,
    fixed_capacity,
    maximal_safe_subset,
    maximal_safe_extension,
    page3_indices,
    page3_token,
    rebuild_record_fixed,
)


class MovieFixedLayoutTests(unittest.TestCase):
    def make_record(self) -> Record:
        record_offset = 0x1000
        text = page3_token(0) + page3_token(1) + b"\0" + b"\0" * 3
        original = (0x70018).to_bytes(4, "little") + text
        text_end = 0x20 + len(original)
        raw = bytearray(b"\0" * text_end)
        raw[0x20:text_end] = original
        raw.extend((128).to_bytes(4, "little"))
        raw.extend(bytes(range(64)) + bytes(reversed(range(64))))
        return Record(
            index=2,
            offset=record_offset,
            raw=bytes(raw),
            text_end=text_end,
            font=bytes(raw[text_end + 4:]),
            subtitles=[Subtitle(record_offset + 0x24, page3_token(0) + page3_token(1) + b"\0", b"", original)],
        )

    def test_page3_indices_skips_controls(self) -> None:
        encoded = page3_token(3) + b"A" + b"\x80|" + page3_token(9) + b"\0"
        self.assertEqual(page3_indices(encoded), {3, 9})

    @patch("mgs3d_movie_tool.render_character", return_value=b"K" * 64)
    def test_fixed_rebuild_preserves_size_and_uses_freed_slots(self, _render) -> None:
        record = self.make_record()
        rebuilt, allocation = rebuild_record_fixed(
            record, {record.subtitles[0].offset: "한글"}, object()
        )
        self.assertEqual(len(rebuilt), len(record.raw))
        self.assertEqual(allocation, {"한": "9001", "글": "9002"})
        self.assertEqual(rebuilt[record.text_end + 4:record.text_end + 4 + 128], b"K" * 128)

    def test_fixed_rebuild_refuses_font_deficit(self) -> None:
        record = self.make_record()
        with self.assertRaisesRegex(MovieError, "fixed-layout font deficit"):
            rebuild_record_fixed(record, {record.subtitles[0].offset: "한글화"}, object())

    def test_capacity_matches_fixed_rebuild_constraints(self) -> None:
        record = self.make_record()
        safe = fixed_capacity(record, {record.subtitles[0].offset: "가나"})
        self.assertTrue(safe["safe"])
        self.assertEqual(safe["font_deficit"], 0)
        self.assertEqual(safe["entries"][0]["deficit_bytes"], 0)

        unsafe = fixed_capacity(record, {record.subtitles[0].offset: "가나다"})
        self.assertFalse(unsafe["safe"])
        self.assertEqual(unsafe["font_deficit"], 1)

    def test_maximal_subset_drops_only_what_is_needed(self) -> None:
        record = self.make_record()
        offset = record.subtitles[0].offset
        self.assertEqual(maximal_safe_subset(record, {offset: "가나"}), {offset: "가나"})
        self.assertEqual(maximal_safe_subset(record, {offset: "가나다"}), {})

    def test_maximal_extension_preserves_safe_base(self) -> None:
        record = self.make_record()
        offset = record.subtitles[0].offset
        self.assertEqual(maximal_safe_extension(record, {offset: "가나"}, {}), {})
        with self.assertRaisesRegex(MovieError, "base translations are not"):
            maximal_safe_extension(record, {offset: "가나다"}, {})


if __name__ == "__main__":
    unittest.main()
