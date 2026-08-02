#!/usr/bin/env python3
"""Decompress Nintendo backward-LZ (.code BLZ) files."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def decompress(source: bytes) -> bytes:
    if len(source) < 8:
        raise ValueError("BLZ input is too short")
    footer, extra = struct.unpack_from("<II", source, len(source) - 8)
    encoded_size = footer & 0x00FFFFFF
    header_size = footer >> 24
    if not 8 <= header_size <= 11 or not header_size <= encoded_size <= len(source):
        raise ValueError("invalid BLZ footer")
    output = bytearray(source)
    output.extend(b"\0" * extra)
    source_pos = len(source) - header_size
    source_limit = len(source) - encoded_size
    output_pos = len(output)
    while source_pos > source_limit and output_pos > 0:
        source_pos -= 1
        flags = source[source_pos]
        for _ in range(8):
            if flags & 0x80:
                if source_pos - 2 < source_limit:
                    raise ValueError("truncated BLZ back-reference")
                source_pos -= 2
                value = source[source_pos] | source[source_pos + 1] << 8
                length = (value >> 12) + 3
                displacement = (value & 0x0FFF) + 3
                for _ in range(length):
                    output_pos -= 1
                    copy_pos = output_pos + displacement
                    if output_pos < 0 or copy_pos >= len(output):
                        raise ValueError("invalid BLZ back-reference")
                    output[output_pos] = output[copy_pos]
            else:
                if source_pos <= source_limit:
                    break
                source_pos -= 1
                output_pos -= 1
                output[output_pos] = source[source_pos]
            flags = (flags << 1) & 0xFF
            if source_pos <= source_limit or output_pos <= 0:
                break
    if output_pos != source_limit:
        raise ValueError(f"BLZ output did not meet prefix: {output_pos:#x} != {source_limit:#x}")
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = decompress(args.source.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(f"wrote {len(result)} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
