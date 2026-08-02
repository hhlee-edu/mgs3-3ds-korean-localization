#!/usr/bin/env python3
"""Report the PS2 Korean CODEC.DAT font layout using the shared GCX parser."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, parse_codec  # noqa: E402


PS2_GLYPH_WIDTH = 24
PS2_GLYPH_HEIGHT = 24
PS2_GLYPH_BITS_PER_PIXEL = 2
PS2_GLYPH_SIZE = PS2_GLYPH_WIDTH * PS2_GLYPH_HEIGHT * PS2_GLYPH_BITS_PER_PIXEL // 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    raw = args.codec.read_bytes()
    records = parse_codec(raw)
    rows: list[dict[str, object]] = []
    histogram: Counter[int] = Counter()
    incompatible: list[dict[str, object]] = []
    populated = 0
    total_glyphs = 0

    for index, record in enumerate(records):
        start = record.block_start + record.font_data_offset
        end = record.block_start + record.proc_offset
        section_size = end - start
        payload_size = struct.unpack_from("<I", record.raw, start)[0] if section_size > 4 else 0
        valid = section_size <= 4 or payload_size == section_size - 4
        glyph_count = 0
        if valid and payload_size:
            valid = payload_size % PS2_GLYPH_SIZE == 0
            if valid:
                glyph_count = payload_size // PS2_GLYPH_SIZE
                populated += 1
                total_glyphs += glyph_count
                histogram[glyph_count] += 1
        item = {
            "gcx": index,
            "source_offset": record.source_offset,
            "section_size": section_size,
            "payload_size": payload_size,
            "glyph_size": PS2_GLYPH_SIZE,
            "glyph_count": glyph_count,
            "valid_ps2_font_region": valid,
        }
        if valid:
            rows.append(item)
        else:
            incompatible.append(item)

    document = {
        "format": "mgs3-ps2-korean-codec-font-report-v1",
        "source": str(args.codec.resolve()),
        "source_size": len(raw),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": len(records),
        "resource_count": sum(len(record.resources()) for record in records),
        "ps2_glyph_layout": {
            "width": PS2_GLYPH_WIDTH,
            "height": PS2_GLYPH_HEIGHT,
            "bits_per_pixel": PS2_GLYPH_BITS_PER_PIXEL,
            "bytes_per_glyph": PS2_GLYPH_SIZE,
        },
        "summary": {
            "compatible_records": len(rows),
            "incompatible_records": len(incompatible),
            "populated_records": populated,
            "total_glyphs": total_glyphs,
            "maximum_glyphs_in_record": max((int(row["glyph_count"]) for row in rows), default=0),
            "glyph_count_histogram": {str(k): v for k, v in sorted(histogram.items())},
        },
        "records": rows,
        "incompatible_records": incompatible,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(document["summary"], ensure_ascii=False))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CodecError as exc:
        raise SystemExit(str(exc)) from exc
