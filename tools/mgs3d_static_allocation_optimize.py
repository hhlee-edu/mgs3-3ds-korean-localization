#!/usr/bin/env python3
"""Choose static Hangul that unlock the most fixed-font codec rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from mgs3d_hpk_static_korean import (
    EXTENDED_STATIC_SLOTS,
    STATIC_SLOTS,
    token_for_allocation_slot,
)


def hangul(text: str) -> frozenset[str]:
    return frozenset(character for character in text
                     if 0xAC00 <= ord(character) <= 0xD7A3)


def optimize(translation: dict, report: dict, required_allocation: dict,
             slots: int = STATIC_SLOTS,
             additional_required: list[str] | None = None,
             allow_feasible_regressions: bool = False) -> dict:
    required = list(dict.fromkeys(required_allocation.get("required_hangul", [])))
    for text in additional_required or []:
        for character in text:
            if (0xAC00 <= ord(character) <= 0xD7A3 and character not in required):
                required.append(character)
    if not STATIC_SLOTS <= slots <= EXTENDED_STATIC_SLOTS:
        raise ValueError("static slots must be between 165 and 191")
    if len(required) > slots:
        raise ValueError("required allocation exceeds the static page")
    capacities = {
        int(row["gcx"]): int(row["glyph_limit"] or 0)
        for row in report["records"]
    }
    eligible = {
        (int(row["gcx"]), resource)
        for row in report["records"]
        for resource in row["candidate_resources"]
    }
    rows: list[tuple[int, frozenset[str]]] = []
    frequency: Counter[str] = Counter()
    memberships: dict[str, list[int]] = defaultdict(list)
    for unit in translation.get("units", []):
        key = (int(unit["gcx"]), int(unit["resource"]))
        if key not in eligible:
            continue
        characters = hangul(str(unit.get("text", "")))
        index = len(rows)
        rows.append((key[0], characters))
        frequency.update(str(unit.get("text", "")))
        for character in characters:
            memberships[character].append(index)

    selected = set(required)
    missing = [len(characters - selected) for _, characters in rows]
    choices = set(memberships) - selected
    selection_trace = []
    while len(selected) < slots and choices:
        gains: Counter[str] = Counter()
        for character in choices:
            gains[character] = sum(
                missing[index] == capacities.get(rows[index][0], 0) + 1
                for index in memberships[character]
            )
        character = max(choices, key=lambda item: (gains[item], frequency[item], -ord(item)))
        selected.add(character)
        choices.remove(character)
        for index in memberships[character]:
            missing[index] -= 1
        selection_trace.append({
            "character": character,
            "new_individually_feasible_rows": gains[character],
            "frequency": frequency[character],
        })

    optional = [row["character"] for row in selection_trace]
    unselected = set(memberships) - selected
    swap_trace = []
    while optional and unselected:
        current_score = sum(
            count <= capacities.get(rows[index][0], 0)
            for index, count in enumerate(missing)
        )
        best: tuple[int, int, int, int, str, str] | None = None
        for outgoing in optional:
            outgoing_rows = set(memberships[outgoing])
            for incoming in unselected:
                affected = outgoing_rows | set(memberships[incoming])
                score = current_score
                lost = 0
                for index in affected:
                    limit = capacities.get(rows[index][0], 0)
                    before = missing[index] <= limit
                    after_missing = (missing[index]
                                     + (outgoing in rows[index][1])
                                     - (incoming in rows[index][1]))
                    lost += before and after_missing > limit
                    score += (after_missing <= limit) - before
                if lost and not allow_feasible_regressions:
                    continue
                gain = score - current_score
                candidate = (gain, frequency[incoming], -frequency[outgoing],
                             -ord(incoming), outgoing, incoming)
                if best is None or candidate > best:
                    best = candidate
        if best is None or best[0] <= 0:
            break
        gain, _, _, _, outgoing, incoming = best
        position = optional.index(outgoing)
        optional[position] = incoming
        selected.remove(outgoing)
        selected.add(incoming)
        unselected.remove(incoming)
        unselected.add(outgoing)
        for index in set(memberships[outgoing]) | set(memberships[incoming]):
            missing[index] += ((outgoing in rows[index][1])
                               - (incoming in rows[index][1]))
        swap_trace.append({
            "out": outgoing,
            "in": incoming,
            "feasible_row_gain": gain,
            "allow_feasible_regressions": allow_feasible_regressions,
        })

    ordered = required + optional
    individually_feasible = sum(
        count <= capacities.get(rows[index][0], 0)
        for index, count in enumerate(missing)
    )
    return {
        "format": "mgs3d-static-korean-allocation-optimized-v1",
        "characters": {
            character: token_for_allocation_slot(slot).hex().upper()
            for slot, character in enumerate(ordered)
        },
        "required_hangul": required,
        "eligible_codec_rows": len(rows),
        "individually_feasible_codec_rows": individually_feasible,
        "selection_trace": selection_trace,
        "swap_trace": swap_trace,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("translation", type=Path)
    parser.add_argument("fixed_slot_report", type=Path)
    parser.add_argument("required_allocation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--slots", type=int, default=STATIC_SLOTS)
    parser.add_argument("--required-csv", type=Path)
    parser.add_argument("--required-offset", type=int, action="append")
    parser.add_argument(
        "--allow-feasible-regressions", action="store_true",
        help="allow a higher total that makes previously feasible rows infeasible",
    )
    args = parser.parse_args()
    additional_required: list[str] = []
    if args.required_csv:
        offsets = set(args.required_offset or [])
        with args.required_csv.open(encoding="utf-8-sig", newline="") as stream:
            additional_required.extend(
                row.get("korean", "") for row in csv.DictReader(stream)
                if not offsets or int(row["offset"]) in offsets
            )
    result = optimize(
        json.loads(args.translation.read_text(encoding="utf-8-sig")),
        json.loads(args.fixed_slot_report.read_text(encoding="utf-8-sig")),
        json.loads(args.required_allocation.read_text(encoding="utf-8-sig")),
        args.slots,
        additional_required,
        args.allow_feasible_regressions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(
        f"allocated {len(result['characters'])}/{args.slots}; "
        f"individually feasible codec rows "
        f"{result['individually_feasible_codec_rows']}/{result['eligible_codec_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
