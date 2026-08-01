#!/usr/bin/env python3
"""List or extract the DARC (.la2) and MT Framework ARC files in this project."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath


class FormatError(ValueError):
    pass


@dataclass
class Entry:
    path: str
    offset: int
    stored_size: int
    size: int
    compressed: bool
    type_hash: str | None = None
    flags: str | None = None


def safe_target(root: Path, archive_path: str) -> Path:
    """Convert an archive path to a path below root, rejecting traversal."""
    normalized = archive_path.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise FormatError(f"unsafe archive path: {archive_path!r}")
    # A drive prefix and an absolute POSIX path are both invalid here.
    if PurePosixPath(normalized).is_absolute() or ":" in parts[0]:
        raise FormatError(f"unsafe archive path: {archive_path!r}")
    return root.joinpath(*parts)


def checked_slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise FormatError(
            f"{label} is outside archive: offset=0x{offset:x}, size=0x{size:x}"
        )
    return data[offset : offset + size]


def read_cstring(data: bytes, offset: int, encoding: str, unit: int) -> str:
    if offset < 0 or offset >= len(data):
        raise FormatError(f"string offset outside archive: 0x{offset:x}")
    cursor = offset
    while cursor + unit <= len(data):
        if data[cursor : cursor + unit] == b"\0" * unit:
            try:
                return data[offset:cursor].decode(encoding)
            except UnicodeDecodeError as exc:
                raise FormatError(f"invalid {encoding} string at 0x{offset:x}") from exc
        cursor += unit
    raise FormatError(f"unterminated string at 0x{offset:x}")


def parse_darc(data: bytes) -> tuple[dict[str, object], list[Entry]]:
    if data[:4] != b"darc":
        raise FormatError("not a DARC archive")
    if len(data) < 0x1C:
        raise FormatError("truncated DARC header")

    bom_bytes = data[4:6]
    if bom_bytes == b"\xff\xfe":
        order, encoding = "<", "utf-16-le"
    elif bom_bytes == b"\xfe\xff":
        order, encoding = ">", "utf-16-be"
    else:
        raise FormatError(f"unsupported DARC BOM: {bom_bytes.hex()}")

    bom, header_size, version, file_size, table_offset, table_size, data_offset = (
        struct.unpack_from(order + "HHIIIII", data, 4)
    )
    if header_size < 0x1C or file_size > len(data):
        raise FormatError("invalid DARC header sizes")
    if table_offset + 12 > len(data):
        raise FormatError("DARC entry table is outside archive")

    root_word, root_parent, entry_count = struct.unpack_from(
        order + "III", data, table_offset
    )
    if not (root_word & 0x01000000) or entry_count < 1:
        raise FormatError("invalid DARC root entry")
    entries_end = table_offset + entry_count * 12
    if entries_end > len(data) or entries_end > table_offset + table_size:
        raise FormatError("DARC entry table is truncated")
    names_offset = entries_end

    result: list[Entry] = []
    directories: list[tuple[int, str]] = [(entry_count, "")]
    for index in range(1, entry_count):
        while directories and index >= directories[-1][0]:
            directories.pop()
        parent = directories[-1][1] if directories else ""
        word, value1, value2 = struct.unpack_from(
            order + "III", data, table_offset + index * 12
        )
        is_directory = bool(word & 0x01000000)
        name_relative = word & 0x00FFFFFF
        name = read_cstring(data, names_offset + name_relative, encoding, 2)
        path = f"{parent}/{name}" if parent else name
        if is_directory:
            if value1 >= index or value2 <= index or value2 > entry_count:
                raise FormatError(f"invalid DARC directory entry {index}")
            # These LA2 files use a literal "." directory below the unnamed
            # DARC root. Treat it as the extraction root, not a path element.
            directories.append((value2, parent if name == "." else path))
            continue
        checked_slice(data, value1, value2, f"DARC entry {path}")
        result.append(Entry(path, value1, value2, value2, False))

    metadata = {
        "format": "DARC",
        "byte_order": "little" if order == "<" else "big",
        "header_size": header_size,
        "version": f"0x{version:08x}",
        "declared_file_size": file_size,
        "table_offset": table_offset,
        "table_size": table_size,
        "data_offset": data_offset,
        "entry_count_including_directories": entry_count,
        "file_count": len(result),
        "container_compression": "none",
    }
    return metadata, result


def parse_arc(data: bytes) -> tuple[dict[str, object], list[Entry]]:
    if data[:4] != b"ARC\0":
        raise FormatError("not an MT Framework ARC archive")
    if len(data) < 12:
        raise FormatError("truncated ARC header")
    version, entry_count, reserved = struct.unpack_from("<HHI", data, 4)
    table_end = 12 + entry_count * 0x50
    if table_end > len(data):
        raise FormatError("ARC entry table is truncated")

    result: list[Entry] = []
    for index in range(entry_count):
        entry_offset = 12 + index * 0x50
        raw_name = data[entry_offset : entry_offset + 0x40].split(b"\0", 1)[0]
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError as exc:
            raise FormatError(f"invalid ARC name in entry {index}") from exc
        if not name:
            raise FormatError(f"empty ARC name in entry {index}")
        type_hash, stored_size, packed_size, data_offset = struct.unpack_from(
            "<IIII", data, entry_offset + 0x40
        )
        size = packed_size & 0x1FFFFFFF
        flags = packed_size & 0xE0000000
        blob = checked_slice(data, data_offset, stored_size, f"ARC entry {name}")
        compressed = blob[:2] in (b"x\x01", b"x\x5e", b"x\x9c", b"x\xda")
        result.append(
            Entry(
                name,
                data_offset,
                stored_size,
                size,
                compressed,
                f"0x{type_hash:08x}",
                f"0x{flags:08x}",
            )
        )

    metadata = {
        "format": "MT Framework ARC",
        "byte_order": "little",
        "version": f"0x{version:04x}",
        "reserved": f"0x{reserved:08x}",
        "table_offset": 12,
        "entry_size": 0x50,
        "entry_count": entry_count,
        "per_entry_compression": "zlib or stored (detected per entry)",
    }
    return metadata, result


def parse(data: bytes) -> tuple[dict[str, object], list[Entry]]:
    if data[:4] == b"darc":
        return parse_darc(data)
    if data[:4] == b"ARC\0":
        return parse_arc(data)
    raise FormatError(f"unsupported archive magic: {data[:4]!r}")


def payload(data: bytes, entry: Entry) -> bytes:
    blob = checked_slice(data, entry.offset, entry.stored_size, entry.path)
    if not entry.compressed:
        if len(blob) != entry.size:
            raise FormatError(f"stored-size mismatch for {entry.path}")
        return blob
    try:
        unpacked = zlib.decompress(blob)
    except zlib.error as exc:
        raise FormatError(f"zlib decompression failed for {entry.path}: {exc}") from exc
    if len(unpacked) != entry.size:
        raise FormatError(
            f"decompressed-size mismatch for {entry.path}: "
            f"expected {entry.size}, got {len(unpacked)}"
        )
    return unpacked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("-l", "--list", action="store_true", help="list entries only")
    parser.add_argument(
        "--manifest", action="store_true", help="write _archive_manifest.json"
    )
    args = parser.parse_args()

    try:
        data = args.archive.read_bytes()
        metadata, entries = parse(data)
        if args.list:
            print(json.dumps(metadata, ensure_ascii=False, indent=2))
            for item in entries:
                method = "zlib" if item.compressed else "stored"
                print(
                    f"{item.offset:08x} {item.stored_size:8d} {item.size:8d} "
                    f"{method:6s} {item.path}"
                )
            return 0

        output = args.output or args.archive.with_name(args.archive.name + "_extracted")
        output.mkdir(parents=True, exist_ok=True)
        for item in entries:
            target = safe_target(output, item.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload(data, item))
            print(item.path)
        if args.manifest:
            manifest = {**metadata, "entries": [asdict(item) for item in entries]}
            (output / "_archive_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return 0
    except (OSError, FormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
