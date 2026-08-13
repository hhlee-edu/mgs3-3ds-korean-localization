#!/usr/bin/env python3
"""Stage the last runtime-confirmed 가나다 renderer POC without rebuilding it."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "analysis/global_korean_glyph_poc_2026-08-12/successful_page3_renderer_isolation"
OUT = ROOT / "output/known_good_ganada_poc/partition0"

FILES = {
    "code.poc.bin": "exefs/code.bin",
    "exheader.poc.bin": "exheader.bin",
    "movie.poc.dat": "romfs/movie.dat",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads((SRC / "patch_manifest.json").read_text(encoding="utf-8"))
    expected = {
        "code.poc.bin": manifest["outputs"]["code_bin_sha256"],
        "exheader.poc.bin": manifest["outputs"]["exheader_sha256"],
        "movie.poc.dat": manifest["outputs"]["movie_sha256"],
    }
    for source_name, relative_dest in FILES.items():
        source = SRC / source_name
        actual = sha256(source)
        if actual != expected[source_name]:
            raise SystemExit(f"hash mismatch: {source} ({actual})")
        dest = OUT / relative_dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    shutil.copy2(SRC / "patch_manifest.json", OUT.parent / "patch_manifest.json")
    shutil.copy2(SRC / "test_results.json", OUT.parent / "test_results.json")
    print(f"staged known-good POC: {OUT}")
    print("WARNING: diagnostic only; 8401-8403 are intercepted and this is not the failed asset-loader build.")


if __name__ == "__main__":
    main()
