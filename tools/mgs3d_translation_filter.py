#!/usr/bin/env python3
"""Filter MGS3D translation units by GCX and resource index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gcx", type=int, required=True)
    parser.add_argument("--resource", type=int, action="append")
    parser.add_argument("--keep-donors", action="store_true",
                        help="retain <00> donor units when filtering resources")
    parser.add_argument("--first", type=int)
    parser.add_argument("--first-nonempty", type=int,
                        help="keep all <00> donor units and the first N other units")
    args = parser.parse_args()

    document = json.loads(args.source.read_text(encoding="utf-8-sig"))
    units = [unit for unit in document.get("units", [])
             if int(unit["gcx"]) == args.gcx]
    units.sort(key=lambda unit: int(unit["resource"]))
    if args.resource:
        wanted = set(args.resource)
        units = [unit for unit in units
                 if int(unit["resource"]) in wanted
                 or (args.keep_donors and str(unit.get("text")) == "<00>")]
    if args.first is not None:
        if args.first < 0:
            parser.error("--first must be non-negative")
        units = units[:args.first]
    if args.first_nonempty is not None:
        if args.first_nonempty < 0:
            parser.error("--first-nonempty must be non-negative")
        nonempty = [unit for unit in units if str(unit.get("text")) != "<00>"]
        chosen = {(int(unit["gcx"]), int(unit["resource"]))
                  for unit in nonempty[:args.first_nonempty]}
        units = [unit for unit in units
                 if str(unit.get("text")) == "<00>"
                 or (int(unit["gcx"]), int(unit["resource"])) in chosen]

    output = dict(document)
    output["units"] = units
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"selected {len(units)} units: "
          f"{[int(unit['resource']) for unit in units]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
