#!/usr/bin/env python3
"""Fill missing duplicate Codec targets without changing existing selections."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402


def hangul(text: str) -> set[str]:
    return {ch for ch in text if "가" <= ch <= "힣"}


def encoded_size(text: str, old_count: int) -> int:
    del old_count  # Every custom Hangul token occupies exactly two bytes.
    size = cursor = 0
    while cursor < len(text):
        if (cursor + 3 < len(text) and text[cursor] == "<" and text[cursor + 3] == ">"
                and all(ch in "0123456789abcdefABCDEF" for ch in text[cursor + 1:cursor + 3])):
            size += 1
            cursor += 4
        else:
            size += 2 if "가" <= text[cursor] <= "힣" else 1
            cursor += 1
    return size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("selection_report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("candidate", type=Path, nargs="+")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--max-glyphs", type=int, default=100)
    args = parser.parse_args()

    records = parse_codec(args.codec.read_bytes())
    print("parsed codec", flush=True)
    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    current_units = document.get("units", [])
    current = {(int(x["gcx"]), int(x["resource"])): str(x["text"])
               for x in current_units if str(x["text"]) != "<00>"}
    all_candidates = {}
    for path in args.candidate:
        units = json.loads(path.read_text(encoding="utf-8-sig")).get("units", [])
        for row in units:
            if str(row["text"]) != "<00>":
                all_candidates[(int(row["gcx"]), int(row["resource"]))] = str(row["text"])
    print("loaded translations", flush=True)

    reports = {int(x["gcx"]): x for x in json.loads(
        args.selection_report.read_text(encoding="utf-8"))["records"]}
    foreign = {(gcx, int(resource)) for gcx, row in reports.items()
               for resource in row.get("foreign_block_excluded_resources", [])}
    resource_cache = {}

    def resources_for(gcx: int):
        if gcx not in resource_cache:
            resource_cache[gcx] = records[gcx].resources()
        return resource_cache[gcx]

    by_raw = defaultdict(list)
    for key, text in current.items():
        gcx, resource = key
        by_raw[resources_for(gcx)[resource].data].append(text)

    states = {}
    for gcx, row in reports.items():
        resources = resources_for(gcx)
        selected = {resource: text for (row_gcx, resource), text in current.items()
                    if row_gcx == gcx}
        states[gcx] = {"resources": resources, "old_count": 0,
                       "donor_savings": int(row.get("donor_savings", 0)),
                       "free_slots": int(row.get("reused_glyph_slots", 0)),
                       "selected": selected}
    print("built GCX states", flush=True)

    size_cache = {}

    def size_for(gcx: int, text: str) -> int:
        # Custom glyph tokens are always two bytes; the old slot index changes
        # their value, not encoded length, so duplicate text is globally cacheable.
        key = text
        if key not in size_cache:
            size_cache[key] = encoded_size(text, states[gcx]["old_count"])
        return size_cache[key]

    for gcx, state in states.items():
        selected = state["selected"]
        state["glyphs"] = (set().union(*(hangul(text) for text in selected.values()))
                           if selected else set())
        state["savings"] = state["donor_savings"] + sum(
            len(state["resources"][resource].data) - size_for(gcx, text)
            for resource, text in selected.items())

    proposals = []
    for key in sorted(set(all_candidates) - set(current) - foreign):
        gcx, resource = key
        raw = resources_for(gcx)[resource].data
        texts = set(by_raw.get(raw, []))
        if not texts or gcx not in states:
            continue
        # Prefer a user's compact duplicate variant; stable lexical order breaks ties.
        text = min(texts, key=lambda x: (size_for(gcx, x),
                                         len(hangul(x)), x))
        proposals.append((gcx, resource, text))
    print(f"built {len(proposals)} proposals", flush=True)

    added = []
    rejected = []
    for gcx, resource, text in proposals:
        state = states[gcx]
        trial_glyphs = state["glyphs"] | hangul(text)
        trial_savings = (state["savings"] + len(state["resources"][resource].data)
                         - size_for(gcx, text))
        glyph_count = len(trial_glyphs)
        net = trial_savings - max(0, glyph_count - state["free_slots"]) * 64
        if glyph_count <= args.max_glyphs and net >= 0:
            state["selected"][resource] = text
            state["glyphs"] = trial_glyphs
            state["savings"] = trial_savings
            current[(gcx, resource)] = text
            added.append({"gcx": gcx, "resource": resource, "text": text,
                          "glyphs": glyph_count, "headroom": net})
        else:
            rejected.append({"gcx": gcx, "resource": resource, "text": text,
                             "glyphs": glyph_count, "headroom": net})
    print("evaluated proposals", flush=True)

    units_by_key = {(int(x["gcx"]), int(x["resource"])): dict(x) for x in document["units"]}
    for row in added:
        units_by_key[(row["gcx"], row["resource"])] = {
            "gcx": row["gcx"], "resource": row["resource"], "kind": "string",
            "text": row["text"],
        }
    output = dict(document)
    output["units"] = sorted(units_by_key.values(), key=lambda x: (int(x["gcx"]), int(x["resource"])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_doc = {"proposals": len(proposals), "added": added, "rejected": rejected}
    if args.report:
        args.report.write_text(json.dumps(report_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"duplicate completion: {len(added)}/{len(proposals)} added, {len(rejected)} capacity-rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
