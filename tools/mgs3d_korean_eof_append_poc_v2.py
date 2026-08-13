#!/usr/bin/env python3
"""EOF-append Korean glyph POC, v2 (stage-independent addressing).

v1 anchored on `*(0x00A472AC) - 4 + <one stage's file size>`.  That only
resolves while that exact stage is resident; the runtime test showed garbled
glyphs, i.e. the pointer landed on real-but-wrong bytes.

v2 keeps the same hypothesis (bytes appended past a stage file's EOF stay
resident) but makes the address stage-independent:

    korean_page_base = table[2] + K          table[2] = *(0x00A46FE0)

Every stage file is padded so its Korean page starts at exactly
`page2_offset + K`, so one constant works for all 91 stages.  table[2] is the
page-2 font pointer the draw path itself uses, so it is valid whenever text
renders at all.

Originals are read from the v2 backup, then the v1 backup, when present so
repeated runs never compound.  Nothing is written outside OUT unless
--stage-romforge is passed.
"""

from __future__ import annotations

import argparse
import binascii
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
LIVE = Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0")
V1_BACKUP = Path(r"C:\Users\hhlee\Desktop\Romforge\output\backup_before_korean_eof_append_20260812")
V2_BACKUP = Path(r"C:\Users\hhlee\Desktop\Romforge\output\backup_before_korean_eof_v2_20260812")
KOREAN_PAGE = ROOT / "experiments/global_korean_page_build_2026-08-12/korean_page_stress_64.bin"
THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"
AS = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-as.exe")
LD = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-ld.exe")
OBJCOPY = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-objcopy.exe")
NM = Path(r"C:\devkitPro\devkitARM\bin\arm-none-eabi-nm.exe")

EXPECTED_DECOMPRESSED_SHA256 = "10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7"
TEXT = (0x00100000, 0x780, 0x77F8C4)
TEXT_CAVE_VA = 0x0087F8C4
TABLE_PAGE2_VA = 0x00A46FE0          # &table[2]; live-verified
K = 0x56000                          # page2_offset -> korean page, all stages
BANK = 0xFF00
FONT_SIG_HEX = ("000000000000000000000000000001000ff42fe0341db0387007c01c6003800c3"
                "00ed0282d7839b00550054000000000000000000000000000000000000000000")

PATCH_SITES = {
    "draw_1": (0x0015E600, "korean_draw_1", 0xE3C11A06),
    "draw_2": (0x0015EC58, "korean_draw_2", 0xE3C91A06),
    "width_1": (0x00184398, "korean_width_1", 0xE3C00A06),
    "width_2": (0x0018445C, "korean_width_2", 0xE3C11A06),
    "pre_draw": (0x0015E5A4, "korean_pre_draw", 0xE3C11A06),
    "layout_classify": (0x00183A04, "korean_layout_classify", 0xE3C10A06),
}


class PocError(RuntimeError):
    pass


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def page2_offset(data: bytes) -> int:
    """Font page-2 offset, derived the way the game's own parser (0x00108320)
    does it: a header word, a u32 table terminated by 0xFFFFFFFF, then four
    section deltas.  page2 = section3 + 4.

    This replaces the previous font-signature search, which silently failed on
    every stage whose font content differs from the one the signature was
    lifted from -- 78 of 169 stages, including `title`, the stage actually
    resident during the movie test.  Verified against two live captures
    (v001a 0x568E4, title 0x234B4) and parses all 169 stage files."""
    i = 4
    while struct.unpack_from("<I", data, i)[0] != 0xFFFFFFFF:
        i += 4
        if i + 4 > len(data):
            raise PocError("offset table terminator not found")
    r0 = i + 4
    return r0 + struct.unpack_from("<I", data, r0 + 0xC)[0] + 4


def branch_word(src: int, dst: int) -> int:
    delta = dst - (src + 8)
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise PocError(f"branch out of range {src:X}->{dst:X}")
    return 0xEA000000 | ((delta >> 2) & 0x00FFFFFF)


def pristine_stage_bytes(name: str) -> bytes:
    """Prefer pristine v2/v1 backups so re-runs never compound a patch."""
    candidates = (
        V2_BACKUP / "romfs/stage" / name / "scenerio.gcx",
        V1_BACKUP / "romfs/stage" / name / "scenerio.gcx",
        LIVE / "romfs/stage" / name / "scenerio.gcx",
    )
    return next(path for path in candidates if path.exists()).read_bytes()


