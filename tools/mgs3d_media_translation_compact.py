#!/usr/bin/env python3
"""First-pass fixed-budget compaction using English names/terms and shared glyphs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


GLOSSARY = [
    ("현자들의 유산", "Philosophers' Legacy"), ("현자의 유산", "Philosophers' Legacy"),
    ("그로즈니 그라드", "Groznyj Grad"), ("코브라 부대", "Cobra Unit"),
    ("버추어스 미션", "Virtuous Mission"), ("지면효과익선", "WIG"),
    ("더 소로우", "The Sorrow"), ("더 퓨리", "The Fury"),
    ("더 피어", "The Fear"), ("디 엔드", "The End"), ("더 페인", "The Pain"),
    ("더 보스", "The Boss"), ("스네이크", "Snake"), ("오셀롯", "Ocelot"),
    ("소콜로프", "Sokolov"), ("샤고호드", "Shagohod"), ("볼긴", "Volgin"),
    ("그라닌", "Granin"), ("라이코프", "Raikov"), ("흐루쇼프", "Khrushchev"),
    ("브레즈네프", "Brezhnev"), ("코시긴", "Kosygin"), ("아담스카", "Adamska"),
    ("파라메딕", "Para-Medic"), ("시긴트", "Sigint"), ("에바", "EVA"),
    ("조니", "Johnny"), ("잭", "Jack"), ("존", "John"),
    ("임무", "MISSION"), ("무전", "RADIO"), ("위장", "CAMO"),
    ("식량", "FOOD"), ("치료", "CURE"), ("아이템", "ITEM"),
]


def byte_size(text: str) -> int:
    return 1 + sum(1 if ord(char) < 0x80 else 2 for char in text)


def tidy(text: str) -> str:
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    for korean, english in GLOSSARY:
        text = text.replace(korean, english)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"([,(])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation", type=Path)
    parser.add_argument("inspect", type=Path)
    parser.add_argument("static_allocation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("review", type=Path)
    args = parser.parse_args()
    with args.inspect.open(encoding="utf-8-sig", newline="") as stream:
        capacities = {int(row["offset"]): int(row.get("fixed_capacity") or row["size"])
                      for row in csv.DictReader(stream) if row["entry_type"] == "1"}
    static = set(json.loads(args.static_allocation.read_text(encoding="utf-8-sig"))["characters"])
    with args.translation.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0])
    review = []
    fitted_before = fitted_after = 0
    for row in rows:
        original = row["korean"]
        compact = tidy(original)
        capacity = capacities[int(row["offset"])]
        fitted_before += byte_size(original) <= capacity
        fitted_after += byte_size(compact) <= capacity
        row["korean"] = compact
        if byte_size(compact) > capacity:
            hangul = {char for char in compact if 0xAC00 <= ord(char) <= 0xD7A3}
            review.append({"media": row["media"], "record": row["record"],
                           "entry": row["entry"], "offset": row["offset"],
                           "capacity_bytes": capacity, "current_bytes": byte_size(compact),
                           "deficit_bytes": byte_size(compact) - capacity,
                           "english": row["preview"], "source_korean": original,
                           "compact_korean": compact,
                           "nonshared_hangul": "".join(sorted(hangul - static)),
                           "user_korean": ""})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    review_fields = list(review[0]) if review else ["media", "record", "entry", "offset",
        "capacity_bytes", "current_bytes", "deficit_bytes", "english", "source_korean",
        "compact_korean", "nonshared_hangul", "user_korean"]
    with args.review.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=review_fields)
        writer.writeheader(); writer.writerows(review)
    print(f"fit {fitted_before}->{fitted_after}/{len(rows)}; review={len(review)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
