#!/usr/bin/env python3
"""Verify a natural media grow without requiring absolute record/scene offsets."""

from __future__ import annotations
import argparse, csv, hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_demo_scene_compact import scene_starts, walk_blocks  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402

def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind",choices=("movie","demo")); p.add_argument("source",type=Path)
    p.add_argument("built",type=Path); p.add_argument("translation",type=Path); p.add_argument("report",type=Path)
    a=p.parse_args(); old=a.source.read_bytes(); new=a.built.read_bytes()
    _,ors,_=parse_records(old); _,nrs,_=parse_records(new)
    with a.translation.open(encoding="utf-8-sig",newline="") as f:
        targets={(int(r["record"]),int(r["entry"])) for r in csv.DictReader(f)
                 if r.get("accept","").lower() in {"yes","y","1","true","ok","o"} and r.get("korean","").strip()}
    failures=[]; donor_changed=[]; untouched_changed=[]; relayout=[]
    if len(ors)!=len(nrs): failures.append(f"record count {len(ors)} -> {len(nrs)}")
    for ro,rn in zip(ors,nrs):
        if len(ro.subtitles)!=len(rn.subtitles): failures.append(f"record {ro.index} subtitle count changed"); continue
        for index,(so,sn) in enumerate(zip(ro.subtitles,rn.subtitles)):
            if so.entry_type!=sn.entry_type: failures.append(f"record {ro.index} entry {index} type changed")
            key=(ro.index,index)
            if so.entry_type in {2,3,4,5} and so.raw!=sn.raw: donor_changed.append(key)
            if key not in targets and so.raw!=sn.raw: untouched_changed.append(key)
            if (so.offset-ro.offset)!=(sn.offset-rn.offset): relayout.append(key)
    if donor_changed: failures.append(f"donor content changed: {len(donor_changed)}")
    if untouched_changed: failures.append(f"untouched subtitle content changed: {len(untouched_changed)}")
    scenes=None
    if a.kind=="demo":
        os=scene_starts(old,walk_blocks(old)); ns=scene_starts(new,walk_blocks(new)); scenes={"count":len(os),"shifted":sum(x!=y for x,y in zip(os,ns)),"max_delta":max((y-x for x,y in zip(os,ns)),default=0)}
        if len(os)!=len(ns): failures.append(f"scene count {len(os)} -> {len(ns)}")
        if scenes["shifted"]:
            failures.append(
                f"demo scene starts shifted: {scenes['shifted']} (runtime-unsafe; first-demo stall confirmed)"
            )
    report={"format":"mgs3d-media-natural-grow-verify-v1","kind":a.kind,
            "source_sha256":sha(old),"built_sha256":sha(new),"size_delta":len(new)-len(old),
            "record_count":len(ors),"target_rows":len(targets),"relative_subtitle_offsets_changed":len(relayout),
            "donor_changed":len(donor_changed),"untouched_changed":len(untouched_changed),"scenes":scenes,
            "passed":not failures,"failures":failures,
            "runtime_status":("rejected" if failures else
                              "structure gate passed; runtime smoke still required")}
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2)); return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
