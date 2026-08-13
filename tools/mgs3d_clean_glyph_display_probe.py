#!/usr/bin/env python3
"""Add one fixed-capacity controlled subtitle to the verified V2 staging."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_movie_tool import parse_records  # noqa: E402

EXP = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
CLEAN_MOVIE = EXP / "clean-tree/romfs/movie.dat"
DEST = Path(r"C:\Users\hhlee\Desktop\metagear3d\romforge\output\unpacked\partition0\romfs\movie.dat")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    source = CLEAN_MOVIE.read_bytes()
    _, records, _ = parse_records(source)
    payload = b"ABC " + b"".join(token.to_bytes(2, "big") for token in (0x8401, 0x8402, 0x8403)) + b" XYZ\0"
    output = bytearray(source)
    patch = None
    for record in records:
        for entry, subtitle in enumerate(record.subtitles):
            if subtitle.entry_type == 1 and len(subtitle.raw) >= len(payload):
                original = bytes(output[subtitle.offset:subtitle.offset + len(subtitle.raw)])
                replacement = payload + bytes(len(subtitle.raw) - len(payload))
                output[subtitle.offset:subtitle.offset + len(subtitle.raw)] = replacement
                patch = {"record": record.index, "entry": entry, "offset": subtitle.offset,
                         "capacity": len(subtitle.raw), "original_hex": original.hex(),
                         "replacement_hex": replacement.hex()}
                break
        if patch:
            break
    if patch is None:
        raise RuntimeError("no fixed-capacity subtitle can hold the display probe")
    if len(output) != len(source):
        raise RuntimeError("movie layout changed")
    before = DEST.read_bytes()
    if sha(before) != sha(source):
        raise RuntimeError("V2 staging movie.dat is not the clean V1/V2 baseline")
    artifact = EXP / "V2-display-probe-movie.dat"
    artifact.write_bytes(output)
    shutil.copy2(artifact, DEST)
    if DEST.read_bytes() != output:
        raise RuntimeError("staged movie probe verification failed")
    manifest = {
        "format": "mgs3d-v2-controlled-display-probe",
        "status": "STAGED_RUNTIME_UNVERIFIED",
        "base": "V2 (169 pages + trampoline)",
        "changed_files": ["romfs/movie.dat"],
        "unexpected_diff": [],
        "source_movie_sha256": sha(source),
        "output_movie_sha256": sha(output),
        "source_size": len(source),
        "output_size": len(output),
        "layout_size_preserved": len(source) == len(output),
        "controlled_text": "ABC <0x8401><0x8402><0x8403> XYZ",
        "expected_visual": "ABC <Korean glyph indices 0,1,2> XYZ",
        "patch": patch,
    }
    (EXP / "V2-display-probe-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EXP / "V2-to-display-probe-diff.txt").write_text(
        "V2-to-display-probe changed-file diff\nstatus=PASS\nchanged_count=1\nromfs/movie.dat\n\n[UNEXPECTED]\n",
        encoding="utf-8")
    print(json.dumps({"status": "PASS", "changed": ["romfs/movie.dat"],
                      "record": patch["record"], "entry": patch["entry"],
                      "offset": patch["offset"], "size_preserved": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
