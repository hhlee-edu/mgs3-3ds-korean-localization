#!/usr/bin/env python3
"""Create an auditable fixed-capacity media candidate; never lose source text."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_movie_tool import parse_records, wrap_like_source  # noqa: E402


def encoded_size(text: str) -> int:
    return 1 + sum(1 if ord(c) < 0x80 else 2 for c in text)


def built_size(text: str, source: bytes) -> int:
    wrapped = wrap_like_source(text, source)
    return 1 + sum(2 if c == "\n" or ord(c) >= 0x80 else 1 for c in wrapped)


def conservative_forms(text: str):
    yield text
    text = text.replace("...", ".").replace("…", ".")
    yield text
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"([,(])\s+", r"\1", text)
    yield text
    yield text.replace(" ", "")
    yield re.sub(r"[,.!?]+$", "", text.replace(" ", ""))


def clipped(text: str, capacity: int, source: bytes) -> str:
    """Fit a visibly provisional prefix; full source remains in the review CSV."""
    suffix = "."
    value = text
    while value and built_size(value + suffix, source) > capacity:
        value = value[:-1]
    return value.rstrip(" ,.!?|\"") + suffix if value else (suffix if built_size(suffix, source) <= capacity else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation", type=Path)
    parser.add_argument("inspect", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("--media-source", required=True, type=Path)
    args = parser.parse_args()
    with args.inspect.open(encoding="utf-8-sig", newline="") as stream:
        capacity = {int(r["offset"]): int(r.get("fixed_capacity") or r["size"])
                    for r in csv.DictReader(stream)
                    if r["entry_type"] == "1"}
    with args.translation.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream); rows = list(reader); fields = list(reader.fieldnames or [])
    _, records, _ = parse_records(args.media_source.read_bytes())
    raw_by_offset = {s.offset: s.raw for r in records for s in r.subtitles}
    audit = []
    counts = {"unchanged": 0, "mechanical": 0, "forced_clip": 0}
    for row in rows:
        source = row["korean"]
        cap = capacity[int(row["offset"])]
        raw = raw_by_offset[int(row["offset"])]
        selected = next((v for v in conservative_forms(source) if built_size(v, raw) <= cap), None)
        status = "unchanged" if selected == source else "mechanical"
        if selected is None:
            selected = clipped(source.replace(" ", ""), cap, raw)
            status = "forced_clip"
        if built_size(selected, raw) > cap:
            raise ValueError(f"cannot fit offset {row['offset']} in {cap} bytes")
        row["korean"] = selected
        counts[status] += 1
        if selected != source:
            audit.append({"media": row["media"], "record": row["record"],
                          "entry": row["entry"], "offset": row["offset"],
                          "capacity_bytes": cap, "status": status,
                          "english": row["preview"], "source_korean": source,
                          "candidate_korean": selected, "user_korean": ""})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    review_fields = ["media", "record", "entry", "offset", "capacity_bytes", "status",
                     "english", "source_korean", "candidate_korean", "user_korean"]
    with args.review.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=review_fields); writer.writeheader(); writer.writerows(audit)
    print(" ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
