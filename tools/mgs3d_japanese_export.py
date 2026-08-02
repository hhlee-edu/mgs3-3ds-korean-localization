#!/usr/bin/env python3
"""Export every MGS3D text resource with lossless partial Japanese reassembly."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_gcx_font_tool import GLYPH_SIZE, font_region  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402
from mgs3d_text_reassembler import (  # noqa: E402
    TOOL_VERSION, custom_glyph_index, split_static_lead, static_character,
    streams, tokenize,
)


EXPORT_FORMAT = "mgs3d-japanese-export-v1"


def reconstruct(raw: bytes, glyph_hashes: dict[tuple[int, int], str] | None = None,
                glyph_map: dict[str, str] | None = None) -> dict[str, object]:
    glyph_hashes = glyph_hashes or {}
    glyph_map = glyph_map or {}
    text: list[str] = []
    raw_tokens: list[str] = []
    controls: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    end = raw.find(b"\0")
    text_raw = raw if end < 0 else raw[:end + 1]
    trailing = b"" if end < 0 else raw[end + 1:]
    tokens = tokenize(text_raw)
    for index, token in enumerate(tokens):
        code = token.raw.hex().upper()
        raw_tokens.append(code)
        previous_raw = tokens[index - 1].raw if index else None
        next_raw = tokens[index + 1].raw if index + 1 < len(tokens) else None
        character = static_character(token.raw)
        if token.raw == b"\x80#" and next_raw == b"\xa0{" or \
                token.raw == b"\x80#" and previous_raw == b"\xc0}":
            controls.append({"token_index": index, "byte_offset": token.offset,
                             "raw_hex": code, "kind": "markup-hash-delimiter"})
        elif token.raw == b"\xa0{":
            controls.append({"token_index": index, "byte_offset": token.offset,
                             "raw_hex": code, "kind": "markup-open"})
        elif token.raw == b"\xc0}":
            controls.append({"token_index": index, "byte_offset": token.offset,
                             "raw_hex": code, "kind": "markup-close"})
        elif token.token_class == "ascii":
            text.append(chr(token.value))
        elif character is not None:
            text.append(character)
            split = split_static_lead(token.raw[0]) if len(token.raw) == 2 else None
            if split and split[1]:
                controls.append({"token_index": index, "byte_offset": token.offset,
                                 "raw_hex": code, "kind": "static-page-flags",
                                 "base_page": f"0x{split[0]:02X}",
                                 "flags": f"0x{split[1]:02X}"})
        elif token.token_class in ("line-feed", "line-break-807C") or \
                token.token_class.startswith("line-break-807C-flags-"):
            text.append("\n")
            controls.append({"token_index": index, "byte_offset": token.offset,
                             "raw_hex": code, "kind": "line-break"})
        elif token.token_class == "terminator":
            controls.append({"token_index": index, "byte_offset": token.offset,
                             "raw_hex": code, "kind": "terminator"})
        else:
            page2 = custom_glyph_index(token.raw, 2)
            page3 = custom_glyph_index(token.raw, 3)
            if page2 is not None:
                glyph_hash = glyph_hashes.get((2, page2))
                character = glyph_map.get(glyph_hash or "")
                marker = character or f"<GLYPH2:{page2:04d}>"
            elif page3 is not None:
                glyph_hash = glyph_hashes.get((3, page3))
                character = glyph_map.get(glyph_hash or "")
                marker = character or f"<GLYPH3:{page3:04d}>"
            else:
                split = split_static_lead(token.raw[0]) if len(token.raw) == 2 else None
                if split:
                    marker = f"<STATIC{split[0]:02X}:{token.raw[1]:02X}:FLAGS{split[1]:02X}>"
                else:
                    marker = f"<RAW:{code}>"
            text.append(marker)
            if character is None:
                unresolved.append({"token_index": index, "byte_offset": token.offset,
                                   "raw_hex": code, "class": token.token_class,
                                   "marker": marker})
    return {"raw_hex": raw.hex().upper(), "raw_tokens": raw_tokens,
            "text_raw_hex": text_raw.hex().upper(),
            "trailing_raw_hex": trailing.hex().upper(),
            "reconstructed": "".join(text), "controls": controls,
            "unresolved": unresolved}


def load_glyph_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format") != "mgs3d-japanese-glyph-map-v1":
        raise ValueError(f"unsupported glyph map: {path}")
    result = {}
    for digest, entry in document.get("entries", {}).items():
        character = entry.get("character")
        if len(digest) != 64 or not isinstance(character, str) or len(character) != 1:
            raise ValueError(f"invalid glyph-map entry: {digest}")
        result[digest] = character
    return result


def font_hashes(source: Path, kind: str) -> dict[int, dict[tuple[int, int], str]]:
    result = {}
    if kind == "codec":
        for index, record in enumerate(parse_codec(source.read_bytes())):
            start, count = font_region(record)
            result[index] = {(2, slot): hashlib.sha256(
                record.raw[start + slot * GLYPH_SIZE:start + (slot + 1) * GLYPH_SIZE]
            ).hexdigest() for slot in range(count)}
    else:
        for record in parse_records(source.read_bytes())[1]:
            result[record.index] = {(3, slot): hashlib.sha256(
                record.font[slot * GLYPH_SIZE:(slot + 1) * GLYPH_SIZE]
            ).hexdigest() for slot in range(len(record.font) // GLYPH_SIZE)}
    return result


def export(kind: str, source: Path, output: Path, audit_output: Path,
           glyph_map_path: Path | None = None) -> dict[str, object]:
    source_data = source.read_bytes()
    glyph_map = load_glyph_map(glyph_map_path)
    hashes = font_hashes(source, kind)
    statuses: Counter[str] = Counter()
    stream_count = token_count = unresolved_count = 0
    digest = hashlib.sha256()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as target:
        for identity, raw in streams(source, kind):
            record_index = int(identity["gcx"] if kind == "codec" else identity["record"])
            rebuilt = reconstruct(raw, hashes.get(record_index, {}), glyph_map)
            row = {"format": EXPORT_FORMAT, "container": kind, **identity,
                   "stream_sha256": hashlib.sha256(raw).hexdigest(), **rebuilt}
            line = json.dumps(row, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")) + "\n"
            target.write(line)
            digest.update(line.encode("utf-8"))
            stream_count += 1
            token_count += len(rebuilt["raw_tokens"])
            unresolved_count += len(rebuilt["unresolved"])
            statuses["complete" if not rebuilt["unresolved"] else "incomplete"] += 1
    audit = {
        "format": "mgs3d-japanese-export-audit-v1", "reassembly_format": TOOL_VERSION,
        "container": kind, "source": str(source), "source_size": len(source_data),
        "source_sha256": hashlib.sha256(source_data).hexdigest(),
        "output": str(output), "output_sha256": digest.hexdigest(),
        "stream_count": stream_count, "token_count": token_count,
        "complete_stream_count": statuses["complete"],
        "incomplete_stream_count": statuses["incomplete"],
        "unresolved_token_occurrences": unresolved_count,
        "confirmed_glyph_mapping_count": len(glyph_map),
        "completion_gate_passed": unresolved_count == 0,
    }
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    audit_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("codec", "movie", "demo"))
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="deterministic JSON Lines output")
    parser.add_argument("audit", type=Path)
    parser.add_argument("--glyph-map", type=Path,
                        default=Path(__file__).resolve().parent / "data" /
                        "mgs3d_japanese_glyphs.json")
    args = parser.parse_args()
    try:
        audit = export(args.kind, args.source, args.output, args.audit, args.glyph_map)
        print(f"{args.kind}: {audit['stream_count']} streams, "
              f"{audit['unresolved_token_occurrences']} unresolved tokens, "
              f"gate={'pass' if audit['completion_gate_passed'] else 'fail'}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
