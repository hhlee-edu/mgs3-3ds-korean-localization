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

The 확장 슬라이드 패드 / C-stick option can only be *changed* on real hardware:
Citra and Azahar both lack the Extrapad library applet (0x208/0x408) and hang
when the game asks for it. See docs/citra-extrapad-applet-freeze-2026-08-17.md.
`enable-cpp` / `disable-cpp` therefore flip it in the save file instead, so a
player keeps their own progress rather than importing someone else's save.

Two profiles decide which bytes get written:

  builtin   the three things the game's own enable path writes (see the block
            comment below): the 0x3C..0xF7 control table, the gate bit at
            0x0C bit0, and the scheme index at 0x13C. Writing the table alone is
            NOT enough — the engine undoes it while the gate bit is clear.

  learned   every byte that actually changed in a CPP-off/CPP-on pair captured
            from ONE console, which removes the playthrough noise the builtin
            profile has to ignore:
                mgs3d_save_tool.py learn-cpp before.sav after.sav -o cpp.json
                mgs3d_save_tool.py enable-cpp savedata --profile cpp.json

Usage:
    mgs3d_save_tool.py show <save>
    mgs3d_save_tool.py diff <save_a> <save_b>
    mgs3d_save_tool.py fix-crc <save>          # rewrite the header CRC in place
    mgs3d_save_tool.py enable-cpp <save> [--profile p.json] [--dry-run]
    mgs3d_save_tool.py disable-cpp <save> [--profile p.json] [--dry-run]
    mgs3d_save_tool.py learn-cpp <cpp_off> <cpp_on> -o p.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
import zlib

SAVE_SIZE = 20768
CTRL_LO, CTRL_HI = 0x40, 0xC0
CPP_LO, CPP_HI = 0xC0, 0xF8

# The save is `u32 CRC || config object`, so config+X lives at save+X+4. Confirmed
# against the game's own code (decompressed .code, 2026-08-19):
#
#   0x0088F470  four 0x100-byte control presets. preset[0] is byte-identical to a
#               CPP-off save's 0x3C..0xF7 and preset[3] to a CPP-on save's, which
#               is where BUILTIN_OFF/BUILTIN_ON below come from.
#   0x0012BD8C  apply_scheme(i): copies 47 words of preset[i] to config+0x38
#               (= save 0x3C) and stores i at config+0x138 (= save 0x13C).
#   0x0010AEC0  the enforcer: if bit0 of config+8 (= save 0x0C) is set it forces
#               scheme 3, otherwise it forces scheme 0. So writing the table
#               WITHOUT that bit gets undone at runtime — enabling CPP means all
#               three of: table, flag bit, scheme index.
BUILTIN_LO = 0x3C
FLAG_OFF, FLAG_BIT = 0x0C, 0x00000001     # config+8 bit0 = "CPP enabled"
SCHEME_OFF = 0x13C                        # config+0x138 = active preset index
SCHEME_ON, SCHEME_OFF_VALUE = 3, 0
BUILTIN_OFF = bytes.fromhex(
    "80000000000100000001000040000000"
    "20000000100000000002000000020000"
    "00400000008000000000002000000010"
    "00000000000000000000000040000000"
    "00040000020000000008000001000000"
    "00040000020000000008000001000000"
    "40000000400000004000000000000000"
    "00020000200000001000000000020000"
    "00010000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000000000"
)
BUILTIN_ON = bytes.fromhex(
    "02000000008000000080000000040000"
    "20000000100000000040000000400000"
    "00020000000100000000002000000010"
    "00000000000000000000000040000000"
    "00000000000000000000000000000000"
    "00040000020000000008000001000000"
    "40000000000400000004000000080000"
    "00400000200000001000000000020000"
    "00010000004000000080000080000000"
    "40000000010000000002000000010000"
    "00010000000200000002000000010000"
    "00020000000100004000000000000000"
)

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


def cpp_state(data: bytes) -> tuple[bool, bool, int]:
    """(gate flag, CPP table populated, scheme index) — the three things the game
    itself uses. A genuine CPP-on save has (True, True, 3)."""
    return (bool(struct.unpack_from("<I", data, FLAG_OFF)[0] & FLAG_BIT),
            any(data[CPP_LO:CPP_HI]),
            struct.unpack_from("<I", data, SCHEME_OFF)[0])


def cpp_enabled(data: bytes) -> bool:
    """True only when all three agree. The gate flag is what the game branches on
    (0x0010AEC0): with it clear, the engine re-applies preset 0 and undoes a
    table-only edit."""
    flag, table, scheme = cpp_state(data)
    return flag and table and scheme == SCHEME_ON


