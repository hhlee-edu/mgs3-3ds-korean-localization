#!/usr/bin/env python3
"""Parse, dump, and losslessly rebuild MGS3D movie.dat subtitle records."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import itertools
import json
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import decode_mgs_preview, render_bytes  # noqa: E402
from mgs3d_gcx_font_tool import decode_glyph, render_character  # noqa: E402


ALIGNMENT = 0x10
FILE_PREFIX_SIZE = 0x30


class MovieError(ValueError):
    pass


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise MovieError(f"read outside file at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


@dataclass
class Subtitle:
    offset: int
    raw: bytes
    tail: bytes
    original: bytes
    entry_type: int = 7


@dataclass
class Record:
    index: int
    offset: int
    raw: bytes
    text_end: int
    font: bytes
    subtitles: list[Subtitle]
    gap_before: bytes | memoryview = b""


def parse_records(data: bytes) -> tuple[bytes, list[Record], bytes]:
    if len(data) < FILE_PREFIX_SIZE:
        raise MovieError("file is shorter than the 0x30-byte prefix")
    records: list[Record] = []
    cursor = FILE_PREFIX_SIZE
    previous_end = FILE_PREFIX_SIZE
    while cursor + 0x20 <= len(data):
        kind, size = struct.unpack_from("<II", data, cursor)
        if kind != 4 or size < 0x30 or size % ALIGNMENT or cursor + size > len(data):
            cursor += ALIGNMENT
            continue
        raw = data[cursor : cursor + size]
        relative_text_end = u32(raw, 0x10) + 0x14
        if relative_text_end < 0x20 or relative_text_end + 4 > len(raw):
            cursor += ALIGNMENT
            continue
        font_size = u32(raw, relative_text_end)
        font_start = relative_text_end + 4
        if font_size % 64 or font_start + font_size > len(raw):
            cursor += ALIGNMENT
            continue

        subtitles: list[Subtitle] = []
        entry = 0x20
        while entry < relative_text_end:
            header = u32(raw, entry)
            entry_size, entry_type = header & 0xFFFF, header >> 16
            # Western releases multiplex five languages as types 1..5 with
            # an empty local-font block (type 1 is English). Japanese/local-
            # glyph entries use type 7. Their framing, timing tail, and size
            # rules are the same, so all observed language types can be
            # parsed and rebuilt losslessly here.
            if entry_type not in (1, 2, 3, 4, 5, 7) or entry_size < 8 or entry_size % 4:
                subtitles = []
                break
            # Ordinary entries include 12 bytes of timing/state data in their
            # declared size.  The final entry keeps the same convention in its
            # header even though those 12 bytes are omitted and the font-size
            # word begins there instead.
            declared_end = entry + entry_size
            end = min(declared_end, relative_text_end)
            if declared_end > relative_text_end and declared_end - relative_text_end != 12:
                raise MovieError(f"record {len(records)} subtitle exceeds text area")
            zero = raw.find(b"\0", entry + 4, end)
            if zero < 0:
                raise MovieError(f"record {len(records)} subtitle lacks terminator")
            # The final 12 bytes are timing/state metadata; padding lies before them.
            has_tail = declared_end <= relative_text_end
            tail_start = end - 12 if has_tail and zero + 1 <= end - 12 else zero + 1
            subtitles.append(
                Subtitle(
                    offset=cursor + entry + 4,
                    raw=raw[entry + 4 : zero + 1],
                    tail=raw[tail_start:end],
                    original=raw[entry:end],
                    entry_type=entry_type,
                )
            )
            entry = end
        if not subtitles or entry != relative_text_end:
            cursor += ALIGNMENT
            continue
        records.append(
            Record(len(records), cursor, raw, relative_text_end,
                   raw[font_start:font_start + font_size], subtitles,
                   memoryview(data)[previous_end:cursor])
        )
        previous_end = cursor + size
        cursor += size
    if not records:
        raise MovieError("no subtitle records found")
    return data[:FILE_PREFIX_SIZE], records, data[previous_end:]


def rebuild(prefix: bytes, records: list[Record], suffix: bytes) -> bytes:
    output = bytearray(prefix)
    for record in records:
        # Preserve every byte exactly for now. This establishes the parser/rebuilder invariant
        # before translated-entry and appended-font mutations are enabled.
        output.extend(record.gap_before)
        output.extend(record.raw)
    output.extend(suffix)
    return bytes(output)


def align(value: int, amount: int = ALIGNMENT) -> int:
    return (value + amount - 1) & ~(amount - 1)


def page3_token(index: int) -> bytes:
    if not 0 <= index < 1020:
        raise MovieError(f"page-3 glyph index exceeds capacity: {index}")
    token = 0x9001 + index + index // 255
    return token.to_bytes(2, "big")


PAGE3_TOKEN_TO_INDEX = {page3_token(index): index for index in range(1020)}


def page3_indices(data: bytes) -> set[int]:
    """Return page-3 font slots referenced by an encoded subtitle."""
    indices: set[int] = set()
    cursor = 0
    while cursor + 1 < len(data) and data[cursor]:
        if data[cursor] >= 0x80:
            token = data[cursor:cursor + 2]
            index = PAGE3_TOKEN_TO_INDEX.get(token)
            if index is not None:
                indices.add(index)
            cursor += 2
        else:
            cursor += 1
    return indices


def encode_translation(text: str, character_map: dict[str, bytes]) -> bytes:
    output = bytearray()
    for character in text:
        if character in character_map:
            output.extend(character_map[character])
        elif character == "\n":
            output.extend(b"\x80|")
        elif 0x20 <= ord(character) <= 0x7E:
            output.append(ord(character))
        else:
            raise MovieError(f"character has no movie-font mapping: {character!r}")
    output.append(0)
    return bytes(output)


def load_static_character_map(path: Path | None) -> dict[str, bytes]:
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    raw = document.get("characters")
    if not isinstance(raw, dict):
        raise MovieError("static allocation lacks a characters object")
    result = {}
    for character, token_hex in raw.items():
        if len(character) != 1:
            raise MovieError(f"static allocation key is not one character: {character!r}")
        try:
            token = bytes.fromhex(token_hex)
        except (TypeError, ValueError) as exc:
            raise MovieError(f"invalid static token for {character!r}: {token_hex!r}") from exc
        if len(token) != 2 or token[0] not in (0x81, 0x82, 0x83) or token[1] == 0:
            raise MovieError(f"invalid static-page token for {character!r}: {token.hex()}")
        result[character] = token
    return result


def wrap_like_source(text: str, source: bytes) -> str:
    """Preserve the subtitle card's explicit 80 7C line layout."""
    if "\n" in text or b"\x80|" not in source:
        return text
    source_lines = source.rstrip(b"\0").split(b"\x80|")
    weights: list[int] = []
    for line in source_lines:
        units = cursor = 0
        while cursor < len(line):
            cursor += 2 if line[cursor] >= 0x80 and cursor + 1 < len(line) else 1
            units += 1
        weights.append(max(1, units))
    words = text.split()
    if len(words) < len(weights):
        # Short one-word cards still need their control marker.  Split by
        # character; empty trailing segments are valid and preserve layout.
        boundaries = [0]
        for index in range(1, len(weights)):
            boundaries.append(round(sum(weights[:index]) / sum(weights) * len(text)))
        boundaries.append(len(text))
        return "\n".join(text[boundaries[i]:boundaries[i + 1]] for i in range(len(weights)))
    boundaries = [0]
    total = sum(weights)
    for index in range(1, len(weights)):
        target = round(sum(weights[:index]) / total * len(words))
        boundaries.append(max(boundaries[-1] + 1, min(len(words) - 1, target)))
    boundaries.append(len(words))
    return "\n".join(
        " ".join(words[boundaries[i]:boundaries[i + 1]]) for i in range(len(weights))
    )


