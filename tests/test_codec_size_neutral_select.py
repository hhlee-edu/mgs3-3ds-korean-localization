from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_codec_size_neutral_select import (  # noqa: E402
    balance,
    confident_non_english_language,
    custom_token,
    glyph_slot_owners,
    language_block_donors,
    select_subset,
    select_subset_exact,
    zero_slot_cardinality_bound,
)


class CodecSizeNeutralSelectionTests(unittest.TestCase):
    def test_zero_slot_bound_is_exact_cardinality_knapsack(self) -> None:
        items = [
            {"saving": -8, "glyphs": set()},
            {"saving": -3, "glyphs": set()},
            {"saving": 1, "glyphs": set()},
            {"saving": 100, "glyphs": {"가"}},
        ]
        self.assertEqual(zero_slot_cardinality_bound(items, 9), 2)

    def test_shared_glyph_cost_is_paid_once(self) -> None:
        items = [
            {"saving": 40, "glyphs": frozenset("한")},
            {"saving": 30, "glyphs": frozenset("한")},
        ]
        self.assertEqual(balance(items, {0, 1}), (6, 70, 1))
        self.assertEqual(select_subset(items), {0, 1})

    def test_donor_savings_can_fund_translation(self) -> None:
        items = [{"saving": 0, "glyphs": frozenset("한글")}]
        self.assertEqual(select_subset(items), set())
        self.assertEqual(select_subset(items, base_savings=128), {0})

    def test_priority_translation_displaces_ordinary_translation(self) -> None:
        items = [
            {"saving": 0, "glyphs": frozenset("가"), "priority": True},
            {"saving": 0, "glyphs": frozenset("나"), "priority": False},
        ]
        self.assertEqual(select_subset(items, base_savings=64), {0})

    def test_selector_refills_capacity_after_priority_removal(self) -> None:
        items = [
            {"saving": 0, "glyphs": frozenset("a"), "priority": True},
            {"saving": 0, "glyphs": frozenset("b"), "priority": False},
            {"saving": 0, "glyphs": frozenset("a"), "priority": False},
        ]
        self.assertEqual(select_subset(items, base_savings=64), {0, 2})

    def test_exact_selector_prefers_more_rows_over_one_priority_row(self) -> None:
        items = [
            {"saving": 0, "glyphs": frozenset("a"), "priority": False, "resource": 1},
            {"saving": 0, "glyphs": frozenset("a"), "priority": False, "resource": 2},
            {"saving": 0, "glyphs": frozenset("bc"), "priority": True, "resource": 0},
        ]
        self.assertEqual(select_subset_exact(items, base_savings=64), {0, 1})

    def test_exact_selector_prefers_priority_at_equal_cardinality(self) -> None:
        items = [
            {"saving": 0, "glyphs": frozenset("a"), "priority": False, "resource": 1},
            {"saving": 0, "glyphs": frozenset("b"), "priority": True, "resource": 2},
        ]
        self.assertEqual(select_subset_exact(items, base_savings=64), {1})

    def test_language_classifier_accepts_spanish_and_french(self) -> None:
        spanish = b"El enemigo te espera en el lago y no puedes volver por aqui."
        french = b"Si un ennemi est dans la base, il ne faut pas rester avec lui."
        english = b"The enemy is waiting for you at the lake and you must go now."
        self.assertEqual(confident_non_english_language(spanish), "es")
        self.assertEqual(confident_non_english_language(french), "fr")
        self.assertIsNone(confident_non_english_language(english))

    def test_language_block_reclaims_short_strings_between_safe_anchors(self) -> None:
        resources = [
            SimpleNamespace(data=b"The enemy is waiting for you and this is the mission.", is_script=False),
            SimpleNamespace(data=b"El enemigo te espera en el lago y no puedes volver por aqui.", is_script=False),
            SimpleNamespace(data=b"Si?", is_script=False),
            SimpleNamespace(data=b"Oui?", is_script=False),
            SimpleNamespace(data=b"Si un ennemi est dans la base, il ne faut pas rester avec lui.", is_script=False),
        ]
        self.assertEqual(language_block_donors(resources, set()), [1, 2, 3, 4])
        self.assertEqual(language_block_donors(resources, {2}), [1, 3, 4])

    def test_language_block_preserves_explicitly_protected_english(self) -> None:
        resources = [
            SimpleNamespace(data=b"El enemigo te espera en el lago y no puedes volver por aqui.", is_script=False),
            SimpleNamespace(data=b"The enemy is waiting for you and this is the mission.", is_script=False),
            SimpleNamespace(data=b"Si un ennemi est dans la base, il ne faut pas rester avec lui.", is_script=False),
        ]
        self.assertEqual(language_block_donors(resources, {1}), [0, 2])

    def test_glyph_slot_owners_is_imported_from_its_new_home(self) -> None:
        # glyph_slot_owners moved to mgs3d_gcx_font_tool.py (2026-08-09, fixed
        # the missing 0x1F accent-escape case there); this module now just
        # re-exports it. Lock in that the accent-escape fix is visible here too.
        resources = [SimpleNamespace(data=b"\x1f\x90" + custom_token(0) + b"\x00")]
        owners = glyph_slot_owners(resources, count=1)
        self.assertEqual(owners[0], {0})


if __name__ == "__main__":
    unittest.main()
