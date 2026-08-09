#!/usr/bin/env python3
"""Inventory every codec.dat GCX's custom-glyph slots: how many exist, how
many are referenced by currently-live text, and how many are dead (zero
live references) and therefore reusable for new Hangul glyphs without
appending to (and growing) the GCX. See dead_font_slots()/glyph_slot_owners()
in mgs3d_gcx_font_tool.py for the exact-parse scan this report is built on.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, sha256  # noqa: E402
from mgs3d_gcx_font_tool import GLYPH_SIZE, dead_font_slots, font_region  # noqa: E402
from mgs3d_translation import validate_codec_translation  # noqa: E402


FORMAT = "mgs3d-codec-dead-glyph-inventory-v1"
CSV_FIELDS = [
    "GCX",
    "total_slots",
    "referenced_slots",
    "dead_slots",
    "reusable_bytes",
    "new_korean_needed",
    "remaining_shortage",
]


def hangul_needed_by_gcx(translation_path: Path) -> dict[int, int]:
    """Unique new Hangul characters each GCX's translation units need,
    beyond whatever the translation's own character_map already covers."""
    document = json.loads(translation_path.read_text(encoding="utf-8-sig"))
    base_map, units = validate_codec_translation(document)
    needed: dict[int, set[str]] = {}
    for unit in units:
        gcx = int(unit["gcx"])
        chars = needed.setdefault(gcx, set())
        for character in str(unit["text"]):
            if 0xAC00 <= ord(character) <= 0xD7A3 and character not in base_map:
                chars.add(character)
    return {gcx: len(chars) for gcx, chars in needed.items()}


def build_inventory(
    codec_path: Path,
    translation_path: Path | None,
    gcx_filter: set[int] | None,
) -> dict[str, object]:
    data = codec_path.read_bytes()
    records = parse_codec(data)
    needed_by_gcx = hangul_needed_by_gcx(translation_path) if translation_path else {}

    records_out: list[dict[str, object]] = []
    total_slots = total_dead = 0
    for gcx, record in enumerate(records):
        if gcx_filter is not None and gcx not in gcx_filter:
            continue
        _, total = font_region(record)
        if total == 0:
            continue
        dead = dead_font_slots(record, set())
        dead_count = len(dead)
        referenced = total - dead_count
        needed = needed_by_gcx.get(gcx, 0)
        row = {
            "gcx": gcx,
            "total_slots": total,
            "referenced_slots": referenced,
            "dead_slots": dead_count,
            "dead_slot_indices": dead,
            "reusable_bytes": dead_count * GLYPH_SIZE,
            "new_korean_needed": needed,
            "remaining_shortage": max(0, needed - dead_count),
        }
        records_out.append(row)
        total_slots += total
        total_dead += dead_count

    summary = {
        "total_gcx": len(records),
        "gcx_with_font": len(records_out),
        "gcx_with_dead_slots": sum(1 for r in records_out if r["dead_slots"]),
        "total_slots": total_slots,
        "total_dead_slots": total_dead,
        "total_reusable_bytes": total_dead * GLYPH_SIZE,
    }
    document = {
        "format": FORMAT,
        "source_codec_sha256": sha256(data),
        "records": records_out,
        "summary": summary,
    }
    if translation_path:
        document["translation_sha256"] = sha256(translation_path.read_bytes())
    return document


def write_csv(document: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in document["records"]:
            writer.writerow(
                {
                    "GCX": row["gcx"],
                    "total_slots": row["total_slots"],
                    "referenced_slots": row["referenced_slots"],
                    "dead_slots": row["dead_slots"],
                    "reusable_bytes": row["reusable_bytes"],
                    "new_korean_needed": row["new_korean_needed"],
                    "remaining_shortage": row["remaining_shortage"],
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument(
        "--translation", type=Path,
        help="translation.json to compute new_korean_needed/remaining_shortage; "
             "omit for a structural-only report",
    )
    parser.add_argument("--csv", type=Path, help="also write the CSV view")
    parser.add_argument(
        "--gcx", type=int, action="append",
        help="restrict the scan to specific GCX indices (repeatable)",
    )
    args = parser.parse_args()

    gcx_filter = set(args.gcx) if args.gcx else None
    document = build_inventory(args.codec, args.translation, gcx_filter)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.csv:
        write_csv(document, args.csv)

    summary = document["summary"]
    print(
        f"scanned {summary['total_gcx']} GCX, {summary['gcx_with_font']} with a font "
        f"table; {summary['gcx_with_dead_slots']} have dead slots "
        f"({summary['total_dead_slots']}/{summary['total_slots']} slots, "
        f"{summary['total_reusable_bytes']} reusable bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
