#!/usr/bin/env python3
"""Freeze the selected glyph decoder and validate full-page boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
DEFAULT_PAGE = ROOT / "experiments/global_korean_page_build_2026-08-12/korean_page_full.bin"
GLYPH_BYTES = 64
AUTHORED_GLYPHS = 928
AUTHORED_SIZE = AUTHORED_GLYPHS * GLYPH_BYTES
PHYSICAL_PAGE_SIZE = 1020 * GLYPH_BYTES


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts if count)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    page = args.page.read_bytes()
    if len(page) != PHYSICAL_PAGE_SIZE:
        raise ValueError(f"expected physical page 0x{PHYSICAL_PAGE_SIZE:X}, got 0x{len(page):X}")
    authored = page[:AUTHORED_SIZE]
    spare = page[AUTHORED_SIZE:]
    middle_start = (AUTHORED_SIZE // 2) & ~0x3F
    middle = authored[middle_start:middle_start + 4096]
    checks = {
        "start_4k": {"offset": 0, "size": 4096, "sha256": digest(authored[:4096])},
        "middle_4k": {"offset": middle_start, "size": len(middle), "sha256": digest(middle),
                       "entropy_bits_per_byte": entropy(middle)},
        "end_4k": {"offset": AUTHORED_SIZE - 4096, "size": 4096,
                   "sha256": digest(authored[-4096:])},
        "authored_end": {"offset": AUTHORED_SIZE, "size": 0},
        "physical_page_end": {"offset": len(page), "size": 0},
        "spare_tail": {"offset": AUTHORED_SIZE, "size": len(spare),
                       "sha256": digest(spare), "all_zero": not any(spare)},
    }
    settings = {
        "status": "CONFIRMED_BY_USER",
        "selection": "permutation-001",
        "decoder": {"bit_order": "MSB-first", "layout": "linear-row-major", "vertical_flip": False},
        "glyph_dimensions": [16, 16],
        "bits_per_pixel": 2,
        "bytes_per_glyph": GLYPH_BYTES,
        "source": str(args.page.resolve()),
        "source_sha256": digest(page),
        "authored_glyph_count": AUTHORED_GLYPHS,
        "authored_size": AUTHORED_SIZE,
        "physical_page_glyph_capacity": 1020,
        "physical_page_size": len(page),
        "note": "The authored 928-glyph region is 0xE800 bytes; the physical renderer page is 0xFF00 bytes and includes 92 spare slots.",
        "validation": checks,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "glyph-decoder-settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "Glyph layout validation",
        "selection=permutation-001",
        "decoder=MSB-first / linear-row-major / vertical_flip=false",
        f"source_sha256={digest(page)}",
        f"authored_region={AUTHORED_GLYPHS} glyphs, {AUTHORED_SIZE} bytes (0x{AUTHORED_SIZE:X})",
        f"physical_page=1020 glyphs, {len(page)} bytes (0x{len(page):X})",
        f"spare_region=92 glyphs, {len(spare)} bytes (0x{len(spare):X}), all_zero={not any(spare)}",
        f"middle_4k_offset=0x{middle_start:X}",
        f"middle_4k_entropy={entropy(middle):.6f} bits/byte",
        "boundary_negative_controls=pending until V1 embeds the page in scenerio.gcx",
    ]
    (args.out / "glyph-layout-validation.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("decoder=permutation-001 authored=0xE800 physical=0xFF00 boundary_controls=pending_V1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
