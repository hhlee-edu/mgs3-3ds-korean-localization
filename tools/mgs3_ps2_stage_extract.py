#!/usr/bin/env python3
"""Minimal Python extractor for encrypted/compressed PS2 MGS3 STAGE.DAT stages."""

from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

KEY1, KEY2, KEY34 = 0x02E90EDD, 0x7A88FB59, 0xA78925D9
KEY6, KEY7, KEY8 = 0x9385, 0x116, 0x6576


def words(data: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(data)//4}I", data))


def pack(values: list[int]) -> bytes:
    return struct.pack(f"<{len(values)}I", *values)


def decrypt_header(data: bytes, initial: int) -> bytes:
    out, key = [], initial
    for value in words(data):
        out.append(value ^ key)
        key = (key * KEY1 + (initial ^ 0xF0F0)) & 0xFFFFFFFF
    return pack(out)


def strcode24(name: bytes) -> int:
    value = 0
    for char in name.split(b"\0", 1)[0]:
        value = (((value << 5) | (value >> 19)) + char) & 0xFFFFFF
    return value or 1


def decrypt_stage(data: bytes, initial: int, name: bytes) -> bytes:
    namehash = strcode24(name)
    work = ((namehash << 7) + initial + namehash + KEY34) & 0xFFFFFFFF
    step = ((namehash << 7) + namehash + KEY2) & 0xFFFFFFFF
    out = []
    for value in words(data):
        out.append(value ^ work)
        work = (work * KEY1 + step) & 0xFFFFFFFF
    return pack(out)


def decrypt_content(data: bytes) -> bytes:
    values = words(data)
    key5 = values[0] & 0xFFFF
    workv = key5 ^ KEY6
    step = (workv * KEY7) & 0xFFFFFFFF
    work = (workv | ((workv ^ KEY8) << 16)) & 0xFFFFFFFF
    out = []
    for value in values:
        out.append(value ^ work)
        work = (work * KEY1 + step) & 0xFFFFFFFF
    out[0] = (out[0] & 0xFFFF0000) | ((out[0] + 0x8F3) & 0xFFFF)
    return pack(out)


def align(value: int, amount: int) -> int:
    return (value + amount - 1) // amount * amount


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dat", type=Path)
    ap.add_argument("output", type=Path, nargs="?")
    ap.add_argument("--stage", action="append")
    ap.add_argument("--all", action="store_true",
                    help="extract every stage")
    ap.add_argument("--list", action="store_true",
                    help="list stage names without extracting")
    args = ap.parse_args()
    data = args.dat.read_bytes()
    initial = struct.unpack_from("<I", data)[0]
    header = decrypt_header(data[4:16], initial)
    version, blocks, count, game, unknown = struct.unpack("<HHHHI", header)
    table = decrypt_header(data[4:4 + 12 + count * 12], initial)
    stages = []
    for index in range(count):
        raw_name, sector = struct.unpack_from("<8sI", table, 12 + index * 12)
        stages.append((index, raw_name, sector * 0x800))
    print(f"header version={version} blocks={blocks} stages={count} game={game:#x} hash={unknown:#x}")
    if args.list:
        for index, raw_name, stage_start in stages:
            name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
            print(f"{index:4d} {name:8s} offset={stage_start:#010x}")
        return 0
    if not args.output or (not args.stage and not args.all):
        ap.error("output and at least one --stage are required unless --list is used")
    wanted = {raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
              for _, raw_name, _ in stages} if args.all else set(args.stage)
    for index, raw_name, stage_start in stages:
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        if name not in wanted:
            continue
        first = decrypt_stage(data[stage_start:stage_start + 4], initial, raw_name)
        info_size = struct.unpack("<I", first)[0] * 8 + 4
        info = decrypt_stage(data[stage_start:stage_start + info_size], initial, raw_name)[4:]
        entries = [struct.unpack_from("<II", info, pos) for pos in range(0, len(info), 8)]
        data_start = align(stage_start + info_size, 0x800)
        outdir = args.output / name
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "index.bin").write_bytes(info)
        cursor = 0
        files_written = 0
        # Compressed groups carry offsets relative to data_start.  Plain PSQ
        # groups follow the packed groups at the next sector boundary.
        packed_end = 0
        scan = 0
        while scan + 1 < len(entries):
            folder, unpacked_size = entries[scan]
            if not folder or not unpacked_size:
                break
            scan += 1
            if folder not in {0x7F000010, 0x7F000005, 0x7F000004}:
                compressed_size = entries[scan][0] & 0xFFFFFF
                relative = entries[scan][1]
                packed_end = max(packed_end, relative + align(compressed_size, 4))
            scan += 1
            while scan + 1 < len(entries) and entries[scan][0] != 0x7F000000:
                scan += 1
            scan += 1
        plain_start = align(data_start + packed_end, 0x800)
        while cursor + 1 < len(entries):
            folder, unpacked_size = entries[cursor]
            if not folder or not unpacked_size:
                break
            cursor += 1
            if folder in {0x7F000010, 0x7F000005, 0x7F000004}:
                unpacked = data[plain_start:plain_start + unpacked_size]
                if len(unpacked) != unpacked_size:
                    raise ValueError(f"{name}: truncated plain group")
                plain_start = align(plain_start + unpacked_size, 0x800)
                while cursor + 1 < len(entries) and entries[cursor][0] != 0x7F000000:
                    hashed, offset = entries[cursor]
                    next_offset = entries[cursor + 1][1]
                    stem = hashed & 0xFFFFFF
                    (outdir / f"{stem:05x}.psq").write_bytes(unpacked[offset:next_offset])
                    files_written += 1
                    cursor += 1
                cursor += 1
                continue
            compressed_size = entries[cursor][0] & 0xFFFFFF
            relative = entries[cursor][1]
            read_size = align(compressed_size, 4)
            encrypted = decrypt_content(data[data_start + relative:data_start + relative + read_size])
            unpacked = zlib.decompress(encrypted)
            if len(unpacked) != unpacked_size:
                raise ValueError(f"{name}: expected {unpacked_size}, got {len(unpacked)}")
            cursor += 1
            while cursor + 1 < len(entries) and entries[cursor][0] != 0x7F000000:
                hashed, offset = entries[cursor]
                next_offset = entries[cursor + 1][1]
                extension, stem = hashed >> 24, hashed & 0xFFFFFF
                (outdir / f"{folder:08x}_{stem:06x}.{extension:02x}").write_bytes(
                    unpacked[offset:next_offset])
                files_written += 1
                cursor += 1
            cursor += 1
        print(f"extracted stage {index} {name}: {files_written} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
