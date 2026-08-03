import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mgs3_ps2_stage_text_catalog import decode_text, token_index


class Ps2StageTextCatalogTests(unittest.TestCase):
    def test_decode_static_local_ascii_and_controls(self) -> None:
        decoded, local, unknown = decode_text(
            bytes.fromhex("8101208c01410a820100"), {"8101": "가"}
        )
        self.assertEqual(decoded, "가 <L000>A\n<S8201>")
        self.assertEqual((local, unknown), (1, 1))

    def test_local_index_skips_zero_low_bytes(self) -> None:
        self.assertEqual(token_index(0x8C01, 0x8C01), 0)
        self.assertEqual(token_index(0x8D01, 0x8C01), 255)


if __name__ == "__main__":
    unittest.main()
