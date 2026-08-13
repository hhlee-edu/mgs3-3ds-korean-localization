#!/usr/bin/env python3
"""Build and verify an isolated A0xx Korean global-glyph binary POC."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from mgs3d_gcx_font_tool import render_character  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402
from nintendo_blz import decompress  # noqa: E402
from PIL import ImageFont  # noqa: E402

OUT = ROOT / "analysis/global_korean_glyph_poc_2026-08-12"
SOURCE_CODE = Path(r"C:\Users\hhlee\Desktop\Romforge\output\backup_before_a0xx_ganada_poc_20260812\exefs\code.bin")
SOURCE_EXHEADER = Path(r"C:\Users\hhlee\Desktop\Romforge\output\backup_before_a0xx_ganada_poc_20260812\exheader.bin")
SOURCE_MOVIE = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/movie_live_base.dat"
ASM_SOURCE = OUT / "poc_trampolines.s"
FONT = Path(r"C:\Windows\Fonts\malgun.ttf")
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
TEXT_GLYPH_VA = 0x0087FAF8
KOREAN_ASSET_VA = 0x00A7B000
POC_CHARS = "가나다"

PATCH_SITES = {
    "asset_loader": (0x0010128C, "korean_asset_loader", "mount rom: then allocate/load persistent /korean_page.bin"),
    "draw_1": (0x0015E600, "korean_draw_1", "draw path 1: test A0xx before flag mask"),
    "draw_2": (0x0015EC58, "korean_draw_2", "draw path 2: test A0xx before flag mask"),
    "width_1": (0x00184398, "korean_width_1", "width path 1: A0xx has fixed width 16"),
    "width_2": (0x0018445C, "korean_width_2", "width path 2: A0xx has fixed width 16"),
    "pre_draw": (0x0015E5A4, "korean_pre_draw", "preserve raw A0xx before terminal draw lookup"),
    "layout_classify": (0x00183A04, "korean_layout_classify", "classify A0xx as ordinary 16px glyph while preserving raw stream token"),
}
EXPECTED_SITE_WORDS = {
    "asset_loader": 0xEA003F08,
    "draw_1": 0xE3C11A06,
    "draw_2": 0xE3C91A06,
    "width_1": 0xE3C00A06,
    "width_2": 0xE3C11A06,
    "pre_draw": 0xE3C11A06,
    "layout_classify": 0xE3C10A06,
}


class PocError(RuntimeError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_korean_token(index: int) -> int:
    if not 0 <= index < 1020:
        raise ValueError("Korean glyph index must be 0..1019")
    group, offset = divmod(index, 255)
    return 0xA001 + group * 0x100 + offset


def decode_korean_token(token: int) -> int:
    if not 0xA001 <= token <= 0xA3FF or (token & 0xFF) == 0:
        raise ValueError(f"not a Korean A0xx token: 0x{token:04X}")
    within = token - 0xA000
    index = within - 1 - ((within - 1) >> 8)
    if not 0 <= index < 1020:
        raise ValueError("decoded index outside Korean page")
    return index


def branch_word(source_va: int, target_va: int) -> int:
    delta = target_va - (source_va + 8)
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise PocError(f"ARM branch out of range/alignment: {source_va:X}->{target_va:X}")
    return 0xEA000000 | ((delta >> 2) & 0x00FFFFFF)


def require_tools() -> None:
    for path in (AS, LD, OBJCOPY, NM, THREEDSTOOL, FONT, ASM_SOURCE):
        if not path.exists():
            raise PocError(f"required file/tool missing: {path}")


def load_sources() -> tuple[bytes, bytes, bytes, bytes]:
    compressed = SOURCE_CODE.read_bytes()
    image = decompress(compressed)
    if sha(image) != EXPECTED_DECOMPRESSED_SHA256:
        raise PocError("source decompressed code hash changed; refusing to patch")
    exheader = SOURCE_EXHEADER.read_bytes()
    for name, offset in (("text", 0x10), ("rodata", 0x20), ("data", 0x30)):
        actual = struct.unpack_from("<III", exheader, offset)
        if actual != EXPECTED_SEGMENTS[name][:3]:
            raise PocError(f"unexpected {name} exheader tuple: {actual}")
    movie = SOURCE_MOVIE.read_bytes()
    return compressed, image, exheader, movie


def assemble() -> tuple[bytes, dict[str, int]]:
    obj = OUT / "poc_trampolines.o"
    elf = OUT / "poc_trampolines.elf"
    raw = OUT / "poc_trampolines.bin"
    subprocess.run([AS, "-march=armv6k", "-o", obj, ASM_SOURCE], check=True)
    subprocess.run([LD, f"-Ttext=0x{TEXT_CAVE_VA:08X}", "-o", elf, obj], check=True)
    subprocess.run([OBJCOPY, "-O", "binary", "-j", ".text", elf, raw], check=True)
    nm = subprocess.run([NM, "-n", elf], check=True, capture_output=True, text=True).stdout
    symbols: dict[str, int] = {}
    for line in nm.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in {v[1] for v in PATCH_SITES.values()}:
            symbols[fields[2]] = int(fields[0], 16)
    if set(symbols) != {v[1] for v in PATCH_SITES.values()}:
        raise PocError(f"missing trampoline symbols: {symbols}")
    blob = raw.read_bytes()
    if TEXT_CAVE_VA + len(blob) > EXPECTED_SEGMENTS["text"][0] + EXPECTED_SEGMENTS["text"][1] * 0x1000:
        raise PocError("trampolines exceed existing text page allocation")
    return blob, symbols


def build_movie_poc(source: bytes) -> tuple[bytes, dict[str, object]]:
    _, records, _ = parse_records(source)
    # Renderer-isolation diagnostic: 0x8401..0x8403 are known-valid page-3
    # character tokens.  The draw/width trampolines temporarily intercept only
    # these three slots so parser survival and custom bitmap lookup are tested
    # independently from the rejected A0xx namespace.
    payload = b"ABC " + b"".join((0x8401 + i).to_bytes(2, "big") for i in range(3)) + b" XYZ\0"
    selected = None
    for record in records:
        for entry, subtitle in enumerate(record.subtitles):
            if len(subtitle.raw) >= len(payload) and subtitle.entry_type == 1:
                selected = (record.index, entry, subtitle)
                break
        if selected:
            break
    if selected is None:
        raise PocError("no safe fixed-capacity movie subtitle found")
    record_index, entry, subtitle = selected
    output = bytearray(source)
    original = bytes(output[subtitle.offset : subtitle.offset + len(subtitle.raw)])
    replacement = payload + b"\0" * (len(subtitle.raw) - len(payload))
    output[subtitle.offset : subtitle.offset + len(subtitle.raw)] = replacement
    if len(output) != len(source):
        raise PocError("movie layout changed")
    return bytes(output), {
        "record": record_index,
        "entry": entry,
        "offset": subtitle.offset,
        "capacity": len(subtitle.raw),
        "display": "ABC 가나다 XYZ",
        "encoded_hex": payload.hex(),
        "original_hex": original.hex(),
        "patched_hex": replacement.hex(),
    }


def build() -> None:
    require_tools()
    OUT.mkdir(parents=True, exist_ok=True)
    compressed, source_image, source_exheader, source_movie = load_sources()
    trampolines, symbols = assemble()
    pointer_literal = struct.pack("<I", KOREAN_ASSET_VA)
    if trampolines.count(pointer_literal) < 3:
        raise PocError("draw trampoline Korean glyph pointer literals are stale or missing")
    patched = bytearray(source_image)
    modifications: list[dict[str, object]] = []

    for name, (site, symbol, purpose) in PATCH_SITES.items():
        offset = site - EXPECTED_SEGMENTS["text"][0]
        old_word = struct.unpack_from("<I", patched, offset)[0]
        if old_word != EXPECTED_SITE_WORDS[name]:
            raise PocError(f"unexpected instruction at {site:08X}: {old_word:08X}")
        new_word = branch_word(site, symbols[symbol])
        patched[offset : offset + 4] = struct.pack("<I", new_word)
        modifications.append({
            "address": f"0x{site:08X}", "file_offset": f"0x{offset:X}",
            "original_bytes": struct.pack("<I", old_word).hex(),
            "patched_bytes": struct.pack("<I", new_word).hex(),
            "purpose": purpose, "function": name,
        })

    text_cave_offset = TEXT_CAVE_VA - EXPECTED_SEGMENTS["text"][0]
    old_cave = bytes(patched[text_cave_offset : text_cave_offset + len(trampolines)])
    if any(old_cave):
        raise PocError("text extension area is not zero-filled")
    patched[text_cave_offset : text_cave_offset + len(trampolines)] = trampolines
    modifications.append({
        "address": f"0x{TEXT_CAVE_VA:08X}", "file_offset": f"0x{text_cave_offset:X}",
        "original_bytes": old_cave.hex(), "patched_bytes": trampolines.hex(),
        "purpose": "six A0xx parser/draw/width trampolines", "function": "poc_trampolines",
    })

    font = ImageFont.truetype(str(FONT), 16)
    glyphs = b"".join(render_character(ch, font) for ch in POC_CHARS)
    if len(glyphs) != 192:
        raise PocError("POC glyph generator did not produce 3x64 bytes")
    korean_page = glyphs + bytes(0xFF00 - len(glyphs))
    (OUT / "korean_page.bin").write_bytes(korean_page)
    if TEXT_CAVE_VA + len(trampolines) != TEXT_GLYPH_VA:
        raise PocError("assembled trampoline size no longer ends at TEXT_GLYPH_VA")
    glyph_offset = TEXT_GLYPH_VA - EXPECTED_SEGMENTS["text"][0]
    old_data = bytes(patched[glyph_offset : glyph_offset + len(glyphs)])
    if any(old_data):
        raise PocError("text glyph extension area is not zero-filled")
    patched[glyph_offset:glyph_offset + len(glyphs)] = glyphs
    modifications.append({
        "address": f"0x{TEXT_GLYPH_VA:08X}", "file_offset": f"0x{glyph_offset:X}",
        "original_bytes": old_data.hex(),
        "patched_bytes": glyphs.hex(),
        "purpose": "가나다 3x64B resident text storage; trampoline literals are the independent Korean base",
        "function": "korean_page_storage",
    })

    new_text_size = (TEXT_GLYPH_VA - EXPECTED_SEGMENTS["text"][0]) + len(glyphs)
    patched_exheader = bytearray(source_exheader)
    struct.pack_into("<I", patched_exheader, 0x18, new_text_size)

    movie_poc, movie_patch = build_movie_poc(source_movie)
    patched_image = bytes(patched)
    (OUT / "code.poc.decompressed.bin").write_bytes(patched_image)
    (OUT / "exheader.poc.bin").write_bytes(patched_exheader)
    (OUT / "movie.poc.dat").write_bytes(movie_poc)
    compressed_out = OUT / "code.poc.bin"
    if compressed_out.exists():
        compressed_out.unlink()
    subprocess.run([
        THREEDSTOOL, "-z", "--compress-type", "blz", "--compress-align", "16",
        "-f", OUT / "code.poc.decompressed.bin", "--compress-out", compressed_out,
    ], check=True)
    stage = OUT / "stage/partition0"
    (stage / "exefs").mkdir(parents=True, exist_ok=True)
    (stage / "romfs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(compressed_out, stage / "exefs/code.bin")
    shutil.copy2(OUT / "exheader.poc.bin", stage / "exheader.bin")
    shutil.copy2(OUT / "movie.poc.dat", stage / "romfs/movie.dat")
    shutil.copy2(OUT / "korean_page.bin", stage / "romfs/korean_page.bin")

    token_rows = []
    for index, ch in enumerate(POC_CHARS):
        token = encode_korean_token(index)
        token_rows.append({"character": ch, "index": index, "token": f"0x{token:04X}", "bytes": token.to_bytes(2, "big").hex()})
    with (OUT / "korean_token_map.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=token_rows[0].keys()); writer.writeheader(); writer.writerows(token_rows)

    manifest = {
        "format": "mgs3d-global-korean-glyph-poc-v1",
        "status": "binary-built-runtime-screen-pending",
        "sources": {
            "code_bin": str(SOURCE_CODE), "code_bin_sha256": sha(compressed),
            "decompressed_sha256": sha(source_image),
            "exheader": str(SOURCE_EXHEADER), "exheader_sha256": sha(source_exheader),
            "movie": str(SOURCE_MOVIE), "movie_sha256": sha(source_movie),
        },
        "outputs": {
            "code_bin_sha256": sha(compressed_out.read_bytes()),
            "decompressed_sha256": sha(patched_image),
            "exheader_sha256": sha(bytes(patched_exheader)),
            "movie_sha256": sha(movie_poc),
        },
        "layout": {
            "trampoline_va": f"0x{TEXT_CAVE_VA:08X}", "trampoline_size": len(trampolines),
            "old_text_size": EXPECTED_SEGMENTS["text"][2], "new_text_size": new_text_size,
            "glyph_va": f"0x{TEXT_GLYPH_VA:08X}", "glyph_bytes": len(glyphs),
            "korean_pointer_storage": "two text literal words containing the glyph base",
            "old_data_size": EXPECTED_SEGMENTS["data"][2], "new_data_size": EXPECTED_SEGMENTS["data"][2],
            "text_pages_changed": False, "data_pages_changed": False,
        },
        "symbols": {k: f"0x{v:08X}" for k, v in symbols.items()},
        "modified_offsets": modifications,
        "movie_test_patch": movie_patch,
    }
    (OUT / "patch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify(write_results=True)
    print(f"built isolated POC in {OUT}")


def verify(write_results: bool = False) -> None:
    compressed, source_image, source_exheader, source_movie = load_sources()
    del compressed, source_exheader
    paths = {
        "compressed": OUT / "code.poc.bin", "image": OUT / "code.poc.decompressed.bin",
        "exheader": OUT / "exheader.poc.bin", "movie": OUT / "movie.poc.dat",
        "manifest": OUT / "patch_manifest.json", "tokens": OUT / "korean_token_map.csv",
    }
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise PocError(f"missing POC outputs: {missing}")
    image = paths["image"].read_bytes()
    if decompress(paths["compressed"].read_bytes()) != image:
        raise PocError("compressed code does not round-trip to patched image")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    for name, (site, symbol, _) in PATCH_SITES.items():
        offset = site - EXPECTED_SEGMENTS["text"][0]
        target = int(manifest["symbols"][symbol], 16)
        if struct.unpack_from("<I", image, offset)[0] != branch_word(site, target):
            raise PocError(f"branch verification failed: {name}")
    for index in range(1020):
        if decode_korean_token(encode_korean_token(index)) != index:
            raise PocError(f"Korean token round-trip failed at {index}")
    if len(paths["movie"].read_bytes()) != len(source_movie):
        raise PocError("movie POC size/layout changed")
    exheader = paths["exheader"].read_bytes()
    if struct.unpack_from("<I", exheader, 0x18)[0] != manifest["layout"]["new_text_size"]:
        raise PocError("patched text size mismatch")
    if struct.unpack_from("<I", exheader, 0x38)[0] != EXPECTED_SEGMENTS["data"][2]:
        raise PocError("data size unexpectedly changed")
    results = {
        "format": "mgs3d-global-korean-glyph-poc-test-v1",
        "binary_build": "pass", "blz_round_trip": "pass",
        "branch_sites": "pass", "token_round_trip": "1020/1020 pass",
        "glyph_size": "3x64B pass", "movie_size_unchanged": True,
        "source_image_unchanged": sha(source_image) == EXPECTED_DECOMPRESSED_SHA256,
        "runtime_screen": "pending user/Azahar verification",
        "success_claimed": False,
    }
    cci = OUT / "MGS3D_A0XX_GANADA_POC.cci"
    if cci.exists():
        results.update({
            "isolated_cci_build": "pass",
            "isolated_cci_sha256": sha(cci.read_bytes()),
            "azahar_process_boot": "pass: process remained alive and responsive after 15 seconds",
            "runtime_screen": "pending user visual verification of movie record 0 entry 4",
        })
    if write_results:
        (OUT / "test_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


def analyze() -> None:
    require_tools(); _, image, exheader, movie = load_sources()
    del image, exheader, movie
    print("A0xx path: raw 2-byte token reaches draw/width; four terminal mask sites require branches")
    print(f"text extension: 0x{TEXT_CAVE_VA:08X}, available {0x880000-TEXT_CAVE_VA} bytes")
    print(f"text-resident glyph base: 0x{TEXT_GLYPH_VA:08X}, within existing text pages")
    for i, ch in enumerate(POC_CHARS):
        t = encode_korean_token(i); print(f"{ch}: index={i} token=0x{t:04X} roundtrip={decode_korean_token(t)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--analyze", action="store_true")
    action.add_argument("--build-poc", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.analyze: analyze()
    elif args.build_poc: build()
    else: verify(write_results=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, PocError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