def assemble() -> tuple[bytes, dict[str, int]]:
    obj, elf, raw = OUT / "poc.o", OUT / "poc.elf", OUT / "poc.bin"
    subprocess.run([AS, "-march=armv6k", "-o", obj, ASM_SOURCE], check=True)
    subprocess.run([LD, f"-Ttext=0x{TEXT_CAVE_VA:08X}", "-o", elf, obj], check=True)
    subprocess.run([OBJCOPY, "-O", "binary", "-j", ".text", elf, raw], check=True)
    nm = subprocess.run([NM, "-n", elf], check=True, capture_output=True, text=True).stdout
    wanted = {s for _, s, _ in PATCH_SITES.values()}
    syms = {f[2]: int(f[0], 16) for f in (l.split() for l in nm.splitlines())
            if len(f) == 3 and f[2] in wanted}
    if set(syms) != wanted:
        raise PocError(f"missing symbols: {sorted(wanted - set(syms))}")
    blob = raw.read_bytes()
    if struct.pack("<I", TABLE_PAGE2_VA) not in blob or struct.pack("<I", K) not in blob:
        raise PocError("trampoline literals are stale — check poc_trampolines.s")
    if TEXT_CAVE_VA + len(blob) > TEXT[0] + TEXT[1] * 0x1000:
        raise PocError("trampolines exceed text page allocation")
    return blob, syms


def build_movie(count: int) -> tuple[bytes, dict[str, object]]:
    src = SOURCE_MOVIE.read_bytes()
    _, records, _ = parse_records(src)
    payload = b"ABC " + b"".join((0x8401 + i).to_bytes(2, "big") for i in range(count)) + b" XYZ\0"
    for rec in records:
        for entry, sub in enumerate(rec.subtitles):
            if sub.entry_type == 1 and len(sub.raw) >= len(payload):
                out = bytearray(src)
                repl = payload + b"\0" * (len(sub.raw) - len(payload))
                out[sub.offset:sub.offset + len(sub.raw)] = repl
                if len(out) != len(src):
                    raise PocError("movie layout changed")
                return bytes(out), {"record": rec.index, "entry": entry,
                                    "offset": sub.offset, "capacity": len(sub.raw),
                                    "tokens": count, "patched_hex": repl.hex()}
    raise PocError("no subtitle with enough fixed capacity")


def build_stages(page: bytes) -> tuple[list[dict], Path]:
    dst_root = OUT / "stage/partition0/romfs/stage"
    if dst_root.exists():
        shutil.rmtree(dst_root)
    rows = []
    for src in sorted((LIVE / "romfs/stage").glob("*/scenerio.gcx")):
        name = src.parent.name
        data = pristine_stage_bytes(name)
        page2 = page2_offset(data)
        if not 0 < page2 < len(data):
            raise PocError(f"{name}: page2 offset 0x{page2:X} outside file")
        target = page2 + K
        if target < len(data):
            raise PocError(f"{name}: K=0x{K:X} lands inside existing data "
                           f"(need >= 0x{len(data) - page2:X})")
        patched = data + bytes(target - len(data)) + page
        out = dst_root / name / "scenerio.gcx"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(patched)
        rows.append({"stage": name, "original_size": len(data), "page2_offset": page2,
                     "korean_offset": target, "new_size": len(patched),
                     "growth": len(patched) - len(data), "sha256": sha(patched)})
    return rows, dst_root


