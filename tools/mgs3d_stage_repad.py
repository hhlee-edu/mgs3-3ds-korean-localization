#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild every production scenerio.gcx with the corrected trailing padding.

`mgs3d_stage_apply.py` used to fill the slack a shorter Korean string leaves in
a fixed resource slot with NUL. Hardware showed that is not inert: v001a built
that way reproduced The Boss showing EVA and Major Tom's missing name, and the
same build with only the surplus NULs replaced rendered both correctly.

This applies the corrected policy -- keep the terminator run the clean resource
had, fill the rest with 0x20 -- to the existing production files rather than
re-running the translation pipeline. Taking production as the source is what
makes "padding-only" provable: the translated payload is copied, never
regenerated, so no other difference can enter.

    build   write the repadded set under builds/diag-2026-08-20-stage-repad
    verify  compare the new set against clean and against old production
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import GcxRecord, align  # noqa: E402

CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/stage"
PROD = ROOT / "builds/diag-2026-08-20-clean-tree-swap/staging-backup/romfs/stage"
OUT = ROOT / "builds/diag-2026-08-20-stage-repad/romfs/stage"
NUL = bytes([0])
PAD = bytes([0x20])


def rec(data: bytes) -> GcxRecord:
    padded = data + NUL * (align(len(data)) - len(data))
    record, _ = GcxRecord.from_codec(padded, 0)
    return record


def trail(b: bytes) -> int:
    return len(b) - len(b.rstrip(NUL))


def repad(clean: bytes, prod: bytes) -> tuple[bytes, int, int]:
    """Return (new file, resources rewritten, NUL bytes converted)."""
    body = prod[:len(clean)]
    rc, rp = rec(clean).resources(), rec(body)
    src = rp.resources()
    repl: dict[int, bytes] = {}
    converted = 0
    for i, r in enumerate(src):
        tp, tc = trail(r.data), trail(rc[i].data)
        if tp <= 1 or tp <= tc:
            continue
        core = r.data.rstrip(NUL)
        keep = max(1, tc)
        if len(core) + keep > len(r.data):
            continue
        fill = len(r.data) - len(core) - keep
        repl[i] = core + NUL * keep + PAD * fill
        converted += tp - keep
    if not repl:
        return prod, 0, 0
    out = rp.replace_resources(repl, preserve_layout=True)
    out = out[:len(clean)] if len(out) >= len(clean) else out + NUL * (len(clean) - len(out))
    return out + prod[len(clean):], len(repl), converted


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "verify"))
    args = ap.parse_args()
    names = sorted(p.parent.name for p in PROD.glob("*/scenerio.gcx"))
    if args.action == "build":
        tot_r = tot_c = 0
        for n in names:
            c = (CLEAN / n / "scenerio.gcx").read_bytes()
            p = (PROD / n / "scenerio.gcx").read_bytes()
            new, nr, nc = repad(c, p)
            if len(new) != len(p):
                raise SystemExit(f"{n}: length {len(new)} != production {len(p)}")
            d = OUT / n
            d.mkdir(parents=True, exist_ok=True)
            (d / "scenerio.gcx").write_bytes(new)
            tot_r += nr
            tot_c += nc
        print(f"repadded {len(names)} stage files")
        print(f"  resources rewritten        : {tot_r:,}")
        print(f"  NUL bytes converted to 0x20: {tot_c:,}")
        print(f"  output: {OUT}")
        return 0

    bad = 0
    stats = {"clean": [0, 0, 0], "old": [0, 0, 0], "new": [0, 0, 0]}
    payload_diff = unexpected = 0
    for n in names:
        c = (CLEAN / n / "scenerio.gcx").read_bytes()
        p = (PROD / n / "scenerio.gcx").read_bytes()
        q = (OUT / n / "scenerio.gcx").read_bytes()
        if len(q) != len(p):
            print(f"{n}: SIZE {len(q)} != {len(p)}")
            bad += 1
            continue
        if q[len(c):] != p[len(c):]:
            print(f"{n}: appended region changed")
            bad += 1
        rc, rp, rq = rec(c), rec(p[:len(c)]), rec(q[:len(c)])
        a, b, d = rc.resources(), rp.resources(), rq.resources()
        if not (len(a) == len(b) == len(d)):
            print(f"{n}: resource count {len(a)}/{len(b)}/{len(d)}")
            bad += 1
            continue
        if (rq.string_resources_offset, rq.resource_table_offset,
                rq.font_data_offset, rq.proc_offset) != \
           (rp.string_resources_offset, rp.resource_table_offset,
                rp.font_data_offset, rp.proc_offset):
            print(f"{n}: header offsets moved")
            bad += 1
        for i in range(len(b)):
            if len(d[i].data) != len(b[i].data) or d[i].table_word != b[i].table_word:
                unexpected += 1
            if d[i].data.split(NUL)[0] != b[i].data.split(NUL)[0]:
                payload_diff += 1
        for tag, res in (("clean", a), ("old", b), ("new", d)):
            s = stats[tag]
            s[0] += sum(trail(x.data) for x in res)
            s[1] += sum(1 for x in res if trail(x.data) > 1)
            s[2] = max(s[2], max((trail(x.data) for x in res), default=0))
    print(f"stage files verified : {len(names)}   failures: {bad}")
    print(f"  translation payload differing from old production : {payload_diff}")
    print(f"  unexpected differences (length / table_word)      : {unexpected}")
    print(f"\n{'':<8}{'trailing NUL total':>20}{'>1 trailing NUL':>18}{'max run':>9}")
    for tag in ("clean", "old", "new"):
        s = stats[tag]
        print(f"{tag:<8}{s[0]:>20,}{s[1]:>18,}{s[2]:>9}")
    return 1 if (bad or unexpected or payload_diff) else 0


if __name__ == "__main__":
    sys.exit(main())
