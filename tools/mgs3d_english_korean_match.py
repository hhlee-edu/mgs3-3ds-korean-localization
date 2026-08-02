#!/usr/bin/env python3
"""Match English-release game strings to the existing English/Korean script alignment."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, render_bytes  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402


WORDS = re.compile(r"[a-z0-9]+")


def decode_western(raw: bytes) -> str:
    """Decode observed Western text bytes while treating layout controls as spaces."""
    pieces: list[str] = []
    cursor = 0
    while cursor < len(raw) and raw[cursor]:
        value = raw[cursor]
        if value == 0x0A:
            pieces.append(" ")
            cursor += 1
        elif value == 0x80 and cursor + 1 < len(raw) and raw[cursor + 1] == 0x7C:
            pieces.append(" ")
            cursor += 2
        elif 0x20 <= value <= 0x7E:
            pieces.append(chr(value))
            cursor += 1
        elif value == 0x1F and cursor + 1 < len(raw):
            # Western accent/extended-character escape. It is not expected in
            # English type-1 text, but retaining an explicit marker prevents a
            # false exact match if one occurs.
            pieces.append(f" <1f{raw[cursor + 1]:02x}> ")
            cursor += 2
        else:
            pieces.append(" ")
            cursor += 1
    return "".join(pieces).strip()


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return " ".join(WORDS.findall(text))


def alignment_index(path: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = normalized(row.get("english", ""))
            if key and row.get("korean", "").strip():
                result[key].append(row)
    return result


def game_rows(kind: str, source: Path):
    data = source.read_bytes()
    if kind == "codec":
        for gcx, record in enumerate(parse_codec(data)):
            for resource, item in enumerate(record.resources()):
                if item.is_script:
                    continue
                english = decode_western(item.data)
                if english:
                    yield {
                        "container": kind, "gcx": gcx, "resource": resource,
                        "record": "", "entry": "", "entry_type": "", "offset": "",
                        "raw_text": render_bytes(item.data), "english": english,
                    }
    else:
        for record in parse_records(data)[1]:
            for entry, subtitle in enumerate(record.subtitles):
                if subtitle.entry_type != 1:
                    continue
                yield {
                    "container": kind, "gcx": "", "resource": "",
                    "record": record.index, "entry": entry,
                    "entry_type": subtitle.entry_type, "offset": subtitle.offset,
                    "raw_text": render_bytes(subtitle.raw),
                    "english": decode_western(subtitle.raw),
                }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("codec", "movie", "demo"))
    parser.add_argument("source", type=Path)
    parser.add_argument("alignment", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    index = alignment_index(args.alignment)
    fields = [
        "accept", "container", "gcx", "resource", "record", "entry",
        "entry_type", "offset", "raw_text", "english", "korean",
        "alignment_confidence", "english_sequence", "korean_sequence",
        "match_status", "candidate_count",
    ]
    rows = []
    scanned = matched = unambiguous = 0
    for game in game_rows(args.kind, args.source):
        scanned += 1
        candidates = index.get(normalized(str(game["english"])), [])
        if not candidates:
            continue
        matched += 1
        korean = {row["korean"].strip() for row in candidates if row["korean"].strip()}
        unique = len(korean) == 1
        if unique:
            unambiguous += 1
        first = candidates[0]
        rows.append({
            "accept": "",
            **game,
            "korean": next(iter(korean)) if unique else "",
            "alignment_confidence": first.get("confidence", ""),
            "english_sequence": first.get("english_sequence", ""),
            "korean_sequence": first.get("korean_sequence", ""),
            "match_status": "exact-unique-korean" if unique else "exact-ambiguous-korean",
            "candidate_count": len(candidates),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"{args.kind}: scanned={scanned}, exact_matches={matched}, "
        f"unique_korean={unambiguous}, output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
