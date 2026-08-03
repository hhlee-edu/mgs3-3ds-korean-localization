import importlib.util
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
SPEC = importlib.util.spec_from_file_location(
    "mgs3d_runtime_language_toggle", TOOLS / "mgs3d_runtime_language_toggle.py"
)
toggle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = toggle
SPEC.loader.exec_module(toggle)


class RuntimeLanguageToggleTests(unittest.TestCase):
    def test_selector_donor_is_not_user_translation(self) -> None:
        donor = {"gcx": 1, "resource": 2, "kind": "string", "text": "<00>"}
        korean = {"gcx": 1, "resource": 3, "kind": "string", "text": "한글<00>"}
        punctuation = {"gcx": 1, "resource": 4, "kind": "string", "text": "...?<00>"}
        self.assertFalse(toggle.is_codec_translation(donor))
        self.assertTrue(toggle.is_codec_translation(korean))
        self.assertTrue(toggle.is_codec_translation(punctuation))

    def test_action_vocabulary(self) -> None:
        self.assertIn("영어", toggle.ENGLISH_ACTIONS)
        self.assertIn("한글", toggle.KOREAN_ACTIONS)
        self.assertNotIn("maybe", toggle.ENGLISH_ACTIONS | toggle.KOREAN_ACTIONS)

    def test_identifiers_are_stable(self) -> None:
        self.assertEqual("codec:1:2", f"codec:{1}:{2}")
        self.assertEqual("movie:1064", f"movie:{1064}")


if __name__ == "__main__":
    unittest.main()
