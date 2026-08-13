#!/usr/bin/env python3
"""Normalize equal-width Korean terms inside parsed movie/demo subtitle text."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_rendered
from mgs3d_movie_tool import parse_records


TERMS = (("버츄어스 미션", "버추어스 미션"), ("소콜로프", "소코로프"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("character_map", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--manifest", type=Path)
    args = ap.parse_args()
    doc = json.loads(args.character_map.read_text(encoding="utf-8"))
    mapping = {ch: bytes.fromhex(token) for ch, token in doc["character_map"].items()}
    pairs = [(old, new, parse_rendered(old, mapping), parse_rendered(new, mapping)) for old, new in TERMS]
    if any(len(a) != len(b) for _, _, a, b in pairs):
        raise SystemExit("normalization terms must have equal encoded width")
    original = args.source.read_bytes()
    output = bytearray(original)
    _, records, _ = parse_records(original)
    counts = {f"{old}->{new}": 0 for old, new in TERMS}
    for record in records:
        for subtitle in record.subtitles:
            raw = bytes(output[subtitle.offset:subtitle.offset + len(subtitle.raw)])
            changed = raw
            for old, new, encoded_old, encoded_new in pairs:
                count = changed.count(encoded_old)
                if count:
                    changed = changed.replace(encoded_old, encoded_new)
                    counts[f"{old}->{new}"] += count
            output[subtitle.offset:subtitle.offset + len(subtitle.raw)] = changed
    rebuilt = bytes(output)
    _, after, _ = parse_records(rebuilt)
    if [(r.offset, len(r.raw)) for r in after] != [(r.offset, len(r.raw)) for r in records]:
        raise SystemExit("record layout changed")
    args.output.write_bytes(rebuilt)
    manifest = {"source_sha256": hashlib.sha256(original).hexdigest(), "output_sha256": hashlib.sha256(rebuilt).hexdigest(), "size_preserved": len(original) == len(rebuilt), "record_layout_preserved": True, "counts": counts}
    (args.manifest or args.output.with_suffix(args.output.suffix + ".manifest.json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
