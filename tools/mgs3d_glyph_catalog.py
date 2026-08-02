#!/usr/bin/env python3
"""Catalog and deduplicate referenced MGS3D per-record bitmap glyphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_gcx_font_tool import GLYPH_SIZE, HEIGHT, WIDTH, decode_glyph, font_region  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402
from mgs3d_text_reassembler import custom_glyph_index, sha256, tokenize  # noqa: E402


FORMAT = "mgs3d-referenced-glyph-catalog-v1"


def add_reference(catalog, glyph: bytes, reference: dict[str, object], occurrences: int) -> None:
    key = hashlib.sha256(glyph).hexdigest()
    item = catalog.setdefault(key, {
        "glyph_sha256": key, "raw_hex": glyph.hex().upper(),
        "occurrences": 0, "reference_count": 0, "containers": set(),
        "references": [],
    })
    item["occurrences"] += occurrences
    item["reference_count"] += 1
    item["containers"].add(reference["container"])
    if len(item["references"]) < 12:
        item["references"].append({**reference, "occurrences": occurrences})


def codec_glyphs(path: Path, catalog) -> tuple[int, int]:
    referenced_slots = occurrences = 0
    for gcx, record in enumerate(parse_codec(path.read_bytes())):
        counts: Counter[int] = Counter()
        for resource in record.resources():
            if resource.is_script:
                continue
            end = resource.data.find(b"\0")
            text_raw = resource.data if end < 0 else resource.data[:end + 1]
            for token in tokenize(text_raw):
                index = custom_glyph_index(token.raw, 2)
                if index is not None:
                    counts[index] += 1
        start, available = font_region(record)
        for index, count in sorted(counts.items()):
            if index >= available:
                raise ValueError(f"GCX {gcx} references glyph {index}, only {available} available")
            glyph = record.raw[start + index * GLYPH_SIZE:start + (index + 1) * GLYPH_SIZE]
            add_reference(catalog, glyph, {"container": "codec", "gcx": gcx,
                                          "slot": index}, count)
            referenced_slots += 1
            occurrences += count
    return referenced_slots, occurrences


def subtitle_glyphs(path: Path, kind: str, catalog) -> tuple[int, int]:
    referenced_slots = occurrences = 0
    for record in parse_records(path.read_bytes())[1]:
        counts: Counter[int] = Counter()
        for subtitle in record.subtitles:
            for token in tokenize(subtitle.raw):
                index = custom_glyph_index(token.raw, 3)
                if index is not None:
                    counts[index] += 1
        available = len(record.font) // GLYPH_SIZE
        for index, count in sorted(counts.items()):
            if index >= available:
                raise ValueError(f"{kind} record {record.index} references glyph {index}, "
                                 f"only {available} available")
            glyph = record.font[index * GLYPH_SIZE:(index + 1) * GLYPH_SIZE]
            add_reference(catalog, glyph, {"container": kind, "record": record.index,
                                          "slot": index}, count)
            referenced_slots += 1
            occurrences += count
    return referenced_slots, occurrences


def build(sources: list[tuple[str, Path]]) -> dict[str, object]:
    catalog = {}
    source_rows = []
    for kind, path in sources:
        slots, occurrences = (codec_glyphs(path, catalog) if kind == "codec"
                              else subtitle_glyphs(path, kind, catalog))
        data = path.read_bytes()
        source_rows.append({"container": kind, "source": str(path),
                            "source_sha256": sha256(data),
                            "referenced_slots": slots,
                            "glyph_occurrences": occurrences})
    rows = []
    for key in sorted(catalog):
        item = catalog[key]
        item["containers"] = sorted(item["containers"])
        rows.append(item)
    return {"format": FORMAT, "sources": source_rows,
            "unique_glyph_bitmaps": len(rows), "glyphs": rows}


def write_sheet(document: dict[str, object], path: Path, columns: int = 32,
                tiles: Path | None = None) -> None:
    glyphs = document["glyphs"]
    rows = (len(glyphs) + columns - 1) // columns
    sheet = Image.new("L", (columns * WIDTH, rows * HEIGHT))
    for index, item in enumerate(glyphs):
        glyph = bytes.fromhex(item["raw_hex"])
        image = decode_glyph(glyph, "linear")
        sheet.paste(image,
                    ((index % columns) * WIDTH, (index // columns) * HEIGHT))
        item["sheet_index"] = index
        if tiles is not None:
            tiles.mkdir(parents=True, exist_ok=True)
            canvas = Image.new("L", (96, 96), 255)
            # OCR engines perform better with a quiet border and black strokes.
            enlarged = Image.eval(image.resize((64, 64), Image.Resampling.NEAREST),
                                  lambda value: 255 - value)
            canvas.paste(enlarged, (16, 16))
            canvas.save(tiles / f"{index:04d}_{item['glyph_sha256']}.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--codec", type=Path)
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--tiles", type=Path,
                        help="write padded, enlarged per-hash PNGs for OCR review")
    args = parser.parse_args()
    sources = [(kind, path) for kind, path in
               (("codec", args.codec), ("movie", args.movie), ("demo", args.demo)) if path]
    if not sources:
        parser.error("at least one source is required")
    try:
        document = build(sources)
        if args.sheet:
            write_sheet(document, args.sheet, tiles=args.tiles)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        cross = sum(len(item["containers"]) > 1 for item in document["glyphs"])
        print(f"glyph catalog: {document['unique_glyph_bitmaps']} unique bitmaps, "
              f"{cross} shared across containers")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
