#!/usr/bin/env python3
"""Small dependency-free ARM32 scanner for targeted MGS3D code analysis."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def ror(value: int, shift: int) -> int:
    shift &= 31
    return ((value >> shift) | (value << (32 - shift))) & 0xFFFFFFFF if shift else value


def imm12(word: int) -> int:
    return ror(word & 0xFF, ((word >> 8) & 0xF) * 2)


def describe(word: int, address: int) -> str:
    cond = word >> 28
    suffix = "" if cond == 0xE else f".{cond:x}"
    if (word >> 25) & 0x7 == 0b101:
        delta = word & 0xFFFFFF
        if delta & 0x800000:
            delta -= 1 << 24
        target = (address + 8 + delta * 4) & 0xFFFFFFFF
        return f"{'bl' if word & 0x01000000 else 'b'}{suffix} 0x{target:x}"
    if (word >> 26) & 0x3 == 0b01:
        load = bool(word & (1 << 20))
        byte = bool(word & (1 << 22))
        up = bool(word & (1 << 23))
        rn, rd = (word >> 16) & 0xF, (word >> 12) & 0xF
        off = word & 0xFFF
        return f"{'ldr' if load else 'str'}{'b' if byte else ''}{suffix} r{rd}, [r{rn}, #{'+' if up else '-'}0x{off:x}]"
    if ((word >> 25) & 0x7) == 0b001:
        op = (word >> 21) & 0xF
        names = {0x2: "sub", 0x4: "add", 0xA: "cmp", 0xC: "orr", 0xD: "mov"}
        rn, rd = (word >> 16) & 0xF, (word >> 12) & 0xF
        val = imm12(word)
        name = names.get(op, f"op{op:x}")
        if name == "mov":
            return f"mov{suffix} r{rd}, #0x{val:x}"
        if name == "cmp":
            return f"cmp{suffix} r{rn}, #0x{val:x}"
        return f"{name}{suffix} r{rd}, r{rn}, #0x{val:x}"
    return f".word 0x{word:08x}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--value", type=lambda x: int(x, 0), action="append", required=True)
    parser.add_argument("--context", type=int, default=8, help="words before and after")
    parser.add_argument("--start", type=lambda x: int(x, 0), default=0)
    parser.add_argument("--end", type=lambda x: int(x, 0))
    args = parser.parse_args()
    data = args.binary.read_bytes()
    hits: list[int] = []
    wanted = set(args.value)
    end = min(len(data), args.end if args.end is not None else len(data))
    for off in range(args.start, end - 3, 4):
        word = struct.unpack_from("<I", data, off)[0]
        values = {word}
        if ((word >> 25) & 0x7) == 0b001:
            values.add(imm12(word))
        if ((word >> 26) & 0x3) == 0b01:
            values.add(word & 0xFFF)
        if values & wanted:
            hits.append(off)
    print(f"hits={len(hits)}")
    for hit in hits:
        print(f"\n== 0x{hit:x} ==")
        lo = max(0, hit - args.context * 4)
        hi = min(len(data), hit + (args.context + 1) * 4)
        for off in range(lo, hi, 4):
            word = struct.unpack_from("<I", data, off)[0]
            mark = ">" if off == hit else " "
            print(f"{mark} {off:08x}: {word:08x}  {describe(word, off)}")


if __name__ == "__main__":
    main()
