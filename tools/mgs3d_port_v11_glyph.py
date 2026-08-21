#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Port the Korean glyph patch set from clean 1.0 onto the 1.1 update's code.bin.

Scope, deliberately narrow: the six glyph hooks, the 816-byte trampoline cave,
the two re-derived absolute symbols, and the 0xA4..0xA7 alias range. The CPP /
C-stick patch is **not** ported -- 1.1 rewrote that enforcer and the 1.0 pattern
does not exist there at all, so it needs its own analysis and its own build.

Everything here is derived from bytes, not from prose:

  hook sites          six `bic rX, rY, #0x6000` alias folds. All six are present
                      in 1.1 with the identical encoding; located by unique 48 B
                      context match. Two shift groups, -0x500 and -0x2224.
  cave                copied verbatim from the production 1.0 image, then
                      relocated. Internal branch displacements survive a block
                      move untouched; the 12 external returns are remapped.
  korean_desc         1.0 0x008E1618 -> 1.1 0x009191F8. Single-writer global;
                      found via the writer that also calls set_font_page, the
                      same procedure recovers 0x008E1618 on 1.0 as a control.
  korean_table2       1.0 0x00A46FE0 -> 1.1 0x00A87910. font_page_table[2];
                      table base agreed on by three independent sites.
  blank glyph         points just past the cave, into .text page padding.
  K = 0x56000         a constant, not an address. Unchanged.

    build    write the ported code.bin under builds/
    verify   re-check an already built code.bin against every invariant

Nothing here touches the RomForge staging tree, git, or a CCI.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nintendo_blz import decompress  # noqa: E402

THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"

CLEAN10 = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/exefs/code.bin"
CLEAN11 = ROOT / "analysis/unpacked_1.1/partition0/exefs/code.bin"
PROD10 = pathlib.Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\exefs\code.bin")
OUTDIR = ROOT / "builds/diag-2026-08-21-v1.1-port"

BASE = 0x00100000

# --- 1.0 geometry -----------------------------------------------------------
CAVE10_VA = 0x0087F8C4
CAVE_LEN = 0x330
TEXT10_SIZE = 0x0077F8C4
TEXT10_PAGES = 1920

# --- 1.1 geometry -----------------------------------------------------------
TEXT11_SIZE = 0x007A8104
TEXT11_PAGES = 1961
CAVE11_VA = BASE + TEXT11_SIZE          # 0x008A8104

# --- the six hooks: 1.0 VA -> (1.1 VA, cave entry in 1.0) -------------------
HOOKS = [
    (0x0015E5A4, 0x0015E0A4, 0x0087FB68),
    (0x0015E600, 0x0015E100, 0x0087F8C4),
    (0x0015EC58, 0x0015E758, 0x0087F9C8),
    (0x00183A04, 0x001817E0, 0x0087FB90),
    (0x00184398, 0x00182174, 0x0087FAC8),
    (0x0018445C, 0x00182238, 0x0087FB18),
]

# --- external cave returns: 1.0 target -> 1.1 target ------------------------
# every one verified independently by unique forward context match
TARGET_MAP = {
    0x0015E5A8: 0x0015E0A8,
    0x0015E604: 0x0015E104,
    0x0015E67C: 0x0015E17C,
    0x0015EC5C: 0x0015E75C,
    0x0015ECD0: 0x0015E7D0,
    0x00183A08: 0x001817E4,
    0x0018439C: 0x00182178,
    0x001843A4: 0x00182180,
    0x00184460: 0x0018223C,
    0x00184484: 0x00182260,
}

# --- cave literal pool: offset -> (1.0 value, 1.1 value) -------------------
LITERALS = {
    0x320: (0x008E1618, 0x009191F8),                 # korean_desc global
    0x324: (0x00A46FE0, 0x00A87910),                 # font_page_table[2]
    0x328: (0x00056000, 0x00056000),                 # K, a constant
    0x32C: (0x0087FBF4, CAVE11_VA + CAVE_LEN),       # blank-glyph slot
}

# alias range the cave must already spell (the 0xA0->0xA4 fix, applied at v0.93)
ALIAS_LO, ALIAS_HI = 0xA4, 0xA7

# the CPP enforcer range in 1.0 -- must stay untouched here
CPP10_VA = 0x0010AEF4


def sha(d: bytes) -> str:
    return hashlib.sha256(d).hexdigest()


def load(p: pathlib.Path) -> bytes:
    return decompress(p.read_bytes())


def rd(img: bytes, va: int) -> int:
    return struct.unpack_from("<I", img, va - BASE)[0]


def wr(img: bytearray, va: int, val: int) -> None:
    struct.pack_into("<I", img, va - BASE, val)


def bl_word(src_va: int, dst_va: int, cond: int = 0xE, link: bool = False) -> int:
    """Encode a B/BL from src_va to dst_va."""
    off = (dst_va - (src_va + 8)) >> 2
    if not (-0x800000 <= off < 0x800000):
        raise ValueError(f"branch out of range: 0x{src_va:08X} -> 0x{dst_va:08X}")
    op = 0xB if link else 0xA
    return (cond << 28) | (op << 24) | (off & 0xFFFFFF)


