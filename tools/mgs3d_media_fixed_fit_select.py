#!/usr/bin/env python3
"""Disable translation rows that cannot fit their immutable subtitle slot."""
from __future__ import annotations
import argparse,csv,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mgs3d_movie_tool import encode_translation,load_static_character_map,parse_records,wrap_like_source  # noqa:E402
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("translation",type=Path);p.add_argument("allocation",type=Path);p.add_argument("output",type=Path);p.add_argument("review",type=Path);a=p.parse_args()
 _,records,_=parse_records(a.source.read_bytes()); subs={(r.index,i):s for r in records for i,s in enumerate(r.subtitles)}; static=load_static_character_map(a.allocation)
 with a.translation.open(encoding="utf-8-sig",newline="") as f:rd=csv.DictReader(f);rows=list(rd);fields=list(rd.fieldnames or [])
 rejected=[]
 for row in rows:
  if row.get("accept","").lower() not in {"yes","y","1","true","ok","o"}:continue
  sub=subs[(int(row["record"]),int(row["entry"]))]; text=row.get("korean",""); missing={c for c in text if ord(c)>=128 and c not in static}
  # Local glyph tokens are always two bytes, so a synthetic mapping suffices
  # for immutable text-capacity calculation.
  mapping=static|{c:b"\x90\x01" for c in missing}; need=len(encode_translation(wrap_like_source(text,sub.raw),mapping)); cap=len(sub.original)-4-len(sub.tail)
  if need>cap:
   row["accept"]="no"; rejected.append({**row,"needed_bytes":need,"capacity_bytes":cap,"deficit_bytes":need-cap})
 for path,items,fs in ((a.output,rows,fields),(a.review,rejected,fields+["needed_bytes","capacity_bytes","deficit_bytes"])):
  path.parent.mkdir(parents=True,exist_ok=True)
  with path.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fs);w.writeheader();w.writerows(items)
 print(f"fixed_fit={sum(r.get('accept','').lower() in {'yes','y','1','true','ok','o'} for r in rows)}/{len(rows)} rejected={len(rejected)}");return 0
if __name__=="__main__":raise SystemExit(main())
