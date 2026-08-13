#!/usr/bin/env python3
"""Stage V2: preserve V1 pages and add only the verified renderer trampoline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nintendo_blz import decompress  # noqa: E402

EXP = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
CLEAN = EXP / "clean-tree"
DEST = Path(r"C:\Users\hhlee\Desktop\metagear3d\romforge\output\unpacked\partition0")
ASM_SOURCE = ROOT / "experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s"
THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"
AS = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-as.exe")
LD = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-ld.exe")
OBJCOPY = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-objcopy.exe")
NM = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-nm.exe")

EXPECTED_DECOMPRESSED_SHA256 = "10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7"
TEXT_BASE = 0x00100000
TEXT_CAVE_VA = 0x0087F8C4
K = 0x56000
TABLE_PAGE2_VA = 0x00A46FE0
PATCH_SITES = {
    "draw_1": (0x0015E600, "korean_draw_1", 0xE3C11A06),
    "draw_2": (0x0015EC58, "korean_draw_2", 0xE3C91A06),
    "width_1": (0x00184398, "korean_width_1", 0xE3C00A06),
    "width_2": (0x0018445C, "korean_width_2", 0xE3C11A06),
    "pre_draw": (0x0015E5A4, "korean_pre_draw", 0xE3C11A06),
    "layout_classify": (0x00183A04, "korean_layout_classify", 0xE3C10A06),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def branch_word(source: int, target: int) -> int:
    delta = target - (source + 8)
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise ValueError(f"branch out of range: 0x{source:X}->0x{target:X}")
    return 0xEA000000 | ((delta >> 2) & 0x00FFFFFF)


def file_map(root: Path) -> dict[str, tuple[int, str]]:
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        result[path.relative_to(root).as_posix()] = (len(data), sha(data))
    return result


def assemble() -> tuple[bytes, dict[str, int]]:
    obj, elf, raw = EXP / "V2-trampoline.o", EXP / "V2-trampoline.elf", EXP / "V2-trampoline.bin"
    subprocess.run([AS, "-march=armv6k", "-o", obj, ASM_SOURCE], check=True)
    subprocess.run([LD, f"-Ttext=0x{TEXT_CAVE_VA:08X}", "-o", elf, obj], check=True)
    subprocess.run([OBJCOPY, "-O", "binary", "-j", ".text", elf, raw], check=True)
    nm_text = subprocess.run([NM, "-n", elf], check=True, capture_output=True, text=True).stdout
    wanted = {symbol for _, symbol, _ in PATCH_SITES.values()}
    symbols = {fields[2]: int(fields[0], 16) for fields in (line.split() for line in nm_text.splitlines())
               if len(fields) == 3 and fields[2] in wanted}
    blob = raw.read_bytes()
    if set(symbols) != wanted:
        raise ValueError("assembled trampoline is missing symbols")
    if struct.pack("<I", TABLE_PAGE2_VA) not in blob or struct.pack("<I", K) not in blob:
        raise ValueError("assembled trampoline has stale address literals")
    return blob, symbols


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", type=Path, default=CLEAN)
    parser.add_argument("--dest", type=Path, default=DEST)
    args = parser.parse_args()
    before = file_map(args.dest)
    clean = file_map(args.clean)
    expected_v1 = sorted(f"romfs/stage/{path.parent.name}/scenerio.gcx"
                         for path in (args.clean / "romfs/stage").glob("*/scenerio.gcx"))
    existing_v1_changes = sorted(rel for rel in clean if before.get(rel) != clean[rel])
    if existing_v1_changes != expected_v1:
        raise RuntimeError("destination is not the verified V1 staging state")

    source_code = (args.clean / "exefs/code.bin").read_bytes()
    image = decompress(source_code)
    if sha(image) != EXPECTED_DECOMPRESSED_SHA256:
        raise RuntimeError("clean code decompressed hash mismatch")
    exheader = bytearray((args.clean / "exheader.bin").read_bytes())
    trampoline, symbols = assemble()
    patched = bytearray(image)
    modifications = []
    for name, (site, symbol, expected) in PATCH_SITES.items():
        offset = site - TEXT_BASE
        original = struct.unpack_from("<I", patched, offset)[0]
        if original != expected:
            raise RuntimeError(f"unexpected instruction at 0x{site:08X}")
        replacement = branch_word(site, symbols[symbol])
        struct.pack_into("<I", patched, offset, replacement)
        modifications.append({"name": name, "address": f"0x{site:08X}",
                              "original_word": f"0x{original:08X}",
                              "patched_word": f"0x{replacement:08X}"})
    cave = TEXT_CAVE_VA - TEXT_BASE
    if any(patched[cave:cave + len(trampoline)]):
        raise RuntimeError("text cave is not zero-filled")
    patched[cave:cave + len(trampoline)] = trampoline
    new_text_size = cave + len(trampoline)
    struct.pack_into("<I", exheader, 0x18, new_text_size)

    decompressed_out = EXP / "V2-code.decompressed.bin"
    compressed_out = EXP / "V2-code.bin"
    exheader_out = EXP / "V2-exheader.bin"
    decompressed_out.write_bytes(patched)
    exheader_out.write_bytes(exheader)
    compressed_out.unlink(missing_ok=True)
    subprocess.run([THREEDSTOOL, "-z", "--compress-type", "blz", "--compress-align", "16",
                    "-f", decompressed_out, "--compress-out", compressed_out], check=True)
    if decompress(compressed_out.read_bytes()) != bytes(patched):
        raise RuntimeError("compressed code round-trip mismatch")

    shutil.copy2(compressed_out, args.dest / "exefs/code.bin")
    shutil.copy2(exheader_out, args.dest / "exheader.bin")
    after = file_map(args.dest)
    v1_to_v2 = sorted(rel for rel in after if after.get(rel) != before.get(rel))
    expected_diff = ["exefs/code.bin", "exheader.bin"]
    unexpected = sorted(set(v1_to_v2) ^ set(expected_diff))
    v1_pages_preserved = all(after[rel] == before[rel] for rel in expected_v1)
    status = "PASS" if not unexpected and v1_pages_preserved else "INCONCLUSIVE"
    manifest = {
        "format": "mgs3d-clean-glyph-v2-trampoline",
        "status": status,
        "K": K,
        "anchor_va": f"0x{TABLE_PAGE2_VA:08X}",
        "formula": f"*(0x{TABLE_PAGE2_VA:08X}) + 0x{K:X}",
        "source_code_sha256": sha(source_code),
        "source_decompressed_sha256": sha(image),
        "output_code_sha256": sha(compressed_out.read_bytes()),
        "output_decompressed_sha256": sha(bytes(patched)),
        "source_exheader_sha256": clean["exheader.bin"][1],
        "output_exheader_sha256": sha(bytes(exheader)),
        "trampoline_sha256": sha(trampoline),
        "trampoline_size": len(trampoline),
        "trampoline_va": f"0x{TEXT_CAVE_VA:08X}",
        "old_text_size": struct.unpack_from("<I", (args.clean / "exheader.bin").read_bytes(), 0x18)[0],
        "new_text_size": new_text_size,
        "modified_offsets": modifications,
        "v1_to_v2_changed_files": v1_to_v2,
        "unexpected_diff": unexpected,
        "v1_stage_pages_preserved": v1_pages_preserved,
    }
    (EXP / "V2-build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EXP / "V1-to-V2-diff.txt").write_text(
        "\n".join(["V1-to-V2 changed-file diff", f"status={status}",
                    f"changed_count={len(v1_to_v2)}", *v1_to_v2, "", "[UNEXPECTED]", *unexpected]) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": status, "changed": v1_to_v2, "unexpected": unexpected,
                      "v1_pages_preserved": v1_pages_preserved, "trampoline_size": len(trampoline)}, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