def rebuild_record_fixed(record: Record, replacements: dict[int, str], font: ImageFont.FreeTypeFont) -> tuple[bytes, dict[str, str]]:
    """Rebuild a record without changing any entry, record, or file offsets."""
    needed: list[str] = []
    seen: set[str] = set()
    for subtitle in record.subtitles:
        for character in replacements.get(subtitle.offset, ""):
            if ord(character) >= 0x80 and character not in seen:
                seen.add(character)
                needed.append(character)
    if not replacements:
        return record.raw, {}

    old_count = len(record.font) // 64
    replaced_offsets = set(replacements)
    replaced_slots: set[int] = set()
    retained_slots: set[int] = set()
    for subtitle in record.subtitles:
        slots = page3_indices(subtitle.raw)
        if subtitle.offset in replaced_offsets:
            replaced_slots.update(slots)
        else:
            retained_slots.update(slots)
    freed = sorted(index for index in replaced_slots - retained_slots if index < old_count)
    if len(needed) > len(freed):
        raise MovieError(
            f"record {record.index} fixed-layout font deficit: "
            f"need {len(needed)}, freed {len(freed)}, deficit {len(needed) - len(freed)}"
        )
    mapping = {ch: page3_token(freed[i]) for i, ch in enumerate(needed)}
    body = bytearray(record.raw)
    for subtitle in record.subtitles:
        replacement = replacements.get(subtitle.offset)
        if replacement is None:
            continue
        encoded = encode_translation(wrap_like_source(replacement, subtitle.raw), mapping)
        relative = subtitle.offset - record.offset
        text_capacity = len(subtitle.original) - 4 - len(subtitle.tail)
        if len(encoded) > text_capacity:
            raise MovieError(
                f"record {record.index} subtitle at 0x{subtitle.offset:x} fixed-layout text "
                f"deficit: need {len(encoded)}, capacity {text_capacity}"
            )
        body[relative:relative + text_capacity] = encoded + b"\0" * (text_capacity - len(encoded))

    font_start = record.text_end + 4
    for character, token in mapping.items():
        slot = PAGE3_TOKEN_TO_INDEX[token]
        start = font_start + slot * 64
        body[start:start + 64] = render_character(character, font)
    if len(body) != len(record.raw):
        raise MovieError(f"record {record.index} fixed-layout rebuild changed its size")
    return bytes(body), {ch: mapping[ch].hex().upper() for ch in needed}


