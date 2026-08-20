#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify a repacked CCI actually carries the static-font diagnostic.

`tools/mgs3d_diag_static_font_swap.py apply` only changes the staging tree. A
staging-only check is not sufficient (wiki/Build-System.md): the CCI has to be
confirmed to contain what staging contained. This script does that without
unpacking 3.3 GB — it locates each `stage/<name>/resident.hpk` payload inside
the image by a unique byte anchor and hashes it in place.

    python tools/mgs3d_diag_cci_verify.py "<path to .cci>"

Reports the image SHA-256 plus, per stage, whether the embedded archive is the
clean/diagnostic font or the Korean/production font. Exit 0 only when both
stages carry the diagnostic font.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree"
PROD = ROOT / "builds/diag-2026-08-20-static-font/production-backup"
STAGES = ("r_sna01", "r_sna02")
ANCHOR = 96  # bytes of tail used to find the payload inside the image


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def find_all(image: pathlib.Path, needle: bytes) -> list[int]:
    """Byte-offset scan of a multi-GB file with an overlapping window."""
    hits: list[int] = []
    keep = len(needle) - 1
    tail = b""
    base = 0
    with image.open("rb") as fh:
        while True:
            chunk = fh.read(1 << 24)
            if not chunk:
                return hits
            buf = tail + chunk
            start = 0
            while True:
                i = buf.find(needle, start)
                if i < 0:
                    break
                hits.append(base - len(tail) + i)
                start = i + 1
            base += len(chunk)
            tail = buf[-keep:] if keep else b""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cci", type=pathlib.Path)
    args = ap.parse_args()
    if not args.cci.exists():
        print("missing image: %s" % args.cci)
        return 2

    print("image  %s" % args.cci)
    print("size   %d" % args.cci.stat().st_size)
    print("sha256 %s" % sha256_file(args.cci))
    print()

    rc = 0
    for stage in STAGES:
        clean = (CLEAN / "romfs/stage" / stage / "resident.hpk").read_bytes()
        prod_path = PROD / stage / "resident.hpk"
        prod = prod_path.read_bytes() if prod_path.exists() else None
        want = sha256_bytes(clean)
        # Anchor on the clean tail; production differs only inside the font
        # member, so the tail is shared and finds either build.
        anchor = clean[-ANCHOR:]
        offsets = find_all(args.cci, anchor)
        found = []
        with args.cci.open("rb") as fh:
            for end in offsets:
                start = end + ANCHOR - len(clean)
                if start < 0:
                    continue
                fh.seek(start)
                blob = fh.read(len(clean))
                if len(blob) != len(clean):
                    continue
                digest = sha256_bytes(blob)
                if digest in (want, sha256_bytes(prod) if prod else None):
                    found.append((start, digest))
        if not found:
            print("%-8s NOT FOUND in image" % stage)
            rc = 1
            continue
        for start, digest in found:
            which = ("clean/diagnostic font" if digest == want
                     else "Korean/production font")
            flag = "OK" if digest == want else "*** PRODUCTION, NOT DIAGNOSTIC ***"
            print("%-8s @0x%09X  %s  %s  %s" % (stage, start, digest[:16], which, flag))
            if digest != want:
                rc = 1
    print()
    print("VERDICT:", "diagnostic CCI confirmed" if rc == 0 else "NOT the diagnostic build")
    return rc


if __name__ == "__main__":
    sys.exit(main())
