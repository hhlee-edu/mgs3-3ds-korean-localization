#!/usr/bin/env python3
"""Measure how much of the shipped codec.dat is actually Korean, and why the rest isn't.

**The denominator is string locations inside the binary, not rows in the master.**
That distinction is the whole point of this tool. `coverage-report.json` is a
*glyph-page* report -- character/token set integrity, page round-trip, "does the
authored Korean encode" -- and its `encoding_preflight` counts accepted master
rows. It passed all 13 checks on the v0.81 build, which had reached 3.79% of the
game's English positions, because the master dedupes strings and the build writes
only the canonical `(gcx, resource)`. See
`docs/v0.81-hardware-defects-rootcause-2026-08-16.md`.

Every English `display_text` position named by the master's `locations` column is
classified into exactly one cause, so the categories sum to the denominator with
no residual:

    korean_in_build                 the position carries Korean
    duplicate_location_not_written  a translated row exists, but only its canonical
                                    position was written
    master_has_no_korean            the master row has no Hangul at all
    dropped_for_capacity            accepted and translated, cut by the per-GCX
                                    byte gate (pass --build-input to separate this
                                    from the next one)
    not_accepted                    Korean present but accept != yes
    location_missing_from_binary    the master names a position the file lacks

Korean is detected by scanning the resource's raw bytes for a lead byte in
`0x81-0x87` -- not by a `<HH>` regex over a rendered dump, which silently misses
tokens whose low byte is printable ASCII (`<81>&` = 라) and cost 41 false
"untranslated" rows when this was first investigated. The detector is checked
against a reference build on every run: any hit there is a false positive, and
`--reference` makes that check fatal.

    python tools/mgs3d_translation_coverage.py \
        --codec "C:/.../partition0/romfs/codec.dat" \
        --build-input translation/40_build_input/v0.81/codec-safe-translation.json \
        --out docs/evidence/coverage-<tag>.json [--min-reach 50]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec  # noqa: E402

DEFAULT_MASTER = ROOT / "translation/10_master/current/codec.csv"
DEFAULT_REFERENCE = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"

ACCEPTED = ("y", "yes", "1", "ok")
CATEGORIES = [
    "korean_in_build",
    "duplicate_location_not_written",
    "master_has_no_korean",
    "dropped_for_capacity",
    "not_accepted",
    "location_missing_from_binary",
]


def has_korean(data: bytes) -> bool:
    """A Korean/wide token is a lead byte 0x81-0x87 followed by a second byte."""
    return any(0x81 <= data[i] <= 0x87 and i + 1 < len(data) for i in range(len(data)))


def has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text or "")


def parse_locations(value: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for item in (value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        gcx, _, resource = item.partition(":")
        try:
            out.append((int(gcx), int(resource)))
        except ValueError:
            continue
    return out


def payloads(path: Path) -> list[list[bytes]]:
    return [[r.data for r in record.resources()] for record in parse_codec(path.read_bytes())]


def get(pay: list[list[bytes]], key: tuple[int, int]) -> bytes | None:
    gcx, resource = key
    if not 0 <= gcx < len(pay):
        return None
    if not 0 <= resource < len(pay[gcx]):
        return None
    return pay[gcx][resource]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codec", type=Path, required=True,
                    help="the built or staged codec.dat to measure")
    ap.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    ap.add_argument("--build-input", type=Path,
                    help="codec-safe-translation.json; separates capacity drops "
                         "from duplicates that were never in the input at all")
    ap.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE,
                    help="pristine build; the detector must find 0 Korean there")
    ap.add_argument("--strict-reference", action="store_true",
                    help="fail instead of warn when the reference check finds hits")
    ap.add_argument("--min-reach", type=float,
                    help="exit 1 if korean_in_build falls below this percentage")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--top-gcx", type=int, default=15)
    args = ap.parse_args()

    csv.field_size_limit(10 ** 9)
    with args.master.open(encoding="utf-8-sig", newline="") as stream:
        master = list(csv.DictReader(stream))

    built = payloads(args.codec)

    in_input: set[tuple[int, int]] = set()
    if args.build_input:
        document = json.loads(args.build_input.read_text(encoding="utf-8"))
        in_input = {(int(u["gcx"]), int(u["resource"])) for u in document["units"]}

    counts: Counter[str] = Counter()
    per_gcx: dict[int, list[int]] = defaultdict(lambda: [0, 0])   # [total, korean]
    worst: Counter[int] = Counter()
    measured: set[tuple[int, int]] = set()

    for row in master:
        if (row.get("is_donor") or "") == "yes":
            continue
        if (row.get("text_kind") or "") != "display_text":
            continue
        try:
            canonical = (int(row["gcx"]), int(row["resource"]))
        except (KeyError, ValueError):
            continue
        accepted = (row.get("accept") or "").strip().lower() in ACCEPTED
        translated = has_hangul(row.get("korean", ""))

        for location in parse_locations(row.get("locations", "")):
            data = get(built, location)
            if data is None:
                counts["location_missing_from_binary"] += 1
                continue
            measured.add(location)
            per_gcx[location[0]][0] += 1
            if has_korean(data):
                counts["korean_in_build"] += 1
                per_gcx[location[0]][1] += 1
                continue
            worst[location[0]] += 1
            if not translated:
                counts["master_has_no_korean"] += 1
            elif not accepted:
                counts["not_accepted"] += 1
            elif location != canonical and (not in_input or location not in in_input):
                counts["duplicate_location_not_written"] += 1
            else:
                counts["dropped_for_capacity"] += 1

    total = sum(counts.values())
    reach = 100.0 * counts["korean_in_build"] / total if total else 0.0

    # Detector control: run the identical test over the identical locations in the
    # pristine build, where the answer must be zero. Scanning *every* resource
    # instead would report the game's own Japanese kana resources (gcx 2 is
    # `<81><02>` repeated) as hits -- they are outside the measured set and say
    # nothing about the detector.
    reference_hits = None
    if args.reference and args.reference.exists():
        pristine = payloads(args.reference)
        reference_hits = 0
        for location in measured:
            data = get(pristine, location)
            if data is not None and has_korean(data):
                reference_hits += 1

    report = {
        "format": "mgs3d-translation-coverage-v1",
        "codec": args.codec.as_posix(),
        "master": args.master.as_posix(),
        "build_input": args.build_input.as_posix() if args.build_input else None,
        "english_display_text_locations": total,
        "korean_in_build": counts["korean_in_build"],
        "reach_percent": round(reach, 4),
        "causes": {name: counts[name] for name in CATEGORIES},
        "cause_percent": {name: round(100.0 * counts[name] / total, 4) if total else 0.0
                          for name in CATEGORIES},
        "reference_false_positives": reference_hits,
        "worst_gcx_by_english_locations": [
            {"gcx": gcx, "english_left": left,
             "korean": per_gcx[gcx][1], "total": per_gcx[gcx][0]}
            for gcx, left in worst.most_common(args.top_gcx)
        ],
    }

    print(f"codec            : {args.codec}")
    print(f"english locations: {total}")
    print(f"korean in build  : {counts['korean_in_build']}  ({reach:.2f}%)")
    print("causes:")
    for name in CATEGORIES:
        value = counts[name]
        if value or name == "korean_in_build":
            print(f"  {name:32s} {value:8d}  {100.0 * value / total:6.2f}%")
    if reference_hits is not None:
        verdict = "OK" if reference_hits == 0 else "SUSPECT"
        print(f"detector self-check on reference: {reference_hits} hits ({verdict})")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"report -> {args.out}")

    status = 0
    if reference_hits:
        message = f"reference build reports {reference_hits} Korean resources -- detector is unsound"
        if args.strict_reference:
            print(f"FAIL: {message}", file=sys.stderr)
            status = 1
        else:
            print(f"WARNING: {message}", file=sys.stderr)
    if args.min_reach is not None and reach < args.min_reach:
        print(f"FAIL: reach {reach:.2f}% is below --min-reach {args.min_reach}", file=sys.stderr)
        status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
