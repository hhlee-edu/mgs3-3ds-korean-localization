import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from dotnet_bundle_extract import seven_bit_int


class DotnetBundleExtractTests(unittest.TestCase):
    def test_reads_binary_writer_7bit_integer(self):
        self.assertEqual(seven_bit_int(b"\x7f", 0), (127, 1))
        self.assertEqual(seven_bit_int(b"\x80\x01", 0), (128, 2))


if __name__ == "__main__":
    unittest.main()
