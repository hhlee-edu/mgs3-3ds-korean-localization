"""Merge the PERSONAL DATA separator-only scratch into a full translation.

This is deliberately a scratch-only analysis helper. It never edits a master,
staged DAT, or production build; it only writes the requested dry-run JSON.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--personal", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    base = json.loads(args.base.read_text(encoding="utf-8"))
    personal = json.loads(args.personal.read_text(encoding="utf-8"))
    replacements = {(u["gcx"], u["resource"]): u["text"] for u in personal["units"]}
    replaced = 0
    for unit in base["units"]:
        key = (unit["gcx"], unit["resource"])
        if key in replacements:
            unit["text"] = replacements[key]
            replaced += 1
    if replaced != len(replacements):
        missing = sorted(set(replacements) - {(u["gcx"], u["resource"]) for u in base["units"]})
        raise SystemExit(f"replacement locations missing from base: {missing[:10]}")
    base["note"] = "scratch-only merge: PERSONAL DATA separator restoration feasibility"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"replaced_units={replaced}")
    print(f"out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
