#!/usr/bin/env python3
"""Build an offline codec compact-translation reviewer with live capacity checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, render_bytes  # noqa: E402
from mgs3d_codec_size_neutral_select import language_block_donors  # noqa: E402
from mgs3d_gcx_font_tool import font_region, freed_font_slots  # noqa: E402
from mgs3d_translation import validate_codec_translation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--initial", type=Path,
                        help="optional compact translation JSON whose text overrides matching rows")
    parser.add_argument("--capacity-report", type=Path,
                        help="existing selector report; avoids rescanning every language resource")
    parser.add_argument("--gcx", type=int, action="append", help="limit to selected GCX (repeatable)")
    args = parser.parse_args()

    records = parse_codec(args.codec.read_bytes())
    _, units = validate_codec_translation(json.loads(args.translation.read_text(encoding="utf-8")))
    initial: dict[tuple[int, int], str] = {}
    if args.initial:
        _, initial_units = validate_codec_translation(json.loads(args.initial.read_text(encoding="utf-8")))
        initial = {(int(unit["gcx"]), int(unit["resource"])): str(unit["text"])
                   for unit in initial_units}
        primary_keys = {(int(unit["gcx"]), int(unit["resource"])) for unit in units}
        units.extend(unit for unit in initial_units
                     if (int(unit["gcx"]), int(unit["resource"])) not in primary_keys)
    wanted = set(args.gcx or [])
    if wanted:
        units = [unit for unit in units if int(unit["gcx"]) in wanted]

    physical = []
    by_gcx: dict[int, list[dict[str, object]]] = {}
    resource_cache: dict[int, list[object]] = {}
    for unit in units:
        gcx, resource = int(unit["gcx"]), int(unit["resource"])
        if gcx not in resource_cache:
            resource_cache[gcx] = records[gcx].resources()
        source = resource_cache[gcx][resource]
        row = {
            "gcx": gcx, "resource": resource, "kind": "string",
            "original_size": len(source.data), "english": render_bytes(source.data),
            "full": str(unit["text"]), "text": initial.get((gcx, resource), str(unit["text"])),
            "enabled": True,
        }
        physical.append(row)
        by_gcx.setdefault(gcx, []).append(row)

    report_rows = {}
    if args.capacity_report:
        report_rows = {int(row["gcx"]): row for row in json.loads(
            args.capacity_report.read_text(encoding="utf-8"))["records"]}
    capacities = {}
    for gcx, rows in sorted(by_gcx.items()):
        record = records[gcx]
        resources = resource_cache[gcx]
        protected = {int(row["resource"]) for row in rows}
        if gcx in report_rows:
            donors = [int(index) for index in report_rows[gcx].get("donor_resources", [])]
            donor_savings = int(report_rows[gcx].get("donor_savings", 0))
        else:
            donors = language_block_donors(resources, protected)
            donor_savings = sum(max(0, len(resources[index].data) - 1) for index in donors)
        capacities[str(gcx)] = {
            "donor_savings": donor_savings,
            "donors": len(donors),
            "free_slots": len(freed_font_slots(record, set(donors))),
        }

    groups: dict[tuple[str, str], dict[str, object]] = {}
    for index, row in enumerate(physical):
        key = (str(row["english"]), str(row["full"]))
        group = groups.setdefault(key, {
            "id": len(groups) + 1, "english": row["english"], "full": row["full"],
            "text": row["text"], "enabled": True, "indices": [], "decision": "",
        })
        group["indices"].append(index)

    payload = json.dumps({
        "physical": physical, "groups": list(groups.values()), "capacities": capacities,
        "source": str(args.codec), "filename": "codec_compact_reviewed.json",
    }, ensure_ascii=False).replace("</", "<\\/")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(TEMPLATE.replace("__PAYLOAD__", payload), encoding="utf-8")
    print(f"wrote {len(groups)} groups / {len(physical)} physical rows / "
          f"{len(capacities)} GCXs: {args.output}")
    return 0


TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MGS3D codec 용량 검수기</title>
<style>:root{--bg:#0d1319;--panel:#18212b;--line:#394959;--text:#edf2f7;--muted:#9fb0c0;--ok:#62d391;--bad:#ff6b78;--focus:#63a9ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}header{position:sticky;top:0;z-index:5;background:#0d1319f5;border-bottom:1px solid var(--line);padding:12px 18px}h1{font-size:19px;margin:0 0 8px}.bar{display:flex;gap:8px;flex-wrap:wrap}input,button,textarea{background:#101820;color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px}input[type=search]{min-width:280px;flex:1}button{cursor:pointer}.primary{border-color:#35885b;color:var(--ok)}#summary{margin-top:7px;color:var(--muted)}main{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:14px;padding:14px 18px 60px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:13px;margin-bottom:10px}.card.current{outline:3px solid var(--focus)}.card.off{opacity:.55}.english,.full{white-space:pre-wrap}.english{font-size:16px}.full{color:#b9c9d8}.meta{font-size:12px;color:var(--muted)}textarea{width:100%;min-height:96px;resize:vertical;margin-top:7px}.metrics{display:flex;gap:12px;flex-wrap:wrap;margin-top:6px}.ok{color:var(--ok)}.bad{color:var(--bad);font-weight:700}aside{position:sticky;top:112px;align-self:start;max-height:calc(100vh - 130px);overflow:auto}.gcx{padding:8px;border-bottom:1px solid var(--line)}@media(max-width:900px){main{grid-template-columns:1fr}aside{position:static;max-height:none}}</style></head><body>
<header><h1>MGS3D codec 축약·용량 검수기</h1><div class="bar"><input id="q" type="search" placeholder="영문·한글·GCX 검색"><label><input id="over" type="checkbox"> 용량 초과 GCX만</label><button id="prev">← 이전</button><button id="next">다음 →</button><button class="primary" id="save">빌드 JSON 저장</button></div><div class="meta">Enter: 다음 · Ctrl+Enter: 확인 후 다음 · Space: 적용/제외 · 권장 한도는 중복 위치 중 가장 작은 GCX 기준</div><div id="summary"></div></header>
<main><section id="cards"></section><aside class="card"><b>GCX 실시간 용량</b><div id="gcxs"></div></aside></main>
<script>const data=__PAYLOAD__,$=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let current=0;
function hangul(s){return new Set([...s].filter(c=>c>='가'&&c<='힣'))}function encoded(s){let n=0;for(let i=0;i<s.length;){if(s[i]==='<'&&/^<[0-9A-Fa-f]{2}>/.test(s.slice(i,i+4))){n++;i+=4}else{n+=(s.codePointAt(i)>127?2:1);i+=s.codePointAt(i)>65535?2:1}}return n}
function sync(){data.groups.forEach(g=>g.indices.forEach(i=>{data.physical[i].text=g.text;data.physical[i].enabled=g.enabled}))}function calc(){sync();const state={};for(const [g,c] of Object.entries(data.capacities))state[g]={...c,strings:0,glyphs:new Set(),rows:0};data.physical.forEach(r=>{if(!r.enabled)return;const s=state[r.gcx];s.rows++;s.strings+=r.original_size-encoded(r.text);hangul(r.text).forEach(c=>s.glyphs.add(c))});for(const s of Object.values(state)){s.glyphCount=s.glyphs.size;s.glyphBytes=Math.max(0,s.glyphCount-s.free_slots)*64;s.remaining=s.donor_savings+s.strings-s.glyphBytes;s.recommended=Math.max(0,Math.floor((s.donor_savings+s.strings)/64)+s.free_slots)}return state}
function visible(state){const q=$('#q').value.toLowerCase(),over=$('#over').checked;return data.groups.filter(g=>(!q||(g.english+g.full+g.text+g.indices.map(i=>data.physical[i].gcx).join(' ')).toLowerCase().includes(q))&&(!over||g.indices.some(i=>state[data.physical[i].gcx].remaining<0)))}
function updateCapacity(state,count){$('#summary').textContent=`표시 ${count}/${data.groups.length} · 통과 ${Object.values(state).filter(s=>s.remaining>=0).length}/${Object.keys(state).length} GCX`;$('#gcxs').innerHTML=Object.entries(state).map(([g,s])=>`<div class="gcx"><b>GCX ${g}</b> · ${s.rows}개<br><span class="${s.remaining>=0?'ok':'bad'}">${s.remaining>=0?'여유':'초과'} ${Math.abs(s.remaining)}B</span><br><span class="meta">외국어 회수 ${s.donor_savings}B · 문자열 ${s.strings>=0?'+':''}${s.strings}B · 글리프 ${s.glyphCount}/${s.recommended}자 (${s.glyphBytes}B)</span></div>`).join('')}
function render(){const state=calc(),groups=visible(state);if(current>=groups.length)current=Math.max(0,groups.length-1);updateCapacity(state,groups.length);
$('#cards').innerHTML=groups.map((g,p)=>{const loc=g.indices.map(i=>data.physical[i]),limits=loc.map(r=>state[r.gcx].recommended),limit=Math.min(...limits),h=hangul(g.text).size,bytes=encoded(g.text),old=Math.min(...loc.map(r=>r.original_size));return `<article class="card ${p===current?'current':''} ${g.enabled?'':'off'}" data-p="${p}"><label><input type="checkbox" data-e="${g.id}" ${g.enabled?'checked':''}> 적용</label> <span class="meta">#${g.id} · ${loc.map(r=>`GCX ${r.gcx}/${r.resource}`).join(', ')}</span><div class="english">${esc(g.english)}</div><div class="meta">검수 원문</div><div class="full">${esc(g.full)}</div><textarea data-t="${g.id}">${esc(g.text)}</textarea><div class="metrics"><span>문장 ${bytes}/${old}B</span><span>고유 한글 ${h}자</span><span>권장 GCX 전체 ≤ ${limit}자</span><span class="${g.decision==='confirmed'?'ok':''}">${g.decision==='confirmed'?'확인됨':''}</span></div></article>`}).join('');
}
function group(id){return data.groups.find(g=>g.id===+id)}$('#cards').oninput=e=>{if(e.target.dataset.t){group(e.target.dataset.t).text=e.target.value;const state=calc();updateCapacity(state,visible(state).length)}if(e.target.dataset.e){group(e.target.dataset.e).enabled=e.target.checked;render()}};$('#cards').onclick=e=>{const c=e.target.closest('[data-p]');if(c&&+c.dataset.p!==current){current=+c.dataset.p;render()}};$('#q').oninput=render;$('#over').oninput=render;function jump(d,confirm=false){const gs=visible(calc());if(confirm&&gs[current])gs[current].decision='confirmed';current=Math.max(0,Math.min(gs.length-1,current+d));render();requestAnimationFrame(()=>$('.current')?.scrollIntoView({block:'center'}))}$('#prev').onclick=()=>jump(-1);$('#next').onclick=()=>jump(1);document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();jump(1,true)}else if(e.target.matches('textarea,input'))return;else if(e.key==='Enter'||e.key==='ArrowRight'){e.preventDefault();jump(1)}else if(e.key==='ArrowLeft'){e.preventDefault();jump(-1)}else if(e.code==='Space'){e.preventDefault();const g=visible(calc())[current];if(g){g.enabled=!g.enabled;render()}}});
$('#save').onclick=()=>{sync();const units=data.physical.filter(r=>r.enabled).map(({gcx,resource,kind,original_size,text})=>({gcx,resource,kind,original_size,text})),doc={format:'mgs3d-codec-translation-v1',character_map:{},units};const blob=new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=data.filename;a.click();URL.revokeObjectURL(a.href)};render();</script></body></html>'''


if __name__ == "__main__":
    raise SystemExit(main())
