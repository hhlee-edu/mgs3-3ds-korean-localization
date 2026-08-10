#!/usr/bin/env python3
"""Extract structurally framed movie/demo calls from 3DS scenerio.gcx files.

This scanner uses the runtime's 24-bit strcode and the observed 3DS command
frame (0x06 followed by a little-endian 24-bit command hash).  Results remain
static candidates until a runtime request confirms the decoded identifier.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3_ps2_stage_extract import strcode24  # noqa: E402
from mgs3d_codec_tool import GcxRecord  # noqa: E402


COMMAND_MARKERS = (0x06, 0x64)


def load_demo_table(path: Path) -> tuple[dict[int, list[tuple[int, str]]],
                                          dict[int, list[str]]]:
    by_descriptor: dict[int, list[tuple[int, str]]] = {}
    by_id: dict[int, list[str]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            scene_id = int(parts[1])
        except ValueError:
            continue
        name = parts[0]
        descriptor = ((strcode24(name.encode("ascii")) & 0xFFFF) << 8) | 0x06
        by_descriptor.setdefault(descriptor, []).append((scene_id, name))
        by_id.setdefault(scene_id, []).append(name)
    return by_descriptor, by_id


@dataclass(frozen=True)
class TaggedArgument:
    tag: int
    value: int | None
    size: int
    kind: str


def decode_tagged_argument(data: bytes, offset: int) -> TaggedArgument:
    """Decode constant forms proven by guest function 0x00171C7C.

    Dynamic variable/expression forms are deliberately reported unresolved.
    """
    if not 0 <= offset < len(data):
        raise ValueError("argument offset outside procedure data")
    lead = data[offset]
    top, low = lead & 0xF0, lead & 0x0F
    if top == 0xC0:
        return TaggedArgument(9, (lead & 0x3F) - 1, 1, "small_constant")
    if top != 0:
        return TaggedArgument(top >> 4, None, 1, "dynamic_or_reference")
    if low == 0:
        return TaggedArgument(0, 0, 1, "zero")
    if low in (2, 3, 4):
        return TaggedArgument(low, lead, 1, "small_immediate")
    if low == 6:
        if offset + 3 > len(data):
            raise ValueError("truncated 24-bit immediate")
        return TaggedArgument(6, int.from_bytes(data[offset:offset + 3], "little"), 3,
                              "u24_immediate")
    if low == 8:
        if offset + 2 > len(data):
            raise ValueError("truncated 16-bit immediate")
        return TaggedArgument(8, int.from_bytes(data[offset:offset + 2], "little"), 2,
                              "u16_immediate")
    return TaggedArgument(low, None, 1, "unsupported_constant_form")


def procedure_index(record: GcxRecord, file_offset: int) -> int | None:
    relative = file_offset - record.block_start
    candidates = [(word & 0xFFFFFF, index)
                  for index, word in enumerate(record.proc_table)
                  if (word & 0xFFFFFF) <= relative]
    return max(candidates, default=(0, None))[1]


def scan(root: Path, demo_table: Path | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    by_descriptor, by_id = load_demo_table(demo_table) if demo_table else ({}, {})
    hashes = {name: strcode24(name.encode("ascii")) for name in ("demo", "movie")}
    per_proc_order: dict[tuple[str, int | None], int] = {}
    for path in sorted(root.glob("*/scenerio.gcx")):
        record = GcxRecord(path.read_bytes())
        proc_start = record.block_start + record.proc_offset
        blob = record.raw[proc_start:]
        for media_type, command_hash in hashes.items():
            hash_bytes = command_hash.to_bytes(3, "little")
            cursor = 0
            while (hash_hit := blob.find(hash_bytes, cursor)) >= 0:
                if hash_hit == 0 or blob[hash_hit - 1] not in COMMAND_MARKERS:
                    cursor = hash_hit + 1
                    continue
                hit = hash_hit - 1
                absolute = proc_start + hit
                arg_offset = hash_hit + len(hash_bytes)
                argument = decode_tagged_argument(blob, arg_offset)
                packed_descriptor = None if argument.value is None else (
                    (5 << 24) | (argument.value & 0xFFFFFF)
                )
                mappings: list[tuple[int, str]] = []
                if argument.value is not None:
                    if argument.kind == "u24_immediate":
                        mappings = by_descriptor.get(argument.value, [])
                    elif argument.kind == "small_constant":
                        mappings = [(argument.value, name)
                                    for name in by_id.get(argument.value, [])]
                scene_ids = sorted({item[0] for item in mappings})
                resource_names = sorted({item[1] for item in mappings})
                confidence = "static_structural_candidate"
                if len(scene_ids) == 1 and len(resource_names) == 1:
                    confidence = "static_table_exact"
                elif mappings:
                    confidence = "static_table_ambiguous"
                proc = procedure_index(record, absolute)
                key = (path.parent.name, proc)
                per_proc_order[key] = per_proc_order.get(key, 0) + 1
                rows.append({
                    "stage": path.parent.name,
                    "procedure": "" if proc is None else proc,
                    "call_order": per_proc_order[key],
                    "type": media_type,
                    "scene_id": "",
                    "demo_table_id": "|".join(str(value) for value in scene_ids),
                    "record_id/descriptor": "" if argument.value is None
                    else f"0x{argument.value:08X}",
                    "packed_file_descriptor": "" if packed_descriptor is None
                    else f"0x{packed_descriptor:08X}",
                    "descriptor_file": "demo.dat",
                    "resource_id": "|".join(resource_names),
                    "script_offset": f"0x{absolute:X}",
                    "argument_tag": argument.tag,
                    "argument_kind": argument.kind,
                    "confidence": confidence,
                })
                cursor = hash_hit + len(hash_bytes)
    return sorted(rows, key=lambda row: (str(row["stage"]), int(str(row["script_offset"]), 16)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_root", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--demo-table", type=Path)
    args = parser.parse_args()
    rows = scan(args.scenario_root, args.demo_table)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["stage", "procedure", "call_order", "type", "scene_id", "demo_table_id",
              "record_id/descriptor", "packed_file_descriptor", "descriptor_file",
              "resource_id", "script_offset", "argument_tag",
              "argument_kind", "confidence"]
    with args.output_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    counts = {kind: sum(row["type"] == kind for row in rows) for kind in ("demo", "movie")}
    print(f"wrote {args.output_csv}: rows={len(rows)} demo={counts['demo']} movie={counts['movie']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
