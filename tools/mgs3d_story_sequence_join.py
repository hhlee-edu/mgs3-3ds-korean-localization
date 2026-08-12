#!/usr/bin/env python3
"""Promote PS2 Korean matches only when English sequence context agrees."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_demo_scene_compact import scene_starts, walk_blocks  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402


FIELDS = ["type", "story_order", "resource_id", "record", "entry", "offset",
          "english_sequence", "korean_sequence", "english", "korean",
          "confidence", "note"]


def cards(path: Path) -> tuple[bytes, list[dict[str, object]], list]:
    data = path.read_bytes()
    records = parse_records(data)[1]
    result = []
    for record in records:
        for entry, subtitle in enumerate(record.subtitles):
            if subtitle.entry_type == 1:
                result.append({"record": record.index, "entry": entry,
                               "offset": subtitle.offset,
                               "english": decode_western(subtitle.raw)})
    return data, result, records


def boundaries(kind: str, data: bytes, records: list) -> list[int]:
    if kind == "demo":
        return scene_starts(data, walk_blocks(data))
    starts = [records[0].offset]
    for index in range(1, len(records)):
        current = struct.unpack_from("<I", records[index].raw, 8)[0]
        previous = struct.unpack_from("<I", records[index - 1].raw, 8)[0]
        if current < previous:
            starts.append(records[index].offset)
    return starts


def contextual_rows(kind: str, dat: Path, direct_csv: Path,
                    sequence_csv: Path) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    data, all_cards, records = cards(dat)
    starts = boundaries(kind, data, records)
    with direct_csv.open(encoding="utf-8-sig", newline="") as handle:
        direct = [row for row in csv.DictReader(handle)
                  if row["match_status"] == "exact-unique-korean" and row["korean"].strip()]
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in direct:
        group = bisect.bisect_right(starts, int(row["offset"])) - 1
        grouped.setdefault(group, []).append(row)

    accepted: dict[int, dict[str, str]] = {}
    for group, rows in grouped.items():
        rows.sort(key=lambda row: int(row["offset"]))
        run: list[dict[str, str]] = []
        previous = None
        for row in rows + [None]:
            sequence = None if row is None else int(row["english_sequence"])
            if row is not None and (previous is None or 0 <= sequence - previous <= 8):
                run.append(row)
            else:
                if len(run) >= 2:
                    for item in run:
                        item = dict(item)
                        item["confidence"] = "high_context_sequence_run"
                        item["note"] = f"{kind} structural group {group}; {len(run)}-line monotonic run"
                        accepted[int(item["offset"])] = item
                run = [] if row is None else [row]
            previous = sequence

    # Exact matches spanning two or more consecutive subtitle cards are an
    # independent context check and may add cards absent from the direct set.
    with sequence_csv.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["sequence_cards"]) < 2:
                continue
            if not row.get("korean", "").strip():
                continue
            item = dict(row)
            item["confidence"] = "high_multi_card_exact"
            item["note"] = f"{row['sequence_cards']}-card English sequence match"
            accepted[int(row["offset"])] = item
    actual_offsets = {int(card["offset"]) for card in all_cards}
    return [row for offset, row in accepted.items() if offset in actual_offsets], all_cards


def opening_resources(story_csv: Path) -> dict[str, tuple[str, str]]:
    with story_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    demo = [row for row in rows if row["stage"] == "v000a_0" and row["type"] == "demo"]
    movie = next((row for row in rows if row["resource_id"].lower() == "v020_020_m010"), None)
    return {
        "demo": ("|".join(row["resource_id"] for row in demo),
                 "|".join(row["story_order"] for row in demo)),
        "movie": ((movie or {}).get("resource_id", ""), (movie or {}).get("story_order", "")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story_csv", type=Path)
    parser.add_argument("movie_dat", type=Path)
    parser.add_argument("demo_dat", type=Path)
    parser.add_argument("movie_direct", type=Path)
    parser.add_argument("demo_direct", type=Path)
    parser.add_argument("movie_sequence", type=Path)
    parser.add_argument("demo_sequence", type=Path)
    parser.add_argument("matched_csv", type=Path)
    parser.add_argument("gap_csv", type=Path)
    parser.add_argument("summary_json", type=Path)
    args = parser.parse_args()

    anchors = opening_resources(args.story_csv)
    matched: list[dict[str, str]] = []
    all_by_kind: dict[str, list[dict[str, object]]] = {}
    for kind, dat, direct, sequence in (
        ("movie", args.movie_dat, args.movie_direct, args.movie_sequence),
        ("demo", args.demo_dat, args.demo_direct, args.demo_sequence),
    ):
        rows, all_cards = contextual_rows(kind, dat, direct, sequence)
        all_by_kind[kind] = all_cards
        for row in rows:
            resource = order = ""
            note = row["note"]
            # Runtime established only these opening resource boundaries.
            seq = int(row.get("english_sequence") or -1)
            if kind == "movie" and 15 <= seq <= 125:
                resource, order = anchors["movie"]
                note += "; opening movie runtime anchor"
            elif kind == "demo" and 0 <= seq <= 14:
                resource, order = anchors["demo"]
                note += "; opening demo alias boundary"
            matched.append({
                "type": kind, "story_order": order, "resource_id": resource,
                "record": row["record"], "entry": row["entry"], "offset": row["offset"],
                "english_sequence": row.get("english_sequence", ""),
                "korean_sequence": row.get("korean_sequence", ""),
                "english": row["english"], "korean": row["korean"],
                "confidence": row["confidence"], "note": note,
            })
    matched.sort(key=lambda row: (int(row["english_sequence"] or 999999), row["type"], int(row["offset"])))
    matched_offsets = {(row["type"], int(row["offset"])) for row in matched}
    gaps = [{
        "type": kind, "story_order": "", "resource_id": "",
        "record": card["record"], "entry": card["entry"], "offset": card["offset"],
        "english_sequence": "", "korean_sequence": "", "english": card["english"],
        "korean": "", "confidence": "unresolved", "note": "no multi-line context confirmation",
    } for kind, values in all_by_kind.items() for card in values
       if (kind, int(card["offset"])) not in matched_offsets]
    for path, rows in ((args.matched_csv, matched), (args.gap_csv, gaps)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    total = len(matched) + len(gaps)
    summary = {
        "total_3ds_english_rows": total,
        "automatic_context_matches": len(matched),
        "high_confidence_rate": round(len(matched) / total, 6) if total else 0,
        "movie_matches": sum(row["type"] == "movie" for row in matched),
        "demo_matches": sum(row["type"] == "demo" for row in matched),
        "resource_anchored_matches": sum(bool(row["resource_id"]) for row in matched),
        "gap_unresolved_rows": len(gaps),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