def rebuild_record_growing(
    record: Record,
    replacements: dict[int, str],
    font: ImageFont.FreeTypeFont,
    donor_offsets: set[int] | None = None,
    target_size: int | None = None,
    static_map: dict[str, bytes] | None = None,
) -> tuple[bytes, dict[str, str]]:
    """Repack a record and append glyphs, for Western records with no font slots."""
    donor_offsets = donor_offsets or set()
    static_map = static_map or {}
    if not replacements and not donor_offsets:
        return record.raw, {}
    needed = list(dict.fromkeys(
        character
        for subtitle in record.subtitles
        for character in replacements.get(subtitle.offset, "")
        if 0xAC00 <= ord(character) <= 0xD7A3 and character not in static_map
    ))
    old_count = len(record.font) // 64
    if old_count + len(needed) > 1020:
        raise MovieError(
            f"record {record.index} needs {len(needed)} Hangul glyphs but only "
            f"{1020 - old_count} page-3 slots remain"
        )
    local_mapping = {character: page3_token(old_count + index)
                     for index, character in enumerate(needed)}
    mapping = static_map | local_mapping

    body = bytearray(record.raw[:0x20])
    for subtitle in record.subtitles:
        replacement = replacements.get(subtitle.offset)
        is_donor = subtitle.offset in donor_offsets
        if replacement is None and not is_donor:
            body.extend(subtitle.original)
            continue
        encoded = (b"\0" if is_donor
                   else encode_translation(wrap_like_source(replacement, subtitle.raw), mapping))
        old_header = u32(subtitle.original, 0)
        old_declared = old_header & 0xFFFF
        omitted_tail = old_declared - len(subtitle.original)
        if omitted_tail not in (0, 12):
            raise MovieError(
                f"record {record.index} subtitle at 0x{subtitle.offset:x} "
                f"has unsupported declared-size delta {omitted_tail}"
            )
        actual_size = align(4 + len(encoded) + len(subtitle.tail), 4)
        padding = actual_size - 4 - len(encoded) - len(subtitle.tail)
        declared_size = actual_size + omitted_tail
        if declared_size > 0xFFFF:
            raise MovieError(f"record {record.index} subtitle exceeds 16-bit size")
        entry_type = old_header >> 16
        body.extend(struct.pack("<I", entry_type << 16 | declared_size))
        body.extend(encoded)
        body.extend(b"\0" * padding)
        body.extend(subtitle.tail)

    text_end = len(body)
    struct.pack_into("<I", body, 0x10, text_end - 0x14)
    new_font = bytearray(record.font)
    for character in needed:
        new_font.extend(render_character(character, font))
    body.extend(struct.pack("<I", len(new_font)))
    body.extend(new_font)
    body.extend(b"\0" * (align(len(body)) - len(body)))
    if target_size is not None:
        if len(body) > target_size:
            raise MovieError(
                f"record {record.index} size-neutral deficit: need {len(body)}, "
                f"capacity {target_size}, deficit {len(body) - target_size}"
            )
        body.extend(b"\0" * (target_size - len(body)))
    struct.pack_into("<I", body, 4, len(body))
    return bytes(body), {character: local_mapping[character].hex().upper()
                         for character in needed}


