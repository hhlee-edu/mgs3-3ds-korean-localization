#!/usr/bin/env python3
"""Apply an HPK static-glyph allocation as a codec translation character map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation", type=Path)
    parser.add_argument("allocation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--overlay",
        type=Path,
        action="append",
        help="replace/add units by GCX/resource before applying the static map",
    )
    parser.add_argument(
        "--replace-character-map",
        action="store_true",
        help="replace a previous static allocation instead of merging it",
    )
    args = parser.parse_args()

    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    units = {
        (int(unit["gcx"]), int(unit["resource"])): unit
        for unit in document.get("units", [])
    }
    for overlay_path in args.overlay or []:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8-sig"))
        for unit in overlay.get("units", []):
            units[(int(unit["gcx"]), int(unit["resource"]))] = unit
    document["units"] = [units[key] for key in sorted(units)]
    allocation = json.loads(args.allocation.read_text(encoding="utf-8-sig"))
    existing = ({} if args.replace_character_map
                else dict(document.get("character_map", {})))
    overlap = set(existing) & set(allocation["characters"])
    if any(existing[key].upper() != allocation["characters"][key].upper()
           for key in overlap):
        raise SystemExit("static allocation conflicts with the existing character map")
    existing.update(allocation["characters"])
    document["character_map"] = existing
    document["static_korean_allocation"] = str(args.allocation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {len(document.get('units', []))} units with "
        f"{len(existing)} static mappings to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