def branch_target(word: int, va: int) -> int | None:
    if ((word >> 24) & 0xF) not in (0xA, 0xB):
        return None
    imm = word & 0xFFFFFF
    if imm & 0x800000:
        imm -= 0x1000000
    return va + 8 + imm * 4


def build_cave(prod10: bytes) -> bytes:
    """Take the production cave and relocate it to CAVE11_VA."""
    off = CAVE10_VA - BASE
    cave = bytearray(prod10[off:off + CAVE_LEN])

    # 1) literal pool
    for lo, (old, new) in LITERALS.items():
        got = struct.unpack_from("<I", cave, lo)[0]
        if got != old:
            raise RuntimeError(f"cave literal +0x{lo:03X}: expected 0x{old:08X}, found 0x{got:08X}")
        struct.pack_into("<I", cave, lo, new)

    # 2) external branches. Internal ones move with the block and stay correct.
    remapped = 0
    for i in range(0, CAVE_LEN, 4):
        w = struct.unpack_from("<I", cave, i)[0]
        va10 = CAVE10_VA + i
        tgt = branch_target(w, va10)
        if tgt is None:
            continue
        if CAVE10_VA <= tgt < CAVE10_VA + CAVE_LEN:
            continue                                  # internal, displacement preserved
        if tgt not in TARGET_MAP:
            raise RuntimeError(f"unmapped external branch at +0x{i:03X} -> 0x{tgt:08X}")
        cond = (w >> 28) & 0xF
        link = ((w >> 24) & 0xF) == 0xB
        new_w = bl_word(CAVE11_VA + i, TARGET_MAP[tgt], cond, link)
        struct.pack_into("<I", cave, i, new_w)
        remapped += 1
    if remapped != 12:
        raise RuntimeError(f"expected 12 external branches, remapped {remapped}")
    return bytes(cave)


def apply_patch(img11: bytes, prod10: bytes) -> bytes:
    out = bytearray(img11)

    # cave landing zone must be untouched padding
    lo = CAVE11_VA - BASE
    if out[lo:lo + CAVE_LEN] != bytes(CAVE_LEN):
        raise RuntimeError("1.1 cave landing zone is not zero-filled")
    pad_end = TEXT11_PAGES * 4096
    if lo + CAVE_LEN > pad_end:
        raise RuntimeError("cave does not fit inside .text page padding")
    # blank-glyph slot: 64 zero bytes right after the cave
    bg = lo + CAVE_LEN
    if out[bg:bg + 64] != bytes(64):
        raise RuntimeError("blank-glyph slot is not zero-filled")

    out[lo:lo + CAVE_LEN] = build_cave(prod10)

    # the six hooks
    for va10, va11, entry10 in HOOKS:
        orig = rd(img11, va11)
        expect = rd(load_clean10(), va10)
        if orig != expect:
            raise RuntimeError(f"hook 0x{va11:08X}: 1.1 holds 0x{orig:08X}, 1.0 had 0x{expect:08X}")
        entry11 = CAVE11_VA + (entry10 - CAVE10_VA)
        wr(out, va11, bl_word(va11, entry11))

    return bytes(out)


_clean10_cache: bytes | None = None


def load_clean10() -> bytes:
    global _clean10_cache
    if _clean10_cache is None:
        _clean10_cache = load(CLEAN10)
    return _clean10_cache


