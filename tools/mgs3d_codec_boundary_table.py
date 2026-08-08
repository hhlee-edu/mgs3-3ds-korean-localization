#!/usr/bin/env python3
"""Part 1: detailed offset/alignment/sector boundary table for specific GCX,
comparing original vs a relocated build. Read-only diagnostic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402

MODS = (0x10, 0x20, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800, 0x1000)
DIVS = (0x200, 0x400, 0x800, 0x1000)


def describe(label: str, rec) -> list[str]:
    start = rec.source_offset
    size = len(rec.raw)
    end = start + size
    lines = [f"[{label}] start={start} (0x{start:x})  size={size}  end={end} (0x{end:x})"]
    for m in MODS:
        lines.append(f"    start %% 0x{m:<4x} = {start % m:<6}  end %% 0x{m:<4x} = {end % m}")
    for d in DIVS:
        start_sector = start // d
        end_sector = (end - 1) // d
        lines.append(f"    sector(0x{d:x}): start={start_sector}  end={end_sector}  "
                     f"spans={end_sector - start_sector + 1} sector(s)")
    return lines


def main() -> int:
    orig = parse_codec(Path(
        "C:/Users/hhlee/Desktop/Romforge/backups/codec_2026-08-08_120556_pre-growth-experiment.dat"
    ).read_bytes())
    new36 = parse_codec(Path(
        "analysis/ps2_korean/full_build/rebuild_2026-08-08/codec_bisect8_test.dat"
    ).read_bytes())  # 36-shift, PASSED
    new37 = parse_codec(Path(
        "analysis/ps2_korean/full_build/rebuild_2026-08-08/codec_bisect9_test.dat"
    ).read_bytes())  # 37-shift, CRASHED

    out: list[str] = []
    for gcx in (52, 53, 54):
        out.append(f"===== GCX {gcx} =====")
        out.extend(describe("original", orig[gcx]))
        out.extend(describe("36-shift build (PASSED)", new36[gcx]))
        out.extend(describe("37-shift build (CRASHED)", new37[gcx]))
        out.append("")

    # explicit boundary-crossing comparison for GCX53 orig -> 37-shift
    o = orig[53]
    n = new37[53]
    out.append("===== GCX53 original -> 37-shift: boundary crossings =====")
    for d in DIVS:
        o_start_sec = o.source_offset // d
        o_end_sec = (o.source_offset + len(o.raw) - 1) // d
        n_start_sec = n.source_offset // d
        n_end_sec = (n.source_offset + len(n.raw) - 1) // d
        out.append(f"0x{d:x}: orig sectors [{o_start_sec},{o_end_sec}] -> "
                   f"new sectors [{n_start_sec},{n_end_sec}]  "
                   f"start_sector_changed={o_start_sec != n_start_sec}  "
                   f"end_sector_changed={o_end_sec != n_end_sec}")

    out.append("")
    out.append("===== same comparison, GCX52 original -> 36-shift (control, PASSED) =====")
    o = orig[52]
    n = new36[52]
    for d in DIVS:
        o_start_sec = o.source_offset // d
        o_end_sec = (o.source_offset + len(o.raw) - 1) // d
        n_start_sec = n.source_offset // d
        n_end_sec = (n.source_offset + len(n.raw) - 1) // d
        out.append(f"0x{d:x}: orig sectors [{o_start_sec},{o_end_sec}] -> "
                   f"new sectors [{n_start_sec},{n_end_sec}]  "
                   f"start_sector_changed={o_start_sec != n_start_sec}  "
                   f"end_sector_changed={o_end_sec != n_end_sec}")

    text = "\n".join(out)
    out_path = Path("analysis/ps2_korean/full_build/rebuild_2026-08-08/gcx53_boundary_table.txt")
    out_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
