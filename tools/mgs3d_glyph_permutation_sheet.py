#!/usr/bin/env python3
"""Render decoder permutation sheets for existing and generated glyph pages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_clean_glyph_baseline import page2_offset  # noqa: E402

GLYPH_BYTES = 64
SIDE = 16
SCALE = 5


def morton_index(x: int, y: int) -> int:
    value = 0
    for bit in range(4):
        value |= ((x >> bit) & 1) << (bit * 2)
        value |= ((y >> bit) & 1) << (bit * 2 + 1)
    return value


def pixel_number(x: int, y: int, layout: str) -> int:
    if layout == "linear":
        return y * SIDE + x
    if layout == "tile8":
        return (y // 8) * 128 + (x // 8) * 64 + (y % 8) * 8 + (x % 8)
    if layout == "morton":
        return morton_index(x, y)
    raise ValueError(layout)


def decode(raw: bytes, bit_order: str, layout: str, vflip: bool) -> Image.Image:
    if len(raw) != GLYPH_BYTES:
        raise ValueError("glyph must be 64 bytes")
    image = Image.new("L", (SIDE, SIDE), 255)
    palette = (255, 176, 80, 0)
    for y_out in range(SIDE):
        y = SIDE - 1 - y_out if vflip else y_out
        for x in range(SIDE):
            number = pixel_number(x, y, layout)
            byte = raw[number // 4]
            shift = (6 - 2 * (number % 4)) if bit_order == "msb" else 2 * (number % 4)
            image.putpixel((x, y_out), palette[(byte >> shift) & 3])
    return image


def samples(page: bytes, indices: list[int]) -> list[bytes]:
    return [page[index * GLYPH_BYTES:(index + 1) * GLYPH_BYTES] for index in indices]


def sheet(existing: list[bytes], korean: list[bytes], setting: dict[str, object], output: Path) -> None:
    margin, label_h, gap = 16, 34, 2
    cell = SIDE * SCALE
    width = margin * 2 + 16 * (cell + gap) - gap
    height = margin * 2 + label_h * 2 + cell * 2 + 18
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    title = f"{setting['id']}  {setting['bit_order']} / {setting['layout']} / vflip={setting['vflip']}"
    draw.text((margin, 5), title, fill="black")
    y1 = margin + label_h
    draw.text((margin, y1 - 18), "Existing page2: indices 0..15", fill="black")
    y2 = y1 + cell + label_h
    draw.text((margin, y2 - 18), "Generated Korean page: indices 0..15", fill="black")
    for row_y, glyphs in ((y1, existing), (y2, korean)):
        for index, raw in enumerate(glyphs):
            decoded = decode(raw, str(setting["bit_order"]), str(setting["layout"]), bool(setting["vflip"]))
            decoded = decoded.resize((cell, cell), Image.Resampling.NEAREST).convert("RGB")
            x = margin + index * (cell + gap)
            canvas.paste(decoded, (x, row_y))
            draw.rectangle((x, row_y, x + cell - 1, row_y + cell - 1), outline="#999999")
    canvas.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcx", type=Path, default=ROOT / "originals/3ds_pristine/romfs/stage/title/scenerio.gcx")
    parser.add_argument("--korean-page", type=Path, default=ROOT / "experiments/global_korean_page_build_2026-08-12/korean_page_full.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "experiments/2026-08-13-clean-glyph-baseline")
    args = parser.parse_args()
    data = args.gcx.read_bytes()
    page2 = page2_offset(data)
    existing_page = data[page2:page2 + 16 * GLYPH_BYTES]
    korean_page = args.korean_page.read_bytes()
    if len(existing_page) != 16 * GLYPH_BYTES:
        raise ValueError("existing page2 sample is truncated")
    if len(korean_page) < 16 * GLYPH_BYTES:
        raise ValueError("Korean page is truncated")
    settings = []
    number = 1
    for layout in ("linear", "tile8", "morton"):
        for bit_order in ("msb", "lsb"):
            settings.append({"id": f"permutation-{number:03d}", "layout": layout,
                             "bit_order": bit_order, "vflip": False})
            number += 1
    for bit_order in ("msb", "lsb"):
        settings.append({"id": f"permutation-{number:03d}", "layout": "linear",
                         "bit_order": bit_order, "vflip": True})
        number += 1
    args.out.mkdir(parents=True, exist_ok=True)
    for setting in settings:
        sheet(samples(existing_page, list(range(16))), samples(korean_page, list(range(16))),
              setting, args.out / f"{setting['id']}.png")
    rendered = [Image.open(args.out / f"{setting['id']}.png").convert("RGB") for setting in settings]
    contact = Image.new("RGB", (max(image.width for image in rendered), sum(image.height for image in rendered)), "white")
    y = 0
    for image in rendered:
        contact.paste(image, (0, y))
        y += image.height
    contact.save(args.out / "permutation-contact-sheet.png")
    metadata = {
        "status": "awaiting-user-selection",
        "existing_source": str(args.gcx.resolve()),
        "existing_page2_file_offset": page2,
        "existing_indices": list(range(16)),
        "korean_source": str(args.korean_page.resolve()),
        "korean_indices": list(range(16)),
        "settings": settings,
    }
    (args.out / "glyph-permutation-index.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated={len(settings)} page2=0x{page2:X} out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
