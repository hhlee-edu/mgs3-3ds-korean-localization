import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mgs3d_text_reassembler import custom_glyph_index, static_character, tokenize  # noqa: E402
from mgs3d_decoder_compare import compare_bytes, conservative_render  # noqa: E402
from mgs3d_japanese_export import load_glyph_map, reconstruct  # noqa: E402
from mgs3d_glyph_catalog import add_reference  # noqa: E402
from mgs3d_glyph_candidates import jis_level1_characters  # noqa: E402


class TextReassemblerTests(unittest.TestCase):
    def test_tokenizer_is_lossless_and_classifies_known_structure(self) -> None:
        raw = b"A\x0a\x80|\x81\x01\x8c\x01\x90\x01\0"
        tokens = tokenize(raw)
        self.assertEqual(b"".join(item.raw for item in tokens), raw)
        self.assertEqual(
            [item.token_class for item in tokens],
            ["ascii", "line-feed", "line-break-807C",
             "page1-hiragana", "page2-glyph-reference",
             "page3-glyph-reference", "terminator"],
        )

    def test_truncated_pair_is_reported_not_dropped(self) -> None:
        tokens = tokenize(b"x\x81")
        self.assertEqual(tokens[-1].token_class, "truncated-pair")
        self.assertEqual(tokens[-1].status, "error")
        self.assertEqual(b"".join(item.raw for item in tokens), b"x\x81")

    def test_conservative_renderer_does_not_claim_provisional_japanese(self) -> None:
        rendered = conservative_render(b"A\x81\x01\x8c\x01\0")
        self.assertEqual(
            rendered,
            "Aぁ<page2-glyph-reference:8C01><END>",
        )

    def test_kana_table_omits_obsolete_wi_and_we(self) -> None:
        self.assertEqual(static_character(b"\x81\x51"), "ん")
        self.assertEqual(static_character(b"\x82\x51"), "ン")
        self.assertEqual(static_character(b"\x82\x52"), "ヴ")
        self.assertEqual(static_character(b"\x82\x54"), "ヶ")

    def test_static_page_flags_preserve_character_identity(self) -> None:
        self.assertEqual(static_character(b"\xc1\x23"), static_character(b"\x81\x23"))
        self.assertEqual(tokenize(b"\xc1\x23")[0].token_class,
                         "page1-hiragana-flags-40")

    def test_confirmed_page83_punctuation_and_layout_glyphs(self) -> None:
        self.assertEqual(static_character(b"\xc3\x08"), "、")
        self.assertEqual(static_character(b"\xc3\x09"), "。")
        self.assertEqual(static_character(b"\x83\x12"), "ー")
        self.assertEqual(static_character(b"\x83\x14"), "…")

    def test_custom_glyph_indices_skip_reserved_xx00_values(self) -> None:
        self.assertEqual(custom_glyph_index(b"\x8c\x01", 2), 0)
        self.assertEqual(custom_glyph_index(b"\x8d\x01", 2), 255)
        self.assertEqual(custom_glyph_index(b"\x90\x01", 3), 0)
        self.assertIsNone(custom_glyph_index(b"\x8d\x00", 2))

    def test_partial_reconstruction_preserves_raw_and_controls(self) -> None:
        raw = b"A\x81\x02\x8c\x01\x80|\0FON"
        result = reconstruct(raw)
        self.assertEqual(bytes.fromhex(result["raw_hex"]), raw)
        self.assertEqual(result["reconstructed"], "Aあ<GLYPH2:0000>\n")
        self.assertEqual([x["kind"] for x in result["controls"]],
                         ["line-break", "terminator"])
        self.assertEqual(len(result["unresolved"]), 1)
        self.assertEqual(result["trailing_raw_hex"], "464F4E")

    def test_confirmed_bitmap_hash_resolves_local_glyph_reference(self) -> None:
        digest = "a" * 64
        result = reconstruct(b"\x8c\x01\0", {(2, 0): digest}, {digest: "下"})
        self.assertEqual(result["reconstructed"], "下")
        self.assertEqual(result["unresolved"], [])

    def test_committed_glyph_map_is_hash_addressed_and_contains_fps_fixture(self) -> None:
        path = Path(__file__).resolve().parents[1] / "tools" / "data" / \
            "mgs3d_japanese_glyphs.json"
        mapping = load_glyph_map(path)
        self.assertEqual(len(mapping), 921)
        self.assertEqual(
            mapping["3bfa4eee88664f710683cb0262ab80e6cd343d18ff2437ec47bf509ad27d2aae"],
            "・",
        )
        self.assertTrue(
            set("下画面右射撃切替可能換上左任意方向攻行出来"
                "使中時動食用手発力北作前武地弾大後彼持所立今本近全東服知思者確移棟女生目取的火効私務勢"
                "庫爆性内味有明破話先常実接同以充特究情受成路療待掛木側空子表放等引決配道速反調流現草付利心達握示")
            <= set(mapping.values()),
        )

    def test_button_markup_delimiters_are_controls_not_visible_text(self) -> None:
        raw = b"\x80#\xa0{\xa3\x1e\x805\xc3\x08X\xc0}\x80#\0"
        result = reconstruct(raw)
        self.assertNotIn("#{", result["reconstructed"])
        self.assertNotIn("}#", result["reconstructed"])
        self.assertEqual([x["kind"] for x in result["controls"][:2]],
                         ["markup-hash-delimiter", "markup-open"])

    def test_glyph_catalog_deduplicates_by_bitmap_not_local_slot(self) -> None:
        catalog = {}
        glyph = bytes(range(64))
        add_reference(catalog, glyph, {"container": "codec", "gcx": 1, "slot": 2}, 3)
        add_reference(catalog, glyph, {"container": "movie", "record": 4, "slot": 9}, 5)
        item = next(iter(catalog.values()))
        self.assertEqual(item["occurrences"], 8)
        self.assertEqual(item["reference_count"], 2)
        self.assertEqual(item["containers"], {"codec", "movie"})

    def test_glyph_candidate_repertoire_is_deterministic_and_common_kanji(self) -> None:
        characters = jis_level1_characters()
        self.assertEqual(len(characters), len(set(characters)))
        self.assertIn("下", characters)
        self.assertIn("撃", characters)

    def test_comparison_records_matcher_information_loss(self) -> None:
        result = compare_bytes(b"\x8c\x01\0")
        self.assertEqual(result["shared_decoder_disposition"], "confirmed-same-function")
        self.assertEqual(result["matcher_disposition"], "unsupported-as-decoder")
        self.assertIn("matcher removes angle-bracket token output", result["disagreements"])

    def test_comparison_marks_legacy_kana_drift_as_corrected(self) -> None:
        result = compare_bytes(b"\x82\x51")
        self.assertEqual(result["outputs"]["codec"], "ヱ")
        self.assertEqual(result["outputs"]["conservative"], "ン")
        self.assertEqual(result["legacy_semantic_disposition"], "corrected")


if __name__ == "__main__":
    unittest.main()
