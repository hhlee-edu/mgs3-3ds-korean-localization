#!/usr/bin/env python3
"""Seed and audit the PS2 Korean 81/82 static-token character map."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402


VISIBLE = re.compile(r"[가-힣A-Za-z0-9]")


def ps_symbols(raw: bytes) -> list[bytes]:
    result: list[bytes] = []
    cursor = 0
    raw = raw.split(b"\0", 1)[0]
    while cursor < len(raw):
        first = raw[cursor]
        if first >= 0x80 and cursor + 1 < len(raw):
            result.append(raw[cursor:cursor + 2])
            cursor += 2
        elif chr(first).isalnum():
            result.append(bytes((first,)))
            cursor += 1
        else:
            cursor += 1
    return result


def korean_characters(text: str) -> list[str]:
    return VISIBLE.findall(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ps2_codec", type=Path)
    parser.add_argument("alignment_csv", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ps2-gcx", type=int, default=16)
    parser.add_argument("--resource-start", type=int, default=14)
    parser.add_argument("--resource-end", type=int, default=17,
                        help="exclusive; default covers the first official radio paragraph")
    parser.add_argument("--english-anchor", default="Do you copy?")
    args = parser.parse_args()

    codec_raw = args.ps2_codec.read_bytes()
    record = parse_codec(codec_raw)[args.ps2_gcx]
    resources = record.resources()[args.resource_start:args.resource_end]
    symbols = [symbol for resource in resources for symbol in ps_symbols(resource.data)]

    with args.alignment_csv.open(encoding="utf-8-sig", newline="") as stream:
        matches = [row for row in csv.DictReader(stream)
                   if args.english_anchor in row.get("english", "")]
    if len(matches) != 1:
        raise ValueError(f"expected one alignment row, found {len(matches)}")
    characters = korean_characters(matches[0]["korean"])
    if len(symbols) != len(characters):
        raise ValueError(
            f"seed alignment is not positional: {len(symbols)} PS symbols, "
            f"{len(characters)} Korean characters"
        )

    observations: dict[str, list[str]] = defaultdict(list)
    local: dict[str, str] = {}
    ascii_checks: list[dict[str, str]] = []
    for symbol, character in zip(symbols, characters):
        key = symbol.hex().upper()
        if len(symbol) == 1:
            ascii_checks.append({"symbol": key, "character": character})
        elif symbol[0] in (0x81, 0x82):
            observations[key].append(character)
        elif 0x8C <= symbol[0] <= 0x8F:
            previous = local.setdefault(key, character)
            if previous != character:
                raise ValueError(f"conflicting local token {key}: {previous!r}/{character!r}")

    static: dict[str, str] = {}
    conflicts: dict[str, list[str]] = {}
    for key, values in sorted(observations.items()):
        unique = sorted(set(values))
        if len(unique) == 1:
            static[key] = unique[0]
        else:
            conflicts[key] = unique
    if conflicts:
        raise ValueError(f"conflicting static-token observations: {conflicts}")
    if any(bytes.fromhex(row["symbol"]).decode("ascii") != row["character"]
           for row in ascii_checks):
        raise ValueError("ASCII anchors disagree with aligned Korean text")

    document = {
        "format": "mgs3-ps2-korean-token-map-v1",
        "source_sha256": hashlib.sha256(codec_raw).hexdigest(),
        "seed": {
            "ps2_gcx": args.ps2_gcx,
            "resources": [args.resource_start, args.resource_end],
            "english_anchor": args.english_anchor,
            "korean_sequence": matches[0].get("korean_sequence"),
            "symbol_count": len(symbols),
            "character_count": len(characters),
        },
        "static_tokens": static,
        "local_tokens": {str(args.ps2_gcx): local},
        "unresolved_static_tokens": 164 - len(static),
        "evidence": "exact positional alignment with consistent repeated-token observations",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "symbols": len(symbols),
        "static_tokens": len(static),
        "local_tokens": len(local),
        "unresolved_static_tokens": document["unresolved_static_tokens"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
