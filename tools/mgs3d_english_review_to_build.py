#!/usr/bin/env python3
"""Convert a combined English-review CSV into codec/movie/demo build inputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ACCEPTED = {"confirmed", "corrected"}
TOKEN = re.compile(r"<[^>]+>")
PUNCTUATION = str.maketrans({
    "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "‚": "'",
    "…": "...", "–": "-", "—": "-", "‐": "-", " ": " ",
})


def normalize_korean(text: str) -> str:
    return " ".join(text.translate(PUNCTUATION).split())


def wrap_codec(korean: str, raw: str) -> str:
    korean = normalize_korean(korean)
    line_count = max(1, raw.count("<0A>"))
    if line_count == 1:
        return korean + "<0A><00>"
    visible = TOKEN.sub("", raw).splitlines()
    del visible
    words = korean.split()
    if len(words) >= line_count:
        boundaries = [round(index * len(words) / line_count) for index in range(line_count + 1)]
        lines = [" ".join(words[boundaries[i]:boundaries[i + 1]]) for i in range(line_count)]
    else:
        boundaries = [round(index * len(korean) / line_count) for index in range(line_count + 1)]
        lines = [korean[boundaries[i]:boundaries[i + 1]] for i in range(line_count)]
    return "<0A>".join(lines) + "<0A><00>"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    with args.review.open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream)
                if row.get("disposition") in ACCEPTED and row.get("korean", "").strip()]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    codec_units = []
    for row in rows:
        if row.get("container") != "codec":
            continue
        codec_units.append({
            "gcx": int(row["gcx"]), "resource": int(row["resource"]), "kind": "string",
            "original_size": len(row.get("raw_text", "")),
            "text": wrap_codec(row["korean"].strip(), row.get("raw_text", "")),
        })
    codec = {"format": "mgs3d-codec-translation-v1", "character_map": {}, "units": codec_units}
    (args.output_dir / "codec_translation.json").write_text(
        json.dumps(codec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for container in ("movie", "demo"):
        selected = [row for row in rows if row.get("container") == container]
        path = args.output_dir / f"{container}_translation.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("accept", "offset", "korean"))
            writer.writeheader()
            writer.writerows({"accept": "yes", "offset": row["offset"],
                              "korean": normalize_korean(row["korean"])} for row in selected)
    print(f"codec={len(codec_units)}, movie={sum(r.get('container') == 'movie' for r in rows)}, "
          f"demo={sum(r.get('container') == 'demo' for r in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
