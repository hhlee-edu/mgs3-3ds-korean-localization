#!/usr/bin/env python3
"""Verify and report a reflowed codec.dat against its pristine source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, parse_codec  # noqa: E402


def verify(source: bytes, built: bytes) -> tuple[dict[str, object], list[dict[str, object]]]:
    old_records = parse_codec(source)
    new_records = parse_codec(built)
    if len(old_records) != len(new_records):
        raise CodecError(f"record count changed: {len(old_records)} -> {len(new_records)}")

    rows: list[dict[str, object]] = []
    cumulative_delta = 0
    changed_size = shifted = relocated_total = 0
    for index, (old, new) in enumerate(zip(old_records, new_records)):
        expected_new_offset = old.source_offset + cumulative_delta
        if new.source_offset != expected_new_offset:
            raise CodecError(
                f"GCX {index}: boundary gap/overlap, expected 0x{expected_new_offset:x}, "
                f"got 0x{new.source_offset:x}"
            )
        if len(old.proc_table) != len(new.proc_table):
            raise CodecError(f"GCX {index}: procedure word count changed")

        delta = new.source_offset - old.source_offset
        expected_relocated: set[int] = set()
        # GCX53 is the currently proven fixed-container case. Its payload starts
        # at container-relative 0x1000; moving the record moves that suffix.
        if index == 53 and delta:
            expected_relocated = {
                proc_index
                for proc_index, word in enumerate(old.proc_table)
                if (word & 0x00FFFFFF) >= 0x1000
            }

        actual_relocated: set[int] = set()
        for proc_index, (old_word, new_word) in enumerate(zip(old.proc_table, new.proc_table)):
            if (old_word & 0xFF000000) != (new_word & 0xFF000000):
                raise CodecError(f"GCX {index} proc {proc_index}: high flag byte changed")
            old_target = old_word & 0x00FFFFFF
            new_target = new_word & 0x00FFFFFF
            expected_target = old_target + delta if proc_index in expected_relocated else old_target
            if not 0 <= expected_target <= 0x00FFFFFF:
                raise CodecError(f"GCX {index} proc {proc_index}: 24-bit relocation overflow")
            if new_target != expected_target:
                raise CodecError(
                    f"GCX {index} proc {proc_index}: relocation mismatch "
                    f"0x{old_target:x} -> 0x{new_target:x}, expected 0x{expected_target:x}"
                )
            if new_target != old_target:
                actual_relocated.add(proc_index)

        if actual_relocated != expected_relocated:
            raise CodecError(
                f"GCX {index}: missed/extra relocation words: "
                f"expected {sorted(expected_relocated)}, got {sorted(actual_relocated)}"
            )
        size_delta = len(new.raw) - len(old.raw)
        changed_size += size_delta != 0
        shifted += delta != 0
        relocated_total += len(actual_relocated)
        if size_delta or delta or actual_relocated:
            rows.append({
                "gcx": index,
                "old_offset": f"0x{old.source_offset:08X}",
                "new_offset": f"0x{new.source_offset:08X}",
                "delta": delta,
                "old_record_size": len(old.raw),
                "new_record_size": len(new.raw),
                "record_size_delta": size_delta,
                "relocated_procedure_words": len(actual_relocated),
            })
        cumulative_delta += size_delta

    if new_records and new_records[-1].source_offset + len(new_records[-1].raw) != len(built):
        raise CodecError("final GCX boundary does not equal file size")
    summary = {
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "built_sha256": hashlib.sha256(built).hexdigest(),
        "source_size": len(source),
        "built_size": len(built),
        "file_size_delta": len(built) - len(source),
        "record_count": len(old_records),
        "procedure_word_count": sum(len(record.proc_table) for record in old_records),
        "size_changed_records": changed_size,
        "shifted_records": shifted,
        "relocated_procedure_words": relocated_total,
        "checks": {
            "full_parse": "pass",
            "contiguous_record_boundaries": "pass",
            "procedure_word_counts": "pass",
            "required_relocations_complete": "pass",
            "high_flag_bytes_preserved": "pass",
            "low24_no_overflow": "pass",
        },
    }
    return summary, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("built", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    summary, rows = verify(args.source.read_bytes(), args.built.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"summary": summary, "records": rows}, indent=2) + "\n")
    csv_path = args.report.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["gcx"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))
    print(f"report: {args.report}\ncsv: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
