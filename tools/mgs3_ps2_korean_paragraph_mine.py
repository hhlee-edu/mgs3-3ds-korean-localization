#!/usr/bin/env python3
"""Mine PS2 Korean tokens from exact multi-resource paragraph alignments."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3_ps2_korean_port import correspondence  # noqa: E402
from mgs3_ps2_korean_token_map import korean_characters, ps_symbols  # noqa: E402
from mgs3d_codec_tool import parse_codec  # noqa: E402


ASCII_ALNUM = re.compile(r"[A-Za-z0-9]")


def english_key(text: str) -> str:
    return "".join(ASCII_ALNUM.findall(text)).lower()


def resource_english(raw: bytes) -> str:
    raw = raw.split(b"\0", 1)[0]
    return "".join(chr(value) for value in raw if value < 0x80)


def compatible(symbols: list[bytes], chars: list[str], known: dict[str, str]) -> bool:
    if len(symbols) != len(chars):
        return False
    for symbol, char in zip(symbols, chars):
        if len(symbol) == 1 and symbol.decode("ascii") != char:
            return False
        key = symbol.hex().upper()
        if len(symbol) == 2 and symbol[0] in (0x81, 0x82) and key in known:
            if known[key] != char:
                return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ps2_codec", type=Path)
    parser.add_argument("target_codec", type=Path)
    parser.add_argument("reference_codec", type=Path)
    parser.add_argument("alignment_csv", type=Path)
    parser.add_argument("seed_map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-span", type=int, default=12)
    parser.add_argument("--conflict-minimum-votes", type=int, default=10)
    parser.add_argument("--conflict-minimum-share", type=float, default=0.90)
    args = parser.parse_args()

    ps2 = parse_codec(args.ps2_codec.read_bytes())
    target = parse_codec(args.target_codec.read_bytes())
    reference = parse_codec(args.reference_codec.read_bytes())
    target_to_ps2 = {b: a for a, b, evidence in correspondence(ps2, reference)
                     if evidence == "exact-structure"}
    aligned: dict[str, list[dict[str, str]]] = defaultdict(list)
    with args.alignment_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = english_key(row.get("english", ""))
            chars = korean_characters(row.get("korean", ""))
            if key and chars:
                aligned[key].append(row)

    seed = json.loads(args.seed_map.read_text(encoding="utf-8"))
    known = dict(seed["static_tokens"])
    votes: dict[str, Counter[str]] = defaultdict(Counter)
    evidence: list[dict[str, object]] = []
    seen_sequences: set[str] = set()

    for target_gcx, ps2_gcx in sorted(target_to_ps2.items()):
        target_resources = target[target_gcx].resources()
        paragraph_spans: list[tuple[int, int, dict[str, str]]] = []
        for start in range(len(target_resources)):
            combined = ""
            for end in range(start, min(len(target_resources), start + args.max_span)):
                combined += resource_english(target_resources[end].data)
                rows = aligned.get(english_key(combined), [])
                for row in rows:
                    paragraph_spans.append((start, end + 1, row))
        if not paragraph_spans:
            continue
        # Prefer the longest exact English spans and keep a monotonic,
        # non-overlapping paragraph sequence in this GCX.
        paragraph_spans.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        selected: list[tuple[int, int, dict[str, str]]] = []
        cursor = -1
        for item in paragraph_spans:
            if item[0] < cursor:
                continue
            if selected and item[0] == selected[-1][0]:
                continue
            selected.append(item)
            cursor = item[1]
        if not selected:
            continue

        ps_resources = ps2[ps2_gcx].resources()
        ps_cursor = selected[0][0]
        for target_start, target_end, row in selected:
            chars = korean_characters(row["korean"])
            symbols: list[bytes] = []
            ps_start = ps_cursor
            while ps_cursor < len(ps_resources) and len(symbols) < len(chars):
                symbols.extend(ps_symbols(ps_resources[ps_cursor].data))
                ps_cursor += 1
            if not compatible(symbols, chars, known):
                continue
            sequence_key = f"{ps2_gcx}:{ps_start}:{ps_cursor}:{row.get('korean_sequence')}"
            if sequence_key in seen_sequences:
                continue
            seen_sequences.add(sequence_key)
            for symbol, char in zip(symbols, chars):
                if len(symbol) == 2 and symbol[0] in (0x81, 0x82):
                    votes[symbol.hex().upper()][char] += 1
            evidence.append({
                "target_gcx": target_gcx,
                "target_resources": [target_start, target_end],
                "ps2_gcx": ps2_gcx,
                "ps2_resources": [ps_start, ps_cursor],
                "korean_sequence": row.get("korean_sequence"),
                "characters": len(chars),
            })

    additions: dict[str, str] = {}
    consensus_additions: dict[str, str] = {}
    conflicts: dict[str, object] = {}
    for token, counts in sorted(votes.items()):
        ranked = counts.most_common()
        if len(ranked) == 1 and token not in known:
            additions[token] = ranked[0][0]
        elif len(ranked) > 1:
            conflicts[token] = ranked
            winner, count = ranked[0]
            total = sum(item[1] for item in ranked)
            if (token not in known and count >= args.conflict_minimum_votes
                    and count / total >= args.conflict_minimum_share):
                consensus_additions[token] = winner
    combined = dict(known)
    # Enforce the static page's one-token/one-character property.
    assigned = {char: token for token, char in combined.items()}
    accepted: dict[str, str] = {}
    duplicate_rejections: dict[str, str] = {}
    for token, char in (additions | consensus_additions).items():
        if char in assigned and assigned[char] != token:
            duplicate_rejections[token] = char
        else:
            accepted[token] = char
            assigned[char] = token
    combined.update(accepted)
    document = {
        "format": "mgs3-ps2-korean-token-map-v3",
        "static_tokens": dict(sorted(combined.items())),
        "seed_static_tokens": len(known),
        "paragraph_additions": accepted,
        "unanimous_additions": additions,
        "consensus_additions": consensus_additions,
        "unresolved_static_tokens": 164 - len(combined),
        "exact_paragraph_alignments": len(evidence),
        "conflicts": conflicts,
        "duplicate_rejections": duplicate_rejections,
        "evidence": evidence,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: document[key] for key in
                      ("seed_static_tokens", "unresolved_static_tokens",
                       "exact_paragraph_alignments")}
                     | {"paragraph_additions": len(accepted),
                        "consensus_additions": len(consensus_additions),
                        "conflicts": len(conflicts),
                        "duplicate_rejections": len(duplicate_rejections)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