def maximal_size_neutral_subset(
    record: Record,
    replacements: dict[int, str],
    donor_offsets: set[int],
    font: ImageFont.FreeTypeFont,
    static_map: dict[str, bytes] | None = None,
) -> dict[int, str]:
    """Select a deterministic large subset that fits after donor reclamation."""
    selected = dict(replacements)
    while True:
        try:
            rebuild_record_growing(record, selected, font, donor_offsets,
                                   len(record.raw), static_map)
            return selected
        except MovieError as exc:
            if "size-neutral deficit" not in str(exc) or not selected:
                if not selected:
                    # Donor-only records must still remain structurally valid.
                    rebuild_record_growing(record, {}, font, donor_offsets,
                                           len(record.raw), static_map)
                    return {}
                raise
        counts = Counter(character for text in selected.values() for character in set(text)
                         if 0xAC00 <= ord(character) <= 0xD7A3)
        choices = []
        by_offset = {subtitle.offset: subtitle for subtitle in record.subtitles}
        for offset, text in selected.items():
            subtitle = by_offset[offset]
            glyphs = {ch for ch in text if 0xAC00 <= ord(ch) <= 0xD7A3}
            exclusive = sum(counts[ch] == 1 for ch in glyphs)
            encoded = encode_translation(wrap_like_source(text, subtitle.raw),
                                         {ch: b"\x90\x01" for ch in glyphs})
            saving = max(0, len(subtitle.original) - (4 + len(encoded) + len(subtitle.tail)))
            improvement = exclusive * 64 - saving
            choices.append((improvement, len(glyphs), offset))
        del selected[max(choices)[2]]


def fixed_capacity(record: Record, replacements: dict[int, str]) -> dict:
    """Report whether a record can be rebuilt without moving any bytes."""
    needed = list(dict.fromkeys(
        character
        for subtitle in record.subtitles
        for character in replacements.get(subtitle.offset, "")
        if ord(character) >= 0x80
    ))
    replaced_offsets = set(replacements)
    replaced_slots: set[int] = set()
    retained_slots: set[int] = set()
    for subtitle in record.subtitles:
        slots = page3_indices(subtitle.raw)
        (replaced_slots if subtitle.offset in replaced_offsets else retained_slots).update(slots)
    old_count = len(record.font) // 64
    freed = sorted(index for index in replaced_slots - retained_slots if index < old_count)
    mapping = {ch: page3_token(freed[i]) for i, ch in enumerate(needed[:len(freed)])}
    entries = []
    for subtitle in record.subtitles:
        replacement = replacements.get(subtitle.offset)
        if replacement is None:
            continue
        capacity = len(subtitle.original) - 4 - len(subtitle.tail)
        missing = sorted({ch for ch in replacement if ord(ch) >= 0x80 and ch not in mapping})
        encoded_size = None
        if not missing:
            encoded_size = len(encode_translation(wrap_like_source(replacement, subtitle.raw), mapping))
        entries.append({
            "offset": subtitle.offset,
            "needed_bytes": encoded_size,
            "capacity_bytes": capacity,
            "deficit_bytes": None if encoded_size is None else max(0, encoded_size - capacity),
            "missing_characters": missing,
        })
    font_deficit = max(0, len(needed) - len(freed))
    return {
        "record": record.index,
        "accepted_rows": len(replacements),
        "needed_glyphs": len(needed),
        "freed_slots": len(freed),
        "font_deficit": font_deficit,
        "entries": entries,
        "safe": font_deficit == 0 and all(entry["deficit_bytes"] == 0 for entry in entries),
    }


