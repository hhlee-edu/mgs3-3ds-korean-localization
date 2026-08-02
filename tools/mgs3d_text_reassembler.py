#!/usr/bin/env python3
"""Inventory MGS3D text tokens without guessing their Japanese meaning.

This is the evidence-gathering layer for the Japanese reassembler.  It keeps
the original bytes and stable container identities, and deliberately separates
observed encoding facts from provisional semantic labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import decode_mgs_preview, parse_codec, render_bytes  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402


TOOL_VERSION = "mgs3d-japanese-reassembly-v1"

# The static kana pages follow Unicode order but omit obsolete WI/WE. Katakana
# then continues with VU/small KA/small KE. This fixes the legacy arithmetic
# decoder's two-codepoint drift at the end of both pages (for example 8251).
HIRAGANA = "".join(chr(value) for value in range(0x3041, 0x3094)
                   if value not in (0x3090, 0x3091))
KATAKANA = "".join(chr(value) for value in range(0x30A1, 0x30F7)
                   if value not in (0x30F0, 0x30F1))
PAGE83_CHARACTERS = {
    0x08: "、",
    0x09: "。",
    0x12: "ー",
    0x14: "…",
}


def split_static_lead(first: int) -> tuple[int, int] | None:
    """Split a static-page lead into base page and observed style flag bits."""
    base = first & ~0x60
    if 0x80 <= base <= 0x83 and first in (base, base | 0x20, base | 0x40):
        return base, first ^ base
    return None


def static_character(raw: bytes) -> str | None:
    if len(raw) != 2 or raw[1] == 0:
        return None
    split = split_static_lead(raw[0])
    if split is None:
        return None
    page, _flags = split
    index = raw[1] - 1
    if page == 0x80 and 0x20 <= raw[1] <= 0x7E and raw[1] != 0x7C:
        return chr(raw[1])
    if page == 0x81 and 0 <= index < len(HIRAGANA):
        return HIRAGANA[index]
    if page == 0x82 and 0 <= index < len(KATAKANA):
        return KATAKANA[index]
    if page == 0x83:
        return PAGE83_CHARACTERS.get(raw[1])
    return None


def custom_glyph_index(raw: bytes, page: int) -> int | None:
    if len(raw) != 2 or page not in (2, 3):
        return None
    start, end = ((0x8C01, 0x9000) if page == 2 else (0x9001, 0x9400))
    value = int.from_bytes(raw, "big")
    if not start <= value < end or raw[1] == 0:
        return None
    relative = value - start
    return relative - relative // 256


@dataclass(frozen=True)
class Token:
    offset: int
    raw: bytes
    token_class: str
    status: str
    value: int


def classify(raw: bytes) -> tuple[str, str]:
    """Return evidence-based class and resolution status.

    Names describe byte-level facts only.  In particular, 8Cxx and 90xx are
    page references, not the old speculative G/D dictionary names.
    """
    if raw == b"\0":
        return "terminator", "confirmed"
    if len(raw) == 1:
        value = raw[0]
        if 0x20 <= value <= 0x7E:
            return "ascii", "confirmed"
        if value == 0x0A:
            return "line-feed", "observed-control"
        return "single-byte-control", "unresolved"
    value = int.from_bytes(raw, "big")
    low = value & 0xFF
    if low == 0:
        return "invalid-reserved-pair", "unresolved"
    if 0x8C01 <= value < 0x9000:
        return "page2-glyph-reference", "index-confirmed-glyph-unmapped"
    if 0x9001 <= value < 0x9400:
        return "page3-glyph-reference", "index-confirmed-glyph-unmapped"
    split = split_static_lead(raw[0])
    if split is not None:
        page, flags = split
        suffix = f"-flags-{flags:02X}" if flags else ""
        if page == 0x80 and low == 0x7C:
            return f"line-break-807C{suffix}", "observed-control"
        if static_character(raw) is not None:
            names = {0x80: "page0-ascii", 0x81: "page1-hiragana",
                     0x82: "page1-katakana", 0x83: "page83-punctuation"}
            return f"{names[page]}{suffix}", "mapped-static-character"
        return f"static-page-{page:02X}{suffix}", "unresolved"
    return f"two-byte-page-{raw[0]:02X}", "unresolved"


def tokenize(data: bytes) -> list[Token]:
    result: list[Token] = []
    cursor = 0
    while cursor < len(data):
        first = data[cursor]
        if first >= 0x80:
            if cursor + 1 == len(data):
                raw = data[cursor:cursor + 1]
                result.append(Token(cursor, raw, "truncated-pair", "error", first))
                break
            raw = data[cursor:cursor + 2]
        else:
            raw = data[cursor:cursor + 1]
        token_class, status = classify(raw)
        result.append(Token(cursor, raw, token_class, status, int.from_bytes(raw, "big")))
        cursor += len(raw)
    return result


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def streams(path: Path, kind: str):
    data = path.read_bytes()
    if kind == "codec":
        for gcx, record in enumerate(parse_codec(data)):
            resource_cursor = 0
            for resource, item in enumerate(record.resources()):
                identity = {"gcx": gcx, "resource": resource,
                            "gcx_file_offset": record.source_offset,
                            "resource_region_offset": resource_cursor,
                            "resource_kind": "script" if item.is_script else "string"}
                resource_cursor += len(item.data)
                if item.is_script:
                    continue
                yield identity, item.data
    else:
        for record in parse_records(data)[1]:
            for entry, subtitle in enumerate(record.subtitles):
                yield {"record": record.index, "entry": entry,
                       "entry_type": subtitle.entry_type,
                       "record_file_offset": record.offset,
                       "text_file_offset": subtitle.offset}, subtitle.raw


def inventory(path: Path, kind: str, max_examples: int = 3) -> dict[str, object]:
    counts: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    stream_count = token_count = trailing_byte_count = trailing_stream_count = 0
    for identity, raw in streams(path, kind):
        stream_count += 1
        end = raw.find(b"\0")
        text_raw = raw if end < 0 else raw[:end + 1]
        trailing = b"" if end < 0 else raw[end + 1:]
        if trailing:
            trailing_stream_count += 1
            trailing_byte_count += len(trailing)
        tokens = tokenize(text_raw)
        token_count += len(tokens)
        raw_hash = sha256(raw)
        for index, token in enumerate(tokens):
            key = token.raw.hex().upper()
            counts[key] += 1
            classes[token.token_class] += 1
            statuses[token.status] += 1
            if len(examples[key]) < max_examples:
                left = max(0, token.offset - 8)
                right = min(len(text_raw), token.offset + len(token.raw) + 8)
                examples[key].append({
                    **identity, "stream_sha256": raw_hash, "token_index": index,
                    "byte_offset_in_stream": token.offset,
                    "context_start": left, "context_hex": text_raw[left:right].hex().upper(),
                    "legacy_preview": decode_mgs_preview(text_raw),
                })
    values = []
    for key in sorted(counts, key=lambda item: int(item, 16)):
        raw = bytes.fromhex(key)
        token_class, status = classify(raw)
        values.append({"raw_hex": key, "value": f"0x{int(key, 16):0{len(key)}X}",
                       "width": len(raw), "class": token_class, "status": status,
                       "count": counts[key], "examples": examples[key]})
    resolved_statuses = {"confirmed", "mapped-static-character"}
    unresolved = sum(count for status, count in statuses.items()
                     if status not in resolved_statuses)
    return {
        "format": TOOL_VERSION, "source": str(path), "source_size": path.stat().st_size,
        "source_sha256": sha256(path.read_bytes()), "container": kind,
        "stream_count": stream_count, "token_count": token_count,
        "trailing_payload_stream_count": trailing_stream_count,
        "trailing_payload_byte_count": trailing_byte_count,
        "distinct_token_values": len(values), "unresolved_token_occurrences": unresolved,
        "class_counts": dict(sorted(classes.items())),
        "status_counts": dict(sorted(statuses.items())), "tokens": values,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("codec", "movie", "demo"))
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-examples", type=int, default=3)
    args = parser.parse_args()
    try:
        document = inventory(args.source, args.kind, args.max_examples)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"{args.kind}: {document['token_count']} tokens, "
              f"{document['distinct_token_values']} values, "
              f"{document['unresolved_token_occurrences']} unresolved occurrences")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
