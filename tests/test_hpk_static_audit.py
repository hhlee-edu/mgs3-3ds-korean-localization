from __future__ import annotations

import struct
import sys
import unittest
import zlib
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_hpk_static_audit import (  # noqa: E402
    DEFAULT_KEY,
    parse_static_entries,
    scenario_residents,
)


class HpkStaticAuditTests(unittest.TestCase):
    def test_finds_valid_entry_and_resident_references(self) -> None:
        unpacked = b"font data"
        packed = zlib.compress(unpacked)
        data = (b"prefix" + DEFAULT_KEY
                + struct.pack("<II", len(unpacked), len(packed)) + packed)
        entries = parse_static_entries(data, "fixture.hpk")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["unpacked_size"], len(unpacked))
        self.assertEqual(scenario_residents(b"x r_sna01 y r_sna02 z"), [
            "r_sna01", "r_sna02",
        ])

    def test_rejects_invalid_compressed_entry(self) -> None:
        data = DEFAULT_KEY + struct.pack("<II", 4, 4) + b"nope"
        with self.assertRaisesRegex(ValueError, "invalid HPK zlib entry"):
            parse_static_entries(data, "bad.hpk")


if __name__ == "__main__":
    unittest.main()