def maximal_safe_subset(record: Record, replacements: dict[int, str]) -> dict[int, str]:
    """Return a largest fixed-layout-safe subset, preserving CSV/record order."""
    items = list(replacements.items())
    if fixed_capacity(record, replacements)["safe"]:
        return replacements.copy()
    for count in range(len(items) - 1, 0, -1):
        for combination in itertools.combinations(items, count):
            candidate = dict(combination)
            if fixed_capacity(record, candidate)["safe"]:
                return candidate
    return {}


def maximal_safe_extension(
    record: Record, base: dict[int, str], candidates: dict[int, str]
) -> dict[int, str]:
    """Keep every safe base row and return a largest safe candidate extension."""
    if not fixed_capacity(record, base)["safe"]:
        raise MovieError(f"record {record.index} base translations are not fixed-layout safe")
    extras = [(offset, text) for offset, text in candidates.items() if offset not in base]
    for count in range(len(extras), 0, -1):
        for combination in itertools.combinations(extras, count):
            extension = dict(combination)
            if fixed_capacity(record, base | extension)["safe"]:
                return extension
    return {}


def existing_local_glyph_offsets(record: Record, exclude_offsets: set[int]) -> list[int]:
    """Type-1 offsets in *record*, other than *exclude_offsets*, whose raw bytes
    already reference a page-3 local glyph token (0x90 prefix) -- i.e. text a
    prior build already Koreanized. Never stub or overwrite these: they are not
    untranslated placeholder English, they are existing work. See
    docs/session-handoff-2026-08-07.md section 4.2 for why this check exists
    (a build against a stale/empty base file almost destroyed 558 glyphs of
    prior demo.dat work before this check was added)."""
    return sorted(
        subtitle.offset
        for subtitle in record.subtitles
        if subtitle.entry_type == 1
        and subtitle.offset not in exclude_offsets
        and b"\x90" in subtitle.raw
    )


def audit_existing_content(records: list[Record], accepted_offsets: set[int]) -> dict[int, list[int]]:
    """For every record touched by *accepted_offsets*, report any OTHER type-1
    offset in that same record that already has local-glyph content. Returns
    {record_index: [conflicting_offsets]} for records with at least one hit --
    callers must preserve those offsets' existing text unchanged, never stub
    or replace them as if they were plain untranslated English."""
    conflicts: dict[int, list[int]] = {}
    for record in records:
        local = {s.offset for s in record.subtitles if s.offset in accepted_offsets}
        if not local:
            continue
        hits = existing_local_glyph_offsets(record, local)
        if hits:
            conflicts[record.index] = hits
    return conflicts


def read_replacements(path: Path) -> dict[int, str]:
    replacements: dict[int, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("accept", "").strip().lower() not in {"1", "y", "yes", "true", "ok", "o"}:
                continue
            if row.get("korean", "").strip():
                replacements[int(row["offset"])] = row["korean"].strip()
    return replacements


def command_inspect(args: argparse.Namespace) -> None:
    data = args.input.read_bytes()
    prefix, records, suffix = parse_records(data)
    rows = []
    global_index = 0
    for record in records:
        for local_index, subtitle in enumerate(record.subtitles):
            rows.append({
                "index": global_index,
                "record": record.index,
                "entry": local_index,
                "entry_type": subtitle.entry_type,
                "offset": subtitle.offset,
                "size": len(subtitle.raw),
                "preview": decode_mgs_preview(subtitle.raw),
                "raw_text": render_bytes(subtitle.raw),
            })
            global_index += 1
    report = {
        "format": "mgs3d-movie-records-v1",
        "source": args.input.name,
        "file_size": len(data),
        "prefix_size": len(prefix),
        "record_count": len(records),
        "subtitle_count": len(rows),
        "suffix_size": len(suffix),
        "records": [{
            "index": r.index,
            "offset": r.offset,
            "size": len(r.raw),
            "subtitle_count": len(r.subtitles),
            "font_glyph_count": len(r.font) // 64,
        } for r in records],
        "subtitles": rows,
    }
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"parsed {len(records)} records, {len(rows)} subtitles, {len(suffix)} suffix bytes")


