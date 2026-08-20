#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A/B bisect the 177 changed files against the clean v1.0 baseline.

2026-08-20: clean v1.0 renders PROFILE, Major Tom, The Boss and SAVE correctly,
so all four defects are a regression in our change set, not stock behaviour.
D2 already showed the PERSONAL DATA *data* is not the cause -- restoring those
27,132 resources to clean English left PROFILE broken -- so the culprit is one
of the other changed files.

This tool re-injects production files onto the clean tree in named groups, so
each repack answers a yes/no question instead of testing one file at a time.
Every file is always in a defined state: production or clean. Never a mix left
over from a previous run.

    groups                    list the groups and their file counts
    status                    report how many files of each group are production
    apply <group> [<group>..] set exactly those groups to production, rest clean
    apply <group> --slice a:b sub-bisect inside one group by file index
    reset                     everything back to clean v1.0
    record --profile/--tom/--boss/--save ok|ng|unknown   log the four symptoms
    plan                      show the journal as a symptom table

The four defects are recorded separately on purpose: they may not have the same
cause inside the change set, and a round where one splits differently from the
others settles that immediately.

Production sources are pinned to the binaries the defects were actually observed
with: `code.bin` = 4e693f32 (CPP + glyph hooks, alias 0xA0..0xA3) and
`codec.dat` = 72936022 (v0.96), not the later D2/alias-fix builds.
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
SWAP = ROOT / "builds/diag-2026-08-20-clean-tree-swap"
BACKUP = SWAP / "staging-backup"
MANIFEST = SWAP / "manifest.json"
JOURNAL = ROOT / "builds/diag-2026-08-20-bisect/journal.json"

# production binaries as observed failing, overriding the D2-era backup
PINNED = {
    "exefs/code.bin": ROOT / "builds/diag-2026-08-20-alias-range/production-backup/exefs/code.bin",
    "romfs/codec.dat": ROOT / "builds/diag-2026-08-20-codec-textidentity/romfs/codec.dat",
}


# save: the SAVE contact's LABEL STRING. Corrected 2026-08-20 - the channel
# itself works; only its label text goes missing, so this is a string defect,
# not a contact-index shift.
SYMPTOMS = ("profile", "tom", "boss", "save", "titlearea")


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def group_of(path: str) -> str:
    if path in ("exefs/code.bin", "exheader.bin"):
        return "exec"
    if path.endswith(("resident.hpk", "cache.hpk")):
        return "font"
    if path == "romfs/codec.dat":
        return "codec"
    if path in ("romfs/movie.dat", "romfs/demo.dat"):
        return "media"
    if path.endswith("scenerio.gcx"):
        return "stage"
    return "other"


def as_ranges(idx: list[int]) -> str:
    """Compress sorted indices into the comma-separated a:b form --slice accepts."""
    out, start, prev = [], idx[0], idx[0]
    for x in idx[1:]:
        if x == prev + 1:
            prev = x; continue
        out.append((start, prev + 1)); start = prev = x
    out.append((start, prev + 1))
    return ",".join(f"{a}:{b}" for a, b in out)


def load() -> dict[str, list[str]]:
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    out: dict[str, list[str]] = {}
    for r in files:
        out.setdefault(group_of(r["path"]), []).append(r["path"])
    for v in out.values():
        v.sort()
    return out


def prod_source(rel: str) -> pathlib.Path:
    return PINNED.get(rel, BACKUP / rel)


