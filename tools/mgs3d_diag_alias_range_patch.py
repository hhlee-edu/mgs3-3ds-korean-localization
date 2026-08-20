#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Narrow the glyph hooks' alias range from 0xA0..0xA3 to 0xA4..0xA7 (#1 diagnostic).

`exefs/code.bin` carries six hooks that replace `bic rX, rY, #0x6000` with a
branch into an 815-byte cave at VA 0x0087F8C4. That `bic` is the game's alias
fold: token pages 0xA0/0xC0/0xE0 are alias copies of base page 0x80, and
clearing bits 13-14 folds them back. Each hook tests two lead-byte ranges and
otherwise re-runs the original `bic`.

    0x84..0x87   our Korean page. mgs3d_korean_global_page_build.py declares the
                 namespace as 0x8401..0x87FF. Correct, and untouched here.
    0xA0..0xA3   WRONG. The alias of 0x84..0x87 is 0xA4..0xA7 (t|0x2000).
                 0xA0..0xA3 is the alias of 0x80..0x83 -- the game's own page,
                 where A0 7B = '{', C0 7D = '}', 80 23 = '#', i.e. the
                 '#{ ... }#' inline markup used for button glyphs. Clean
                 codec.dat holds 33,798 of them across 179 of 2,326 GCX records.

This script rewrites only the twelve `cmp` immediates that spell that second
range -- six pairs, one byte each, all inside the cave. Nothing else in the
image is touched, and no RomFS file is touched.

    apply   staging code.bin -> alias range 0xA4..0xA7 (diagnostic)
    revert  staging code.bin -> production backup
    status  report which build is staged

Recompression uses the same 3dstool BLZ path as mgs3d_cpp_default_patch.py and
is round-trip verified before anything is written.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nintendo_blz import decompress  # noqa: E402

STAGING = pathlib.Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0")
STAGED_CODE = STAGING / "exefs/code.bin"
BUILD = ROOT / "builds/diag-2026-08-20-alias-range"
PROD = BUILD / "production-backup/exefs/code.bin"
DIAG = BUILD / "exefs/code.bin"
THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"

VA_BASE = 0x00100000
CAVE_VA = (0x0087F8C4, 0x0087FBF4)          # [start, end)
OLD_LO, OLD_HI = 0xA0, 0xA3
NEW_LO, NEW_HI = 0xA4, 0xA7
KEEP_LO, KEEP_HI = 0x84, 0x87               # Korean range: must not change


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def cmp_imm(word: int) -> int | None:
    """Return imm8 if `word` is `cmp Rn, #imm8` with rotate 0, else None."""
    if (word & 0x0FF0_0F00) != 0x0350_0000:   # cond xx | CMP,S=1 | Rd=0,rot=0
        return None
    return word & 0xFF


def find_sites(image: bytes) -> list[tuple[int, int]]:
    """(file_offset, imm8) for every `cmp Rn,#0xA0/#0xA3` inside the cave."""
    lo, hi = CAVE_VA[0] - VA_BASE, CAVE_VA[1] - VA_BASE
    out = []
    for off in range(lo, hi, 4):
        imm = cmp_imm(struct.unpack_from("<I", image, off)[0])
        if imm in (OLD_LO, OLD_HI):
            out.append((off, imm))
    return out


def patch(image: bytes) -> tuple[bytes, list[tuple[int, int, int]]]:
    sites = find_sites(image)
    if len(sites) != 12:
        raise SystemExit(f"expected 12 alias-range cmp sites, found {len(sites)}")
    pairs = list(zip(sites[0::2], sites[1::2]))
    for (o1, i1), (o2, i2) in pairs:
        if (i1, i2) != (OLD_LO, OLD_HI):
            raise SystemExit(f"unexpected pair at 0x{o1:07X}: {i1:#04x}/{i2:#04x}")
    buf = bytearray(image)
    changes = []
    for off, imm in sites:
        new = NEW_LO if imm == OLD_LO else NEW_HI
        buf[off] = new                      # imm8 is byte 0 of the LE word
        changes.append((off, imm, new))
    return bytes(buf), changes


def compress(image: bytes, workdir: pathlib.Path) -> bytes:
    workdir.mkdir(parents=True, exist_ok=True)
    raw, packed = workdir / "code.raw.bin", workdir / "code.blz.bin"
    raw.write_bytes(image)
    packed.unlink(missing_ok=True)
    subprocess.run([str(THREEDSTOOL), "-z", "--compress-type", "blz",
                    "--compress-align", "16", "-f", str(raw),
                    "--compress-out", str(packed)], check=True,
                   stdout=subprocess.DEVNULL)
    data = packed.read_bytes()
    if decompress(data) != image:
        raise SystemExit("BLZ round-trip failed: decompress(output) != patched image")
    return data


def build() -> None:
    source = PROD.read_bytes()
    print(f"source (production backup) : {len(source):>9,} B  sha {sha(source)}")
    image = decompress(source)
    print(f"  decompressed             : {len(image):>9,} B  sha {sha(image)}")
    patched, changes = patch(image)
    print(f"\npatched {len(changes)} cmp immediates ({len(changes)} bytes):")
    for off, old, new in changes:
        print(f"   file 0x{off:07X}  VA 0x{VA_BASE+off:08X}  #{old:#04x} -> #{new:#04x}")
    delta = [i for i in range(len(image)) if image[i] != patched[i]]
    print(f"\ndecompressed image diff: {len(delta)} bytes"
          f" -- {'OK' if len(delta) == 12 else '*** UNEXPECTED ***'}")
    if len(delta) != 12:
        raise SystemExit(1)
    print(f"  patched image sha        : {sha(patched)}")
    out = compress(patched, BUILD / "work")
    DIAG.parent.mkdir(parents=True, exist_ok=True)
    DIAG.write_bytes(out)
    print(f"\nrecompressed             : {len(out):>9,} B  sha {sha(out)}")
    print(f"  round-trip               : OK")
    print(f"  written                  : {DIAG}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "apply", "revert", "status"))
    args = ap.parse_args()

    if args.action == "build":
        build()
        return 0

    cur = STAGED_CODE.read_bytes()
    prod = PROD.read_bytes() if PROD.exists() else None
    diag = DIAG.read_bytes() if DIAG.exists() else None
    if args.action == "status":
        which = ("diagnostic (alias 0xA4..0xA7)" if diag and cur == diag
                 else "production (alias 0xA0..0xA3)" if prod and cur == prod
                 else "unrecognised")
        print(f"exefs/code.bin  {len(cur):>9,} B  {sha(cur)[:16]}  {which}")
        return 0

    src = diag if args.action == "apply" else prod
    if src is None:
        raise SystemExit(f"missing source for '{args.action}' -- run 'build' first")
    if cur == src:
        print(f"already {args.action} ({sha(cur)[:16]})")
        return 0
    STAGED_CODE.write_bytes(src)
    got = STAGED_CODE.read_bytes()
    ok = got == src
    print(f"{args.action}: {sha(cur)[:16]} -> {sha(got)[:16]}  {'OK' if ok else 'MISMATCH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
