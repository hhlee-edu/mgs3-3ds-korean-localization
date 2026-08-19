#!/usr/bin/env python3
"""Rebuild the movie/demo English-to-Korean alignment with a monotone DP.

Every existing alignment artifact is the origin of the mis-placed Korean, not
evidence about it (see docs/evidence/2026-08-19-media-offset-audit/), so this
starts from the two raw axes instead:

  Korean   `20_matching/shinsnote/shinsnote_mgs3_script.csv`, ordered by
           (page, sequence) -- 4,071 lines with a `speaker` column
  English  `10_master/current/{movie,demo}.csv` `preview`, ordered by
           (record, entry) -- verified byte-identical to the DAT, 2,917/2,917

The old aligner matched a Korean line by **string uniqueness**, which for a short
line lands anywhere in the script. This one never does that: a pairing has to sit
on a monotone path through both axes, and the score is carried by anchors that
survive translation -- digits and proper nouns -- rather than by string shape.

Alignment is per record. A record is one cutscene, its entries are in playback
order, and its Korean is a contiguous run of the Shinsnote script. The run is
located from the record's already-confirmed-correct lines, then a Needleman-
Wunsch style DP walks both sides forward inside a margin around it.

Auto-remap needs all three, per the agreed confidence rule:
  * the pair lies on the DP path
  * at least one anchor agrees
  * both neighbours are on the path too
Anything short of that is HUMAN. Short anchorless lines ("그래 ?", "음 .") are
exactly the set that mis-placed in the first place and stay HUMAN by design.

READ-ONLY. Writes a report; touches no master, DAT, build or staging.

Usage:
  python tools/mgs3d_media_realign.py --gate      # reproduce the confirmed KEEP rows
  python tools/mgs3d_media_realign.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
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
SHINSNOTE = ROOT / "translation/20_matching/shinsnote/shinsnote_mgs3_script.csv"
VERDICTS = ROOT / "docs/evidence/2026-08-19-media-qa/verdicts.py"

DIGITS = re.compile(r"\d+")
LATIN = re.compile(r"[A-Za-z][A-Za-z'\-\.]+")
HANGUL = re.compile(r"[가-힣]")

# Proper nouns that survive into Korean as a fixed transliteration. Anchors have
# to be things a translator cannot paraphrase away; these were read off the
# corpus, not guessed.
NAMES = {
    "snake": "스네이크", "sokolov": "소코로프", "ocelot": "오셀롯", "volgin": "볼긴",
    "zero": "제로", "eva": "에바", "adam": "아담", "boss": "보스", "jack": "잭",
    "granin": "그라닌", "tatyana": "타티야나", "khrushchev": "흐루쇼프",
    "shagohod": "샤고호드", "groznyj": "그로즈니", "tselinoyarsk": "첼리노야르스크",
    "sigint": "시긴트", "raikov": "라이코프", "johnny": "조니", "sorrow": "소로우",
    "pain": "페인", "fear": "피어", "fury": "퓨리", "end": "엔드", "cobra": "코브라",
    "kgb": "KGB", "cia": "CIA", "gru": "GRU", "nsa": "NSA", "cqc": "CQC",
    "spetsnaz": "스페츠나츠", "makarov": "마카로프", "patriot": "패트리어트",
}
MARGIN = 60          # Shinsnote lines of slack around a record's anchored window
GAP = -0.35          # cost of advancing one side alone


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text or "").replace("|", " ")).strip()


def anchors_en(text: str) -> set[str]:
    found = {f"#{d}" for d in DIGITS.findall(text)}
    for word in LATIN.findall(text):
        key = word.lower().strip(".")
        if key in NAMES:
            found.add(f"@{key}")
    return found


def anchors_ko(text: str) -> set[str]:
    found = {f"#{d}" for d in DIGITS.findall(text)}
    for key, korean in NAMES.items():
        if korean and korean in text:
            found.add(f"@{key}")
    return found


def score(en: dict, ko: dict) -> tuple[float, int]:
    shared = en["anchors"] & ko["anchors"]
    union = en["anchors"] | ko["anchors"]
    value = 0.0
    if union:
        value += 2.0 * len(shared) / len(union)
    if shared:
        value += 0.6
    # length agreement: Korean runs shorter than English but proportionally
    le, lk = max(1, en["length"]), max(1, ko["length"])
    ratio = min(le, lk * 1.6) / max(le, lk * 1.6)
    value += 0.5 * ratio
    return value, len(shared)


def load_shinsnote() -> list[dict]:
    rows = []
    with io.open(SHINSNOTE, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = clean(row.get("text"))
            if not text or not HANGUL.search(text):
                continue
            rows.append({
                "page": int(row["page"]) if row["page"].isdigit() else 0,
                "sequence": int(row["sequence"]) if row["sequence"].isdigit() else 0,
                "speaker": (row.get("speaker") or "").strip(),
                "kind": row.get("kind") or "",
                "text": text, "length": len(text), "anchors": anchors_ko(text),
                "norm": "".join(re.findall(r"[0-9A-Za-z가-힣]+",
                                           unicodedata.normalize("NFKC", text))),
            })
    rows.sort(key=lambda r: (r["page"], r["sequence"]))
    for index, row in enumerate(rows):
        row["index"] = index
    return rows


def load_master():
    records = defaultdict(list)
    for media in ("movie", "demo"):
        with io.open(MASTERS / f"{media}.csv", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                english = clean(row["preview"])
                records[(media, int(row["record"]))].append({
                    "media": media, "record": int(row["record"]),
                    "entry": int(row["entry"]), "english": english,
                    "korean": clean(row["korean"]), "source": row["translation_source"],
                    "length": len(english), "anchors": anchors_en(english),
                    "norm_ko": "".join(re.findall(r"[0-9A-Za-z가-힣]+",
                                                  unicodedata.normalize("NFKC", row["korean"] or ""))),
                })
    for block in records.values():
        block.sort(key=lambda r: r["entry"])
    return records


def align(english: list[dict], korean: list[dict]) -> dict[int, int]:
    """Monotone DP. Returns english-position -> korean-position for matched pairs."""
    n, m = len(english), len(korean)
    if not n or not m:
        return {}
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            value, _ = score(english[i - 1], korean[j - 1])
            diagonal = best[i - 1][j - 1] + value
            up = best[i - 1][j] + GAP
            left = best[i][j - 1] + GAP
            if diagonal >= up and diagonal >= left:
                best[i][j], back[i][j] = diagonal, 0
            elif up >= left:
                best[i][j], back[i][j] = up, 1
            else:
                best[i][j], back[i][j] = left, 2
    pairs = {}
    i, j = n, m
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


def window(block, shin_by_norm, shinsnote):
    """Bracket the record's Korean run using lines whose text is already in Shinsnote."""
    positions = []
    for row in block:
        for candidate in shin_by_norm.get(row["norm_ko"], []):
            positions.append(candidate)
    if not positions:
        return None
    positions.sort()
    middle = positions[len(positions) // 2]
    low = max(0, min(positions[0], middle) - MARGIN)
    high = min(len(shinsnote), max(positions[-1], middle) + MARGIN)
    return shinsnote[low:high]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/evidence/2026-08-19-media-offset-audit")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)

    spec = importlib.util.spec_from_file_location("media_qa_verdicts", VERDICTS)
    verdicts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verdicts)
    misplaced = set(verdicts.MISMAPPED)

    shinsnote = load_shinsnote()
    shin_by_norm = defaultdict(list)
    for row in shinsnote:
        shin_by_norm[row["norm"]].append(row["index"])
    records = load_master()

    results = []
    for key, block in sorted(records.items()):
        candidates = window(block, shin_by_norm, shinsnote)
        if not candidates:
            for row in block:
                results.append({**row, "status": "NO_WINDOW", "proposed": "",
                                "anchor_hits": 0, "on_path": False})
            continue
        pairs = align(block, candidates)
        for position, row in enumerate(block):
            matched = pairs.get(position)
            proposed = anchor_hits = 0
            if matched is None:
                results.append({**row, "status": "UNMATCHED", "proposed": "",
                                "anchor_hits": 0, "on_path": False})
                continue
            partner = candidates[matched]
            _, anchor_hits = score(row, partner)
            neighbours = all((position + delta) in pairs
                             for delta in (-1, 1)
                             if 0 <= position + delta < len(block))
            results.append({**row, "status": "MATCHED", "proposed": partner["text"],
                            "proposed_speaker": partner["speaker"],
                            "anchor_hits": anchor_hits, "on_path": True,
                            "neighbours_on_path": neighbours})
    # --- gate: do the confirmed-correct rows come back with their own Korean? ---
    keep_rows = [r for r in results
                 if r["source"] == "offset"
                 and (r["media"], r["record"], r["entry"]) not in misplaced
                 and r["korean"]]
    reproduced = sum(1 for r in keep_rows
                     if r["status"] == "MATCHED" and r["norm_ko"] and
                     r["norm_ko"] == "".join(re.findall(r"[0-9A-Za-z가-힣]+",
                                                        unicodedata.normalize("NFKC", r["proposed"]))))
    mis_rows = [r for r in results
                if (r["media"], r["record"], r["entry"]) in misplaced]
    confident = [r for r in mis_rows
                 if r["status"] == "MATCHED" and r["anchor_hits"] >= 1
                 and r.get("neighbours_on_path")]

    fields = ["media", "record", "entry", "source", "status", "anchor_hits",
              "on_path", "neighbours_on_path", "english", "korean", "proposed",
              "proposed_speaker"]
    out = args.outdir / "media-realign-dryrun.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "shinsnote_lines": len(shinsnote),
        "master_lines": len(results),
        "status": dict(Counter(r["status"] for r in results).most_common()),
        "gate_confirmed_keep_rows": len(keep_rows),
        "gate_reproduced": reproduced,
        "gate_pass_rate": round(reproduced / len(keep_rows), 3) if keep_rows else None,
        "misplaced_rows_seen": len(mis_rows),
        "misplaced_auto_remap_candidates": len(confident),
    }
    (args.evidence / "realign-dryrun-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
