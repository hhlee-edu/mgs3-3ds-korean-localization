#!/usr/bin/env python3
"""Search all stage/*/scenerio.gcx files for embedded values matching
codec.dat's actual GCX offsets/indices/timestamps, in several candidate
encodings. Read-only diagnostic tool — builds one value->positions index per
file (fast), then looks up all candidate values against it."""

from __future__ import annotations

import json
import struct
from collections import defaultdict
from pathlib import Path

ROMFS = Path("C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs")
CANDIDATES = json.loads(Path(
    "analysis/ps2_korean/full_build/rebuild_2026-08-08/codec_gcx_candidates.json"
).read_text(encoding="utf-8"))


def index_u32le(data: bytes) -> dict[int, list[int]]:
    idx: dict[int, list[int]] = defaultdict(list)
    for i in range(len(data) - 3):
        v = struct.unpack_from("<I", data, i)[0]
        idx[v].append(i)
    return idx


def main() -> int:
    scenerio_files = sorted(ROMFS.glob("stage/**/scenerio.gcx"))
    print(f"scenerio.gcx files: {len(scenerio_files)}")

    candidate_values: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in CANDIDATES:
        candidate_values[row["offset"]].append((row["index"], "abs_offset"))
        candidate_values[row["offset"] // 0x10].append((row["index"], "offset_div10"))
        candidate_values[row["offset"] // 0x20].append((row["index"], "offset_div20"))
        candidate_values[row["offset"] // 0x800].append((row["index"], "offset_div800"))
        candidate_values[row["timestamp"]].append((row["index"], "timestamp"))
        candidate_values[row["seed"]].append((row["index"], "seed"))
    print(f"unique candidate values across all fields: {len(candidate_values)}")

    hits = []
    for f in scenerio_files:
        data = f.read_bytes()
        u32idx = index_u32le(data)
        rel = str(f.relative_to(ROMFS))
        for value, meta in candidate_values.items():
            positions = u32idx.get(value)
            if not positions:
                continue
            for gcx_index, field in meta:
                for pos in positions:
                    hits.append({
                        "file": rel, "byte_offset": pos, "value": value,
                        "gcx": gcx_index, "field": field,
                    })

    print(f"raw hits: {len(hits)}")
    out_path = Path("analysis/ps2_korean/full_build/rebuild_2026-08-08/scenerio_scan_hits.json")
    out_path.write_text(json.dumps(hits, indent=1), encoding="utf-8")
    print(f"wrote {out_path}")

    # summarize by field
    by_field: dict[str, int] = defaultdict(int)
    for h in hits:
        by_field[h["field"]] += 1
    for field, count in sorted(by_field.items(), key=lambda kv: -kv[1]):
        print(f"  {field}: {count} hits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
