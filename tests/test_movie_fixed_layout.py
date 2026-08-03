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
    maximal_size_neutral_subset,
    page3_indices,
    page3_token,
    rebuild_record_fixed,
    rebuild_record_growing,
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

    def make_western_multilingual_record(self) -> Record:
        record_offset = 0x2000

        def entry(entry_type: int, text: bytes) -> tuple[bytes, Subtitle]:
            payload = text + b"\0"
            size = (4 + len(payload) + 3) & ~3
            original = ((entry_type << 16) | size).to_bytes(4, "little")
            original += payload + b"\0" * (size - 4 - len(payload))
            return original, Subtitle(0, payload, b"", original, entry_type)

        english_raw, english = entry(1, b"A" * 80)
        donor_raw, donor = entry(2, b"B" * 160)
        english = Subtitle(record_offset + 0x24, english.raw, english.tail,
                           english.original, english.entry_type)
        donor_offset = record_offset + 0x20 + len(english_raw) + 4
        donor = Subtitle(donor_offset, donor.raw, donor.tail, donor.original, donor.entry_type)
        body = bytearray(b"\0" * 0x20)
        body.extend(english_raw)
        body.extend(donor_raw)
        text_end = len(body)
        body.extend((0).to_bytes(4, "little"))
        body.extend(b"\0" * ((16 - len(body) % 16) % 16))
        body[4:8] = len(body).to_bytes(4, "little")
        body[0x10:0x14] = (text_end - 0x14).to_bytes(4, "little")
        return Record(3, record_offset, bytes(body), text_end, b"", [english, donor])

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

    @patch("mgs3d_movie_tool.render_character", return_value=b"K" * 64)
    def test_growing_rebuild_appends_new_font_slot(self, _render) -> None:
        record = self.make_record()
        rebuilt, allocation = rebuild_record_growing(
            record, {record.subtitles[0].offset: "\uac00"}, object()
        )
        self.assertEqual(allocation, {"\uac00": "9003"})
        self.assertEqual(int.from_bytes(rebuilt[4:8], "little"), len(rebuilt))
        self.assertEqual(len(rebuilt) % 16, 0)
        self.assertIn(page3_token(2) + b"\0", rebuilt)

    @patch("mgs3d_movie_tool.render_character", return_value=b"K" * 64)
    def test_growing_rebuild_reuses_static_page_without_local_glyph(self, render) -> None:
        record = self.make_record()
        rebuilt, allocation = rebuild_record_growing(
            record,
            {record.subtitles[0].offset: "\uac00"},
            object(),
            static_map={"\uac00": b"\x81\x01"},
        )
        self.assertEqual(allocation, {})
        self.assertEqual(len(rebuilt[record.text_end + 4:]), len(record.font))
        self.assertIn(b"\x81\x01\0", rebuilt)
        render.assert_not_called()

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

    @patch("mgs3d_movie_tool.render_character", return_value=b"K" * 64)
    def test_size_neutral_rebuild_reclaims_non_english_entry(self, _render) -> None:
        record = self.make_western_multilingual_record()
        english, donor = record.subtitles
        rebuilt, allocation = rebuild_record_growing(
            record, {english.offset: "한글"}, object(), {donor.offset}, len(record.raw)
        )
        self.assertEqual(len(rebuilt), len(record.raw))
        self.assertEqual(int.from_bytes(rebuilt[4:8], "little"), len(record.raw))
        self.assertEqual(allocation, {"한": "9001", "글": "9002"})
        self.assertIn(b"K" * 128, rebuilt)
        self.assertNotIn(b"B" * 32, rebuilt)

    @patch("mgs3d_movie_tool.render_character", return_value=b"K" * 64)
    def test_maximal_size_neutral_subset_keeps_fitting_translation(self, _render) -> None:
        record = self.make_western_multilingual_record()
        english, donor = record.subtitles
        selected = maximal_size_neutral_subset(
            record, {english.offset: "한글"}, {donor.offset}, object()
        )
        self.assertEqual(selected, {english.offset: "한글"})


if __name__ == "__main__":
    unittest.main()
