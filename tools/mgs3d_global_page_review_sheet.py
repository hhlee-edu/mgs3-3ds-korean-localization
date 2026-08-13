#!/usr/bin/env python3
"""Render token-labelled review sheets for a global Korean glyph page."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent


def decode_glyph(data: bytes) -> Image.Image:
    if len(data) != 64:
        raise ValueError("glyph must be 64 bytes")
    image = Image.new("L", (16, 16))
    pixels = image.load()
    for index, value in enumerate(data):
        x = (index * 4) % 16
        y = (index * 4) // 16
        for shift in range(4):
            pixels[x + shift, y] = (value >> (6 - shift * 2) & 3) * 85
    return image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=Path,
                        default=ROOT / "glyph/pages/global_korean_page_v2/korean_page_full.bin")
    parser.add_argument("--map", dest="token_map", type=Path,
                        default=ROOT / "glyph/pages/global_korean_page_v2/korean_token_map_full.csv")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "glyph/validation/global_page_v2")
    args = parser.parse_args()
    page = args.page.read_bytes()
    with args.token_map.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    args.out.mkdir(parents=True, exist_ok=True)

    label_font = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 14)
    token_font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 12)
    columns, rows_per_sheet = 8, 8
    cell_w, cell_h = 112, 112
    per_sheet = columns * rows_per_sheet
    bitmap_owners: dict[str, list[str]] = defaultdict(list)

    for sheet_index, start in enumerate(range(0, len(rows), per_sheet), 1):
        subset = rows[start:start + per_sheet]
        sheet = Image.new("RGB", (columns * cell_w, rows_per_sheet * cell_h), "white")
        draw = ImageDraw.Draw(sheet)
        for local, row in enumerate(subset):
            index = int(row["index"])
            glyph = page[index * 64:(index + 1) * 64]
            digest = hashlib.sha256(glyph).hexdigest()
            bitmap_owners[digest].append(row["character"])
            enlarged = decode_glyph(glyph).resize((64, 64), Image.Resampling.NEAREST)
            x = local % columns * cell_w
            y = local // columns * cell_h
            draw.rectangle((x, y, x + cell_w - 1, y + cell_h - 1), outline="#b8c0c8")
            sheet.paste(enlarged, (x + 24, y + 5))
            draw.text((x + 7, y + 73), f"{row['character']}  {row['unicode']}", fill="black", font=label_font)
            draw.text((x + 7, y + 92), row["token"], fill="#334455", font=token_font)
        sheet.save(args.out / f"global-page-v2-{sheet_index:02d}.png")

    duplicate_groups = [characters for characters in bitmap_owners.values() if len(characters) > 1]
    authored = [page[index * 64:(index + 1) * 64] for index in range(len(rows))]
    report = {
        "format": "mgs3d-global-page-visual-review-v1",
        "status": "PASS" if all(any(glyph) for glyph in authored) else "FAIL",
        "glyph_count": len(rows),
        "sheet_count": (len(rows) + per_sheet - 1) // per_sheet,
        "nonzero_glyphs": sum(any(glyph) for glyph in authored),
        "unique_bitmap_count": len(bitmap_owners),
        "duplicate_bitmap_group_count": len(duplicate_groups),
        "duplicate_bitmap_groups": duplicate_groups,
        "decoder": "MSB-first, linear row-major, no vertical flip",
        "page_sha256": hashlib.sha256(page).hexdigest(),
    }
    (args.out / "review-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
