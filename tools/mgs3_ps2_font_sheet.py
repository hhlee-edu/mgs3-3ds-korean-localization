#!/usr/bin/env python3
"""Render the official PS2 Korean GCX 24x24 2-bpp local font."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, parse_codec  # noqa: E402


WIDTH = HEIGHT = 24
GLYPH_SIZE = WIDTH * HEIGHT // 4
LEVELS = (0, 85, 170, 255)


def decode_glyph(raw: bytes, lsb_first: bool = False) -> Image.Image:
    if len(raw) != GLYPH_SIZE:
        raise CodecError(f"PS2 glyph must be {GLYPH_SIZE} bytes")
    image = Image.new("L", (WIDTH, HEIGHT))
    pixels = image.load()
    for index in range(WIDTH * HEIGHT):
        shift = (index & 3) * 2 if lsb_first else 6 - (index & 3) * 2
        pixels[index % WIDTH, index // WIDTH] = LEVELS[(raw[index // 4] >> shift) & 3]
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("gcx", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lsb-first", action="store_true")
    parser.add_argument("--columns", type=int, default=16)
    args = parser.parse_args()
    record = parse_codec(args.codec.read_bytes())[args.gcx]
    start = record.block_start + record.font_data_offset
    end = record.block_start + record.proc_offset
    size = struct.unpack_from("<I", record.raw, start)[0]
    if size != end - start - 4 or size % GLYPH_SIZE:
        raise CodecError("record does not contain a valid PS2 24x24 2-bpp font")
    count = size // GLYPH_SIZE
    columns = min(args.columns, count)
    rows = (count + columns - 1) // columns
    sheet = Image.new("L", (columns * WIDTH, rows * HEIGHT))
    for index in range(count):
        off = start + 4 + index * GLYPH_SIZE
        sheet.paste(decode_glyph(record.raw[off:off + GLYPH_SIZE], args.lsb_first),
                    ((index % columns) * WIDTH, (index // columns) * HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"GCX {args.gcx}: {count} glyphs -> {args.output}")


if __name__ == "__main__":
    main()
