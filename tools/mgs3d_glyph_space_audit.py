#!/usr/bin/env python3
"""Read-only glyph and byte-capacity audit for MGS3D translations.

This tool never renders translations and never writes DAT/GCX/HPK files.  It
uses the same token encoders and binary parsers as the builders, so resident
glyph reuse, local-font allocation, string sizes, and reclaimable slots are
derived from actual tables rather than text-frequency estimates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import (  # noqa: E402
    CodecError,
    decode_mgs_preview,
    parse_codec,
    parse_rendered,
)
from mgs3d_demo_scene_compact import (  # noqa: E402
    scene_bounds,
    scene_starts,
    trailing_pad_run,
    walk_blocks,
)
from mgs3d_gcx_font_tool import (  # noqa: E402
    GLYPH_SIZE,
    custom_token,
    dead_font_slots,
    font_region,
)
from mgs3d_movie_tool import (  # noqa: E402
    PAGE3_TOKEN_TO_INDEX,
    align,
    encode_translation,
    page3_indices,
    page3_token,
    parse_records,
    wrap_like_source,
)
from mgs3d_hpk_static_korean import physical_slot_for_token  # noqa: E402
from mgs3d_translation import validate_codec_translation  # noqa: E402


HANGUL = lambda ch: len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_static_allocation(path: Path) -> tuple[dict[str, bytes], dict]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    characters = document.get("characters")
    if not isinstance(characters, dict):
        raise ValueError(f"static allocation has no characters map: {path}")
    mapping = {str(ch): bytes.fromhex(str(token)) for ch, token in characters.items()}
    for ch, token in mapping.items():
        if len(ch) != 1 or len(token) != 2 or token[0] not in (0x81, 0x82, 0x83):
            raise ValueError(f"invalid resident glyph mapping {ch!r}: {token.hex()}")
    return mapping, document


def verify_resident(allocation_doc: dict, residents: list[Path],
                    proof_docs: list[dict]) -> list[dict[str, object]]:
    result = []
    for index, resident in enumerate(residents):
        proof = proof_docs[index] if index < len(proof_docs) else allocation_doc
        expected = str(proof.get("archive", {}).get("output_sha256", "")).lower()
        same_map = proof.get("characters") == allocation_doc.get("characters")
        actual = sha256(resident)
        result.append({"path": str(resident), "sha256": actual,
                       "proof_sha256": expected,
                       "allocation_sha256_match": bool(expected and actual == expected),
                       "same_character_map": same_map})
    return result


def hangul_chars(text: str) -> set[str]:
    return {ch for ch in text if HANGUL(ch)}


def glyph_usage_rows(units: list[dict], common: set[str], scope: str,
                     scope_id: int) -> list[dict[str, object]]:
    usage: dict[str, list[dict]] = defaultdict(list)
    for unit in units:
        for ch in hangul_chars(str(unit["korean"])) - common:
            usage[ch].append(unit)
    rows = []
    for ch, owners in sorted(usage.items()):
        rows.append({
            "scope": scope,
            "scope_id": scope_id,
            "glyph": ch,
            "cost_bytes": GLYPH_SIZE,
            "line_count": len(owners),
            "row_ids": "|".join(str(x["row_id"]) for x in owners),
            "english": " || ".join(str(x.get("english", "")) for x in owners),
            "korean": " || ".join(str(x["korean"]) for x in owners),
            "saving_if_removed_from_scope": GLYPH_SIZE,
            "english_substitution": "not_generated",
        })
    return rows


def movie_slot_owners(record) -> list[set[int]]:
    count = len(record.font) // GLYPH_SIZE
    owners = [set() for _ in range(count)]
    for sub_index, subtitle in enumerate(record.subtitles):
        for slot in page3_indices(subtitle.raw):
            if slot < count:
                owners[slot].add(sub_index)
    return owners


def audit_media_file(media: str, source: Path, translation: Path,
                     static_map: dict[str, bytes]) -> tuple[list[dict], list[dict], dict]:
    data = source.read_bytes()
    _, records, _ = parse_records(data)
    by_offset = {s.offset: (record, i, s) for record in records
                 for i, s in enumerate(record.subtitles)}
    units_by_record: dict[int, list[dict]] = defaultdict(list)
    rejected = []
    for row in read_csv(translation):
        if row.get("accept", "yes").strip().lower() not in {"1", "y", "yes", "true", "ok", "o"}:
            continue
        offset = int(row["offset"])
        hit = by_offset.get(offset)
        if hit is None:
            rejected.append(offset)
            continue
        record, sub_index, subtitle = hit
        units_by_record[record.index].append({
            "row_id": row.get("three_ds_id") or f"{media}:{record.index}:{offset}",
            "record": record.index, "sub_index": sub_index, "offset": offset,
            "english": row.get("english", ""), "korean": row.get("korean", ""),
            "subtitle": subtitle,
        })

    scene_for_record: dict[int, int] = {}
    scene_pad: dict[int, int] = {}
    if media == "demo":
        blocks = walk_blocks(data)
        starts = scene_starts(data, blocks)
        bounds = scene_bounds(starts, len(data))
        for scene, (start, end) in enumerate(bounds):
            scene_pad[scene] = trailing_pad_run(data, end)
            for record in records:
                if start <= record.offset < end:
                    scene_for_record[record.index] = scene

    summaries, glyph_rows = [], []
    growth_by_scene: dict[int, int] = defaultdict(int)
    for record_index, record in enumerate(records):
        units = units_by_record.get(record_index, [])
        common_used = set().union(*(hangul_chars(x["korean"]) & set(static_map) for x in units))
        all_hangul = set().union(*(hangul_chars(x["korean"]) for x in units))
        local_needed = all_hangul - set(static_map)
        replaced_indices = {int(x["sub_index"]) for x in units}
        owners = movie_slot_owners(record)
        existing_dead = [i for i, refs in enumerate(owners) if not refs]
        freed_by_build = [i for i, refs in enumerate(owners) if refs and refs <= replaced_indices]
        available = sorted(set(existing_dead) | set(freed_by_build))
        appended_count = max(0, len(local_needed) - len(available))

        local_map = dict(static_map)
        assigned = available[:len(local_needed)] + list(
            range(len(record.font) // GLYPH_SIZE,
                  len(record.font) // GLYPH_SIZE + appended_count))
        local_map.update({ch: page3_token(slot) for ch, slot in zip(sorted(local_needed), assigned)})
        string_delta = 0
        string_increase = 0
        text_overflow = 0
        for unit in units:
            subtitle = unit["subtitle"]
            encoded = encode_translation(wrap_like_source(unit["korean"], subtitle.raw), local_map)
            capacity = len(subtitle.original) - 4 - len(subtitle.tail)
            delta = len(encoded) - len(subtitle.raw)
            string_delta += delta
            string_increase += max(0, delta)
            text_overflow += max(0, len(encoded) - capacity)

        natural_end = record.text_end + 4 + len(record.font)
        internal_slack = max(0, len(record.raw) - align(natural_end))
        record_growth = max(0, align(natural_end + appended_count * GLYPH_SIZE) - len(record.raw))
        scene = scene_for_record.get(record_index, -1)
        if scene >= 0:
            growth_by_scene[scene] += record_growth
        summary = {
            "media": media, "record": record_index, "scene": scene if scene >= 0 else "",
            "translation_rows": len(units), "used_hangul": "".join(sorted(all_hangul)),
            "common_glyphs": "".join(sorted(common_used)),
            "common_glyph_count": len(common_used),
            "new_glyphs": "".join(sorted(local_needed)), "new_glyph_count": len(local_needed),
            "glyph_add_bytes": len(local_needed) * GLYPH_SIZE,
            "existing_local_slots": len(record.font) // GLYPH_SIZE,
            "existing_dead_slots": len(existing_dead),
            "newly_freed_slots": len(freed_by_build),
            "glyph_reclaim_bytes": len(available) * GLYPH_SIZE,
            "donor_reclaim_bytes": 0,
            "string_reclaim_bytes": max(0, -string_delta),
            "appended_glyph_count": appended_count,
            "appended_glyph_bytes": appended_count * GLYPH_SIZE,
            "string_delta_bytes": string_delta, "string_increase_bytes": string_increase,
            "text_overflow_bytes": text_overflow, "internal_slack_bytes": internal_slack,
            "record_growth_bytes": record_growth,
            "final_headroom": max(0, internal_slack - appended_count * GLYPH_SIZE),
            "overflow_bytes": text_overflow + (record_growth if media == "movie" else 0),
            "row_ids": "|".join(str(x["row_id"]) for x in units),
            "confidence": "confirmed_binary_and_builder_logic",
        }
        summaries.append(summary)
        details = glyph_usage_rows(units, set(static_map), media, record_index)
        for detail in details:
            detail["scene"] = scene if scene >= 0 else ""
        glyph_rows.extend(details)

    if media == "demo":
        for row in summaries:
            scene = int(row["scene"])
            budget = scene_pad.get(scene, 0)
            growth = growth_by_scene[scene]
            row["scene_pad_budget"] = budget
            row["scene_total_growth"] = growth
            row["scene_final_headroom"] = max(0, budget - growth)
            row["scene_overflow_bytes"] = max(0, growth - budget)

    metadata = {"source": str(source), "source_sha256": sha256(source),
                "translation": str(translation), "translation_sha256": sha256(translation),
                "records": len(records), "matched_rows": sum(map(len, units_by_record.values())),
                "unmatched_offsets": rejected}
    return summaries, glyph_rows, metadata


def audit_codec(source: Path, translation: Path, static_map: dict[str, bytes]
                ) -> tuple[list[dict], list[dict], dict]:
    records = parse_codec(source.read_bytes())
    document = json.loads(translation.read_text(encoding="utf-8-sig"))
    document = dict(document)
    merged_map = dict(document.get("character_map", {}))
    merged_map.update({ch: token.hex().upper() for ch, token in static_map.items()})
    document["character_map"] = merged_map
    base_map, units = validate_codec_translation(document)
    by_gcx: dict[int, list[dict]] = defaultdict(list)
    for unit in units:
        gcx, resource = int(unit["gcx"]), int(unit["resource"])
        by_gcx[gcx].append({"row_id": f"codec:{gcx}:{resource}", "gcx": gcx,
                            "resource": resource, "english": "", "korean": str(unit["text"]),
                            "unit": unit})

    summaries, glyph_rows = [], []
    for gcx, record in enumerate(records):
        audit_units = by_gcx.get(gcx, [])
        resources = record.resources()
        changed = []
        for item in audit_units:
            resource = item["resource"]
            item["english"] = decode_mgs_preview(resources[resource].data)
            try:
                rendered = parse_rendered(item["korean"], base_map)
                if rendered != resources[resource].data:
                    changed.append(item)
            except CodecError:
                changed.append(item)
        replaced = {x["resource"] for x in changed}
        all_hangul = set().union(*(hangul_chars(x["korean"]) for x in changed)) if changed else set()
        common_used = all_hangul & set(static_map)
        local_needed = all_hangul - set(base_map)
        existing_dead = dead_font_slots(record, set())
        available = dead_font_slots(record, replaced)
        newly_freed = sorted(set(available) - set(existing_dead))
        appended_count = max(0, len(local_needed) - len(available))
        _, old_count = font_region(record)
        assigned = available[:len(local_needed)] + list(range(old_count, old_count + appended_count))
        local_map = dict(base_map)
        local_map.update({ch: custom_token(slot) for ch, slot in zip(sorted(local_needed), assigned)})
        replacements = {x["resource"]: parse_rendered(x["korean"], local_map) for x in changed}
        string_delta = sum(len(data) - len(resources[i].data) for i, data in replacements.items())
        string_increase = sum(max(0, len(data) - len(resources[i].data)) for i, data in replacements.items())
        old_region = record.font_data_offset - record.string_resources_offset
        target_region = old_region - appended_count * GLYPH_SIZE
        final_resource_bytes = sum(len(replacements.get(i, r.data)) for i, r in enumerate(resources))
        overflow = max(0, final_resource_bytes - target_region)
        headroom = max(0, target_region - final_resource_bytes)
        summaries.append({
            "media": "codec", "gcx": gcx, "pinned_record": "yes" if gcx == 53 else "no",
            "translation_rows": len(changed), "used_hangul": "".join(sorted(all_hangul)),
            "common_glyphs": "".join(sorted(common_used)), "common_glyph_count": len(common_used),
            "new_glyphs": "".join(sorted(local_needed)), "new_glyph_count": len(local_needed),
            "glyph_add_bytes": len(local_needed) * GLYPH_SIZE,
            "existing_local_slots": old_count, "existing_dead_slots": len(existing_dead),
            "newly_freed_slots": len(newly_freed),
            "glyph_reclaim_bytes": len(available) * GLYPH_SIZE,
            "donor_reclaim_bytes": 0,
            "string_reclaim_bytes": max(0, -string_delta),
            "appended_glyph_count": appended_count,
            "appended_glyph_bytes": appended_count * GLYPH_SIZE,
            "string_delta_bytes": string_delta, "string_increase_bytes": string_increase,
            "string_region_bytes": old_region, "final_headroom": headroom,
            "overflow_bytes": overflow,
            "row_ids": "|".join(x["row_id"] for x in changed),
            "confidence": "confirmed_binary_and_builder_logic",
            "layout_policy": "per_gcx_size_preserved; no record relocation",
        })
        glyph_rows.extend(glyph_usage_rows(changed, set(base_map), "codec", gcx))

    metadata = {"source": str(source), "source_sha256": sha256(source),
                "translation": str(translation), "translation_sha256": sha256(translation),
                "gcx_records": len(records), "translation_gcx": len(by_gcx)}
    return summaries, glyph_rows, metadata


def live_slot_inventory(media: str, path: Path) -> list[dict[str, object]]:
    rows = []
    if media in {"movie", "demo"}:
        _, records, _ = parse_records(path.read_bytes())
        for record in records:
            owners = movie_slot_owners(record)
            dead = [index for index, refs in enumerate(owners) if not refs]
            rows.append({"media": media, "scope": "record", "scope_id": record.index,
                         "font_table_offset": record.offset + record.text_end + 4,
                         "token_page": "0x90", "total_slots": len(owners),
                         "referenced_slots": len(owners) - len(dead), "dead_slots": len(dead),
                         "dead_slot_indices": "|".join(map(str, dead)),
                         "reusable_bytes": len(dead) * GLYPH_SIZE,
                         "reuse_primitive": "page3 token remap + overwrite 64B record font slot",
                         "cross_scope_reuse": "forbidden"})
    elif media == "codec":
        records = parse_codec(path.read_bytes())
        for gcx, record in enumerate(records):
            start, total = font_region(record)
            dead = dead_font_slots(record, set())
            rows.append({"media": media, "scope": "gcx", "scope_id": gcx,
                         "font_table_offset": record.source_offset + start,
                         "token_page": "0x8C", "total_slots": total,
                         "referenced_slots": total - len(dead), "dead_slots": len(dead),
                         "dead_slot_indices": "|".join(map(str, dead)),
                         "reusable_bytes": len(dead) * GLYPH_SIZE,
                         "reuse_primitive": "custom_token(index) + overwrite_font_slots()",
                         "cross_scope_reuse": "forbidden"})
    return rows


def aggregate_demo_scenes(rows: list[dict]) -> list[dict[str, object]]:
    groups: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("scene") != "":
            groups[int(row["scene"])].append(row)
    output = []
    for scene, records in sorted(groups.items()):
        used = set().union(*(set(str(r["used_hangul"])) for r in records))
        common = set().union(*(set(str(r["common_glyphs"])) for r in records))
        new = set().union(*(set(str(r["new_glyphs"])) for r in records))
        first = records[0]
        output.append({
            "media": "demo_scene", "scene": scene, "records": len(records),
            "translation_records": sum(int(r["translation_rows"]) > 0 for r in records),
            "translation_rows": sum(int(r["translation_rows"]) for r in records),
            "used_hangul": "".join(sorted(used)), "common_glyphs": "".join(sorted(common)),
            "common_glyph_count": len(common), "new_glyphs": "".join(sorted(new)),
            "new_glyph_count": len(new), "glyph_add_bytes": len(new) * GLYPH_SIZE,
            "glyph_reclaim_bytes": sum(int(r["glyph_reclaim_bytes"]) for r in records),
            "donor_reclaim_bytes": sum(int(r["donor_reclaim_bytes"]) for r in records),
            "string_reclaim_bytes": sum(int(r["string_reclaim_bytes"]) for r in records),
            "string_delta_bytes": sum(int(r["string_delta_bytes"]) for r in records),
            "string_increase_bytes": sum(int(r["string_increase_bytes"]) for r in records),
            "scene_pad_budget": int(first["scene_pad_budget"]),
            "scene_total_growth": int(first["scene_total_growth"]),
            "final_headroom": int(first["scene_final_headroom"]),
            "overflow_bytes": int(first["scene_overflow_bytes"]),
            "row_ids": "|".join(str(r["row_ids"]) for r in records if r["row_ids"]),
            "confidence": "confirmed_scene_markers_padding_and_builder_logic",
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-allocation", type=Path, required=True)
    parser.add_argument("--resident", type=Path, action="append", default=[])
    parser.add_argument("--resident-proof", type=Path, action="append", default=[],
                        help="allocation report corresponding to each --resident, in order")
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--live-movie", type=Path)
    parser.add_argument("--movie-translation", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--live-demo", type=Path)
    parser.add_argument("--demo-translation", type=Path)
    parser.add_argument("--codec", type=Path)
    parser.add_argument("--live-codec", type=Path)
    parser.add_argument("--codec-translation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    static_map, allocation_doc = load_static_allocation(args.static_allocation)
    proof_docs = [json.loads(path.read_text(encoding="utf-8-sig"))
                  for path in args.resident_proof]
    args.output.mkdir(parents=True, exist_ok=True)
    common_rows = [{"glyph": ch, "token": token.hex().upper(),
                    "physical_slot": physical_slot_for_token(token), "cost_if_reused": 0,
                    "evidence": "resident_allocation_table"}
                   for index, (ch, token) in enumerate(static_map.items())]
    write_csv(args.output / "common_glyphs.csv", common_rows)
    summaries: list[dict] = []
    glyph_rows: list[dict] = []
    scene_rows: list[dict] = []
    sources = {}
    if args.movie and args.movie_translation:
        rows, glyphs, meta = audit_media_file("movie", args.movie, args.movie_translation, static_map)
        write_csv(args.output / "movie_records.csv", rows)
        summaries.extend(rows); glyph_rows.extend(glyphs); sources["movie"] = meta
    if args.demo and args.demo_translation:
        rows, glyphs, meta = audit_media_file("demo", args.demo, args.demo_translation, static_map)
        write_csv(args.output / "demo_records.csv", rows)
        scene_rows = aggregate_demo_scenes(rows)
        write_csv(args.output / "demo_scenes.csv", scene_rows)
        summaries.extend(rows); glyph_rows.extend(glyphs); sources["demo"] = meta
    if args.codec and args.codec_translation:
        rows, glyphs, meta = audit_codec(args.codec, args.codec_translation, static_map)
        write_csv(args.output / "codec_gcx.csv", rows)
        summaries.extend(rows); glyph_rows.extend(glyphs); sources["codec"] = meta
    write_csv(args.output / "glyph_cost_details.csv", glyph_rows)
    overflow_movie = {int(r["record"]) for r in summaries
                      if r.get("media") == "movie" and int(r.get("overflow_bytes", 0))}
    overflow_demo_records = {int(r["record"]) for r in summaries
                             if r.get("media") == "demo" and
                             int(r.get("overflow_bytes", 0))}
    overflow_codec = {int(r["gcx"]) for r in summaries
                      if r.get("media") == "codec" and int(r.get("overflow_bytes", 0))}
    overflow_scenes = {int(r["scene"]) for r in scene_rows if int(r["overflow_bytes"])}
    overflow_glyphs = [r for r in glyph_rows if
        (r["scope"] == "movie" and int(r["scope_id"]) in overflow_movie) or
        (r["scope"] == "codec" and int(r["scope_id"]) in overflow_codec) or
        (r["scope"] == "demo" and
         (int(r["scope_id"]) in overflow_demo_records or
          (r.get("scene") != "" and int(r["scene"]) in overflow_scenes)))]
    write_csv(args.output / "overflow_glyphs.csv", overflow_glyphs)
    live_rows = []
    for media, path in (("movie", args.live_movie), ("demo", args.live_demo),
                        ("codec", args.live_codec)):
        if path:
            live_rows.extend(live_slot_inventory(media, path))
    write_csv(args.output / "live_local_slots.csv", live_rows)
    write_csv(args.output / "overflows.csv", [r for r in summaries + scene_rows
              if int(r.get("overflow_bytes", 0))])
    report = {
        "format": "mgs3d-glyph-space-audit-v1", "analysis_only": True,
        "glyph_size": GLYPH_SIZE, "static_allocation": str(args.static_allocation),
        "static_allocation_sha256": sha256(args.static_allocation),
        "common_glyph_count": len(static_map),
        "resident_verification": verify_resident(allocation_doc, args.resident, proof_docs),
        "sources": sources,
        "live_sources": {
            media: {"path": str(path), "sha256": sha256(path)}
            for media, path in (("movie", args.live_movie), ("demo", args.live_demo),
                                ("codec", args.live_codec)) if path
        },
        "summary": {"scopes": len(summaries), "glyph_detail_rows": len(glyph_rows),
                    "overflow_scopes": sum(bool(int(r.get("overflow_bytes", 0)))
                        for r in summaries + scene_rows),
                    "live_local_slot_scopes": len(live_rows),
                    "live_dead_slots": sum(int(r["dead_slots"]) for r in live_rows),
                    "live_reusable_bytes": sum(int(r["reusable_bytes"]) for r in live_rows)},
    }
    (args.output / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
