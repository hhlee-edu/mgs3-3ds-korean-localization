#!/usr/bin/env python3
"""Rebase translation rows onto an exact media source by record/entry identity."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("translation", type=Path)
    p.add_argument("source_inspect", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    with args.source_inspect.open(encoding="utf-8-sig", newline="") as f:
        source = {(r["record"], r["entry"]): r for r in csv.DictReader(f)}
    with args.translation.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); rows = list(reader); fields = list(reader.fieldnames or [])
    if "fixed_capacity" not in fields:
        fields.append("fixed_capacity")
    missing = []
    for row in rows:
        key = (row["record"], row["entry"])
        exact = source.get(key)
        if exact is None or exact["entry_type"] != "1":
            missing.append(key); continue
        for field in ("index", "entry_type", "offset", "size", "fixed_capacity", "preview", "raw_text"):
            row[field] = exact[field]
        row["source_file"] = str(args.source_inspect)
    if missing:
        raise ValueError(f"{len(missing)} record/entry rows absent from exact source: {missing[:10]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(f"rebased={len(rows)} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
