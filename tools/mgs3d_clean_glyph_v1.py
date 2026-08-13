#!/usr/bin/env python3
"""Stage V1: 169 Korean pages, data only, no code or trampoline patch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from mgs3d_clean_glyph_baseline import page2_offset

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
CLEAN = EXP / "clean-tree"
DEST = Path(r"C:\Users\hhlee\Desktop\metagear3d\romforge\output\unpacked\partition0")
PAGE = ROOT / "experiments/global_korean_page_build_2026-08-12/korean_page_full.bin"
K = 0x56000
PHYSICAL_PAGE_SIZE = 0xFF00


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_map(root: Path) -> dict[str, tuple[int, str]]:
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        result[path.relative_to(root).as_posix()] = (len(data), digest(data))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", type=Path, default=CLEAN)
    parser.add_argument("--dest", type=Path, default=DEST)
    parser.add_argument("--page", type=Path, default=PAGE)
    args = parser.parse_args()
    page = args.page.read_bytes()
    if len(page) != PHYSICAL_PAGE_SIZE:
        raise ValueError(f"physical Korean page must be 0xFF00, got 0x{len(page):X}")
    glyph_chunks = [page[offset:offset + 64] for offset in range(0, len(page), 64)]
    authored_count = sum(any(chunk) for chunk in glyph_chunks)
    if any(any(glyph_chunks[index]) for index in range(authored_count, len(glyph_chunks))):
        raise ValueError("Korean page has a nonzero glyph after the authored prefix")
    authored_size = authored_count * 64

    # Normalize every whitelisted partition0 file to V0c before applying V1.
    clean_map = file_map(args.clean)
    dest_map = file_map(args.dest)
    if set(clean_map) != set(dest_map):
        raise RuntimeError("destination whitelist differs from V0c clean tree")
    for rel in clean_map:
        if clean_map[rel] != dest_map[rel]:
            shutil.copy2(args.clean / Path(rel), args.dest / Path(rel))

    rows = []
    for source in sorted((args.clean / "romfs/stage").glob("*/scenerio.gcx")):
        data = source.read_bytes()
        p2 = page2_offset(data)
        target = p2 + K
        if len(data) > target:
            raise RuntimeError(f"{source.parent.name}: original size exceeds page2+K")
        padding = target - len(data)
        patched = data + bytes(padding) + page
        destination = args.dest / source.relative_to(args.clean)
        destination.write_bytes(patched)
        before = patched[target - 64:target]
        after = patched[target + len(page):target + len(page) + 64]
        rows.append({
            "stage": source.parent.name,
            "relative_path": source.relative_to(args.clean).as_posix(),
            "original_size": len(data),
            "original_sha256": digest(data),
            "page2_file_offset": p2,
            "K": K,
            "korean_file_offset": target,
            "padding_needed": padding,
            "authored_glyph_count": authored_count,
            "authored_size": authored_size,
            "physical_page_size": len(page),
            "output_size": len(patched),
            "output_sha256": digest(patched),
            "page_sha256": digest(patched[target:target + len(page)]),
            "pre_boundary_sha256": digest(before),
            "pre_boundary_equals_page_prefix": before == page[:64],
            "post_boundary_size": len(after),
            "post_boundary_equals_page_prefix": after == page[:len(after)],
        })

    after_map = file_map(args.dest)
    changed = sorted(rel for rel in clean_map if after_map.get(rel) != clean_map[rel])
    expected = sorted(row["relative_path"] for row in rows)
    unexpected = sorted(set(changed) ^ set(expected))
    status = "PASS" if len(rows) == 169 and not unexpected else "INCONCLUSIVE"
    fields = list(rows[0])
    with (EXP / "V1-offset-manifest.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "format": "mgs3d-clean-glyph-v1-data-only",
        "status": status,
        "source": str(args.clean.resolve()),
        "destination": str(args.dest.resolve()),
        "K": K,
        "address_formula": "korean_file_offset = parser_page2_file_offset + K",
        "page_source": str(args.page.resolve()),
        "page_sha256": digest(page),
        "authored_glyph_count": authored_count,
        "authored_size": authored_size,
        "physical_page_size": len(page),
        "stages_patched": len(rows),
        "changed_files": changed,
        "unexpected_diff": unexpected,
        "code_bin_changed": after_map.get("exefs/code.bin") != clean_map.get("exefs/code.bin"),
        "exheader_changed": after_map.get("exheader.bin") != clean_map.get("exheader.bin"),
        "movie_dat_changed": after_map.get("romfs/movie.dat") != clean_map.get("romfs/movie.dat"),
    }
    (EXP / "V1-build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    diff_lines = [
        "V0c-to-V1 changed-file diff",
        f"status={status}",
        f"changed_count={len(changed)}",
        f"expected_count={len(expected)}",
        f"unexpected_count={len(unexpected)}",
        "", "[CHANGED]", *changed, "", "[UNEXPECTED]", *unexpected,
    ]
    (EXP / "V0c-to-V1-diff.txt").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "stages": len(rows), "changed": len(changed),
                      "unexpected": len(unexpected), "code_changed": manifest["code_bin_changed"]}, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
