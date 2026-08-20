#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the clean / production / M1 / M2 / P1 decomposition for one stage.

A production `scenerio.gcx` differs from clean in two independent ways: the
strings in the original GCX record are translated, and a large Korean glyph
page is appended past the original EOF. The 2026-08-20 work on `v001a` split
them like this and the split is what identified the trailing-NUL padding:

    M1  translated original region, append stripped   (size == clean)
    M2  clean original region + production's append   (size == production)
    P1  M1 with every surplus trailing NUL restored to the clean run length
        and the slack filled with 0x20                (size == clean)

M1 and M2 are exact complements. P1 differs from M1 only in padding bytes.

    build <stage>    write the four variants under builds/diag-2026-08-20-variants/<stage>
    verify <stage>   prove what each variant does and does not change
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
OUT = ROOT / "builds/diag-2026-08-20-variants"
NUL = bytes([0])
PAD = bytes([0x20])


def rec(data: bytes) -> GcxRecord:
    padded = data + NUL * (align(len(data)) - len(data))
    record, _ = GcxRecord.from_codec(padded, 0)
    return record


def trail(b: bytes) -> int:
    return len(b) - len(b.rstrip(NUL))


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def variants(stage: str) -> dict[str, bytes]:
    c = (CLEAN / stage / "scenerio.gcx").read_bytes()
    p = (PROD / stage / "scenerio.gcx").read_bytes()
    m1 = p[:len(c)]
    m2 = c + p[len(c):]
    rm = rec(m1)
    src, ref = rm.resources(), rec(c).resources()
    repl = {}
    for i, r in enumerate(src):
        tp, tc = trail(r.data), trail(ref[i].data)
        if tp <= 1 or tp <= tc:
            continue
        core = r.data.rstrip(NUL)
        keep = max(1, tc)
        if len(core) + keep > len(r.data):
            continue
        repl[i] = core + NUL * keep + PAD * (len(r.data) - len(core) - keep)
    p1 = rm.replace_resources(repl, preserve_layout=True) if repl else m1
    p1 = p1[:len(c)] if len(p1) >= len(c) else p1 + NUL * (len(c) - len(p1))
    return {"clean": c, "production": p, "M1": m1, "M2": m2, "P1": p1}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "verify"))
    ap.add_argument("stage")
    args = ap.parse_args()
    v = variants(args.stage)
    if args.action == "build":
        d = OUT / args.stage
        d.mkdir(parents=True, exist_ok=True)
        for name, blob in v.items():
            if name in ("clean", "production"):
                continue
            (d / f"{args.stage}-{name}.gcx").write_bytes(blob)
        print(f"{args.stage}: wrote M1 / M2 / P1 to {d}")
    c, p = v["clean"], v["production"]
    print(f"\n{'variant':<12}{'size':>10}  sha256")
    for name in ("clean", "production", "M1", "M2", "P1"):
        print(f"{name:<12}{len(v[name]):>10,}  {sha(v[name])}")
    print(f"\nwhat each variant changes")
    print(f"  M1 size == clean                     : {len(v['M1']) == len(c)}")
    print(f"  M1 body == production body           : {v['M1'] == p[:len(c)]}")
    print(f"  M2 size == production                : {len(v['M2']) == len(p)}")
    print(f"  M2 body == clean body (byte)         : {v['M2'][:len(c)] == c}")
    print(f"  M2 append == production append       : {v['M2'][len(c):] == p[len(c):]}")
    print(f"  M1/M2 share no bytes in the body     : {v['M1'] != v['M2'][:len(c)]}")
    rc, r1, rp1 = rec(c).resources(), rec(v["M1"]).resources(), rec(v["P1"]).resources()
    same_len = all(len(rp1[i].data) == len(r1[i].data) for i in range(len(r1)))
    same_str = all(rp1[i].data.split(NUL)[0] == r1[i].data.split(NUL)[0] for i in range(len(r1)))
    same_tw = all(rp1[i].table_word == r1[i].table_word for i in range(len(r1)))
    print(f"  P1 size == clean                     : {len(v['P1']) == len(c)}")
    print(f"  P1 resource lengths == M1            : {same_len}")
    print(f"  P1 payload to first terminator == M1 : {same_str}")
    print(f"  P1 table_word == M1                  : {same_tw}")
    for tag, res in (("clean", rc), ("M1", r1), ("P1", rp1)):
        print(f"    {tag:<6} resources {len(res):>6}  trailing-NUL total {sum(trail(x.data) for x in res):>8,}"
              f"  >1 run {sum(1 for x in res if trail(x.data) > 1):>6,}"
              f"  max run {max((trail(x.data) for x in res), default=0):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
