# -*- coding: utf-8 -*-
"""Map the verified register rewrites onto master rows and re-verify byte-fit
across EVERY location the row occupies, not just the canonical one."""
import csv, json, sys, collections
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
ROOT = Path("D:/dev/3dsmetal")
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_qa_final_verify import load_character_map, verify_record
from mgs3d_codec_tool import parse_codec

P = ROOT / "translation/10_master/review/full-qa-final"
MASTER = ROOT / "translation/10_master/current/codec.csv"
STAGED = ROOT / "builds/v0.89-round5/dist/0004000000081E00/romfs/codec.dat"

res = [r for r in json.loads((P / "_register_applied.json").read_text(encoding="utf-8"))
       if r["outcome"] == "PASS"]
with open(MASTER, encoding="utf-8-sig", newline="") as f:
    master = list(csv.DictReader(f))

canon = {(m["gcx"], m["resource"]): i for i, m in enumerate(master)}
loc_index = collections.defaultdict(list)
for i, m in enumerate(master):
    for loc in (m["locations"] or "").split(";"):
        loc = loc.strip()
        if loc:
            loc_index[loc].append(i)

missing, mismatch, plan = [], [], {}
for r in res:
    k = (r["gcx"], r["resource"])
    i = canon.get(k)
    if i is None:
        missing.append(f'{k[0]}:{k[1]}'); continue
    if master[i]["korean"] != r["korean"]:
        mismatch.append((f'{k[0]}:{k[1]}', master[i]["korean"], r["korean"]))
    plan[i] = r["new_korean"]

print(f"PASS rows {len(res)}  mapped {len(plan)}  not-canonical {len(missing)}  master-text-mismatch {len(mismatch)}")
for x in missing[:20]: print("  MISS", x)
for a, b, c in mismatch[:10]: print("  DIFF", a, "\n    master:", b, "\n    work  :", c)

# every location of every touched row
by_gcx = collections.defaultdict(dict)
locs_total = 0
shared = []
for i, new in plan.items():
    locs = [l.strip() for l in (master[i]["locations"] or "").split(";") if l.strip()]
    if not locs:
        locs = [f'{master[i]["gcx"]}:{master[i]["resource"]}']
    for l in locs:
        g, rr = l.split(":")
        if int(rr) in by_gcx[int(g)] and by_gcx[int(g)][int(rr)] != new:
            shared.append(l)
        by_gcx[int(g)][int(rr)] = new
        locs_total += 1
print(f"locations touched {locs_total} across {len(by_gcx)} records; conflicting {len(shared)}")

staged = parse_codec(STAGED.read_bytes())
cm = load_character_map()
bad = []
for g, ch in sorted(by_gcx.items()):
    ok, detail = verify_record(staged[g], ch, cm)
    if not ok:
        bad.append((g, detail))
print(f"records failing byte-fit with full propagation: {len(bad)}")
for g, d in bad[:40]: print("  ", g, d)
json.dump({str(i): v for i, v in plan.items()},
          (Path(__file__).with_name("_plan.json")).open("w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
