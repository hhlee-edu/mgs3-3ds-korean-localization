#!/usr/bin/env python3
"""Transplant one grown GCX and fund it from selected later donor GCXs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, GcxRecord, parse_codec  # noqa: E402
from mgs3d_codec_size_neutral_select import language_block_donors  # noqa: E402


def pad_record(raw: bytes, amount: int, source_offset: int) -> bytes:
    if not amount:
        return raw
    record = GcxRecord(raw, source_offset)
    resources = record.resources()
    old_size = record.font_data_offset - record.string_resources_offset
    return record.replace_resources(
        {0: resources[0].data}, string_region_size=old_size + amount)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("receiver_source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receiver-gcx", type=int, required=True)
    parser.add_argument("--receiver-end", type=int,
                        help="transplant a contiguous receiver range through this GCX")
    parser.add_argument("--donor-gcx", type=int, action="append")
    parser.add_argument("--donor-start", type=int)
    parser.add_argument("--donor-end", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    base_data = args.base.read_bytes()
    base = parse_codec(base_data)
    source = parse_codec(args.receiver_source.read_bytes())
    receiver = args.receiver_gcx
    receiver_end = args.receiver_end if args.receiver_end is not None else receiver
    donors = set(args.donor_gcx or [])
    if args.donor_start is not None or args.donor_end is not None:
        if args.donor_start is None or args.donor_end is None or args.donor_end < args.donor_start:
            raise CodecError("donor range requires valid --donor-start and --donor-end")
        donors.update(range(args.donor_start, args.donor_end + 1))
    donors = sorted(donors)
    if receiver_end < receiver:
        raise CodecError("receiver end precedes receiver start")
    if not donors or donors[0] <= receiver_end:
        raise CodecError("all donor GCXs must follow the receiver range")

    outputs = [record.raw for record in base]
    for gcx in range(receiver, receiver_end + 1):
        outputs[gcx] = source[gcx].raw
    needed = sum(len(source[gcx].raw) - len(base[gcx].raw)
                 for gcx in range(receiver, receiver_end + 1))
    if needed <= 0 or needed % 16:
        raise CodecError(f"receiver growth must be positive and aligned: {needed}")

    remaining = needed
    donor_report = []
    for gcx in donors:
        if not remaining:
            break
        record = base[gcx]
        resources = record.resources()
        indices = language_block_donors(resources, set())
        if not indices:
            continue
        natural = record.replace_resources({index: b"\0" for index in indices})
        maximum = len(record.raw) - len(natural)
        used = min(maximum, remaining)
        if used % 16:
            used -= used % 16
        if not used:
            continue
        outputs[gcx] = pad_record(natural, maximum - used, record.source_offset)
        remaining -= used
        donor_report.append({"gcx": gcx, "resources": indices,
                             "maximum": maximum, "used": used})
    if remaining:
        raise CodecError(f"selected donors leave {remaining} unfunded bytes")

    output = b"".join(outputs)
    verified = parse_codec(output)
    if len(output) != len(base_data) or len(verified) != len(base):
        raise CodecError("local reflow changed total size or record count")
    last = max(item["gcx"] for item in donor_report)
    original_offsets = [record.source_offset for record in base]
    built_offsets = [record.source_offset for record in verified]
    if built_offsets[last + 1:] != original_offsets[last + 1:]:
        raise CodecError("offsets after the donor window were not restored")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    report = {
        "format": "mgs3d-codec-local-reflow-probe-v1",
        "base_sha256": hashlib.sha256(base_data).hexdigest(),
        "receiver_source_sha256": hashlib.sha256(args.receiver_source.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "file_size": len(output), "record_count": len(verified),
        "receiver_gcx": receiver, "receiver_end": receiver_end,
        "receiver_growth": needed,
        "donors": donor_report, "restored_after_gcx": last,
        "moved_gcxs": [index for index, (old, new) in enumerate(
            zip(original_offsets, built_offsets)) if old != new],
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
