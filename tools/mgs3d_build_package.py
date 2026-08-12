#!/usr/bin/env python3
"""Assemble a hashed Romforge-ready DAT/resident-HPK candidate package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--movie", required=True, type=Path)
    p.add_argument("--demo", required=True, type=Path)
    p.add_argument("--codec", required=True, type=Path)
    p.add_argument("--sna01", required=True, type=Path)
    p.add_argument("--sna02", required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise SystemExit(f"package already exists: {args.output}")
    mapping = [
        (args.movie, "romfs/movie.dat"), (args.demo, "romfs/demo.dat"),
        (args.codec, "romfs/codec.dat"),
        (args.sna01, "stage/r_sna01/resident.hpk"),
        (args.sna02, "stage/r_sna02/resident.hpk"),
    ]
    files = []
    for source, relative in mapping:
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append({"install_target": relative, "source": str(source.resolve()),
                      "size": target.stat().st_size, "sha256": digest(target)})
    manifest = {"format": "mgs3d-romforge-build-candidate-v1",
                "status": "static/content verified; runtime smoke pending",
                "requires_atomic_set": True, "files": files}
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"packaged {len(files)} files -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
