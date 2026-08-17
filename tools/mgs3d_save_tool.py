#!/usr/bin/env python3
"""Inspect / repair an MGS3D (title 0004000000081E00) SD save file.

Save layout established 2026-08-17 from two independent saves (Citra 2026-08-16,
Azahar 2026-08-13), both 20,768 bytes:

    0x0000  u32 little-endian  CRC32 of save[4:]   <- verified on both saves
    0x0008  ..              title/slot fields
    0x001C  char[]          room id, e.g. "r_sna01"
    0x002C  char[]          stage id, e.g. "v001a"
    0x0040..0x00BF          32 x u32 button-mask table (the control config block)
    ...                     progress, flags, positions

The button-mask table uses 3DS HID PAD bits, and already contains the New-3DS /
Circle Pad Pro inputs in the default configuration:

    0x0001 A     0x0002 B     0x0004 Select  0x0008 Start
    0x0010 Right 0x0020 Left  0x0040 Up      0x0080 Down
    0x0100 R     0x0200 L     0x0400 X       0x0800 Y
    0x4000 ZL    0x8000 ZR    0x10000000 / 0x20000000  extended stick bits

NOT YET KNOWN: which field is the 확장 슬라이드 패드 / C-stick *toggle*. The two
saves available have a byte-identical control block, because the option can only
be changed on real hardware — Citra and Azahar both lack the Extrapad library
applet (0x208/0x408) and hang when the game asks for it. See
docs/citra-extrapad-applet-freeze-2026-08-17.md.

To identify it, capture one save before and one after changing that option on
hardware and run:  mgs3d_save_tool.py diff before.sav after.sav

Usage:
    mgs3d_save_tool.py show <save>
    mgs3d_save_tool.py diff <save_a> <save_b>
    mgs3d_save_tool.py fix-crc <save>          # rewrite the header CRC in place
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys
import zlib

SAVE_SIZE = 20768
CTRL_LO, CTRL_HI = 0x40, 0xC0
CPP_LO, CPP_HI = 0xC0, 0xF8

PAD_BITS = [
    (0x00000001, "A"), (0x00000002, "B"), (0x00000004, "Select"), (0x00000008, "Start"),
    (0x00000010, "Right"), (0x00000020, "Left"), (0x00000040, "Up"), (0x00000080, "Down"),
    (0x00000100, "R"), (0x00000200, "L"), (0x00000400, "X"), (0x00000800, "Y"),
    (0x00004000, "ZL"), (0x00008000, "ZR"),
    (0x01000000, "CStickRight"), (0x02000000, "CStickLeft"),
    (0x04000000, "CStickUp"), (0x08000000, "CStickDown"),
    (0x10000000, "CircleRight"), (0x20000000, "CircleLeft"),
    (0x40000000, "CircleUp"), (0x80000000, "CircleDown"),
]


def decode_pad(value: int) -> str:
    if value == 0:
        return "-"
    names = [n for bit, n in PAD_BITS if value & bit]
    left = value & ~sum(bit for bit, _ in PAD_BITS if value & bit)
    if left:
        names.append(f"?0x{left:08X}")
    return "+".join(names) if names else f"?0x{value:08X}"


def expected_crc(data: bytes) -> int:
    return zlib.crc32(data[4:]) & 0xFFFFFFFF


def stored_crc(data: bytes) -> int:
    return struct.unpack_from("<I", data, 0)[0]


def cpp_enabled(data: bytes) -> bool:
    """True if the Circle Pad Pro / C-stick control set is active.

    The 0xC0..0xF7 table is all zero with CPP off and fully populated with it on
    (verified: user's own save vs the four RT37 CPP saves)."""
    return any(data[CPP_LO:CPP_HI])


def cstring(data: bytes, off: int, size: int) -> str:
    raw = data[off:off + size].split(b"\0", 1)[0]
    return raw.decode("latin1", "replace")


def load(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    if len(data) != SAVE_SIZE:
        print(f"warning: {path.name} is {len(data)} bytes, expected {SAVE_SIZE}", file=sys.stderr)
    return data


def cmd_show(args) -> int:
    data = load(args.save)
    good = stored_crc(data) == expected_crc(data)
    print(f"file        : {args.save}")
    print(f"size        : {len(data)}")
    print(f"crc32 (LE)  : stored 0x{stored_crc(data):08X}  computed 0x{expected_crc(data):08X}  "
          f"{'OK' if good else 'MISMATCH'}")
    print(f"room        : {cstring(data, 0x1C, 16)!r}")
    print(f"stage       : {cstring(data, 0x2C, 16)!r}")
    print(f"Circle Pad Pro / C-stick : {'ENABLED' if cpp_enabled(data) else 'disabled'}")
    print("\nprimary control block 0x40..0xBF (u32 button masks):")
    for off in range(CTRL_LO, CTRL_HI, 4):
        v = struct.unpack_from("<I", data, off)[0]
        print(f"  [{(off - CTRL_LO) // 4:2d}] 0x{off:03X} = 0x{v:08X}  {decode_pad(v)}")
    print("\nCPP control block 0xC0..0xF7 (all zero when CPP is off):")
    for off in range(CPP_LO, CPP_HI, 4):
        v = struct.unpack_from("<I", data, off)[0]
        print(f"  [{(off - CPP_LO) // 4:2d}] 0x{off:03X} = 0x{v:08X}  {decode_pad(v)}")
    return 0 if good else 2


def cmd_diff(args) -> int:
    a, b = load(args.save_a), load(args.save_b)
    print(f"A = {args.save_a}")
    print(f"B = {args.save_b}")
    for tag, d in (("A", a), ("B", b)):
        ok = stored_crc(d) == expected_crc(d)
        print(f"  {tag} crc {'OK' if ok else 'MISMATCH'}   stage={cstring(d, 0x2C, 16)!r}"
              f"   CPP={'on' if cpp_enabled(d) else 'off'}")
    runs, i, n = [], 0, min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    total = sum(j - i for i, j in runs)
    print(f"\n{len(runs)} differing runs, {total} bytes")
    for i, j in runs:
        where = "  <-- CONTROL BLOCK" if i < CTRL_HI and j > CTRL_LO else ""
        print(f"  0x{i:05X}..0x{j:05X} ({j - i:4d} B)  A={a[i:min(j, i + 12)].hex(' ')}"
              f"  B={b[i:min(j, i + 12)].hex(' ')}{where}")
    ctrl = [(off, struct.unpack_from("<I", a, off)[0], struct.unpack_from("<I", b, off)[0])
            for off in range(CTRL_LO, CTRL_HI, 4)]
    changed = [(o, x, y) for o, x, y in ctrl if x != y]
    print(f"\ncontrol-block fields changed: {len(changed)}")
    for off, x, y in changed:
        print(f"  [{(off - CTRL_LO) // 4:2d}] 0x{off:03X}: 0x{x:08X} ({decode_pad(x)})"
              f"  ->  0x{y:08X} ({decode_pad(y)})")
    if not changed:
        print("  (none — if these saves bracket an option change, the flag lives outside 0x40..0xBF;"
              " look at the runs listed above)")
    return 0


def cmd_fix_crc(args) -> int:
    data = bytearray(load(args.save))
    before, after = stored_crc(data), expected_crc(data)
    if before == after:
        print(f"crc already correct (0x{before:08X}); nothing written")
        return 0
    struct.pack_into("<I", data, 0, after)
    args.save.write_bytes(bytes(data))
    print(f"crc 0x{before:08X} -> 0x{after:08X}, written to {args.save}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show", help="print header, stage and the control block")
    s.add_argument("save", type=pathlib.Path)
    s.set_defaults(func=cmd_show)
    s = sub.add_parser("diff", help="compare two saves, highlighting control-block changes")
    s.add_argument("save_a", type=pathlib.Path)
    s.add_argument("save_b", type=pathlib.Path)
    s.set_defaults(func=cmd_diff)
    s = sub.add_parser("fix-crc", help="recompute and rewrite the header CRC in place")
    s.add_argument("save", type=pathlib.Path)
    s.set_defaults(func=cmd_fix_crc)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
