import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_review_translation import active_relation_map, target_rows  # noqa: E402


class ReviewTranslationTests(unittest.TestCase):
    def test_last_active_relation_owns_duplicate_left_id(self):
        state = {"relations": [
            {"id": "old", "decision": "match", "left_ids": ["x"]},
            {"id": "new", "decision": "match", "left_ids": ["x"], "active": True},
        ]}
        selected, duplicates = active_relation_map(state)
        self.assertEqual(selected["x"]["id"], "new")
        self.assertEqual(duplicates["x"], ["old", "new"])

    def test_target_rows_preserve_existing_korean_and_overrides(self):
        html = {
            "ROWS": [
                {"id": "a", "type": "movie", "group": 0, "offset": 1,
                 "english": "A", "korean": "기존"},
                {"id": "b", "type": "movie", "group": 0, "offset": 2,
                 "english": "B", "korean": ""},
                {"id": "c", "type": "movie", "group": 0, "offset": 3,
                 "english": "C", "korean": ""},
            ],
            "SCRIPT": [{"index": 7, "english": "B", "korean": "공식"}],
        }
        state = {
            "relations": [{"id": "r", "decision": "match", "left_ids": ["a", "b", "c"],
                           "right_sequences": [7]}],
            "translation_overrides": {"c": "수정"},
        }
        rows, _ = target_rows(html, state)
        self.assertEqual([row["id"] for row in rows], ["b"])
        self.assertEqual(rows[0]["ref_ko"], "공식")


if __name__ == "__main__":
    unittest.main()
