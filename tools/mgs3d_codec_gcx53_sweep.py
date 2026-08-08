#!/usr/bin/env python3
"""Part 2: sweep GCX53's start-offset delta (+0x10 .. +0x800) with GCX53's
own content and size held byte-identical, and everything from GCX54 onward
restored to its original position. Uses mgs3d_codec_precise_relocate for
exact byte control (no translation/glyph involvement at all).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_precise_relocate import build  # noqa: E402
from mgs3d_codec_tool import parse_codec  # noqa: E402

SOURCE = Path("C:/Users/hhlee/Desktop/Romforge/backups/codec_2026-08-08_120556_pre-growth-experiment.dat")
OUT_DIR = Path("analysis/ps2_korean/full_build/rebuild_2026-08-08")

DELTAS = [0x10, 0x20, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800]


def main() -> int:
    orig = parse_codec(SOURCE.read_bytes())
    gcx53_orig = orig[53]
    gcx53_old_start = gcx53_orig.source_offset
    gcx53_old_end = gcx53_old_start + len(gcx53_orig.raw)

    manifest = []
    for delta in DELTAS:
        name = f"codec_gcx53_shift_{delta:04x}.dat"
        out_path = OUT_DIR / name
        result = build(SOURCE, grow_gcx=52, grow_delta=delta, shrink_gcx=54,
                      shrink_donor_resource=524, output=out_path)

        new_records = parse_codec(out_path.read_bytes())
        gcx53_new = new_records[53]
        new_start = gcx53_new.source_offset
        new_end = new_start + len(gcx53_new.raw)

        entry = {
            "file": name,
            "sha256": result["sha256"],
            "total_size": result["total_size"],
            "gcx53_old_start": gcx53_old_start,
            "gcx53_new_start": new_start,
            "gcx53_old_end": gcx53_old_end,
            "gcx53_new_end": new_end,
            "delta": new_start - gcx53_old_start,
            "gcx53_content_identical": gcx53_orig.raw == gcx53_new.raw,
            "gcx_with_any_change": result["gcx_with_offset_or_size_change"],
        }
        for boundary in (0x200, 0x400, 0x800, 0x1000):
            old_sec = gcx53_old_start // boundary
            new_sec = new_start // boundary
            entry[f"crossed_0x{boundary:x}"] = old_sec != new_sec
        manifest.append(entry)
        print(f"{name}: delta={entry['delta']:+d}  content_identical={entry['gcx53_content_identical']}  "
              f"crossed_0x800={entry['crossed_0x800']}  crossed_0x1000={entry['crossed_0x1000']}  "
              f"sha256={entry['sha256'][:16]}...")

    manifest_path = OUT_DIR / "gcx53_sweep_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