def describe_cpp(data: bytes) -> str:
    flag, table, scheme = cpp_state(data)
    if flag and table and scheme == SCHEME_ON:
        return "ENABLED"
    if not flag and not table and scheme == SCHEME_OFF_VALUE:
        return "disabled"
    return (f"INCONSISTENT (gate flag {'set' if flag else 'clear'}, "
            f"table {'populated' if table else 'zero'}, scheme index {scheme})")


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
    flag, table, scheme = cpp_state(data)
    print(f"Circle Pad Pro / C-stick : {describe_cpp(data)}")
    print(f"  gate flag 0x0C bit0    : {int(flag)}      (config+8, what the engine branches on)")
    print(f"  CPP table 0xC0..0xF7   : {'populated' if table else 'zero'}")
    print(f"  scheme index 0x13C     : {scheme}      (3 = dual-stick preset)")
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


# Four remaining bytes that are constant within each group of reference saves and
# differ between the groups, with no counterpart found in the code yet. They are
# zero in every CPP-off save, and 0x162/0x168 (45 / 64) look like camera
# sensitivities the game may write when CPP is switched on. Unproven — opt in with
# --with-option-block, or settle it for good with learn-cpp.
OPTION_BLOCK = {0x140: (0x00, 0x04), 0x15C: (0x00, 0x02),
                0x162: (0x00, 0x2D), 0x168: (0x00, 0x40)}

# Offsets whose other bits belong to unrelated options, so they are edited as a
# bit mask rather than copied wholesale — even from a learned profile. (Extreme's
# flags word is 0x00908801 where Normal's is 0x00908003: same CPP bit, different
# neighbours.)
BIT_SEMANTICS = {FLAG_OFF: FLAG_BIT}


def builtin_profile(with_option_block: bool = False) -> dict:
    """The structural profile as {offset: (off_byte, on_byte)} for changed bytes."""
    prof = {BUILTIN_LO + i: (o, n)
            for i, (o, n) in enumerate(zip(BUILTIN_OFF, BUILTIN_ON)) if o != n}
    prof[FLAG_OFF] = (0x00, FLAG_BIT)                  # config+8 bit0, masked (see BIT_SEMANTICS)
    prof[SCHEME_OFF] = (SCHEME_OFF_VALUE, SCHEME_ON)   # config+0x138, u32 but < 256
    if with_option_block:
        prof.update(OPTION_BLOCK)
    return prof


