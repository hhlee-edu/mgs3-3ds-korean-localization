#!/usr/bin/env python3
"""Build a per-GCX candidate-value table for reverse-engineering whatever
mechanism the game uses to reference/dispatch codec GCX records, and search
for those values across code.bin/ExeFS/RomFS/codec.dat-non-GCX-regions.

This is a diagnostic tool only — it never writes to any game file.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402


def build_table(codec_path: Path) -> list[dict]:
    data = codec_path.read_bytes()
    records = parse_codec(data)
    rows = []
    for i, rec in enumerate(records):
        next_offset = records[i + 1].source_offset if i + 1 < len(records) else len(data)
        rows.append({
            "index": i,
            "offset": rec.source_offset,
            "size": len(rec.raw),
            "next_offset": next_offset,
            "timestamp": rec.timestamp,
            "seed": rec.seed,
            "proc_table_len": len(rec.proc_table),
            "proc_table_first": rec.proc_table[0] if rec.proc_table else None,
            "proc_table_last": rec.proc_table[-1] if rec.proc_table else None,
            "block_start": rec.block_start,
            "proc_offset": rec.proc_offset,
            "resource_table_offset": rec.resource_table_offset,
            "string_resources_offset": rec.string_resources_offset,
            "font_data_offset": rec.font_data_offset,
        })
    return rows


def main() -> int:
    codec_path = Path("C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/codec.dat")
    out_path = Path("experiments/script_ref/full_build/rebuild_2026-08-08/codec_gcx_candidates.json")
    rows = build_table(codec_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} GCX rows to {out_path}")

    # sanity: alignment check
    misaligned = [r for r in rows if r["offset"] % 0x10]
    print(f"GCX not 0x10-aligned: {len(misaligned)}")
    div0x800 = [r for r in rows if r["offset"] % 0x800 == 0]
    print(f"GCX exactly 0x800-aligned (coincidence check): {len(div0x800)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
