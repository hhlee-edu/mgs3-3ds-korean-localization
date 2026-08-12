#!/usr/bin/env python3
"""Build a conservative story-media order and cross-reference report."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import GcxRecord  # noqa: E402
from mgs3d_story_media_calls import load_demo_table  # noqa: E402


FIELDS = ["story_order", "stage", "procedure", "call_order", "type",
          "resource_id", "demo_table_id", "ps2_resource", "hd_resource",
          "english", "korean", "confidence", "note"]
HD_PATH = re.compile(r"(?:^|[\\/])(demo|movie)[\\/]_bp[\\/]([^\\/]+)\.sdt$", re.I)


def stage_key(stage: str) -> tuple[int, int, str]:
    match = re.match(r"([vs])(\d+)", stage.lower())
    if match:
        return (0 if match.group(1) == "v" else 1, int(match.group(2)), stage)
    return (2, 0, stage)


def load_hd(filelist: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for line in filelist.read_text(encoding="utf-8", errors="replace").splitlines():
        match = HD_PATH.search(line)
        if match:
            result[match.group(1).lower()].append(match.group(2))
    return result


def canonical(name: str) -> str:
    value = name.lower()
    value = re.sub(r"_(?:poly)?demo$", "", value)
    return value


def hd_candidates(kind: str, resource: str, hd: dict[str, list[str]]) -> list[str]:
    exact = [name for name in hd.get(kind, []) if name.lower() == resource.lower()]
    if exact:
        return exact
    normalized = [name for name in hd.get(kind, []) if canonical(name) == canonical(resource)]
    if normalized:
        return normalized
    # HD collapses several alias payloads (p010/p011 -> p0).
    prefix = re.match(r"^([mv]\d{3}_\d{3})_", resource.lower())
    if prefix:
        same = [name for name in hd.get(kind, [])
                if name.lower().startswith(prefix.group(1) + "_")]
        if len(same) == 1:
            return same
    return []


def ps2_demo_match(row: dict[str, str], ps2_root: Path,
                   descriptors: dict[str, int], cache: dict[str, bytes]) -> str:
    stage = row["stage"]
    if stage not in cache:
        files = sorted((ps2_root / stage).glob("*.02"))
        if len(files) != 1:
            cache[stage] = b""
        else:
            record = GcxRecord(files[0].read_bytes())
            cache[stage] = record.raw[record.block_start + record.proc_offset:]
    blob = cache[stage]
    matches = [name for name in row["resource_id"].split("|")
               if name in descriptors and descriptors[name].to_bytes(3, "little") in blob]
    return "|".join(matches)


def load_opening_dialogue(demo_dialogue: Path, movie_dialogue: Path) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    with demo_dialogue.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    first = next((row for row in rows
                  if row.get("container", "demo") == "demo"
                  and "Spread your wings and fly" in row["english"]), None)
    if first:
        result["opening_demo"] = (
            "Flying over Pakistan, altitude 30,000 feet. [...] " + first["english"],
            "파키스탄 상공, 고도 3만 피트. […] " + (first.get("korean_full") or first.get("korean", "")),
        )
    with movie_dialogue.open(encoding="utf-8-sig", newline="") as handle:
        first = next((row for row in csv.DictReader(handle)
                      if row.get("container", "movie") == "movie"
                      and "Jack, I've got some important news" in row.get("english", "")), None)
    if first:
        result["opening_movie"] = (first["english"], first.get("korean_full") or first.get("korean", ""))
    return result


def build(demo_csv: Path, movie_csv: Path, filelist: Path, demo_table: Path,
          ps2_root: Path, demo_dialogue: Path, movie_dialogue: Path) -> list[dict[str, str]]:
    with demo_csv.open(encoding="utf-8-sig", newline="") as handle:
        demos = list(csv.DictReader(handle))
    with movie_csv.open(encoding="utf-8-sig", newline="") as handle:
        movies = list(csv.DictReader(handle))
    hd = load_hd(filelist)
    by_descriptor, _ = load_demo_table(demo_table)
    descriptors = {name: value for value, mappings in by_descriptor.items() for _, name in mappings}
    opening = load_opening_dialogue(demo_dialogue, movie_dialogue)
    ps2_cache: dict[str, bytes] = {}

    # Movie rows are positioned between their actual bounding demo offsets.
    placement: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    unresolved_movies: list[dict[str, str]] = []
    for row in movies:
        if row["stage"]:
            placement[(row["stage"], row["procedure"])].append(row)
        else:
            unresolved_movies.append(row)
    for values in placement.values():
        values.sort(key=lambda row: int(media_number(row["resource_id"])))

    ordered: list[dict[str, str]] = []
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in demos:
        groups[(row["stage"], row["procedure"])].append(row)
    for key in sorted(groups, key=lambda item: (stage_key(item[0]), int(item[1] or -1))):
        calls = sorted(groups[key], key=lambda row: int(row["script_offset"], 16))
        inserted = False
        for call in calls:
            ordered.append(call)
            if not inserted and placement.get(key) and call["script_offset"] == placement[key][0]["evidence_before_offset"]:
                ordered.extend(placement[key])
                inserted = True
        if not inserted:
            ordered.extend(placement.get(key, []))
    # The one known cross-stage opening movie is placed after opening v000 calls.
    for movie in unresolved_movies:
        if movie["resource_id"].lower() == "v020_020_m010":
            index = max((i for i, row in enumerate(ordered) if row["stage"] == "v000a_0"), default=-1)
            ordered.insert(index + 1, movie)
        else:
            ordered.append(movie)

    output: list[dict[str, str]] = []
    for order, source in enumerate(ordered, 1):
        kind = source["type"]
        resources = source["resource_id"].split("|") if source["resource_id"] else []
        hd_names = sorted({name for resource in resources for name in hd_candidates(kind, resource, hd)})
        ps2 = ""
        if kind == "demo":
            ps2 = ps2_demo_match(source, ps2_root, descriptors, ps2_cache)
        elif source.get("ps2_hd_crosscheck") == "bounding_demo_descriptors_match":
            ps2 = source["resource_id"] + " (boundary-confirmed)"
        english = korean = ""
        notes: list[str] = []
        confidence = source["confidence"]
        if source["stage"] == "v000a_0" and kind == "demo" and "opening_demo" in opening:
            english, korean = opening["opening_demo"]
            notes.append("runtime opening boundary; p010/p011 subdivision unresolved")
            confidence += "+runtime_story_boundary_alias"
        if kind == "movie" and source["resource_id"].lower() == "v020_020_m010" and "opening_movie" in opening:
            english, korean = opening["opening_movie"]
            notes.append("runtime-confirmed movie after Pakistan opening; stage/procedure remains unresolved")
            confidence = "runtime_story_boundary+english_similarity"
        if len(resources) > 1:
            notes.append("resource/hash collision retained")
        if not hd_names:
            notes.append("no HD filelist resource match")
        if not ps2:
            notes.append("PS2 same-stage resource not confirmed")
        if not english:
            notes.append("dialogue resource boundary not yet proven")
        output.append({
            "story_order": str(order), "stage": source["stage"],
            "procedure": source["procedure"], "call_order": source["call_order"],
            "type": kind, "resource_id": source["resource_id"],
            "demo_table_id": source.get("demo_table_id", ""),
            "ps2_resource": ps2, "hd_resource": "|".join(hd_names),
            "english": english, "korean": korean, "confidence": confidence,
            "note": "; ".join(notes),
        })
    return output


def media_number(name: str) -> int:
    match = re.match(r"^[mv]\d{3}_(\d{3})_", name, re.I)
    return int(match.group(1)) if match else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo_csv", type=Path)
    parser.add_argument("movie_csv", type=Path)
    parser.add_argument("filelist", type=Path)
    parser.add_argument("demo_table", type=Path)
    parser.add_argument("ps2_root", type=Path)
    parser.add_argument("demo_dialogue", type=Path)
    parser.add_argument("movie_dialogue", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("review_csv", type=Path)
    parser.add_argument("summary_json", type=Path)
    args = parser.parse_args()
    rows = build(args.demo_csv, args.movie_csv, args.filelist, args.demo_table,
                 args.ps2_root, args.demo_dialogue, args.movie_dialogue)
    review = [row for row in rows if not row["english"] or "collision" in row["note"]]
    for path, values in ((args.output_csv, rows), (args.review_csv, review)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader(); writer.writerows(values)
    summary = {
        "rows": len(rows), "demo_rows": sum(r["type"] == "demo" for r in rows),
        "movie_rows": sum(r["type"] == "movie" for r in rows),
        "ps2_resource_rows": sum(bool(r["ps2_resource"]) for r in rows),
        "hd_resource_rows": sum(bool(r["hd_resource"]) for r in rows),
        "dialogue_rows": sum(bool(r["english"] and r["korean"]) for r in rows),
        "resource_auto_rows": sum(bool(r["ps2_resource"] and r["hd_resource"])
                                  and "collision" not in r["note"] for r in rows),
        "dialogue_unresolved_rows": sum(not bool(r["english"] and r["korean"]) for r in rows),
        "manual_review_rows": len(review),
        "collision_rows": sum("collision" in r["note"] for r in rows),
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
