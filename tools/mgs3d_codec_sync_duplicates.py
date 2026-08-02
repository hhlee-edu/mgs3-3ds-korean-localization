#!/usr/bin/env python3
"""Copy reviewed selections to byte-identical Codec resources in other GCXs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-gcx", type=int, required=True)
    parser.add_argument("--target-gcx", type=int, action="append", required=True)
    parser.add_argument("--first-resource", type=int, required=True)
    parser.add_argument("--last-resource", type=int, required=True)
    args = parser.parse_args()

    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    records = parse_codec(args.codec.read_bytes())
    units = {(int(row["gcx"]), int(row["resource"])): row
             for row in document["units"]}
    source_resources = records[args.source_gcx].resources()
    copied = removed = skipped = 0
    for target_gcx in args.target_gcx:
        target_resources = records[target_gcx].resources()
        for resource in range(args.first_resource, args.last_resource + 1):
            if (resource >= len(source_resources) or resource >= len(target_resources)
                    or source_resources[resource].data != target_resources[resource].data):
                skipped += 1
                continue
            source = units.get((args.source_gcx, resource))
            target_key = (target_gcx, resource)
            if source is None or str(source["text"]) == "<00>":
                if target_key in units and str(units[target_key]["text"]) != "<00>":
                    del units[target_key]
                    removed += 1
            else:
                row = dict(source)
                row["gcx"] = target_gcx
                units[target_key] = row
                copied += 1
    output = dict(document)
    output["units"] = sorted(units.values(), key=lambda x: (int(x["gcx"]), int(x["resource"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"copied {copied}, removed {removed}, skipped nonidentical {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
