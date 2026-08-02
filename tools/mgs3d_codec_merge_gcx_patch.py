#!/usr/bin/env python3
"""Replace complete GCX selections in a full translation JSON with a focused patch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("patch", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    base = json.loads(args.base.read_text(encoding="utf-8-sig"))
    patch = json.loads(args.patch.read_text(encoding="utf-8-sig"))
    patch_gcxs = {int(row["gcx"]) for row in patch.get("units", [])}
    units = [row for row in base.get("units", []) if int(row["gcx"]) not in patch_gcxs]
    units.extend(patch.get("units", []))
    output = dict(base)
    output["units"] = sorted(units, key=lambda row: (int(row["gcx"]), int(row["resource"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {len(patch_gcxs)} GCXs; {len(output['units'])} total units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
