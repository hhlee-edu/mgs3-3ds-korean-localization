#!/usr/bin/env python3
"""Extract, inspect, patch, and rebuild MGS3D codec.dat GCX records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from mgs3d_translation import validate_codec_translation


ALIGNMENT = 0x10
END_MARKER = 0xFFFFFFFF


class CodecError(ValueError):
    pass


def align(value: int, amount: int = ALIGNMENT) -> int:
    return (value + amount - 1) & ~(amount - 1)


def u32(data: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise CodecError(f"read outside data at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def crypt(seed: int, data: bytes) -> bytes:
    result = bytearray(data)
    if not seed:
        return bytes(result)
    for index in range(len(result)):
        seed = (seed * 0x7D2B89DD + 0xCF9) & 0xFFFFFFFF
        result[index] ^= (seed >> 15) & 0xFF
    return bytes(result)


def render_bytes(data: bytes) -> str:
    """Lossless editable representation: printable ASCII or <HH> bytes."""
    pieces: list[str] = []
    for value in data:
        char = chr(value)
        if 0x20 <= value <= 0x7E and char not in "<>":
            pieces.append(char)
        else:
            pieces.append(f"<{value:02X}>")
    return "".join(pieces)


def decode_mgs_preview(data: bytes) -> str:
    """Human-readable preview of confirmed MGS text tokens (not used to rebuild)."""
    pieces: list[str] = []
    cursor = 0
    while cursor < len(data):
        first = data[cursor]
        if first == 0:
            pieces.append("<END>")
            cursor += 1
        elif first == 0x1F and cursor + 1 < len(data):
            pieces.append(f"<G{data[cursor + 1]:02X}>")
            cursor += 2
        elif first < 0x80:
            pieces.append(chr(first) if 0x20 <= first <= 0x7E else f"<{first:02X}>")
            cursor += 1
        elif cursor + 1 >= len(data):
            pieces.append(f"<{first:02X}>")
            cursor += 1
        else:
            token = (first << 8) | data[cursor + 1]
            low = token & 0xFF
            if first == 0x80 and 0x20 <= low <= 0x7E:
                pieces.append(chr(low))
            elif first == 0x81 and 1 <= low <= 0x7F:
                pieces.append(chr(0x3040 + low))
            elif first == 0x82 and 1 <= low <= 0x7F:
                pieces.append(chr(0x30A0 + low))
            elif 0x8C01 <= token < 0x9000 and low != 0:
                relative = token - 0x8C01
                pieces.append(f"<G{relative - relative // 256:03d}>")
            elif 0x9001 <= token < 0x9400 and low != 0:
                relative = token - 0x9001
                pieces.append(f"<D{relative - relative // 256:03d}>")
            else:
                pieces.append(f"<{token:04X}>")
            cursor += 2
    return "".join(pieces)


TOKEN = re.compile(r"<([0-9A-Fa-f]{2})>")


def parse_rendered(text: str, character_map: dict[str, bytes] | None = None) -> bytes:
    character_map = character_map or {}
    result = bytearray()
    cursor = 0
    while cursor < len(text):
        match = TOKEN.match(text, cursor)
        if match:
            result.append(int(match.group(1), 16))
            cursor = match.end()
            continue
        char = text[cursor]
        if char in character_map:
            result.extend(character_map[char])
            cursor += 1
            continue
        if char in "<>":
            raise CodecError(
                f"literal {char!r} is not allowed; encode it as <{ord(char):02X}>"
            )
        value = ord(char)
        if not 0x20 <= value <= 0x7E:
            raise CodecError(
                f"non-ASCII character {char!r} needs a character-map encoder"
            )
        result.append(value)
        cursor += 1
    return bytes(result)


@dataclass
class Resource:
    table_word: int
    data: bytes

    @property
    def flags(self) -> int:
        return self.table_word & 0xFF000000

    @property
    def is_script(self) -> bool:
        return self.flags != 0x80000000


class GcxRecord:
    def __init__(self, raw: bytes, source_offset: int = 0):
        self.raw = raw
        self.source_offset = source_offset
        self.timestamp = u32(raw, 0)
        cursor = 4
        self.proc_table: list[int] = []
        while True:
            value = u32(raw, cursor)
            cursor += 4
            if value == END_MARKER:
                break
            self.proc_table.append(value)
            if len(self.proc_table) > 0x10000:
                raise CodecError("implausibly large GCX procedure table")
        self.block_start = cursor
        if self.block_start + 20 > len(raw):
            raise CodecError("truncated GCX block header")
        (
            self.proc_offset,
            self.resource_table_offset,
            self.string_resources_offset,
            self.font_data_offset,
            self.seed,
        ) = struct.unpack_from("<5I", raw, self.block_start)
        if not (
            20
            <= self.resource_table_offset
            <= self.string_resources_offset
            <= self.font_data_offset
            <= self.proc_offset
        ):
            raise CodecError("invalid GCX section offsets")
        if self.block_start + self.proc_offset + 4 > len(raw):
            raise CodecError("GCX procedure block is outside record")

    @classmethod
    def from_codec(cls, codec: bytes, start: int) -> tuple[GcxRecord, int]:
        # Parse enough structure to locate the main procedure, which is the
        # final logical object in every tested codec.dat record.
        timestamp = u32(codec, start)
        del timestamp
        cursor = start + 4
        count = 0
        while u32(codec, cursor) != END_MARKER:
            cursor += 4
            count += 1
            if count > 0x10000:
                raise CodecError(f"bad GCX procedure table at 0x{start:x}")
        block_start = cursor + 4
        if block_start + 20 > len(codec):
            raise CodecError(f"truncated GCX at 0x{start:x}")
        proc_offset = u32(codec, block_start)
        main_offset_field = block_start + proc_offset
        proc_start = main_offset_field + 4
        main_relative = u32(codec, main_offset_field)
        main_size_field = proc_start + main_relative
        main_size = u32(codec, main_size_field)
        logical_end = main_size_field + 4 + main_size
        stored_end = align(logical_end)
        if logical_end <= start or stored_end > len(codec):
            raise CodecError(f"invalid GCX size at 0x{start:x}")
        return cls(codec[start:stored_end], start), stored_end

    def resources(self) -> list[Resource]:
        count_bytes = self.string_resources_offset - self.resource_table_offset
        if count_bytes % 4:
            raise CodecError("unaligned GCX resource table")
        count = count_bytes // 4
        strings_start = self.block_start + self.string_resources_offset
        strings_end = self.block_start + self.font_data_offset
        encrypted = self.raw[strings_start:strings_end]
        plain = crypt(self.seed, encrypted)
        words = [
            u32(self.raw, self.block_start + self.resource_table_offset + i * 4)
            for i in range(count)
        ]
        result: list[Resource] = []
        for index, word in enumerate(words):
            offset = word & 0x00FFFFFF
            end = (
                words[index + 1] & 0x00FFFFFF
                if index + 1 < len(words)
                else len(plain)
            )
            if offset > end or end > len(plain):
                raise CodecError(f"invalid GCX resource offsets at index {index}")
            result.append(Resource(word, plain[offset:end]))
        return result

    def replace_resources(
        self,
        replacements: dict[int, bytes],
        preserve_layout: bool = False,
        string_region_size: int | None = None,
        alias_adjacent: bool = False,
        alias_all: bool = False,
    ) -> bytes:
        if not replacements:
            return self.raw
        resources = self.resources()
        for index in replacements:
            if index < 0 or index >= len(resources):
                raise CodecError(f"resource index out of range: {index}")

        old_string_start = self.block_start + self.string_resources_offset
        old_font_start = self.block_start + self.font_data_offset
        old_proc_start = self.block_start + self.proc_offset

        final_data = [replacements.get(index, resource.data)
                      for index, resource in enumerate(resources)]
        plain = bytearray()
        words: list[int] = []
        aliases: dict[tuple[int, bytes], int] = {}
        index = 0
        while index < len(resources):
            if len(plain) > 0x00FFFFFF:
                raise CodecError("GCX resource region exceeds 24-bit offset limit")
            resource = resources[index]
            if alias_all:
                key = (resource.flags, final_data[index])
                if key in aliases:
                    words.append(resource.flags | aliases[key])
                else:
                    aliases[key] = len(plain)
                    words.append(resource.flags | len(plain))
                    plain.extend(final_data[index])
                index += 1
                continue
            end = index + 1
            if alias_adjacent and final_data[index] not in (b"", b"\0"):
                while (end < len(resources)
                       and resources[end].flags == resource.flags
                       and final_data[end] == final_data[index]):
                    end += 1
            words.extend(resource.flags | len(plain) for _ in range(index, end))
            plain.extend(final_data[index])
            index = end

        old_plain_size = old_font_start - old_string_start
        if preserve_layout and string_region_size is not None:
            raise CodecError("select only one string-region layout mode")
        if string_region_size is not None:
            if string_region_size < 0:
                raise CodecError("negative target string-region size")
            if len(plain) > string_region_size:
                raise CodecError(
                    f"replacement strings exceed target region by "
                    f"{len(plain) - string_region_size} bytes"
                )
            plain.extend(b"\0" * (string_region_size - len(plain)))
        elif preserve_layout:
            if len(plain) > old_plain_size:
                raise CodecError(
                    f"replacement strings exceed fixed region by "
                    f"{len(plain) - old_plain_size} bytes"
                )
            plain.extend(b"\0" * (old_plain_size - len(plain)))

        # The font and procedure sections are read as word-addressed data by
        # the game.  Replacement strings may have arbitrary byte lengths, so
        # preserve their required 4-byte boundary with encrypted zero padding.
        # The final resource conventionally owns this trailing padding.
        if not preserve_layout:
            plain.extend(b"\0" * (align(len(plain), 4) - len(plain)))

        delta = len(plain) - (old_font_start - old_string_start)
        new_font_offset = self.font_data_offset + delta
        new_proc_offset = self.proc_offset + delta
        if new_font_offset < self.string_resources_offset or new_proc_offset < new_font_offset:
            raise CodecError("replacement produced invalid GCX section ordering")

        output = bytearray()
        output.extend(self.raw[:old_string_start])
        output.extend(crypt(self.seed, bytes(plain)))
        output.extend(self.raw[old_font_start:old_proc_start])
        output.extend(self.raw[old_proc_start:])

        struct.pack_into("<II", output, self.block_start + 12, new_font_offset, self.seed)
        struct.pack_into("<I", output, self.block_start, new_proc_offset)
        table = self.block_start + self.resource_table_offset
        for index, word in enumerate(words):
            struct.pack_into("<I", output, table + index * 4, word)

        # Record padding belongs to codec.dat rather than GCX semantics.
        logical_size = self.logical_size(output)
        del output[logical_size:]
        output.extend(b"\0" * (align(len(output)) - len(output)))
        return bytes(output)

    def logical_size(self, data: bytes | bytearray | None = None) -> int:
        source = self.raw if data is None else data
        proc_offset = u32(source, self.block_start)
        main_offset_field = self.block_start + proc_offset
        proc_start = main_offset_field + 4
        main_relative = u32(source, main_offset_field)
        main_size_field = proc_start + main_relative
        return main_size_field + 4 + u32(source, main_size_field)

    def metadata(self, index: int) -> dict[str, object]:
        resources = self.resources()
        return {
            "index": index,
            "offset": self.source_offset,
            "stored_size": len(self.raw),
            "logical_size": self.logical_size(),
            "timestamp": f"0x{self.timestamp:08x}",
            "procedure_count": len(self.proc_table),
            "resource_count": len(resources),
            "seed": f"0x{self.seed:08x}",
        }


def relocate_gcx_internal_offsets(
    record: GcxRecord, old_offset: int, new_offset: int
) -> bytes:
    """Relocate every procedure-table target at/after an internal boundary.

    Procedure-table words use their high byte as flags and their low 24 bits as
    a record-local target.  When a suffix beginning at ``old_offset`` moves to
    ``new_offset``, preserve the flags and apply that signed delta to every
    target in the moved suffix.
    """
    if not 0 <= old_offset <= 0x00FFFFFF:
        raise CodecError(f"old GCX internal offset is outside 24-bit range: {old_offset}")
    if not 0 <= new_offset <= 0x00FFFFFF:
        raise CodecError(f"new GCX internal offset is outside 24-bit range: {new_offset}")
    delta = new_offset - old_offset
    raw = bytearray(record.raw)
    patched_fields: list[int] = []
    for index, word in enumerate(record.proc_table):
        inner_offset = word & 0x00FFFFFF
        if inner_offset < old_offset:
            continue
        relocated = inner_offset + delta
        if not 0 <= relocated <= 0x00FFFFFF:
            raise CodecError(
                f"GCX53 relocated procedure offset is outside 24-bit range: "
                f"0x{inner_offset:x} + {delta}"
            )
        new_word = (word & 0xFF000000) | relocated
        field_offset = 4 + index * 4
        struct.pack_into("<I", raw, field_offset, new_word)
        patched_fields.append(field_offset)

    if not patched_fields:
        raise CodecError(
            f"no GCX procedure offsets found at/after 0x{old_offset:x}"
        )
    return bytes(raw)


def relocate_gcx53_inner_offsets(record: GcxRecord, delta: int) -> bytes:
    """Validated GCX53 wrapper around the generic internal-offset fixer."""
    relocated = relocate_gcx_internal_offsets(record, 0x1000, 0x1000 + delta)
    patched_fields = {
        4 + index * 4
        for index, old_word in enumerate(record.proc_table)
        if old_word != u32(relocated, 4 + index * 4)
    }

    expected_fields = {0x64, 0x70, 0x7C}
    if patched_fields != expected_fields:
        raise CodecError(
            "unexpected GCX53 inner-offset fields: "
            f"expected {sorted(expected_fields)}, got {sorted(patched_fields)}"
        )
    return relocated


def parse_codec(data: bytes) -> list[GcxRecord]:
    records: list[GcxRecord] = []
    cursor = 0
    while cursor < len(data):
        record, cursor = GcxRecord.from_codec(data, cursor)
        records.append(record)
    if cursor != len(data):
        raise CodecError("codec.dat did not end on a GCX boundary")
    return records


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def command_info(args: argparse.Namespace) -> None:
    data = args.codec.read_bytes()
    records = parse_codec(data)
    resource_count = sum(len(record.resources()) for record in records)
    print(f"size: {len(data)}")
    print(f"sha256: {sha256(data)}")
    print(f"GCX records: {len(records)}")
    print(f"resources: {resource_count}")


def command_extract(args: argparse.Namespace) -> None:
    data = args.codec.read_bytes()
    records = parse_codec(data)
    args.output.mkdir(parents=True, exist_ok=True)
    catalog = {
        "format": "MGS3D codec.dat / sequential GCX",
        "source_size": len(data),
        "source_sha256": sha256(data),
        "alignment": ALIGNMENT,
        "records": [],
    }
    for index, record in enumerate(records):
        filename = f"{index:05d}_{record.source_offset:08x}.gcx"
        (args.output / filename).write_bytes(record.raw)
        item = record.metadata(index)
        item["filename"] = filename
        catalog["records"].append(item)
    (args.output / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"extracted {len(records)} GCX records to {args.output}")


def command_dump(args: argparse.Namespace) -> None:
    records = parse_codec(args.codec.read_bytes())
    units: list[dict[str, object]] = []
    for gcx_index, record in enumerate(records):
        if args.gcx is not None and gcx_index not in args.gcx:
            continue
        for resource_index, resource in enumerate(record.resources()):
            if args.strings_only and resource.is_script:
                continue
            text = render_bytes(resource.data)
            if args.contains and args.contains.lower() not in text.lower():
                continue
            units.append({
                "gcx": gcx_index,
                "resource": resource_index,
                "kind": "script" if resource.is_script else "string",
                "original_size": len(resource.data),
                "preview": decode_mgs_preview(resource.data),
                "text": text,
            })
    document = {
        "format": "mgs3d-codec-translation-v1",
        "note": "Edit text only. <HH> tokens represent exact non-ASCII bytes.",
        "character_map": {},
        "units": units,
    }
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"dumped {len(units)} resources to {args.output}")


def command_apply(args: argparse.Namespace) -> None:
    original = args.codec.read_bytes()
    records = parse_codec(original)
    document = json.loads(args.translation.read_text(encoding="utf-8"))
    character_map, units = validate_codec_translation(document)
    changes: dict[int, dict[int, bytes]] = {}
    for unit in units:
        gcx_index = int(unit["gcx"])
        resource_index = int(unit["resource"])
        if gcx_index < 0 or gcx_index >= len(records):
            raise CodecError(f"GCX index out of range: {gcx_index}")
        replacement = parse_rendered(unit["text"], character_map)
        resources = records[gcx_index].resources()
        if resource_index < 0 or resource_index >= len(resources):
            raise CodecError(
                f"resource index out of range: GCX {gcx_index}, resource {resource_index}"
            )
        current = resources[resource_index].data
        if replacement != current:
            changes.setdefault(gcx_index, {})[resource_index] = replacement

    output = bytearray()
    offsets: list[int] = []
    for index, record in enumerate(records):
        offsets.append(len(output))
        output.extend(record.replace_resources(changes.get(index, {})))
    args.output.write_bytes(output)
    print(
        f"wrote {args.output}: {len(changes)} GCX records changed, "
        f"{len(original)} -> {len(output)} bytes, sha256={sha256(output)}"
    )


def command_validate_translation(args: argparse.Namespace) -> None:
    document = json.loads(args.translation.read_text(encoding="utf-8"))
    character_map, units = validate_codec_translation(document)
    gcx_indices: set[int] = set()
    hangul: set[str] = set()
    total_rendered_bytes = 0
    for unit_index, unit in enumerate(units):
        text = str(unit["text"])
        local_map = dict(character_map)
        for character in text:
            if 0xAC00 <= ord(character) <= 0xD7A3:
                hangul.add(character)
                local_map.setdefault(character, b"\x8c\x01")
        try:
            total_rendered_bytes += len(parse_rendered(text, local_map))
        except CodecError as exc:
            raise CodecError(f"unit {unit_index} text is not encodable: {exc}") from exc
        gcx_indices.add(int(unit["gcx"]))
    report = {
        "format": "mgs3d-codec-translation-validation-v1",
        "translation": str(args.translation),
        "valid": True,
        "units": len(units),
        "gcx_records": len(gcx_indices),
        "character_map_entries": len(character_map),
        "unique_hangul": len(hangul),
        "rendered_bytes_before_font_allocation": total_rendered_bytes,
    }
    print(
        f"valid translation: units={report['units']}, "
        f"GCX={report['gcx_records']}, Hangul={report['unique_hangul']}, "
        f"character-map={report['character_map_entries']}"
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"validation report: {args.json}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="validate and summarize codec.dat")
    info.add_argument("codec", type=Path)
    info.set_defaults(function=command_info)

    extract = subparsers.add_parser("extract", help="extract all GCX records")
    extract.add_argument("codec", type=Path)
    extract.add_argument("output", type=Path)
    extract.set_defaults(function=command_extract)

    dump = subparsers.add_parser("dump", help="dump editable GCX resources to JSON")
    dump.add_argument("codec", type=Path)
    dump.add_argument("output", type=Path)
    dump.add_argument(
        "--strings-only",
        action="store_true",
        help="include only resources marked with the GCX string flag",
    )
    dump.add_argument(
        "--gcx",
        action="append",
        type=int,
        help="dump only this GCX index (repeatable)",
    )
    dump.add_argument(
        "--contains",
        help="dump only resources whose lossless representation contains text",
    )
    dump.set_defaults(function=command_dump)

    validate = subparsers.add_parser(
        "validate-translation",
        help="validate and summarize a translation JSON without game files",
    )
    validate.add_argument("translation", type=Path)
    validate.add_argument("--json", type=Path)
    validate.set_defaults(function=command_validate_translation)

    apply_cmd = subparsers.add_parser("apply", help="apply edited JSON and rebuild")
    apply_cmd.add_argument("codec", type=Path)
    apply_cmd.add_argument("translation", type=Path)
    apply_cmd.add_argument("output", type=Path)
    apply_cmd.set_defaults(function=command_apply)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (CodecError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
