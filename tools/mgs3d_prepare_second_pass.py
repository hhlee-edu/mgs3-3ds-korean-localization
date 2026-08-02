#!/usr/bin/env python3
"""Prepare a provenance-aware second-pass CSV from an English review export."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def key(row: dict[str, str]) -> str:
    return row.get("english_sequence", "") or row.get("english", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reviewed", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("sources", type=Path, nargs="+")
    parser.add_argument("--flag", action="append", default=[], metavar="SEQUENCE=NOTE")
    parser.add_argument("--resolve", action="append", default=[], metavar="SEQUENCE=KOREAN",
                        help="replace a sequence's Korean text and mark it corrected")
    args = parser.parse_args()

    fields, rows = read_rows(args.reviewed)
    source_korean: dict[str, str] = {}
    for path in args.sources:
        _, source_rows = read_rows(path)
        for row in source_rows:
            source_korean.setdefault(key(row), row.get("korean", ""))
    flags: dict[str, str] = {}
    for value in args.flag:
        sequence, separator, note = value.partition("=")
        if not separator:
            parser.error(f"invalid --flag (expected SEQUENCE=NOTE): {value}")
        flags[sequence] = note
    resolutions: dict[str, str] = {}
    for value in args.resolve:
        sequence, separator, korean = value.partition("=")
        if not separator or not korean.strip():
            parser.error(f"invalid --resolve (expected SEQUENCE=KOREAN): {value}")
        resolutions[sequence] = korean.strip()

    for field in ("disposition", "correction_note"):
        if field not in fields:
            fields.append(field)
    corrected: set[str] = set()
    confirmed: set[str] = set()
    flagged: set[str] = set()
    for row in rows:
        sequence = key(row)
        if sequence in resolutions:
            row["korean"] = resolutions[sequence]
            row["disposition"] = "corrected"
            row["accept"] = "yes"
            row["correction_note"] = "2차 문맥 검수 교정"
            corrected.add(sequence)
        elif sequence in flags:
            row["disposition"] = ""
            row["accept"] = ""
            row["correction_note"] = flags[sequence]
            flagged.add(sequence)
        elif row.get("korean", "") != source_korean.get(sequence, ""):
            row["disposition"] = "corrected"
            row["accept"] = "yes"
            corrected.add(sequence)
        else:
            row["disposition"] = "confirmed"
            row["accept"] = "yes"
            confirmed.add(sequence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"wrote {args.output}: {len(corrected)} corrected, {len(confirmed)} confirmed, "
        f"{len(flagged)} pending second-pass groups"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
