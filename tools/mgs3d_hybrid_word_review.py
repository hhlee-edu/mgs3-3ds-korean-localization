#!/usr/bin/env python3
"""List Korean words whose English replacement removes record-local glyphs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("translation", type=Path)
    p.add_argument("allocation", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    shared = set(json.loads(args.allocation.read_text(encoding="utf-8-sig"))["characters"])
    with args.translation.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    scopes: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        scopes[row["record"]].update(c for c in row["korean"] if 0xAC00 <= ord(c) <= 0xD7A3)
    word_scopes: dict[str, set[str]] = defaultdict(set)
    occurrences = Counter()
    examples: dict[str, tuple[str, str]] = {}
    for row in rows:
        for word in re.findall(r"[가-힣]+", row["korean"]):
            local = set(word) - shared
            if not local:
                continue
            word_scopes[word].add(row["record"])
            occurrences[word] += 1
            examples.setdefault(word, (row["preview"], row["korean"]))
    output = []
    for word, records in word_scopes.items():
        removable = sum(len((set(word) - shared) & scopes[record]) for record in records)
        english, korean = examples[word]
        output.append({"korean_word": word, "english_replacement": "",
                       "record_scopes": len(records), "occurrences": occurrences[word],
                       "local_slots_touched": removable,
                       "potential_bytes": removable * 64,
                       "example_english": english, "example_korean": korean,
                       "decision": "review"})
    output.sort(key=lambda r: (-int(r["potential_bytes"]), -int(r["occurrences"]), r["korean_word"]))
    fields = list(output[0]) if output else ["korean_word", "english_replacement"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(output)
    print(f"review_words={len(output)} potential_bytes={sum(int(r['potential_bytes']) for r in output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
