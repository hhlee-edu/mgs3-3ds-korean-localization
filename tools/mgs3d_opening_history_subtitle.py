#!/usr/bin/env python3
"""Add the missing Korean history card to demo scene 127 without relocation."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_rendered
from mgs3d_movie_tool import parse_records


LINES = (
    "제2차 세계대전 종결 후,",
    "세계는 동서로 나뉘게 되었다.",
    "냉전이라 불리게 되는 시대의",
    "막이 열린 것이다.",
)
TIMES = ((0x0000, 0x0B00), (0x0B00, 0x1600), (0x1600, 0x2100), (0x2100, 0x2B00))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("character_map", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--manifest", type=Path)
    args = ap.parse_args()

    original = args.source.read_bytes()
    _, records, _ = parse_records(original)
    record = records[287]
    if len(record.subtitles) < 5 or record.subtitles[4].entry_type != 1:
        raise SystemExit("opening record layout differs from verified baseline")
    mapping_doc = json.loads(args.character_map.read_text(encoding="utf-8"))
    mapping = {ch: bytes.fromhex(token) for ch, token in mapping_doc["character_map"].items()}
    output = bytearray(original)
    changes = []
    for index, (line, times) in enumerate(zip(LINES, TIMES)):
        subtitle = record.subtitles[index]
        encoded = parse_rendered(line + "<00>", mapping)
        capacity = len(subtitle.original) - 4 - 12
        if len(encoded) > capacity:
            raise SystemExit(f"entry {index}: needs {len(encoded)}, capacity {capacity}")
        entry_start = subtitle.offset - 4
        old_header = struct.unpack_from("<I", output, entry_start)[0]
        declared_size = old_header & 0xFFFF
        struct.pack_into("<I", output, entry_start, (1 << 16) | declared_size)
        text_start = subtitle.offset
        tail_start = entry_start + len(subtitle.original) - 12
        output[text_start:tail_start] = encoded.ljust(tail_start - text_start, b"\0")
        output[tail_start:tail_start + 12] = struct.pack("<III", times[0], times[1], 0)
        changes.append({"entry": index, "text": line, "start_ms": times[0], "end_ms": times[1], "capacity": capacity, "encoded": len(encoded)})

    rebuilt = bytes(output)
    _, reparsed, _ = parse_records(rebuilt)
    for index, line in enumerate(LINES):
        if reparsed[287].subtitles[index].entry_type != 1:
            raise SystemExit(f"entry {index} did not become type 1")
    args.output.write_bytes(rebuilt)
    manifest = {
        "format": "mgs3d-opening-history-subtitle-v1",
        "source": str(args.source),
        "source_sha256": sha(original),
        "output_sha256": sha(rebuilt),
        "file_size": len(rebuilt),
        "file_size_preserved": len(rebuilt) == len(original),
        "record": 287,
        "record_offset": record.offset,
        "record_size": len(record.raw),
        "record_position_preserved": reparsed[287].offset == record.offset and len(reparsed[287].raw) == len(record.raw),
        "first_existing_english_start_ms": int.from_bytes(record.subtitles[4].tail[:4], "little"),
        "changes": changes,
    }
    manifest_path = args.manifest or args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
