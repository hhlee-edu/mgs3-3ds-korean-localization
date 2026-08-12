#!/usr/bin/env python3
"""Replace non-shared Korean word stems with aligned source-English words."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

PARTICLES = sorted(("으로부터", "에게서", "에서는", "으로는", "이라는", "이라고",
                    "에서", "에게", "까지", "부터", "처럼", "보다", "으로", "라고",
                    "이라", "의", "은", "는", "이", "가", "을", "를", "에", "와", "과",
                    "도", "만", "로"), key=len, reverse=True)


def english_words(value: str) -> list[str]:
    value = re.sub(r"<[^>]+>", " ", value).replace("|", " ")
    return re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", value)


def split_particle(word: str, shared: set[str]) -> tuple[str, str]:
    for particle in PARTICLES:
        if word.endswith(particle) and len(word) > len(particle) and set(particle) <= shared:
            return word[:-len(particle)], particle
    return word, ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("translation", type=Path)
    p.add_argument("allocation", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("review", type=Path)
    args = p.parse_args()
    shared = set(json.loads(args.allocation.read_text(encoding="utf-8-sig"))["characters"])
    with args.translation.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); rows = list(reader); fields = list(reader.fieldnames or [])
    reviews = []
    changed_words = 0
    for row in rows:
        source = row["korean"]
        candidates = english_words(row["preview"])
        hangul_matches = list(re.finditer(r"[가-힣]+", source))
        replacements: list[tuple[int, int, str]] = []
        for index, match in enumerate(hangul_matches):
            word = match.group()
            if set(word) <= shared:
                continue
            stem, particle = split_particle(word, shared)
            if not candidates:
                english = "EN"
            else:
                position = round(index * (len(candidates) - 1) / max(1, len(hangul_matches) - 1))
                english = candidates[position]
            replacements.append((match.start(), match.end(), english + particle))
            changed_words += 1
        value = source
        for start, end, replacement in reversed(replacements):
            value = value[:start] + replacement + value[end:]
        if value != source:
            reviews.append({"media": row["media"], "record": row["record"],
                            "entry": row["entry"], "offset": row["offset"],
                            "english": row["preview"], "source_korean": source,
                            "hybrid_korean": value, "user_korean": ""})
            row["korean"] = value
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    review_fields = ["media", "record", "entry", "offset", "english", "source_korean",
                     "hybrid_korean", "user_korean"]
    with args.review.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=review_fields); writer.writeheader(); writer.writerows(reviews)
    print(f"rows_changed={len(reviews)} words_changed={changed_words}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
