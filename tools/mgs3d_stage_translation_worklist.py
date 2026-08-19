#!/usr/bin/env python3
"""Prepare a read-only stage/scenerio translation worklist.

This consumes the existing output of mgs3d_stage_text_scan.py and the existing
stage_worklist_classify rules.  It does not parse or rewrite game files and it
does not translate text.  The generated CSV is a review/translation input only.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10**9)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_stage_worklist_classify import classify  # noqa: E402

PS2 = {
    "I see him!!": "있다!!",
    "Who's that!": "누구냐!",
    "Speak!": "말해!",
}

CATEGORY_ORDER = [
    "ENEMY_BARK", "NPC_DIALOGUE", "TUTORIAL_CONTROL", "ITEM_WEAPON",
    "MEDICINE", "FOOD", "FLORA_FAUNA", "INJURY", "AREA_NAME", "RESULTS",
    "TITLE_AWARD", "OTHER",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def join_values(values: list[str], limit: int = 8) -> str:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return " || ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", type=Path,
                    default=ROOT / "docs/evidence/2026-08-19-stage-text-scan")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "docs/evidence/2026-08-19-stage-translation-worklist")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    unique = read_csv(args.scan / "stage-text-unique.csv")
    locations = read_csv(args.scan / "stage-text-locations.csv")
    scan_summary = json.loads((args.scan / "stage-text-summary.json").read_text(encoding="utf-8"))

    # This is the same scope used by the established scan: English branch plus
    # shared/no-evidence strings that remain visible to an English/Korean build.
    scope = {
        r["raw_hex"]: r for r in unique
        if r["branch_span"] in {"english", "shared", "unknown"}
    }
    loc_by_raw: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in locations:
        if row["raw_hex"] in scope:
            loc_by_raw[row["raw_hex"]].append(row)

    # Context is taken from English-resolved rows in the same stage/GCX record,
    # ordered by resource.  It is evidence for the next session, never a match.
    sequence: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in locations:
        if row["raw_hex"] in scope and row["language"] == "english":
            sequence[(row["stage"], row["record"])].append(row)
    for rows in sequence.values():
        rows.sort(key=lambda r: int(r["resource"]))

    context: dict[str, tuple[list[str], list[str]]] = defaultdict(lambda: ([], []))
    for rows in sequence.values():
        for index, row in enumerate(rows):
            before, after = context[row["raw_hex"]]
            if index:
                before.append(rows[index - 1]["text"])
            if index + 1 < len(rows):
                after.append(rows[index + 1]["text"])

    rows_out: list[dict[str, str]] = []
    for item in scope.values():
        raw = item["raw_hex"]
        item_locations = loc_by_raw[raw]
        resource_numbers = {int(r["resource"]) for r in item_locations}
        stage_names = {r["stage"] for r in item_locations}
        category, basis = classify(item["text"], item["kind"], resource_numbers, stage_names)
        current_korean = PS2.get(item["text"], "")
        status = "READY" if current_korean else "UNTRANSLATED"
        source = "PS2_OFFICIAL" if current_korean else ""
        note = basis
        if item["branch_span"] in {"shared", "unknown"}:
            note += " | shared/unknown visible scope; verify branch before applying"
        if current_korean:
            note += " | confirmed PS2 correspondence; no further PS2 recovery"
        before, after = context[raw]
        locations_text = ";".join(
            f"{r['stage']}:{r['record']}:{r['resource']}" for r in item_locations
        )
        rows_out.append({
            "id": f"stage-{raw}",
            "english": item["text"],
            "category": category,
            "priority": CATEGORY_ORDER.index(category) + 1 if category in CATEGORY_ORDER else 99,
            "occurrences": item["locations"],
            "stage_count": item["stages"],
            "stage_locations": locations_text,
            "context_before": join_values(before),
            "context_after": join_values(after),
            "current_korean": current_korean,
            "source": source,
            "status": status,
            "note": note,
            "scan_basis": item["basis"],
            "branch_span": item["branch_span"],
            "kind": item["kind"],
            "raw_hex": raw,
        })

    # Priority first, then category, then most frequent strings.  No text is
    # edited; the three fixed PS2 rows are the only non-empty Korean cells.
    rows_out.sort(key=lambda r: (int(r["priority"]), -int(r["occurrences"]), r["english"]))
    fields = [
        "id", "english", "category", "priority", "occurrences", "stage_count",
        "stage_locations", "context_before", "context_after", "current_korean",
        "source", "status", "note", "scan_basis", "branch_span", "kind", "raw_hex",
    ]
    out_csv = args.out / "stage-translation-worklist.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows_out)

    category_counts = Counter(r["category"] for r in rows_out)
    category_locations = Counter()
    for r in rows_out:
        category_locations[r["category"]] += int(r["occurrences"])
    location_count = sum(len(loc_by_raw[r["raw_hex"]]) for r in rows_out)
    unique_count = len(rows_out)
    ready_count = sum(r["status"] == "READY" for r in rows_out)
    integrity = {
        "stage_files": scan_summary["stage_files"],
        "stage_files_pass": scan_summary["stage_files"] == 169,
        "branch_conflicts": scan_summary["diagnostics"]["conflicts"],
        "unique_en_scope": unique_count,
        "expected_unique_en_scope": scan_summary["korean_scope"]["total_unique"],
        "unique_match": unique_count == scan_summary["korean_scope"]["total_unique"],
        "english_occurrences": sum(int(r["occurrences"]) for r in rows_out),
        "expected_english_occurrences": scan_summary["korean_scope"]["total_locations"],
        "occurrence_match": sum(int(r["occurrences"]) for r in rows_out) == scan_summary["korean_scope"]["total_locations"],
        "location_rows_preserved": location_count == scan_summary["korean_scope"]["total_locations"],
        "location_loss": scan_summary["korean_scope"]["total_locations"] - location_count,
        "ready_rows": ready_count,
        "new_translation_rows": unique_count - ready_count,
        "category_unique": dict(category_counts),
        "category_occurrences": dict(category_locations),
        "output": str(out_csv),
        "source_scan": str(args.scan),
    }
    (args.out / "stage-translation-worklist-summary.json").write_text(
        json.dumps(integrity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(integrity, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
