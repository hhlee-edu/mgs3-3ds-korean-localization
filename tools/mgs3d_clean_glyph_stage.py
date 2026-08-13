#!/usr/bin/env python3
"""Stage V0c/V1 clean glyph builds into an isolated RomForge unpacked tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
DEFAULT_SOURCE = EXPERIMENT / "clean-tree"
DEFAULT_DEST = Path(r"C:\Users\hhlee\Desktop\metagear3d\romforge\output\unpacked\partition0")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files(root: Path) -> dict[str, tuple[int, str]]:
    return {p.relative_to(root).as_posix(): (p.stat().st_size, sha(p))
            for p in sorted(x for x in root.rglob("*") if x.is_file())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--label", default="V0c")
    args = parser.parse_args()
    before = files(args.dest)
    source = files(args.source)
    if set(before) != set(source):
        raise RuntimeError("destination whitelist differs from clean source; refusing to stage")
    for rel in sorted(source):
        src = args.source / Path(rel)
        dst = args.dest / Path(rel)
        if before[rel] != source[rel]:
            shutil.copy2(src, dst)
    after = files(args.dest)
    if after != source:
        raise RuntimeError("post-stage destination differs from clean source")
    changed_before = sorted(rel for rel in source if before[rel] != source[rel])
    record = {
        "label": args.label,
        "source": str(args.source.resolve()),
        "destination": str(args.dest.resolve()),
        "source_file_count": len(source),
        "destination_file_count": len(after),
        "files_replaced": changed_before,
        "post_stage_added": sorted(set(after) - set(source)),
        "post_stage_deleted": sorted(set(source) - set(after)),
        "post_stage_changed": sorted(rel for rel in source if after.get(rel) != source[rel]),
        "status": "PASS",
    }
    output = EXPERIMENT / f"{args.label}-stage-manifest.json"
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": args.label, "files": len(source),
                      "files_replaced": len(changed_before), "post_stage": "PASS"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
