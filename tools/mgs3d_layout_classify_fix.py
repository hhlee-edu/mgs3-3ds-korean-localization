#!/usr/bin/env python3
"""V2 -> V2.1: fix korean_layout_classify's missing 0x84xx-0x87xx range check.

Root cause (found 2026-08-15, static analysis cross-checked live via GDB):
tools/mgs3d_clean_glyph_v2.py's trampoline assembles six functions from
experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s. Four of them
(korean_draw_1/2, korean_width_1/2) correctly check the global-page range
0x84xx-0x87xx before falling back to the legacy 0xA0xx-0xA3xx check.
korean_layout_classify (call site 0x00183A04) never got that same check --
it only recognises 0xA0xx-0xA3xx and falls straight to `bic r0,r1,#0x6000`
for every global-page Hangul token, which is why those characters render as
blank glyphs on hardware despite the glyph page itself being complete and
correct (draw/width already handle them fine).

This script re-assembles the *fixed* .s source (same toolchain as
mgs3d_clean_glyph_v2.py), then -- unlike that script, which starts from a
zero-filled cave -- verifies the input code.bin is exactly the known V2
output, replaces only the trampoline blob (draw_1/2, width_1/2, pre_draw must
decode to the identical instructions -- the two `ldr rX,[pc,#N]` literal-pool
loads inside draw_1/draw_2 are the only expected exception, since growing
korean_layout_classify pushes the shared literal pool 32 bytes further away
and the linker correctly re-encodes their offset; both old and new must still
resolve to the same two literal values), extends the exheader text-size to
cover the now-larger trampoline, and
recompresses. None of the 6 branch-instruction patch sites need touching:
korean_layout_classify is the last function before the literal pool, so its
start address (0x0087FA80) does not move -- only its body grows into the
already-reserved zero padding after the trampoline.

Usage:
    python tools/mgs3d_layout_classify_fix.py <in code.bin> <in exheader.bin> \
        <out dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nintendo_blz import decompress  # noqa: E402

ASM_SOURCE = ROOT / "experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s"
THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"
AS = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-as.exe")
LD = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-ld.exe")
OBJCOPY = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-objcopy.exe")
NM = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-nm.exe")

TEXT_BASE = 0x00100000
TEXT_CAVE_VA = 0x0087F8C4
EXPECTED_V2_CODE_SHA256 = "8c542191bdc62dffbd851d730dac14bc4dcf14208e54b4d15dbd409c885da7d0"
EXPECTED_V2_DECOMPRESSED_SHA256 = "105c8a1575dd3c0a65dc89ac6e81aa7e3eb9710f1c9449a00894cfb32cbc5ffa"
OLD_TRAMPOLINE_SIZE = 504
UNCHANGED_SYMBOLS = ("korean_draw_1", "korean_draw_2", "korean_width_1",
                     "korean_width_2", "korean_pre_draw")
CHANGED_SYMBOL = "korean_layout_classify"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def literal_pool_value(insns: list, index: int, blob: bytes, base: int) -> int | None:
    """For `ldr rX, [pc, #N]`, resolve the loaded 32-bit literal value."""
    insn = insns[index]
    if insn.mnemonic != "ldr" or "[pc" not in insn.op_str:
        return None
    target = insn.address + 8 + int(insn.op_str.rsplit("#", 1)[1].rstrip("]"), 0)
    offset = target - base
    return struct.unpack_from("<I", blob, offset)[0]


def verify_unchanged_prefix(old_blob: bytes, new_blob: bytes, length: int, base: int) -> None:
    """draw_1/draw_2/width_1/width_2/pre_draw must decode identically, except
    the two literal-pool `ldr` loads inside draw_1/draw_2 -- those legitimately
    re-encode when the shared literal pool moves, but must still resolve to
    the same underlying constant."""
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    old_insns = list(md.disasm(old_blob[:length], base))
    new_insns = list(md.disasm(new_blob[:length], base))
    if len(old_insns) != len(new_insns):
        raise SystemExit(
            f"unchanged-prefix instruction count differs: {len(old_insns)} vs {len(new_insns)}"
        )
    for i, (o, n) in enumerate(zip(old_insns, new_insns)):
        if o.mnemonic == n.mnemonic == "ldr" and "[pc" in o.op_str and "[pc" in n.op_str:
            old_value = literal_pool_value(old_insns, i, old_blob, base)
            new_value = literal_pool_value(new_insns, i, new_blob, base)
            if old_value != new_value:
                raise SystemExit(
                    f"0x{o.address:08X}: literal-pool load resolves to a different "
                    f"value (0x{old_value:08X} -> 0x{new_value:08X}), not just a "
                    "relocation shift -- aborting"
                )
            continue
        if o.mnemonic != n.mnemonic or o.op_str != n.op_str:
            raise SystemExit(
                f"0x{o.address:08X}: unchanged-prefix instruction differs: "
                f"'{o.mnemonic} {o.op_str}' -> '{n.mnemonic} {n.op_str}' -- not a minimal patch, aborting"
            )


def assemble(work: Path) -> tuple[bytes, dict[str, int]]:
    obj, elf, raw = work / "fix.o", work / "fix.elf", work / "fix.bin"
    subprocess.run([AS, "-march=armv6k", "-o", obj, ASM_SOURCE], check=True)
    subprocess.run([LD, f"-Ttext=0x{TEXT_CAVE_VA:08X}", "-o", elf, obj], check=True)
    subprocess.run([OBJCOPY, "-O", "binary", "-j", ".text", elf, raw], check=True)
    nm_text = subprocess.run([NM, "-n", elf], check=True, capture_output=True, text=True).stdout
    wanted = set(UNCHANGED_SYMBOLS) | {CHANGED_SYMBOL}
    symbols = {fields[2]: int(fields[0], 16) for fields in (line.split() for line in nm_text.splitlines())
               if len(fields) == 3 and fields[2] in wanted}
    if set(symbols) != wanted:
        raise ValueError(f"assembled trampoline is missing symbols: {wanted - set(symbols)}")
    return raw.read_bytes(), symbols


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("code_bin", type=Path)
    ap.add_argument("exheader_bin", type=Path)
    ap.add_argument("out_dir", type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    work = args.out_dir / "_work"
    work.mkdir(exist_ok=True)

    source_code = args.code_bin.read_bytes()
    if sha(source_code) != EXPECTED_V2_CODE_SHA256:
        raise SystemExit(
            f"input code.bin is not the known V2 build (sha256={sha(source_code)}); "
            "refusing to patch an unverified base"
        )
    image = bytearray(decompress(source_code))
    if sha(bytes(image)) != EXPECTED_V2_DECOMPRESSED_SHA256:
        raise SystemExit("decompressed V2 image hash mismatch")

    trampoline, symbols = assemble(work)
    if symbols[CHANGED_SYMBOL] != TEXT_CAVE_VA + (0x0087FA80 - TEXT_CAVE_VA):
        raise SystemExit(
            f"korean_layout_classify start address moved to 0x{symbols[CHANGED_SYMBOL]:08X}; "
            "expected 0x0087FA80 unchanged -- a preceding function's size changed, "
            "the 6 existing branch patch sites would need re-verifying"
        )

    cave = TEXT_CAVE_VA - TEXT_BASE
    old_trampoline = bytes(image[cave:cave + OLD_TRAMPOLINE_SIZE])
    layout_offset_in_blob = symbols[CHANGED_SYMBOL] - TEXT_CAVE_VA
    verify_unchanged_prefix(old_trampoline, trampoline, layout_offset_in_blob, TEXT_CAVE_VA)

    new_trampoline_size = len(trampoline)
    if new_trampoline_size < OLD_TRAMPOLINE_SIZE:
        raise SystemExit("new trampoline is smaller than the old one -- unexpected, aborting")
    extension = image[cave + OLD_TRAMPOLINE_SIZE:cave + new_trampoline_size]
    if any(extension):
        raise SystemExit(
            "the space the larger trampoline would grow into is not zero-filled "
            "-- something else already occupies it, aborting"
        )
    patched = bytearray(image)
    patched[cave:cave + new_trampoline_size] = trampoline

    exheader = bytearray(args.exheader_bin.read_bytes())
    old_text_size = struct.unpack_from("<I", exheader, 0x18)[0]
    new_text_size = cave + new_trampoline_size
    struct.pack_into("<I", exheader, 0x18, new_text_size)

    decompressed_out = args.out_dir / "code.decompressed.bin"
    compressed_out = args.out_dir / "code.bin"
    exheader_out = args.out_dir / "exheader.bin"
    decompressed_out.write_bytes(patched)
    exheader_out.write_bytes(exheader)
    compressed_out.unlink(missing_ok=True)
    subprocess.run([THREEDSTOOL, "-z", "--compress-type", "blz", "--compress-align", "16",
                    "-f", decompressed_out, "--compress-out", compressed_out], check=True)
    if decompress(compressed_out.read_bytes()) != bytes(patched):
        raise SystemExit("compressed code round-trip mismatch")

    # Byte-level diff between old and new *decompressed* images, for the manifest.
    old_image = bytes(image)
    new_image = bytes(patched)
    changed_ranges = []
    i = 0
    while i < len(new_image):
        if i >= len(old_image) or old_image[i] != new_image[i]:
            start = i
            while i < len(new_image) and (i >= len(old_image) or old_image[i] != new_image[i]):
                i += 1
            changed_ranges.append((start, i))
        else:
            i += 1

    manifest = {
        "format": "mgs3d-layout-classify-fix-v1",
        "status": "PASS",
        "input_code_sha256": sha(source_code),
        "output_code_sha256": sha(compressed_out.read_bytes()),
        "input_decompressed_sha256": EXPECTED_V2_DECOMPRESSED_SHA256,
        "output_decompressed_sha256": sha(new_image),
        "old_trampoline_size": OLD_TRAMPOLINE_SIZE,
        "new_trampoline_size": new_trampoline_size,
        "korean_layout_classify_va": f"0x{symbols[CHANGED_SYMBOL]:08X}",
        "old_text_size": old_text_size,
        "new_text_size": new_text_size,
        "changed_byte_ranges_va": [
            [f"0x{TEXT_BASE + a:08X}", f"0x{TEXT_BASE + b:08X}"] for a, b in changed_ranges
        ],
        "branch_patch_sites_touched": [],
        "note": "Only korean_layout_classify's own body (0x0087FA80 onward) and "
                "the trampoline's trailing literal pool changed; the 6 branch "
                "instructions at the original call sites are untouched because "
                "korean_layout_classify's start address did not move.",
    }
    (args.out_dir / "layout-classify-fix-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
