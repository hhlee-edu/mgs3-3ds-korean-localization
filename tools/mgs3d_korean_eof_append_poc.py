#!/usr/bin/env python3
"""Build the EOF-append Korean glyph POC.

Candidate 1 from docs/font-resource-identified-2026-08-12.md: append the
0xFF00 Korean page to one stage's scenerio.gcx and reach it at runtime via

    buffer_base      = *(uint32_t*)0x00A472AC - 4
    korean_page_base = buffer_base + <original file size>

The stage file is loaded whole and contiguous (live-verified), so bytes past
the original EOF are resident iff the loader sizes its allocation from the
RomFS file size.  That is exactly what this POC tests; nothing about it is
proven yet.

Originals are never written.  Everything lands under OUT / the isolated
staging tree.
"""

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
from mgs3d_movie_tool import parse_records  # noqa: E402
from nintendo_blz import decompress  # noqa: E402

OUT = ROOT / "experiments/korean_eof_append_poc_2026-08-12"
ASM_SOURCE = OUT / "poc_trampolines.s"

SOURCE_CODE = Path(r"C:\Users\hhlee\Desktop\Romforge\output\backup_before_a0xx_ganada_poc_20260812\exefs\code.bin")
SOURCE_EXHEADER = Path(r"C:\Users\hhlee\Desktop\Romforge\output\backup_before_a0xx_ganada_poc_20260812\exheader.bin")
SOURCE_MOVIE = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/movie_live_base.dat"
ROMFS = Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs")
KOREAN_PAGE = ROOT / "experiments/global_korean_page_build_2026-08-12/korean_page_stress_64.bin"
TOKEN_MAP = ROOT / "experiments/global_korean_page_build_2026-08-12/korean_token_map_stress_64.csv"

THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"
AS = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-as.exe")
LD = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-ld.exe")
OBJCOPY = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-objcopy.exe")
NM = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-nm.exe")

EXPECTED_DECOMPRESSED_SHA256 = "10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7"
EXPECTED_SEGMENTS = {
    "text": (0x00100000, 0x780, 0x77F8C4, 0),
    "rodata": (0x00880000, 0x3A, 0x39970, 0x780000),
    "data": (0x008BA000, 0x5C, 0x5BF20, 0x7BA000),
}
TEXT_CAVE_VA = 0x0087F8C4
FONT_DESCRIPTOR_VA = 0x00A472AC   # live-verified: [0] == buffer_base + 4
BANK = 0xFF00

PATCH_SITES = {
    "draw_1": (0x0015E600, "korean_draw_1"),
    "draw_2": (0x0015EC58, "korean_draw_2"),
    "width_1": (0x00184398, "korean_width_1"),
    "width_2": (0x0018445C, "korean_width_2"),
    "pre_draw": (0x0015E5A4, "korean_pre_draw"),
    "layout_classify": (0x00183A04, "korean_layout_classify"),
}
EXPECTED_SITE_WORDS = {
    "draw_1": 0xE3C11A06, "draw_2": 0xE3C91A06,
    "width_1": 0xE3C00A06, "width_2": 0xE3C11A06,
    "pre_draw": 0xE3C11A06, "layout_classify": 0xE3C10A06,
}


class PocError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def branch_word(source_va: int, target_va: int) -> int:
    delta = target_va - (source_va + 8)
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise PocError(f"branch out of range: {source_va:X}->{target_va:X}")
    return 0xEA000000 | ((delta >> 2) & 0x00FFFFFF)


def stage_path(stage: str) -> Path:
    return ROMFS / "stage" / stage / "scenerio.gcx"


def write_asm_delta(size: int) -> None:
    """Rewrite the delta literal so the assembled trampolines target this stage."""
    text = ASM_SOURCE.read_text(encoding="utf-8")
    marker = "korean_delta_literal:\n    .word "
    head, _, tail = text.partition(marker)
    if not tail:
        raise PocError("delta literal marker missing from the assembly source")
    rest = tail.split("\n", 1)[1] if "\n" in tail else ""
    ASM_SOURCE.write_text(f"{head}{marker}0x{size - 4:08X}\n{rest}", encoding="utf-8")


