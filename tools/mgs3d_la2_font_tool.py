#!/usr/bin/env python3
"""Inspect the raw 16x16 2-bpp glyph array stored in ui/font.la2."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from mgs3d_gcx_font_tool import GLYPH_SIZE, decode_glyph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=512)
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--layout", choices=("linear", "tiled8"), default="linear")
    args = parser.parse_args()
    data = args.font.read_bytes()
    if len(data) % GLYPH_SIZE:
        raise SystemExit("font.la2 is not a whole number of 64-byte glyphs")
    total = len(data) // GLYPH_SIZE
    end = min(total, args.start + args.count)
    count = max(0, end - args.start)
    rows = (count + args.columns - 1) // args.columns
    sheet = Image.new("L", (args.columns * 16, rows * 16))
    for output_index, glyph_index in enumerate(range(args.start, end)):
        raw = data[glyph_index * GLYPH_SIZE:(glyph_index + 1) * GLYPH_SIZE]
        sheet.paste(decode_glyph(raw, args.layout),
                    ((output_index % args.columns) * 16, (output_index // args.columns) * 16))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"extracted slots {args.start}..{end - 1} of {total} using {args.layout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
