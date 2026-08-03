#!/usr/bin/env python3
"""Catalog official-Korean text resources from extracted PS2 MGS3 stages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import GcxRecord, render_bytes  # noqa: E402
from mgs3_ps2_font_sheet import GLYPH_SIZE  # noqa: E402


def token_index(token: int, base: int) -> int:
    relative = token - base
    return relative - relative // 256


def decode_text(raw: bytes, static: dict[str, str],
                local_glyphs: dict[int, str] | None = None) -> tuple[str, int, int]:
    pieces: list[str] = []
    local = unknown_static = 0
    cursor = 0
    while cursor < len(raw):
        first = raw[cursor]
        if first == 0:
            break
        if first < 0x80:
            if first == 0x0A:
                pieces.append("\n")
            elif 0x20 <= first <= 0x7E:
                pieces.append(chr(first))
            else:
                pieces.append(f"<C{first:02X}>")
            cursor += 1
            continue
        if cursor + 1 >= len(raw):
            pieces.append(f"<{first:02X}>")
            break
        token = (first << 8) | raw[cursor + 1]
        key = f"{token:04X}"
        if key in static:
            pieces.append(static[key])
        elif first in (0x81, 0x82, 0x83):
            pieces.append(f"<S{key}>")
            unknown_static += 1
        elif 0x8C01 <= token < 0x9000 and (token & 0xFF):
            index = token_index(token, 0x8C01)
            pieces.append((local_glyphs or {}).get(index, f"<L{index:03d}>"))
            local += 1
        else:
            pieces.append(f"<{key}>")
        cursor += 2
    return "".join(pieces), local, unknown_static


def ocr_map(path: Path | None, minimum_confidence: float) -> dict[str, str]:
    if path is None:
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))["glyphs"]
    return {
        row["sha256"]: row["text"]
        for row in rows
        if len(row["text"]) == 1 and row["confidence"] >= minimum_confidence
    }


def record_local_map(record: GcxRecord, recognized: dict[str, str]) -> dict[int, str]:
    start = record.block_start + record.font_data_offset
    end = record.block_start + record.proc_offset
    if end - start < 4:
        return {}
    size = struct.unpack_from("<I", record.raw, start)[0]
    if size != end - start - 4 or size % GLYPH_SIZE:
        return {}
    result = {}
    for index, pos in enumerate(range(start + 4, end, GLYPH_SIZE)):
        digest = hashlib.sha256(record.raw[pos:pos + GLYPH_SIZE]).hexdigest()
        if digest in recognized:
            result[index] = recognized[digest]
    return result


def recognized_local_count(raw: bytes, local_glyphs: dict[int, str]) -> int:
    count = cursor = 0
    while cursor + 1 < len(raw) and raw[cursor]:
        if raw[cursor] < 0x80:
            cursor += 1
            continue
        token = (raw[cursor] << 8) | raw[cursor + 1]
        if 0x8C01 <= token < 0x9000 and (token & 0xFF):
            count += token_index(token, 0x8C01) in local_glyphs
        cursor += 2
    return count


def build_catalog(stages: Path, token_map: Path, local_ocr: Path | None = None,
                  minimum_confidence: float = 80.0) -> list[dict[str, object]]:
    mapping = json.loads(token_map.read_text(encoding="utf-8"))["static_tokens"]
    recognized = ocr_map(local_ocr, minimum_confidence)
    candidates: list[tuple[Path, int, bytes, dict[int, str]]] = []
    occurrences: Counter[str] = Counter()
    for path in sorted(stages.rglob("*.02")):
        record = GcxRecord(path.read_bytes())
        local = record_local_map(record, recognized)
        for resource_index, resource in enumerate(record.resources()):
            if resource.is_script:
                continue
            visible = resource.data.split(b"\0", 1)[0]
            if not any(value in range(0x81, 0x90) for value in visible):
                continue
            digest = hashlib.sha1(resource.data).hexdigest()
            occurrences[digest] += 1
            candidates.append((path, resource_index, resource.data, local))
    rows: list[dict[str, object]] = []
    for path, resource_index, raw, local in candidates:
        digest = hashlib.sha1(raw).hexdigest()
        decoded, local_count, unknown_static = decode_text(raw, mapping, local)
        rows.append({
            "stage": path.parent.name,
            "gcx": path.name,
            "resource": resource_index,
            "decoded": decoded,
            "raw": render_bytes(raw),
            "bytes": len(raw),
            "local_token_references": local_count,
            "recognized_local_references": recognized_local_count(raw, local),
            "unknown_static_references": unknown_static,
            "occurs_in_stage_gcxs": occurrences[digest],
            "stage_specific": occurrences[digest] == 1,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stages", type=Path)
    parser.add_argument("token_map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--stage-specific-only", action="store_true",
                        help="write only resources occurring in one stage GCX")
    parser.add_argument("--local-glyph-ocr", type=Path,
                        help="optional SHA-256 keyed local-glyph OCR result")
    parser.add_argument("--minimum-ocr-confidence", type=float, default=80.0)
    args = parser.parse_args()
    rows = build_catalog(args.stages, args.token_map, args.local_glyph_ocr,
                         args.minimum_ocr_confidence)
    if args.stage_specific_only:
        rows = [row for row in rows if row["stage_specific"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "rows": len(rows),
        "stage_specific": sum(bool(row["stage_specific"]) for row in rows),
        "fully_static_decoded": sum(
            row["local_token_references"] == 0 and row["unknown_static_references"] == 0
            for row in rows
        ),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
