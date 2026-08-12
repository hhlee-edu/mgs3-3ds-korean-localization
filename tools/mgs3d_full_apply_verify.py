#!/usr/bin/env python3
"""Verify full movie/demo or codec Korean build content, not only structure."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from mgs3d_codec_tool import parse_codec, parse_rendered
from mgs3d_gcx_font_tool import validate_codec_translation
from mgs3d_movie_tool import (encode_translation, load_static_character_map,
                              parse_records, wrap_like_source)


def verify_media(args: argparse.Namespace) -> None:
    _, source, _ = parse_records(args.source.read_bytes())
    _, built, _ = parse_records(args.built.read_bytes())
    sidecar = json.loads(args.built.with_suffix(args.built.suffix + ".hangul.json").read_text(encoding="utf-8"))
    static = load_static_character_map(args.static_allocation)
    wanted = {}
    with args.translation.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("accept", "").lower() in {"yes", "y", "1", "true", "ok", "o"}:
                wanted[(int(row["record"]), int(row["entry"]))] = row["korean"]
    failures = []
    for (record, entry), text in wanted.items():
        local = {char: bytes.fromhex(token) for char, token in
                 sidecar.get("allocations", {}).get(str(record), {}).items()}
        expected = encode_translation(wrap_like_source(text, source[record].subtitles[entry].raw),
                                      static | local)
        actual = built[record].subtitles[entry].raw
        if actual != expected:
            failures.append((record, entry))
    if failures:
        raise SystemExit(f"media verification failed: {failures[:10]}")
    print(f"media verified: {len(wanted)}/{len(wanted)} translations")


def verify_codec(args: argparse.Namespace) -> None:
    records = parse_codec(args.built.read_bytes())
    resources = [record.resources() for record in records]
    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    base, units = validate_codec_translation(document)
    sidecar = json.loads(args.built.with_suffix(args.built.suffix + ".hangul.json").read_text(encoding="utf-8"))
    failures = []
    checked = 0
    for unit in units:
        gcx, resource = int(unit["gcx"]), int(unit["resource"])
        local = {char: bytes.fromhex(token) for char, token in
                 sidecar.get("allocations", {}).get(str(gcx), {}).items()}
        text = str(unit["text"])
        expected = parse_rendered(text, base | local)
        actual = resources[gcx][resource].data
        expected_hangul = "".join(c for c in text if 0xAC00 <= ord(c) <= 0xD7A3)
        if not expected_hangul:
            continue
        checked += 1
        inverse = {token: char for char, token in (base | local).items()
                   if 0xAC00 <= ord(char) <= 0xD7A3}
        decoded = []
        cursor = 0
        while cursor < len(actual) and actual[cursor]:
            token = actual[cursor:cursor + 2]
            if token in inverse:
                decoded.append(inverse[token])
                cursor += 2
            else:
                cursor += 2 if actual[cursor] >= 0x80 and cursor + 1 < len(actual) else 1
        actual_hangul = "".join(decoded)
        # Relocation can legitimately adjust embedded script offsets. For
        # translated dialogue, verify the complete Hangul sequence instead.
        if actual_hangul != expected_hangul:
            failures.append((gcx, resource))
    if failures:
        raise SystemExit(f"codec verification failed: {failures[:10]}")
    print(f"codec verified: {checked}/{checked} Hangul translation units "
          f"({len(units)} total selected resources)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    media = commands.add_parser("media")
    media.add_argument("source", type=Path)
    media.add_argument("built", type=Path)
    media.add_argument("translation", type=Path)
    media.add_argument("static_allocation", type=Path)
    media.set_defaults(function=verify_media)
    codec = commands.add_parser("codec")
    codec.add_argument("built", type=Path)
    codec.add_argument("translation", type=Path)
    codec.set_defaults(function=verify_codec)
    args = parser.parse_args()
    args.function(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
