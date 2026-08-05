#!/usr/bin/env python3
"""Audit every codec donor selected for size-neutral Western-language reclamation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_codec_size_neutral_select import (  # noqa: E402
    confident_non_english_language,
    language_scores,
)
from mgs3d_english_korean_match import decode_western  # noqa: E402


def main() -> int:
    csv.field_size_limit(2 ** 31 - 1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("selection_report", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args()
    records = parse_codec(args.codec.read_bytes())
    report = json.loads(args.selection_report.read_text(encoding="utf-8"))["records"]
    donors = {(int(row["gcx"]), int(resource))
              for row in report for resource in row.get("donor_resources", [])}
    protected = set()
    with args.review.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("container") == "codec" and row.get("gcx") and row.get("resource"):
                protected.add((int(row["gcx"]), int(row["resource"])))
    # Selection reports include every primary and supplemental candidate.  They
    # are authoritative protection targets even when an automatic matcher did
    # not emit the split row into the browser-review CSV.
    protected.update((int(row["gcx"]), int(resource))
                     for row in report for resource in row.get("candidate_resources", []))
    blocks = {int(row["gcx"]): row.get("language_block") for row in report}
    rows = []
    failures = []
    languages = Counter()
    resource_cache = {gcx: records[gcx].resources() for gcx in {item[0] for item in donors}}
    for gcx, resource_index in sorted(donors):
        resource = resource_cache[gcx][resource_index]
        words, scores = language_scores(resource.data)
        language = confident_non_english_language(resource.data)
        block = blocks.get(gcx)
        block_backed = bool(block and int(block[0]) <= resource_index <= int(block[1]))
        if (language is None and not block_backed) or resource.is_script:
            failures.append((gcx, resource_index, "classification-or-script"))
        languages[language or ("anchored-block" if block_backed else "unclassified")] += 1
        rows.append({
            "gcx": gcx, "resource": resource_index,
            "language": language or ("anchored-block" if block_backed else ""),
            "word_count": len(words), "byte_count": len(resource.data),
            "en_score": scores["en"], "es_score": scores["es"],
            "fr_score": scores["fr"], "de_score": scores["de"],
            "it_score": scores["it"],
            "sha256": hashlib.sha256(resource.data).hexdigest(),
            "preview": decode_western(resource.data),
        })
    overlap = sorted(donors & protected)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "donor_count": len(donors), "protected_count": len(protected),
        "protected_overlap_count": len(overlap), "protected_overlap": overlap[:100],
        "classification_failure_count": len(failures), "classification_failures": failures[:100],
        "language_counts": dict(sorted(languages.items())),
        "samples": {language: [row for row in rows if row["language"] == language][:20]
                    for language in sorted(languages)},
    }
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    print(json.dumps({key: summary[key] for key in (
        "donor_count", "protected_count", "protected_overlap_count",
        "classification_failure_count", "language_counts")}, ensure_ascii=False))
    if overlap or failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
