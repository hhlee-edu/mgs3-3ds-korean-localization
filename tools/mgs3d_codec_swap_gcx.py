#!/usr/bin/env python3
"""Experiment I/P: swap two GCX records' positions via pure list reordering
(codec.dat is a flat sequential concatenation of self-contained GCX blocks —
each GCX's own header offsets are relative to its own block_start, not the
absolute file position, so reordering is structurally clean: no resource
content, header, or internal pointer needs to change at all, only which
byte range each GCX occupies in the final file).

Total file size is automatically preserved (same records, different order).
Read-only against the source; writes only to the given output path.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, CodecError  # noqa: E402


def swap_build(source: Path, gcx_a: int, gcx_b: int, output: Path) -> dict:
    data = source.read_bytes()
    records = parse_codec(data)

    reordered = list(records)
    reordered[gcx_a], reordered[gcx_b] = reordered[gcx_b], reordered[gcx_a]

    output_bytes = b"".join(r.raw for r in reordered)
    if len(output_bytes) != len(data):
        raise CodecError(f"size mismatch after swap: {len(output_bytes)} vs {len(data)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(output_bytes)

    new_records = parse_codec(output_bytes)
    if len(new_records) != len(records):
        raise CodecError("GCX count changed")

    a_old, b_old = records[gcx_a], records[gcx_b]
    a_new, b_new = new_records[gcx_a], new_records[gcx_b]

    # verify: position gcx_a now holds what used to be gcx_b's content (raw bytes match)
    assert a_new.raw == b_old.raw, "slot A does not contain original GCX B content"
    assert b_new.raw == a_old.raw, "slot B does not contain original GCX A content"

    shifted = [i for i, (o, n) in enumerate(zip(records, new_records))
              if o.source_offset != n.source_offset or len(o.raw) != len(n.raw)]

    return {
        "output": str(output),
        "sha256": hashlib.sha256(output_bytes).hexdigest(),
        "total_size": len(output_bytes),
        "gcx_a": gcx_a, "gcx_a_old_offset": a_old.source_offset,
        "gcx_a_new_offset": a_new.source_offset, "gcx_a_size": len(a_old.raw),
        "gcx_b": gcx_b, "gcx_b_old_offset": b_old.source_offset,
        "gcx_b_new_offset": b_new.source_offset, "gcx_b_size": len(b_old.raw),
        "num_gcx_with_offset_change": len(shifted),
        "shifted_range": (shifted[0], shifted[-1]) if shifted else None,
        "content_verified_swapped": True,
    }


if __name__ == "__main__":
    import json
    result = swap_build(
        Path("C:/Users/hhlee/Desktop/Romforge/backups/codec_2026-08-08_120556_pre-growth-experiment.dat"),
        gcx_a=53, gcx_b=1020,
        output=Path("analysis/ps2_korean/full_build/rebuild_2026-08-08/codec_swap_gcx53_gcx1020.dat"),
    )
    print(json.dumps(result, indent=2))
