from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_codec_tool import CodecError, GcxRecord, align  # noqa: E402
from mgs3d_gcx_font_tool import (  # noqa: E402
    GLYPH_SIZE,
    build_parser,
    custom_token,
    dead_font_slots,
    font_region,
    freed_glyphs,
    glyph_slot_owners,
    plan_capacity_resources,
    unit_is_changed,
)


MALGUN = Path(r"C:\Windows\Fonts\malgun.ttf")


def build_synthetic_gcx(glyph_count: int = 3) -> bytes:
    """A minimal, hand-assembled, byte-valid single-GCX codec.dat: 2 string
    resources (resource 0 references glyph slot 0; resource 1 references
    glyph slot 1 via a `0x1F <suffix>` accent escape immediately followed by
    the real token, to exercise the escape-skipping fix), and glyph_count
    glyph slots (any slot beyond 1 is genuinely unreferenced/dead).
    """
    assert glyph_count >= 3
    resource0 = custom_token(0) + b"\x00"
    resource1 = b"\x1f\x90" + custom_token(1) + b"\x00"
    plain = resource0 + resource1

    block_start = 8  # timestamp (4) + END_MARKER (4), empty proc table
    resource_table_offset = 20  # right after the 5-word block header
    string_resources_offset = resource_table_offset + 2 * 4
    font_data_offset = string_resources_offset + len(plain)
    font_payload_size = glyph_count * GLYPH_SIZE
    proc_offset = font_data_offset + 4 + font_payload_size

    header = struct.pack(
        "<5I", proc_offset, resource_table_offset, string_resources_offset,
        font_data_offset, 0,  # seed=0 -> crypt() is a no-op, plaintext == ciphertext
    )
    resource_table = struct.pack("<II", 0x80000000, 0x80000000 | len(resource0))
    font_section = struct.pack("<I", font_payload_size) + b"".join(
        bytes([0xAA + slot]) * GLYPH_SIZE for slot in range(glyph_count)
    )
    procedure = struct.pack("<II", 0, 0)  # main_relative=0, main_size=0

    body = header + resource_table + plain + font_section + procedure
    raw = b"\x00" * 4 + b"\xff" * 4 + body
    return raw + b"\x00" * (align(len(raw)) - len(raw))


class TranslationChangeTests(unittest.TestCase):
    def test_lossless_original_text_is_not_a_change(self) -> None:
        unit = {"text": "ABC<0A><00>"}
        self.assertFalse(unit_is_changed(unit, b"ABC\n\0", {}))

    def test_different_lossless_text_is_a_change(self) -> None:
        unit = {"text": "ABD<0A><00>"}
        self.assertTrue(unit_is_changed(unit, b"ABC\n\0", {}))

    def test_hangul_is_conservatively_a_change_without_allocation(self) -> None:
        unit = {"text": "한글<0A><00>"}
        self.assertTrue(unit_is_changed(unit, b"original\n\0", {}))

    def test_character_map_can_preserve_an_existing_resource(self) -> None:
        unit = {"text": "한<00>"}
        self.assertFalse(unit_is_changed(unit, b"\x8c\x01\0", {"한": b"\x8c\x01"}))


class CapacityOwnershipTests(unittest.TestCase):
    def test_glyph_is_freed_only_when_all_owners_are_selected(self) -> None:
        owners = [frozenset({1, 2}), frozenset({2}), frozenset()]
        self.assertEqual(freed_glyphs(owners, {1}), {2})
        self.assertEqual(freed_glyphs(owners, {1, 2}), {0, 1, 2})

    def test_planner_keeps_mandatory_resources(self) -> None:
        owners = [
            frozenset({1, 2}),
            frozenset({2}),
            frozenset({3}),
        ]
        selected = plan_capacity_resources(owners, {1}, 2, {1, 2, 3})
        self.assertTrue({1, 2} <= selected)
        self.assertGreaterEqual(len(freed_glyphs(owners, selected)), 2)

    def test_planner_never_selects_outside_allowed_range(self) -> None:
        owners = [frozenset({1}), frozenset({4})]
        selected = plan_capacity_resources(owners, {1}, 1, {0, 1, 2})
        self.assertEqual(selected, {1})

    def test_planner_fails_when_target_is_impossible_in_range(self) -> None:
        owners = [frozenset({1}), frozenset({4})]
        with self.assertRaises(CodecError):
            plan_capacity_resources(owners, {1}, 2, {0, 1, 2})


