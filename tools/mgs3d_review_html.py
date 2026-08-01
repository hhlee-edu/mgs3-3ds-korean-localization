#!/usr/bin/env python3
"""Create a self-contained offline HTML reviewer for MGS3D translation CSVs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


def load_table(path: Path, kind: str) -> dict[str, object]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames or []
    return {"name": kind, "file": path.name, "fields": fields, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--codec", type=Path)
    args = parser.parse_args()
    tables = [load_table(path, kind) for kind, path in (
        ("movie", args.movie), ("demo", args.demo), ("codec", args.codec)
    ) if path]
    if not tables:
        parser.error("provide at least one of --movie, --demo, or --codec")
    payload = json.dumps(tables, ensure_ascii=False).replace("</", "<\\/")
    title = "MGS3D Korean Translation Review"
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#11151b;--panel:#1b222c;--line:#364251;--text:#e8edf3;--muted:#9ba9b8;--good:#75d69c;--warn:#ffd166}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:2;background:#11151bf2;border-bottom:1px solid var(--line);padding:12px 18px}}
h1{{font-size:18px;margin:0 0 10px}} .controls{{display:flex;gap:8px;flex-wrap:wrap}}
select,input,button{{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:5px;padding:7px 9px}}
input[type=search]{{min-width:300px;flex:1}} button{{cursor:pointer}} button.primary{{border-color:#40916c;color:var(--good)}}
#stats{{color:var(--muted);margin-top:8px}} main{{padding:12px 18px 40px}} .row{{display:grid;grid-template-columns:52px 96px 1fr 1fr;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:10px;margin:8px 0}}
.meta{{color:var(--muted);font-size:12px}} .jp,.ko{{white-space:pre-wrap;overflow-wrap:anywhere}} .ko textarea{{width:100%;min-height:76px;background:#111820;color:var(--text);border:1px solid var(--line);padding:7px}}
.english{{grid-column:3/5;color:#b9c7d5}} .context{{grid-column:3/5;color:#d8c99b;white-space:pre-wrap;font-family:ui-monospace,monospace}} .accepted{{border-color:#40916c}} .blank{{color:var(--warn)}}
.group{{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:14px;margin:10px 0}} .group.accepted{{border-color:#40916c}} .group h2{{font-size:16px;margin:0 0 8px}} .group-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} .group textarea{{width:100%;min-height:150px;background:#111820;color:var(--text);border:1px solid var(--line);padding:9px}} .resources{{max-height:420px;overflow:auto;white-space:pre-wrap;background:#111820;border:1px solid var(--line);padding:9px;font-family:ui-monospace,monospace}}
@media(max-width:850px){{.row{{grid-template-columns:48px 1fr}} .jp,.ko,.english,.context{{grid-column:1/3}}}}
</style></head><body><header><h1>{html.escape(title)}</h1><div class="controls">
<select id="table"></select><select id="confidence"><option value="">모든 신뢰도</option></select>
<select id="conversation"><option value="">모든 대화 묶음</option></select>
<select id="state"><option value="">모든 상태</option><option value="accepted">승인됨</option><option value="pending">미승인</option><option value="blank">번역 없음</option></select>
<input id="query" type="search" placeholder="한국어 / 영어 / 일본어 / GCX 검색">
<button id="viewmode">행 보기</button><button id="visible">보이는 항목 전부 승인</button><button class="primary" id="download">현재 표 CSV 저장</button></div><div id="stats"></div></header>
<main id="list"></main><script>
const tables={payload}; let active=0,groupMode=!!tables[0]?.rows.some(r=>r.group_start!==undefined); const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function conf(r){{return r.dat_confidence||r.confidence||''}} function accepted(r){{return /^(y|yes|1|ok|true|o)$/i.test((r.accept||'').trim())}}
function korean(r){{return r.korean||''}} function searchText(r){{return Object.values(r).join(' ').toLowerCase()}}
function filtered(){{const q=$('#query').value.toLowerCase(),c=$('#confidence').value,v=$('#conversation').value,s=$('#state').value;return tables[active].rows.filter(r=>(!q||searchText(r).includes(q))&&(!c||conf(r)===c)&&(!v||(r.conversation_key||'')===v)&&(!s||(s==='accepted'&&accepted(r))||(s==='pending'&&!accepted(r)&&korean(r))||(s==='blank'&&!korean(r))))}}
function splitGroup(rows,text){{const words=text.trim().split(/\\s+/).filter(Boolean),weights=rows.map(r=>Math.max(1,(r.game_preview||r.japanese_preview||'').replace(/<[^>]+>/g,'').length)),total=weights.reduce((a,b)=>a+b,0);let used=0,start=0;rows.forEach((r,i)=>{{used+=weights[i];const end=i===rows.length-1?words.length:Math.max(start,Math.min(words.length,Math.round(used/total*words.length)));r.korean=words.slice(start,end).join(' ');r.korean_full=text;start=end}})}}
function renderGroups(rows,all,list){{const groups=new Map;rows.forEach(r=>{{const key=r.conversation_key||`single-${{all.indexOf(r)}}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r)}});for(const [key,group] of groups){{const box=document.createElement('article'),blocked=group.some(r=>(r.contradictions||'').trim()),done=group.every(accepted),full=group.find(r=>r.korean_full)?.korean_full||group.map(korean).join(' '),english=group.find(r=>r.english)?.english||'',resources=group.map(r=>`${{r.resource}}: ${{r.game_preview||r.japanese_preview||''}}`).join('\\n\\n');box.className='group'+(done?' accepted':'');box.innerHTML=`<h2><label><input type="checkbox" data-g="${{esc(key)}}" ${{done?'checked':''}} ${{blocked?'disabled':''}}> ${{blocked?'충돌 — 승인 불가':'대화 묶음 전체 승인'}}</label> · ${{esc(key)}} · ${{group.length}}행</h2><div class="group-grid"><div><div class="meta">영어 전체 문단</div><div class="english">${{esc(english)}}</div><div class="meta">한국어 전체 문단 — 여기서 수정하면 저장용 행에 자동 재분할</div><textarea data-full="${{esc(key)}}">${{esc(full)}}</textarea>${{blocked?`<div class="context">⚠ ${{esc([...new Set(group.map(r=>r.contradictions).filter(Boolean))].join('; '))}}</div>`:''}}</div><div><div class="meta">게임 리소스 연속 목록</div><div class="resources">${{esc(resources)}}</div></div></div>`;list.appendChild(box)}}}}
function render(){{const rows=filtered(),all=tables[active].rows;$('#stats').textContent=`표 ${{tables[active].name}} · 표시 ${{rows.length}} / ${{all.length}} · 전체 승인 ${{all.filter(accepted).length}} · 번역 후보 ${{all.filter(r=>korean(r)).length}}`;const list=$('#list');list.innerHTML='';if(groupMode&&rows.some(r=>r.conversation_key)){{renderGroups(rows,all,list);return}}rows.forEach(r=>{{const index=all.indexOf(r),box=document.createElement('article');box.className='row'+(accepted(r)?' accepted':'');const target=r.gcx!==undefined?`GCX ${{r.gcx}} / ${{r.resource}}`:`record ${{r.record??'-'}} / entry ${{r.entry??'-'}}`;const blocked=!!(r.contradictions||'').trim();box.innerHTML=`<label><input type="checkbox" data-i="${{index}}" ${{accepted(r)?'checked':''}} ${{blocked?'disabled':''}}> ${{blocked?'충돌':'승인'}}</label><div class="meta">${{esc(target)}}<br>${{esc(conf(r))}} / ${{esc(r.bilingual_confidence||'')}}<br>${{esc(r.conversation_key||'')}}<br>offset ${{esc(r.offset||'')}}</div><div class="jp">${{esc(r.japanese_preview||r.game_preview||'')}}</div><div class="ko ${{korean(r)?'':'blank'}}"><textarea data-k="${{index}}">${{esc(korean(r))}}</textarea></div><div class="english">${{esc(r.english||'')}}</div>${{r.contradictions?`<div class="context">⚠ ${{esc(r.contradictions)}}</div>`:''}}`;list.appendChild(box)}})}}
function refreshFilters(){{const rows=tables[active].rows,values=[...new Set(rows.map(conf).filter(Boolean))].sort(),groups=[...new Set(rows.map(r=>r.conversation_key||'').filter(Boolean))].sort();$('#confidence').innerHTML='<option value="">모든 신뢰도</option>'+values.map(x=>`<option>${{esc(x)}}</option>`).join('');$('#conversation').innerHTML='<option value="">모든 대화 묶음</option>'+groups.map(x=>`<option>${{esc(x)}}</option>`).join('')}}
tables.forEach((t,i)=>$('#table').insertAdjacentHTML('beforeend',`<option value="${{i}}">${{esc(t.name)}} (${{t.rows.length}})</option>`));$('#viewmode').textContent=groupMode?'행 보기':'묶음 보기';refreshFilters();render();
$('#table').onchange=e=>{{active=+e.target.value;refreshFilters();render()}};['confidence','conversation','state','query'].forEach(id=>$('#'+id).oninput=render);
$('#list').onchange=e=>{{if(e.target.matches('[data-i]')){{tables[active].rows[+e.target.dataset.i].accept=e.target.checked?'yes':'';render()}}}};
$('#list').onchange=e=>{{if(e.target.matches('[data-g]')){{const key=e.target.dataset.g;tables[active].rows.filter(r=>(r.conversation_key||'')===key&&!(r.contradictions||'').trim()).forEach(r=>r.accept=e.target.checked?'yes':'');render()}}}};
$('#list').oninput=e=>{{if(e.target.matches('[data-k]'))tables[active].rows[+e.target.dataset.k].korean=e.target.value;if(e.target.matches('[data-full]'))splitGroup(tables[active].rows.filter(r=>(r.conversation_key||'')===e.target.dataset.full),e.target.value)}};
$('#viewmode').onclick=()=>{{groupMode=!groupMode;$('#viewmode').textContent=groupMode?'행 보기':'묶음 보기';render()}};
$('#visible').onclick=()=>{{filtered().forEach(r=>{{if(korean(r)&&!(r.contradictions||'').trim())r.accept='yes'}});render()}};
function csvCell(v){{v=String(v??'');return /[",\\r\\n]/.test(v)?'"'+v.replaceAll('"','""')+'"':v}}
$('#download').onclick=()=>{{const t=tables[active],lines=[t.fields.map(csvCell).join(',')];t.rows.forEach(r=>lines.push(t.fields.map(f=>csvCell(r[f])).join(',')));const blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{{type:'text/csv;charset=utf-8'}}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=t.file.replace(/\\.csv$/,'_reviewed.csv');a.click();URL.revokeObjectURL(a.href)}};
</script></body></html>'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"wrote offline reviewer with {sum(len(t['rows']) for t in tables)} rows: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
