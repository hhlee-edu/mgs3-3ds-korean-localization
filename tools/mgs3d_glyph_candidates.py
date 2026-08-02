#!/usr/bin/env python3
"""Generate non-authoritative Unicode candidates for MGS3D bitmap glyph review."""

from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_gcx_font_tool import decode_glyph  # noqa: E402


FORMAT = "mgs3d-glyph-candidates-v1"


def jis_level1_characters() -> list[str]:
    result = []
    seen = set()
    # CP932's 0x889F..0x9872 region is the JIS X 0208 level-1 Kanji block.
    for value in range(0x889F, 0x9873):
        raw = value.to_bytes(2, "big")
        if raw[1] == 0x7F:
            continue
        try:
            character = raw.decode("cp932")
        except UnicodeDecodeError:
            continue
        if len(character) == 1 and character not in seen:
            seen.add(character)
            result.append(character)
    return result


def image_mask(image: Image.Image, threshold: int) -> int:
    result = 0
    for index, value in enumerate(image.convert("L").getdata()):
        if value >= threshold:
            result |= 1 << index
    return result


def render(character: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    image = Image.new("L", (16, 16), 0)
    draw = ImageDraw.Draw(image)
    box = draw.textbbox((0, 0), character, font=font)
    x = (16 - (box[2] - box[0])) // 2 - box[0]
    y = (16 - (box[3] - box[1])) // 2 - box[1]
    draw.text((x, y), character, font=font, fill=255)
    return image


def templates(characters: list[str], font_path: Path, sizes: list[int]):
    result = []
    for character in characters:
        variants = set()
        for size in sizes:
            image = render(character, ImageFont.truetype(str(font_path), size))
            for threshold in (64, 128):
                mask = image_mask(image, threshold)
                if mask:
                    variants.add(mask)
        result.append((character, [(mask, mask.bit_count()) for mask in variants]))
    return result


def score(target: int, target_count: int, variants) -> float:
    return max((target & mask).bit_count() /
               math.sqrt(max(1, target_count * count)) for mask, count in variants)


def generate(catalog: dict[str, object], font_path: Path, sizes: list[int], top: int):
    characters = jis_level1_characters()
    candidates = templates(characters, font_path, sizes)
    rows = []
    for item in catalog["glyphs"]:
        image = decode_glyph(bytes.fromhex(item["raw_hex"]), "linear")
        target_masks = [image_mask(image, threshold) for threshold in (64, 128)]
        scored = []
        for character, variants in candidates:
            value = max(score(mask, mask.bit_count(), variants) for mask in target_masks)
            scored.append((value, character))
        best = heapq.nlargest(top, scored)
        rows.append({"glyph_sha256": item["glyph_sha256"],
                     "sheet_index": item.get("sheet_index"),
                     "occurrences": item["occurrences"],
                     "candidates": [{"character": character, "score": round(value, 6)}
                                    for value, character in best],
                     "disposition": "unresolved-needs-review"})
    return {"format": FORMAT, "catalog_format": catalog["format"],
            "font": str(font_path), "font_sizes": sizes,
            "candidate_repertoire": "CP932 JIS-X-0208 level-1 Kanji",
            "candidate_character_count": len(characters),
            "note": "Similarity is candidate evidence only; no row is automatically confirmed.",
            "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path,
                        default=Path(r"C:\Windows\Fonts\msgothic.ttc"))
    parser.add_argument("--size", type=int, action="append", default=[])
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        if catalog.get("format") != "mgs3d-referenced-glyph-catalog-v1":
            raise ValueError("unsupported glyph catalog")
        document = generate(catalog, args.font, args.size or [15, 16, 17], args.top)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"glyph candidates: {len(document['rows'])} glyphs against "
              f"{document['candidate_character_count']} characters")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
