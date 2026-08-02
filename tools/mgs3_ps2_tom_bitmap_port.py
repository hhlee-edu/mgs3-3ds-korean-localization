#!/usr/bin/env python3
"""Port an ordered PS2 Korean resource range using its official glyph bitmaps.

This avoids Unicode/OCR entirely: every PS2 static or record-local glyph used
by the selected resources is copied into new MGS3D record-local glyph slots.
Inactive Western-language resources listed by the donor audit fund the added
font while the GCX and codec sizes remain byte-for-byte fixed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3_ps2_font_sheet import GLYPH_SIZE as PS2_GLYPH_SIZE, decode_glyph  # noqa: E402
from mgs3_ps2_korean_port import replace_font  # noqa: E402
from mgs3d_codec_tool import CodecError, GcxRecord, parse_codec  # noqa: E402
from mgs3d_gcx_font_tool import GLYPH_SIZE, custom_token, encode_glyph  # noqa: E402
from mgs3d_text_reassembler import custom_glyph_index, split_static_lead, tokenize  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def static_slot(raw: bytes) -> int | None:
    if len(raw) != 2 or raw[1] == 0:
        return None
    split = split_static_lead(raw[0])
    if split is None:
        return None
    page, _flags = split
    starts = {0x81: 0, 0x82: 81, 0x83: 165}
    if page not in starts:
        return None
    return starts[page] + raw[1] - 1


def ps2_local_glyph(record: GcxRecord, index: int) -> bytes:
    start = record.block_start + record.font_data_offset + 4 + index * PS2_GLYPH_SIZE
    end = start + PS2_GLYPH_SIZE
    font_end = record.block_start + record.proc_offset
    if end > font_end:
        raise CodecError(f"PS2 local glyph {index} exceeds the font section")
    image = decode_glyph(record.raw[start:end]).resize((16, 16), Image.Resampling.LANCZOS)
    return encode_glyph(image, "linear")


def load_static_glyphs(entry: bytes) -> list[bytes]:
    if len(entry) < 8:
        raise CodecError("truncated PS2 static-font entry")
    offset = struct.unpack_from("<I", entry, 4)[0]
    payload = entry[offset:]
    if len(payload) % GLYPH_SIZE:
        raise CodecError("PS2 static-font payload is not 64-byte aligned")
    return [payload[pos:pos + GLYPH_SIZE] for pos in range(0, len(payload), GLYPH_SIZE)]


def donor_indices(path: Path, gcx: int) -> list[int]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        return [int(row["resource"]) for row in rows
                if int(row["gcx"]) == gcx and row["language"] in ("es", "fr")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ps2_codec", type=Path)
    ap.add_argument("ps2_static_entry", type=Path)
    ap.add_argument("target_codec", type=Path)
    ap.add_argument("donor_audit", type=Path)
    ap.add_argument("output_codec", type=Path)
    ap.add_argument("report", type=Path)
    ap.add_argument("--ps2-gcx", type=int, default=245)
    ap.add_argument("--target-gcx", type=int, default=243)
    ap.add_argument("--start", type=int, default=300)
    ap.add_argument("--end", type=int, default=440)
    args = ap.parse_args()

    source_raw = args.ps2_codec.read_bytes()
    target_raw = args.target_codec.read_bytes()
    source = parse_codec(source_raw)[args.ps2_gcx]
    records = parse_codec(target_raw)
    target = records[args.target_gcx]
    source_resources = source.resources()
    target_resources = target.resources()
    if args.end >= min(len(source_resources), len(target_resources)):
        raise CodecError("selected resource range exceeds source or target record")

    old_font_start = target.block_start + target.font_data_offset
    old_font_end = target.block_start + target.proc_offset
    old_font = target.raw[old_font_start + 4:old_font_end]
    if len(old_font) % GLYPH_SIZE:
        raise CodecError("target local font is not 64-byte aligned")
    old_count = len(old_font) // GLYPH_SIZE
    static = load_static_glyphs(args.ps2_static_entry.read_bytes())

    identities: dict[tuple[str, int], bytes] = {}
    glyphs: list[bytes] = []

    def mapped(identity: tuple[str, int]) -> bytes:
        if identity in identities:
            return identities[identity]
        kind, index = identity
        if kind == "static":
            if index >= len(static):
                raise CodecError(f"PS2 static glyph {index} exceeds {len(static)} slots")
            glyph = static[index]
        else:
            glyph = ps2_local_glyph(source, index)
        slot = old_count + len(glyphs)
        token = custom_token(slot)
        identities[identity] = token
        glyphs.append(glyph)
        return token

    replacements: dict[int, bytes] = {}
    for resource_index in range(args.start, args.end + 1):
        src = source_resources[resource_index]
        dst = target_resources[resource_index]
        if src.is_script != dst.is_script:
            raise CodecError(f"resource flag mismatch at {resource_index}")
        if src.is_script:
            continue
        output = bytearray()
        for token in tokenize(src.data):
            slot = static_slot(token.raw)
            local = custom_glyph_index(token.raw, 2)
            if slot is not None:
                output.extend(mapped(("static", slot)))
            elif local is not None:
                output.extend(mapped(("local", local)))
            else:
                output.extend(token.raw)
        replacements[resource_index] = bytes(output)

    donors = [index for index in donor_indices(args.donor_audit, args.target_gcx)
              if not args.start <= index <= args.end]
    replacements.update({index: b"\0" for index in donors})
    new_font = old_font + b"".join(glyphs)
    if len(new_font) // GLYPH_SIZE > 1020:
        raise CodecError("ported font exceeds the page-2 custom glyph capacity")

    old_string_size = target.font_data_offset - target.string_resources_offset
    font_growth = len(new_font) - len(old_font)
    string_budget = old_string_size - font_growth
    if string_budget < 0:
        raise CodecError("font growth exceeds the complete string region")
    with_strings = GcxRecord(target.replace_resources(
        replacements, string_region_size=string_budget
    ))
    rebuilt = replace_font(with_strings, new_font)
    if len(rebuilt) != len(target.raw):
        raise CodecError(f"GCX size changed: {len(target.raw)} -> {len(rebuilt)}")

    output = bytearray()
    for index, record in enumerate(records):
        output.extend(rebuilt if index == args.target_gcx else record.raw)
    if len(output) != len(target_raw):
        raise CodecError(f"codec size changed: {len(target_raw)} -> {len(output)}")
    parse_codec(bytes(output))

    args.output_codec.parent.mkdir(parents=True, exist_ok=True)
    args.output_codec.write_bytes(output)
    report = {
        "format": "mgs3d-ps2-tom-bitmap-port-v1",
        "source_ps2_sha256": sha256(source_raw),
        "target_sha256": sha256(target_raw),
        "output_sha256": sha256(output),
        "ps2_gcx": args.ps2_gcx,
        "target_gcx": args.target_gcx,
        "resources": [args.start, args.end],
        "changed_strings": len(replacements) - len(donors),
        "cleared_donors": len(donors),
        "old_local_glyphs": old_count,
        "added_official_glyphs": len(glyphs),
        "final_local_glyphs": len(new_font) // GLYPH_SIZE,
        "gcx_size": len(rebuilt),
        "codec_size": len(output),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
