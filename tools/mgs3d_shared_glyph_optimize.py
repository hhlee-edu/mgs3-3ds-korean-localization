#!/usr/bin/env python3
"""Rank shared Hangul by the number of local 64-byte slots it eliminates."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from mgs3d_hpk_static_korean import EXTENDED_STATIC_SLOTS, token_for_allocation_slot


def chars(text: str) -> set[str]:
    return {char for char in text if 0xAC00 <= ord(char) <= 0xD7A3}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("codec", type=Path)
    parser.add_argument("media", type=Path, nargs="+")
    parser.add_argument("output", type=Path)
    parser.add_argument("--codec-output", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    codec = json.loads(args.codec.read_text(encoding="utf-8-sig"))
    scopes: dict[tuple[str, str], set[str]] = {}
    for unit in codec["units"]:
        scopes.setdefault(("codec", str(unit["gcx"])), set()).update(chars(unit["text"]))
    for media_path in args.media:
        with media_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("accept", "").lower() not in {"yes", "y", "1", "true", "ok", "o"}:
                    continue
                scopes.setdefault((row["media"], row["record"]), set()).update(chars(row["korean"]))
    benefit = Counter(char for scope in scopes.values() for char in scope)
    ranked = sorted(benefit, key=lambda char: (-benefit[char], ord(char)))
    selected = ranked[:EXTENDED_STATIC_SLOTS]
    tokens = [token_for_allocation_slot(i).hex().upper() for i in range(EXTENDED_STATIC_SLOTS)]
    existing = set(baseline["characters"])
    old_score = sum(benefit[char] for char in existing)
    new_score = sum(benefit[char] for char in selected)
    result = {
        "format": "mgs3d-shared-glyph-scope-benefit-v1",
        "cost_per_local_slot": 64,
        "scope_count": len(scopes),
        "baseline": {"characters": len(existing), "eliminated_local_slots": old_score,
                     "saved_bytes": old_score * 64},
        "optimized": {"characters": len(selected), "eliminated_local_slots": new_score,
                      "saved_bytes": new_score * 64,
                      "incremental_slots": new_score - old_score,
                      "incremental_bytes": (new_score - old_score) * 64},
        "characters": dict(zip(selected, tokens)),
        "ranking": [{"character": char, "scopes": benefit[char],
                     "saved_bytes": benefit[char] * 64,
                     "in_verified_baseline": char in existing} for char in ranked],
        "warning": "Optimized mapping is theoretical until both resident HPKs are patched and runtime-verified.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.codec_output:
        codec["character_map"] = result["characters"]
        args.codec_output.parent.mkdir(parents=True, exist_ok=True)
        args.codec_output.write_text(json.dumps(codec, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    print(f"baseline={old_score * 64} optimized={new_score * 64} delta={(new_score-old_score)*64}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
