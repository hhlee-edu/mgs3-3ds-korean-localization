#!/usr/bin/env python3
"""Prepare and audit a deterministic 191-slot shared Hangul candidate."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from mgs3d_hpk_static_korean import EXTENDED_STATIC_SLOTS, token_for_allocation_slot


def hangul(text: str) -> list[str]:
    return [character for character in text if 0xAC00 <= ord(character) <= 0xD7A3]


def read_codec(path: Path) -> list[str]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    return [str(unit.get("text", "")) for unit in document.get("units", [])]


def read_csv(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [row.get("korean") or row.get("target_ko") or ""
                for row in csv.DictReader(stream)
                if (row.get("accept", "yes").strip().lower()
                    in {"1", "y", "yes", "true", "ok", "o"})]


def prepare(baseline: dict, corpora: dict[str, list[str]], slots: int = 191) -> dict:
    if slots != EXTENDED_STATIC_SLOTS:
        raise ValueError("runtime-verified shared allocation must contain 191 slots")
    raw = baseline.get("characters")
    if not isinstance(raw, dict):
        raise ValueError("baseline allocation lacks a characters object")
    required = list(dict.fromkeys(baseline.get("required_hangul", [])))
    frequency: Counter[str] = Counter()
    for texts in corpora.values():
        for text in texts:
            frequency.update(hangul(text))
    existing = list(raw)
    ordered = required + [character for character in existing if character not in required]
    # Translation work is deliberately deferred. Preserve every proven baseline
    # character, then fill only genuinely vacant slots from the integrated corpus.
    for character, _ in sorted(frequency.items(), key=lambda item: (-item[1], ord(item[0]))):
        if character not in ordered:
            ordered.append(character)
    ordered = ordered[:slots]
    characters = {str(character): str(token).upper()
                  for character, token in raw.items()}
    valid_tokens = [token_for_allocation_slot(index).hex().upper()
                    for index in range(slots)]
    if len(set(characters.values())) != len(characters):
        raise ValueError("baseline allocation contains duplicate tokens")
    if any(token not in valid_tokens for token in characters.values()):
        raise ValueError("baseline allocation contains an invalid 191-slot token")
    free_tokens = [token for token in valid_tokens if token not in characters.values()]
    additions = [character for character in ordered if character not in characters]
    characters.update(zip(additions, free_tokens))
    selected = set(characters)
    scopes = {}
    for name, texts in corpora.items():
        used = set().union(*(set(hangul(text)) for text in texts)) if texts else set()
        scopes[name] = {
            "rows": len(texts),
            "unique_hangul": len(used),
            "shared_hangul": len(used & selected),
            "local_hangul": len(used - selected),
            "missing_characters": "".join(sorted(used - selected)),
        }
    return {
        "format": "mgs3d-shared-korean-allocation-candidate-v1",
        "slots": slots,
        "characters": characters,
        "required_hangul": required,
        "baseline_characters_preserved": sum(character in characters for character in existing),
        "corpus_scopes": scopes,
        "policy": "preserve verified baseline; fill vacancies by integrated frequency",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("codec_translation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--movie-csv", type=Path, action="append", default=[])
    parser.add_argument("--demo-csv", type=Path, action="append", default=[])
    parser.add_argument("--review-csv", type=Path, action="append", default=[])
    args = parser.parse_args()
    corpora = {"codec": read_codec(args.codec_translation)}
    for name, paths in (("movie", args.movie_csv), ("demo", args.demo_csv),
                        ("review", args.review_csv)):
        corpora[name] = [text for path in paths for text in read_csv(path)]
    result = prepare(json.loads(args.baseline.read_text(encoding="utf-8-sig")), corpora)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"prepared {len(result['characters'])}/191 shared characters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
