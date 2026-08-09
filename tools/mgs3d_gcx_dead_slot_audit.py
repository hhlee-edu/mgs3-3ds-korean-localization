#!/usr/bin/env python3
"""Independently re-verify a dead-glyph-slot inventory before it is trusted
for reuse. Follows mgs3d_codec_donor_audit.py's methodology: never trust the
tool that proposed a reuse, re-derive the safety property from raw source
bytes via a genuinely different code path, and fail loudly on discrepancy.

Two independent implementations of "which slots are referenced" already
exist:
  - glyph_slot_owners()/dead_font_slots() (mgs3d_gcx_font_tool.py): precise,
    per-resource, boundary-respecting scan. This is what the inventory
    (mgs3d_gcx_dead_slot_inventory.py) is built on.
  - freed_font_slots() (mgs3d_gcx_font_tool.py): a cruder, raw cross-resource
    substring join. It can only UNDER-report dead slots (a spurious
    cross-boundary token match makes it more conservative, never less), so
    it is a valid, independent lower bound.

This audit re-derives dead slots for every GCX in the inventory using the
raw-join method and requires inventory-claimed-dead to be a superset of (or
equal to) the raw-join result. Any slot dead only per the precise scanner is
tagged "precise-only" rather than "confirmed-by-two-methods"; a production
build should default to consuming only the latter.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, sha256  # noqa: E402
from mgs3d_gcx_font_tool import font_region, freed_font_slots  # noqa: E402


FORMAT = "mgs3d-codec-dead-glyph-audit-v1"


def audit(codec_path: Path, inventory_path: Path) -> dict[str, object]:
    data = codec_path.read_bytes()
    records = parse_codec(data)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

    if inventory.get("source_codec_sha256") != sha256(data):
        raise SystemExit(
            "inventory was built against a different codec.dat "
            f"(inventory sha256={inventory.get('source_codec_sha256')}, "
            f"current sha256={sha256(data)}) -- re-run the inventory first"
        )

    results: list[dict[str, object]] = []
    overlap_failures: list[dict[str, object]] = []
    for row in inventory["records"]:
        gcx = int(row["gcx"])
        record = records[gcx]
        _, total = font_region(record)
        claimed_dead = set(row["dead_slot_indices"])
        raw_join_dead = set(freed_font_slots(record, set()))

        # claimed_dead must be a superset of the independent lower bound.
        missing_from_claim = raw_join_dead - claimed_dead
        if missing_from_claim:
            overlap_failures.append({
                "gcx": gcx,
                "reason": "raw-join scanner found dead slots the inventory did not claim",
                "slots": sorted(missing_from_claim),
            })

        confirmed = sorted(claimed_dead & raw_join_dead)
        precise_only = sorted(claimed_dead - raw_join_dead)
        results.append({
            "gcx": gcx,
            "total_slots": total,
            "claimed_dead": sorted(claimed_dead),
            "confirmed_by_two_methods": confirmed,
            "precise_only": precise_only,
        })

    summary = {
        "gcx_audited": len(results),
        "gcx_with_overlap_failure": len(overlap_failures),
        "total_confirmed_by_two_methods": sum(len(r["confirmed_by_two_methods"]) for r in results),
        "total_precise_only": sum(len(r["precise_only"]) for r in results),
        # Structural facts, verified by code inspection (see docstring/plan):
        "cross_gcx_independence": (
            "every glyph_slot_owners()/freed_font_slots() lookup is scoped to "
            "one GcxRecord.resources()/font_region() call; font_data_offset "
            "and proc_offset are per-record fields (mgs3d_codec_tool.py "
            "GcxRecord.__init__); no table anywhere is shared across GCX"
        ),
        "shared_pool_contrast": (
            "the HPK static-font system (mgs3d_hpk_static_korean.py) is the "
            "one real shared/global glyph pool in this game (a single "
            "191-slot table addressed via 0x81/82/83 tokens, shared across "
            "the whole static-text UI); codec.dat's per-GCX 0x8C-page custom "
            "glyphs have no equivalent -- confirmed not touched by this tool"
        ),
        "bitmap_only_sufficiency": (
            "font_region() parses exactly [u32 payload_size][64-byte glyph]*; "
            "GcxRecord's block header has exactly 5 fields "
            "(proc_offset, resource_table_offset, string_resources_offset, "
            "font_data_offset, seed), none a metrics/width table; "
            "decode_glyph/encode_glyph hard-code 16x16 -- a bitmap-only "
            "overwrite via overwrite_font_slots() needs no separate metric "
            "update, already validated at scale by prior Hangul builds"
        ),
    }
    return {
        "format": FORMAT,
        "codec_sha256": sha256(data),
        "records": results,
        "overlap_failures": overlap_failures,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = audit(args.codec, args.inventory)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    summary = report["summary"]
    print(
        f"audited {summary['gcx_audited']} GCX: "
        f"{summary['total_confirmed_by_two_methods']} slots confirmed dead by "
        f"both scanners, {summary['total_precise_only']} precise-scanner-only"
    )
    if report["overlap_failures"]:
        print(
            f"FAIL: {len(report['overlap_failures'])} GCX have slots the raw-join "
            f"scanner considers dead but the inventory did not claim -- "
            f"re-run the inventory, do not trust it as-is"
        )
        return 1
    print("PASS: inventory's claimed-dead set is a superset of the independent lower bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
