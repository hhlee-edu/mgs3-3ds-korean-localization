#!/usr/bin/env python3
"""Locate the alignment failure behind the movie/demo mis-placed Korean.

The 514 master rows with `translation_source = offset` were filled from
`20_matching/en_{demo,movie}_korean_matches.csv`. That table is **not**
independent evidence about them -- it is where they came from, so it agrees with
the master on every single one. What it does carry is the pair of sequence
indices the aligner used: `english_sequence` and `korean_sequence`.

A correct alignment walks both scripts forward together, so `korean_sequence`
must increase as `english_sequence` does. Where the aligner used
`match_status = exact-unique-korean` it instead searched for a Korean line whose
*text* was unique, which for short lines ("그래 ?", "몰라 .", "음 .") latches onto an
arbitrary occurrence and throws the index anywhere in the script.

So the backbone of the real alignment is the **longest increasing subsequence**
of `korean_sequence` ordered by `english_sequence`. Rows on it are consistent
with a monotone walk through both scripts; rows off it are the aligner jumping.
For an off-backbone row the correct `korean_sequence` can be bracketed by its
backbone neighbours, which both bounds the answer and says how tight the bound is.

READ-ONLY. Writes an audit CSV and a summary; touches nothing else.

Usage:
  python tools/mgs3d_media_offset_align.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
import bisect
import csv
import importlib.util
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parent.parent
MASTERS = ROOT / "translation/10_master/current"
MATCHING = ROOT / "translation/20_matching"
VERDICTS = ROOT / "docs/evidence/2026-08-19-media-qa/verdicts.py"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text or "").replace("|", " ")).strip()


def longest_increasing(values: list[int]) -> list[int]:
    """Indices of a longest strictly-increasing subsequence."""
    tails: list[int] = []
    tail_index: list[int] = []
    previous = [-1] * len(values)
    for i, value in enumerate(values):
        position = bisect.bisect_left(tails, value)
        if position == len(tails):
            tails.append(value)
            tail_index.append(i)
        else:
            tails[position] = value
            tail_index[position] = i
        previous[i] = tail_index[position - 1] if position else -1
    result = []
    cursor = tail_index[-1] if tail_index else -1
    while cursor != -1:
        result.append(cursor)
        cursor = previous[cursor]
    return result[::-1]


def load_hand_verdicts() -> set:
    if not VERDICTS.exists():
        return set()
    spec = importlib.util.spec_from_file_location("media_qa_verdicts", VERDICTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(getattr(module, "MISMAPPED", []))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/evidence/2026-08-19-media-offset-audit")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)

    hand = load_hand_verdicts()

    master = {}
    for media in ("movie", "demo"):
        with io.open(MASTERS / f"{media}.csv", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                master[(media, int(row["record"]), int(row["entry"]))] = row

    results = []
    ko_text = {}
    for media in ("movie", "demo"):
        path = MATCHING / f"en_{media}_korean_matches.csv"
        with io.open(path, encoding="utf-8-sig", newline="") as handle:
            table = list(csv.DictReader(handle))
        rows = []
        for row in table:
            if not (row.get("english_sequence") or "").strip():
                continue
            if not (row.get("korean_sequence") or "").strip():
                continue
            rows.append({
                "media": media,
                "record": int(row["record"]), "entry": int(row["entry"]),
                "en_seq": int(row["english_sequence"]),
                "ko_seq": int(row["korean_sequence"]),
                "english": clean(row.get("english")),
                "korean": clean(row.get("korean")),
                "status": row.get("match_status") or "",
                "candidates": row.get("candidate_count") or "",
            })
        rows.sort(key=lambda r: r["en_seq"])
        for row in rows:
            if row["korean"]:
                ko_text.setdefault((media, row["ko_seq"]), row["korean"])
        backbone = set(longest_increasing([r["ko_seq"] for r in rows]))
        anchors = [(rows[i]["en_seq"], rows[i]["ko_seq"]) for i in sorted(backbone)]
        anchor_en = [a[0] for a in anchors]

        for index, row in enumerate(rows):
            key = (row["media"], row["record"], row["entry"])
            on_backbone = index in backbone
            expected_low = expected_high = ""
            if not on_backbone and anchors:
                position = bisect.bisect_left(anchor_en, row["en_seq"])
                left = anchors[position - 1] if position else None
                right = anchors[position] if position < len(anchors) else None
                expected_low = left[1] if left else ""
                expected_high = right[1] if right else ""
            row.update({
                "on_backbone": on_backbone,
                "expected_ko_seq_low": expected_low,
                "expected_ko_seq_high": expected_high,
                "in_master": key in master,
                "master_source": master[key]["translation_source"] if key in master else "",
                "master_korean": clean(master[key]["korean"]) if key in master else "",
                "hand_verdict": "MISPLACED" if key in hand else "",
            })
            results.append(row)

    # A bracket of width 1 pins the answer to a single Korean sequence index.
    for row in results:
        low, high = row["expected_ko_seq_low"], row["expected_ko_seq_high"]
        target = ""
        if isinstance(low, int) and isinstance(high, int) and high - low == 2:
            target = low + 1
        row["remap_ko_seq"] = target
        row["remap_korean"] = ko_text.get((row["media"], target), "") if target != "" else ""
        if row["on_backbone"]:
            row["verdict"] = "KEEP"
        elif row["remap_korean"]:
            row["verdict"] = "REMAP"
        else:
            row["verdict"] = "MISPLACED"

    fields = ["media", "record", "entry", "verdict", "hand_verdict", "on_backbone",
              "en_seq", "ko_seq", "expected_ko_seq_low", "expected_ko_seq_high",
              "remap_ko_seq", "status", "candidates", "in_master", "master_source",
              "english", "korean", "master_korean", "remap_korean"]
    out = args.outdir / "media-offset-alignment.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    off = [r for r in results if not r["on_backbone"]]
    agree = sum(1 for r in results if r["hand_verdict"] and not r["on_backbone"])
    disagree = sum(1 for r in results if r["hand_verdict"] and r["on_backbone"])
    summary = {
        "rows_with_both_sequences": len(results),
        "by_media": dict(Counter(r["media"] for r in results)),
        "on_backbone_keep": sum(1 for r in results if r["on_backbone"]),
        "off_backbone": len(off),
        "off_backbone_by_media": dict(Counter(r["media"] for r in off)),
        "verdicts": dict(Counter(r["verdict"] for r in results).most_common()),
        "off_backbone_by_match_status": dict(Counter(r["status"] for r in off)),
        "hand_read_cross_check": {
            "hand_misplaced_rows_present": agree + disagree,
            "also_off_backbone": agree,
            "on_backbone_despite_hand_read": disagree,
        },
        "master_coverage": {
            "rows_present_in_master": sum(1 for r in results if r["in_master"]),
            "of_those_source_offset": sum(1 for r in results
                                          if r["master_source"] == "offset"),
        },
    }
    (args.evidence / "alignment-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
