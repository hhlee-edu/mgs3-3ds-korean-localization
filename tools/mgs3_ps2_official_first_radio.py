#!/usr/bin/env python3
"""Create a translation document with the PS2 Korean first radio paragraph.

Only EN GCX 15 resources 14..17 are changed.  Resource indices, terminators,
line controls, and the EN procedure are therefore left to the fixed-layout
codec builder instead of importing any cross-region binary structure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


OFFICIAL = {
    14: "잘 들리나?<0A>그곳은 이미 적지다.<0A>도청될 위험성이 있지.<0A><00>",
    15: "이후부터는 서로 암호명으로<0A>부르도록 하겠다.<0A><00>",
    16: '이번 임무의 코드네임은<0A>"네이키드 스네이크"다.<0A>이후부터 스네이크라 부르겠다.<0A><00>',
    17: "본명은 입 밖에 내지 않도록.<0A><00>",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--whole-gcx",
        action="store_true",
        help="retain every GCX 15 unit so its string space can fund new glyphs",
    )
    args = parser.parse_args()

    document = json.loads(args.source.read_text(encoding="utf-8"))
    changed = set()
    selected = []
    for unit in document.get("units", []):
        gcx, resource = int(unit["gcx"]), int(unit["resource"])
        if args.whole_gcx and gcx == 15:
            selected.append(unit)
        if gcx == 15 and resource in OFFICIAL:
            unit["text"] = OFFICIAL[resource]
            changed.add(resource)
            if not args.whole_gcx:
                selected.append(unit)
    missing = sorted(set(OFFICIAL) - changed)
    if missing:
        raise SystemExit(f"missing GCX 15 resources: {missing}")
    document["units"] = sorted(selected, key=lambda unit: int(unit["resource"]))

    document["ps2_official_port"] = {
        "scope": "first-radio-paragraph",
        "gcx": 15,
        "resources": sorted(OFFICIAL),
        "structure": "EN index/procedure preserved; Unicode text re-encoded to local glyphs",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"gcx": 15, "resources": sorted(changed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
