#!/usr/bin/env python3
"""Port structurally matching PS2 official-Korean GCX text/fonts to MGS3D."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import struct
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3_ps2_font_sheet import GLYPH_SIZE as PS2_GLYPH_SIZE, decode_glyph  # noqa: E402
from mgs3d_codec_tool import GcxRecord, align, parse_codec  # noqa: E402
from mgs3d_gcx_font_tool import encode_glyph  # noqa: E402


def signature(record: GcxRecord) -> tuple[int, int]:
    return len(record.proc_table), resource_count(record)


def resource_count(record: GcxRecord) -> int:
    return (record.string_resources_offset - record.resource_table_offset) // 4


def correspondence(ps2: list[GcxRecord], target: list[GcxRecord]) -> list[tuple[int, int, str]]:
    matcher = difflib.SequenceMatcher(
        None, [signature(r) for r in ps2], [signature(r) for r in target], autojunk=False
    )
    pairs: list[tuple[int, int, str]] = []
    for tag, a1, a2, b1, b2 in matcher.get_opcodes():
        if tag == "equal":
            pairs.extend((a1 + n, b1 + n, "exact-structure") for n in range(a2 - a1))
        elif tag == "replace" and a2 - a1 == b2 - b1:
            # Equal-length blocks bounded by exact monotonic anchors represent
            # platform/locale variants whose resource counts differ, while
            # preserving GCX sequence identity.
            pairs.extend((a1 + n, b1 + n, "anchored-equal-length")
                         for n in range(a2 - a1))
    return pairs


def convert_font(record: GcxRecord) -> bytes:
    start = record.block_start + record.font_data_offset
    end = record.block_start + record.proc_offset
    if end - start == 4:
        return b""
    payload = struct.unpack_from("<I", record.raw, start)[0]
    if payload != end - start - 4 or payload % PS2_GLYPH_SIZE:
        raise ValueError("invalid PS2 GCX font section")
    output = bytearray()
    for offset in range(start + 4, end, PS2_GLYPH_SIZE):
        source = decode_glyph(record.raw[offset:offset + PS2_GLYPH_SIZE])
        reduced = source.resize((16, 16), Image.Resampling.LANCZOS)
        output.extend(encode_glyph(reduced, "linear"))
    return bytes(output)


def replace_font(record: GcxRecord, font: bytes) -> bytes:
    old_start = record.block_start + record.font_data_offset
    old_end = record.block_start + record.proc_offset
    section = struct.pack("<I", len(font)) + font
    output = bytearray(record.raw[:old_start] + section + record.raw[old_end:])
    delta = len(section) - (old_end - old_start)
    struct.pack_into("<I", output, record.block_start, record.proc_offset + delta)
    logical = GcxRecord(bytes(output)).logical_size()
    del output[logical:]
    output.extend(b"\0" * (align(len(output)) - len(output)))
    return bytes(output)


def page2_references(record: GcxRecord) -> list[tuple[int, int]]:
    """Return (resource, glyph index) for visible 8C01..8FFF tokens."""
    result: list[tuple[int, int]] = []
    for resource_index, resource in enumerate(record.resources()):
        visible = resource.data.split(b"\0", 1)[0]
        cursor = 0
        while cursor + 1 < len(visible):
            value = int.from_bytes(visible[cursor:cursor + 2], "big")
            if 0x8C01 <= value < 0x9000 and visible[cursor + 1] != 0:
                relative = value - 0x8C01
                result.append((resource_index, relative - relative // 256))
                cursor += 2
            else:
                cursor += 1
    return result


def validate_ported_record(record: GcxRecord) -> int:
    font_size = record.proc_offset - record.font_data_offset - 4
    if font_size < 0 or font_size % 64:
        raise ValueError("invalid 3DS font section size")
    glyph_count = font_size // 64
    references = page2_references(record)
    bad = [(resource, glyph) for resource, glyph in references if glyph >= glyph_count]
    if bad:
        raise ValueError(
            f"{len(bad)} page-2 references exceed {glyph_count} converted glyphs; first={bad[0]}"
        )
    return len(references)


def port_record(ps2: GcxRecord, target: GcxRecord) -> bytes:
    source_resources = ps2.resources()
    target_resources = target.resources()
    if len(source_resources) > len(target_resources):
        raise ValueError("target has fewer resources than PS2")
    if any(a.flags != b.flags for a, b in zip(source_resources, target_resources)):
        raise ValueError("resource-flag mismatch")
    replacements = {i: resource.data for i, resource in enumerate(source_resources)}
    # Western 3DS records conventionally append Spanish/French variants after
    # the slot occupied by Korean in the official PS2 record.  They must not
    # retain references to the target's old local font after we replace it.
    replacements.update({i: b"\0" for i in range(len(source_resources), len(target_resources))})
    with_text = GcxRecord(target.replace_resources(replacements))
    return replace_font(with_text, convert_font(ps2))


def port_whole_record(ps2: GcxRecord) -> bytes:
    """Keep the PS2 GCX VM/resource layout and convert only its local font."""
    return replace_font(ps2, convert_font(ps2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ps2_codec", type=Path)
    parser.add_argument("target_codec", type=Path)
    parser.add_argument("output_codec", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--reference-codec", type=Path,
                        help="3DS JP structural reference; target indices must align with it")
    parser.add_argument("--ps2-gcx", type=int, action="append",
                        help="port only selected PS2 GCX indices (repeatable)")
    parser.add_argument("--whole-record", action="store_true",
                        help="port PS2 procedure/resources together; intended for focused probes")
    parser.add_argument("--reference-shell", action="store_true",
                        help="use the 3DS reference record's procedure/layout with PS2 text/font")
    parser.add_argument("--reference-record-only", action="store_true",
                        help="diagnostic: insert the untouched 3DS reference GCX")
    parser.add_argument("--exact-only", action="store_true",
                        help="exclude anchored equal-length variant blocks")
    args = parser.parse_args()
    modes = sum((args.whole_record, args.reference_shell, args.reference_record_only))
    if modes > 1:
        raise ValueError("select only one port mode")
    if (args.reference_shell or args.reference_record_only) and not args.reference_codec:
        raise ValueError("reference-based modes require --reference-codec")
    ps2_raw = args.ps2_codec.read_bytes()
    target_raw = args.target_codec.read_bytes()
    ps2 = parse_codec(ps2_raw)
    target = parse_codec(target_raw)
    reference = parse_codec(args.reference_codec.read_bytes()) if args.reference_codec else target
    if len(reference) != len(target):
        raise ValueError("reference and target record counts differ")
    selected = set(args.ps2_gcx or [])
    pairs = correspondence(ps2, reference)
    if args.exact_only:
        pairs = [pair for pair in pairs if pair[2] == "exact-structure"]
    rows: list[dict[str, object]] = []
    built = [record.raw for record in target]
    for ps2_index, target_index, mapping_evidence in pairs:
        if selected and ps2_index not in selected:
            continue
        row: dict[str, object] = {
            "ps2_gcx": ps2_index,
            "target_gcx": target_index,
            "mapping_evidence": mapping_evidence,
        }
        try:
            if args.whole_record:
                built[target_index] = port_whole_record(ps2[ps2_index])
                port_mode = "whole-record"
            elif args.reference_record_only:
                built[target_index] = reference[target_index].raw
                port_mode = "reference-record-only"
            elif args.reference_shell:
                built[target_index] = port_record(ps2[ps2_index], reference[target_index])
                port_mode = "reference-shell"
            else:
                built[target_index] = port_record(ps2[ps2_index], target[target_index])
                port_mode = "text-font"
            reparsed = GcxRecord(built[target_index])
            reference_count = validate_ported_record(reparsed)
            row.update({
                "status": "ported",
                "port_mode": port_mode,
                "resources": len(reparsed.resources()),
                "ps2_glyphs": (ps2[ps2_index].proc_offset - ps2[ps2_index].font_data_offset - 4)
                               // PS2_GLYPH_SIZE,
                "page2_references": reference_count,
                "target_size_before": len(target[target_index].raw),
                "target_size_after": len(built[target_index]),
            })
        except (ValueError, IndexError) as exc:
            row.update({"status": "skipped", "reason": str(exc)})
        rows.append(row)
    output = b"".join(built)
    # Full structural reparse is the minimum acceptance gate.
    reparsed = parse_codec(output)
    if len(reparsed) != len(target):
        raise RuntimeError("record count changed after port")
    args.output_codec.parent.mkdir(parents=True, exist_ok=True)
    args.output_codec.write_bytes(output)
    paired_ps2 = {a for a, _, _ in pairs}
    paired_target = {b for _, b, _ in pairs}
    document = {
        "format": "mgs3d-ps2-official-korean-port-v1",
        "ps2_sha256": hashlib.sha256(ps2_raw).hexdigest(),
        "target_sha256": hashlib.sha256(target_raw).hexdigest(),
        "reference_sha256": hashlib.sha256(args.reference_codec.read_bytes()).hexdigest()
                            if args.reference_codec else hashlib.sha256(target_raw).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "target_size_before": len(target_raw),
        "target_size_after": len(output),
        "ported": sum(row["status"] == "ported" for row in rows),
        "skipped": sum(row["status"] == "skipped" for row in rows),
        "matched_pairs": len(rows),
        "unmatched_ps2_records": len(ps2) - len(paired_ps2),
        "unmatched_target_records": len(target) - len(paired_target),
        "validated_page2_references": sum(int(row.get("page2_references", 0)) for row in rows),
        "unmatched_ps2": [
            {"gcx": i, "procedure_count": len(record.proc_table),
             "resource_count": resource_count(record)}
            for i, record in enumerate(ps2) if i not in paired_ps2
        ],
        "unmatched_target": [
            {"gcx": i, "procedure_count": len(record.proc_table),
             "resource_count": resource_count(record)}
            for i, record in enumerate(target) if i not in paired_target
        ],
        "rows": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: document[k] for k in
                      ("target_size_before", "target_size_after", "ported", "skipped")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
