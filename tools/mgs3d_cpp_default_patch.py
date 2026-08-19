#!/usr/bin/env python3
"""Force the Circle Pad Pro / C-stick control scheme on, in code, with no save edit.

Why this exists: the in-game 확장 슬라이드 패드 toggle opens the Extrapad library
applet (0x408), which Citra and Azahar do not implement, so the game hangs there
(docs/citra-extrapad-applet-freeze-2026-08-17.md). Editing the player's save works
but is awkward on Android. This patches the enforcer instead.

The engine keeps CPP state in three places (all confirmed in the decompressed
.code, see docs/cstick-default-scheme-feasibility-2026-08-19.md):

    config+0x008 bit0   the gate flag        (= save 0x00C bit0)
    config+0x138        control preset index (= save 0x13C, 3 = dual-stick)
    config+0x038..      47 words copied from preset[index] (= save 0x03C..0x0F7)

and re-derives the last two from the first at 0x0010AEC0:

    ldr r1,[r0,#8] / ldr r0,[r0,#0x138] / tst r1,#1
    beq  0x0010AEF4        <- flag clear: force preset 0   (the six words we take)
    cmp r0,#3 / movne r0,#3 / blne apply_scheme            <- flag set: force preset 3

The patch rewrites that "force preset 0" arm into "set the gate flag, then fall
into the preset-3 arm", so the state ends up byte-identical to a save that had
CPP switched on for real — which is what RT37's 2021 saves prove works in Citra.

    0010AEF4  ldr r0, [r6]              ; r6 = &config_ptr, live from 0x0010AEC0
    0010AEF8  ldr r1, [r0, #8]
    0010AEFC  orr r1, r1, #1            ; set the gate flag in memory
    0010AF00  str r1, [r0, #8]
    0010AF04  ldr r0, [r0, #0x138]
    0010AF08  b   0x0010AEDC            ; rejoin the genuine "CPP on" arm

Same size, no code cave, exheader untouched. The only branch into the rewritten
range is the enforcer's own beq (checked), and no jump-table word points into it.

NOTE: preset 3 binds ZL/ZR and the right stick, which an original 3DS without a
Circle Pad Pro does not have. This belongs in a separate optional build, never in
the default patch. See docs/cstick-default-scheme-feasibility-2026-08-19.md §5.

Usage:
    mgs3d_cpp_default_patch.py --code <code.bin> --output <code.bin> [--verify-only]
    mgs3d_cpp_default_patch.py --code <code.bin> --stage <partition0 dir> [--backup <dir>]
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

THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"
TEXT_BASE = 0x00100000
PATCH_VA = 0x0010AEF4

ORIGINAL = [0xE3500000, 0x0A000004, 0xE3A00000, 0xEB0083A1, 0xE320F000, 0xE320F000]
PATCHED = [
    0xE5960000,  # ldr r0, [r6]
    0xE5901008,  # ldr r1, [r0, #8]
    0xE3811001,  # orr r1, r1, #1
    0xE5801008,  # str r1, [r0, #8]
    0xE5900138,  # ldr r0, [r0, #0x138]
    0xEAFFFFF3,  # b   0x0010AEDC
]
# Sanity anchors that must be intact in whatever image we are handed.
ANCHORS = {
    0x0010AED8: 0x0A000005,   # beq 0x0010AEF4 (the only way into the patched range)
    0x0010AEDC: 0xE3500003,   # cmp r0, #3
    0x0010AEE0: 0x13A00003,   # movne r0, #3
    0x0010AEE4: 0x1B0083A8,   # blne apply_scheme
    0x0012BD8C: 0xE3500004,   # apply_scheme entry: cmp r0, #4
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word(image: bytes, va: int) -> int:
    return struct.unpack_from("<I", image, va - TEXT_BASE)[0]


def patch_image(image: bytes) -> tuple[bytes, bool]:
    """Returns (patched image, changed). Idempotent: an already-patched image is
    detected and left alone rather than corrupted."""
    for va, expected in ANCHORS.items():
        actual = word(image, va)
        if actual != expected:
            raise RuntimeError(f"anchor mismatch at 0x{va:08X}: "
                               f"expected 0x{expected:08X}, found 0x{actual:08X}")
    current = [word(image, PATCH_VA + i * 4) for i in range(len(PATCHED))]
    if current == PATCHED:
        return image, False
    if current != ORIGINAL:
        raise RuntimeError("the six words at 0x0010AEF4 are neither the original nor "
                           "the patched sequence — refusing to guess:\n  " +
                           " ".join(f"{w:08X}" for w in current))
    out = bytearray(image)
    for i, w in enumerate(PATCHED):
        struct.pack_into("<I", out, PATCH_VA - TEXT_BASE + i * 4, w)
    return bytes(out), True


def compress(image: bytes, workdir: pathlib.Path) -> bytes:
    raw = workdir / "code.decompressed.bin"
    packed = workdir / "code.blz.bin"
    raw.write_bytes(image)
    packed.unlink(missing_ok=True)
    subprocess.run([str(THREEDSTOOL), "-z", "--compress-type", "blz",
                    "--compress-align", "16", "-f", str(raw),
                    "--compress-out", str(packed)], check=True)
    data = packed.read_bytes()
    if decompress(data) != image:
        raise RuntimeError("BLZ round-trip mismatch — refusing to emit this code.bin")
    return data


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--code", type=pathlib.Path, required=True,
                   help="BLZ-compressed code.bin to patch (usually the staged one)")
    p.add_argument("--output", type=pathlib.Path, help="write the patched code.bin here")
    p.add_argument("--stage", type=pathlib.Path,
                   help="partition0 directory to install exefs/code.bin into")
    p.add_argument("--backup", type=pathlib.Path,
                   help="directory to copy the pre-patch code.bin into before staging")
    p.add_argument("--verify-only", action="store_true",
                   help="report what the image contains and exit without writing")
    args = p.parse_args()

    source = args.code.read_bytes()
    image = decompress(source)
    print(f"input       : {args.code}")
    print(f"              {len(source)} B compressed, sha256 {sha(source)[:16]}")
    print(f"              {len(image)} B decompressed, sha256 {sha(image)[:16]}")
    current = [word(image, PATCH_VA + i * 4) for i in range(len(PATCHED))]
    state = ("already patched" if current == PATCHED
             else "unpatched" if current == ORIGINAL else "UNKNOWN")
    print(f"0x{PATCH_VA:08X}  : {state}  " + " ".join(f"{w:08X}" for w in current))

    patched, changed = patch_image(image)
    if args.verify_only:
        print("--verify-only: nothing written")
        return 0
    if not changed:
        print("nothing to do: this code.bin already forces the CPP scheme")
        return 0
    print(f"anchors     : {len(ANCHORS)}/{len(ANCHORS)} OK")
    print("patched     : " + " ".join(f"{w:08X}" for w in PATCHED))

    workdir = (args.output.parent if args.output else args.code.parent)
    packed = compress(patched, workdir)
    print(f"recompressed: {len(packed)} B (was {len(source)}), sha256 {sha(packed)[:16]}")
    print(f"round-trip  : OK (decompress(output) == patched image)")

    if args.output:
        args.output.write_bytes(packed)
        print(f"written     : {args.output}")
    if args.stage:
        target = args.stage / "exefs" / "code.bin"
        if args.backup:
            args.backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, args.backup / "code.bin")
            print(f"backup      : {args.backup / 'code.bin'}")
        target.write_bytes(packed)
        print(f"staged      : {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
