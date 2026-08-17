# -*- coding: utf-8 -*-
"""Write the verified register rewrites into translation/10_master/current/codec.csv.

Every row is re-checked against the CURRENT master text (not the QA proposal
that some rows were drafted on top of): glyph coverage, control-token identity,
and per-record byte-fit with the string propagated to all of its `locations`.
"""
import csv, json, sys, shutil, collections
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
ROOT = Path("D:/dev/3dsmetal")
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_qa_final_verify import load_character_map, verify, verify_record
from mgs3d_codec_tool import parse_codec

P = ROOT / "translation/10_master/review/full-qa-final"
MASTER = ROOT / "translation/10_master/current/codec.csv"
BACKUP = ROOT / "translation/10_master/current/codec.csv.bak-register-2026-08-18"
STAGED = ROOT / "builds/v0.89-round5/dist/0004000000081E00/romfs/codec.dat"

res = [r for r in json.loads((P / "_register_applied.json").read_text(encoding="utf-8"))
       if r["outcome"] == "PASS"]
with open(MASTER, encoding="utf-8-sig", newline="") as f:
    rdr = csv.DictReader(f)
    fields = rdr.fieldnames
    master = list(rdr)
canon = {(m["gcx"], m["resource"]): i for i, m in enumerate(master)}

cm = load_character_map()
plan, rejected = {}, []
for r in res:
    i = canon[(r["gcx"], r["resource"])]
    old = master[i]["korean"]
    new = r["new_korean"]
    if new == old:
        rejected.append((r["gcx"], r["resource"], "no-op vs master")); continue
    v = verify(old, new, cm)                       # vs master, not vs proposal
    if v.missing:
        rejected.append((r["gcx"], r["resource"], "new glyph: " + "".join(v.missing))); continue
    if v.control_code != "PASS":
        rejected.append((r["gcx"], r["resource"], "control-code drift")); continue
    plan[i] = new

by_gcx = collections.defaultdict(dict)
for i, new in plan.items():
    locs = [l.strip() for l in (master[i]["locations"] or "").split(";") if l.strip()] \
        or [f'{master[i]["gcx"]}:{master[i]["resource"]}']
    for l in locs:
        g, rr = l.split(":")
        by_gcx[int(g)][int(rr)] = new

staged = parse_codec(STAGED.read_bytes())
bad = [(g, verify_record(staged[g], ch, cm)[1])
       for g, ch in sorted(by_gcx.items()) if not verify_record(staged[g], ch, cm)[0]]

print(f"PASS rows {len(res)}  applying {len(plan)}  rejected {len(rejected)}  bad records {len(bad)}")
for x in rejected[:20]: print("  REJ", x)
for x in bad[:20]: print("  BAD", x)
if bad or "--dry-run" in sys.argv:
    print("dry run / not applied"); raise SystemExit(1 if bad else 0)

if not BACKUP.exists():
    shutil.copy2(MASTER, BACKUP)
    print("backup:", BACKUP)
for i, new in plan.items():
    master[i]["korean"] = new
    master[i]["missing_count"] = "0"
    master[i]["missing_glyphs"] = ""
with open(MASTER, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(master)
print(f"master updated: {len(plan)} rows, {sum(len(c) for c in by_gcx.values())} locations, {len(by_gcx)} records")
