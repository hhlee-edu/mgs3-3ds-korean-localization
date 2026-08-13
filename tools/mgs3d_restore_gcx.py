#!/usr/bin/env python3
"""Restore selected same-layout GCX records from a pristine codec.dat."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec


def records(data: bytes) -> list[tuple[int, int]]:
    return [(record.source_offset, len(record.raw)) for record in parse_codec(data)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pristine", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("indices", nargs="+", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    pristine = args.pristine.read_bytes()
    source = args.source.read_bytes()
    pristine_records = records(pristine)
    source_records = records(source)
    if len(pristine_records) != len(source_records):
        raise ValueError("codec record counts differ")
    output = bytearray(source)
    changes = []
    for index in args.indices:
        poffset, psize = pristine_records[index]
        soffset, ssize = source_records[index]
        if (poffset, psize) != (soffset, ssize):
            raise ValueError(f"GCX {index} layout differs")
        before = bytes(output[soffset:soffset + ssize])
        replacement = pristine[poffset:poffset + psize]
        output[soffset:soffset + ssize] = replacement
        changes.append({
            "gcx": index, "offset": soffset, "size": ssize,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "pristine_sha256": hashlib.sha256(replacement).hexdigest(),
        })
    rebuilt = bytes(output)
    if records(rebuilt) != source_records:
        raise ValueError("record layout changed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rebuilt)
    report = {
        "format": "mgs3d-restore-gcx-v1",
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "output_sha256": hashlib.sha256(rebuilt).hexdigest(),
        "size_preserved": len(source) == len(rebuilt),
        "record_layout_preserved": True,
        "changes": changes,
    }
    report_path = args.report or args.output.with_suffix(args.output.suffix + ".manifest.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
