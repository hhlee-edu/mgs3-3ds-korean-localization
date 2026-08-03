#!/usr/bin/env python3
"""Audit MGS3D RomFS static-font HPK entries and scenario references."""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from collections import Counter
from pathlib import Path


DEFAULT_KEY = bytes.fromhex("453c386e")
RESIDENT_NAMES = (b"r_sna01", b"r_sna02")


def parse_static_entries(data: bytes, label: str,
                         key: bytes = DEFAULT_KEY) -> list[dict[str, int]]:
    entries: list[dict[str, int]] = []
    cursor = 0
    while True:
        offset = data.find(key, cursor)
        if offset < 0:
            return entries
        if offset + 12 > len(data):
            raise ValueError(f"truncated HPK entry header: {label}@{offset}")
        unpacked_size, packed_size = struct.unpack_from("<II", data, offset + 4)
        packed = data[offset + 12:offset + 12 + packed_size]
        try:
            unpacked = zlib.decompress(packed)
        except zlib.error as error:
            raise ValueError(f"invalid HPK zlib entry: {label}@{offset}") from error
        if len(unpacked) != unpacked_size:
            raise ValueError(f"HPK unpacked-size mismatch: {label}@{offset}")
        entries.append({
            "entry_offset": offset,
            "unpacked_size": unpacked_size,
            "packed_size": packed_size,
        })
        cursor = offset + 1


def scenario_residents(data: bytes) -> list[str]:
    return [name.decode("ascii") for name in RESIDENT_NAMES if name in data]


def audit(romfs: Path, key: bytes = DEFAULT_KEY) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    hpk_files = sorted(romfs.rglob("*.hpk"))
    for path in hpk_files:
        data = path.read_bytes()
        for entry in parse_static_entries(data, str(path), key):
            entries.append({
                "path": path.relative_to(romfs).as_posix(),
                "archive_size": len(data),
                **entry,
            })

    scenarios = sorted(romfs.rglob("scenerio.gcx"))
    references: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for path in scenarios:
        data = path.read_bytes()
        names = scenario_residents(data)
        if names:
            counts.update(names)
            references.append({
                "path": path.relative_to(romfs).as_posix(),
                "residents": names,
            })
    return {
        "format": "mgs3d-hpk-static-audit-v1",
        "romfs": str(romfs),
        "hpk_files": len(hpk_files),
        "static_entries": entries,
        "scenario_files": len(scenarios),
        "referencing_scenarios": len(references),
        "resident_reference_counts": dict(sorted(counts.items())),
        "scenario_references": references,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("romfs", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--expect-entry-count", type=int)
    args = parser.parse_args()
    report = audit(args.romfs)
    if (args.expect_entry_count is not None
            and len(report["static_entries"]) != args.expect_entry_count):
        raise SystemExit(
            f"expected {args.expect_entry_count} static entries; "
            f"found {len(report['static_entries'])}"
        )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"HPK={report['hpk_files']}, static entries={len(report['static_entries'])}, "
        f"scenarios={report['referencing_scenarios']}/{report['scenario_files']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
