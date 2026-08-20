#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure untranslated English left in a built codec.dat by reading the binary.

Added 2026-08-20. The final gate's coverage number is a *master-side declaration*:
it sums `occurrences` over accept=yes rows and never re-reads the built DAT, so a
build step that silently drops duplicate locations still reports 100%. That is
exactly how v0.91-v0.93 shipped 570 dropped locations (see
docs/evidence/2026-08-20-hardware-qa-4defects/README.md).

This is the binary-side counterpart. For every accepted master row that carries a
translation, each of its `locations` is classified against BOTH the clean
reference DAT and the built DAT:

  APPLIED      built bytes == the master translation, encoded
  ENGLISH      built bytes == the clean English bytes, and the translation differs
               -> the translation never reached this location
  OTHER        built bytes match neither; usually the location is claimed by two
               master rows and the other row (correctly) owns it

Counting "does it still equal the clean English" rather than "does it look Latin"
matters: 141 accepted rows translate to ASCII on purpose (proper nouns such as
"Snake!", "C3?", "TUXEDO."), and a Latin-script heuristic reports those as
untranslated when they are in fact applied.

Usage:
    mgs3d_codec_dat_residue.py --built <codec.dat> [--clean <codec.dat>]
        [--master <codec.csv>] [--json OUT]
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, parse_rendered  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
DEFAULT_MASTER = ROOT / "translation/10_master/current/codec.csv"
DEFAULT_MAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"

NUL = bytes([0])


def payloads(path: pathlib.Path) -> list[list[bytes]]:
    return [[r.data for r in rec.resources()] for rec in parse_codec(path.read_bytes())]


def parse_locations(value: str) -> list[tuple[int, int]]:
    out = []
    for item in (value or "").split(";"):
        item = item.strip()
        if ":" not in item:
            continue
        gcx, _, res = item.partition(":")
        try:
            out.append((int(gcx), int(res)))
        except ValueError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--built", type=pathlib.Path, required=True)
    ap.add_argument("--clean", type=pathlib.Path, default=DEFAULT_CLEAN)
    ap.add_argument("--master", type=pathlib.Path, default=DEFAULT_MASTER)
    ap.add_argument("--character-map", type=pathlib.Path, default=DEFAULT_MAP)
    ap.add_argument("--json", dest="json_out", type=pathlib.Path)
    args = ap.parse_args()

    csv.field_size_limit(10 ** 9)
    cmap = {c: bytes.fromhex(str(t)) for c, t in
            json.loads(args.character_map.read_text(encoding="utf-8"))["characters"].items()}
    built = payloads(args.built)
    clean = payloads(args.clean)
    with args.master.open(encoding="utf-8-sig", newline="") as fh:
        master = list(csv.DictReader(fh))

    def at(pay, gcx, res):
        if not (0 <= gcx < len(pay)) or not (0 <= res < len(pay[gcx])):
            return None
        return pay[gcx][res]

    counts = collections.Counter()
    english_locs: list[dict] = []
    other_locs: list[dict] = []
    ascii_only_locs = 0
    encode_failures: list[dict] = []

    for row in master:
        if (row.get("accept") or "").strip().lower() != "yes":
            continue
        korean = row.get("korean") or ""
        if not korean.strip():
            continue
        donor = (row.get("is_donor") or "") == "yes"
        try:
            want = parse_rendered(korean, cmap).rstrip(NUL)
        except Exception as exc:                                  # noqa: BLE001
            # The builder maps a few typographic characters that the plain
            # encoder does not (e.g. U+2026 -> "..."); such a row cannot be
            # compared here, but it is not evidence of residue.
            encode_failures.append({"gcx": row.get("gcx"), "resource": row.get("resource"),
                                    "error": str(exc)[:80]})
            continue
        is_ascii_only = all(b < 0x80 for b in want)
        for gcx, res in parse_locations(row.get("locations", "")):
            b = at(built, gcx, res)
            c = at(clean, gcx, res)
            if b is None or c is None:
                counts["MISSING"] += 1
                continue
            bn, cn = b.rstrip(NUL), c.rstrip(NUL)
            if bn == want:
                counts["APPLIED"] += 1
                if is_ascii_only:
                    ascii_only_locs += 1
            elif bn == cn and want != cn:
                counts["ENGLISH"] += 1
                rec = {"location": "%d:%d" % (gcx, res),
                       "canonical": "%s:%s" % (row.get("gcx"), row.get("resource")),
                       "language": row.get("language"), "is_donor": row.get("is_donor")}
                english_locs.append(rec)
            else:
                counts["OTHER"] += 1
                other_locs.append({"location": "%d:%d" % (gcx, res),
                                   "canonical": "%s:%s" % (row.get("gcx"), row.get("resource")),
                                   "is_donor": row.get("is_donor")})

    nondonor = [e for e in english_locs if e["is_donor"] != "yes"]
    donor = [e for e in english_locs if e["is_donor"] == "yes"]

    result = {
        "format": "mgs3d-codec-dat-residue-v1",
        "built": str(args.built),
        "clean": str(args.clean),
        "locations_checked": sum(counts.values()),
        "by_state": dict(counts),
        "nondonor_english_locations": len(nondonor),
        "donor_english_locations": len(donor),
        "ascii_only_translation_locations": ascii_only_locs,
        "other_locations": len(other_locs),
        "encode_failures": len(encode_failures),
        "nondonor_english_sample": nondonor[:50],
        "other_sample": other_locs[:20],
        "encode_failure_sample": encode_failures[:10],
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")

    print("locations checked            : %d" % result["locations_checked"])
    for k in ("APPLIED", "ENGLISH", "OTHER", "MISSING"):
        print("   %-8s %d" % (k, counts[k]))
    print("non-donor English locations  : %d" % len(nondonor))
    print("donor (fr/es) English        : %d" % len(donor))
    print("ASCII-only translations      : %d  (counted as APPLIED)" % ascii_only_locs)
    print("ambiguous OTHER              : %d" % len(other_locs))
    print("encode failures              : %d" % len(encode_failures))
    for e in nondonor[:15]:
        print("   ENGLISH %s (canonical %s, lang=%s)" % (e["location"], e["canonical"], e["language"]))
    return 0 if not nondonor else 1


if __name__ == "__main__":
    raise SystemExit(main())
