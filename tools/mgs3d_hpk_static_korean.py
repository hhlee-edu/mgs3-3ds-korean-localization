#!/usr/bin/env python3
"""Patch an MGS3D HPK static font entry with a deterministic Korean page."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_gcx_font_tool import GLYPH_SIZE, render_character  # noqa: E402


ENTRY_KEY = bytes.fromhex("453c386e")
FONT_OFFSET = 0x2208
STATIC_SLOTS = 165  # 81xx (81 slots) followed by 82xx (84 slots)
EXTENDED_STATIC_SLOTS = 191  # plus 83xx slots 02..1B; 8301 is runtime-cleared


def token_for_slot(slot: int) -> bytes:
    if not 0 <= slot < STATIC_SLOTS:
        raise ValueError(f"static slot out of range: {slot}")
    if slot < 81:
        return bytes((0x81, slot + 1))
    return bytes((0x82, slot - 81 + 1))


def token_for_allocation_slot(slot: int) -> bytes:
    if slot < STATIC_SLOTS:
        return token_for_slot(slot)
    if slot < EXTENDED_STATIC_SLOTS:
        return bytes((0x83, slot - STATIC_SLOTS + 2))
    raise ValueError(f"extended static slot out of range: {slot}")


def physical_slot_for_token(token: bytes) -> int:
    if len(token) != 2 or token[1] == 0:
        raise ValueError(f"invalid static token: {token.hex()}")
    if token[0] == 0x81:
        return token[1] - 1
    if token[0] == 0x82:
        return 81 + token[1] - 1
    if token[0] == 0x83 and token[1] >= 2:
        return 165 + token[1] - 1
    raise ValueError(f"unsupported static token: {token.hex()}")


def korean_characters(document: dict[str, object], extra_texts: list[str] | None = None) -> list[str]:
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for unit in document.get("units", []):
        for character in str(unit.get("text", "")):
            if 0xAC00 <= ord(character) <= 0xD7A3:
                if character not in first_seen:
                    first_seen[character] = len(first_seen)
                counts[character] += 1
    for text in extra_texts or []:
        for character in text:
            if 0xAC00 <= ord(character) <= 0xD7A3:
                if character not in first_seen:
                    first_seen[character] = len(first_seen)
                counts[character] += 1
    return sorted(counts, key=lambda character: (-counts[character], first_seen[character]))


def smallest_zlib(data: bytes) -> bytes:
    candidates: list[bytes] = []
    for level in range(1, 10):
        for memory_level in range(1, 10):
            for strategy in (
                zlib.Z_DEFAULT_STRATEGY,
                zlib.Z_FILTERED,
                zlib.Z_RLE,
                zlib.Z_HUFFMAN_ONLY,
            ):
                compressor = zlib.compressobj(
                    level,
                    zlib.DEFLATED,
                    zlib.MAX_WBITS,
                    memory_level,
                    strategy,
                )
                candidates.append(compressor.compress(data) + compressor.flush())
    return min(candidates, key=lambda value: (len(value), value))


def patch_archive(
    source: Path,
    output: Path,
    characters: list[str],
    font: ImageFont.FreeTypeFont,
    physical_slots: list[int] | None = None,
) -> dict[str, object]:
    archive = bytearray(source.read_bytes())
    entry = archive.find(ENTRY_KEY)
    if entry < 0 or archive.find(ENTRY_KEY, entry + 1) >= 0:
        raise ValueError(f"entry key is missing or non-unique in {source}")
    unpacked_size, packed_size = struct.unpack_from("<II", archive, entry + 4)
    packed_start = entry + 12
    unpacked = bytearray(zlib.decompress(archive[packed_start : packed_start + packed_size]))
    if len(unpacked) != unpacked_size:
        raise ValueError("HPK entry unpacked-size mismatch")
    physical_slots = physical_slots or list(range(len(characters)))
    if len(physical_slots) != len(characters):
        raise ValueError("character and physical-slot counts differ")
    font_end = FONT_OFFSET + (max(physical_slots, default=-1) + 1) * GLYPH_SIZE
    if font_end > len(unpacked):
        raise ValueError("static font region exceeds HPK entry")
    for slot, character in zip(physical_slots, characters):
        start = FONT_OFFSET + slot * GLYPH_SIZE
        unpacked[start : start + GLYPH_SIZE] = render_character(character, font)
    repacked = smallest_zlib(bytes(unpacked))
    if len(repacked) > packed_size:
        raise ValueError(
            f"patched entry needs {len(repacked)} compressed bytes; fixed budget is {packed_size}"
        )
    archive[packed_start : packed_start + packed_size] = repacked.ljust(packed_size, b"\0")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(archive)
    return {
        "source": str(source),
        "output": str(output),
        "entry_offset": entry,
        "unpacked_size": unpacked_size,
        "packed_budget": packed_size,
        "patched_packed_size": len(repacked),
        "padding": packed_size - len(repacked),
        "output_size": len(archive),
        "output_sha256": hashlib.sha256(archive).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_hpk", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("output_hpk", type=Path)
    parser.add_argument("allocation", type=Path)
    parser.add_argument(
        "--required-translation",
        type=Path,
        action="append",
        help="translation whose Hangul must be retained before frequency allocation",
    )
    parser.add_argument("--font-size", type=int, default=15)
    parser.add_argument(
        "--corpus-csv", type=Path, action="append",
        help="add accepted Korean CSV rows to static-glyph frequency ranking",
    )
    parser.add_argument(
        "--required-csv", type=Path,
        help="CSV containing Korean rows that must fit the static page",
    )
    parser.add_argument(
        "--required-offset", type=int, action="append",
        help="offset from --required-csv whose Hangul must be allocated",
    )
    parser.add_argument(
        "--character-allocation", type=Path,
        help="patch the exact ordered character map from an optimized allocation",
    )
    args = parser.parse_args()

    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    extra_texts: list[str] = []
    for csv_path in args.corpus_csv or []:
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            extra_texts.extend(
                row.get("korean", "") for row in csv.DictReader(stream)
                if row.get("korean", "") and row.get("accept", "yes").strip().lower()
                in {"1", "y", "yes", "true", "ok", "o"}
            )
    characters = korean_characters(document, extra_texts)
    total_characters = len(characters)
    required: list[str] = []
    supplied: dict[str, object] | None = None
    required_seen: set[str] = set()
    for required_path in args.required_translation or []:
        required_document = json.loads(required_path.read_text(encoding="utf-8-sig"))
        for unit in required_document.get("units", []):
            for character in str(unit.get("text", "")):
                if (0xAC00 <= ord(character) <= 0xD7A3
                        and character not in required_seen):
                    required.append(character)
                    required_seen.add(character)
    if args.required_csv:
        offsets = set(args.required_offset or [])
        with args.required_csv.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if offsets and int(row["offset"]) not in offsets:
                    continue
                for character in row.get("korean", ""):
                    if (0xAC00 <= ord(character) <= 0xD7A3
                            and character not in required_seen):
                        required.append(character)
                        required_seen.add(character)
    if args.character_allocation:
        supplied = json.loads(args.character_allocation.read_text(encoding="utf-8-sig"))
        characters = list(supplied["characters"])
        required = list(supplied.get("required_hangul", required))
    capacity = (len(supplied["characters"]) if supplied is not None else STATIC_SLOTS)
    if len(required) > capacity:
        raise SystemExit(
            f"required translations need {len(required)} slots; only {capacity} exist"
        )
    if not args.character_allocation:
        characters = required + [character for character in characters
                                 if character not in required_seen]
        characters = characters[:STATIC_SLOTS]
    font = ImageFont.truetype(str(args.font), args.font_size)
    supplied_tokens = (list(supplied["characters"].values())
                       if supplied is not None else None)
    physical_slots = ([physical_slot_for_token(bytes.fromhex(token))
                       for token in supplied_tokens]
                      if supplied_tokens is not None else None)
    report = patch_archive(args.source_hpk, args.output_hpk, characters, font,
                           physical_slots)
    allocation = {
        "format": "mgs3d-static-korean-allocation-v1",
        "font": str(args.font),
        "font_size": args.font_size,
        "entry_key": ENTRY_KEY.hex().upper(),
        "font_offset": FONT_OFFSET,
        "characters": (dict(supplied["characters"]) if supplied is not None else {
            character: token_for_slot(slot).hex().upper()
            for slot, character in enumerate(characters)
        }),
        "corpus_unique_hangul": total_characters,
        "unallocated_unique_hangul": total_characters - len(characters),
        "required_hangul": required,
        "archive": report,
    }
    args.allocation.parent.mkdir(parents=True, exist_ok=True)
    args.allocation.write_text(
        json.dumps(allocation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    print(
        f"allocated {len(characters)}/{capacity} static Korean glyphs "
        f"from {total_characters} corpus characters"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
