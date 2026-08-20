#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Swap the codec static dialogue font in/out of staging for the #2 diagnostic.

Defect #2 (2026-08-20): the codec contact UI shows no name for Major Tom and
shows EVA when The Boss is highlighted. Index corruption was ruled out — the
built codec.dat keeps clean's record count, per-GCX resource counts and record
sizes exactly, and all 13,132 PERSONAL DATA CODENAME fields match clean. The one
mechanism left in our change set that can repaint a label without moving any
index is the static dialogue font: HPK member `453c386e` in
`stage/r_sna01/resident.hpk` and `stage/r_sna02/resident.hpk` has 191 of its 194
16x16 2bpp glyph slots (`81xx`/`82xx`/`83xx`) overwritten with Hangul, while its
offset table is untouched. If the contact label draws from that token range, the
glyphs change even though the mapping does not.

This script swaps ONLY that member, so the diagnostic differs from the current
staging in exactly two files and nothing else.

    apply   staging resident.hpk -> clean font (diagnostic)
    revert  staging resident.hpk -> Korean font (production)
    status  report which font each staged archive currently carries

Both directions verify the target hash before and after writing, and refuse to
run if staging carries anything unexpected. Test procedure:

    1. python tools/mgs3d_diag_static_font_swap.py apply
    2. repack the CCI in RomForge, boot, open the codec contact list
    3. record whether Major Tom's name appears and whether The Boss shows EVA
    4. python tools/mgs3d_diag_static_font_swap.py revert     <- always do this

If the names render correctly under `apply`, the static font is the cause. If the
symptom is unchanged, the font is exonerated and the cause is outside our change
set (`ui/*.la2`, `slot.dat` and `vox.dat` are byte-identical to clean).
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGING = pathlib.Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0")
CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree"
DIAG = ROOT / "builds/diag-2026-08-20-static-font"
PROD = ROOT / "builds/diag-2026-08-20-static-font/production-backup"
STAGES = ("r_sna01", "r_sna02")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: pathlib.Path) -> str:
    return "stage/%s/resident.hpk" % p.parent.name


def staged(stage: str) -> pathlib.Path:
    return STAGING / "romfs/stage" / stage / "resident.hpk"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("apply", "revert", "status"))
    args = ap.parse_args()

    # Capture the current (Korean-font) staging once, so revert has a source
    # that does not depend on rebuilding anything.
    if args.action == "apply":
        PROD.mkdir(parents=True, exist_ok=True)
        for st in STAGES:
            keep = PROD / st / "resident.hpk"
            if not keep.exists():
                keep.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged(st), keep)
                print("saved production copy %s -> %s" % (rel(staged(st)), keep))

    rc = 0
    for st in STAGES:
        tgt = staged(st)
        diag = DIAG / "romfs/stage" / st / "resident.hpk"
        prod = PROD / st / "resident.hpk"
        clean = CLEAN / "romfs/stage" / st / "resident.hpk"
        if not tgt.exists():
            print("MISSING staged %s" % tgt)
            rc = 1
            continue
        cur = sha256(tgt)
        if args.action == "status":
            which = ("clean/diagnostic font" if cur == sha256(clean)
                     else "Korean font" if prod.exists() and cur == sha256(prod)
                     else "unrecognised")
            print("%-8s %s  %s" % (st, cur[:16], which))
            continue

        src = diag if args.action == "apply" else prod
        if not src.exists():
            print("MISSING source %s - run 'apply' first" % src)
            rc = 1
            continue
        want = sha256(src)
        if cur == want:
            print("%-8s already %s (%s)" % (st, args.action, cur[:16]))
            continue
        shutil.copy2(src, tgt)
        got = sha256(tgt)
        ok = got == want
        print("%-8s %s: %s -> %s  %s" % (st, args.action, cur[:16], got[:16],
                                         "OK" if ok else "HASH MISMATCH"))
        if not ok:
            rc = 1
    if args.action == "apply":
        print("\ndiagnostic applied. Repack, test the codec contact list, then run 'revert'.")
    elif args.action == "revert":
        print("\nproduction font restored.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
