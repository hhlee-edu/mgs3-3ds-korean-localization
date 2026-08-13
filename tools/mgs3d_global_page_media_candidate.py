#!/usr/bin/env python3
"""Stage the verified global-page media candidate after clean V1/V2."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments/2026-08-13-clean-glyph-baseline"
CLEAN = EXP / "clean-tree"
DEST = Path(r"C:\Users\hhlee\Desktop\metagear3d\romforge\output\unpacked\partition0")
INPUT = ROOT / "translation/40_build_input/global_page_v2"
FILES = {
    INPUT / "movie-global-max-safe.dat": Path("romfs/movie.dat"),
    INPUT / "demo-global-max-safe.dat": Path("romfs/demo.dat"),
    ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/stage/r_sna01/resident.hpk":
        Path("romfs/stage/r_sna01/resident.hpk"),
    ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/stage/r_sna02/resident.hpk":
        Path("romfs/stage/r_sna02/resident.hpk"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_map(root: Path) -> dict[str, tuple[int, str]]:
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        result[path.relative_to(root).as_posix()] = (path.stat().st_size, sha(path))
    return result


def main() -> int:
    clean = file_map(CLEAN)
    before = file_map(DEST)
    stages = {f"romfs/stage/{path.parent.name}/scenerio.gcx"
              for path in (CLEAN / "romfs/stage").glob("*/scenerio.gcx")}
    expected_v2 = stages | {"exefs/code.bin", "exheader.bin"}
    current_diff = {path for path in clean if clean[path] != before.get(path)}
    if current_diff != expected_v2:
        raise RuntimeError("destination is not a clean V2 staging state")

    copied = []
    for source, relative in FILES.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        target = DEST / relative
        shutil.copy2(source, target)
        copied.append({"path": relative.as_posix(), "source": source.relative_to(ROOT).as_posix(),
                       "size": source.stat().st_size, "sha256": sha(source)})

    after = file_map(DEST)
    final_diff = {path for path in clean if clean[path] != after.get(path)}
    expected_final = expected_v2 | {item["path"] for item in copied}
    unexpected = sorted(final_diff ^ expected_final)
    status = "PASS" if not unexpected else "INCONCLUSIVE"
    manifest = {
        "format": "mgs3d-global-page-media-candidate-v1",
        "status": status,
        "scope": "929 global page + trampoline + 191 static HPK + max-safe movie/demo; codec unchanged",
        "global_page_sha256": sha(ROOT / "glyph/pages/global_korean_page_v2/korean_page_full.bin"),
        "files_staged": copied,
        "stage_pages": 169,
        "K": "0x56000",
        "codec_changed": after["romfs/codec.dat"] != clean["romfs/codec.dat"],
        "changed_file_count": len(final_diff),
        "unexpected_diff": unexpected,
        "warning": "Test candidate only; movie/demo are maximum fixed-layout subsets, not full natural-master coverage.",
    }
    (EXP / "media-candidate-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
