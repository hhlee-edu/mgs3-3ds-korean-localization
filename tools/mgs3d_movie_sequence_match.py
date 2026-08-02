#!/usr/bin/env python3
"""Match consecutive English movie cards to whole bilingual transcript lines."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import render_bytes  # noqa: E402
from mgs3d_english_korean_match import decode_western, normalized  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402


def split_korean(text: str, weights: list[int]) -> list[str]:
    words = text.split()
    if len(weights) == 1:
        return [text.strip()]
    if not words:
        return [""] * len(weights)
    total = sum(max(1, x) for x in weights)
    boundaries = [0]
    used = 0
    for weight in weights[:-1]:
        used += max(1, weight)
        target = round(used / total * len(words))
        boundaries.append(max(boundaries[-1], min(len(words), target)))
    boundaries.append(len(words))
    return [" ".join(words[boundaries[i]:boundaries[i + 1]])
            for i in range(len(weights))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movie", type=Path)
    parser.add_argument("alignment", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-cards", type=int, default=8)
    parser.add_argument("--base-csv", type=Path,
                        help="accepted reviewed rows that override/add exact sequence matches")
    args = parser.parse_args()

    index = defaultdict(list)
    with args.alignment.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = normalized(row.get("english", ""))
            if key and row.get("korean", "").strip():
                index[key].append(row)
    cards = []
    for record in parse_records(args.movie.read_bytes())[1]:
        for entry, subtitle in enumerate(record.subtitles):
            if subtitle.entry_type == 1:
                english = decode_western(subtitle.raw)
                cards.append({"record": record.index, "entry": entry,
                              "offset": subtitle.offset, "raw_text": render_bytes(subtitle.raw),
                              "english": english})

    rows = []
    cursor = 0
    groups = 0
    while cursor < len(cards):
        found = None
        combined = ""
        for count in range(1, min(args.max_cards, len(cards) - cursor) + 1):
            combined += " " + cards[cursor + count - 1]["english"]
            candidates = index.get(normalized(combined), [])
            korean = {row["korean"].strip() for row in candidates if row["korean"].strip()}
            if len(korean) == 1:
                found = (count, next(iter(korean)), candidates[0])
        if not found:
            cursor += 1
            continue
        count, korean, source = found
        group = cards[cursor:cursor + count]
        pieces = split_korean(korean, [len(normalized(x["english"])) for x in group])
        groups += 1
        for card, piece in zip(group, pieces):
            rows.append({"accept": "yes", **card, "korean": piece,
                         "korean_full": korean, "sequence_cards": count,
                         "alignment_confidence": source.get("confidence", ""),
                         "english_sequence": source.get("english_sequence", ""),
                         "korean_sequence": source.get("korean_sequence", "")})
        cursor += count

    if args.base_csv:
        by_offset = {int(row["offset"]): row for row in rows}
        with args.base_csv.open(encoding="utf-8-sig", newline="") as stream:
            for base in csv.DictReader(stream):
                if base.get("accept", "").strip().lower() not in {"yes", "y", "1", "true"}:
                    continue
                offset = int(base["offset"])
                card = next((item for item in cards if item["offset"] == offset), None)
                if card is None:
                    continue
                by_offset[offset] = {
                    "accept": "yes", **card, "korean": base["korean"].strip(),
                    "korean_full": base["korean"].strip(), "sequence_cards": 1,
                    "alignment_confidence": "reviewed", "english_sequence": "",
                    "korean_sequence": "",
                }
        rows = [by_offset[offset] for offset in sorted(by_offset)]

    fields = ["accept", "record", "entry", "offset", "raw_text", "english", "korean",
              "korean_full", "sequence_cards", "alignment_confidence",
              "english_sequence", "korean_sequence"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"matched/merged {len(rows)}/{len(cards)} cards in {groups} exact sequence groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
