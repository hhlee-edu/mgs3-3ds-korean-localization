#!/usr/bin/env python3
"""Build a byte-exact single-record movie.dat relocation probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_movie_tool import ALIGNMENT, MovieError, parse_records  # noqa: E402


def grow_record(raw: bytes, delta: int) -> bytes:
    if delta <= 0 or delta % ALIGNMENT:
        raise MovieError(f"delta must be a positive multiple of 0x{ALIGNMENT:x}")
    declared = struct.unpack_from("<I", raw, 4)[0]
    output = bytearray(raw)
    struct.pack_into("<I", output, 4, declared + delta)
    output.extend(b"\0" * delta)
    return bytes(output)


def build(source: bytes, record_indices: list[int], delta: int) -> tuple[bytes, dict[str, object]]:
    prefix, records, suffix = parse_records(source)
    selected = set(record_indices)
    if not selected:
        raise MovieError("select at least one record")
    invalid = sorted(index for index in selected if not 0 <= index < len(records))
    if invalid:
        raise MovieError(f"record indices out of range: {invalid}")
    output = bytearray(prefix)
    for record in records:
        output.extend(record.gap_before)
        output.extend(grow_record(record.raw, delta) if record.index in selected else record.raw)
    output.extend(suffix)
    built = bytes(output)
    _, reparsed, _ = parse_records(built)
    if len(reparsed) != len(records):
        raise MovieError(f"record count changed: {len(records)} -> {len(reparsed)}")
    rows = []
    for old, new in zip(records, reparsed):
        if old.offset != new.offset or len(old.raw) != len(new.raw):
            rows.append({
                "record": old.index,
                "old_offset": old.offset,
                "new_offset": new.offset,
                "delta": new.offset - old.offset,
                "old_size": len(old.raw),
                "new_size": len(new.raw),
            })
    return built, {
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "output_sha256": hashlib.sha256(built).hexdigest(),
        "source_size": len(source),
        "output_size": len(built),
        "grown_records": sorted(selected),
        "growth": delta,
        "records": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--record", type=int, action="append", required=True)
    parser.add_argument("--delta", type=lambda value: int(value, 0), default=0x10)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    built, report = build(args.source.read_bytes(), args.record, args.delta)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(built)
    report_path = args.report or args.output.with_suffix(args.output.suffix + ".json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
