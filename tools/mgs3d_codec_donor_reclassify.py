#!/usr/bin/env python3
"""Find accepted codec rows that are really donor-language text, and reclassify them.

`language` and `is_donor` in `current/codec.csv` are not reliable. 42 rows carry
French or Spanish in `english` while labelled `language=en, is_donor=no`, so they
passed the donor filter and were translated, approved and built. Duplicate
propagation would carry that Korean to every one of their in-game positions.

**The language verdict comes from the game bytes, not from the CSV.** For each
candidate this reads the actual resource in the reference `codec.dat` and
classifies *that*. A row is only reclassified when the game data itself is
French/Spanish at **every** position the row names -- if any position holds
English, the row is left alone and reported, because then the metadata is wrong
rather than the row being donor text.

Default action is `--unaccept`: donor text is out of scope for this project
(English and Korean only), and Korean written into a branch the player never
selects is invisible and only consumes GCX bytes. Use `--keep-accepted` to fix
the classification only and leave `accept` untouched.

    python tools/mgs3d_codec_donor_reclassify.py --report-only
    python tools/mgs3d_codec_donor_reclassify.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec  # noqa: E402

DEFAULT_CODEC = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
DEFAULT_MASTER = ROOT / "translation/10_master/current/codec.csv"
ACCEPTED = ("y", "yes", "1", "ok")

FR = re.compile(r"\b(le|la|les|des|une|est|pour|avec|dans|vous|nous|je|tu|il|elle|ce|cette"
                r"|mais|plus|tout|tous|sur|pas|que|qui|se|son|sa|ses|au|aux|du|en|et|ne"
                r"|donc|alors|comme|bien|fait|faire|peut|dois)\b", re.I)
ES = re.compile(r"\b(el|los|las|una|es|para|con|en|usted|nosotros|yo|pero|más|todo|todos"
                r"|sobre|no|que|quien|su|sus|del|y|como|hacer|puede|debe|esto|esta|eso"
                r"|muy|hay|ser|está)\b", re.I)
EN = re.compile(r"\b(the|is|are|you|your|to|of|and|that|this|it|in|on|for|with|have|has"
                r"|will|can|not|but|be|do|does|was|were|they|we|he|she|there|what|when)\b", re.I)


def classify(text: str) -> str:
    fr, es, en = len(FR.findall(text)), len(ES.findall(text)), len(EN.findall(text))
    if en >= max(fr, es) and en >= 3:
        return "en"
    if max(fr, es) >= 3 and max(fr, es) > en * 2:
        return "fr" if fr >= es else "es"
    return "unknown"


def parse_locations(value: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for item in (value or "").split(";"):
        gcx, _, resource = item.strip().partition(":")
        try:
            out.append((int(gcx), int(resource)))
        except ValueError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codec", type=Path, default=DEFAULT_CODEC)
    ap.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--apply", action="store_true", help="write the master back")
    ap.add_argument("--keep-accepted", action="store_true",
                    help="fix language/is_donor only; leave accept as it is")
    args = ap.parse_args()

    records = parse_codec(args.codec.read_bytes())
    payloads = [[r.data for r in rec.resources()] for rec in records]

    def game_text(key: tuple[int, int]) -> str | None:
        gcx, resource = key
        if not 0 <= gcx < len(payloads) or not 0 <= resource < len(payloads[gcx]):
            return None
        return payloads[gcx][resource].decode("latin-1").replace("\x00", "").replace("\x80", "")

    csv.field_size_limit(10 ** 9)
    with args.master.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise SystemExit("master has no header")

    changed: list[dict] = []
    mixed: list[dict] = []
    for row in rows:
        if (row.get("accept") or "").strip().lower() not in ACCEPTED:
            continue
        if (row.get("is_donor") or "") == "yes":
            continue
        english = row.get("english") or ""
        if not english.strip() or classify(english) not in ("fr", "es"):
            continue

        locations = parse_locations(row.get("locations", ""))
        verdicts = Counter()
        for key in locations:
            text = game_text(key)
            if text is not None:
                verdicts[classify(text)] += 1
        if not verdicts:
            continue
        record = {
            "gcx": row.get("gcx"), "resource": row.get("resource"),
            "occurrences": row.get("occurrences"),
            "locations_checked": sum(verdicts.values()),
            "game_language_counts": dict(verdicts),
            "english": english[:160], "korean": (row.get("korean") or "")[:160],
        }
        if verdicts.get("en"):
            # Some position really is English -> the metadata is wrong, not the row.
            # Never silently unaccept those; a human has to look.
            mixed.append(record)
            continue

        language = "fr" if verdicts.get("fr", 0) >= verdicts.get("es", 0) else "es"
        record["new_language"] = language
        record["previous_accept"] = row.get("accept")
        row["language"] = language
        row["is_donor"] = "yes"
        if not args.keep_accepted:
            row["accept"] = ""
            row["note"] = ((row.get("note") or "") +
                           " | 2026-08-16 donor-language row: game data is "
                           f"{language} at all {sum(verdicts.values())} positions; "
                           "unaccepted per the English/Korean-only rule").strip(" |")
        changed.append(record)

    print(f"donor-language rows reclassified : {len(changed)}")
    print(f"  by language                    : "
          f"{dict(Counter(c['new_language'] for c in changed))}")
    print(f"  in-game positions they cover   : {sum(c['locations_checked'] for c in changed)}")
    print(f"  accept cleared                 : {not args.keep_accepted}")
    print(f"rows left for a human (mixed)    : {len(mixed)}")
    for record in mixed[:10]:
        print(f"    gcx {record['gcx']} res {record['resource']}: {record['game_language_counts']}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({
            "format": "mgs3d-donor-reclassify-v1",
            "codec": args.codec.as_posix(),
            "master": args.master.as_posix(),
            "applied": bool(args.apply),
            "kept_accepted": bool(args.keep_accepted),
            "reclassified": changed,
            "needs_human": mixed,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"report -> {args.report}")

    if args.apply and changed:
        backup = args.master.with_suffix(args.master.suffix + ".bak-pre-donor-reclass-20260816")
        if not backup.exists():
            shutil.copy2(args.master, backup)
            print(f"backup -> {backup}")
        with args.master.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {args.master}")
    elif not args.apply:
        print("(report only -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
