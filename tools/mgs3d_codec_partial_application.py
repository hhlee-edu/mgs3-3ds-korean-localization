#!/usr/bin/env python3
"""Find strings that are Korean at some in-game locations and still English at others.

Round 5 (2026-08-17) exists because master-level and "representative location"
checks both passed while real hardware still showed English. The cause is that a
master row carries *every* location of its string in `locations`, but a build
step can write only some of them. Checking the canonical `gcx`/`resource` alone
cannot see that.

PARTIAL_APPLICATION = one master row whose locations decode to a mix of Korean
and Latin text in the shipped codec.dat.

Classification per location, from the decoded resource bytes:
  KO      contains a 0x81-0x87 lead-byte wide token (the Korean pages)
  LATIN   no Korean token, but has ASCII letters
  EMPTY   no letters at all (separators, numbers, icon-only)
  MISSING location is not present in the binary

Usage:
    mgs3d_codec_partial_application.py --codec <codec.dat> [--master <codec.csv>]
        [--json OUT] [--csv OUT] [--only-accepted] [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402

csv.field_size_limit(10 ** 9)

DEFAULT_MASTER = pathlib.Path("translation/10_master/current/codec.csv")
CHAR_MAP = pathlib.Path("translation/40_build_input/global_page_v2/character-map.json")


def load_char_map() -> dict[int, str]:
    if not CHAR_MAP.exists():
        return {}
    chars = json.loads(CHAR_MAP.read_text(encoding="utf-8"))["characters"]
    return {int(str(tok), 16): ch for ch, tok in chars.items()}


def decode(data: bytes, inv: dict[int, str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(data):
        c = data[i]
        if 0x81 <= c <= 0x87 and i + 1 < len(data):
            out.append(inv.get((c << 8) | data[i + 1], f"<{c:02X}{data[i + 1]:02X}>"))
            i += 2
        elif c == 0x00:
            out.append("<00>")
            i += 1
        elif c == 0x0A:
            out.append("<0A>")
            i += 1
        elif 0x20 <= c < 0x7F:
            out.append(chr(c))
            i += 1
        else:
            out.append(f"<{c:02X}>")
            i += 1
    return "".join(out)


def has_korean(data: bytes) -> bool:
    """Same rule the coverage gate uses: a 0x81-0x87 lead byte with a second byte."""
    return any(0x81 <= data[i] <= 0x87 and i + 1 < len(data) for i in range(len(data)))


def has_letters(data: bytes) -> bool:
    return any(0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A for b in data)


def classify(data: bytes | None) -> str:
    if data is None:
        return "MISSING"
    if has_korean(data):
        return "KO"
    if has_letters(data):
        return "LATIN"
    return "EMPTY"


def parse_locations(value: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for item in (value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        gcx, _, res = item.partition(":")
        try:
            out.append((int(gcx), int(res)))
        except ValueError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codec", type=pathlib.Path, required=True)
    ap.add_argument("--master", type=pathlib.Path, default=DEFAULT_MASTER)
    ap.add_argument("--json", type=pathlib.Path)
    ap.add_argument("--csv", dest="csv_out", type=pathlib.Path)
    ap.add_argument("--only-accepted", action="store_true",
                    help="restrict to rows with accept=yes")
    ap.add_argument("--limit", type=int, default=25, help="rows to print")
    args = ap.parse_args()

    inv = load_char_map()
    payloads = [[r.data for r in rec.resources()] for rec in parse_codec(args.codec.read_bytes())]

    def get(gcx: int, res: int) -> bytes | None:
        if not 0 <= gcx < len(payloads):
            return None
        if not 0 <= res < len(payloads[gcx]):
            return None
        return payloads[gcx][res]

    with args.master.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    findings = []
    totals = {"rows": 0, "rows_multi_location": 0, "locations": 0,
              "KO": 0, "LATIN": 0, "EMPTY": 0, "MISSING": 0}

    for row in rows:
        if args.only_accepted and (row.get("accept") or "").strip().lower() != "yes":
            continue
        locs = parse_locations(row.get("locations", ""))
        if not locs:
            continue
        totals["rows"] += 1
        if len(locs) > 1:
            totals["rows_multi_location"] += 1
        states: dict[str, list[str]] = {}
        for gcx, res in locs:
            state = classify(get(gcx, res))
            totals["locations"] += 1
            totals[state] += 1
            states.setdefault(state, []).append(f"{gcx}:{res}")
        if "KO" in states and "LATIN" in states:
            findings.append({
                "gcx": row.get("gcx"),
                "resource": row.get("resource"),
                "accept": row.get("accept"),
                "translate": row.get("translate"),
                "language": row.get("language"),
                "is_donor": row.get("is_donor"),
                "blocker": row.get("blocker"),
                "occurrences": len(locs),
                "ko_count": len(states["KO"]),
                "latin_count": len(states["LATIN"]),
                "ko_locations": ";".join(states["KO"]),
                "latin_locations": ";".join(states["LATIN"]),
                "english": row.get("english"),
                "korean": row.get("korean"),
                "sample_latin": decode(get(*[int(x) for x in states["LATIN"][0].split(":")]) or b"", inv),
            })

    findings.sort(key=lambda f: -f["latin_count"])
    print("== PARTIAL_APPLICATION scan ==")
    print(f"codec        : {args.codec}")
    print(f"master       : {args.master}")
    print(f"master rows with locations : {totals['rows']}")
    print(f"  of which multi-location  : {totals['rows_multi_location']}")
    print(f"locations examined         : {totals['locations']}")
    for k in ("KO", "LATIN", "EMPTY", "MISSING"):
        print(f"    {k:8s}: {totals[k]}")
    latin_total = sum(f["latin_count"] for f in findings)
    print(f"\nPARTIAL_APPLICATION rows   : {len(findings)}")
    print(f"  English locations in them: {latin_total}")

    for f in findings[:args.limit]:
        print(f"\n  gcx {f['gcx']}:{f['resource']}  accept={f['accept']} translate={f['translate']} "
              f"lang={f['language']} donor={f['is_donor']}")
        print(f"    KO {f['ko_count']} @ {f['ko_locations'][:90]}")
        print(f"    EN {f['latin_count']} @ {f['latin_locations'][:90]}")
        print(f"    english: {(f['english'] or '')[:90]}")
        print(f"    korean : {(f['korean'] or '')[:90]}")

    if args.json:
        args.json.write_text(json.dumps(
            {"codec": str(args.codec), "totals": totals, "findings": findings},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json}")
    if args.csv_out and findings:
        with args.csv_out.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(findings[0].keys()))
            w.writeheader()
            w.writerows(findings)
        print(f"wrote {args.csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
