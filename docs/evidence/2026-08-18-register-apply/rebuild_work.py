# -*- coding: utf-8 -*-
"""Rebuild _register_work.json from the (re-run) actionable CSV.

Needed after the POLITE regex fix: `ㅂ니다` written as a bare jamo can never
match composed Hangul, so `-겁니다`/`-줍니다` rows were mis-scored.
"""
import csv, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
ROOT = Path("D:/dev/3dsmetal")
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec

P = ROOT / "translation/10_master/review/full-qa-final"
STAGED = ROOT / "builds/v0.89-round5/dist/0004000000081E00/romfs/codec.dat"

def load(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

act = load(ROOT / "output/speaker-register-actionable/codec-register-actionable.csv")
prop = {(r["gcx"], r["resource"]): r for r in load(P / "codec-final-revision-proposals.csv")}

staged = parse_codec(STAGED.read_bytes())
head = {}
for g, rec in enumerate(staged):
    try:
        region = rec.font_data_offset - rec.string_resources_offset
        used = sum(len(r.data) for r in rec.resources())
        head[g] = region - used
    except Exception:
        head[g] = 0

rows = []
for a in act:
    k = (a["gcx"], a["resource"])
    pr = prop.get(k)
    rows.append({
        "gcx": a["gcx"], "resource": a["resource"], "speaker": a["speaker"],
        "expected": a["expected_register"], "observed": a["observed_register"],
        "english": a["english"], "korean": a["korean"],
        "proposal": (pr or {}).get("final_korean", ""),
        "issue_type": (pr or {}).get("issue_type", ""),
        "reason": (pr or {}).get("final_reason", ""),
        "prior": a["prior_verdict"], "headroom": head.get(int(a["gcx"]), 0),
    })

old = {f'{w["gcx"]}:{w["resource"]}': w for w in
       json.loads((P / "_register_work.json").read_text(encoding="utf-8"))}
new = {f'{r["gcx"]}:{r["resource"]}': r for r in rows}
dropped = sorted(set(old) - set(new))
added = sorted(set(new) - set(old))
print(f"old={len(old)} new={len(new)} dropped={len(dropped)} added={len(added)}")

(P / "_register_work.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
(Path(__file__).with_name("_delta.json")).write_text(
    json.dumps({"dropped": dropped, "added": added}, ensure_ascii=False, indent=1),
    encoding="utf-8")
