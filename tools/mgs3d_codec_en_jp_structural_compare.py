#!/usr/bin/env python3
"""Read-only structural comparison of the English and Japanese SKU codec.dat
files, GCX-index by GCX-index. Never assumes semantic correspondence between
the same index in the two files -- this is a structural size/layout
comparison only. Does not modify either input file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_gcx_font_tool import GLYPH_SIZE, font_region  # noqa: E402


FORMAT = "mgs3d-codec-en-jp-structural-compare-v1"
CSV_FIELDS = [
    "gcx", "en_offset", "jp_offset", "en_record_size", "jp_record_size",
    "record_size_delta", "en_resource_count", "jp_resource_count",
    "en_font_slots", "jp_font_slots", "font_slot_delta",
    "en_font_bytes", "jp_font_bytes", "font_bytes_delta",
    "en_string_blob_size", "jp_string_blob_size", "string_blob_delta",
    "en_font_data_offset", "jp_font_data_offset",
    "en_proc_offset", "jp_proc_offset",
    "en_script_resource_count", "jp_script_resource_count",
    "en_display_resource_count", "jp_display_resource_count",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_row(gcx: int, en_record, jp_record) -> dict[str, object]:
    en_slots = jp_slots = 0
    en_resources = jp_resources = []
    en_script = en_display = jp_script = jp_display = 0
    en_string_blob = jp_string_blob = 0

    if en_record is not None:
        _, en_slots = font_region(en_record)
        en_resources = en_record.resources()
        en_script = sum(1 for r in en_resources if r.is_script)
        en_display = len(en_resources) - en_script
        en_string_blob = en_record.font_data_offset - en_record.string_resources_offset
    if jp_record is not None:
        _, jp_slots = font_region(jp_record)
        jp_resources = jp_record.resources()
        jp_script = sum(1 for r in jp_resources if r.is_script)
        jp_display = len(jp_resources) - jp_script
        jp_string_blob = jp_record.font_data_offset - jp_record.string_resources_offset

    en_size = len(en_record.raw) if en_record is not None else None
    jp_size = len(jp_record.raw) if jp_record is not None else None

    return {
        "gcx": gcx,
        "en_offset": en_record.source_offset if en_record is not None else None,
        "jp_offset": jp_record.source_offset if jp_record is not None else None,
        "en_record_size": en_size,
        "jp_record_size": jp_size,
        "record_size_delta": (jp_size - en_size) if None not in (en_size, jp_size) else None,
        "en_resource_count": len(en_resources) if en_record is not None else None,
        "jp_resource_count": len(jp_resources) if jp_record is not None else None,
        "en_font_slots": en_slots,
        "jp_font_slots": jp_slots,
        "font_slot_delta": jp_slots - en_slots,
        "en_font_bytes": en_slots * GLYPH_SIZE,
        "jp_font_bytes": jp_slots * GLYPH_SIZE,
        "font_bytes_delta": (jp_slots - en_slots) * GLYPH_SIZE,
        "en_string_blob_size": en_string_blob if en_record is not None else None,
        "jp_string_blob_size": jp_string_blob if jp_record is not None else None,
        "string_blob_delta": (
            (jp_string_blob - en_string_blob) if en_record is not None and jp_record is not None else None
        ),
        "en_font_data_offset": en_record.font_data_offset if en_record is not None else None,
        "jp_font_data_offset": jp_record.font_data_offset if jp_record is not None else None,
        "en_proc_offset": en_record.proc_offset if en_record is not None else None,
        "jp_proc_offset": jp_record.proc_offset if jp_record is not None else None,
        "en_script_resource_count": en_script if en_record is not None else None,
        "jp_script_resource_count": jp_script if jp_record is not None else None,
        "en_display_resource_count": en_display if en_record is not None else None,
        "jp_display_resource_count": jp_display if jp_record is not None else None,
    }


def build_comparison(en_path: Path, jp_path: Path) -> dict[str, object]:
    en_data = en_path.read_bytes()
    jp_data = jp_path.read_bytes()
    en_records = parse_codec(en_data)
    jp_records = parse_codec(jp_data)

    count = max(len(en_records), len(jp_records))
    rows = []
    for gcx in range(count):
        en_record = en_records[gcx] if gcx < len(en_records) else None
        jp_record = jp_records[gcx] if gcx < len(jp_records) else None
        rows.append(record_row(gcx, en_record, jp_record))

    def totals(records) -> dict[str, int]:
        font_bearing = 0
        total_slots = 0
        total_resources = 0
        for record in records:
            _, slots = font_region(record)
            if slots:
                font_bearing += 1
            total_slots += slots
            total_resources += len(record.resources())
        return {
            "record_count": len(records),
            "resource_total_count": total_resources,
            "font_bearing_gcx_count": font_bearing,
            "total_font_slots": total_slots,
            "total_font_bytes": total_slots * GLYPH_SIZE,
        }

    summary = {
        "en": {
            "path": str(en_path), "file_size": len(en_data), "sha256": sha256(en_data),
            **totals(en_records),
        },
        "jp": {
            "path": str(jp_path), "file_size": len(jp_data), "sha256": sha256(jp_data),
            **totals(jp_records),
        },
    }
    return {"format": FORMAT, "summary": summary, "records": rows}


def write_csv(document: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in document["records"]:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("en_codec", type=Path)
    parser.add_argument("jp_codec", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()

    document = build_comparison(args.en_codec, args.jp_codec)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.csv:
        write_csv(document, args.csv)

    for label in ("en", "jp"):
        print(f"{label.upper()}: {json.dumps(document['summary'][label])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
