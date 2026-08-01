from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_codec_tool import CodecError  # noqa: E402
from mgs3d_gcx_font_tool import (  # noqa: E402
    build_parser,
    freed_glyphs,
    plan_capacity_resources,
    unit_is_changed,
)


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


class CliTests(unittest.TestCase):
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
