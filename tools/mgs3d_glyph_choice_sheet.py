#!/usr/bin/env python3
"""Render unresolved MGS3D glyphs beside their five font-similarity choices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("font_candidates", type=Path)
    parser.add_argument("ocr_candidates", type=Path)
    parser.add_argument("tiles", type=Path)
    parser.add_argument("glyph_map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--font", type=Path,
                        default=Path(r"C:\Windows\Fonts\msgothic.ttc"))
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    font_rows = {row["glyph_sha256"]: row for row in
                 json.loads(args.font_candidates.read_text(encoding="utf-8"))["rows"]}
    ocr_rows = {row["glyph_sha256"]: row for row in
                json.loads(args.ocr_candidates.read_text(encoding="utf-8"))["rows"]}
    confirmed = set(json.loads(args.glyph_map.read_text(encoding="utf-8"))["entries"])
    rows = [item for item in catalog["glyphs"]
            if item["glyph_sha256"] not in confirmed]
    rows.sort(key=lambda row: (-row["occurrences"], row["glyph_sha256"]))
    total = len(rows)
    rows = rows[args.start:args.start + args.count]

    columns, card_width, card_height = 4, 260, 122
    sheet = Image.new("RGB", (columns * card_width,
                              ((len(rows) + columns - 1) // columns) * card_height), "white")
    draw = ImageDraw.Draw(sheet)
    jp_font = ImageFont.truetype(str(args.font), 36)
    label_font = ImageFont.truetype(str(args.font), 12)
    for number, row in enumerate(rows):
        x, y = (number % columns) * card_width, (number // columns) * card_height
        digest = row["glyph_sha256"]
        filename = f"{row['sheet_index']:04d}_{digest}.png"
        original = Image.open(args.tiles / filename).convert("L").crop((16, 16, 80, 80))
        sheet.paste(Image.merge("RGB", (original, original, original)), (x + 4, y + 4))
        choices = [entry["character"] for entry in font_rows[digest]["candidates"]]
        draw.text((x + 73, y + 2), " ".join(choices), font=jp_font, fill="black")
        ocr = ocr_rows[digest]
        draw.text((x + 4, y + 72),
                  f"#{args.start + number} idx={row['sheet_index']} n={row['occurrences']}",
                  font=label_font, fill="black")
        draw.text((x + 4, y + 91),
                  f"OCR={ocr['candidate']!r} conf={ocr['confidence']}",
                  font=label_font, fill="black")
        draw.rectangle((x, y, x + card_width - 1, y + card_height - 1), outline="#999")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"choice sheet: {len(rows)} rows at {args.start}, {total} unresolved glyphs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