def build(glyph_count: int, do_stage: bool) -> None:
    for p in (AS, LD, OBJCOPY, NM, THREEDSTOOL, ASM_SOURCE, KOREAN_PAGE, SOURCE_CODE):
        if not p.exists():
            raise PocError(f"missing: {p}")
    page = KOREAN_PAGE.read_bytes()
    if len(page) != BANK:
        raise PocError(f"korean page must be 0x{BANK:X}, got 0x{len(page):X}")
    OUT.mkdir(parents=True, exist_ok=True)

    image = decompress(SOURCE_CODE.read_bytes())
    if sha(image) != EXPECTED_DECOMPRESSED_SHA256:
        raise PocError("source code.bin changed; refusing to patch")
    exheader = bytearray(SOURCE_EXHEADER.read_bytes())

    trampolines, syms = assemble()
    patched = bytearray(image)
    mods = []
    for name, (site, sym, expect) in PATCH_SITES.items():
        off = site - TEXT[0]
        old = struct.unpack_from("<I", patched, off)[0]
        if old != expect:
            raise PocError(f"unexpected instruction at {site:08X}: {old:08X}")
        new = branch_word(site, syms[sym])
        patched[off:off + 4] = struct.pack("<I", new)
        mods.append({"address": f"0x{site:08X}", "original_bytes": f"{old:08x}",
                     "patched_bytes": f"{new:08x}", "function": name})
    cave = TEXT_CAVE_VA - TEXT[0]
    if any(patched[cave:cave + len(trampolines)]):
        raise PocError("text cave is not zero-filled")
    patched[cave:cave + len(trampolines)] = trampolines
    new_text_size = cave + len(trampolines)
    struct.pack_into("<I", exheader, 0x18, new_text_size)

    movie, movie_patch = build_movie(glyph_count)
    stage_rows, _ = build_stages(page)

    (OUT / "code.poc.decompressed.bin").write_bytes(bytes(patched))
    (OUT / "exheader.poc.bin").write_bytes(bytes(exheader))
    (OUT / "movie.poc.dat").write_bytes(movie)
    code_out = OUT / "code.poc.bin"
    code_out.unlink(missing_ok=True)
    subprocess.run([THREEDSTOOL, "-z", "--compress-type", "blz", "--compress-align", "16",
                    "-f", OUT / "code.poc.decompressed.bin", "--compress-out", code_out], check=True)
    if decompress(code_out.read_bytes()) != bytes(patched):
        raise PocError("BLZ round-trip mismatch")

    sdir = OUT / "stage/partition0"
    (sdir / "exefs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(code_out, sdir / "exefs/code.bin")
    shutil.copy2(OUT / "exheader.poc.bin", sdir / "exheader.bin")
    (sdir / "romfs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT / "movie.poc.dat", sdir / "romfs/movie.dat")

    built = [r for r in stage_rows if "new_size" in r]
    manifest = {
        "format": "mgs3d-korean-eof-append-poc-v2",
        "status": "built-runtime-unverified",
        "supersedes": "v1 (buffer_base + per-stage file size) — garbled glyphs at runtime",
        "hypothesis": "bytes appended past a stage scenerio.gcx EOF stay resident",
        "addressing": {
            "anchor_va": f"0x{TABLE_PAGE2_VA:08X}", "anchor_meaning": "&table[2]",
            "K": f"0x{K:X}", "formula": f"*(0x{TABLE_PAGE2_VA:08X}) + 0x{K:X}",
            "stage_independent": True,
        },
        "glyph_count": glyph_count,
        "intercepted_tokens": f"0x8401..0x{0x8400 + glyph_count:04X}",
        "outputs": {
            "code_bin_sha256": sha(code_out.read_bytes()),
            "exheader_sha256": sha(bytes(exheader)),
            "movie_sha256": sha(movie),
            "stages_patched": len(built),
            "total_stage_growth": sum(r["growth"] for r in built),
        },
        "layout": {"trampoline_va": f"0x{TEXT_CAVE_VA:08X}", "trampoline_size": len(trampolines),
                   "old_text_size": TEXT[2], "new_text_size": new_text_size,
                   "text_pages_changed": False},
        "symbols": {k: f"0x{v:08X}" for k, v in syms.items()},
        "modified_offsets": mods,
        "movie_test_patch": movie_patch,
        "stages": stage_rows,
    }
    (OUT / "patch_manifest_v2.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"stages_patched": len(built),
                      "total_growth_mb": round(sum(r["growth"] for r in built) / 1048576, 2),
                      "trampoline_size": len(trampolines), "new_text_size": new_text_size,
                      "formula": f"*(0x{TABLE_PAGE2_VA:08X}) + 0x{K:X}"}, indent=2))

    if do_stage:
        stage_into_romforge(stage_rows)


def stage_into_romforge(stage_rows: list[dict]) -> None:
    sdir = OUT / "stage/partition0"
    files = [Path("exefs/code.bin"), Path("exheader.bin"), Path("romfs/movie.dat")]
    files += [Path("romfs/stage") / r["stage"] / "scenerio.gcx" for r in stage_rows if "new_size" in r]
    for rel in files:
        dst = V2_BACKUP / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LIVE / rel, dst)
    for rel in files:
        shutil.copy2(sdir / rel, LIVE / rel)
    bad = [str(r) for r in files if sha((LIVE / r).read_bytes()) != sha((sdir / r).read_bytes())]
    if bad:
        raise PocError(f"staging verification failed: {bad}")
    print(f"\nbacked up + staged {len(files)} files (backup: {V2_BACKUP})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--glyphs", type=int, default=3)
    ap.add_argument("--stage-romforge", action="store_true")
    a = ap.parse_args()
    build(a.glyphs, a.stage_romforge)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, PocError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
