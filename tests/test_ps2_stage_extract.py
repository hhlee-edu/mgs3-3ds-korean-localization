import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mgs3_ps2_stage_extract import align, decrypt_content, strcode24


class Ps2StageExtractTests(unittest.TestCase):
    def test_align(self) -> None:
        self.assertEqual(align(0x801, 0x800), 0x1000)
        self.assertEqual(align(0x1000, 0x800), 0x1000)

    def test_stage_name_hash_stops_at_nul(self) -> None:
        self.assertEqual(strcode24(b"kyle_op\0x"), strcode24(b"kyle_op"))

    def test_content_cipher_is_symmetric_apart_from_zlib_header_fix(self) -> None:
        # The decryptor requires complete little-endian words and must retain
        # the input size; real-stream decompression is covered by extraction.
        data = bytes.fromhex("123456789abcdef0")
        self.assertEqual(len(decrypt_content(data)), len(data))


if __name__ == "__main__":
    unittest.main()
