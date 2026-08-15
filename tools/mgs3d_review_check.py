#!/usr/bin/env python3
"""Check, and optionally apply, the shortened lines written into the worklist.

Workflow is one file and two commands:

    1. edit  translation/10_master/review/dialogue-worklist.csv  -- fill korean_new
    2. python tools/mgs3d_review_check.py            # does it fit? any bad glyph?
    3. python tools/mgs3d_review_check.py --apply    # write into current/*.csv

--apply is precondition-checked: a row is written only if the master still holds
exactly the `korean` the worklist was generated from, so a stale worklist can
never overwrite newer edits. Masters are backed up before the first write.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10 ** 8)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_rendered  # noqa: E402

import json  # noqa: E402

MASTER = ROOT / "translation/10_master/current"
CHARMAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
WORKLIST = ROOT / "translation/10_master/review/dialogue-worklist.csv"
HANGUL = re.compile(r"[가-힣]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--worklist", type=Path, default=WORKLIST)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    cmap = {c: bytes.fromhex(t)
            for c, t in json.loads(CHARMAP.read_text(encoding="utf-8"))["characters"].items()}
    rows = list(csv.DictReader(args.worklist.open(newline="", encoding="utf-8-sig")))
    edited = [r for r in rows if (r.get("korean_new") or "").strip()]
    print(f"worklist rows {len(rows)}   edited {len(edited)}")
    if not edited:
        print("nothing to check -- fill the korean_new column first")
        return 0

    ok, bad = [], []
    for r in edited:
        text = r["korean_new"].strip()
        budget = int(r["bytes_budget"] or 0)
        missing = "".join(dict.fromkeys(
            ch for ch in text if HANGUL.match(ch) and ch not in cmap))
        try:
            used = len(parse_rendered(text, cmap))
            err = ""
        except Exception as exc:
            used, err = None, str(exc)[:70]
        problems = []
        if missing:
            problems.append(f"glyph page lacks: {missing}")
        if err:
            problems.append(err)
        elif used > budget:
            problems.append(f"{used - budget} bytes over ({used}/{budget})")
        if not text.endswith("<00>") and r["media"] == "codec" and r["korean"].endswith("<00>"):
            problems.append("codec line lost its trailing <00> terminator")
        (bad if problems else ok).append((r, used, problems))

    for r, used, problems in bad:
        print(f"  FAIL {r['media']:5s} {r['key']:22s} {'; '.join(problems)}")
        print(f"       {r['korean_new'][:80]}")
    print(f"\nPASS {len(ok)}   FAIL {len(bad)}")
    if bad:
        print("fix the failures above; nothing was written")
        return 1
    if not args.apply:
        print("all good -- re-run with --apply to write these into current/*.csv")
        return 0

    by_media: dict[str, list] = {}
    for r, _, _ in ok:
        by_media.setdefault(r["media"], []).append(r)

    applied = Counter()
    for media, items in by_media.items():
        path = MASTER / f"{media}.csv"
        backup = path.with_suffix(".csv.bak-pre-shorten")
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames)
            master_rows = list(reader)
        if media == "codec":
            index = {(str(x.get("gcx")), str(x.get("resource"))): x for x in master_rows}
            keys = [(str(r["gcx"]), str(r["resource"])) for r in items]
        else:
            index = {str(x.get("offset")): x for x in master_rows}
            keys = [r["key"].split("@", 1)[1] for r in items]
        stale = []
        for r, key in zip(items, keys):
            target = index.get(key)
            if target is None or (target.get("korean") or "").strip() != r["korean"].strip():
                stale.append(r["key"])
        if stale:
            print(f"  {media}: {len(stale)} row(s) changed in the master since this "
                  f"worklist was generated -- regenerate it. First: {stale[0]}")
            return 1
        if not backup.exists():
            shutil.copy2(path, backup)
        for r, key in zip(items, keys):
            index[key]["korean"] = r["korean_new"].strip()
            applied[media] += 1
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(master_rows)

    for media, n in applied.items():
        print(f"applied {n} row(s) to current/{media}.csv")
    print("\nnext: regenerate the build input and rebuild the DATs "
          "(see docs/v0.80-staging-2026-08-16.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
