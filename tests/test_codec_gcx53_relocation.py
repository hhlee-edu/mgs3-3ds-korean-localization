from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_codec_tool import (  # noqa: E402
    CodecError,
    GcxRecord,
    relocate_gcx_internal_offsets,
    relocate_gcx53_inner_offsets,
)


def make_record() -> GcxRecord:
    record = GcxRecord.__new__(GcxRecord)
    record.proc_table = [0] * 32
    record.proc_table[24] = 0x2000104E  # raw +0x64
    record.proc_table[27] = 0x2000108A  # raw +0x70
    record.proc_table[30] = 0x200010B3  # raw +0x7C
    raw = bytearray(0x90)
    for index, word in enumerate(record.proc_table):
        struct.pack_into("<I", raw, 4 + index * 4, word)
    record.raw = bytes(raw)
    return record


class Gcx53RelocationTests(unittest.TestCase):
    def test_generic_fixer_relocates_all_targets_at_boundary(self) -> None:
        record = make_record()
        relocated = relocate_gcx_internal_offsets(record, 0x1000, 0x1020)

        self.assertEqual(struct.unpack_from("<I", relocated, 0x64)[0], 0x2000106E)
        self.assertEqual(struct.unpack_from("<I", relocated, 0x70)[0], 0x200010AA)
        self.assertEqual(struct.unpack_from("<I", relocated, 0x7C)[0], 0x200010D3)

    def test_generic_fixer_supports_negative_delta(self) -> None:
        record = make_record()
        relocated = relocate_gcx_internal_offsets(record, 0x1000, 0x0FF0)

        self.assertEqual(struct.unpack_from("<I", relocated, 0x64)[0], 0x2000103E)

    def test_relocates_only_three_inner_offsets_and_preserves_flags(self) -> None:
        record = make_record()
        relocated = relocate_gcx53_inner_offsets(record, 0x10)

        self.assertEqual(struct.unpack_from("<I", relocated, 0x64)[0], 0x2000105E)
        self.assertEqual(struct.unpack_from("<I", relocated, 0x70)[0], 0x2000109A)
        self.assertEqual(struct.unpack_from("<I", relocated, 0x7C)[0], 0x200010C3)
        self.assertEqual(relocated[:0x64], record.raw[:0x64])

    def test_rejects_unexpected_inner_offset_layout(self) -> None:
        record = make_record()
        record.proc_table[1] = 0x10002000

        with self.assertRaisesRegex(CodecError, "unexpected GCX53 inner-offset fields"):
            relocate_gcx53_inner_offsets(record, 0x10)


if __name__ == "__main__":
    unittest.main()
