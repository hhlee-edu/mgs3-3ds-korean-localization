#!/usr/bin/env python3
"""Point selected identical GCX resources at one address without compacting data."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, parse_codec  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gcx", type=int, required=True)
    parser.add_argument("--resource", type=int, action="append", required=True)
    args = parser.parse_args()
    if len(args.resource) < 2:
        raise CodecError("pointer alias probe needs at least two resources")

    source = args.codec.read_bytes()
    records = parse_codec(source)
    record = records[args.gcx]
    resources = record.resources()
    selected = [resources[index] for index in args.resource]
    if any(item.flags != selected[0].flags or item.data != selected[0].data
           for item in selected[1:]):
        raise CodecError("selected resources are not byte-identical with matching flags")

    raw = bytearray(record.raw)
    table = record.block_start + record.resource_table_offset
    first_word = struct.unpack_from("<I", raw, table + args.resource[0] * 4)[0]
    first_offset = first_word & 0x00FFFFFF
    for index in args.resource[1:]:
        word = struct.unpack_from("<I", raw, table + index * 4)[0]
        struct.pack_into("<I", raw, table + index * 4,
                         (word & 0xFF000000) | first_offset)

    outputs = [item.raw for item in records]
    outputs[args.gcx] = bytes(raw)
    built = b"".join(outputs)
    reparsed = parse_codec(built)
    if len(built) != len(source) or len(reparsed) != len(records):
        raise CodecError("probe changed codec size or record count")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(built)
    print(f"GCX {args.gcx} resources {args.resource} -> offset {first_offset:#x}; "
          f"sha256={hashlib.sha256(built).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
