#!/usr/bin/env python3
"""Full audit of the movie/demo master rows whose `translation_source` is `offset`.

Those rows were transplanted from a **Japanese-keyed** comparison table by byte
offset, so their Korean can sit on the wrong English line. This tool decides,
per row, whether the English and the Korean are actually the same line of
dialogue, and where the Korean belongs when they are not.

READ-ONLY. Reads masters and matching tables, writes an audit CSV/JSON. It never
touches master, the DATs, a build, or staging.

Evidence, strongest first:

  A  `20_matching/en_{demo,movie}_korean_matches.csv` -- keyed to the **English**
     DAT (record, entry), so an agreeing row is direct confirmation and a
     disagreeing one hands over the correct Korean.
  B  `20_matching/{demo,movie}_korean_comparison_review.csv` -- Japanese-keyed, so
     its record/entry are useless here, but each row pairs an English line with
     its Korean *internally*. Looking the master's Korean up in that table
     therefore recovers the English it was really translated from.

Verdicts:

  KEEP       English and Korean are the same line
  MISPLACED  the Korean demonstrably belongs to a different English line
  REMAP      MISPLACED *and* the correct Korean for this line was located
  HUMAN      no evidence either way, or the evidence conflicts

Drift blocks: when consecutive entries in one record are all misplaced by the
same number of entry positions, that is one offset slip, not N mistranslations.
Those runs are reported separately.

Usage:
  python tools/mgs3d_media_offset_audit.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
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
MATCHING = ROOT / "translation/20_matching"

EN_WORD = re.compile(r"[a-z0-9']+")
KO_KEEP = re.compile(r"[0-9A-Za-z가-힣]+")

# Above this the two English strings are the same line; below the lower bound the
# Korean is answering a different line entirely. Between them nobody should guess.
SAME_LINE = 0.72
DIFFERENT_LINE = 0.42


def norm_en(text: str) -> str:
    text = re.sub(r"<[^>]*>", " ", text or "").replace("|", " ")
    return " ".join(EN_WORD.findall(unicodedata.normalize("NFKC", text).casefold()))


def norm_ko(text: str) -> str:
    text = re.sub(r"<[^>]*>", " ", text or "").replace("|", " ")
    return "".join(KO_KEEP.findall(unicodedata.normalize("NFKC", text)))


def similarity(a: str, b: str) -> float:
    """Ratio, lifted when one side is a clean fragment of the other.

    Subtitle cards split one sentence across several entries, so a master line is
    routinely a substring of the comparison table's whole-sentence field. Scoring
    that as a mismatch would invent hundreds of false misplacements."""
    if not a or not b:
        return 0.0
    if a in b or b in a:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        if len(shorter) >= 8 or len(shorter) / len(longer) >= 0.5:
            return max(0.85, len(shorter) / len(longer))
    return difflib.SequenceMatcher(None, a, b).ratio()


def load_master():
    rows = {}
    order = defaultdict(list)
    for media in ("movie", "demo"):
        with io.open(MASTERS / f"{media}.csv", encoding="utf-8-sig", newline="") as handle:
            items = list(csv.DictReader(handle))
        items.sort(key=lambda r: (int(r["record"]), int(r["entry"])))
        for row in items:
            key = (media, int(row["record"]), int(row["entry"]))
            rows[key] = row
            order[(media, int(row["record"]))].append(key)
    return rows, order


def load_english_keyed():
    """Evidence A: (media, record, entry) -> korean, from the English-keyed tables."""
    table = {}
    for media in ("demo", "movie"):
        path = MATCHING / f"en_{media}_korean_matches.csv"
        if not path.exists():
            continue
        with io.open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                korean = (row.get("korean") or "").strip()
                if not korean:
                    continue
                table[(media, int(row["record"]), int(row["entry"]))] = {
                    "korean": korean,
                    "english": row.get("english") or "",
                    "status": row.get("match_status") or "",
                }
    return table


def load_pairs():
    """Evidence B: internally-paired (english, korean) rows, media-scoped."""
    pairs = defaultdict(list)
    for media in ("demo", "movie"):
        path = MATCHING / f"{media}_korean_comparison_review.csv"
        if not path.exists():
            continue
        with io.open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                english = row.get("english") or ""
                if not english:
                    continue
                for field in ("korean", "korean_full"):
                    korean = (row.get(field) or "").strip()
                    if korean:
                        pairs[media].append({
                            "en": english, "ko": korean,
                            "en_n": norm_en(english), "ko_n": norm_ko(korean),
                            "speaker": (row.get("english_speaker") or "").strip(),
                        })
    return pairs


def best(candidates, key, target, floor=0.0):
    winner, score = None, floor
    for candidate in candidates:
        value = similarity(candidate[key], target)
        if value > score:
            winner, score = candidate, value
    return winner, score


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    parser.add_argument("--evidence", type=Path,
                        default=ROOT / "docs/evidence/2026-08-19-media-offset-audit")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)

    master, order = load_master()
    english_keyed = load_english_keyed()
    pairs = load_pairs()

    # Every master line, so a displaced Korean can be traced to the line it belongs on.
    by_english = defaultdict(list)
    for key, row in master.items():
        by_english[key[0]].append({"key": key, "en_n": norm_en(row["preview"])})

    targets = [k for k, r in master.items() if r["translation_source"] == "offset"]
    targets.sort()

    results = []
    for key in targets:
        media, record, entry = key
        row = master[key]
        en_now = norm_en(row["preview"])
        ko_now = norm_ko(row["korean"])
        record_keys = order[(media, record)]
        position = record_keys.index(key)

        result = {
            "media": media, "record": record, "entry": entry,
            "english": re.sub(r"<[^>]*>", " ", row["preview"] or "").replace("|", " ").strip(),
            "korean": row["korean"] or "",
            "verdict": "", "confidence": "", "evidence": "",
            "source_english": "", "source_speaker": "",
            "belongs_to": "", "correct_korean": "", "correct_korean_evidence": "",
            "score_pair": "", "score_direct": "", "drift": "",
        }

        # --- evidence A: the English-keyed table has this exact (record, entry) ---
        direct = english_keyed.get(key)
        if direct:
            score = similarity(ko_now, norm_ko(direct["korean"]))
            result["score_direct"] = round(score, 2)
            if score >= 0.85:
                result.update(verdict="KEEP", confidence="high",
                              evidence="English-keyed match table agrees with the master Korean")
                results.append(result)
                continue
            result["correct_korean"] = direct["korean"]
            result["correct_korean_evidence"] = (
                f"en_{media}_korean_matches.csv at this (record, entry); "
                f"status={direct['status']}")

        # --- evidence B: what English was this Korean actually translated from? ---
        pair, pair_score = best(pairs[media], "ko_n", ko_now)
        result["score_pair"] = round(pair_score, 2)
        if pair and pair_score >= 0.80:
            result["source_english"] = pair["en"][:200]
            result["source_speaker"] = pair["speaker"]
            agreement = similarity(en_now, pair["en_n"])
            result["evidence"] = (
                f"Korean traced to the comparison table (ko score {pair_score:.2f}); "
                f"its English vs this line: {agreement:.2f}")
            if agreement >= SAME_LINE:
                result.update(verdict="KEEP", confidence="high")
            elif agreement <= DIFFERENT_LINE:
                result.update(verdict="MISPLACED", confidence="high")
                home, home_score = best(by_english[media], "en_n", pair["en_n"], SAME_LINE)
                if home and home["key"] != key:
                    result["belongs_to"] = "%s r%d e%d" % home["key"]
                    hr, he = home["key"][1], home["key"][2]
                    if (media, hr) == (media, record):
                        result["drift"] = record_keys.index(home["key"]) - position
            else:
                result.update(verdict="HUMAN", confidence="low")
        else:
            result["evidence"] = (
                f"Korean not found in any matching table (best ko score {pair_score:.2f})")
            result.update(verdict="HUMAN", confidence="low")

        # --- can the correct Korean for THIS English be recovered? ---
        if result["verdict"] == "MISPLACED" and not result["correct_korean"]:
            fix, fix_score = best(pairs[media], "en_n", en_now, SAME_LINE)
            if fix:
                result["correct_korean"] = fix["ko"]
                result["correct_korean_evidence"] = (
                    f"comparison table row whose English matches this line ({fix_score:.2f})")
        if result["verdict"] == "MISPLACED" and result["correct_korean"]:
            result["verdict"] = "REMAP"

        results.append(result)

    # --- consecutive drift blocks -------------------------------------------
    blocks = []
    current = None
    for result in results:
        drift = result["drift"]
        signature = (result["media"], result["record"], drift)
        if drift == "" or drift == 0:
            current = None
            continue
        if current and current["signature"] == signature and \
                result["entry"] > current["last_entry"]:
            current["rows"] += 1
            current["last_entry"] = result["entry"]
        else:
            current = {"signature": signature, "media": result["media"],
                       "record": result["record"], "drift": drift,
                       "first_entry": result["entry"], "last_entry": result["entry"],
                       "rows": 1}
            blocks.append(current)
    blocks = [b for b in blocks if b["rows"] >= 2]

    fields = list(results[0].keys())
    audit = args.outdir / "media-offset-audit.csv"
    with audit.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "offset_rows_total": len(targets),
        "audited": len(results),
        "by_verdict": dict(Counter(r["verdict"] for r in results).most_common()),
        "by_media": {m: dict(Counter(r["verdict"] for r in results if r["media"] == m)
                             .most_common()) for m in ("movie", "demo")},
        "misplaced_with_home_located": sum(1 for r in results if r["belongs_to"]),
        "correct_korean_recovered": sum(1 for r in results if r["correct_korean"]),
        "drift_blocks": [
            {"media": b["media"], "record": b["record"], "drift_entries": b["drift"],
             "entries": f'{b["first_entry"]}-{b["last_entry"]}', "rows": b["rows"]}
            for b in blocks],
        "thresholds": {"same_line": SAME_LINE, "different_line": DIFFERENT_LINE},
    }
    (args.evidence / "offset-audit-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
