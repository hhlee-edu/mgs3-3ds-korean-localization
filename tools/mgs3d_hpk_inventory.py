#!/usr/bin/env python3
"""Inventory and optionally extract every verifiable zlib entry in an MGS3D HPK."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


def scan(data: bytes) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for offset in range(0, len(data) - 14):
        unpacked_size, packed_size = struct.unpack_from("<II", data, offset + 4)
        if not (2 <= packed_size <= len(data) - offset - 12):
            continue
        if not (1 <= unpacked_size <= 256 * 1024 * 1024):
            continue
        if data[offset + 12] != 0x78:
            continue
        packed = data[offset + 12:offset + 12 + packed_size]
        try:
            unpacked = zlib.decompress(packed)
        except zlib.error:
            continue
        if len(unpacked) != unpacked_size:
            continue
        entries.append({
            "offset": offset,
            "key": data[offset:offset + 4].hex(),
            "packed_size": packed_size,
            "unpacked_size": unpacked_size,
            "sha256": hashlib.sha256(unpacked).hexdigest(),
            "data": unpacked,
        })
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    entries = scan(args.archive.read_bytes())
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        for index, entry in enumerate(entries):
            name = f"{index:04d}_{entry['key']}_{entry['offset']:08x}.bin"
            (args.output / name).write_bytes(entry["data"])
    report = {
        "archive": str(args.archive),
        "entry_count": len(entries),
        "entries": [{key: value for key, value in entry.items() if key != "data"}
                    for entry in entries],
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
