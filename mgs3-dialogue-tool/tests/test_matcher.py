import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parents[1] / "mgs3_matcher.py"
SPEC = importlib.util.spec_from_file_location("mgs3_matcher", MODULE_PATH)
MATCHER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MATCHER)


class MatcherTests(unittest.TestCase):
    def test_control_codes_are_removed_but_text_is_preserved(self):
        raw = "スネ<8312>ク<C308>｜BACKPACK<C30A><0A><END>"
        self.assertEqual(MATCHER.clean_japanese(raw), "スネク｜BACKPACK")

    def test_numbered_multiline_records(self):
        source = "380: 一行目<0A>\n二行目<END>\n\n381: 次の行<END>\n"
        records = MATCHER.parse_records(source)
        self.assertEqual([row[0] for row in records], [380, 381])
        self.assertEqual(records[0][2], "一行目 二行目")

    def test_html_pre_extraction(self):
        text = MATCHER.extract_region("<html><pre>A\nB</pre></html>", "pre")
        self.assertEqual(MATCHER.normalized_lines(text), ["A", "B"])

    def test_blog_region_extraction(self):
        source = '<div>skip</div><div class="entry contents_style"><p>백팩</p><p>무기</p></div>'
        text = MATCHER.extract_region(source, "contents_style")
        self.assertEqual(MATCHER.normalized_lines(text), ["백팩", "무기"])

    def test_local_korean_segments_are_grouped_by_page(self):
        parts = MATCHER.korean_segments_by_part([
            {"page": 1, "speaker": "스네이크", "text": "백팩을 연다."},
            {"page": 2, "speaker": "", "text": "무기를 선택한다."},
        ])
        self.assertEqual(parts[1], ["스네이크: 백팩을 연다."])
        self.assertEqual(parts[2], ["무기를 선택한다."])


if __name__ == "__main__":
    unittest.main()