def verify(img11_clean: bytes, patched: bytes, prod10: bytes) -> list[str]:
    """Static invariants. Returns a list of PASS/FAIL lines; raises on nothing."""
    out = []

    def chk(ok: bool, msg: str) -> None:
        out.append(("PASS  " if ok else "FAIL  ") + msg)

    chk(len(patched) == len(img11_clean),
        f"decompressed size unchanged ({len(patched):,} B) -> exheader needs no edit")

    # exact diff extent
    diff = [i for i in range(len(patched)) if patched[i] != img11_clean[i]]
    runs: list[list[int]] = []
    for i in diff:
        if runs and i <= runs[-1][1] + 8:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    chk(len(runs) == 7, f"patch touches {len(runs)} sites (6 hooks + 1 cave), {len(diff)} bytes")

    cave_lo = CAVE11_VA - BASE
    hook_offs = {va11 - BASE for _, va11, _ in HOOKS}
    for s, e in runs:
        if s in hook_offs:
            chk(e - s + 1 == 4, f"hook site 0x{BASE + s:08X} is exactly 4 B")
        else:
            chk(s == cave_lo, f"cave site at 0x{BASE + s:08X} (expected 0x{CAVE11_VA:08X})")
            chk(e < cave_lo + CAVE_LEN, "cave write stays inside its 0x330 extent")

    # CPP must NOT be ported
    cpp_touched = any(s <= (CPP10_VA - BASE) <= e for s, e in runs)
    chk(not cpp_touched, "CPP enforcer not patched (out of scope by instruction)")

    # hooks branch into the cave
    for va10, va11, entry10 in HOOKS:
        w = rd(patched, va11)
        tgt = branch_target(w, va11)
        want = CAVE11_VA + (entry10 - CAVE10_VA)
        chk(tgt == want, f"hook 0x{va11:08X} -> 0x{tgt:08X} (want 0x{want:08X})")

    # every cave branch resolves correctly
    ok_int = ok_ext = 0
    bad = []
    for i in range(0, CAVE_LEN, 4):
        w = struct.unpack_from("<I", patched, cave_lo + i)[0]
        va = CAVE11_VA + i
        t = branch_target(w, va)
        if t is None:
            continue
        w10 = struct.unpack_from("<I", prod10, (CAVE10_VA - BASE) + i)[0]
        t10 = branch_target(w10, CAVE10_VA + i)
        if CAVE10_VA <= t10 < CAVE10_VA + CAVE_LEN:
            if t == CAVE11_VA + (t10 - CAVE10_VA):
                ok_int += 1
            else:
                bad.append(f"+0x{i:03X} internal")
        else:
            if t == TARGET_MAP.get(t10):
                ok_ext += 1
            else:
                bad.append(f"+0x{i:03X} external -> 0x{t:08X}")
    chk(not bad, f"cave branches resolve: {ok_int} internal + {ok_ext} external"
                 + (f" | BAD: {bad}" if bad else ""))

    # literals
    for lo_, (old, new) in LITERALS.items():
        got = struct.unpack_from("<I", patched, cave_lo + lo_)[0]
        chk(got == new, f"literal +0x{lo_:03X} = 0x{got:08X} (want 0x{new:08X})")

    # the two re-derived symbols land in the right 1.1 segments
    desc = LITERALS[0x320][1]
    tab2 = LITERALS[0x324][1]
    chk(0x008EA000 <= desc < 0x00957000, f"korean_desc 0x{desc:08X} inside 1.1 .data")
    chk(tab2 >= 0x00957000, f"font_page_table[2] 0x{tab2:08X} inside 1.1 .bss")

    # alias range still 0xA4..0xA7 (the v0.93 fix must survive the port)
    alias = []
    for i in range(0, CAVE_LEN, 4):
        w = struct.unpack_from("<I", patched, cave_lo + i)[0]
        if (w & 0x0FF00000) == 0x03500000:                 # cmp rX, #imm
            imm = w & 0xFF
            rot = (w >> 8) & 0xF
            if rot == 0 and imm in (0xA0, 0xA3, ALIAS_LO, ALIAS_HI, 0x84, 0x87):
                alias.append(imm)
    chk(0xA0 not in alias and 0xA3 not in alias,
        f"alias range is A4..A7, no A0/A3 immediates left (cmp imms seen: {sorted(set(alias))})")

    # blank glyph slot still zero and inside padding
    bg = CAVE11_VA + CAVE_LEN
    chk(patched[bg - BASE: bg - BASE + 64] == bytes(64), f"blank-glyph slot 0x{bg:08X} is 64 B of zero")
    chk(bg + 64 <= BASE + TEXT11_PAGES * 4096, "blank-glyph slot inside .text padding")

    return out


def compress(image: bytes, workdir: pathlib.Path) -> bytes:
    workdir.mkdir(parents=True, exist_ok=True)
    raw = workdir / "code.decompressed.bin"
    packed = workdir / "code.blz.bin"
    raw.write_bytes(image)
    packed.unlink(missing_ok=True)
    subprocess.run([str(THREEDSTOOL), "-z", "--compress-type", "blz",
                    "--compress-align", "16", "-f", str(raw),
                    "--compress-out", str(packed)], check=True)
    data = packed.read_bytes()
    if decompress(data) != image:
        raise RuntimeError("BLZ round-trip mismatch -- refusing to emit this code.bin")
    raw.unlink(missing_ok=True)
    packed.unlink(missing_ok=True)
    return data


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["build", "verify"])
    ap.add_argument("--out", type=pathlib.Path, default=OUTDIR)
    a = ap.parse_args()

    clean11 = load(CLEAN11)
    prod10 = load(PROD10)

    if a.mode == "build":
        patched = apply_patch(clean11, prod10)
        lines = verify(clean11, patched, prod10)
        for ln in lines:
            print(ln)
        if any(ln.startswith("FAIL") for ln in lines):
            print("\nrefusing to write: static verification failed")
            return 1
        a.out.mkdir(parents=True, exist_ok=True)
        dec = a.out / "code.decompressed.bin"
        dec.write_bytes(patched)
        packed = compress(patched, a.out / ".work")
        cb = a.out / "code.bin"
        cb.write_bytes(packed)
        try:
            (a.out / ".work").rmdir()
        except OSError:
            pass
        print()
        print(f"decompressed  {len(patched):,} B  sha256 {sha(patched)}")
        print(f"code.bin      {len(packed):,} B  sha256 {sha(packed)}")
        print(f"written to    {a.out}")
        print("\nnot staged, not committed, no CCI.")
        return 0

    cb = a.out / "code.bin"
    if not cb.is_file():
        print(f"no build at {cb}")
        return 1
    patched = decompress(cb.read_bytes())
    for ln in verify(clean11, patched, prod10):
        print(ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