def assemble() -> tuple[bytes, dict[str, int]]:
    obj, elf, raw = OUT / "poc.o", OUT / "poc.elf", OUT / "poc.bin"
    subprocess.run([AS, "-march=armv6k", "-o", obj, ASM_SOURCE], check=True)
    subprocess.run([LD, f"-Ttext=0x{TEXT_CAVE_VA:08X}", "-o", elf, obj], check=True)
    subprocess.run([OBJCOPY, "-O", "binary", "-j", ".text", elf, raw], check=True)
    nm = subprocess.run([NM, "-n", elf], check=True, capture_output=True, text=True).stdout
    wanted = {sym for _, sym in PATCH_SITES.values()}
    symbols = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines())
               if len(f) == 3 and f[2] in wanted}
    if set(symbols) != wanted:
        raise PocError(f"missing trampoline symbols: {sorted(wanted - set(symbols))}")
    blob = raw.read_bytes()
    limit = EXPECTED_SEGMENTS["text"][0] + EXPECTED_SEGMENTS["text"][1] * 0x1000
    if TEXT_CAVE_VA + len(blob) > limit:
        raise PocError("trampolines exceed the existing text page allocation")
    return blob, symbols


def build_movie(source: bytes, count: int) -> tuple[bytes, dict[str, object]]:
    """Put 'ABC <first N korean tokens> XYZ' into a fixed-capacity subtitle."""
    _, records, _ = parse_records(source)
    tokens = b"".join((0x8401 + i).to_bytes(2, "big") for i in range(count))
    payload = b"ABC " + tokens + b" XYZ\0"
    for record in records:
        for entry, subtitle in enumerate(record.subtitles):
            if subtitle.entry_type == 1 and len(subtitle.raw) >= len(payload):
                out = bytearray(source)
                original = bytes(out[subtitle.offset:subtitle.offset + len(subtitle.raw)])
                repl = payload + b"\0" * (len(subtitle.raw) - len(payload))
                out[subtitle.offset:subtitle.offset + len(subtitle.raw)] = repl
                if len(out) != len(source):
                    raise PocError("movie layout changed")
                return bytes(out), {
                    "record": record.index, "entry": entry, "offset": subtitle.offset,
                    "capacity": len(subtitle.raw), "tokens": count,
                    "original_hex": original.hex(), "patched_hex": repl.hex(),
                }
    raise PocError("no fixed-capacity subtitle large enough")