def set_state(rel: str, production: bool) -> tuple[bool, str]:
    src = prod_source(rel) if production else CLEAN / rel
    dst = STAGING / rel
    want = sha(src)
    if sha(dst) == want:
        return True, want
    shutil.copy2(src, dst)
    return sha(dst) == want, want


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("groups", "status", "apply", "reset", "record", "plan"))
    ap.add_argument("names", nargs="*")
    ap.add_argument("--slice", help="a:b index range inside a single group; several "
                                    "comma-separated ranges are allowed, e.g. 0:42,85:127, "
                                    "so two independent bisections can share one repack")
    ap.add_argument("--note", default="")
    for sym in SYMPTOMS:
        ap.add_argument(f"--{sym}", choices=("ok", "ng", "unknown"),
                        help=f"{sym} result; 'unknown' = not checked this round")
    args = ap.parse_args()
    groups = load()

    if args.action == "groups":
        for g, fs in sorted(groups.items()):
            print(f"{g:<8}{len(fs):>5} files   e.g. {fs[0]}")
        print(f"{'TOTAL':<8}{sum(len(f) for f in groups.values()):>5}")
        return 0

    if args.action == "status":
        for g, fs in sorted(groups.items()):
            p = sum(1 for rel in fs if sha(STAGING / rel) == sha(prod_source(rel)))
            print(f"{g:<8}{p:>5}/{len(fs):<5} production")
        return 0

    if args.action == "plan":
        j = json.loads(JOURNAL.read_text(encoding="utf-8")) if JOURNAL.exists() else {"runs": []}
        universe = {rel for fs in groups.values() for rel in fs}
        print("  " + "".join(f"{s:<10}" for s in SYMPTOMS) + "files  set")
        for r in j["runs"]:
            sym = r.get("symptoms") or {}
            cells = "".join(f"{sym.get(s, "-"):<10}" for s in SYMPTOMS)
            sl = r.get("slice")
            label = ("+".join(r["groups"]) or "clean") + (f" {sl}" if sl else "")
            note = r.get("note", "")
            files_in = r["files"]
            print(f"  {cells}{len(files_in):<7}{label}   {note}")
        print()
        print("  per-symptom candidates (in every ng set, in no ok set)")
        for s in SYMPTOMS:
            cand = set(universe)
            seen = False
            for r in j["runs"]:
                v = (r.get("symptoms") or {}).get(s)
                if v == "ng":
                    cand &= set(r["files"]); seen = True
                elif v == "ok":
                    cand -= set(r["files"]); seen = True
            if not seen:
                print(f"    {s:<8} no verdicts yet")
                continue
            owner = {group_of(x) for x in cand}
            where = next(iter(owner)) if len(owner) == 1 else f"{len(owner)} groups"
            print(f"    {s:<8}{len(cand):>5} candidates   ({where})")
            if len(cand) == 1:
                print(f"             CULPRIT: {sorted(cand)[0]}")
            elif len(cand) > 1 and len(owner) == 1:
                g = next(iter(owner))
                idx = sorted(groups[g].index(x) for x in cand)
                half = idx[: (len(idx) + 1) // 2]
                print(f"             next: apply {g} --slice {as_ranges(half)}"
                      f"   ({len(half)} of {len(idx)})")
        return 0

    if args.action == "record":
        given = {s: getattr(args, s) for s in SYMPTOMS if getattr(args, s)}
        if not given:
            raise SystemExit("record needs at least one of --profile/--tom/--boss/--save ok|ng")
        j = json.loads(JOURNAL.read_text(encoding="utf-8")) if JOURNAL.exists() else {"runs": []}
        if not j["runs"]:
            raise SystemExit("no applied set to record - run 'apply' first")
        j["runs"][-1].setdefault("symptoms", {}).update(given)
        if args.note:
            j["runs"][-1]["note"] = args.note
        JOURNAL.write_text(json.dumps(j, indent=1), encoding="utf-8")
        print(f"recorded {given} for {'+'.join(j['runs'][-1]['groups']) or 'clean'}")
        return 0

    # apply / reset
    want_prod: list[str] = []
    picked = [] if args.action == "reset" else args.names
    for g in picked:
        if g not in groups:
            raise SystemExit(f"unknown group {g!r}; try 'groups'")
    if args.slice:
        if len(picked) != 1:
            raise SystemExit("--slice needs exactly one group")
        for part in args.slice.split(","):
            a, b = (int(x) if x else None for x in part.split(":"))
            want_prod += groups[picked[0]][a:b]
    else:
        for g in picked:
            want_prod += groups[g]

    prod = set(want_prod)
    rc = 0
    changed = 0
    for g, fs in sorted(groups.items()):
        for rel in fs:
            ok, _ = set_state(rel, rel in prod)
            if not ok:
                print(f"HASH MISMATCH {rel}")
                rc = 1
            else:
                changed += 1
    print(f"staged: {len(prod)} production / {changed - len(prod)} clean  (177 total)")
    for g in sorted(groups):
        n = sum(1 for rel in groups[g] if rel in prod)
        print(f"   {g:<8}{n:>5}/{len(groups[g])}")
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    j = json.loads(JOURNAL.read_text(encoding="utf-8")) if JOURNAL.exists() else {"runs": []}
    j["runs"].append({"groups": picked, "slice": args.slice, "files": sorted(prod), "symptoms": {}})
    JOURNAL.write_text(json.dumps(j, indent=1), encoding="utf-8")
    print(f"\njournal: {JOURNAL}  (run 'record good|bad' after the hardware test)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
