#!/usr/bin/env python3
"""Evidence-backed analysis of the MGS3D global glyph-page lookup.

This tool never modifies game data.  Runtime pointer values cannot be recovered
from code.bin, so static initialization evidence and structured media token use
are deliberately reported separately.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402

DEFAULT_CODE = ROOT / "experiments/ps2_korean/full_build/rebuild_2026-08-08/code_en_decompressed_verified.bin"
DEFAULT_MOVIE = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/movie_live_base.dat"
DEFAULT_DEMO = ROOT / "experiments/scene_fixed_natural_2026-08-12/demo_live_safe_base.dat"
DEFAULT_CODEC = ROOT / "experiments/full_korean_apply_2026-08-12/codec_official_plus_3ds.dat"
DEFAULT_CSV = ROOT / "analysis/glyph_page_table.csv"
DEFAULT_RUNTIME_CSV = ROOT / "analysis/glyph_page_runtime_dump.csv"

EXPECTED_CODE_SHA256 = "10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7"
TABLE_VA = 0x00A46FD8
SETTER_VA = 0x0010A894
GLYPH_SIZE = 64
GLYPHS_PER_PAGE = 1020
GENERIC_BASE = 0x8400
FLAG_MASK = 0x6000

# All exact little-endian A46FD8 literals in the verified image.
EXPECTED_LITERAL_OFFSETS = (0xA8AC, 0x5E878, 0x5EF18, 0x5435C0)


def integer(text: str) -> int:
    return int(text, 0)


def decode_glyph_token(token: int) -> tuple[int, int]:
    """Return renderer page/index after its flag-bit normalization."""
    if not 0 <= token <= 0xFFFF:
        raise ValueError("token must fit in 16 bits")
    normalized = token & ~FLAG_MASK
    if normalized < GENERIC_BASE + 1:
        raise ValueError(f"0x{token:04X} is not a generic-page glyph token")
    page, within = divmod(normalized - GENERIC_BASE, 0x400)
    if page > 6:
        raise ValueError("normalized generic page exceeds the representable page 0..6 range")
    if within == 0 or (within & 0xFF) == 0:
        raise ValueError(f"0x{token:04X} lands on an xx00 hole")
    index = within - 1 - ((within - 1) // 0x100)
    if not 0 <= index < GLYPHS_PER_PAGE:
        raise ValueError("decoded glyph index is outside a 1020-glyph page")
    return page, index


def encode_glyph_token(page: int, index: int) -> int:
    """Encode an unflagged generic-page token accepted by the renderer."""
    if not 0 <= page <= 6:
        raise ValueError("page must be 0..6; page 7 aliases after the 0x6000 flag mask")
    if not 0 <= index < GLYPHS_PER_PAGE:
        raise ValueError("index must be 0..1019")
    group, offset = divmod(index, 255)
    token = GENERIC_BASE + page * 0x400 + group * 0x100 + offset + 1
    if token & FLAG_MASK:
        raise ValueError("encoded token collides with renderer flag bits")
    return token


def verify_code(path: Path) -> bytes:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_CODE_SHA256:
        raise ValueError(f"unexpected code image SHA-256: {digest}")
    needle = struct.pack("<I", TABLE_VA)
    offsets = tuple(i for i in range(len(data) - 3) if data[i : i + 4] == needle)
    if offsets != EXPECTED_LITERAL_OFFSETS:
        raise ValueError(f"table literal sites changed: {[hex(x) for x in offsets]}")
    return data


def iter_tokens(raw: bytes):
    i = 0
    while i < len(raw):
        lead = raw[i]
        if lead == 0:
            break
        if lead >= 0x80 and i + 1 < len(raw):
            yield (lead << 8) | raw[i + 1]
            i += 2
        else:
            i += 1


def add_generic(counter: Counter[int], raw: bytes) -> None:
    for token in iter_tokens(raw):
        try:
            page, _ = decode_glyph_token(token)
        except ValueError:
            continue
        counter[page] += 1


def scan_movie(path: Path) -> Counter[int]:
    result: Counter[int] = Counter()
    _, records, _ = parse_records(path.read_bytes())
    for record in records:
        for subtitle in record.subtitles:
            add_generic(result, subtitle.raw)
    return result


def scan_codec(path: Path) -> Counter[int]:
    result: Counter[int] = Counter()
    for record in parse_codec(path.read_bytes()):
        for resource in record.resources():
            add_generic(result, resource.data)
    return result


def page_rows(movie: Path, demo: Path, codec: Path) -> list[dict[str, object]]:
    counts = {
        "movie": scan_movie(movie),
        "demo": scan_movie(demo),
        "codec": scan_codec(codec),
    }
    initialization = {
        0: "direct write at 0x643594: font_base+0x3080",
        1: "setter-capable; no direct initializer found",
        2: "setter-capable; page 4 is derived when page 2 is set",
        3: "setter-capable; no direct initializer found",
        4: "0x10A8A0/0x10A8A4: page2_pointer+0xFF00",
        5: "direct write at 0x6435A0: font_base+0x12F80",
        6: "direct write at 0x6435A4: font_base+0x22E80",
    }
    rows = []
    for page in range(7):
        total = sum(c[page] for c in counts.values())
        if total:
            status = "used_in_scanned_dialogue"
        elif page in (0, 4, 5, 6):
            status = "initialized_not_seen_in_scanned_dialogue"
        else:
            status = "runtime_state_unknown"
        rows.append({
            "page": page,
            "token_range": f"0x{GENERIC_BASE + page*0x400 + 1:04X}-0x{GENERIC_BASE + (page+1)*0x400 - 1:04X} (xx00 excluded)",
            "pointer": "runtime; static image cannot supply value",
            "status": status,
            "glyph_count": GLYPHS_PER_PAGE,
            "movie_tokens": counts["movie"][page],
            "demo_tokens": counts["demo"][page],
            "codec_tokens": counts["codec"][page],
            "notes": initialization[page],
        })
    return rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_runtime_log(log_path: Path) -> list[dict[str, object]]:
    """Parse GLYPH_DUMP markers emitted by citra_gdb_mi_controller.py."""
    import re

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    state: str | None = None
    prior: list[int] | None = None
    rows: list[dict[str, object]] = []
    for line in lines:
        begin = re.search(r"GLYPH_DUMP_BEGIN:([A-Za-z0-9_.-]+)", line)
        if begin:
            state = {
                "cold_boot": "post_init_first_attach",
                "title_or_init": "post_init_plus_12s",
            }.get(begin.group(1), begin.group(1))
            continue
        if state is None or "memory=[" not in line or "contents=" not in line:
            continue
        match = re.search(r'contents="([0-9a-fA-F]{56})"', line)
        if not match:
            continue
        raw = bytes.fromhex(match.group(1))
        pointers = list(struct.unpack("<7I", raw))
        for page, pointer in enumerate(pointers):
            rows.append({
                "state": state,
                "page": page,
                "pointer": f"0x{pointer:08X}",
                "is_null": str(pointer == 0).lower(),
                "changed": "initial" if prior is None else str(pointer != prior[page]).lower(),
                "notes": "runtime GDB read at 0x00A46FD8",
            })
        prior = pointers
        state = None
    if not rows:
        raise ValueError("no complete GLYPH_DUMP memory response found in log")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dump-pages", action="store_true")
    action.add_argument("--check-unused-pages", action="store_true")
    action.add_argument("--decode-token", type=integer, metavar="TOKEN")
    action.add_argument("--encode-token", nargs=2, type=integer, metavar=("PAGE", "INDEX"))
    action.add_argument("--parse-runtime-log", type=Path, metavar="LOG")
    parser.add_argument("--code", type=Path, default=DEFAULT_CODE)
    parser.add_argument("--movie", type=Path, default=DEFAULT_MOVIE)
    parser.add_argument("--demo", type=Path, default=DEFAULT_DEMO)
    parser.add_argument("--codec", type=Path, default=DEFAULT_CODEC)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--runtime-csv", type=Path, default=DEFAULT_RUNTIME_CSV)
    args = parser.parse_args()

    if args.decode_token is not None:
        page, index = decode_glyph_token(args.decode_token)
        print(f"token=0x{args.decode_token:04X} page={page} index={index}")
        return 0
    if args.encode_token is not None:
        page, index = args.encode_token
        token = encode_glyph_token(page, index)
        print(f"page={page} index={index} token=0x{token:04X}")
        return 0
    if args.parse_runtime_log is not None:
        rows = parse_runtime_log(args.parse_runtime_log)
        write_csv(rows, args.runtime_csv)
        print(f"runtime states={len(rows)//7} rows={len(rows)} CSV: {args.runtime_csv}")
        return 0

    verify_code(args.code)
    rows = page_rows(args.movie, args.demo, args.codec)
    write_csv(rows, args.csv)
    if args.dump_pages:
        for row in rows:
            print(
                f"page {row['page']:02d}: {row['status']}; "
                f"movie={row['movie_tokens']} demo={row['demo_tokens']} codec={row['codec_tokens']}; "
                f"{row['notes']}"
            )
        print(f"CSV: {args.csv}")
    else:
        candidates = [r for r in rows if r["status"] == "runtime_state_unknown"]
        print("No page is statically proven NULL or globally unused.")
        runtime_non_null: set[int] = set()
        if args.runtime_csv.exists():
            with args.runtime_csv.open(newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if row.get("is_null") == "false":
                        runtime_non_null.add(int(row["page"]))
            if runtime_non_null:
                print("Observed runtime non-NULL pages: " + ", ".join(map(str, sorted(runtime_non_null))))
        candidates = [r for r in candidates if int(r["page"]) not in runtime_non_null]
        if candidates:
            print("Still runtime-unverified candidates: " + ", ".join(str(r["page"]) for r in candidates))
        else:
            print("No reusable candidate remains after runtime evidence.")
        print("Pages absent from dialogue may still serve UI/other language fonts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