def build(stage: str, glyph_count: int) -> None:
    for path in (AS, LD, OBJCOPY, NM, THREEDSTOOL, ASM_SOURCE, KOREAN_PAGE, SOURCE_CODE):
        if not path.exists():
            raise PocError(f"missing required file: {path}")
    src_gcx = stage_path(stage)
    if not src_gcx.exists():
        raise PocError(f"unknown stage: {stage}")
    OUT.mkdir(parents=True, exist_ok=True)

    original_gcx = src_gcx.read_bytes()
    original_size = len(original_gcx)
    page = KOREAN_PAGE.read_bytes()
    if len(page) != BANK:
        raise PocError(f"korean page must be 0x{BANK:X} bytes, got 0x{len(page):X}")

    compressed = SOURCE_CODE.read_bytes()
    image = decompress(compressed)
    if sha(image) != EXPECTED_DECOMPRESSED_SHA256:
        raise PocError("source code.bin changed; refusing to patch")
    exheader = bytearray(SOURCE_EXHEADER.read_bytes())
    for name, off in (("text", 0x10), ("rodata", 0x20), ("data", 0x30)):
        if struct.unpack_from("<III", exheader, off) != EXPECTED_SEGMENTS[name][:3]:
            raise PocError(f"unexpected {name} exheader tuple")

    write_asm_delta(original_size)
    trampolines, symbols = assemble()
    if struct.pack("<I", original_size - 4) not in trampolines:
        raise PocError("delta literal did not make it into the assembled blob")
    if struct.pack("<I", FONT_DESCRIPTOR_VA) not in trampolines:
        raise PocError("descriptor literal missing from the assembled blob")

    patched = bytearray(image)
    mods: list[dict[str, object]] = []
    for name, (site, symbol) in PATCH_SITES.items():
        off = site - EXPECTED_SEGMENTS["text"][0]
        old = struct.unpack_from("<I", patched, off)[0]
        if old != EXPECTED_SITE_WORDS[name]:
            raise PocError(f"unexpected instruction at {site:08X}: {old:08X}")
        new = branch_word(site, symbols[symbol])
        patched[off:off + 4] = struct.pack("<I", new)
        mods.append({"address": f"0x{site:08X}", "file_offset": f"0x{off:X}",
                     "original_bytes": struct.pack("<I", old).hex(),
                     "patched_bytes": struct.pack("<I", new).hex(), "function": name})

    cave_off = TEXT_CAVE_VA - EXPECTED_SEGMENTS["text"][0]
    if any(patched[cave_off:cave_off + len(trampolines)]):
        raise PocError("text extension area is not zero-filled")
    patched[cave_off:cave_off + len(trampolines)] = trampolines
    mods.append({"address": f"0x{TEXT_CAVE_VA:08X}", "file_offset": f"0x{cave_off:X}",
                 "original_bytes": "00" * len(trampolines),
                 "patched_bytes": trampolines.hex(), "function": "trampolines"})

    new_text_size = cave_off + len(trampolines)
    struct.pack_into("<I", exheader, 0x18, new_text_size)

    movie, movie_patch = build_movie(SOURCE_MOVIE.read_bytes(), glyph_count)
    patched_gcx = original_gcx + page

    (OUT / "code.poc.decompressed.bin").write_bytes(bytes(patched))
    (OUT / "exheader.poc.bin").write_bytes(bytes(exheader))
    (OUT / "movie.poc.dat").write_bytes(movie)
    (OUT / "scenerio.poc.gcx").write_bytes(patched_gcx)
    code_out = OUT / "code.poc.bin"
    code_out.unlink(missing_ok=True)
    subprocess.run([THREEDSTOOL, "-z", "--compress-type", "blz", "--compress-align", "16",
                    "-f", OUT / "code.poc.decompressed.bin", "--compress-out", code_out], check=True)
    if decompress(code_out.read_bytes()) != bytes(patched):
        raise PocError("BLZ round-trip mismatch")

    stage_dir = OUT / "stage/partition0"
    (stage_dir / "exefs").mkdir(parents=True, exist_ok=True)
    (stage_dir / f"romfs/stage/{stage}").mkdir(parents=True, exist_ok=True)
    shutil.copy2(code_out, stage_dir / "exefs/code.bin")
    shutil.copy2(OUT / "exheader.poc.bin", stage_dir / "exheader.bin")
    shutil.copy2(OUT / "movie.poc.dat", stage_dir / "romfs/movie.dat")
    shutil.copy2(OUT / "scenerio.poc.gcx", stage_dir / f"romfs/stage/{stage}/scenerio.gcx")

    manifest = {
        "format": "mgs3d-korean-eof-append-poc-v1",
        "status": "built-runtime-unverified",
        "hypothesis": "bytes appended past a stage scenerio.gcx EOF stay resident and are "
                      "reachable at *(0x00A472AC)-4 + original_file_size",
        "stage": stage,
        "glyph_count": glyph_count,
        "intercepted_tokens": f"0x8401..0x{0x8400 + glyph_count:04X}",
        "runtime_pointer": {
            "descriptor_va": f"0x{FONT_DESCRIPTOR_VA:08X}",
            "descriptor_holds": "buffer_base + 4",
            "original_file_size": original_size,
            "delta_literal": f"0x{original_size - 4:08X}",
            "formula": "*(0x00A472AC) + (original_file_size - 4)",
        },
        "sources": {
            "code_bin_sha256": sha(compressed),
            "decompressed_sha256": sha(image),
            "scenerio_gcx": str(src_gcx), "scenerio_sha256": sha(original_gcx),
            "korean_page": str(KOREAN_PAGE), "korean_page_sha256": sha(page),
            "token_map": str(TOKEN_MAP),
        },
        "outputs": {
            "code_bin_sha256": sha(code_out.read_bytes()),
            "decompressed_sha256": sha(bytes(patched)),
            "exheader_sha256": sha(bytes(exheader)),
            "movie_sha256": sha(movie),
            "scenerio_sha256": sha(patched_gcx),
            "scenerio_size": len(patched_gcx),
        },
        "layout": {
            "trampoline_va": f"0x{TEXT_CAVE_VA:08X}", "trampoline_size": len(trampolines),
            "old_text_size": EXPECTED_SEGMENTS["text"][2], "new_text_size": new_text_size,
            "text_pages_changed": False,
        },
        "symbols": {k: f"0x{v:08X}" for k, v in symbols.items()},
        "modified_offsets": mods,
        "movie_test_patch": movie_patch,
    }
    (OUT / "patch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": stage, "original_size": original_size,
        "patched_size": len(patched_gcx), "appended": len(page),
        "delta_literal": f"0x{original_size - 4:08X}",
        "trampoline_size": len(trampolines), "new_text_size": new_text_size,
        "staged": str(stage_dir),
    }, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="v001a")
    ap.add_argument("--glyphs", type=int, default=3,
                    help="how many Korean tokens to put in the test subtitle")
    args = ap.parse_args()
    build(args.stage, args.glyphs)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, PocError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
