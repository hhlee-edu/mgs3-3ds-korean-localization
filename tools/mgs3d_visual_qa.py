#!/usr/bin/env python3
"""Generate the read-only MGS3D visual QA page from live shipping inputs."""
from __future__ import annotations
import argparse, base64, csv, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'tools'))
from mgs3d_codec_tool import decode_mgs_preview, parse_codec, parse_rendered, render_bytes
from mgs3d_movie_tool import parse_records
from mgs3d_gcx_font_tool import decode_glyph
INPUT=ROOT/'translation/40_build_input/global_page_v2'; ROM=ROOT/'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs'; PAGE=ROOT/'glyph/pages/global_korean_page_v2/korean_page_full.bin'
def b64(x): return base64.b64encode(x).decode('ascii')
class QA:
 def __init__(self,page,cmap): self.page=page; self.cmap=cmap; self.reverse={v:c for c,v in cmap.items()}; self.glyphs={}; self.rows=[]; self.counts={'codec':0,'movie':0,'demo':0}
 def glyph(self,key,data):
  if len(data)==64:self.glyphs.setdefault(key,b64(bytes(decode_glyph(data,'linear').tobytes())))
 def tokens(self,data,local,prefix):
  out=[]; warnings=[]; i=0
  while i<len(data):
   a=data[i]
   if a==0:out.append({'control':'00'});i+=1;continue
   if a<128:
    if 32<=a<=126:out.append({'raw':a,'char':chr(a),'source':'fixed'})
    else:out.append({'control':f'{a:02X}'});warnings.append('unknown-control')
    i+=1;continue
   if i+1>=len(data):out.append({'control':f'{a:02X}','invalid':True});warnings.append('invalid-token');break
   raw=(a<<8)|data[i+1]
   if raw==0x807c:out.append({'control':'0A'});i+=2;continue
   tok=raw.to_bytes(2,'big'); idx=None; source=None
   if 0x8401<=raw<=0x87ff and raw&255:
    rel=raw-0x8401;idx=rel-rel//255;source='global'
    if idx is not None:self.glyph(f'global:{idx}',self.page[idx*64:(idx+1)*64])
   elif 0x8c01<=raw<0x9400 and raw&255 and local is not None:
    rel=raw-(0x8c01 if raw<0x9000 else 0x9001);idx=rel-rel//255;source='fixed'
    if 0<=idx<len(local)//64:self.glyph(f'{prefix}:{idx}',local[idx*64:(idx+1)*64])
   char=self.reverse.get(tok,'')
   if idx is None or source=='fixed' and (local is None or idx>=len(local)//64):out.append({'raw':raw,'char':char,'source':'missing','invalid':True});warnings.append('missing' if char else 'invalid-token')
   else:out.append({'raw':raw,'char':char,'source':source,'glyph_index':idx,'glyph_key':f'global:{idx}' if source=='global' else f'{prefix}:{idx}'})
   i+=2
  return out,sorted(set(warnings))
 def add(self,typ,gcx,res,off,eng,ko,data,local,prefix):
  ts,ws=self.tokens(data,local,prefix);self.rows.append({'type':typ,'gcx':gcx,'resource':res,'offset':str(off),'english':eng,'korean':ko,'tokens':ts,'warnings':ws});self.counts[typ]+=1
 def codec(self):
  doc=json.loads((INPUT/'codec_natural_full_global_page.json').read_text(encoding='utf-8-sig')); tr={(int(x['gcx']),int(x['resource'])):x for x in doc['units']}
  records=parse_codec((ROM/'codec.dat').read_bytes())
  for (gi,ri),item in tr.items():
   if gi<0 or gi>=len(records): continue
   r=records[gi]; resources=r.resources()
   if ri<0 or ri>=len(resources): continue
   x=resources[ri]; fs=r.block_start+r.font_data_offset+4; local=r.raw[fs:r.block_start+r.proc_offset]
   eng=render_bytes(x.data);ko=str(item.get('text',''));raw=parse_rendered(ko,self.cmap) if ko else x.data;self.add('codec',gi,ri,f'0x{r.source_offset:X}',eng,ko,raw,local,f'c{gi}')
 def media(self,typ):
  tr={}
  with (INPUT/f'{typ}_natural_full_global_page.csv').open(encoding='utf-8-sig',newline='') as f:
   for x in csv.DictReader(f):tr[int(x['offset'])]=x
  _,records,_=parse_records((ROM/f'{typ}.dat').read_bytes())
  for r in records:
   for ei,s in enumerate(r.subtitles):
    x=tr.get(s.offset,{});ko=x.get('korean','');raw=s.raw
    if ko:
     try:raw=parse_rendered(ko,self.cmap)
     except Exception:pass
    self.add(typ,r.index,ei,s.offset,decode_mgs_preview(s.raw),ko,raw,r.font,f'{typ[0]}{r.index}')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'output/mgs3d_visual_qa.html');a=ap.parse_args();d=json.loads((INPUT/'character-map.json').read_text(encoding='utf-8-sig'));c={k:bytes.fromhex(v) for k,v in d.get('characters',d.get('character_map',{})).items()};q=QA(PAGE.read_bytes(),c);q.codec();q.media('movie');q.media('demo');t=(ROOT/'tools/visual_qa/template.html').read_text(encoding='utf-8');out=t.replace('__STYLE__',(ROOT/'tools/visual_qa/style.css').read_text(encoding='utf-8')).replace('__APP__',(ROOT/'tools/visual_qa/app.js').read_text(encoding='utf-8')).replace('__DATA__',json.dumps({'rows':q.rows,'glyphs':q.glyphs,'counts':q.counts},ensure_ascii=False,separators=(',',':')));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(out,encoding='utf-8');print(json.dumps({'output':str(a.output),'rows':len(q.rows),'counts':q.counts},ensure_ascii=False))
if __name__=='__main__':main()
