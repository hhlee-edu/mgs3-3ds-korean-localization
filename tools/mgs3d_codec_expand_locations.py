#!/usr/bin/env python3
"""Expand a codec translation document to every duplicate location in the master.

`translation/10_master/current/codec.csv` folds identical strings into one row and
records every in-game position in its `locations` column. `make-translation` emits
one unit per row -- the canonical `(gcx, resource)` only -- so the other positions
keep their English. Measured on the v0.81 build that is 193,138 of the 203,449
English display_text location instances in the shipped `codec.dat` (91.3%); byte
capacity accounted for 30. See
`docs/v0.81-hardware-defects-rootcause-2026-08-16.md`.

This copies each canonical unit's already-escaped `text` to its duplicate
locations. A duplicate is only accepted when its **original bytes in the reference
codec.dat are byte-identical to the canonical's** -- the same safety rule
`mgs3d_codec_duplicate_propagate.py` uses. A `locations` entry that names a
different string, or a resource index the record does not have, is skipped and
reported rather than written.

Output is a plain `mgs3d-codec-translation-v1` document, so it feeds
`mgs3d_codec_safe_select.py` (per-GCX byte-capacity gate) exactly like the
unexpanded one. This tool does not check capacity and does not write to staging.

    python tools/mgs3d_codec_expand_locations.py \
        --translation translation/40_build_input/global_page_v2/codec_natural_full_global_page.json \
        --out-doc    <expanded json> \
        --out-report <report json>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec  # noqa: E402

DEFAULT_CODEC = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
DEFAULT_MASTER = ROOT / "translation/10_master/current/codec.csv"
DEFAULT_DOC = ROOT / "translation/40_build_input/global_page_v2/codec_natural_full_global_page.json"


def same_sentence(target: bytes, source: bytes) -> bool:
    """True when two resource payloads carry the same line, ignoring letter case
    and whitespace. Used only under --text-identity; an undecodable payload never
    qualifies, so a Korean or binary payload can never pass this test."""
    from mgs3d_english_korean_match import decode_western
    a, b = decode_western(target), decode_western(source)
    if not a or not b:
        return False
    norm = lambda s: re.sub(r"\s+", " ", s).strip().casefold()
    return norm(a) == norm(b)


def parse_locations(value: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for item in (value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        gcx, _, resource = item.partition(":")
        try:
            out.append((int(gcx), int(resource)))
        except ValueError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codec", type=Path, default=DEFAULT_CODEC)
    ap.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    ap.add_argument("--translation", type=Path, default=DEFAULT_DOC)
    ap.add_argument("--out-doc", type=Path, required=True)
    ap.add_argument("--out-report", type=Path, required=True)
    ap.add_argument("--text-identity", action="store_true",
                    help="also propagate to a duplicate whose original bytes differ but "
                         "whose decoded English is the same line (case/space insensitive)")
    args = ap.parse_args()

    doc = json.loads(args.translation.read_text(encoding="utf-8"))
    records = parse_codec(args.codec.read_bytes())
    # resource payloads of the reference build, for the byte-identity check
    payloads = [ [r.data for r in rec.resources()] for rec in records ]

    canonical = {(int(u["gcx"]), int(u["resource"])): u for u in doc["units"]}

    csv.field_size_limit(10 ** 9)
    with args.master.open(encoding="utf-8-sig", newline="") as stream:
        master = list(csv.DictReader(stream))

    added: list[dict] = []
    skipped: list[dict] = []
    reasons: Counter[str] = Counter()
    rows_expanded = 0

    def original(key: tuple[int, int]) -> bytes | None:
        gcx, resource = key
        if not 0 <= gcx < len(payloads):
            return None
        if not 0 <= resource < len(payloads[gcx]):
            return None
        return payloads[gcx][resource]

    for row in master:
        if (row.get("is_donor") or "") == "yes":
            continue
        try:
            key = (int(row["gcx"]), int(row["resource"]))
        except (KeyError, ValueError):
            continue
        unit = canonical.get(key)
        if unit is None:          # not accepted / not in this build input
            continue
        source = original(key)
        if source is None:
            reasons["canonical missing in reference codec.dat"] += 1
            continue
        row_added = 0
        for location in parse_locations(row.get("locations", "")):
            if location == key or location in canonical:
                continue
            target = original(location)
            if target is None:
                reasons["location out of range"] += 1
                skipped.append({"canonical": list(key), "location": list(location),
                                "reason": "out of range"})
                continue
            if target != source:
                # Byte identity is the default guard. It is stricter than the
                # question we actually care about: does this location hold the same
                # sentence? 118 locations differ only in letter case ("Major!" vs
                # "MAJOR!") and 217 more decode identically while their trailing
                # control bytes differ. Those are the same line and were left in
                # English by the strict guard. --text-identity accepts exactly that
                # set, and still refuses a location whose decoded text differs.
                if not (args.text_identity and same_sentence(target, source)):
                    reasons["original bytes differ from canonical"] += 1
                    skipped.append({"canonical": list(key), "location": list(location),
                                    "reason": "original bytes differ"})
                    continue
                reasons["accepted on decoded-text identity"] += 1
            clone = dict(unit)
            clone["gcx"], clone["resource"] = location
            canonical[location] = clone
            added.append(clone)
            row_added += 1
        if row_added:
            rows_expanded += 1

    out_doc = dict(doc)
    out_doc["units"] = doc["units"] + added
    out_doc["note"] = (doc.get("note", "") +
                       " | duplicate locations expanded via mgs3d_codec_expand_locations.py"
                       ).strip(" |")
    args.out_doc.parent.mkdir(parents=True, exist_ok=True)
    args.out_doc.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    def rel(path: Path) -> str:
        # A caller-supplied path may be relative, or outside ROOT; either made
        # relative_to() raise and lose the whole report after the doc was written.
        try:
            return path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    report = {
        "format": "mgs3d-codec-location-expansion-v1",
        "reference_codec": rel(args.codec),
        "master": rel(args.master),
        "source_translation": rel(args.translation),
        "units_in": len(doc["units"]),
        "units_added": len(added),
        "units_out": len(out_doc["units"]),
        "master_rows_expanded": rows_expanded,
        "skipped_total": len(skipped),
        "skipped_by_reason": dict(reasons),
        "skipped": skipped[:2000],
        "skipped_truncated": len(skipped) > 2000,
    }
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")

    print(f"units {len(doc['units'])} -> {len(out_doc['units'])}  (+{len(added)})")
    print(f"master rows expanded: {rows_expanded}")
    for reason, count in reasons.most_common():
        print(f"  skipped: {reason}: {count}")
    print(f"doc    -> {args.out_doc}")
    print(f"report -> {args.out_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
