#!/usr/bin/env python3
"""Place known movie resources between confirmed static demo calls.

The 3DS scenario corpus contains no structurally framed ``movie`` command.
Consequently this tool does not invent a movie descriptor.  It uses the HD
movie namespace as a resource-name dictionary and records only name-sequence
gaps bounded by already extracted demo calls (for example m010_010 ->
m010_020_m010 -> m010_030_m020 -> m010_040).  Such rows are explicitly marked
as inference, not as decoded call sites.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import GcxRecord  # noqa: E402
from mgs3d_story_media_calls import load_demo_table  # noqa: E402


MOVIE_PATH = re.compile(r"(?:^|[\\/])movie[\\/]_bp[\\/]([^\\/]+)\.sdt$", re.I)
MEDIA_NAME = re.compile(r"^([mv]\d{3})_(\d{3})_[pm]\d{3}(?:_.*)?$", re.I)


def load_movie_names(filelist: Path) -> list[str]:
    names: list[str] = []
    for line in filelist.read_text(encoding="utf-8", errors="replace").splitlines():
        match = MOVIE_PATH.search(line.strip())
        if match:
            names.append(match.group(1))
    return sorted(set(names), key=str.lower)


def media_position(name: str) -> tuple[str, int] | None:
    match = MEDIA_NAME.match(name)
    return None if match is None else (match.group(1).lower(), int(match.group(2)))


def ps2_bounds_match(row: dict[str, str], ps2_root: Path,
                     demo_table: Path) -> bool:
    candidates = sorted((ps2_root / row["stage"]).glob("*.02"))
    if len(candidates) != 1:
        return False
    record = GcxRecord(candidates[0].read_bytes())
    blob = record.raw[record.block_start + record.proc_offset:]
    by_descriptor, _ = load_demo_table(demo_table)
    by_name = {name: descriptor for descriptor, mappings in by_descriptor.items()
               for _, name in mappings}
    for field in ("evidence_before", "evidence_after"):
        names = row[field].split("|")
        descriptors = [by_name[name] for name in names if name in by_name]
        if not descriptors or not any(value.to_bytes(3, "little") in blob
                                      for value in descriptors):
            return False
    return True


def infer_rows(demo_csv: Path, movie_names: list[str], ps2_root: Path | None = None,
               demo_table: Path | None = None) -> list[dict[str, str]]:
    with demo_csv.open(encoding="utf-8-sig", newline="") as handle:
        demos = list(csv.DictReader(handle))
    by_proc: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in demos:
        if row.get("type") == "demo" and row.get("resource_id"):
            by_proc[(row["stage"], row["procedure"])].append(row)
    for values in by_proc.values():
        values.sort(key=lambda row: int(row["script_offset"], 16))

    result: list[dict[str, str]] = []
    unresolved: list[str] = []
    for movie in movie_names:
        position = media_position(movie)
        candidates: list[tuple[dict[str, str], dict[str, str]]] = []
        if position:
            prefix, number = position
            for calls in by_proc.values():
                parsed = [(call, media_position(call["resource_id"])) for call in calls]
                for (left, lp), (right, rp) in zip(parsed, parsed[1:]):
                    if lp and rp and lp[0] == rp[0] == prefix and lp[1] < number < rp[1]:
                        candidates.append((left, right))
        if len(candidates) != 1:
            unresolved.append(movie)
            continue
        left, right = candidates[0]
        result.append({
            "stage": left["stage"],
            "procedure": left["procedure"],
            "call_order": "",
            "type": "movie",
            "scene_id": "",
            "demo_table_id": "",
            "movie_table_id": "",
            "record_id/descriptor": "",
            "packed_file_descriptor": "",
            "descriptor_file": "movie.dat",
            "resource_id": movie,
            "script_offset": "",
            "argument_tag": "",
            "argument_kind": "name_sequence_gap",
            "confidence": "static_sequence_gap_inference",
            "evidence_before": left["resource_id"],
            "evidence_before_offset": left["script_offset"],
            "evidence_after": right["resource_id"],
            "evidence_after_offset": right["script_offset"],
            "ps2_hd_crosscheck": "",
        })
        if ps2_root and demo_table:
            result[-1]["ps2_hd_crosscheck"] = (
                "bounding_demo_descriptors_match"
                if ps2_bounds_match(result[-1], ps2_root, demo_table)
                else "not_confirmed"
            )

    # Cross-stage boundaries are not silently inferred.  Keep them visible so
    # a runtime or outer stage-control trace can resolve them later.
    for movie in unresolved:
        result.append({
            "stage": "", "procedure": "", "call_order": "", "type": "movie",
            "scene_id": "", "demo_table_id": "", "movie_table_id": "",
            "record_id/descriptor": "",
            "packed_file_descriptor": "", "descriptor_file": "movie.dat",
            "resource_id": movie, "script_offset": "", "argument_tag": "",
            "argument_kind": "unresolved_movie_resource",
            "confidence": "resource_name_only",
            "evidence_before": "", "evidence_before_offset": "",
            "evidence_after": "", "evidence_after_offset": "",
            "ps2_hd_crosscheck": "",
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo_csv", type=Path)
    parser.add_argument("hd_filelist", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--ps2-root", type=Path)
    parser.add_argument("--demo-table", type=Path)
    parser.add_argument("--combined-output", type=Path,
                        help="also write demo rows plus movie inference rows")
    args = parser.parse_args()
    names = load_movie_names(args.hd_filelist)
    rows = infer_rows(args.demo_csv, names, args.ps2_root, args.demo_table)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    if args.combined_output:
        with args.demo_csv.open(encoding="utf-8-sig", newline="") as handle:
            demo_rows = list(csv.DictReader(handle))
        combined_fields = list(dict.fromkeys(
            [key for row in demo_rows + rows for key in row]
        ))
        args.combined_output.parent.mkdir(parents=True, exist_ok=True)
        with args.combined_output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=combined_fields)
            writer.writeheader()
            writer.writerows(demo_rows + rows)
    inferred = sum(row["confidence"] == "static_sequence_gap_inference" for row in rows)
    print(f"wrote {args.output_csv}: resources={len(names)} inferred={inferred} unresolved={len(rows)-inferred}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
