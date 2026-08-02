#!/usr/bin/env python3
"""Build an offline English-first reviewer for English-to-Korean match CSVs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


EXTRA_FIELDS = ("disposition", "correction_note")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="primary match CSV (normally codec)")
    parser.add_argument("output", type=Path)
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)
    args = parser.parse_args()
    rows: list[dict[str, str]] = []
    fields: list[str] = []
    inputs = [args.input] + [path for path in (args.movie, args.demo) if path]
    for path in inputs:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            batch = list(reader)
            for field in reader.fieldnames or []:
                if field not in fields:
                    fields.append(field)
            rows.extend(batch)
    for field in EXTRA_FIELDS:
        if field not in fields:
            fields.append(field)

    groups: dict[str, list[int]] = {}
    order: list[str] = []
    for index, row in enumerate(rows):
        key = row.get("english_sequence", "") or row.get("english", "")
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append(index)
        row.setdefault("disposition", "")
        row.setdefault("correction_note", "")
    review = []
    for position, key in enumerate(order):
        indices = groups[key]
        first = rows[indices[0]]
        previous = rows[groups[order[position - 1]][0]] if position else {}
        following = rows[groups[order[position + 1]][0]] if position + 1 < len(order) else {}
        locations = [
            f"{row.get('container', '?')}: GCX {row.get('gcx')}/{row.get('resource')}"
            if row.get("gcx")
            else f"{row.get('container', '?')}: record {row.get('record')}/"
                 f"{row.get('entry')} @ {row.get('offset')}"
            for row in (rows[index] for index in indices)
        ]
        review.append({
            "key": key, "indices": indices, "english": first.get("english", ""),
            "korean": first.get("korean", ""),
            "confidence": first.get("alignment_confidence", ""),
            "match_status": first.get("match_status", ""),
            "previous_english": previous.get("english", ""),
            "previous_korean": previous.get("korean", ""),
            "next_english": following.get("english", ""),
            "next_korean": following.get("korean", ""),
            "locations": locations,
            "disposition": first.get("disposition", ""),
            "correction_note": first.get("correction_note", ""),
        })

    filename = "en_all_matches.csv" if len(inputs) > 1 else args.input.name
    payload = json.dumps({"rows": rows, "fields": fields, "groups": review,
                          "filename": filename}, ensure_ascii=False).replace("</", "<\\/")
    document = TEMPLATE.replace("__PAYLOAD__", payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"wrote {len(review)} English groups / {len(rows)} physical rows: {args.output}")
    return 0


TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MGS3D 영문판 한글 대사 검수</title>
<style>:root{--bg:#10151b;--panel:#1a222c;--line:#364453;--text:#e8edf3;--muted:#9cabb9;--ok:#65d694;--warn:#ffd166;--focus:#62a8ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}header{position:sticky;top:0;z-index:3;padding:12px 18px;background:#10151bf2;border-bottom:1px solid var(--line)}h1{font-size:18px;margin:0 0 9px}.controls,.actions{display:flex;gap:8px;flex-wrap:wrap}input,select,button,textarea{background:#111820;color:var(--text);border:1px solid var(--line);border-radius:5px;padding:8px}input[type=search]{min-width:320px;flex:1}button{cursor:pointer}.primary{color:var(--ok);border-color:#36865b}.actions{margin-top:9px}.actions button{font-size:15px;font-weight:700;padding:9px 18px}.confirm{border-color:#36865b}.correct{border-color:#3b82c4}.unsupported{border-color:#b78732}.unresolved{border-color:#a75b68}.shortcuts{color:var(--muted);margin-top:7px;font-size:12px}kbd{background:#26313d;border:1px solid #526274;border-radius:4px;padding:1px 5px;color:#fff}#stats{color:var(--muted);margin-top:7px}main{padding:12px 18px 50px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px;margin:10px 0;transition:outline-color .12s,box-shadow .12s}.card.done{border-color:#36865b}.card.current{outline:3px solid var(--focus);box-shadow:0 0 0 5px #62a8ff26}.head{display:grid;grid-template-columns:150px 1fr;gap:12px}.meta{color:var(--muted);font-size:12px}.english{font-size:17px;white-space:pre-wrap;margin:5px 0 13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}textarea{width:100%;min-height:125px;resize:vertical}.context{white-space:pre-wrap;color:#b9c6d2;border-left:3px solid var(--line);padding-left:9px;margin:7px 0}.locations{max-height:150px;overflow:auto;white-space:pre-wrap;font-family:ui-monospace,monospace;background:#111820;padding:8px}.decision{width:100%;margin-bottom:8px}@media(max-width:800px){.head,.grid{grid-template-columns:1fr}}</style></head><body>
<header><h1>MGS3D 영문판 → 한글 대사 검수</h1><div class="controls"><select id="conf"><option value="">모든 신뢰도</option></select><select id="disp"><option value="">모든 판정</option><option value="pending">미판정</option><option value="confirmed">확인</option><option value="corrected">교정</option><option value="unsupported">미지원</option><option value="unresolved">미해결</option></select><input id="q" type="search" placeholder="영문 / 한글 / GCX 검색"><button id="prev">← 이전 미판정</button><button id="next">다음 미판정 →</button><button class="primary" id="save">검수 CSV 저장</button></div><div class="actions"><button class="confirm" data-action="confirmed">확인 후 다음 (Enter)</button><button class="correct" data-action="corrected">교정 후 다음 (Ctrl+Enter)</button><button class="unresolved" data-action="unresolved">미해결 후 다음 (U)</button><button class="unsupported" data-action="unsupported">미지원 후 다음 (S)</button></div><div class="shortcuts"><kbd>Enter</kbd> 확인 · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> 교정 · <kbd>U</kbd> 미해결 · <kbd>S</kbd> 미지원 · <kbd>←</kbd>/<kbd>→</kbd> 이전·다음 미판정</div><div id="stats"></div></header><main id="list"></main>
<script>const data=__PAYLOAD__,$=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label={confirmed:'확인',corrected:'교정',unsupported:'미지원',unresolved:'미해결'};let currentKey='';function filtered(){const q=$('#q').value.toLowerCase(),c=$('#conf').value,d=$('#disp').value;return data.groups.filter(g=>(!q||JSON.stringify(g).toLowerCase().includes(q))&&(!c||g.confidence===c)&&(!d||(d==='pending'?!g.disposition:g.disposition===d)))}
function setGroup(g,field,value){g[field]=value;g.indices.forEach(i=>{data.rows[i][field]=value;if(field==='korean'&&data.rows[i].disposition==='confirmed'){data.rows[i].disposition='corrected';g.disposition='corrected'}if(field==='disposition')data.rows[i].accept=['confirmed','corrected'].includes(value)?'yes':''})}
function render(){const gs=filtered(),counts={};data.groups.forEach(g=>counts[g.disposition||'pending']=(counts[g.disposition||'pending']||0)+1);if(!currentKey||!gs.some(g=>String(g.key)===String(currentKey)))currentKey=String((gs.find(g=>!g.disposition)||gs[0]||{}).key||'');$('#stats').textContent=`표시 ${gs.length} / 전체 ${data.groups.length} · 확인 ${counts.confirmed||0} · 교정 ${counts.corrected||0} · 미지원 ${counts.unsupported||0} · 미해결 ${counts.unresolved||0} · 미판정 ${counts.pending||0}`;const list=$('#list');list.innerHTML='';gs.forEach(g=>{const card=document.createElement('article');card.id='g-'+g.key;card.dataset.key=g.key;card.className='card'+(['confirmed','corrected'].includes(g.disposition)?' done':'')+(String(g.key)===String(currentKey)?' current':'');card.innerHTML=`<div class="head"><div><select class="decision" data-d="${esc(g.key)}"><option value="">미판정</option>${Object.entries(label).map(([v,t])=>`<option value="${v}" ${g.disposition===v?'selected':''}>${t}</option>`).join('')}</select><div class="meta">EN-${esc(g.key)}<br>${esc(g.confidence)} · ${esc(g.match_status)}<br>중복 ${g.indices.length}개</div></div><div><div class="meta">영문 원문</div><div class="english">${esc(g.english)}</div></div></div><div class="grid"><div><div class="meta">이전 문맥</div><div class="context">${esc(g.previous_english)}\n${esc(g.previous_korean)}</div><div class="meta">한글 후보 / 교정문</div><textarea data-k="${esc(g.key)}">${esc(g.korean)}</textarea><div class="meta">다음 문맥</div><div class="context">${esc(g.next_english)}\n${esc(g.next_korean)}</div></div><div><div class="meta">실제 중복 위치</div><div class="locations">${esc(g.locations.join('\n'))}</div><div class="meta">판정 메모</div><textarea data-n="${esc(g.key)}">${esc(g.correction_note)}</textarea></div></div>`;list.appendChild(card)})}
const map=new Map(data.groups.map(g=>[String(g.key),g]));[...new Set(data.groups.map(g=>g.confidence).filter(Boolean))].sort().forEach(x=>$('#conf').insertAdjacentHTML('beforeend',`<option>${esc(x)}</option>`));['conf','disp','q'].forEach(id=>$('#'+id).oninput=render);$('#list').onchange=e=>{if(e.target.matches('[data-d]')){setGroup(map.get(e.target.dataset.d),'disposition',e.target.value);render()}};$('#list').oninput=e=>{if(e.target.matches('[data-k]'))setGroup(map.get(e.target.dataset.k),'korean',e.target.value);if(e.target.matches('[data-n]'))setGroup(map.get(e.target.dataset.n),'correction_note',e.target.value)};
function focusGroup(g){if(!g)return;currentKey=String(g.key);$('#conf').value='';$('#disp').value='';$('#q').value='';render();requestAnimationFrame(()=>$('#g-'+CSS.escape(currentKey))?.scrollIntoView({behavior:'smooth',block:'center'}))}function jump(dir){const pending=data.groups.filter(g=>!g.disposition),current=pending.findIndex(g=>String(g.key)===String(currentKey)),index=current<0?(dir>0?0:pending.length-1):Math.max(0,Math.min(pending.length-1,current+dir));focusGroup(pending[index])}function decide(value){const current=map.get(String(currentKey));if(!current)return;const position=data.groups.indexOf(current);setGroup(current,'disposition',value);const next=data.groups.slice(position+1).find(g=>!g.disposition)||data.groups.find(g=>!g.disposition);focusGroup(next||current)}$('#prev').onclick=()=>jump(-1);$('#next').onclick=()=>jump(1);document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>decide(b.dataset.action));$('#list').onclick=e=>{const card=e.target.closest('.card');if(card&&String(card.dataset.key)!==String(currentKey)){currentKey=String(card.dataset.key);document.querySelectorAll('.card.current').forEach(x=>x.classList.remove('current'));card.classList.add('current')}};document.addEventListener('keydown',e=>{const editing=e.target.matches('textarea,input,select');if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();decide('corrected');return}if(editing)return;if(e.key==='Enter'){e.preventDefault();decide('confirmed')}else if(e.key.toLowerCase()==='u'){e.preventDefault();decide('unresolved')}else if(e.key.toLowerCase()==='s'){e.preventDefault();decide('unsupported')}else if(e.key==='ArrowRight'){e.preventDefault();jump(1)}else if(e.key==='ArrowLeft'){e.preventDefault();jump(-1)}});
function cell(v){v=String(v??'');return /[",\r\n]/.test(v)?'"'+v.replaceAll('"','""')+'"':v}$('#save').onclick=()=>{const lines=[data.fields.map(cell).join(',')];data.rows.forEach(r=>lines.push(data.fields.map(f=>cell(r[f])).join(',')));const blob=new Blob(['\ufeff'+lines.join('\r\n')],{type:'text/csv;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=data.filename.replace(/\.csv$/,'_reviewed.csv');a.click();URL.revokeObjectURL(a.href)};render();</script></body></html>'''


if __name__ == "__main__":
    raise SystemExit(main())
