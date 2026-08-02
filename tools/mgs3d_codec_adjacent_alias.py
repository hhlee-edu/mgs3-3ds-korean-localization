#!/usr/bin/env python3
"""Alias adjacent identical GCX strings without changing any record boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, align, crypt, parse_codec  # noqa: E402


def alias_record(record, all_duplicates: bool = False):
    resources = record.resources()
    strings_start = record.block_start + record.string_resources_offset
    strings_end = record.block_start + record.font_data_offset
    capacity = strings_end - strings_start
    plain = bytearray()
    words = []
    groups = []
    seen: dict[tuple[int, bytes], tuple[int, int]] = {}
    duplicate_groups: dict[tuple[int, bytes], list[int]] = {}
    index = 0
    while index < len(resources):
        if all_duplicates:
            resource = resources[index]
            key = (resource.flags, resource.data)
            if key in seen:
                offset, first = seen[key]
                words.append(resource.flags | offset)
                duplicate_groups.setdefault(key, [first]).append(index)
            else:
                offset = len(plain)
                seen[key] = (offset, index)
                words.append(resource.flags | offset)
                plain.extend(resource.data)
            index += 1
            continue
        end = index + 1
        resource = resources[index]
        while (end < len(resources)
               and resources[end].flags == resource.flags
               and resources[end].data == resource.data
               and resource.data not in (b"", b"\0")):
            end += 1
        offset = len(plain)
        if end - index > 1:
            words.extend(resource.flags | offset for _ in range(index, end))
            plain.extend(resource.data)
            groups.append({"first": index, "last": end - 1,
                           "copies": end - index,
                           "bytes_saved": (end - index - 1) * len(resource.data)})
        else:
            words.append(resource.flags | offset)
            plain.extend(resource.data)
        index = end
    if all_duplicates:
        groups = [
            {"first": indices[0], "last": indices[-1],
             "resources": indices, "copies": len(indices),
             "bytes_saved": (len(indices) - 1) * len(key[1])}
            for key, indices in duplicate_groups.items()
        ]
    if len(plain) > capacity:
        raise CodecError("alias output exceeds original string region")
    saved = capacity - len(plain)
    plain.extend(b"\0" * saved)
    output = bytearray(record.raw)
    output[strings_start:strings_end] = crypt(record.seed, bytes(plain))
    table = record.block_start + record.resource_table_offset
    for index, word in enumerate(words):
        struct.pack_into("<I", output, table + index * 4, word)
    if len(output) != len(record.raw) or len(output) != align(len(output)):
        raise CodecError("alias changed record size or alignment")
    return bytes(output), groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--all-duplicates", action="store_true",
                        help="alias every identical flags+bytes resource within each GCX")
    args = parser.parse_args()

    source = args.codec.read_bytes()
    records = parse_codec(source)
    output = []
    report = []
    for gcx, record in enumerate(records):
        raw, groups = alias_record(record, args.all_duplicates)
        output.append(raw)
        if groups:
            report.append({"gcx": gcx, "groups": groups,
                           "bytes_saved": sum(g["bytes_saved"] for g in groups)})
    built = b"".join(output)
    verified = parse_codec(built)
    if len(built) != len(source) or len(verified) != len(records):
        raise CodecError("alias changed codec size or record count")
    if any(a.source_offset != b.source_offset or len(a.raw) != len(b.raw)
           for a, b in zip(records, verified)):
        raise CodecError("alias changed a GCX boundary")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(built)
    payload = {"format": "mgs3d-codec-adjacent-alias-v1",
               "source_sha256": hashlib.sha256(source).hexdigest(),
               "output_sha256": hashlib.sha256(built).hexdigest(),
               "records": report,
               "groups": sum(len(row["groups"]) for row in report),
               "bytes_saved": sum(row["bytes_saved"] for row in report)}
    if args.report:
        args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
