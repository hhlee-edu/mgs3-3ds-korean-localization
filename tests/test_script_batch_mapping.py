import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mgs3d_script_compare import anchor_sentence_fragment, is_codec_metadata_preview, propagate_duplicate_approvals, sequence_map_indices, split_words_by_weights, validate_accepted_review_row


class ScriptBatchMappingTests(unittest.TestCase):
    def test_sequence_mapping_is_monotonic(self):
        result = sequence_map_indices([10, 10, 10, 10], [20, 20])
        self.assertEqual([0, 0, 1, 1], result)
        self.assertEqual(sorted(result), result)

    def test_split_preserves_every_word(self):
        parts = split_words_by_weights("하나 둘 셋 넷 다섯", [1, 2, 1])
        self.assertEqual("하나 둘 셋 넷 다섯", " ".join(part for part in parts if part))
        self.assertEqual(3, len(parts))

    def test_empty_inputs(self):
        self.assertEqual([], sequence_map_indices([], [1]))
        self.assertEqual([], sequence_map_indices([1], []))
        self.assertEqual([], split_words_by_weights("text", []))

    def test_translation_rejects_unresolved_contradiction(self):
        row = {"gcx": "0", "resource": "0", "contradictions": "overlap"}
        with self.assertRaisesRegex(ValueError, "unresolved contradictions"):
            validate_accepted_review_row(row, None)

    def test_hashed_review_requires_codec_validation(self):
        row = {"gcx": "0", "resource": "0", "contradictions": "",
               "game_raw_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "provide --codec"):
            validate_accepted_review_row(row, None)

    def test_duplicate_approval_propagates_only_exact_mapping(self):
        rows = [
            {"accept": "yes", "english_sequence": "10", "game_raw_sha256": "abc",
             "korean": "같음", "contradictions": ""},
            {"accept": "", "english_sequence": "10", "game_raw_sha256": "abc",
             "korean": "같음", "contradictions": ""},
            {"accept": "", "english_sequence": "11", "game_raw_sha256": "abc",
             "korean": "다름", "contradictions": ""},
            {"accept": "", "english_sequence": "10", "game_raw_sha256": "abc",
             "korean": "같음", "contradictions": "overlap"},
        ]
        self.assertEqual(1, propagate_duplicate_approvals(rows))
        self.assertEqual("yes", rows[1]["accept"])
        self.assertEqual("", rows[2]["accept"])
        self.assertEqual("", rows[3]["accept"])

    def test_codec_radio_picture_metadata_is_not_dialogue(self):
        self.assertTrue(is_codec_metadata_preview(
            "No:192/264 page:12|radio_picture156|rd_eqi_tnt<END>"))
        self.assertTrue(is_codec_metadata_preview("rd_eqi_sp_m16<END>"))
        self.assertFalse(is_codec_metadata_preview("FPSモ<8312>ドに切り替える<END>"))

    def test_anchor_sentence_extracts_only_matching_fragment(self):
        text = ("백팩을 회수했다. 서바이벌 뷰어에서 BACKPACK의 WEAPON을 선택해라. "
                "목록에서 장비할 무기를 고른다.")
        self.assertEqual(
            "서바이벌 뷰어에서 BACKPACK의 WEAPON을 선택해라.",
            anchor_sentence_fragment(text, "BACKPACK WEAPON"),
        )

    def test_anchor_sentence_refuses_split_anchors(self):
        self.assertEqual("", anchor_sentence_fragment("BACKPACK을 연다. WEAPON을 고른다.", "BACKPACK WEAPON"))


if __name__ == "__main__":
    unittest.main()
