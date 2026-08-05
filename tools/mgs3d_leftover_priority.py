#!/usr/bin/env python3
"""Reprioritize the PS2대응없음 leftover translator worklist by realistic
build headroom instead of raw unique-vocabulary count.

Splits leftover rows into three buckets using per-GCX figures from a
`mgs3d_codec_size_neutral_select.py --report` document:

- `A_no_donor`: the GCX has zero reclaimable donor bytes at all. Even a
  single new Hangul glyph (64 bytes) has no budget to draw from, so
  shortening the translation cannot help without a structural change to
  record layout. Placed last, flagged for skipping.
- `B_donor_but_unselected`: the GCX has donor headroom but nothing currently
  fits. Ranked by `glyph_deficit_bytes` ascending - the number of *distinct*
  new Hangul characters this GCX's leftover text still needs, times 64,
  minus the donor budget. This is the real bottleneck (glyph diversity, not
  string length): a record's new-glyph cost is charged against the same
  local byte budget as its string content, and per-GCX glyph slot capacity
  (1,020) is never the limiting factor in practice.
- `C_partial`: some candidates in the GCX already landed. Ranked by
  `excluded` ascending - these are closest to full completion.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

BUCKET_ORDER = {"C_partial": 0, "B_donor_but_unselected": 1, "A_no_donor": 2}
NO_DONOR_NOTE = "도너 자료 없음 — 새 글자 1개조차 예산 없음, skip 권장"


def hangul_chars(text: str) -> set[str]:
    return {ch for ch in text if 0xAC00 <= ord(ch) <= 0xD7A3}


def load_report(path: Path) -> dict[int, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return {int(row["gcx"]): row for row in document["records"]}


def classify(gcx_rows: list[dict], info: dict) -> dict[str, object]:
    donor_savings = int(info["donor_savings"])
    selected = int(info["selected"])
    excluded = int(info["excluded"])
    if donor_savings == 0:
        return {"bucket": "A_no_donor", "donor_savings": donor_savings,
                "excluded": excluded, "glyph_deficit": None}
    if selected == 0:
        chars: set[str] = set()
        for row in gcx_rows:
            chars |= hangul_chars(row["current_korean"])
        glyph_deficit = max(0, len(chars) * 64 - donor_savings)
        return {"bucket": "B_donor_but_unselected", "donor_savings": donor_savings,
                "excluded": excluded, "glyph_deficit": glyph_deficit}
    return {"bucket": "C_partial", "donor_savings": donor_savings,
            "excluded": excluded, "glyph_deficit": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path,
                        help="select_report JSON (per-GCX candidates/selected/donor_savings)")
    parser.add_argument("worklist", type=Path,
                        help="existing translator worklist CSV to reprioritize")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    csv.field_size_limit(2 ** 31 - 1)
    report = load_report(args.report)

    with args.worklist.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    by_gcx: dict[int, list[dict]] = {}
    for row in rows:
        by_gcx.setdefault(int(row["gcx"]), []).append(row)

    missing = sorted(gcx for gcx in by_gcx if gcx not in report)
    if missing:
        raise SystemExit(f"GCX in worklist but missing from report: {missing[:10]}")

    gcx_meta = {gcx: classify(gcx_rows, report[gcx]) for gcx, gcx_rows in by_gcx.items()}

    def gcx_sort_key(gcx: int) -> tuple[int, int, int]:
        meta = gcx_meta[gcx]
        bucket = meta["bucket"]
        if bucket == "C_partial":
            secondary = meta["excluded"]
        elif bucket == "B_donor_but_unselected":
            secondary = meta["glyph_deficit"]
        else:
            secondary = 0
        return (BUCKET_ORDER[bucket], secondary, gcx)

    ordered_gcx = sorted(by_gcx, key=gcx_sort_key)

    out_fieldnames = [name for name in fieldnames if name != "priority_rank"]
    out_fieldnames = ["priority_rank"] + out_fieldnames
    for extra in ("bucket", "donor_savings_bytes", "glyph_deficit_bytes", "note"):
        if extra not in out_fieldnames:
            out_fieldnames.append(extra)

    out_rows = []
    for rank, gcx in enumerate(ordered_gcx, start=1):
        meta = gcx_meta[gcx]
        note = NO_DONOR_NOTE if meta["bucket"] == "A_no_donor" else ""
        for row in by_gcx[gcx]:
            new_row = dict(row)
            new_row["priority_rank"] = rank
            new_row["bucket"] = meta["bucket"]
            new_row["donor_savings_bytes"] = meta["donor_savings"]
            new_row["glyph_deficit_bytes"] = (meta["glyph_deficit"]
                                              if meta["glyph_deficit"] is not None else "")
            new_row["note"] = note
            out_rows.append(new_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    row_counts = Counter(gcx_meta[gcx]["bucket"] for gcx in by_gcx for _ in by_gcx[gcx])
    gcx_counts = Counter(meta["bucket"] for meta in gcx_meta.values())
    print(f"reordered {len(out_rows)} rows across {len(by_gcx)} GCX -> {args.output}")
    for bucket in ("C_partial", "B_donor_but_unselected", "A_no_donor"):
        print(f"  {bucket}: {gcx_counts[bucket]} GCX / {row_counts[bucket]} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
