#!/usr/bin/env python3
"""Create or verify a SHA-256 inventory for an unpacked game directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


FORMAT = "unpacked-integrity-manifest-v1"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def inventory(root: Path) -> dict[str, dict[str, object]]:
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    files: dict[str, dict[str, object]] = {}
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        relative = path.relative_to(root).as_posix()
        files[relative] = {"size": path.stat().st_size, "sha256": digest(path)}
    return files


def command_snapshot(args: argparse.Namespace) -> None:
    files = inventory(args.root)
    document = {
        "format": FORMAT,
        "root_label": args.root.name,
        "note": args.note,
        "file_count": len(files),
        "total_size": sum(int(item["size"]) for item in files.values()),
        "files": files,
    }
    args.manifest.write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )
    print(f"recorded {len(files)} files in {args.manifest}")


def command_verify(args: argparse.Namespace) -> None:
    document = json.loads(args.manifest.read_text(encoding="utf-8"))
    if document.get("format") != FORMAT:
        raise ValueError("unsupported integrity manifest")
    expected = document["files"]
    current = inventory(args.root)
    added = sorted(set(current) - set(expected))
    missing = sorted(set(expected) - set(current))
    changed = sorted(
        name for name in set(expected) & set(current) if expected[name] != current[name]
    )
    for label, names in (("ADDED", added), ("MISSING", missing), ("CHANGED", changed)):
        for name in names:
            print(f"{label}: {name}")
    if added or missing or changed:
        print(
            f"FAILED: {len(added)} added, {len(missing)} missing, "
            f"{len(changed)} changed",
            file=sys.stderr,
        )
        raise SystemExit(2)
    print(f"OK: {len(current)} files match {args.manifest}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot", help="write a new baseline manifest")
    snapshot.add_argument("root", type=Path)
    snapshot.add_argument("manifest", type=Path)
    snapshot.add_argument("--note", default="")
    snapshot.set_defaults(function=command_snapshot)
    verify = commands.add_parser("verify", help="compare a directory to a manifest")
    verify.add_argument("root", type=Path)
    verify.add_argument("manifest", type=Path)
    verify.set_defaults(function=command_verify)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
