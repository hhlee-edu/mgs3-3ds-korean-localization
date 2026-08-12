#!/usr/bin/env python3
"""Apply reviewed Korean overrides by stable media record/entry identity."""

from __future__ import annotations
import argparse, csv
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path); p.add_argument("overrides",type=Path); p.add_argument("output",type=Path)
    a=p.parse_args()
    with a.source.open(encoding="utf-8-sig",newline="") as f:
        rd=csv.DictReader(f); rows=list(rd); fields=list(rd.fieldnames or [])
    with a.overrides.open(encoding="utf-8-sig",newline="") as f:
        changes={}
        for r in csv.DictReader(f):
            # Tolerate unquoted dialogue commas by joining overflow fields.
            value=r["korean"]
            if r.get(None): value += "," + ",".join(r[None])
            changes[(r["record"],r["entry"])]=value
    found=set()
    for row in rows:
        key=(row["record"],row["entry"])
        if key in changes: row["korean"]=changes[key]; found.add(key)
    missing=set(changes)-found
    if missing: raise ValueError(f"missing overrides: {sorted(missing)[:10]}")
    with a.output.open("w",encoding="utf-8-sig",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=fields); wr.writeheader(); wr.writerows(rows)
    print(f"applied={len(found)}")
    return 0
if __name__=="__main__": raise SystemExit(main())
