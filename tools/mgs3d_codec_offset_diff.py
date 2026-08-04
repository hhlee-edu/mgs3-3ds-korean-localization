#!/usr/bin/env python3
"""Verify a rebuilt codec.dat preserves every GCX record's start offset and size.

The absolute project rule is: total file size, record count, and every
record's (source_offset, len(raw)) must be byte-identical before and after
a rebuild. Internal string/font/procedure boundaries *within* a record may
move. This is a standalone re-check independent of build-korean's own
internal assertion, for use after any codec.dat rebuild.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, CodecError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("rebuilt", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    original_bytes = args.original.read_bytes()
    rebuilt_bytes = args.rebuilt.read_bytes()

    result = {
        "original_size": len(original_bytes),
        "rebuilt_size": len(rebuilt_bytes),
        "file_size_match": len(original_bytes) == len(rebuilt_bytes),
    }

    try:
        original_records = parse_codec(original_bytes)
        result["original_parse_ok"] = True
    except CodecError as exc:
        result["original_parse_ok"] = False
        result["original_parse_error"] = str(exc)
        original_records = []

    try:
        rebuilt_records = parse_codec(rebuilt_bytes)
        result["rebuilt_parse_ok"] = True
    except CodecError as exc:
        result["rebuilt_parse_ok"] = False
        result["rebuilt_parse_error"] = str(exc)
        rebuilt_records = []

    result["record_count_match"] = len(original_records) == len(rebuilt_records)
    mismatches = []
    changed_gcx = []
    if result["record_count_match"]:
        for index, (orig, built) in enumerate(zip(original_records, rebuilt_records)):
            if orig.source_offset != built.source_offset or len(orig.raw) != len(built.raw):
                mismatches.append({
                    "gcx": index,
                    "original_offset": orig.source_offset, "rebuilt_offset": built.source_offset,
                    "original_len": len(orig.raw), "rebuilt_len": len(built.raw),
                })
            elif orig.raw != built.raw:
                changed_gcx.append(index)

    result["offset_or_size_mismatches"] = mismatches
    result["changed_gcx_count"] = len(changed_gcx)
    result["changed_gcx"] = changed_gcx
    result["all_offsets_and_sizes_match"] = not mismatches
    result["overall_pass"] = (
        result["file_size_match"] and result["original_parse_ok"] and result["rebuilt_parse_ok"]
        and result["record_count_match"] and result["all_offsets_and_sizes_match"]
    )

    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in result.items() if k != "offset_or_size_mismatches"},
                      ensure_ascii=False, indent=2))
    if mismatches:
        print(f"MISMATCHES: {len(mismatches)} (first 10 below)")
        for item in mismatches[:10]:
            print(" ", item)
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
