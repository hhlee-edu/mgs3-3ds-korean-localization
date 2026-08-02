#!/usr/bin/env python3
"""Extract one keyed zlib entry from an MGS3D HPK archive."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("key", help="four-byte entry key as eight hex digits")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    key = bytes.fromhex(args.key)
    if len(key) != 4:
        parser.error("key must encode exactly four bytes")
    archive = args.archive.read_bytes()
    offset = archive.find(key)
    if offset < 0:
        raise SystemExit(f"entry key {args.key} not found")
    if archive.find(key, offset + 1) >= 0:
        raise SystemExit(f"entry key {args.key} is not unique")
    unpacked_size, packed_size = struct.unpack_from("<II", archive, offset + 4)
    packed = archive[offset + 12 : offset + 12 + packed_size]
    if len(packed) != packed_size:
        raise SystemExit("truncated HPK entry")
    unpacked = zlib.decompress(packed)
    if len(unpacked) != unpacked_size:
        raise SystemExit(
            f"size mismatch: expected {unpacked_size}, got {len(unpacked)}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(unpacked)
    print(
        f"key={args.key} offset={offset:#x} packed={packed_size} "
        f"unpacked={unpacked_size} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
