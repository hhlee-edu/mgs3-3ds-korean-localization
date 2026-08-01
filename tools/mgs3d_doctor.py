#!/usr/bin/env python3
"""Check whether the MGS3D localization toolkit is ready to run."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


MINIMUM_PYTHON = (3, 10)
DEPENDENCIES = {
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", type=Path, default=Path("partition0"))
    parser.add_argument("--baseline", type=Path, default=Path("docs/unpacked-baseline.json"))
    parser.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\malgun.ttf"))
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="check Python and packages only; do not require local game/font inputs",
    )
    args = parser.parse_args()

    failures: list[str] = []
    version = sys.version_info[:3]
    if version < MINIMUM_PYTHON:
        failures.append(
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}+ required, got "
            f"{version[0]}.{version[1]}.{version[2]}"
        )
    else:
        print(f"OK Python {version[0]}.{version[1]}.{version[2]}")

    for module, package in DEPENDENCIES.items():
        if importlib.util.find_spec(module) is None:
            failures.append(f"missing package {package} (module {module})")
        else:
            print(f"OK package {package}")

    if not args.source_only:
        required = [
            args.partition / "header.bin",
            args.partition / "romfs/codec.dat",
            args.partition / "romfs/movie.dat",
            args.partition / "romfs/demo.dat",
            args.baseline,
            args.font,
        ]
        for path in required:
            if not path.is_file():
                failures.append(f"missing required file: {path}")
            else:
                print(f"OK file {path}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        print(
            f"TOOLKIT NOT READY: {len(failures)} check(s) failed. "
            "Install dependencies with: python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    print("TOOLKIT READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
