#!/usr/bin/env python3
"""movie/demo re-alignment, second attempt: anchor by monotone backbone, then DP.

The first attempt (`mgs3d_media_realign.py`) failed its own gate 0/107. Cause:
it built each record's the script reference window from *every* master line whose Korean
matched the script -- including the mis-placed ones, whose Korean points at the
wrong part of the script. The window was poisoned by the very defect it was
meant to repair.

This version never trusts a single anchor. It:

  1. takes every master line whose normalised Korean has a **unique** position in
     the script reference script -- a candidate anchor;
  2. orders those candidates by (media, record, entry) and keeps only the
     **longest increasing subsequence** of their the script reference positions. A
     mis-placed line points somewhere else in the script and therefore breaks
     monotonicity, so it falls off the backbone on its own;
  3. interpolates the backbone to estimate a script position for every entry,
     and windows each record around that;
  4. runs a monotone DP inside the window, scored on anchors that survive
     translation (digits, transliterated proper nouns) rather than string shape.

`(record, entry)` order really is story order: measured against the cleaned
sequence anchors it is 96.8% monotone for movie and 85.4% for demo. The earlier
58% reading came from contaminated anchors, not from disordered records.

Auto-remap still needs all three: on the DP path, >=1 anchor agreeing, both
neighbours on the path. Everything else is HUMAN.

**Gate**: the 107 confirmed-correct rows must come back with their own Korean.
Below that, nothing here may be used.

READ-ONLY.

Usage:
  python tools/mgs3d_media_realign2.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
import bisect
import csv
import difflib
import io
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parent.parent
MASTERS = ROOT / "translation/10_master/current"
SCRIPT_REF = ROOT / "translation/20_matching/script_ref/script_ref_mgs3_script.csv"
VERDICTS = ROOT / "output/media-register-qa/media-offset-verdicts.csv"

WORD = re.compile(r"[0-9A-Za-z가-힣]+")
HANGUL = re.compile(r"[가-힣]")
DIGITS = re.compile(r"\d+")
LATIN = re.compile(r"[A-Za-z][A-Za-z'\-\.]+")

NAMES = {
    "snake": "스네이크", "sokolov": "소코로프", "ocelot": "오셀롯", "volgin": "볼긴",
    "zero": "제로", "eva": "에바", "adam": "아담", "boss": "보스", "jack": "잭",
    "granin": "그라닌", "tatyana": "타티야나", "khrushchev": "흐루쇼프",
    "shagohod": "샤고호드", "groznyj": "그로즈니", "sigint": "시긴트",
    "raikov": "라이코프", "johnny": "조니", "sorrow": "소로우", "pain": "페인",
    "fear": "피어", "fury": "퓨리", "cobra": "코브라", "spetsnaz": "스페츠나츠",
    "makarov": "마카로프", "kgb": "KGB", "cia": "CIA", "gru": "GRU", "nsa": "NSA",
    "cqc": "CQC",
}
MARGIN = 40
GAP = -0.30


def normalise(text: str) -> str:
    return "".join(WORD.findall(unicodedata.normalize("NFKC", text or "")))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text or "").replace("|", " ")).strip()


def anchors_en(text: str) -> set[str]:
    found = {f"#{d}" for d in DIGITS.findall(text)}
    found |= {f"@{w.lower().strip('.')}" for w in LATIN.findall(text)
              if w.lower().strip(".") in NAMES}
    return found


def anchors_ko(text: str) -> set[str]:
    found = {f"#{d}" for d in DIGITS.findall(text)}
    found |= {f"@{k}" for k, v in NAMES.items() if v and v in text}
    return found


def pair_score(en: dict, ko: dict) -> tuple[float, int]:
    shared = en["anchors"] & ko["anchors"]
    union = en["anchors"] | ko["anchors"]
    value = 2.0 * len(shared) / len(union) if union else 0.0
    if shared:
        value += 0.8
    le, lk = max(1, en["length"]), max(1, ko["length"] * 1.6)
    value += 0.5 * (min(le, lk) / max(le, lk))
    return value, len(shared)


def longest_increasing(values: list[int]) -> list[int]:
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
    out = []
    cursor = tail_index[-1] if tail_index else -1
    while cursor != -1:
        out.append(cursor)
        cursor = previous[cursor]
    return out[::-1]


def align(english: list[dict], korean: list[dict]) -> dict[int, int]:
    n, m = len(english), len(korean)
    if not n or not m:
        return {}
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row_best, row_back = best[i], back[i]
        prev_best = best[i - 1]
        for j in range(1, m + 1):
            value, _ = pair_score(english[i - 1], korean[j - 1])
            diagonal = prev_best[j - 1] + value
            up = prev_best[j] + GAP
            left = row_best[j - 1] + GAP
            if diagonal >= up and diagonal >= left:
                row_best[j], row_back[j] = diagonal, 0
            elif up >= left:
                row_best[j], row_back[j] = up, 1
            else:
                row_best[j], row_back[j] = left, 2
    pairs, i, j = {}, n, m
    while i > 0 and j > 0:
        move = back[i][j]
        if move == 0:
            pairs[i - 1] = j - 1
            i, j = i - 1, j - 1
        elif move == 1:
            i -= 1
        else:
            j -= 1
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/evidence/2026-08-19-media-offset-audit")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)

    script = []
    with io.open(SCRIPT_REF, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = re.sub(r"\s+", " ", (row.get("text") or "")).strip()
            if not text or not HANGUL.search(text):
                continue
            script.append({
                "page": int(row["page"]) if row["page"].isdigit() else 0,
                "sequence": int(row["sequence"]) if row["sequence"].isdigit() else 0,
                "speaker": (row.get("speaker") or "").strip(), "text": text,
                "norm": normalise(text), "length": len(text),
                "anchors": anchors_ko(text),
            })
    script.sort(key=lambda r: (r["page"], r["sequence"]))
    positions = defaultdict(list)
    for index, row in enumerate(script):
        positions[row["norm"]].append(index)

    verdict = {}
    if VERDICTS.exists():
        with io.open(VERDICTS, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                verdict[(row["media"], int(row["record"]), int(row["entry"]))] = row["verdict"]

    lines = []
    for media in ("movie", "demo"):
        with io.open(MASTERS / f"{media}.csv", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                english = clean(row["preview"])
                korean = clean(row["korean"])
                lines.append({
                    "media": media, "record": int(row["record"]), "entry": int(row["entry"]),
                    "source": row["translation_source"], "english": english,
                    "korean": korean, "norm_ko": normalise(korean),
                    "length": len(english), "anchors": anchors_en(english),
                })
    lines.sort(key=lambda r: (r["media"], r["record"], r["entry"]))

    # --- backbone: unique-position anchors that keep the script moving forward ---
    candidates = [(i, positions[r["norm_ko"]][0]) for i, r in enumerate(lines)
                  if len(positions.get(r["norm_ko"], [])) == 1]
    kept = longest_increasing([c[1] for c in candidates])
    backbone = [candidates[k] for k in kept]
    backbone_keys = {(lines[i]["media"], lines[i]["record"], lines[i]["entry"])
                     for i, _ in backbone}

    anchor_line = [b[0] for b in backbone]
    anchor_pos = [b[1] for b in backbone]

    def estimate(index: int) -> int:
        if not anchor_line:
            return 0
        at = bisect.bisect_left(anchor_line, index)
        if at == 0:
            return anchor_pos[0]
        if at >= len(anchor_line):
            return anchor_pos[-1]
        x0, x1 = anchor_line[at - 1], anchor_line[at]
        y0, y1 = anchor_pos[at - 1], anchor_pos[at]
        if x1 == x0:
            return y0
        return int(y0 + (y1 - y0) * (index - x0) / (x1 - x0))

    records = defaultdict(list)
    for index, row in enumerate(lines):
        row["global_index"] = index
        records[(row["media"], row["record"])].append(row)

    results = []
    for key, block in sorted(records.items()):
        low = max(0, estimate(block[0]["global_index"]) - MARGIN)
        high = min(len(script), estimate(block[-1]["global_index"]) + MARGIN + 1)
        window = script[low:high]
        pairs = align(block, window) if window else {}
        for position, row in enumerate(block):
            matched = pairs.get(position)
            record = {k: row[k] for k in
                      ("media", "record", "entry", "source", "english", "korean")}
            record["verdict_2026_08_19"] = verdict.get(
                (row["media"], row["record"], row["entry"]), "")
            if matched is None:
                record.update(status="UNMATCHED", proposed="", proposed_speaker="",
                              anchor_hits=0, neighbours_on_path=False)
            else:
                partner = window[matched]
                _, hits = pair_score(row, partner)
                neighbours = all((position + d) in pairs for d in (-1, 1)
                                 if 0 <= position + d < len(block))
                record.update(status="MATCHED", proposed=partner["text"],
                              proposed_speaker=partner["speaker"], anchor_hits=hits,
                              neighbours_on_path=neighbours)
            results.append(record)

    index_by_key = {(r["media"], r["record"], r["entry"]): r for r in results}

    def reproduces(row) -> bool:
        if row["status"] != "MATCHED" or not row["korean"]:
            return False
        return difflib.SequenceMatcher(
            None, normalise(row["korean"]), normalise(row["proposed"])).ratio() >= 0.85

    gate_rows = [r for r in results if r["verdict_2026_08_19"] == "KEEP"]
    gate_hits = sum(1 for r in gate_rows if reproduces(r))
    mis_rows = [r for r in results if r["verdict_2026_08_19"] == "MISPLACED"]
    confident = [r for r in mis_rows if r["status"] == "MATCHED" and r["anchor_hits"] >= 1
                 and r["neighbours_on_path"]
                 and normalise(r["proposed"]) != normalise(r["korean"])]

    fields = ["media", "record", "entry", "source", "verdict_2026_08_19", "status",
              "anchor_hits", "neighbours_on_path", "english", "korean", "proposed",
              "proposed_speaker"]
    out = args.outdir / "media-realign2-dryrun.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "script_ref_lines": len(script),
        "master_lines": len(results),
        "unique_position_candidates": len(candidates),
        "backbone_anchors": len(backbone),
        "backbone_check": {
            "confirmed_KEEP_rows_on_backbone": sum(
                1 for k, v in verdict.items() if v == "KEEP" and k in backbone_keys),
            "confirmed_KEEP_total": sum(1 for v in verdict.values() if v == "KEEP"),
            "confirmed_MISPLACED_on_backbone": sum(
                1 for k, v in verdict.items() if v == "MISPLACED" and k in backbone_keys),
            "confirmed_MISPLACED_total": sum(1 for v in verdict.values() if v == "MISPLACED"),
        },
        "status": dict(Counter(r["status"] for r in results).most_common()),
        "gate": {
            "rows": len(gate_rows), "reproduced": gate_hits,
            "rate": round(gate_hits / len(gate_rows), 3) if gate_rows else None,
        },
        "misplaced_auto_remap_candidates": len(confident),
    }
    (args.evidence / "realign2-dryrun-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
