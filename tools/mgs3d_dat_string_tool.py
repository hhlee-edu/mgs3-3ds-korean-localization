#!/usr/bin/env python3
"""Heuristically extract aligned MGS text streams from demo.dat/movie.dat."""

from __future__ import annotations

import argparse
import csv
import json
import mmap
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import decode_mgs_preview, render_bytes  # noqa: E402


TEXT_STREAM = re.compile(
    rb"(?:(?:[\x09\x0a\x0d\x20-\x7e])|(?:[\x80-\x83\x90-\x93\xa0\xa3\xc0-\xc3][\x01-\xff])){8,}\x00"
)


def extract(path: Path, alignment: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for match in TEXT_STREAM.finditer(data):
            if match.start() % alignment:
                continue
            raw = match.group()
            cursor = encoded_pairs = units = 0
            while cursor < len(raw) - 1:
                if raw[cursor] >= 0x80:
                    encoded_pairs += 1
                    cursor += 2
                else:
                    cursor += 1
                units += 1
            if encoded_pairs < 3 or encoded_pairs / max(1, units) < 0.4:
                continue
            rows.append(
                {
                    "index": len(rows),
                    "offset": match.start(),
                    "size": len(raw),
                    "preview": decode_mgs_preview(raw),
                    "raw_text": render_bytes(raw),
                }
            )
    return rows


def command_extract(args: argparse.Namespace) -> None:
    rows = extract(args.dat, args.alignment)
    document = {
        "format": "mgs3d-dat-string-candidates-v1",
        "source": args.dat.name,
        "alignment": args.alignment,
        "candidate_count": len(rows),
        "candidates": rows,
    }
    args.output_json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"extracted {len(rows)} aligned text candidates from {args.dat}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dat", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--alignment", type=int, default=4)
    parser.set_defaults(function=command_extract)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
