#!/usr/bin/env python3
"""Reject media builds that drift record/subtitle layout or demo scene starts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_demo_scene_compact import scene_starts, walk_blocks  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def layout(data: bytes, include_record_placement: bool = True) -> list[dict[str, object]]:
    _, records, _ = parse_records(data)
    return [
        ({
            **({"offset": record.offset, "size": len(record.raw)} if include_record_placement else {}),
            "text_end": record.text_end,
            "subtitles": [
                {
                    "relative_offset": subtitle.offset - record.offset,
                    "capacity": len(subtitle.original) - 4,
                    "entry_type": subtitle.entry_type,
                }
                for subtitle in record.subtitles
            ],
        })
        for record in records
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("movie", "demo"))
    parser.add_argument("original", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    original = args.original.read_bytes()
    candidate = args.candidate.read_bytes()
    failures: list[str] = []
    if len(candidate) != len(original):
        failures.append(f"file size drift: {len(original)} -> {len(candidate)}")

    try:
        # Demo records may grow into their own scene's trailing padding. This
        # moves later records *inside that same scene*, which is runtime-proven
        # safe when every scene start and every subtitle's record-relative
        # layout remain fixed. Movie keeps the stricter absolute placement rule.
        include_placement = args.kind == "movie"
        original_layout = layout(original, include_placement)
        candidate_layout = layout(candidate, include_placement)
        if candidate_layout != original_layout:
            failures.append("record-internal subtitle offsets, capacities, types, or text boundary drifted")
    except Exception as error:  # parser errors are hard gate failures
        failures.append(f"media parse failed: {error}")

    scene_count = None
    if args.kind == "demo":
        try:
            original_scenes = scene_starts(original, walk_blocks(original))
            candidate_scenes = scene_starts(candidate, walk_blocks(candidate))
            scene_count = len(original_scenes)
            if candidate_scenes != original_scenes:
                failures.append("demo scene start offsets drifted")
        except Exception as error:
            failures.append(f"demo scene parse failed: {error}")

    report = {
        "format": "mgs3d-grow-safety-gate-v1",
        "kind": args.kind,
        "original": str(args.original.resolve()),
        "candidate": str(args.candidate.resolve()),
        "original_sha256": sha256(original),
        "candidate_sha256": sha256(candidate),
        "file_size": len(original),
        "scene_count": scene_count,
        "passed": not failures,
        "failures": failures,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
