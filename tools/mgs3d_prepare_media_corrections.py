#!/usr/bin/env python3
"""Map reviewed 3DS Korean corrections onto the offsets of current DAT files."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_english_korean_match import decode_western
from mgs3d_movie_tool import parse_records


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", (text or "").casefold(), re.UNICODE))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corrections_csv", type=Path)
    parser.add_argument("movie_dat", type=Path)
    parser.add_argument("demo_dat", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    with args.corrections_csv.open(encoding="utf-8-sig", newline="") as stream:
        corrections = [row for row in csv.DictReader(stream)
                       if row.get("changed", "").strip().lower() in {"1", "true", "yes"}]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for media, dat_path in (("movie", args.movie_dat), ("demo", args.demo_dat)):
        _, records, _ = parse_records(dat_path.read_bytes())
        selected = [row for row in corrections if row["media"] == media]
        output = []
        english_mismatches = 0
        for row in selected:
            record_index, entry_index = int(row["record"]), int(row["entry"])
            if not 0 <= record_index < len(records):
                raise ValueError(f"{row['three_ds_id']}: record {record_index} is absent")
            record = records[record_index]
            if not 0 <= entry_index < len(record.subtitles):
                raise ValueError(f"{row['three_ds_id']}: entry {entry_index} is absent")
            subtitle = record.subtitles[entry_index]
            if subtitle.entry_type != 1:
                raise ValueError(
                    f"{row['three_ds_id']}: expected type 1, found {subtitle.entry_type}"
                )
            live_english = decode_western(subtitle.raw)
            # Existing Korean tokens cannot be decoded as Western. Compare text
            # only where a usable Western string remains in the live DAT.
            live_norm, review_norm = normalized(live_english), normalized(row["english"])
            if (b"\x90" not in subtitle.raw and live_norm and review_norm
                    and live_norm != review_norm):
                # The live RomForge DAT may already contain Japanese global
                # tokens or earlier Korean work. record/entry and type remain
                # the stable identity; Western decoding is only diagnostic.
                english_mismatches += 1
            output.append({
                "accept": "yes",
                "offset": subtitle.offset,
                "korean": row["corrected_korean"],
                "three_ds_id": row["three_ds_id"],
                "record": record_index,
                "entry": entry_index,
                "review_offset": row["offset"],
                "live_offset": subtitle.offset,
                "english": row["english"],
            })
        fields = ["accept", "offset", "korean", "three_ds_id", "record", "entry",
                  "review_offset", "live_offset", "english"]
        target = args.output_dir / f"{media}_3ds_korean_corrections_v1_apply.csv"
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(output)
        shifted = sum(int(row["review_offset"]) != int(row["live_offset"]) for row in output)
        print(f"{media}: {len(output)} rows, {shifted} live offsets differ from review "
              f"offsets, {english_mismatches} live English checks unavailable/mismatched")
        total += len(output)
    if total != len(corrections):
        raise ValueError(f"prepared {total}/{len(corrections)} corrections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
