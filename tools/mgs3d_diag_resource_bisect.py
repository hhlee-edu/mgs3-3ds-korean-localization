#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resource-level bisection of a stage's translated payload against clean.

By 2026-08-20 the padding policy, the appended glyph page, the line-break
structure and the short UI labels had all been tested on hardware and cleared
for `r_sna01` (SAVE label) and `v007a_0` (PROFILE 04/04). What is left is the
translated payload itself, so this searches it directly instead of inventing
another semantic hypothesis.

Base is each stage's P2 variant. Candidates are every resource whose payload
still differs from clean. A round restores a contiguous slice of the candidate
list -- ordered by (record, resource), never by meaning or length -- to clean's
exact bytes and leaves the rest at P2.

Candidate sets are kept per symptom and are recomputed from the journal by set
algebra (present in every ng set, absent from every ok set), so more than one
culprit resource stays representable.

    candidates <stage>              list the candidate resources
    apply <stage> --slice a:b[,c:d] write the variant, restoring those to clean
    record <symptom> ok|ng|unknown  log the result of the last applied slice
    plan                            journal table and each symptom's candidates
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import GcxRecord, align  # noqa: E402

CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/stage"
P2 = ROOT / "builds/diag-2026-08-20-p2"
OUT = ROOT / "builds/diag-2026-08-20-resource-bisect"
JOURNAL = OUT / "journal.json"
NUL = bytes([0])
SYMPTOM = {"r_sna01": "save", "v007a_0": "profile"}


def rec(data: bytes) -> GcxRecord:
    padded = data + NUL * (align(len(data)) - len(data))
    record, _ = GcxRecord.from_codec(padded, 0)
    return record


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def base_and_clean(stage: str) -> tuple[bytes, bytes]:
    return ((P2 / stage / f"{stage}-P2.gcx").read_bytes(),
            (CLEAN / stage / "scenerio.gcx").read_bytes())


def candidates(stage: str) -> list[int]:
    """Resources whose payload still differs from clean, ordered by index.

    One GCX record per stage file, so (record, resource) collapses to resource
    index -- the ordering is the file's own, never content-derived.
    """
    b, c = base_and_clean(stage)
    rb, rc = rec(b).resources(), rec(c).resources()
    return [i for i in range(len(rc)) if rb[i].data != rc[i].data]


def build(stage: str, restore: list[int]) -> bytes:
    b, c = base_and_clean(stage)
    rb = rec(b)
    rc = rec(c).resources()
    repl = {i: rc[i].data for i in restore}
    out = rb.replace_resources(repl, preserve_layout=True) if repl else b
    return out[:len(c)] if len(out) >= len(c) else out + NUL * (len(c) - len(out))


def parse_slice(spec: str, n: int) -> list[int]:
    idx: list[int] = []
    for part in spec.split(","):
        a, z = (int(x) if x else None for x in part.split(":"))
        idx += list(range(*slice(a, z).indices(n)))
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("candidates", "apply", "record", "plan"))
    ap.add_argument("target", nargs="?")
    ap.add_argument("verdict", nargs="?", choices=("ok", "ng", "unknown"))
    ap.add_argument("--slice")
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    j = json.loads(JOURNAL.read_text(encoding="utf-8")) if JOURNAL.exists() else {"runs": []}

    if args.action == "candidates":
        cand = candidates(args.target)
        print(f"{args.target}: {len(cand)} candidate resources (payload still differs from clean)")
        print(f"  first {cand[:8]} ... last {cand[-8:]}")
        return 0

    if args.action == "plan":
        print("  " + "".join(f"{s:<10}" for s in ("save", "profile")) + "restored  stage/slice")
        for r in j["runs"]:
            sym = r.get("symptoms") or {}
            cells = "".join(f"{sym.get(s, '-'):<10}" for s in ("save", "profile"))
            print(f"  {cells}{len(r['restored']):<10}{r['stage']} {r['slice']}   {r.get('note','')}")
        print()
        for stage, symptom in SYMPTOM.items():
            uni = set(candidates(stage))
            cand = set(uni)
            seen = False
            for r in j["runs"]:
                if r["stage"] != stage:
                    continue
                v = (r.get("symptoms") or {}).get(symptom)
                restored = set(r["restored"])
                if v == "ok":
                    # symptom cured by restoring these -> a culprit is among them
                    cand &= restored; seen = True
                elif v == "ng":
                    # still broken with these restored -> no culprit among them
                    cand -= restored; seen = True
            if not seen:
                print(f"  {symptom:<8} {len(cand):>5} candidates (no verdicts yet)")
                continue
            lst = sorted(cand)
            print(f"  {symptom:<8} {len(lst):>5} candidates")
            if len(lst) == 1:
                print(f"           CULPRIT resource {lst[0]} in {stage}")
            elif lst:
                half = lst[: (len(lst) + 1) // 2]
                print(f"           next: restore {len(half)} of {len(lst)} -> indices {half[0]}..{half[-1]}")
        return 0

    if args.action == "record":
        # A round applies one slice per stage, so the verdict must land on that
        # symptom's own run, not simply on the last one written.
        stage = next((s for s, sym in SYMPTOM.items() if sym == args.target), None)
        if stage is None:
            raise SystemExit(f"unknown symptom {args.target!r}; try {sorted(SYMPTOM.values())}")
        run = next((r for r in reversed(j["runs"]) if r["stage"] == stage), None)
        if run is None:
            raise SystemExit(f"no applied slice for {stage}")
        run.setdefault("symptoms", {})[args.target] = args.verdict
        if args.note:
            run["note"] = args.note
        JOURNAL.write_text(json.dumps(j, indent=1), encoding="utf-8")
        print(f"recorded {args.target}={args.verdict}")
        return 0

    stage = args.target
    cand = candidates(stage)
    restore = [cand[k] for k in parse_slice(args.slice, len(cand))]
    blob = build(stage, restore)
    d = OUT / stage
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stage}-R.gcx").write_bytes(blob)
    print(f"{stage}: {len(cand)} candidates, restoring {len(restore)} to clean -> {d}")
    print(f"   size {len(blob):,}  sha {sha(blob)}")
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    j["runs"].append({"stage": stage, "slice": args.slice, "restored": restore,
                      "candidates": len(cand), "symptoms": {}})
    JOURNAL.write_text(json.dumps(j, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
