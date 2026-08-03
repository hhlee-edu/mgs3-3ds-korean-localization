#!/usr/bin/env python3
"""Add accepted 3DS-only review rows to a codec translation candidate JSON."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from mgs3d_codec_tool import parse_codec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expanded-review", type=Path)
    args = parser.parse_args()

    document = json.loads(args.candidate.read_text(encoding="utf-8-sig"))
    units = document.setdefault("units", [])
    keys = {(int(unit["gcx"]), int(unit["resource"])) for unit in units}
    records = parse_codec(args.codec.read_bytes())
    added = 0
    expanded_rows = []
    with args.review.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        for line, row in enumerate(reader, 2):
            if row.get("accept", "").strip().casefold() not in {"yes", "y", "1", "true", "한글"}:
                continue
            text = (row.get("replacement", "") or row.get("korean", "")).strip()
            if not text:
                raise ValueError(f"accepted row has no Korean text at line {line}")
            if "<00>" not in text:
                text = text.rstrip() + "<0A><00>"
            locations = [item for item in row.get("locations", "").split(";") if item]
            row_keys = ([tuple(map(int, item.split(":"))) for item in locations]
                        if locations else [(int(row["gcx"]), int(row["resource"]))])
            for gcx, resource in row_keys:
                resources = records[gcx].resources() if 0 <= gcx < len(records) else []
                if not 0 <= resource < len(resources) or resources[resource].is_script:
                    raise ValueError(f"invalid string resource at line {line}: {gcx}:{resource}")
                expanded = dict(row)
                expanded["gcx"], expanded["resource"], expanded["korean"] = gcx, resource, text
                expanded_rows.append(expanded)
                key = gcx, resource
                if key in keys:
                    continue
                units.append({"gcx": gcx, "resource": resource, "kind": "string",
                              "original_size": len(resources[resource].data), "text": text})
                keys.add(key)
                added += 1
    units.sort(key=lambda unit: (int(unit["gcx"]), int(unit["resource"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.expanded_review:
        args.expanded_review.parent.mkdir(parents=True, exist_ok=True)
        with args.expanded_review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(expanded_rows)
    print(f"added {added} custom 3DS translations; expanded {len(expanded_rows)} positions; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