class GlyphSlotOwnershipTests(unittest.TestCase):
    def test_accent_escape_does_not_hide_the_following_real_token(self) -> None:
        # 0x1F <suffix> must be consumed as its own 2-byte unit; the OLD
        # (buggy) scanner treated 0x1F as a plain single byte, which could
        # misalign the cursor onto the following real token and miss it.
        resources = [
            SimpleNamespace(data=custom_token(0) + b"\x00"),
            SimpleNamespace(data=b"\x1f\x90" + custom_token(1) + b"\x00"),
        ]
        owners = glyph_slot_owners(resources, count=3)
        self.assertEqual(owners[0], {0})
        self.assertEqual(owners[1], {1})
        self.assertEqual(owners[2], set())

    def test_scan_stops_at_null_terminator(self) -> None:
        # A token appearing only after the null terminator must not count.
        resources = [SimpleNamespace(data=b"A\x00" + custom_token(0))]
        owners = glyph_slot_owners(resources, count=1)
        self.assertEqual(owners[0], set())

    def test_token_beyond_declared_count_is_ignored(self) -> None:
        resources = [SimpleNamespace(data=custom_token(5) + b"\x00")]
        owners = glyph_slot_owners(resources, count=1)
        self.assertEqual(owners[0], set())

    def test_dead_font_slots_on_a_real_synthetic_record(self) -> None:
        record = GcxRecord(build_synthetic_gcx(glyph_count=3))
        self.assertEqual(dead_font_slots(record, set()), [2])
        # Excluding resource 0 (the sole owner of slot 0) frees slot 0 too.
        self.assertEqual(dead_font_slots(record, {0}), [0, 2])


class DeadSlotReuseBuildTests(unittest.TestCase):
    """End-to-end (bytes-in, bytes-out) proof for --reuse-existing-dead-font:
    output size == input size, font_data_offset/proc_offset unchanged, the
    pre-existing dead slot's bitmap changes, nothing else does."""

    @unittest.skipUnless(MALGUN.is_file(), "requires C:/Windows/Fonts/malgun.ttf")
    def test_new_hangul_lands_in_the_pre_existing_dead_slot(self) -> None:
        source = build_synthetic_gcx(glyph_count=3)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codec_path = tmp_path / "codec.dat"
            codec_path.write_bytes(source)
            translation_path = tmp_path / "translation.json"
            translation_path.write_text(json.dumps({
                "format": "mgs3d-codec-translation-v1",
                "character_map": {},
                "units": [{"gcx": 0, "resource": 0, "kind": "string", "text": "가<00>"}],
            }), encoding="utf-8")
            output_path = tmp_path / "out.dat"

            args = build_parser().parse_args([
                "build-korean", str(codec_path), str(translation_path),
                str(MALGUN), str(output_path),
                "--preserve-file-size", "--reuse-freed-font",
                "--reuse-existing-dead-font",
            ])
            args.function(args)

            output = output_path.read_bytes()
            self.assertEqual(len(output), len(source))
            before = GcxRecord(source)
            after = GcxRecord(output)
            self.assertEqual(before.font_data_offset, after.font_data_offset)
            self.assertEqual(before.proc_offset, after.proc_offset)

            allocation = json.loads(
                (tmp_path / "out.dat.hangul.json").read_text(encoding="utf-8")
            )
            token = bytes.fromhex(allocation["allocations"]["0"]["가"])
            self.assertEqual(token, custom_token(2))  # the pre-existing dead slot
            reuse = allocation["reuse_summary"]
            self.assertEqual(reuse["reused_existing_dead"], 1)
            self.assertEqual(reuse["newly_appended"], 0)
            self.assertEqual(reuse["final_gcx_size_delta"], 0)

            # Only the reused glyph slot's 64 bytes changed in the font
            # section; the untouched glyph payload-size header, and the
            # procedure/bytecode tail, are byte-identical.
            font_start, _ = font_region(before)
            slot2_start = font_start + 2 * GLYPH_SIZE
            slot2_end = slot2_start + GLYPH_SIZE
            self.assertEqual(
                source[before.block_start + before.font_data_offset : slot2_start],
                output[before.block_start + before.font_data_offset : slot2_start],
            )
            self.assertNotEqual(source[slot2_start:slot2_end], output[slot2_start:slot2_end])
            self.assertEqual(
                source[before.block_start + before.proc_offset :],
                output[before.block_start + before.proc_offset :],
            )


class CliTests(unittest.TestCase):
    def test_reuse_existing_dead_font_requires_reuse_freed_font(self) -> None:
        args = build_parser().parse_args([
            "build-korean", "codec.dat", "translation.json", "font.ttf", "out.dat",
            "--reuse-existing-dead-font",
        ])
        self.assertTrue(args.reuse_existing_dead_font)
        self.assertFalse(args.reuse_freed_font)

    def test_dry_run_flag_parses(self) -> None:
        args = build_parser().parse_args([
            "build-korean", "codec.dat", "translation.json", "font.ttf", "out.dat",
            "--reuse-freed-font", "--reuse-existing-dead-font", "--dry-run",
        ])
        self.assertTrue(args.dry_run)

    def test_plan_capacity_parser_accepts_template_output(self) -> None:
        args = build_parser().parse_args([
            "plan-capacity",
            "codec.dat",
            "243",
            "32",
            "366",
            "367",
            "--min-resource",
            "300",
            "--max-resource",
            "440",
            "--template",
            "template.json",
        ])
        self.assertEqual(args.command, "plan-capacity")
        self.assertEqual(args.resources, [366, 367])
        self.assertEqual(args.template, Path("template.json"))

    def test_capacity_parser_supports_strict_check(self) -> None:
        args = build_parser().parse_args([
            "capacity",
            "codec.dat",
            "translation.json",
            "--check",
        ])
        self.assertTrue(args.check)


if __name__ == "__main__":
    unittest.main()
