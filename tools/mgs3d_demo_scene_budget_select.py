#!/usr/bin/env python3
"""Select a maximum practical natural-translation subset per fixed demo scene."""

from __future__ import annotations
import argparse, csv, json, sys
from pathlib import Path
from PIL import ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mgs3d_demo_scene_compact import scene_bounds, scene_starts, trailing_pad_run, walk_blocks  # noqa:E402
from mgs3d_movie_tool import load_static_character_map, parse_records, read_replacements, rebuild_record_fixed_reclaim  # noqa:E402

def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("source",type=Path); p.add_argument("translation",type=Path); p.add_argument("font",type=Path); p.add_argument("allocation",type=Path); p.add_argument("output",type=Path); p.add_argument("review",type=Path); p.add_argument("report",type=Path); p.add_argument("--font-size",type=int,default=15); a=p.parse_args()
    data=a.source.read_bytes(); _,records,_=parse_records(data); replacements=read_replacements(a.translation)
    static=load_static_character_map(a.allocation); font=ImageFont.truetype(str(a.font),a.font_size)
    starts=scene_starts(data,walk_blocks(data)); bounds=scene_bounds(starts,len(data))
    record_scene={r.index:next(i for i,(s,e) in enumerate(bounds) if s<=r.offset<e) for r in records}
    selected={r.index:{s.offset:replacements[s.offset] for s in r.subtitles if s.offset in replacements} for r in records}
    cache={}
    def growth(record,local):
        key=(record.index,tuple(local.items()))
        if key not in cache: cache[key]=len(rebuild_record_fixed_reclaim(record,local,font,static_map=static)[0])-len(record.raw)
        return cache[key]
    dropped=[]; scene_rows=[]
    by_scene={i:[r for r in records if record_scene[r.index]==i] for i in range(len(bounds))}
    for scene,(s,e) in enumerate(bounds):
        budget=trailing_pad_run(data,e); owned=by_scene[scene]
        total=sum(growth(r,selected[r.index]) for r in owned)
        while total>budget:
            choices=[]
            for r in owned:
                local=selected[r.index]
                for offset,text in local.items():
                    trial=dict(local); del trial[offset]
                    saving=growth(r,local)-growth(r,trial)
                    # Prefer the largest structural saving, then longer text,
                    # while keeping deterministic record/offset ordering.
                    choices.append((saving,len(text),-r.index,-offset,r,offset,text,trial))
            if not choices: raise ValueError(f"scene {scene} cannot fit even with no selected rows")
            saving,_,_,_,r,offset,text,trial=max(choices)
            if saving<=0:
                # Remove a zero-marginal row so shared glyph ownership can
                # eventually collapse when its last user is removed.
                pass
            selected[r.index]=trial; dropped.append((scene,r.index,offset,text)); total=sum(growth(x,selected[x.index]) for x in owned)
        scene_rows.append({"scene":scene,"start":s,"end":e,"budget":budget,"growth":total,"headroom":budget-total,"selected":sum(len(selected[r.index]) for r in owned),"dropped":sum(1 for x in dropped if x[0]==scene)})
    chosen={offset for local in selected.values() for offset in local}
    with a.translation.open(encoding="utf-8-sig",newline="") as f: rd=csv.DictReader(f); rows=list(rd); fields=list(rd.fieldnames or [])
    review=[]
    for row in rows:
        if int(row["offset"]) not in chosen:
            row["accept"]="no"
            review.append(row.copy())
    for path,items in ((a.output,rows),(a.review,review)):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",encoding="utf-8-sig",newline="") as f: wr=csv.DictWriter(f,fieldnames=fields); wr.writeheader(); wr.writerows(items)
    report={"format":"mgs3d-demo-scene-budget-selection-v1","source":str(a.source),"total_rows":len(replacements),"selected_rows":len(chosen),"dropped_rows":len(dropped),"all_scene_starts_required_unchanged":True,"scenes":scene_rows}
    a.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); print(f"selected={len(chosen)}/{len(replacements)} dropped={len(dropped)} scenes={len(starts)}")
    return 0
if __name__=="__main__": raise SystemExit(main())