def load_profile(path: pathlib.Path | None, with_option_block: bool = False) -> tuple[dict, str]:
    if path is None:
        extra = " + option block" if with_option_block else ""
        return (builtin_profile(with_option_block),
                f"builtin: table 0x3C..0xF7 + gate bit 0x0C.0 + scheme index 0x13C{extra}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    prof = {int(e["offset"]): (int(e["off"], 16), int(e["on"], 16)) for e in doc["deltas"]}
    prof.setdefault(FLAG_OFF, (0x00, FLAG_BIT))          # always carry the gate bit
    prof.setdefault(SCHEME_OFF, (SCHEME_OFF_VALUE, SCHEME_ON))
    return prof, f"learned from {path.name} ({doc.get('captured_on', 'unknown console')})"


def apply_profile(data: bytes, prof: dict, enable: bool) -> bytes:
    out = bytearray(data)
    for offset, (off_b, on_b) in prof.items():
        mask = BIT_SEMANTICS.get(offset)
        if mask is None:
            out[offset] = on_b if enable else off_b
        elif enable:
            out[offset] |= mask
        else:
            out[offset] &= ~mask & 0xFF
    struct.pack_into("<I", out, 0, expected_crc(bytes(out)))
    return bytes(out)


def cmd_set_cpp(args, enable: bool) -> int:
    data = load(args.save)
    if len(data) != SAVE_SIZE:
        print("refusing: not a 20,768-byte MGS3D save", file=sys.stderr)
        return 2
    if stored_crc(data) != expected_crc(data) and not args.force:
        print("refusing: input CRC is already wrong — run fix-crc first, or pass --force",
              file=sys.stderr)
        return 2
    want = "ENABLED" if enable else "disabled"
    if describe_cpp(data) == want:
        print(f"nothing to do: Circle Pad Pro is already {want} in {args.save.name}")
        return 0
    if describe_cpp(data).startswith("INCONSISTENT"):
        print(f"input state : {describe_cpp(data)}\n"
              f"              (a table-only edit looks like this; patching it to {want})")

    prof, origin = load_profile(args.profile, args.with_option_block)
    patched = apply_profile(data, prof, enable)

    # report + self-check
    touched = sorted(o for o in prof if data[o] != patched[o])
    other = [i for i in range(SAVE_SIZE) if data[i] != patched[i] and i not in prof and i >= 4]
    print(f"profile     : {origin}, {len(prof)} bytes")
    print(f"bytes changed: {len(touched)} (+ the 4-byte header CRC)")
    print(f"outside the profile: {len(other)} bytes changed  "
          f"{'OK — progress untouched' if not other else '<-- BUG, aborting'}")
    if other:
        return 3
    print(f"Circle Pad Pro / C-stick : {describe_cpp(patched)} (wanted {want})")
    print(f"crc32 (LE)  : 0x{stored_crc(data):08X} -> 0x{stored_crc(patched):08X}")
    if describe_cpp(patched) != want:
        print("refusing to write: the profile did not produce the requested state", file=sys.stderr)
        return 3

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    out = args.output or args.save
    if out == args.save and not args.no_backup:
        backup = args.save.with_name(args.save.name + ".bak-cpp")
        if not backup.exists():
            backup.write_bytes(data)
            print(f"backup      : {backup}")
        else:
            print(f"backup      : {backup} already exists, kept")
    out.write_bytes(patched)
    print(f"written     : {out}")
    return 0


def cmd_learn_cpp(args) -> int:
    a, b = load(args.cpp_off), load(args.cpp_on)
    for tag, d, want in (("cpp_off", a, False), ("cpp_on", b, True)):
        if stored_crc(d) != expected_crc(d):
            print(f"warning: {tag} CRC mismatch", file=sys.stderr)
        if cpp_enabled(d) != want:
            print(f"warning: {tag} reports CPP={'on' if cpp_enabled(d) else 'off'}, "
                  f"expected {'on' if want else 'off'} — are the two arguments swapped?",
                  file=sys.stderr)
    deltas = [{"offset": i, "off": f"{a[i]:02X}", "on": f"{b[i]:02X}"}
              for i in range(4, min(len(a), len(b))) if a[i] != b[i]]
    doc = {
        "format": "mgs3d-cpp-profile/1",
        "title": "0004000000081E00",
        "captured_on": args.captured_on,
        "source_off": str(args.cpp_off),
        "source_on": str(args.cpp_on),
        "note": "byte deltas between one console's CPP-off and CPP-on save; "
                "header CRC at 0x00..0x03 excluded, it is recomputed on write",
        "deltas": deltas,
    }
    args.output.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    inside = [d for d in deltas if BUILTIN_LO <= d["offset"] < BUILTIN_LO + len(BUILTIN_OFF)]
    builtin = builtin_profile()
    agree = [d for d in inside
             if builtin.get(d["offset"]) == (int(d["off"], 16), int(d["on"], 16))]
    print(f"{len(deltas)} differing bytes -> {args.output}")
    print(f"  inside the builtin window 0x3C..0xF7 : {len(inside)}  "
          f"(agreeing with the builtin profile: {len(agree)}/{len(builtin)})")
    print(f"  outside it                           : {len(deltas) - len(inside)}"
          f"{'  <-- the builtin profile would have missed these' if len(deltas) > len(inside) else ''}")
    for d in deltas:
        if not (BUILTIN_LO <= d["offset"] < BUILTIN_LO + len(BUILTIN_OFF)):
            tag = "  (option-block candidate)" if d["offset"] in OPTION_BLOCK else ""
            print(f"    0x{d['offset']:05X}  {d['off']} -> {d['on']}{tag}")
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
    for stream in (sys.stdout, sys.stderr):
        try:  # Korean Windows consoles default to cp949 and choke on the docstring
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
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
    for name, enable, helptext in (
            ("enable-cpp", True, "turn the Circle Pad Pro / C-stick scheme on in the save"),
            ("disable-cpp", False, "turn it back off (the in-game toggle hangs in Citra)")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("save", type=pathlib.Path)
        s.add_argument("--profile", type=pathlib.Path,
                       help="cpp-profile JSON from learn-cpp; default is the builtin one")
        s.add_argument("-o", "--output", type=pathlib.Path,
                       help="write here instead of patching the save in place")
        s.add_argument("--with-option-block", action="store_true",
                       help="also write the 5 unproven option bytes at 0x13C..0x168 "
                            "(ignored when --profile is given)")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--no-backup", action="store_true")
        s.add_argument("--force", action="store_true", help="patch even if the input CRC is wrong")
        s.set_defaults(func=lambda a, _e=enable: cmd_set_cpp(a, _e))
    s = sub.add_parser("learn-cpp",
                       help="derive an exact profile from one console's CPP-off/CPP-on save pair")
    s.add_argument("cpp_off", type=pathlib.Path)
    s.add_argument("cpp_on", type=pathlib.Path)
    s.add_argument("-o", "--output", type=pathlib.Path, required=True)
    s.add_argument("--captured-on", default="", help="console the pair came from, for the record")
    s.set_defaults(func=cmd_learn_cpp)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
