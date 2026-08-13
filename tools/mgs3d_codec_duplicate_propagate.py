#!/usr/bin/env python3
"""Propagate unambiguous Codec translations to byte-identical English duplicates."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    records = parse_codec(args.codec.read_bytes())
    document = json.loads(args.translation.read_text(encoding="utf-8"))
    translations: dict[str, set[str]] = defaultdict(set)
    existing = set()
    for unit in document["units"]:
        key = int(unit["gcx"]), int(unit["resource"])
        existing.add(key)
        if str(unit["text"]) == "<00>":
            continue
        resource = records[key[0]].resources()[key[1]]
        english = decode_western(resource.data)
        if english.strip():
            translations[english].add(str(unit["text"]))

    unique = {
        english: next(iter(values))
        for english, values in translations.items()
        if len(values) == 1
    }
    additions = []
    for gcx, record in enumerate(records):
        for resource, item in enumerate(record.resources()):
            if (gcx, resource) in existing:
                continue
            english = decode_western(item.data)
            if english not in unique:
                continue
            additions.append({
                "gcx": gcx,
                "resource": resource,
                "kind": "string",
                "original_size": len(item.data),
                "text": unique[english],
            })

    result = dict(document)
    result["units"] = list(document["units"]) + additions
    result["duplicate_propagation"] = {
        "policy": "exact decoded English; one unique Korean translation only",
        "added_units": len(additions),
        "ambiguous_english_skipped": sum(len(values) > 1 for values in translations.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        report = {
            "format": "mgs3d-codec-duplicate-propagation-v1",
            "source_units": len(document["units"]),
            "added_units": len(additions),
            "output_units": len(result["units"]),
            "unique_english_sources": len(unique),
            "ambiguous_english_skipped": sum(len(values) > 1 for values in translations.values()),
            "affected_gcx": len({int(unit["gcx"]) for unit in additions}),
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"propagated {len(additions)} exact duplicate resources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
