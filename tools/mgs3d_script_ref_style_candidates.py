#!/usr/bin/env python3
"""Rank script reference codec lines as style references for direct translations."""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path


def norm(text: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]", "", text).lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("backlog", type=Path)
    ap.add_argument("mapping", type=Path)
    ap.add_argument("script_ref", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    csv.field_size_limit(sys.maxsize)
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    with args.backlog.open(encoding="utf-8-sig", newline="") as h:
        backlog = {r["id"]: r for r in csv.DictReader(h)}
    with args.script_ref.open(encoding="utf-8-sig", newline="") as h:
        refs = [r for r in csv.DictReader(h) if r.get("target") == "codec" and r.get("text")]
    result = []
    for row_id, korean in mapping.items():
        if "<0A>" in backlog[row_id]["english"]:
            continue
        nk = norm(korean)
        ranked = sorted(
            ((difflib.SequenceMatcher(None, nk, norm(r["text"])).ratio(), r) for r in refs),
            key=lambda item: item[0], reverse=True,
        )[:3]
        result.append({
            "id": row_id,
            "english_3ds": backlog[row_id]["english"],
            "direct_korean": korean,
            "candidates": [{"score": round(score, 4), "speaker": r["speaker"], "text": r["text"], "sequence": r["sequence"]} for score, r in ranked],
        })
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"direct={len(result)} references={len(refs)} score_ge_0.55={sum(bool(x['candidates']) and x['candidates'][0]['score'] >= .55 for x in result)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
