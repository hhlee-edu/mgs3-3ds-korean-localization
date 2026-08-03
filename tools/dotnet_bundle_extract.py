#!/usr/bin/env python3
"""Extract files from a modern .NET single-file bundle."""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path


SIGNATURE = bytes.fromhex(
    "8b1202b96a612038727b930214d7a03213f5b9e6efae3318ee3b2dce24b36aae"
)


def seven_bit_int(data: bytes, cursor: int) -> tuple[int, int]:
    value = shift = 0
    for _ in range(5):
        byte = data[cursor]
        cursor += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, cursor
        shift += 7
    raise ValueError("invalid 7-bit encoded integer")


def string(data: bytes, cursor: int) -> tuple[str, int]:
    size, cursor = seven_bit_int(data, cursor)
    end = cursor + size
    return data[cursor:end].decode("utf-8"), end


def manifest(data: bytes) -> dict[str, object]:
    marker = data.find(SIGNATURE)
    if marker < 8:
        raise ValueError(".NET bundle signature is missing")
    header = struct.unpack_from("<q", data, marker - 8)[0]
    major, minor, count = struct.unpack_from("<IIi", data, header)
    cursor = header + 12
    bundle_id, cursor = string(data, cursor)
    if major >= 2:
        cursor += 40
    files = []
    for _ in range(count):
        offset, size = struct.unpack_from("<qq", data, cursor)
        cursor += 16
        compressed = 0
        if major >= 6:
            compressed = struct.unpack_from("<q", data, cursor)[0]
            cursor += 8
        file_type = data[cursor]
        cursor += 1
        name, cursor = string(data, cursor)
        files.append({
            "path": name,
            "offset": offset,
            "size": size,
            "compressed_size": compressed,
            "type": file_type,
        })
    return {
        "major": major,
        "minor": minor,
        "bundle_id": bundle_id,
        "header_offset": header,
        "files": files,
    }


def extract(bundle: Path, output: Path) -> dict[str, object]:
    data = bundle.read_bytes()
    report = manifest(data)
    for row in report["files"]:
        stored_size = row["compressed_size"] or row["size"]
        payload = data[row["offset"]:row["offset"] + stored_size]
        if row["compressed_size"]:
            payload = zlib.decompress(payload, -zlib.MAX_WBITS)
        if len(payload) != row["size"]:
            raise ValueError(f"bundle entry size mismatch: {row['path']}")
        target = output / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (output / "bundle-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = extract(args.bundle, args.output)
    print(f"extracted {len(result['files'])} files from bundle {result['bundle_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
