# -*- coding: utf-8 -*-
"""Apply scoped per-row register rewrites and verify them the way a
`safe-fixed` build would: rebuild each touched GCX record under
preserve-layout, and check glyph coverage and control-token identity.

Edits are (find, replace) pairs scoped to one row. Expressing them this way
means the row's <0A>/<00>/icon tokens survive by construction -- nothing
rewrites the token layout, only the text between tokens.
"""
import csv, json, sys, importlib.util, collections, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
ROOT = Path("D:/dev/3dsmetal")
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_qa_final_verify import load_character_map, verify, verify_record
from mgs3d_codec_tool import parse_codec

P = ROOT / "translation/10_master/review/full-qa-final"
STAGED = ROOT / "builds/v0.89-round5/dist/0004000000081E00/romfs/codec.dat"

spec = importlib.util.spec_from_file_location("q", ROOT / "tools/mgs3d_confirmed_register_qa.py")
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)

def load_props(d):
    props = {}
    for f in sorted(Path(d).glob("reg_*.json")):
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            if k in props: raise SystemExit(f"duplicate {k} in {f}")
            props[k] = v
    # fix_*.json intentionally overrides, so corrections go in a new file
    # instead of rewriting a batch file (which costs a full re-read).
    for f in sorted(Path(d).glob("fix_*.json")):
        props.update(json.loads(f.read_text(encoding="utf-8")))
    for f in sorted(Path(d).glob("reg_*.py")):
        s = importlib.util.spec_from_file_location(f.stem, f)
        m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
        for k, v in m.P.items():
            if k in props: raise SystemExit(f"duplicate {k} in {f}")
            props[k] = v
    return props

work = {f'{r["gcx"]}:{r["resource"]}': r for r in json.loads((P/"_register_work.json").read_text(encoding="utf-8"))}
cm = load_character_map()
props = load_props(sys.argv[1] if len(sys.argv) > 1 else ".")
print(f"proposals: {len(props)} / work rows: {len(work)}")

results, errors, skipped = [], [], []
by_gcx = collections.defaultdict(dict)
for key, spec_ in props.items():
    w = work.get(key)
    if w is None:
        # Row dropped from the work set by the classifier fix: it was already in
        # the right register, so the authored rewrite is unnecessary churn.
        skipped.append(key); continue
    if isinstance(spec_, dict) and spec_.get("verdict") == "HUMAN":
        results.append({**w, "new_korean": "", "outcome": "HUMAN",
                        "note": spec_.get("reason", "")}); continue
    base = w["proposal"] or w["korean"]          # keep earlier semantic fixes
    new = base
    for find, repl in spec_["edits"]:
        if find not in new:
            errors.append((key, f"find absent: {find!r}")); new = None; break
        if new.count(find) > 1:
            errors.append((key, f"find ambiguous x{new.count(find)}: {find!r}")); new = None; break
        new = new.replace(find, repl)
    if new is None: continue
    if new == w["korean"]:
        errors.append((key, "no-op vs master")); continue
    reg = q.classify_register(new)
    if reg != w["expected"] and reg not in ("unknown",):
        errors.append((key, f"still {reg}, expected {w['expected']}")); continue
    v = verify(w["korean"], new, cm)
    results.append({**w, "new_korean": new, "outcome": "PENDING",
                    "register_now": reg,
                    "new_glyph": v.new_glyph if not v.missing else "FAIL:" + "".join(v.missing),
                    "control_code": v.control_code, "note": spec_.get("reason", "")})
    by_gcx[int(w["gcx"])][int(w["resource"])] = new

staged = parse_codec(STAGED.read_bytes())
fit = {}
for g, ch in by_gcx.items():
    ok, detail = verify_record(staged[g], ch, cm)
    fit[str(g)] = (ok, detail)
for r in results:
    if r["outcome"] != "PENDING": continue
    ok, detail = fit[r["gcx"]]
    r["byte_fit"] = detail
    r["outcome"] = "PASS" if (ok and r["new_glyph"] == "PASS" and r["control_code"] == "PASS") else "FAIL"

pas = [r for r in results if r["outcome"] == "PASS"]
fail = [r for r in results if r["outcome"] == "FAIL"]
hum = [r for r in results if r["outcome"] == "HUMAN"]
print(f"PASS {len(pas)}  FAIL {len(fail)}  HUMAN {len(hum)}  errors {len(errors)}  skipped(already-correct) {len(skipped)}")
for k, e in errors[:30]: print("  ERR ", k, e)
seen = set()
for r in fail[:40]:
    tag = (r["gcx"], "byte" if "FAIL" in r.get("byte_fit", "") else "other")
    if tag in seen: continue
    seen.add(tag)
    print(f"  FAIL {r['gcx']}:{r['resource']} byte={r.get('byte_fit','')[:64]} glyph={r['new_glyph']} ctrl={r['control_code']}")
json.dump(results, (P/"_register_applied.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
