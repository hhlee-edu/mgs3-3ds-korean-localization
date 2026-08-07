#!/usr/bin/env python3
"""Compact a naturally-grown demo.dat back to scene-aligned boundaries.

demo.dat is a multiplexed container of independent scenes, each starting
with a type=16/f3=2 tag on a 0x800 boundary and padded with zero bytes up
to the next scene's boundary. Playback only requires every scene's own
start offset to stay byte-identical to the original; content growth
*inside* a scene is safe as long as it never bleeds past that scene's own
trailing padding into the next scene.

Workflow:
  1. Run `mgs3d_movie_tool.py build-korean ... --grow-records` normally to
     naturally grow demo.dat with real translations (that tool already
     handles glyph encoding/allocation correctly).
  2. Run this script on the result: it walks both the original and the
     grown file's scene structure, and for each scene trims exactly as
     many trailing zero-padding bytes as that scene grew, so every scene
     ends up occupying exactly its original length and every scene start
     offset matches the original file exactly.
  3. Any scene whose growth exceeds its own available padding budget is
     reported and fails the build (nothing is silently dropped).
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def walk_blocks(data: bytes) -> list[tuple[int, int, int]]:
    """Return (offset, kind, size) for every block, skipping zero-pad runs."""
    cursor = 0
    blocks: list[tuple[int, int, int]] = []
    while cursor + 8 <= len(data):
        kind, size = struct.unpack_from("<II", data, cursor)
        if kind == 0 and size == 0:
            cursor += 0x10
            continue
        if size == 0 or size % 0x10 or cursor + size > len(data):
            raise ValueError(f"desync at 0x{cursor:x}: kind={kind} size={size}")
        blocks.append((cursor, kind, size))
        cursor += size
    return blocks


def scene_starts(data: bytes, blocks: list[tuple[int, int, int]]) -> list[int]:
    starts = []
    for off, kind, size in blocks:
        if (kind & 0xFFFF) == 16:
            _, f3 = struct.unpack_from("<II", data, off + 8)
            if f3 == 2:
                starts.append(off)
    return starts


def scene_bounds(starts: list[int], file_size: int) -> list[tuple[int, int]]:
    """[(scene_start, scene_end_exclusive), ...] — end is the next scene's start."""
    bounds = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else file_size
        bounds.append((s, end))
    return bounds


def trailing_pad_run(data: bytes, scene_end: int) -> int:
    """Count zero bytes immediately before scene_end, back to the last non-zero byte."""
    cursor = scene_end
    while cursor > 0 and data[cursor - 1] == 0:
        cursor -= 1
    return scene_end - cursor


def command_compact(args: argparse.Namespace) -> None:
    original = args.original.read_bytes()
    grown = args.grown.read_bytes()

    orig_blocks = walk_blocks(original)
    grown_blocks = walk_blocks(grown)
    orig_starts = scene_starts(original, orig_blocks)
    grown_starts = scene_starts(grown, grown_blocks)
    if len(orig_starts) != len(grown_starts):
        raise ValueError(
            f"scene count changed: original {len(orig_starts)} vs grown {len(grown_starts)}"
        )

    orig_bounds = scene_bounds(orig_starts, len(original))
    grown_bounds = scene_bounds(grown_starts, len(grown))

    output = bytearray()
    prev_grown_end = 0
    deficits = []
    for i, ((o_start, o_end), (g_start, g_end)) in enumerate(zip(orig_bounds, grown_bounds)):
        orig_len = o_end - o_start
        grown_len = g_end - g_start
        growth = grown_len - orig_len
        if growth <= 0:
            # A resource re-encoded slightly shorter than original (e.g. a
            # translation shorter than the source English). Pad back out to
            # the original scene length so this scene's own size — and every
            # later scene's start offset — still matches the original exactly.
            scene_content = grown[g_start:g_end] + b"\0" * (-growth)
            output.extend(scene_content)
            continue
        # Copy this scene's grown content, minus `growth` bytes trimmed from
        # its own trailing zero-padding run (immediately before g_end).
        pad_available = trailing_pad_run(grown, g_end)
        if growth > pad_available:
            deficits.append((i, growth, pad_available))
            continue
        scene_content = grown[g_start:g_end - growth]
        output.extend(scene_content)

    if deficits:
        lines = "\n".join(
            f"  scene {i}: needs {growth} bytes, only {pad} available"
            for i, growth, pad in deficits
        )
        raise ValueError(f"{len(deficits)} scene(s) exceed their padding budget:\n{lines}")

    # Prefix before the first scene, and any file tail after the last scene,
    # are copied verbatim from the grown file (untouched by this compaction).
    prefix = grown[:grown_starts[0]]
    tail = grown[grown_bounds[-1][1]:]
    final = bytes(prefix) + bytes(output) + bytes(tail)

    if len(final) != len(original):
        raise ValueError(
            f"compacted size {len(final)} != original size {len(original)} — logic error"
        )

    # Postcondition: every scene start in the final file must exactly match the original.
    final_blocks = walk_blocks(final)
    final_starts = scene_starts(final, final_blocks)
    if final_starts != orig_starts:
        mismatches = [(i, a, b) for i, (a, b) in enumerate(zip(orig_starts, final_starts)) if a != b]
        raise ValueError(f"scene-start postcondition failed: {mismatches[:5]}")

    args.output.write_bytes(final)
    print(f"compacted {args.grown.name} -> {args.output}: "
          f"{len(orig_starts)} scenes, all starts verified identical to original, "
          f"file size {len(final)} (unchanged)")


def command_budget(args: argparse.Namespace) -> None:
    data = args.input.read_bytes()
    blocks = walk_blocks(data)
    starts = scene_starts(data, blocks)
    bounds = scene_bounds(starts, len(data))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with args.output.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("scene_index,scene_start,scene_end,pad_bytes\n")
        for i, (s, e) in enumerate(bounds):
            pad = trailing_pad_run(data, e)
            total += pad
            f.write(f"{i},{s},{e},{pad}\n")
    print(f"{len(bounds)} scenes, total padding budget {total} bytes -> {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    compact = commands.add_parser("compact", help="trim a grown demo.dat back to original scene boundaries")
    compact.add_argument("original", type=Path)
    compact.add_argument("grown", type=Path)
    compact.add_argument("output", type=Path)
    compact.set_defaults(function=command_compact)

    budget = commands.add_parser("budget", help="report per-scene padding budget")
    budget.add_argument("input", type=Path)
    budget.add_argument("output", type=Path)
    budget.set_defaults(function=command_budget)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.function(args)
    except ValueError as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
