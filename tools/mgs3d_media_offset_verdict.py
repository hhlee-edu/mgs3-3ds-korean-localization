#!/usr/bin/env python3
"""Consolidate the movie/demo `translation_source = offset` audit into one sheet.

Three inputs, in decreasing authority:

  1. line-by-line reading, recorded in `docs/evidence/2026-08-19-media-qa/verdicts.py`
  2. `media-offset-alignment.csv` -- the LIS screening signal over the aligner's
     own `english_sequence` / `korean_sequence` pair
  3. `media-offset-audit.csv` -- text tracing through the comparison tables

Reading wins wherever it exists. The screening signal is carried as a priority
hint for the rows nobody has read yet, never as a verdict: measured against the
read rows it recalls 94% but flags 82% of the population, so it can say "look
here next" and cannot say "this one is wrong".

READ-ONLY.

Usage:
  python tools/mgs3d_media_offset_verdict.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parent.parent
MASTERS = ROOT / "translation/10_master/current"
VERDICTS = ROOT / "docs/evidence/2026-08-19-media-qa/verdicts.py"
# Every line carrying the script reference table's space-before-punctuation was read in
# its record's context on 2026-08-19; that set is what "reviewed" means below.
PUNCT_SPACE = re.compile(r"[ \t]+(?=[.!?,…])")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text or "").replace("|", " ")).strip()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/evidence/2026-08-19-media-offset-audit")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)

    verdicts = load_module(VERDICTS)
    misplaced = set(verdicts.MISMAPPED)
    read_ok = {key for keys in verdicts.REGISTER_KEEP.values() for key in keys}
    read_ok |= {(m, r, e) for m, r, e, *_ in verdicts.REGISTER_FIX}

    screen = {}
    path = args.outdir / "media-offset-alignment.csv"
    if path.exists():
        with io.open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                screen[(row["media"], int(row["record"]), int(row["entry"]))] = row

    traced = {}
    path = args.outdir / "media-offset-audit.csv"
    if path.exists():
        with io.open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                traced[(row["media"], int(row["record"]), int(row["entry"]))] = row

    rows = []
    for media in ("movie", "demo"):
        with io.open(MASTERS / f"{media}.csv", encoding="utf-8-sig", newline="") as handle:
            for item in csv.DictReader(handle):
                if item["translation_source"] != "offset":
                    continue
                key = (media, int(item["record"]), int(item["entry"]))
                korean = item["korean"] or ""
                reviewed = (key in misplaced or key in read_ok
                            or bool(PUNCT_SPACE.search(clean(korean))))
                if key in misplaced:
                    verdict, basis = "MISPLACED", "read in record context 2026-08-19"
                elif reviewed:
                    verdict, basis = "KEEP", "read in record context 2026-08-19"
                else:
                    verdict, basis = "UNREVIEWED", ""
                flag = screen.get(key, {})
                trace = traced.get(key, {})
                rows.append({
                    "media": media, "record": key[1], "entry": key[2],
                    "verdict": verdict, "basis": basis,
                    "screen_off_backbone": flag.get("on_backbone", "") == "False",
                    "aligner_status": flag.get("status", ""),
                    "en_seq": flag.get("en_seq", ""), "ko_seq": flag.get("ko_seq", ""),
                    "expected_ko_seq_low": flag.get("expected_ko_seq_low", ""),
                    "expected_ko_seq_high": flag.get("expected_ko_seq_high", ""),
                    "trace_source_english": trace.get("source_english", ""),
                    "trace_belongs_to": trace.get("belongs_to", ""),
                    "english": clean(item["preview"]), "korean": korean,
                })
    rows.sort(key=lambda r: (r["media"], r["record"], r["entry"]))

    fields = list(rows[0].keys())
    out = args.outdir / "media-offset-verdicts.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    unreviewed = [r for r in rows if r["verdict"] == "UNREVIEWED"]
    priority = [r for r in unreviewed if r["screen_off_backbone"]]
    summary = {
        "offset_rows_total": len(rows),
        "by_verdict": dict(Counter(r["verdict"] for r in rows).most_common()),
        "by_media": {m: dict(Counter(r["verdict"] for r in rows if r["media"] == m)
                             .most_common()) for m in ("movie", "demo")},
        "remap_resolved": 0,
        "remap_blocked_reason":
            "the aligner's `korean_sequence` indexes an intermediate Korean list that "
            "was not preserved; it resolves against neither script_ref_mgs3_script.csv "
            "(30/366) nor the classified/movie-demo subsets (0/366), so the correct "
            "Korean cannot be read off an index",
        "next_session_start": {
            "unreviewed": len(unreviewed),
            "priority_first": len(priority),
            "priority_range": (f'{priority[0]["media"]} r{priority[0]["record"]} '
                               f'e{priority[0]["entry"]}') if priority else "",
        },
    }
    (args.evidence / "offset-verdict-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
