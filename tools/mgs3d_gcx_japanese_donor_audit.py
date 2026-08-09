#!/usr/bin/env python3
"""Investigate whether a specific GCX's custom-glyph table is a Japanese
donor-language block (same shape as the existing French/Spanish donor
pipeline's language_block_donors(), mgs3d_codec_size_neutral_select.py:
an English block followed by one contiguous foreign-language block running
to the end of the GCX) -- and, if so, how many of its glyphs are referenced
*only* by resources inside that block (safe to reclaim intra-GCX, once the
block is deliberately blanked like any other donor language).

Reports intra-GCX conclusions ONLY. Never proposes or implies cross-GCX
glyph-pool sharing -- each GCX's custom-glyph table is confirmed
independent (see mgs3d_gcx_dead_slot_audit.py's cross_gcx_independence
note); a resource's glyphs are not transferable to a different GCX's token
space no matter how "similar" the two records look.

Historical note (2026-08-09): this GCX (1412) was originally identified as
a 986-glyph Japanese kanji donor candidate from
`backup_original_dat/codec.dat` (37,141,696 bytes). That file was later
confirmed to be the JAPANESE-SKU codec.dat, not the English one -- the real
English pristine original (`unpacked_en_original_smoke_backup/codec.dat`,
67,204,976 bytes, matching the live production file's size) has GCX 1412
with ZERO custom-glyph slots. This tool is kept general-purpose and can be
pointed at any GCX/codec.dat pair; running it against GCX 1412 of the real
English codec.dat (below) documents the correction rather than repeating
the original mistake.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, sha256  # noqa: E402
from mgs3d_gcx_font_tool import font_region, glyph_slot_owners  # noqa: E402


WORDS = re.compile(rb"[A-Za-z]+")
# Token ranges that are NOT this GCX's own 0x8C-page custom glyphs: 0x81/82
# (Hiragana/Katakana in the Japanese text-decoding scheme, see
# decode_mgs_preview in mgs3d_codec_tool.py) and 0x83 (Japanese punctuation
# in the same scheme). A resource dominated by these, with near-zero ASCII
# words, is a Japanese-block candidate.
JAPANESE_TOKEN_LEAD_BYTES = (0x81, 0x82, 0x83)


def token_composition(data: bytes) -> dict[str, int]:
    japanese_bytes = ascii_words = other_high_bytes = cursor = 0
    while cursor < len(data) and data[cursor]:
        byte = data[cursor]
        if byte in JAPANESE_TOKEN_LEAD_BYTES and cursor + 1 < len(data):
            japanese_bytes += 2
            cursor += 2
        elif byte >= 0x80 and cursor + 1 < len(data):
            other_high_bytes += 2
            cursor += 2
        else:
            cursor += 1
    ascii_words = len(WORDS.findall(data))
    return {"japanese_token_bytes": japanese_bytes, "ascii_words": ascii_words,
            "other_high_bytes": other_high_bytes, "length": len(data)}


def audit_gcx(codec_path: Path, gcx: int) -> dict[str, object]:
    data = codec_path.read_bytes()
    records = parse_codec(data)
    if not 0 <= gcx < len(records):
        raise SystemExit(f"GCX {gcx} out of range (file has {len(records)} records)")
    record = records[gcx]
    _, total_slots = font_region(record)
    resources = record.resources()

    if total_slots == 0:
        return {
            "codec_sha256": sha256(data),
            "gcx": gcx,
            "total_slots": 0,
            "verdict": "no custom-glyph table in this GCX for this codec.dat -- "
                       "not a donor candidate here",
            "resource_count": len(resources),
        }

    owners = glyph_slot_owners(resources, total_slots)
    per_resource = []
    japanese_block_resources: set[int] = set()
    for index, resource in enumerate(resources):
        comp = token_composition(resource.data)
        is_japanese_dominant = (
            comp["japanese_token_bytes"] > 0
            and comp["ascii_words"] == 0
            and comp["japanese_token_bytes"] >= comp["other_high_bytes"]
        )
        if is_japanese_dominant:
            japanese_block_resources.add(index)
        per_resource.append({
            "resource": index, "is_script": resource.is_script,
            "japanese_dominant": is_japanese_dominant, **comp,
        })

    slots_owned_only_by_japanese_block = [
        slot for slot, refs in enumerate(owners)
        if refs and refs <= japanese_block_resources
    ]
    slots_owned_partly_outside = [
        slot for slot, refs in enumerate(owners)
        if refs and not (refs <= japanese_block_resources) and refs & japanese_block_resources
    ]
    unowned = [slot for slot, refs in enumerate(owners) if not refs]
    japanese_block_is_script_count = sum(
        1 for index in japanese_block_resources if resources[index].is_script
    )

    return {
        "codec_sha256": sha256(data),
        "gcx": gcx,
        "total_slots": total_slots,
        "resource_count": len(resources),
        "japanese_block_resource_count": len(japanese_block_resources),
        "japanese_block_is_script_count": japanese_block_is_script_count,
        "slots_owned_only_by_japanese_block": len(slots_owned_only_by_japanese_block),
        "slots_owned_partly_outside_block": len(slots_owned_partly_outside),
        "unowned_slots": len(unowned),
        "safe_to_reclaim_intra_gcx_if_block_blanked": (
            len(slots_owned_only_by_japanese_block)
            if japanese_block_is_script_count == 0 and slots_owned_partly_outside == []
            else 0
        ),
        "verdict": (
            f"{len(slots_owned_only_by_japanese_block)}/{total_slots} glyphs are owned "
            "ONLY by a detected Japanese-dominant resource block; safe to reclaim "
            "intra-GCX-1412-only IF that block is deliberately blanked as a donor "
            "(same as any other donor language) AND cleared through the existing "
            "mgs3d_codec_donor_audit.py-style gate first -- not a free dead-slot case"
            if slots_owned_only_by_japanese_block
            else "no Japanese-dominant resource block found referencing these glyphs"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("--gcx", type=int, default=1412)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = audit_gcx(args.codec, args.gcx)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
