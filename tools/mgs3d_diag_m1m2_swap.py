#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Separate the two variables inside a production scenerio.gcx: translated text
and the EOF-appended Korean glyph page.

Every production stage file is clean's GCX record with the strings replaced
in place (record size, resource count, resource table and every table_word
unchanged) plus a large zero-padded region appended past the original EOF that
carries the Korean glyph page. Those two changes have never been tested apart,
so the 2026-08-20 stage bisection could not say which one causes the UI
regressions.

    M1  translation only : production's original region, append stripped.
                           Size is exactly clean's. Korean will render as
                           garbage - that is expected and not what is judged.
    M2  append only      : clean's original region byte for byte, plus
                           production's appended region at the same offset.
                           Zero translated bytes.

M1 and M2 are exact complements: between them they contain every production
byte and share none.

    build   write both variants next to this build directory
    P1  padding normalised: M1's Korean text unchanged, but every trailing NUL
                           our build added is turned back into 0x20 so the NUL
                           count matches clean exactly. M1 vs P1 isolates the
                           padding from the translation.

    apply m1|m2|p1|clean|production   stage that variant for v001a
    status  report which variant is staged
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGE = "v001a"
REL = f"romfs/stage/{STAGE}/scenerio.gcx"
CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree" / REL
PROD = ROOT / "builds/diag-2026-08-20-clean-tree-swap/staging-backup" / REL
STAGING = pathlib.Path(r"C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0") / REL
OUT = ROOT / "builds/diag-2026-08-20-m1m2-v001a"
M1 = OUT / f"{STAGE}-M1-translation-only.gcx"
M2 = OUT / f"{STAGE}-M2-append-only.gcx"
P1 = ROOT / "builds/diag-2026-08-20-p1-v001a" / f"{STAGE}-P1-nul-padding-normalised.gcx"


def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> None:
    c, p = CLEAN.read_bytes(), PROD.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    M1.write_bytes(p[:len(c)])
    M2.write_bytes(c + p[len(c):])
    for name, path in (("clean", CLEAN), ("production", PROD), ("M1", M1), ("M2", M2)):
        print(f"{name:<12}{path.stat().st_size:>10,}  {sha(path)}")
    a, b = M1.read_bytes(), M2.read_bytes()
    print(f"\nM1 size == clean            : {len(a) == len(c)}")
    print(f"M1 body == production body  : {a == p[:len(c)]}")
    print(f"M2 size == production       : {len(b) == len(p)}")
    print(f"M2 body == clean body       : {b[:len(c)] == c}")
    print(f"M2 append == production's   : {b[len(c):] == p[len(c):]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "apply", "status"))
    ap.add_argument("variant", nargs="?",
                    choices=("m1", "m2", "p1", "clean", "production"))
    args = ap.parse_args()

    if args.action == "build":
        build()
        return 0

    table = {"m1": M1, "m2": M2, "p1": P1, "clean": CLEAN, "production": PROD}
    if args.action == "status":
        cur = sha(STAGING)
        which = next((k for k, v in table.items() if v.exists() and sha(v) == cur), "unrecognised")
        print(f"{REL}  {STAGING.stat().st_size:>10,}  {cur[:16]}  {which}")
        return 0

    if not args.variant:
        raise SystemExit("apply needs m1|m2|p1|clean|production")
    src = table[args.variant]
    if not src.exists():
        raise SystemExit(f"missing {src} - run 'build' first")
    want = sha(src)
    if sha(STAGING) == want:
        print(f"already {args.variant}")
        return 0
    shutil.copy2(src, STAGING)
    got = sha(STAGING)
    print(f"{args.variant}: -> {got[:16]}  {'OK' if got == want else 'HASH MISMATCH'}")
    return 0 if got == want else 1


if __name__ == "__main__":
    sys.exit(main())
