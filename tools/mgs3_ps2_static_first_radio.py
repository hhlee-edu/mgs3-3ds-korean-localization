#!/usr/bin/env python3
"""Build a four-copy first-radio translation using an HPK static allocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mgs3_ps2_official_first_radio import OFFICIAL


GCX_COPIES = (15, 17, 51, 53)
DIAGNOSTIC_DONORS = (18, 19, 20, 22, 23, 24, 25, 26, 30, 31)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("allocation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--no-donors", action="store_true")
    args = parser.parse_args()

    allocation = json.loads(args.allocation.read_text(encoding="utf-8-sig"))
    character_map = allocation["characters"]
    missing = sorted(
        {
            character
            for text in OFFICIAL.values()
            for character in text
            if 0xAC00 <= ord(character) <= 0xD7A3 and character not in character_map
        }
    )
    document = {
        "format": "mgs3d-codec-translation-v1",
        "character_map": character_map,
        "units": [
            {
                "gcx": gcx,
                "resource": resource,
                "kind": "string",
                "text": text,
            }
            for gcx in GCX_COPIES
            for resource, text in sorted(OFFICIAL.items())
        ]
        + ([] if args.no_donors else [
            {
                "gcx": gcx,
                "resource": resource,
                "kind": "string",
                "text": "<00>",
                "diagnostic_donor": True,
            }
            for gcx in GCX_COPIES
            for resource in DIAGNOSTIC_DONORS
        ]),
        "ps2_official_port": {
            "scope": "first-radio-paragraph-static-page",
            "gcx_copies": list(GCX_COPIES),
            "resources": sorted(OFFICIAL),
            "diagnostic_donors": list(DIAGNOSTIC_DONORS),
            "static_allocation": str(args.allocation),
            "local_hangul": missing,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(document['units'])} targets to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
