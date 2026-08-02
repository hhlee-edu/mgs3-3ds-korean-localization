#!/usr/bin/env python3
"""Move one codec GCX boundary while preserving total size and later offsets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, GcxRecord, parse_codec  # noqa: E402
from mgs3d_codec_size_neutral_select import language_block_donors  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--donor-gcx", type=int, required=True)
    parser.add_argument("--receiver-gcx", type=int, required=True)
    parser.add_argument("--movement", type=int,
                        help="move exactly this many aligned bytes instead of the donor maximum")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    original = args.input.read_bytes()
    records = parse_codec(original)
    if args.receiver_gcx == args.donor_gcx:
        raise CodecError("receiver and donor GCX must differ")
    donor = records[args.donor_gcx]
    receiver = records[args.receiver_gcx]
    donor_resources = donor.resources()
    donors = language_block_donors(donor_resources, set())
    if not donors:
        raise CodecError(f"GCX {args.donor_gcx} has no structural language donor block")
    shrunk = donor.replace_resources({index: b"\0" for index in donors})
    maximum_movement = len(donor.raw) - len(shrunk)
    movement = args.movement or maximum_movement
    if (movement <= 0 or movement % 16 or movement > maximum_movement):
        raise CodecError(
            f"invalid aligned movement {movement}; donor maximum is {maximum_movement}")
    if movement < maximum_movement:
        built_donor = GcxRecord(shrunk, donor.source_offset)
        built_resources = built_donor.resources()
        old_string_size = built_donor.font_data_offset - built_donor.string_resources_offset
        shrunk = built_donor.replace_resources(
            {0: built_resources[0].data},
            string_region_size=old_string_size + maximum_movement - movement)

    receiver_resources = receiver.resources()
    old_string_size = receiver.font_data_offset - receiver.string_resources_offset
    grown = receiver.replace_resources(
        {0: receiver_resources[0].data}, string_region_size=old_string_size + movement)
    if len(grown) != len(receiver.raw) + movement:
        raise CodecError("receiver did not absorb the exact donor movement")

    rebuilt_records = [record.raw for record in records]
    rebuilt_records[args.donor_gcx] = shrunk
    rebuilt_records[args.receiver_gcx] = grown
    output = b"".join(rebuilt_records)
    verified = parse_codec(output)
    if len(output) != len(original) or len(verified) != len(records):
        raise CodecError("reflow changed total file size or record count")

    original_offsets = [record.source_offset for record in records]
    built_offsets = [record.source_offset for record in verified]
    changed_offsets = [index for index, pair in enumerate(zip(original_offsets, built_offsets))
                       if pair[0] != pair[1]]
    low, high = sorted((args.donor_gcx, args.receiver_gcx))
    expected_changed = list(range(low + 1, high + 1))
    if changed_offsets != expected_changed:
        raise CodecError(f"unexpected moved GCX offsets: {changed_offsets}")
    expected_shift = -movement if args.donor_gcx < args.receiver_gcx else movement
    if any(built_offsets[index] != original_offsets[index] + expected_shift
           for index in expected_changed):
        raise CodecError("moved GCX range did not shift by the expected amount")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    report = {
        "format": "mgs3d-codec-reflow-probe-v1",
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "file_size": len(output), "record_count": len(verified),
        "donor_gcx": args.donor_gcx, "receiver_gcx": args.receiver_gcx,
        "donor_resources": donors, "movement_bytes": movement,
        "receiver_old_offset": original_offsets[args.receiver_gcx],
        "receiver_new_offset": built_offsets[args.receiver_gcx],
        "moved_gcxs": expected_changed,
        "later_offsets_preserved": built_offsets[high + 1:] == original_offsets[high + 1:],
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
