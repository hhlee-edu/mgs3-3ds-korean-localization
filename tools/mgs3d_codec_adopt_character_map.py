#!/usr/bin/env python3
"""Adopt a verified codec character map without altering translation units."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("translation", type=Path)
    ap.add_argument("map_source", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    document = json.loads(args.translation.read_text(encoding="utf-8"))
    source = json.loads(args.map_source.read_text(encoding="utf-8"))
    mapping = source.get("character_map")
    if not isinstance(mapping, dict) or not mapping:
        raise SystemExit("map source has no character_map")
    document["character_map"] = mapping
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"character_map={len(mapping)} units={len(document.get('units', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
