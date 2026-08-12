#!/usr/bin/env python3
"""Report media translations that exceed immutable subtitle byte capacity."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def encoded_size(text: str) -> int:
    return 1 + sum(1 if ord(char) < 0x80 else 2 for char in text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation", type=Path)
    parser.add_argument("inspect", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.inspect.open(encoding="utf-8-sig", newline="") as stream:
        capacity = {int(row["offset"]): int(row.get("fixed_capacity") or row["size"])
                    for row in csv.DictReader(stream) if row["entry_type"] == "1"}
    with args.translation.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    output = []
    for row in rows:
        size = encoded_size(row["korean"])
        cap = capacity[int(row["offset"])]
        if size > cap:
            output.append({"media": row["media"], "record": row["record"],
                           "entry": row["entry"], "offset": row["offset"],
                           "capacity_bytes": cap, "current_bytes": size,
                           "deficit_bytes": size - cap, "english": row["preview"],
                           "current_korean": row["korean"], "fixed_korean": ""})
    fields = list(output[0]) if output else ["media", "record", "entry", "offset",
        "capacity_bytes", "current_bytes", "deficit_bytes", "english",
        "current_korean", "fixed_korean"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    print(f"overflows={len(output)} deficit_bytes={sum(int(r['deficit_bytes']) for r in output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
