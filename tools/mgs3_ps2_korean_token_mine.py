#!/usr/bin/env python3
"""Mine additional PS2 Korean 81/82 mappings from confirmed Unicode dialogue."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3_ps2_korean_port import correspondence  # noqa: E402
from mgs3_ps2_korean_token_map import korean_characters, ps_symbols  # noqa: E402
from mgs3d_codec_tool import parse_codec  # noqa: E402


def compatible(symbols: list[bytes], characters: list[str], known: dict[str, str]) -> bool:
    if len(symbols) != len(characters):
        return False
    for symbol, character in zip(symbols, characters):
        if len(symbol) == 1 and symbol.decode("ascii") != character:
            return False
        key = symbol.hex().upper()
        if symbol[0] in (0x81, 0x82) and key in known and known[key] != character:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ps2_codec", type=Path)
    parser.add_argument("reference_codec", type=Path)
    parser.add_argument("confirmed_csv", type=Path)
    parser.add_argument("seed_map", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--minimum-votes", type=int, default=8)
    parser.add_argument("--minimum-share", type=float, default=0.98)
    parser.add_argument("--unanimous-minimum-votes", type=int, default=4,
                        help="also accept lower-count mappings with 100%% agreement")
    args = parser.parse_args()

    ps2 = parse_codec(args.ps2_codec.read_bytes())
    reference = parse_codec(args.reference_codec.read_bytes())
    target_to_ps2 = {target: source for source, target, evidence in correspondence(ps2, reference)
                     if evidence == "exact-structure"}
    by_target: dict[int, list[list[str]]] = defaultdict(list)
    with args.confirmed_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("accept") == "yes" and row.get("container") == "codec" and row.get("gcx"):
                chars = korean_characters(row.get("korean", ""))
                if chars:
                    by_target[int(row["gcx"])].append(chars)

    seed = json.loads(args.seed_map.read_text(encoding="utf-8"))
    known = dict(seed["static_tokens"])
    rounds: list[dict[str, object]] = []
    while True:
        votes: dict[str, Counter[str]] = defaultdict(Counter)
        candidate_pairs = 0
        for target_gcx, texts in by_target.items():
            ps2_gcx = target_to_ps2.get(target_gcx)
            if ps2_gcx is None:
                continue
            resources = ps2[ps2_gcx].resources()
            streams = [ps_symbols(resource.data) for resource in resources]
            streams = [symbols for symbols in streams
                       if symbols and any(len(s) == 2 and s[0] in (0x81, 0x82) for s in symbols)]
            for symbols in streams:
                for characters in texts:
                    if not compatible(symbols, characters, known):
                        continue
                    candidate_pairs += 1
                    for symbol, character in zip(symbols, characters):
                        if len(symbol) == 2 and symbol[0] in (0x81, 0x82):
                            votes[symbol.hex().upper()][character] += 1
        additions: dict[str, str] = {}
        audit: dict[str, object] = {}
        for token, counts in sorted(votes.items()):
            character, count = counts.most_common(1)[0]
            total = sum(counts.values())
            share = count / total
            accepted = ((count >= args.minimum_votes and share >= args.minimum_share)
                        or (count >= args.unanimous_minimum_votes and share == 1.0))
            if token not in known and accepted:
                additions[token] = character
            audit[token] = {"votes": total, "winner": character, "winner_votes": count,
                            "share": share, "alternatives": counts.most_common(5)}
        rounds.append({"known_before": len(known), "candidate_pairs": candidate_pairs,
                       "additions": additions, "vote_audit": audit})
        if not additions:
            break
        known.update(additions)

    document = {
        "format": "mgs3-ps2-korean-token-map-v2",
        "static_tokens": dict(sorted(known.items())),
        "seed_static_tokens": len(seed["static_tokens"]),
        "mined_static_tokens": len(known) - len(seed["static_tokens"]),
        "unresolved_static_tokens": 164 - len(known),
        "exact_record_pairs": len(target_to_ps2),
        "confirmed_target_gcxs": len(by_target),
        "thresholds": {"minimum_votes": args.minimum_votes,
                       "minimum_share": args.minimum_share,
                       "unanimous_minimum_votes": args.unanimous_minimum_votes},
        "rounds": rounds,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: document[key] for key in
                      ("seed_static_tokens", "mined_static_tokens", "unresolved_static_tokens",
                       "exact_record_pairs", "confirmed_target_gcxs")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
