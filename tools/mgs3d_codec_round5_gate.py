#!/usr/bin/env python3
"""Round 5 (2026-08-17) codec gate: structural drift, KO->EN regression, and the
three hardware-confirmed anchors, all checked at EVERY location rather than at
the canonical one.

Round 5 exists because canonical-location verification passed 100% while real
hardware still showed English. The defect lived only at duplicate locations, so
this gate always enumerates `locations`, never just `gcx`/`resource`.

Usage:
    mgs3d_codec_round5_gate.py --old <previous codec.dat> --new <rebuilt codec.dat>
        [--master translation/10_master/current/codec.csv] [--json OUT]
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

CHAR_MAP = pathlib.Path("translation/40_build_input/global_page_v2/character-map.json")

# gcx:res -> what the string must be after Round 5.
ANCHORS = {
    "A_backpack": ["20:17", "52:34", "53:47"],
    "C_godzilla": [f"2173:{r}" for r in
                   (10, 11, 18, 19, 20, 21, 22, 25, 27, 28, 29, 31, 34, 35, 38, 39)],
}


def load_inv() -> dict[int, str]:
    chars = json.loads(CHAR_MAP.read_text(encoding="utf-8"))["characters"]
    return {int(str(tok), 16): ch for ch, tok in chars.items()}


def decode(data: bytes, inv: dict[int, str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(data):
        c = data[i]
        if 0x81 <= c <= 0x87 and i + 1 < len(data):
            out.append(inv.get((c << 8) | data[i + 1], "?"))
            i += 2
        elif c == 0x00:
            break
        elif c == 0x0A:
            out.append(" ")
            i += 1
        elif 0x20 <= c < 0x7F:
            out.append(chr(c))
            i += 1
        else:
            out.append(f"<{c:02X}>")
            i += 1
    return "".join(out)


def has_korean(data: bytes) -> bool:
    return any(0x81 <= data[i] <= 0x87 and i + 1 < len(data) for i in range(len(data)))


def has_letters(data: bytes) -> bool:
    return any(0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A for b in data)


def parse_locations(value: str) -> list[tuple[int, int]]:
    out = []
    for item in (value or "").split(";"):
        item = item.strip()
        if not item:
            continue
        g, _, r = item.partition(":")
        try:
            out.append((int(g), int(r)))
        except ValueError:
            continue
    return out


def load(path: pathlib.Path):
    records = parse_codec(path.read_bytes())
    return records, [[r.data for r in rec.resources()] for rec in records]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old", type=pathlib.Path, required=True)
    ap.add_argument("--new", type=pathlib.Path, required=True)
    ap.add_argument("--master", type=pathlib.Path,
                    default=pathlib.Path("translation/10_master/current/codec.csv"))
    ap.add_argument("--json", type=pathlib.Path)
    args = ap.parse_args()

    inv = load_inv()
    old_recs, old_pay = load(args.old)
    new_recs, new_pay = load(args.new)
    results: dict[str, object] = {}
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results[name] = {"pass": bool(ok), "detail": detail}
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
        if not ok:
            failures.append(name)

    print("== structural ==")
    o, n = args.old.stat().st_size, args.new.stat().st_size
    check("size_delta_zero", o == n, f"{o:,} -> {n:,} ({n - o:+d})")
    check("record_count", len(old_recs) == len(new_recs), f"{len(old_recs)} -> {len(new_recs)}")
    drift = sum(1 for a, b in zip(old_recs, new_recs) if a.block_start != b.block_start)
    check("block_start_drift_zero", drift == 0, f"{drift} records drifted")
    sizes = sum(1 for a, b in zip(old_recs, new_recs) if len(a.raw) != len(b.raw))
    check("record_size_drift_zero", sizes == 0, f"{sizes} records changed size")
    counts = sum(1 for a, b in zip(old_pay, new_pay) if len(a) != len(b))
    check("resource_count_drift_zero", counts == 0, f"{counts} records changed resource count")

    print("\n== KO -> EN regression (every location) ==")
    regressions = []
    for g, (a, b) in enumerate(zip(old_pay, new_pay)):
        for r, (x, y) in enumerate(zip(a, b)):
            if has_korean(x) and not has_korean(y) and has_letters(y):
                regressions.append(f"{g}:{r}")
    check("ko_to_en_regression_zero", not regressions,
          f"{len(regressions)} locations lost Korean" +
          (f" e.g. {regressions[:5]}" if regressions else ""))

    print("\n== PARTIAL_APPLICATION (mixed KO/Latin across one row's locations) ==")
    with args.master.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    mixed_old = mixed_new = 0
    mixed_rows = []
    for row in rows:
        locs = parse_locations(row.get("locations", ""))
        if len(locs) < 2:
            continue
        for pay, bump in ((old_pay, "old"), (new_pay, "new")):
            ko = latin = 0
            for g, r in locs:
                if g >= len(pay) or r >= len(pay[g]):
                    continue
                d = pay[g][r]
                if has_korean(d):
                    ko += 1
                elif has_letters(d):
                    latin += 1
            if ko and latin:
                if bump == "old":
                    mixed_old += 1
                else:
                    mixed_new += 1
                    mixed_rows.append(f"{row.get('gcx')}:{row.get('resource')}")
    print(f"  previous build : {mixed_old} rows")
    print(f"  this build     : {mixed_new} rows")
    results["partial_application"] = {"old": mixed_old, "new": mixed_new,
                                      "rows": mixed_rows[:80]}

    print("\n== anchors, at EVERY location ==")
    for name, locs in ANCHORS.items():
        states = []
        for loc in locs:
            g, r = (int(v) for v in loc.split(":"))
            d = new_pay[g][r] if g < len(new_pay) and r < len(new_pay[g]) else b""
            states.append((loc, "KO" if has_korean(d) else "LATIN", decode(d, inv)[:60]))
        ok = all(s == "KO" for _, s, _ in states)
        check(f"anchor_{name}_all_korean", ok,
              f"{sum(1 for _, s, _ in states if s == 'KO')}/{len(states)} Korean")
        for loc, s, txt in states:
            print(f"        {loc:>10}  {s:5s}  {txt}")

    print("\n== summary ==")
    print(f"  failures: {failures if failures else 'none'}")
    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        print(f"  wrote {args.json}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
