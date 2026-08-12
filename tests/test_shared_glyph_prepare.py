import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_shared_glyph_prepare import prepare  # noqa: E402


class SharedGlyphPrepareTests(unittest.TestCase):
    def test_preserves_baseline_and_skips_8301(self):
        baseline = {"characters": {"가": "8101", "나": "8102"},
                    "required_hangul": ["가"]}
        result = prepare(baseline, {"codec": ["가나다"], "movie": ["라마"]})
        self.assertEqual(result["characters"]["가"], "8101")
        self.assertEqual(result["characters"]["나"], "8102")
        self.assertNotIn("8301", result["characters"].values())
        self.assertEqual(result["baseline_characters_preserved"], 2)
        self.assertEqual(result["corpus_scopes"]["movie"]["local_hangul"], 0)


if __name__ == "__main__":
    unittest.main()
