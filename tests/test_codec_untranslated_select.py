import importlib.util
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
SPEC = importlib.util.spec_from_file_location(
    "mgs3d_codec_untranslated_select", TOOLS / "mgs3d_codec_untranslated_select.py"
)
review = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review
SPEC.loader.exec_module(review)


class CodecUntranslatedSelectTests(unittest.TestCase):
    def test_priority_rows_skip_only_glyph_overflow(self) -> None:
        rows = [
            {"gcx": 1, "resource": 1, "text": "가나"},
            {"gcx": 1, "resource": 2, "text": "나다"},
            {"gcx": 1, "resource": 3, "text": "라"},
        ]
        chosen, overflow = review.fit_priority_rows({"가"}, rows, 3)
        self.assertEqual([row["resource"] for row in chosen], [1, 2])
        self.assertEqual([row["resource"] for row in overflow], [3])

    def test_translation_keys_omit_donors(self) -> None:
        document = {"units": [
            {"gcx": 1, "resource": 1, "text": "<00>"},
            {"gcx": 1, "resource": 2, "text": "한글<00>"},
        ]}
        self.assertEqual(review.translation_keys(document), {(1, 2)})

    def test_priority_allocation_preserves_tokens_and_evicts_rare_glyph(self) -> None:
        allocation = {
            "characters": {"가": "8101", "나": "8102", "다": "8103"},
            "required_hangul": ["가"],
        }
        baseline = {"units": [
            {"gcx": 1, "resource": 1, "text": "나"},
            {"gcx": 1, "resource": 2, "text": "나"},
            {"gcx": 1, "resource": 3, "text": "다"},
        ]}
        requested = [{"gcx": 2, "resource": 1, "text": "라"}]
        result, swaps = review.priority_preserving_allocation(allocation, baseline, requested)
        self.assertEqual(swaps, [("다", "라")])
        self.assertEqual(result["characters"]["라"], "8103")
        self.assertEqual(result["characters"]["나"], "8102")


if __name__ == "__main__":
    unittest.main()