def command_roundtrip(args: argparse.Namespace) -> None:
    original = args.input.read_bytes()
    rebuilt = rebuild(*parse_records(original))
    args.output.write_bytes(rebuilt)
    same = original == rebuilt
    print(f"byte_identical={str(same).lower()} sha256={hashlib.sha256(rebuilt).hexdigest()}")
    if not same:
        raise MovieError("round-trip output differs from input")


def command_extract_font(args: argparse.Namespace) -> None:
    _, records, _ = parse_records(args.input.read_bytes())
    if not 0 <= args.record < len(records):
        raise MovieError(f"record out of range: {args.record}")
    font = records[args.record].font
    count = len(font) // 64
    columns = min(args.columns, count)
    sheet = Image.new("L", (columns * 16, ((count + columns - 1) // columns) * 16))
    for index in range(count):
        glyph = decode_glyph(font[index * 64:(index + 1) * 64], "linear")
        sheet.paste(glyph, ((index % columns) * 16, (index // columns) * 16))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"extracted {count} glyphs from record {args.record} to {args.output}")


def command_build_korean(args: argparse.Namespace) -> None:
    if args.grow_records and args.size_neutral_reclaim:
        raise MovieError("select only one of --grow-records and --size-neutral-reclaim")
    original = args.input.read_bytes()
    prefix, records, suffix = parse_records(original)
    replacements = read_replacements(args.translation_csv)
    static_map = load_static_character_map(args.static_allocation)
    if not replacements:
        raise MovieError("CSV has no accepted Korean rows")
    try:
        font = ImageFont.truetype(str(args.font), args.font_size)
    except OSError as exc:
        raise MovieError(f"cannot load font {args.font}: {exc}") from exc

    allocations: dict[str, dict[str, str]] = {}
    used: set[int] = set()
    found: set[int] = set()
    excluded: set[int] = set()
    source_layout = [(record.offset, len(record.raw)) for record in records]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        stream.write(prefix)
        for record in records:
            stream.write(record.gap_before)
            local = {s.offset: replacements[s.offset] for s in record.subtitles if s.offset in replacements}
            found.update(local)
            if args.size_neutral_reclaim and local:
                donors = {s.offset for s in record.subtitles if s.entry_type in {2, 3, 4, 5}}
                chosen = maximal_size_neutral_subset(record, local, donors, font, static_map)
                excluded.update(set(local) - set(chosen))
                rebuilt, allocation = rebuild_record_growing(
                    record, chosen, font, donors, len(record.raw), static_map
                )
                local = chosen
            elif args.grow_records:
                rebuilt, allocation = rebuild_record_growing(
                    record, local, font, static_map=static_map)
            else:
                rebuilt, allocation = rebuild_record_fixed(record, local, font)
            stream.write(rebuilt)
            used.update(local)
            if allocation:
                allocations[str(record.index)] = allocation
        stream.write(suffix)
    missing = sorted(set(replacements) - found)
    if missing:
        raise MovieError(f"{len(missing)} accepted offsets do not identify subtitle entries")
    digest = hashlib.sha256()
    with args.output.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    report = {
        "format": "mgs3d-movie-hangul-allocation-v1",
        "accepted_rows": len(replacements),
        "selected_rows": len(used),
        "excluded_rows": len(excluded),
        "excluded_offsets": sorted(excluded),
        "font": str(args.font),
        "font_size": args.font_size,
        "static_allocation": str(args.static_allocation) if args.static_allocation else None,
        "static_characters": len(static_map),
        "allocations": allocations,
        "sha256": digest.hexdigest(),
    }
    args.output.with_suffix(args.output.suffix + ".hangul.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Parse the changed output as a structural postcondition.
    # Release the potentially very large source before loading the output for
    # the structural postcondition (demo.dat is about 773 MB).
    expected_records = len(records)
    del original, prefix, records, suffix
    gc.collect()
    _, verified, _ = parse_records(args.output.read_bytes())
    if len(verified) != expected_records:
        raise MovieError("rebuilt output changed the record count")
    if args.size_neutral_reclaim:
        output_size = args.output.stat().st_size
        mismatches = [index for index, (expected, actual) in enumerate(
            zip(source_layout, ((record.offset, len(record.raw)) for record in verified)))
            if expected != actual]
        if output_size != args.input.stat().st_size or mismatches:
            raise MovieError(
                f"size-neutral verification failed: file {args.input.stat().st_size} -> "
                f"{output_size}, record mismatches {mismatches[:10]}"
            )
    print(f"rebuilt {args.output}: {len(used)}/{len(replacements)} subtitles selected, "
          f"{len(verified)} records")


def command_audit_existing(args: argparse.Namespace) -> None:
    """Safety gate: run this BEFORE build-korean whenever the base DAT file
    might not be the current live romfs copy. Refuses to proceed silently --
    prints every record where our accepted offsets share a record with
    existing local-glyph (already-Korean) text at other offsets, so those
    offsets don't get treated as blank/stubbable English by mistake."""
    _, records, _ = parse_records(args.input.read_bytes())
    replacements = read_replacements(args.translation_csv)
    if not replacements:
        raise MovieError("CSV has no accepted Korean rows")
    conflicts = audit_existing_content(records, set(replacements))
    total_font = sum(len(record.font) for record in records)
    print(f"입력 파일 총 글리프: {total_font // 64}개")
    if not conflicts:
        print("충돌 없음: 매칭 대상 레코드에 다른 offset의 기존 로컬 글리프 텍스트가 없습니다.")
        return
    print(f"주의: {len(conflicts)}개 레코드에 기존 작업(다른 offset의 로컬 글리프)이 있습니다.")
    print("이 offset들은 절대 스텁하거나 덮어쓰지 마세요:")
    for record_index, offsets in sorted(conflicts.items()):
        print(f"  record {record_index}: {offsets}")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps({"total_font_glyphs": total_font // 64, "conflicts": conflicts},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_capacity(args: argparse.Namespace) -> None:
    _, records, _ = parse_records(args.input.read_bytes())
    replacements = read_replacements(args.translation_csv)
    if not replacements:
        raise MovieError("CSV has no accepted Korean rows")
    used: set[int] = set()
    reports = []
    for record in records:
        local = {s.offset: replacements[s.offset] for s in record.subtitles if s.offset in replacements}
        if local:
            reports.append(fixed_capacity(record, local))
            used.update(local)
    missing = sorted(set(replacements) - used)
    if missing:
        raise MovieError(f"{len(missing)} accepted offsets do not identify subtitle entries")
    result = {
        "format": "mgs3d-movie-fixed-capacity-v1",
        "accepted_rows": len(replacements),
        "changed_records": len(reports),
        "safe_records": sum(report["safe"] for report in reports),
        "safe_rows": sum(report["accepted_rows"] for report in reports if report["safe"]),
        "records": reports,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.safe_csv:
        safe_offsets = {
            entry["offset"]
            for report in reports if report["safe"]
            for entry in report["entries"]
        }
        with args.translation_csv.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows = list(reader)
            fieldnames = reader.fieldnames
        if not fieldnames:
            raise MovieError("translation CSV has no header")
        for row in rows:
            if int(row["offset"]) not in safe_offsets:
                row["accept"] = ""
        args.safe_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.safe_csv.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    if args.max_safe_csv:
        maximal_offsets = set()
        for record in records:
            local = {s.offset: replacements[s.offset] for s in record.subtitles if s.offset in replacements}
            maximal_offsets.update(maximal_safe_subset(record, local))
        with args.translation_csv.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows = list(reader)
            fieldnames = reader.fieldnames
        if not fieldnames:
            raise MovieError("translation CSV has no header")
        for row in rows:
            if int(row["offset"]) not in maximal_offsets:
                row["accept"] = ""
        args.max_safe_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.max_safe_csv.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"maximal safe subset: {len(maximal_offsets)}/{len(replacements)} rows")
    print(f"capacity: {result['safe_records']}/{result['changed_records']} records, "
          f"{result['safe_rows']}/{result['accepted_rows']} rows safe")


def command_extend_safe(args: argparse.Namespace) -> None:
    _, records, _ = parse_records(args.input.read_bytes())
    base = read_replacements(args.base_csv)
    with args.candidate_csv.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fieldnames = reader.fieldnames
    if not fieldnames:
        raise MovieError("candidate CSV has no header")
    if "extension_candidate" not in fieldnames:
        fieldnames.append("extension_candidate")
    candidates = {
        int(row["offset"]): row["korean"].strip()
        for row in rows if row.get("korean", "").strip()
    }
    selected = set(base)
    for record in records:
        local_base = {s.offset: base[s.offset] for s in record.subtitles if s.offset in base}
        local_candidates = {
            s.offset: candidates[s.offset] for s in record.subtitles if s.offset in candidates
        }
        if local_base:
            selected.update(maximal_safe_extension(record, local_base, local_candidates))
    for row in rows:
        offset = int(row["offset"])
        row["accept"] = "yes" if offset in selected else ""
        row["extension_candidate"] = "yes" if offset in selected and offset not in base else ""
        if offset in base:
            row["korean"] = base[offset]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if args.extension_review:
        review_rows = []
        for row in rows:
            if row["extension_candidate"] == "yes":
                review_row = dict(row)
                review_row["accept"] = ""
                review_rows.append(review_row)
        args.extension_review.parent.mkdir(parents=True, exist_ok=True)
        with args.extension_review.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(review_rows)
    print(f"safe extension: {len(base)} base + {len(selected) - len(base)} candidates = {len(selected)} rows")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("output_json", type=Path)
    inspect.add_argument("output_csv", type=Path)
    inspect.set_defaults(function=command_inspect)
    roundtrip = sub.add_parser("roundtrip")
    roundtrip.add_argument("input", type=Path)
    roundtrip.add_argument("output", type=Path)
    roundtrip.set_defaults(function=command_roundtrip)
    font = sub.add_parser("extract-font")
    font.add_argument("input", type=Path)
    font.add_argument("record", type=int)
    font.add_argument("output", type=Path)
    font.add_argument("--columns", type=int, default=16)
    font.set_defaults(function=command_extract_font)
    korean = sub.add_parser("build-korean", help="apply accepted CSV rows and embed Korean glyphs")
    korean.add_argument("input", type=Path)
    korean.add_argument("translation_csv", type=Path)
    korean.add_argument("font", type=Path)
    korean.add_argument("output", type=Path)
    korean.add_argument("--font-size", type=int, default=15)
    korean.add_argument(
        "--static-allocation", type=Path,
        help="reuse a runtime-installed 81/82/83 static Hangul allocation",
    )
    korean.add_argument(
        "--grow-records", action="store_true",
        help="repack records and append glyphs (required by fontless Western records)",
    )
    korean.add_argument(
        "--size-neutral-reclaim", action="store_true",
        help="clear Western entry types 2-5, select a fitting type-1 subset, and preserve every record size",
    )
    korean.set_defaults(function=command_build_korean)
    audit = sub.add_parser(
        "audit-existing",
        help="safety gate: check that accepted offsets don't share a record with existing "
             "local-glyph (already-Korean) text at OTHER offsets -- run before every build",
    )
    audit.add_argument("input", type=Path)
    audit.add_argument("translation_csv", type=Path)
    audit.add_argument("--output-json", type=Path, default=None)
    audit.set_defaults(function=command_audit_existing)
    capacity = sub.add_parser("capacity", help="report safe fixed-layout capacity by record")
    capacity.add_argument("input", type=Path)
    capacity.add_argument("translation_csv", type=Path)
    capacity.add_argument("output_json", type=Path)
    capacity.add_argument("--safe-csv", type=Path, help="copy CSV with unsafe records unaccepted")
    capacity.add_argument("--max-safe-csv", type=Path, help="copy CSV with a largest safe subset per record")
    capacity.set_defaults(function=command_capacity)
    extend = sub.add_parser("extend-safe", help="keep a safe base and add a largest safe candidate subset")
    extend.add_argument("input", type=Path)
    extend.add_argument("base_csv", type=Path)
    extend.add_argument("candidate_csv", type=Path)
    extend.add_argument("output_csv", type=Path)
    extend.add_argument("--extension-review", type=Path, help="write only new candidates, unaccepted")
    extend.set_defaults(function=command_extend_safe)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (OSError, MovieError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
