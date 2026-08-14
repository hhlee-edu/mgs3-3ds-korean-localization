"""BCLIM reader/writer for MGS3D textures, including the ETC1 case.

Why this exists
---------------
`mgs3d_history_texture.py` assumed the Cold War history card
(`timg/cold_war_text_eng_alp_ovl.bclim`, format 10) was a plain 4-bit
luminance image and wrote raw nibbles into it. Format 10 is **ETC1**, a
block-compressed format, so the GPU decoded those nibbles as compressed
blocks and rendered noise. That is the 2026-08-14 "history card glyphs are all
corrupted" hardware defect.

Format enum, derived empirically from every BCLIM in this game's DARC archives
(payload bytes vs. power-of-two-padded dimensions):

    fmt  2 -> LA44   8 bpp
    fmt 10 -> ETC1   4 bpp   (4x4 blocks, 8 bytes per block)
    fmt 12 -> L4     4 bpp
    fmt 13 -> A4     4 bpp

3DS storage rules confirmed against the pristine English texture, whose decode
reproduces the real in-game sentence exactly:

* dimensions are padded up to the next power of two (400x64 -> 512x64);
* ETC1 4x4 blocks are grouped into 8x8-texel tiles, i.e. 2x2 blocks per tile;
  tiles run in raster order and the four blocks inside a tile run in Morton
  order;
* **each 8-byte ETC1 block is stored byte-reversed.**

Usage
-----
    python tools/mgs3d_bclim.py info    <in.bclim>
    python tools/mgs3d_bclim.py decode  <in.bclim> <out.png>
    python tools/mgs3d_bclim.py encode  <in.bclim> <image.png> <out.bclim>
    python tools/mgs3d_bclim.py verify  <in.bclim>

`encode` keeps the original footer and the original byte length: only the pixel
payload is rewritten, so the DARC member size never changes.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from PIL import Image

FOOTER = 40
FMT_LA44, FMT_ETC1, FMT_L4, FMT_A4 = 2, 10, 12, 13

MODIFIERS = (
    (2, 8, -2, -8), (5, 17, -5, -17), (9, 29, -9, -29), (13, 42, -13, -42),
    (18, 60, -18, -60), (24, 80, -24, -80), (33, 106, -33, -106), (47, 183, -47, -183),
)


def clamp(v: int) -> int:
    return 0 if v < 0 else (255 if v > 255 else v)


def pow2(v: int) -> int:
    n = 1
    while n < v:
        n <<= 1
    return n


def read_header(data: bytes) -> tuple[int, int, int, int]:
    width, height, fmt, image_size = struct.unpack_from("<HHII", data, len(data) - 12)
    return width, height, fmt, image_size


def block_index(bx: int, by: int, blocks_w: int) -> int:
    """8x8-texel tile = 2x2 ETC1 blocks; tiles raster, blocks Morton inside."""
    tile = (by // 2) * (blocks_w // 2) + (bx // 2)
    return tile * 4 + ((bx & 1) | ((by & 1) << 1))


# --------------------------------------------------------------------------
# ETC1
# --------------------------------------------------------------------------
def etc1_decode_block(raw: bytes) -> list[list[tuple[int, int, int]]]:
    b = raw[::-1]                       # 3DS stores each block byte-reversed
    hi = int.from_bytes(b[0:4], "big")
    lo = int.from_bytes(b[4:8], "big")
    flip, diff = hi & 1, (hi >> 1) & 1
    t2, t1 = (hi >> 2) & 7, (hi >> 5) & 7

    if diff:
        r, g, bl = (hi >> 27) & 0x1F, (hi >> 19) & 0x1F, (hi >> 11) & 0x1F
        dr, dg, db = (hi >> 24) & 7, (hi >> 16) & 7, (hi >> 8) & 7
        sx = lambda v: v - 8 if v > 3 else v
        c1 = ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (bl << 3) | (bl >> 2))
        r2, g2, b2 = (r + sx(dr)) & 0x1F, (g + sx(dg)) & 0x1F, (bl + sx(db)) & 0x1F
        c2 = ((r2 << 3) | (r2 >> 2), (g2 << 3) | (g2 >> 2), (b2 << 3) | (b2 >> 2))
    else:
        c1 = (((hi >> 28) & 0xF) * 17, ((hi >> 20) & 0xF) * 17, ((hi >> 12) & 0xF) * 17)
        c2 = (((hi >> 24) & 0xF) * 17, ((hi >> 16) & 0xF) * 17, ((hi >> 8) & 0xF) * 17)

    out = [[(0, 0, 0)] * 4 for _ in range(4)]
    for i in range(16):
        x, y = i // 4, i % 4
        mi = (((lo >> (i + 16)) & 1) << 1) | ((lo >> i) & 1)
        sub1 = (x < 2) if flip == 0 else (y < 2)
        base, tbl = (c1, t1) if sub1 else (c2, t2)
        m = MODIFIERS[tbl][mi]
        out[y][x] = tuple(clamp(c + m) for c in base)
    return out


def etc1_encode_block(pixels: list[list[tuple[int, int, int]]]) -> bytes:
    """Encode one 4x4 block. Individual mode, exhaustive over flip and tables.

    The history card is essentially monochrome text, so searching both flips and
    all eight modifier tables with per-pixel best-modifier selection is both fast
    enough and visually exact.
    """
    best = None
    for flip in (0, 1):
        if flip == 0:
            g1 = [(x, y) for y in range(4) for x in range(2)]
            g2 = [(x, y) for y in range(4) for x in range(2, 4)]
        else:
            g1 = [(x, y) for y in range(2) for x in range(4)]
            g2 = [(x, y) for y in range(2, 4) for x in range(4)]

        for group, other in ((g1, g2),):
            def avg(cells):
                n = len(cells)
                return tuple(sum(pixels[y][x][c] for x, y in cells) // n for c in range(3))

            a1, a2 = avg(group), avg(other)
            # 4-bit base colours (individual mode)
            q1 = tuple(min(15, max(0, round(v / 17))) for v in a1)
            q2 = tuple(min(15, max(0, round(v / 17))) for v in a2)
            base1 = tuple(v * 17 for v in q1)
            base2 = tuple(v * 17 for v in q2)

            for t1 in range(8):
                for t2 in range(8):
                    err = 0
                    sel = {}
                    for cells, base, tbl in ((group, base1, t1), (other, base2, t2)):
                        for x, y in cells:
                            target = pixels[y][x]
                            bi, be = 0, None
                            for mi in range(4):
                                m = MODIFIERS[tbl][mi]
                                cand = tuple(clamp(c + m) for c in base)
                                e = sum((cand[k] - target[k]) ** 2 for k in range(3))
                                if be is None or e < be:
                                    bi, be = mi, e
                            sel[(x, y)] = bi
                            err += be
                    if best is None or err < best[0]:
                        best = (err, flip, q1, q2, t1, t2, dict(sel))

    _, flip, q1, q2, t1, t2, sel = best
    hi = (q1[0] << 28) | (q2[0] << 24) | (q1[1] << 20) | (q2[1] << 16) \
        | (q1[2] << 12) | (q2[2] << 8) | (t1 << 5) | (t2 << 2) | (0 << 1) | flip
    lo = 0
    for i in range(16):
        x, y = i // 4, i % 4
        mi = sel[(x, y)]
        lo |= ((mi >> 1) & 1) << (i + 16)
        lo |= (mi & 1) << i
    raw = hi.to_bytes(4, "big") + lo.to_bytes(4, "big")
    return raw[::-1]


# --------------------------------------------------------------------------
# whole-image
# --------------------------------------------------------------------------
def decode(data: bytes) -> Image.Image:
    width, height, fmt, _ = read_header(data)
    payload = data[: len(data) - FOOTER]
    sw, sh = pow2(width), pow2(height)

    if fmt == FMT_ETC1:
        img = Image.new("RGB", (width, height))
        p = img.load()
        blocks_w = sw // 4
        for by in range(sh // 4):
            for bx in range(blocks_w):
                off = block_index(bx, by, blocks_w) * 8
                if off + 8 > len(payload):
                    continue
                blk = etc1_decode_block(payload[off:off + 8])
                for yy in range(4):
                    for xx in range(4):
                        X, Y = bx * 4 + xx, by * 4 + yy
                        if X < width and Y < height:
                            p[X, Y] = blk[yy][xx]
        return img
    raise SystemExit(f"decode not implemented for format {fmt} (only ETC1/10 so far)")


def encode(original: bytes, image: Image.Image) -> bytes:
    width, height, fmt, _ = read_header(original)
    if fmt != FMT_ETC1:
        raise SystemExit(f"encode not implemented for format {fmt}")
    if image.size != (width, height):
        raise SystemExit(f"image must be {width}x{height}, got {image.size}")
    image = image.convert("RGB")
    src = image.load()
    sw, sh = pow2(width), pow2(height)
    payload = bytearray(len(original) - FOOTER)
    blocks_w = sw // 4
    for by in range(sh // 4):
        for bx in range(blocks_w):
            cells = [[(0, 0, 0)] * 4 for _ in range(4)]
            for yy in range(4):
                for xx in range(4):
                    X, Y = bx * 4 + xx, by * 4 + yy
                    cells[yy][xx] = src[X, Y] if (X < width and Y < height) else (0, 0, 0)
            off = block_index(bx, by, blocks_w) * 8
            if off + 8 <= len(payload):
                payload[off:off + 8] = etc1_encode_block(cells)
    return bytes(payload) + original[len(original) - FOOTER:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("info", "verify"):
        s = sub.add_parser(name)
        s.add_argument("bclim", type=Path)
    s = sub.add_parser("decode"); s.add_argument("bclim", type=Path); s.add_argument("png", type=Path)
    s = sub.add_parser("encode")
    s.add_argument("bclim", type=Path); s.add_argument("png", type=Path); s.add_argument("out", type=Path)
    args = ap.parse_args()

    data = args.bclim.read_bytes()
    width, height, fmt, image_size = read_header(data)

    if args.cmd == "info":
        sw, sh = pow2(width), pow2(height)
        payload = len(data) - FOOTER
        print(f"{args.bclim.name}: {width}x{height} fmt={fmt} image_size={image_size} "
              f"payload={payload} padded={sw}x{sh} bpp={payload * 8 / (sw * sh):.2f}")
        return 0

    if args.cmd == "decode":
        decode(data).save(args.png)
        print(f"wrote {args.png}")
        return 0

    if args.cmd == "encode":
        out = encode(data, Image.open(args.png))
        if len(out) != len(data):
            raise SystemExit(f"size changed: {len(data)} -> {len(out)}")
        args.out.write_bytes(out)
        print(f"wrote {args.out} ({len(out)} bytes, unchanged)")
        return 0

    if args.cmd == "verify":
        # round-trip: decode -> encode -> decode, report pixel drift
        first = decode(data)
        again = decode(encode(data, first))
        diff = sum(1 for y in range(height) for x in range(width)
                   if first.load()[x, y] != again.load()[x, y])
        total = width * height
        print(f"round-trip differing pixels: {diff}/{total} ({diff / total:.2%})")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
