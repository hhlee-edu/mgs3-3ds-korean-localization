#!/usr/bin/env python3
"""Read-only feasibility check for restoring PERSONAL DATA separators.

This never edits a master or DAT. It uses the clean English resource as the
layout authority and measures the current master Korean plus the missing LF
bytes against every duplicate location's original fixed resource slot.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10**9)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec, parse_rendered  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def locations(value: str) -> list[tuple[int, int]]:
    out = []
    for part in (value or "").split(";"):
        if ":" not in part:
            continue
        a, b = part.split(":", 1)
        try:
            out.append((int(a), int(b)))
        except ValueError:
            pass
    return out


def explicit_controls(text: str) -> tuple[str, ...]:
    # For this screen, 0A is the field separator and 00 is the terminator.
    # 80 is included in the report if present; 1F is deliberately excluded
    # because staged Korean glyph encodings can contain 1F as a glyph byte.
    return tuple(x.upper() for x in re.findall(r"<([0-9A-Fa-f]{2})>", text or "")
                 if int(x, 16) in (0x00, 0x0A, 0x80))


def raw_controls(data: bytes) -> tuple[str, ...]:
    return tuple(f"{x:02X}" for x in data if x in (0x00, 0x0A, 0x80))


def raw_fields(data: bytes) -> list[bytes]:
    body = data.split(b"\x00", 1)[0]
    return body.split(b"\x0A")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", type=Path, default=ROOT / "translation/10_master/current/codec.csv")
    ap.add_argument("--clean", type=Path, default=ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat")
    ap.add_argument("--staged", type=Path, default=ROOT / "builds/v0.91-codec-final/romfs/codec.dat")
    ap.add_argument("--character-map", type=Path, default=ROOT / "translation/40_build_input/global_page_v2/character-map.json")
    ap.add_argument("--out", type=Path, default=ROOT / "docs/evidence/2026-08-19-personal-data-feasibility")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    clean_records = parse_codec(args.clean.read_bytes())
    staged_records = parse_codec(args.staged.read_bytes())
    cmap_doc = json.loads(args.character_map.read_text(encoding="utf-8"))
    cmap = {k: bytes.fromhex(v) for k, v in cmap_doc.get("characters", {}).items()}
    master = [r for r in read_csv(args.master) if "PERSONAL DATA" in (r.get("english") or "")]

    rows: list[dict[str, object]] = []
    virtual_units: list[dict[str, object]] = []
    summary = Counter()
    seen_locations: set[tuple[int, int]] = set()
    for row in master:
        locs = locations(row.get("locations", ""))
        if not locs:
            continue
        canonical = locs[0]
        ci, cj = canonical
        clean_data = clean_records[ci].resources()[cj].data
        clean_seq = raw_controls(clean_data)
        clean_field_count = len(raw_fields(clean_data))
        korean = (row.get("korean") or "").strip()
        current_seq = explicit_controls(korean)
        current_bytes = 0
        encode_error = ""
        if korean:
            try:
                current_bytes = len(parse_rendered(korean, cmap))
            except Exception as exc:  # report, do not stop the audit
                encode_error = str(exc)
        missing_lf = max(0, clean_seq.count("0A") - current_seq.count("0A"))
        proposed_bytes = current_bytes + missing_lf if korean and not encode_error else current_bytes
        budgets = []
        staged_sequences = Counter()
        staged_mismatch_locations = 0
        for i, j in locs:
            if (i, j) in seen_locations:
                continue
            seen_locations.add((i, j))
            slot = len(clean_records[i].resources()[j].data)
            budgets.append(slot)
            staged_seq = raw_controls(staged_records[i].resources()[j].data)
            staged_sequences[" ".join(staged_seq)] += 1
            if staged_seq != clean_seq:
                staged_mismatch_locations += 1
        if not korean:
            verdict = "HUMAN"
            reason = "current Korean is blank; no automatic field reconstruction"
        elif encode_error:
            verdict = "HUMAN"
            reason = f"current Korean encoding failed: {encode_error}"
        else:
            budget = min(budgets)
            margin = budget - proposed_bytes
            deficit = max(0, -margin)
            if margin >= 0:
                verdict = "PASS"
                reason = "separator restoration only fits every duplicate resource slot"
            elif deficit <= 16:
                verdict = "SHORTEN"
                reason = f"separator restoration exceeds tightest slot by {deficit} bytes; modest label/value shortening required"
            else:
                verdict = "HARD"
                reason = f"separator restoration exceeds tightest slot by {deficit} bytes"
        if korean and not encode_error:
            # Scratch-only placement. This is not a proposed Korean layout;
            # it puts missing LF bytes before <00> solely to measure the exact
            # byte delta through expand_locations/capacity.
            body = korean[:-4] if korean.endswith("<00>") else korean
            virtual_units.append({
                "gcx": int(row.get("gcx") or ci),
                "resource": int(row.get("resource") or cj),
                "kind": "string",
                "text": body + ("<0A>" * missing_lf) + "<00>",
            })
        budget = min(budgets) if budgets else 0
        margin = budget - proposed_bytes if korean and not encode_error else ""
        failing = sum(proposed_bytes > x for x in budgets) if korean and not encode_error else 0
        summary[verdict] += 1
        rows.append({
            "gcx": ci,
            "resource": cj,
            "locations": ";".join(f"{i}:{j}" for i, j in locs),
            "location_count": len(locs),
            "english": row.get("english", ""),
            "current_korean": korean,
            "clean_field_count": clean_field_count,
            "current_field_count": 1 if korean else 0,
            "field_mapping": "ORDER_PRESERVABLE" if korean else "UNRESOLVED",
            "clean_control_sequence": " ".join(clean_seq),
            "current_control_sequence": " ".join(current_seq),
            "proposed_control_sequence": " ".join(clean_seq),
            "current_bytes": current_bytes,
            "proposed_bytes": proposed_bytes,
            "available_bytes": budget - current_bytes if korean and not encode_error else "",
            "byte_margin": margin,
            "min_slot_bytes": budget,
            "max_slot_bytes": max(budgets) if budgets else 0,
            "failing_locations": failing,
            "staged_sequence_counts": json.dumps(dict(staged_sequences), ensure_ascii=False),
            "staged_control_mismatch_locations": staged_mismatch_locations,
            "encode_error": encode_error,
            "verdict": verdict,
            "reason": reason,
        })

    fields = list(rows[0]) if rows else []
    with (args.out / "personal-data-layout-feasibility.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    (args.out / "personal-data-proposed-translation-dryrun.json").write_text(
        json.dumps({
            "format": "mgs3d-codec-translation-v1",
            "note": "Scratch-only mechanical separator byte simulation; not a translation or production input.",
            "units": virtual_units,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    location_rows = sum(int(r["location_count"]) for r in rows)
    failing_locations = sum(int(r["failing_locations"]) for r in rows)
    report = {
        "format": "mgs3d-personal-data-layout-feasibility-v1",
        "analysis_only": True,
        "master_or_dat_modified": False,
        "canonical_rows": len(rows),
        "unique_locations": location_rows,
        "verdicts": dict(summary),
        "separator_restoration": "0A x 9 + 00 from clean authority",
        "predicted_failing_locations": failing_locations,
        "predicted_failing_records": len({r["gcx"] for r in rows if int(r["failing_locations"]) > 0}),
        "predicted_total_slot_deficit": sum(max(0, -int(r["byte_margin"])) for r in rows if str(r["byte_margin"]).lstrip("-").isdigit()),
        "worst_deficit": min((int(r["byte_margin"]) for r in rows if str(r["byte_margin"]).lstrip("-").isdigit()), default=0),
        "new_glyph_required": False,
        "existing_translation_text_changed": 0,
        "field_mapping_human_rows": sum(r["field_mapping"] == "UNRESOLVED" for r in rows),
        "note": "Byte feasibility only; no proposed Korean text is written. Separator insertion is counted as missing 0A bytes.",
    }
    (args.out / "personal-data-layout-feasibility-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
