#!/usr/bin/env python3
"""Render OCR/font-consensus glyph candidates beside original MGS3D bitmaps."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("ocr", type=Path)
    parser.add_argument("font_candidates", type=Path)
    parser.add_argument("tiles", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--confidence", type=float, default=80)
    parser.add_argument("--glyph-map", type=Path,
                        help="exclude hashes already present in this confirmed map")
    parser.add_argument("--font", type=Path,
                        default=Path(r"C:\Windows\Fonts\msgothic.ttc"))
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    ocr = {row["glyph_sha256"]: row for row in
           json.loads(args.ocr.read_text(encoding="utf-8"))["rows"]}
    font_rows = {row["glyph_sha256"]: row for row in
                 json.loads(args.font_candidates.read_text(encoding="utf-8"))["rows"]}
    confirmed = set()
    if args.glyph_map:
        confirmed = set(json.loads(args.glyph_map.read_text(encoding="utf-8"))["entries"])
    rows = []
    for item in catalog["glyphs"]:
        digest = item["glyph_sha256"]
        if digest in confirmed:
            continue
        ocr_row = ocr[digest]
        character = unicodedata.normalize("NFKC", ocr_row["candidate"])
        choices = [entry["character"] for entry in font_rows[digest]["candidates"]]
        if ocr_row["confidence"] >= args.confidence and character in choices:
            rows.append({**item, "character": character,
                         "confidence": ocr_row["confidence"],
                         "font_rank": choices.index(character) + 1})
    rows.sort(key=lambda row: (-row["occurrences"], row["glyph_sha256"]))
    rows = rows[args.start:args.start + args.count]

    columns, card_width, card_height = 5, 190, 116
    sheet = Image.new("RGB", (columns * card_width,
                              ((len(rows) + columns - 1) // columns) * card_height), "white")
    draw = ImageDraw.Draw(sheet)
    jp_font = ImageFont.truetype(str(args.font), 52)
    label_font = ImageFont.truetype(str(args.font), 13)
    for number, row in enumerate(rows):
        x, y = (number % columns) * card_width, (number // columns) * card_height
        filename = f"{row['sheet_index']:04d}_{row['glyph_sha256']}.png"
        original = Image.open(args.tiles / filename).convert("L").crop((16, 16, 80, 80))
        sheet.paste(Image.merge("RGB", (original, original, original)), (x + 4, y + 4))
        draw.text((x + 78, y + 5), row["character"], font=jp_font, fill="black")
        draw.text((x + 4, y + 72),
                  f"#{args.start + number} idx={row['sheet_index']} n={row['occurrences']}",
                  font=label_font, fill="black")
        draw.text((x + 4, y + 91),
                  f"OCR={row['confidence']:.0f} rank={row['font_rank']}",
                  font=label_font, fill="black")
        draw.rectangle((x, y, x + card_width - 1, y + card_height - 1), outline="#999")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"review sheet: {len(rows)} of {len(rows) + args.start} filtered rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
