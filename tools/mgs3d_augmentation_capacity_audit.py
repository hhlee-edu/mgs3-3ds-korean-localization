#!/usr/bin/env python3
"""Quantify savings from scene-shared glyphs and external subtitle strings."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mgs3d_demo_scene_compact import scene_bounds,scene_starts,walk_blocks  # noqa:E402
from mgs3d_movie_tool import load_static_character_map,parse_records,wrap_like_source  # noqa:E402
def units(text:str,source:bytes)->int:
 text=wrap_like_source(text,source);return 1+sum(2 if c=='\n' or ord(c)>=128 else 1 for c in text)
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path);p.add_argument("translation",type=Path);p.add_argument("allocation",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
 data=a.source.read_bytes();_,records,_=parse_records(data);starts=scene_starts(data,walk_blocks(data));bounds=scene_bounds(starts,len(data));static=set(load_static_character_map(a.allocation))
 with a.translation.open(encoding='utf-8-sig',newline='') as f:rows={(int(r['record']),int(r['entry'])):r['korean'] for r in csv.DictReader(f) if r.get('accept','').lower() in {'yes','y','1','true','ok','o'} and r.get('korean','')}
 scenes=[]; total_record=total_shared=external=overflow=0
 for si,(start,end) in enumerate(bounds):
  owned=[r for r in records if start<=r.offset<end]; record_sets=[]; scene_set=set(); scene_external=scene_overflow=0
  for r in owned:
   glyphs=set()
   for ei,s in enumerate(r.subtitles):
    text=rows.get((r.index,ei));
    if text is None:continue
    glyphs|={c for c in text if ord(c)>=128 and c not in static}; need=units(text,s.raw);cap=len(s.original)-4-len(s.tail);scene_external+=need;scene_overflow+=max(0,need-cap)
   record_sets.append(glyphs);scene_set|=glyphs
  record_slots=sum(map(len,record_sets));shared_slots=len(scene_set);total_record+=record_slots;total_shared+=shared_slots;external+=scene_external;overflow+=scene_overflow
  scenes.append({'scene':si,'record_local_slots':record_slots,'scene_shared_slots':shared_slots,'duplicate_slots_removed':record_slots-shared_slots,'duplicate_bytes_removed':(record_slots-shared_slots)*64,'external_encoded_bytes':scene_external,'immutable_string_overflow_bytes':scene_overflow})
 result={'format':'mgs3d-augmentation-capacity-audit-v1','rows':len(rows),'scenes':len(starts),'record_local_glyph_slots':total_record,'scene_shared_glyph_slots':total_shared,'scene_shared_duplicate_slots_removed':total_record-total_shared,'scene_shared_duplicate_bytes_removed':(total_record-total_shared)*64,'external_string_encoded_bytes':external,'immutable_string_overflow_bytes_removed_by_external_table':overflow,'scene_detail':scenes}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='scene_detail'},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
