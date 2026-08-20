#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Swap the RomForge staging tree to the untouched clean v1.0 build, and back.

For defect #2 (Major Tom's name missing, The Boss showing EVA) the cheapest
decisive test is whether the *unpatched* game already behaves that way. The
contact "names" in the bottom radio UI are pre-rendered images
(`rad_icn_zero/medic/sigint/theboss/eva/save.bclim`) inside
`romfs/ui/menu/sv/radio.la2`, and that file -- along with `ui/test/test_radio.la2`
and `slot.dat` -- is already byte-identical to clean, so the only way our work
could cause it is through `exefs/code.bin`. Booting clean settles it in one test:

    clean also shows EVA  -> stock behaviour, drop it from the Korean blockers
    clean shows The Boss  -> our regression, trace code.bin / UI index / slot.dat

`experiments/2026-08-13-clean-glyph-baseline/clean-tree` is a complete 924-file
partition0 tree, the same file set as staging, so the swap is exact.

    plan    list the files that differ, write the restore manifest
    apply   staging -> clean v1.0 (writes a backup of every file it replaces)
    revert  staging -> the backed-up build
    status  report how far staging is from clean

Only files that actually differ are touched, and every write is hash-verified.
Run `plan` first; `apply` refuses to run without a manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree"
STAGING = pathlib.Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0")
BUILD = ROOT / "builds/diag-2026-08-20-clean-tree-swap"
BACKUP = BUILD / "staging-backup"
MANIFEST = BUILD / "manifest.json"


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def survey() -> list[dict]:
    rows = []
    for c in sorted(CLEAN.rglob("*")):
        if not c.is_file():
            continue
        rel = c.relative_to(CLEAN).as_posix()
        s = STAGING / rel
        if not s.exists():
            rows.append({"path": rel, "state": "missing-in-staging"})
            continue
        if c.stat().st_size == s.stat().st_size and sha(c) == sha(s):
            continue
        rows.append({"path": rel, "state": "differs",
                     "clean_sha256": sha(c), "staged_sha256": sha(s),
                     "clean_size": c.stat().st_size, "staged_size": s.stat().st_size})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("plan", "apply", "revert", "status"))
    args = ap.parse_args()

    if args.action in ("plan", "status"):
        rows = survey()
        diff = [r for r in rows if r["state"] == "differs"]
        print(f"files differing from clean v1.0: {len(diff)}")
        for r in diff:
            print(f"   {r['path']:<46} {r['staged_sha256'][:12]} -> {r['clean_sha256'][:12]}")
        missing = [r for r in rows if r["state"] != "differs"]
        if missing:
            print(f"MISSING in staging: {len(missing)}")
        if args.action == "plan":
            BUILD.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(json.dumps({"format": "mgs3d-clean-tree-swap-v1",
                                            "files": diff}, indent=1), encoding="utf-8")
            print(f"\nmanifest written: {MANIFEST}")
            print(f"backup target   : {BACKUP}")
        return 0

    if not MANIFEST.exists():
        raise SystemExit("no manifest - run 'plan' first")
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]

    rc = 0
    for r in files:
        rel = r["path"]
        s = STAGING / rel
        if args.action == "apply":
            keep = BACKUP / rel
            if not keep.exists():
                keep.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, keep)
            src, want = CLEAN / rel, r["clean_sha256"]
        else:
            src, want = BACKUP / rel, r["staged_sha256"]
            if not src.exists():
                print(f"MISSING backup {rel} - run 'apply' first")
                rc = 1
                continue
        if sha(s) == want:
            print(f"{rel:<46} already {args.action}")
            continue
        shutil.copy2(src, s)
        got = sha(s)
        ok = got == want
        print(f"{rel:<46} {args.action}: -> {got[:12]}  {'OK' if ok else 'HASH MISMATCH'}")
        if not ok:
            rc = 1
    print(f"\n{'clean v1.0 staged' if args.action == 'apply' else 'previous build restored'}."
          f" Repack, test, then run the other direction.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
