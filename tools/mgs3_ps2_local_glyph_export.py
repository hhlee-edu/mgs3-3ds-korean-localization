#!/usr/bin/env python3
"""Export deduplicated PS2 stage-local Korean glyphs for offline OCR."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3_ps2_font_sheet import GLYPH_SIZE, decode_glyph  # noqa: E402
from mgs3d_codec_tool import CodecError, GcxRecord  # noqa: E402


def local_glyphs(record: GcxRecord) -> list[bytes]:
    start = record.block_start + record.font_data_offset
    end = record.block_start + record.proc_offset
    if end - start < 4:
        return []
    size = struct.unpack_from("<I", record.raw, start)[0]
    if size != end - start - 4 or size % GLYPH_SIZE:
        return []
    payload = record.raw[start + 4:end]
    return [payload[pos:pos + GLYPH_SIZE]
            for pos in range(0, len(payload), GLYPH_SIZE)]


def export(stages: Path, output: Path, scale: int = 10) -> dict[str, object]:
    identities: dict[str, dict[str, object]] = {}
    gcx_count = reference_count = 0
    for path in sorted(stages.rglob("*.02")):
        try:
            record = GcxRecord(path.read_bytes())
        except (CodecError, IndexError, struct.error):
            continue
        glyphs = local_glyphs(record)
        if not glyphs:
            continue
        gcx_count += 1
        reference_count += len(glyphs)
        for index, raw in enumerate(glyphs):
            digest = hashlib.sha256(raw).hexdigest()
            row = identities.setdefault(digest, {
                "sha256": digest,
                "raw": raw,
                "occurrences": [],
            })
            row["occurrences"].append({
                "stage": path.parent.name,
                "gcx": path.name,
                "local_index": index,
            })

    image_dir = output / "glyphs"
    image_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for ordinal, (digest, row) in enumerate(sorted(identities.items())):
        raw = row.pop("raw")
        # Tesseract performs better with a large black glyph, a white margin,
        # and nearest-neighbour scaling that preserves the official bitmap.
        glyph = ImageOps.invert(decode_glyph(raw))
        glyph = glyph.resize((24 * scale, 24 * scale), Image.Resampling.NEAREST)
        glyph = ImageOps.expand(glyph, border=4 * scale, fill=255)
        filename = f"{ordinal:04d}_{digest[:12]}.png"
        glyph.save(image_dir / filename)
        rows.append({**row, "image": f"glyphs/{filename}"})

    manifest = {
        "source": str(stages),
        "gcx_with_local_fonts": gcx_count,
        "glyph_references": reference_count,
        "unique_glyphs": len(rows),
        "glyphs": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stages", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scale", type=int, default=10)
    args = parser.parse_args()
    result = export(args.stages, args.output, args.scale)
    print(json.dumps({key: result[key] for key in (
        "gcx_with_local_fonts", "glyph_references", "unique_glyphs")},
        ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
