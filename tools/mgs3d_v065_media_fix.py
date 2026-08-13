#!/usr/bin/env python3
"""Apply the reviewed v0.65 Virtue/Virtuous wording fixes in fixed media slots."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_rendered
from mgs3d_movie_tool import parse_records


NORMALIZATIONS = (("버츄어스 미션", "버추어스 미션"),)
JACK_VARIANTS = ("버츄어스 미션 ?", "버추어스 미션 ?", "버츄어스 미션?", "버추어스 미션?")
JACK_REPLACEMENT = "버추(가상)미션?"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("character_map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    mapping_doc = json.loads(args.character_map.read_text(encoding="utf-8"))
    entries = mapping_doc.get("character_map", mapping_doc.get("characters"))
    if not isinstance(entries, dict):
        raise ValueError("character map has no character mapping")
    mapping = {character: bytes.fromhex(token) for character, token in entries.items()}
    original = args.source.read_bytes()
    output = bytearray(original)
    _, records, _ = parse_records(original)
    changes: list[dict[str, object]] = []

    for record_index, record in enumerate(records):
        for subtitle_index, subtitle in enumerate(record.subtitles):
            raw = bytes(output[subtitle.offset:subtitle.offset + len(subtitle.raw)])
            changed = raw
            for old, new in NORMALIZATIONS:
                old_bytes = parse_rendered(old, mapping)
                new_bytes = parse_rendered(new, mapping)
                if len(old_bytes) != len(new_bytes):
                    raise ValueError("normalization must preserve encoded width")
                if old_bytes in changed:
                    count = changed.count(old_bytes)
                    changed = changed.replace(old_bytes, new_bytes)
                    changes.append({"kind": "term", "record": record_index, "subtitle": subtitle_index,
                                    "old": old, "new": new, "count": count})

            for variant in JACK_VARIANTS:
                old_bytes = parse_rendered(variant, mapping)
                if old_bytes not in changed:
                    continue
                new_bytes = parse_rendered(JACK_REPLACEMENT + "<00>", mapping)
                capacity = len(subtitle.original) - 4 - len(subtitle.tail)
                if len(new_bytes) > capacity:
                    raise ValueError(f"Jack wording exceeds slot: {len(new_bytes)} > {capacity}")
                text_start = subtitle.offset
                output[text_start:text_start + capacity] = new_bytes.ljust(capacity, b"\0")
                changed = bytes(output[text_start:text_start + len(subtitle.raw)])
                changes.append({"kind": "virtue-pun", "record": record_index,
                                "subtitle": subtitle_index, "old": variant,
                                "new": JACK_REPLACEMENT, "old_bytes": len(old_bytes),
                                "new_bytes": len(new_bytes), "capacity": capacity})
                break
            output[subtitle.offset:subtitle.offset + len(subtitle.raw)] = changed

    pun_changes = [change for change in changes if change["kind"] == "virtue-pun"]
    if not pun_changes:
        raise ValueError("Jack Virtue line was not found")
    rebuilt = bytes(output)
    _, reparsed, _ = parse_records(rebuilt)
    before_layout = [(record.offset, len(record.raw)) for record in records]
    after_layout = [(record.offset, len(record.raw)) for record in reparsed]
    if before_layout != after_layout or len(rebuilt) != len(original):
        raise ValueError("fixed media layout changed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rebuilt)
    report = {
        "format": "mgs3d-v065-media-fix-v1",
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "output_sha256": hashlib.sha256(rebuilt).hexdigest(),
        "size_preserved": len(rebuilt) == len(original),
        "record_layout_preserved": before_layout == after_layout,
        "changes": changes,
    }
    report_path = args.report or args.output.with_suffix(args.output.suffix + ".manifest.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
