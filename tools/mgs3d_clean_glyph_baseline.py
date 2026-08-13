#!/usr/bin/env python3
"""Prepare the read-only clean baseline and evaluate the 169-stage K gate.

K is relative to the parser-derived page-2 pointer, not to the GCX file start:

    target_file_offset = page2_file_offset + K
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "originals/3ds_pristine"
DEFAULT_OUT = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
K = 0x56000
PAGE_SIZE = 928 * 64


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page2_offset(data: bytes) -> int:
    """Mirror the verified parser formula used by the game at 0x00108320."""
    cursor = 4
    while True:
        if cursor + 4 > len(data):
            raise ValueError("offset table terminator not found")
        if struct.unpack_from("<I", data, cursor)[0] == 0xFFFFFFFF:
            break
        cursor += 4
    section_base = cursor + 4
    if section_base + 0x10 > len(data):
        raise ValueError("section delta lies outside file")
    return section_base + struct.unpack_from("<I", data, section_base + 0xC)[0] + 4


def inventory(root: Path) -> dict[str, tuple[int, str]]:
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        result[rel] = (path.stat().st_size, sha256(path))
    return result


def write_clean_tree(source: Path, clean: Path, out: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    if clean.exists():
        shutil.rmtree(clean)
    shutil.copytree(source, clean, copy_function=shutil.copy2)
    src = inventory(source)
    dst = inventory(clean)
    added = sorted(set(dst) - set(src))
    deleted = sorted(set(src) - set(dst))
    changed = sorted(path for path in set(src) & set(dst) if src[path] != dst[path])
    lines = [
        "MGS3D clean tree diff",
        f"source={source}",
        f"clean={clean}",
        f"source_file_count={len(src)}",
        f"clean_file_count={len(dst)}",
        f"added={len(added)}",
        f"deleted={len(deleted)}",
        f"changed={len(changed)}",
        "",
        "[ADDED]", *added, "", "[DELETED]", *deleted, "", "[CHANGED]", *changed,
    ]
    (out / "clean-tree-diff.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if added or deleted or changed:
        raise RuntimeError("clean copy does not match source; see clean-tree-diff.txt")


def write_offset_manifest(clean: Path, out: Path) -> None:
    files = sorted((clean / "romfs/stage").glob("*/scenerio.gcx"))
    rows = []
    errors = []
    for path in files:
        data = path.read_bytes()
        try:
            page2 = page2_offset(data)
            target = page2 + K
            padding = max(0, target - len(data))
            actual_offset = len(data) + padding
            actual_k = actual_offset - page2
            gate = "PASS" if len(data) <= target and actual_k == K else "FAIL"
            note = "" if gate == "PASS" else "original_size exceeds page2+K"
        except (ValueError, struct.error) as exc:
            page2 = target = padding = actual_offset = actual_k = ""
            gate, note = "FAIL", f"parser error: {exc}"
            errors.append(f"{path.parent.name}: {exc}")
        output_size = actual_offset + PAGE_SIZE if isinstance(actual_offset, int) else ""
        rows.append({
            "stage": path.parent.name,
            "source_path": path.relative_to(clean).as_posix(),
            "original_size": len(data),
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "page2_file_offset": page2,
            "target_K": K,
            "target_file_offset": target,
            "padding_needed": padding,
            "actual_korean_file_offset": actual_offset,
            "actual_K": actual_k,
            "page_size": PAGE_SIZE,
            "output_size": output_size,
            "gate_result": gate,
            "note": note,
        })
    fields = list(rows[0]) if rows else []
    with (out / "offset-manifest.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["actual_K"] for row in rows)
    failed = [row for row in rows if row["gate_result"] != "PASS"]
    numeric_offsets = [row["actual_korean_file_offset"] for row in rows if isinstance(row["actual_korean_file_offset"], int)]
    analysis = [
        "MGS3D 169-stage K gate analysis",
        f"stage_count={len(rows)}",
        f"target_K=0x{K:X}",
        f"page_size={PAGE_SIZE} (0x{PAGE_SIZE:X})",
        f"gate={'PASS' if len(rows) == 169 and not failed else 'FAIL'}",
        f"pass_count={len(rows) - len(failed)}",
        f"fail_count={len(failed)}",
        f"min_korean_file_offset=0x{min(numeric_offsets):X}" if numeric_offsets else "min_korean_file_offset=N/A",
        f"max_korean_file_offset=0x{max(numeric_offsets):X}" if numeric_offsets else "max_korean_file_offset=N/A",
        "",
        "actual_K_counts:",
        *[f"  {('0x%X' % key) if isinstance(key, int) else key}: {value}" for key, value in sorted(counts.items(), key=lambda item: str(item[0]))],
        "",
        "failed_stages:",
        *[f"  {row['stage']}: {row['note']}" for row in failed],
        *(["", "parser_errors:", *[f"  {error}" for error in errors]] if errors else []),
    ]
    (out / "offset-analysis.txt").write_text("\n".join(analysis) + "\n", encoding="utf-8")
    print(json.dumps({"stage_count": len(rows), "pass": len(rows) - len(failed), "fail": len(failed),
                      "gate": "PASS" if len(rows) == 169 and not failed else "FAIL"}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-copy", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    clean = args.out / "clean-tree"
    if not args.skip_copy:
        write_clean_tree(args.source.resolve(), clean, args.out)
    elif not clean.exists():
        raise FileNotFoundError(clean)
    write_offset_manifest(clean, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
