#!/usr/bin/env python3
"""Create an immutable-by-convention translation checkpoint with SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"checkpoint already exists: {args.output}")
    args.output.mkdir(parents=True)
    files = []
    for index, source in enumerate(args.inputs):
        target = args.output / f"{index:02d}_{source.name}"
        shutil.copy2(source, target)
        files.append({"source": str(source.resolve()), "checkpoint": target.name,
                      "size": target.stat().st_size, "sha256": digest(target)})
    manifest = {"format": "mgs3d-translation-checkpoint-v1",
                "policy": "source translations; never edit these copies in place",
                "files": files}
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"checkpointed {len(files)} files -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
