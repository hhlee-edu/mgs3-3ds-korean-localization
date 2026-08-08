#!/usr/bin/env python3
"""Experiment B: mutate ONLY the inter-GCX alignment padding bytes (the
0-15 zero-fill bytes between a GCX's logical content end and its stored
0x10-aligned end) across the whole file. No offset, size, or resource
content changes at all. If this alone breaks codec, the failure is
checksum/validation-shaped (hypothesis D); if not, that hypothesis drops.

Read-only against the source; writes only to the given output path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, GcxRecord  # noqa: E402


def main() -> int:
    src = Path("C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/codec.dat")
    out = Path("analysis/ps2_korean/full_build/rebuild_2026-08-08/codec_padding_experiment.dat")

    data = bytearray(src.read_bytes())
    records = parse_codec(bytes(data))

    mutated_ranges = []
    for rec in records:
        logical = rec.logical_size()
        stored = len(rec.raw)
        pad_len = stored - logical
        if pad_len <= 0:
            continue
        start = rec.source_offset + logical
        end = rec.source_offset + stored
        for i in range(start, end):
            data[i] = 0xAA
        mutated_ranges.append((rec.source_offset, start, end, pad_len))

    total_mutated_bytes = sum(r[3] for r in mutated_ranges)
    print(f"mutated {len(mutated_ranges)} GCX padding regions, {total_mutated_bytes} bytes total")

    out.write_bytes(bytes(data))

    # verify: reparse, confirm every offset/size identical to source, and that
    # padding bytes really did change
    orig = records
    new = parse_codec(bytes(data))
    assert len(orig) == len(new), "GCX count changed!"
    mismatches = [
        i for i, (o, n) in enumerate(zip(orig, new))
        if o.source_offset != n.source_offset or len(o.raw) != len(n.raw)
    ]
    print(f"offset/size mismatches (should be 0): {len(mismatches)}")
    print(f"output size: {len(data)} (source: {len(src.read_bytes())})")

    import hashlib
    print(f"sha256: {hashlib.sha256(bytes(data)).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
