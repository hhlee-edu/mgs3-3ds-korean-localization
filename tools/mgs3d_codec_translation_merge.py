#!/usr/bin/env python3
"""Merge official and 3DS-only codec translations with official Korean priority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def has_hangul(text: str) -> bool:
    return any(0xAC00 <= ord(char) <= 0xD7A3 for char in text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("official", type=Path)
    parser.add_argument("three_ds", type=Path)
    parser.add_argument("static_allocation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    official = json.loads(args.official.read_text(encoding="utf-8-sig"))
    extra = json.loads(args.three_ds.read_text(encoding="utf-8-sig"))
    static = json.loads(args.static_allocation.read_text(encoding="utf-8-sig"))["characters"]
    merged = {(int(unit["gcx"]), int(unit["resource"])): unit
              for unit in official["units"]}
    added = replaced = preserved = 0
    for unit in extra["units"]:
        key = (int(unit["gcx"]), int(unit["resource"]))
        current = merged.get(key)
        if current is None:
            merged[key] = unit
            added += 1
        elif has_hangul(str(current["text"])):
            preserved += 1
        elif has_hangul(str(unit["text"])):
            merged[key] = unit
            replaced += 1
    units = [merged[key] for key in sorted(merged)]
    result = {
        "format": "mgs3d-codec-translation-v1",
        "note": "Official Korean reference plus non-overlapping 3DS-only Korean; official Korean wins conflicts.",
        "character_map": static,
        "units": units,
        "merge_summary": {"official_units": len(official["units"]),
                          "three_ds_units": len(extra["units"]), "added": added,
                          "replaced_non_korean": replaced,
                          "official_korean_preserved": preserved,
                          "merged_units": len(units),
                          "hangul_units": sum(has_hangul(str(unit["text"])) for unit in units)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["merge_summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
