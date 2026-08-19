#!/usr/bin/env python3
"""Append codec rows the master never extracted, recovering Korean from PS2 sources.

`mgs3d_codec_status_catalog.py` drops rows whose status was `적용완료` (already
applied in the build it was generated against). When the pipeline was later
re-based on the clean baseline that Korean disappeared, and no master row existed
to restore it -- see `docs/v0.83-*` and
`docs/evidence/codec-recovery-survey-2026-08-16.json`.

This appends **only** positions the master does not already cover. Existing rows
are never read back out and never rewritten: their `accept`, `korean` and `note`
are untouched, because the merge is keyed on positions that by construction have
no master row.

Korean comes from the project's own verified PS2 material, not from decoding the
old binary -- the golden-era records carry a per-build token allocation with no
embedded font, so their bytes are not decodable with the current map. Each
recovered line is cross-checked against the English actually stored at that
position before it is written, and the source file is recorded in `note`.

`translation/20_matching/mgs3d_script_comparison.csv` is deliberately NOT a
source: it is keyed to stale parser offsets and disagrees with the binary.

    python tools/mgs3d_codec_recover_missing.py            # dry run
    python tools/mgs3d_codec_recover_missing.py --apply
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec, render_bytes  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402
from mgs3d_codec_status_catalog import strict_western, direct_language  # noqa: E402

CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
MASTER = ROOT / "translation/10_master/current/codec.csv"
CHARMAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
SOURCES = [
    ROOT / "translation/30_shortened/script_ref/runtime-language-decisions.csv",
    ROOT / "translation/20_matching/en_codec_korean_matches.csv",
]
ACCENT = re.compile(rb"\x1f[\x20-\x7f]")
TOKEN = re.compile(r"<([0-9A-Fa-f]{2})>")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", (text or "").casefold())


def has_hangul(text: str) -> bool:
    return any("가" <= c <= "힣" for c in text or "")


def control_codes(text: str) -> list[str]:
    return TOKEN.findall(text or "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", type=Path,
                    default=ROOT / "docs/evidence/codec-recovery-append-2026-08-16.json")
    args = ap.parse_args()

    charmap = json.loads(CHARMAP.read_text(encoding="utf-8"))["characters"]
    csv.field_size_limit(10 ** 9)
    with MASTER.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        master = list(reader)
    if not fields:
        raise SystemExit("master has no header")

    covered: set[tuple[int, int]] = set()
    for row in master:
        for item in (row.get("locations") or "").split(";"):
            gcx, _, res = item.partition(":")
            try:
                covered.add((int(gcx), int(res)))
            except ValueError:
                pass

    # --- recovery sources ---------------------------------------------------
    source: dict[tuple[int, int], tuple[str, str, str]] = {}
    for path in SOURCES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            cols = reader.fieldnames or []
            kcol = next((c for c in cols if c and "korean" in c.lower()), None)
            ecol = next((c for c in cols if c and c.lower() == "english"), None)
            if not kcol:
                continue
            for row in reader:
                try:
                    key = (int(row.get("gcx") or -1), int(row.get("resource") or -1))
                except ValueError:
                    continue
                korean = (row.get(kcol) or "").strip()
                if has_hangul(korean) and key not in source:
                    source[key] = (korean, (row.get(ecol) or "").strip(), path.name)

    # --- walk uncovered English positions -----------------------------------
    records = parse_codec(CLEAN.read_bytes())
    groups: dict[str, dict] = {}
    english_only: list[dict] = []
    unrecovered: list[dict] = []
    for gcx, record in enumerate(records):
        try:
            resources = record.resources()
        except Exception:
            continue
        for res, item in enumerate(resources):
            if (gcx, res) in covered:
                continue
            english = decode_western(item.data)
            if not english or not strict_western(item.data):
                continue
            if ACCENT.search(item.data) or direct_language(item.data) in ("fr", "es"):
                continue
            key = norm(english)
            found = source.get((gcx, res))
            if found is None:
                (english_only if key not in groups else unrecovered).append(
                    {"gcx": gcx, "resource": res, "english": english})
                continue
            korean, src_en, src_file = found
            if src_en and letters(src_en)[:40] and letters(src_en)[:40] != letters(english)[:40]:
                unrecovered.append({"gcx": gcx, "resource": res, "english": english,
                                    "reason": "source English disagrees"})
                continue
            entry = groups.setdefault(key, {
                "gcx": gcx, "resource": res, "english": english, "korean": korean,
                "raw_text": render_bytes(item.data), "source": src_file, "locations": [],
            })
            entry["locations"].append((gcx, res))

    # --- build rows ---------------------------------------------------------
    added, review = [], []
    for entry in groups.values():
        korean = entry["korean"]
        missing = sorted({c for c in korean if "가" <= c <= "힣" and c not in charmap})
        drift = control_codes(entry["raw_text"]) != control_codes(korean)
        # Approve only what is unambiguous: the source English matched the binary,
        # every syllable is in the shipped map, and the control codes line up.
        # Anything else is appended unaccepted with the reason recorded.
        reason = ""
        if missing:
            reason = "glyph outside current map: " + "".join(missing)
        elif drift:
            reason = "control-code shape differs from the English original"
        accept = "" if reason else "yes"
        locs = sorted(entry["locations"])
        row = {f: "" for f in fields}
        row.update({
            "translate": "yes",
            "accept": accept,
            "status": "대사집 대응 없음",
            "language": "en",
            "is_donor": "no",
            "text_kind": "display_text",
            "blocker": reason,
            "occurrences": len(locs),
            "locations": ";".join(f"{g}:{r}" for g, r in locs),
            "gcx": locs[0][0],
            "resource": locs[0][1],
            "english": entry["english"],
            "korean": korean,
            "raw_text": entry["raw_text"],
            "note": f"2026-08-16 recovered from {entry['source']} "
                    f"(master extraction gap; reference Korean)"
                    + (f" | REVIEW: {reason}" if reason else ""),
        })
        added.append(row)
        if reason:
            review.append({"gcx": locs[0][0], "resource": locs[0][1],
                           "english": entry["english"], "korean": korean, "reason": reason})

    accepted = sum(1 for r in added if r["accept"] == "yes")
    print("rows to append              : %d  (%d locations)"
          % (len(added), sum(int(r["occurrences"]) for r in added)))
    print("  auto-accepted             : %d" % accepted)
    print("  appended for review       : %d" % (len(added) - accepted))
    for r in review:
        print("     gcx %s res %s -- %s" % (r["gcx"], r["resource"], r["reason"]))
    print("english-only positions      : %d" % len(english_only))
    print("unrecovered positions       : %d" % len(unrecovered))
    print("sources used                : %s" % Counter(e["source"] for e in groups.values()))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "format": "mgs3d-codec-recovery-append-v1",
        "applied": bool(args.apply),
        "rows_appended": len(added),
        "locations_appended": sum(int(r["occurrences"]) for r in added),
        "auto_accepted": accepted,
        "review_rows": review,
        "english_only_positions": len(english_only),
        "unrecovered_positions": len(unrecovered),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.apply and added:
        backup = MASTER.with_suffix(MASTER.suffix + ".bak-pre-recovery-20260816")
        if not backup.exists():
            shutil.copy2(MASTER, backup)
            print("backup -> %s" % backup)
        with MASTER.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(master + added)
        print("wrote %s (%d -> %d rows)" % (MASTER, len(master), len(master) + len(added)))
    elif not args.apply:
        print("(dry run -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
