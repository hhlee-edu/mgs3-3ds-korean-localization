#!/usr/bin/env python3
"""Build an offline whole-GCX translation capacity editor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, render_bytes  # noqa: E402
from mgs3d_gcx_font_tool import font_region, freed_font_slots  # noqa: E402
from mgs3d_translation import validate_codec_translation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("selected", type=Path)
    parser.add_argument("selection_report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--supplement", type=Path, action="append")
    parser.add_argument("--focus-report", type=Path,
                        help="duplicate-completion report; show rejected targets and their active GCX peers")
    args = parser.parse_args()

    records = parse_codec(args.codec.read_bytes())
    _, units = validate_codec_translation(json.loads(args.translation.read_text(encoding="utf-8-sig")))
    for path in args.supplement or []:
        _, extra = validate_codec_translation(json.loads(path.read_text(encoding="utf-8-sig")))
        units.extend(extra)
    _, selected_units = validate_codec_translation(json.loads(args.selected.read_text(encoding="utf-8-sig")))
    selected = {(int(x["gcx"]), int(x["resource"])): str(x["text"])
                for x in selected_units if str(x["text"]) != "<00>"}
    reports = {int(x["gcx"]): x for x in json.loads(
        args.selection_report.read_text(encoding="utf-8"))["records"]}

    # The last reviewed/supplemental value wins for a physical resource.
    candidates = {}
    for unit in units:
        candidates[(int(unit["gcx"]), int(unit["resource"]))] = str(unit["text"])

    focus = None
    focus_text = {}
    if args.focus_report:
        focus_doc = json.loads(args.focus_report.read_text(encoding="utf-8"))
        focus = {(int(row["gcx"]), int(row["resource"]))
                 for row in focus_doc.get("rejected", [])}
        focus_text = {(int(row["gcx"]), int(row["resource"])): str(row["text"])
                      for row in focus_doc.get("rejected", [])}

    gcxs = []
    for gcx in sorted({key[0] for key in candidates}):
        if focus is not None and not any(key[0] == gcx for key in focus):
            continue
        report = reports.get(gcx)
        if not report:
            continue
        foreign = set(map(int, report.get("foreign_block_excluded_resources", [])))
        resources = records[gcx].resources()
        donor_resources = list(map(int, report.get("donor_resources", [])))
        _, old_count = font_region(records[gcx])
        free_slots = len(freed_font_slots(records[gcx], set(donor_resources)))
        rows = []
        for (row_gcx, resource), text in sorted(candidates.items()):
            if row_gcx != gcx or resource in foreign:
                continue
            if focus is not None and (gcx, resource) not in selected and (gcx, resource) not in focus:
                continue
            rows.append({
                "resource": resource,
                "english": render_bytes(resources[resource].data),
                "original_size": len(resources[resource].data),
                "original_text": text,
                "text": selected.get((gcx, resource), focus_text.get((gcx, resource), text)),
                "enabled": (gcx, resource) in selected,
                "focus": focus is not None and (gcx, resource) in focus,
            })
        if focus is not None:
            rows.sort(key=lambda row: (not row["focus"], row["resource"]))
        if rows:
            gcxs.append({
                "gcx": gcx, "rows": rows, "glyph_limit": int(report.get("glyph_limit") or 100),
                "old_font_count": old_count, "free_slots": free_slots,
                "donor_savings": int(report.get("donor_savings", 0)),
                "donors": donor_resources,
            })

    filename = ("codec_duplicate_focus_patch.json" if focus is not None
                else "codec_gcx_corrections.json")
    payload = json.dumps({"gcxs": gcxs, "filename": filename},
                         ensure_ascii=False).replace("</", "<\\/")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    print(f"wrote {len(gcxs)} GCXs / {sum(len(x['rows']) for x in gcxs)} candidate rows: {args.output}")
    return 0


TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Codec GCX 전체 수정기</title>
<style>:root{--bg:#0d1319;--card:#18212b;--line:#3b4b5c;--text:#eef4fa;--muted:#a9bac9;--ok:#66d596;--bad:#ff707c;--focus:#66aaff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}header{position:sticky;top:0;z-index:3;background:#0d1319f5;border-bottom:1px solid var(--line);padding:12px 18px}h1{font-size:20px;margin:0 0 8px}.bar,.metrics{display:flex;gap:8px;flex-wrap:wrap;align-items:center}input,button,textarea{background:#101820;color:var(--text);border:1px solid var(--line);border-radius:7px;padding:8px}input[type=search]{min-width:230px;flex:1}button{cursor:pointer}.primary{border-color:var(--ok)}main{max-width:1150px;margin:auto;padding:14px 18px 70px}.gcxhead{padding:12px;background:#111b24;border:1px solid var(--line);border-radius:9px;margin-bottom:12px}.row{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:12px;margin-bottom:9px}.row.target{border:2px solid #e0aa45}.row.off{opacity:.58}.english,.korean{white-space:pre-wrap}.english{font-size:15px}.meta{color:var(--muted);font-size:12px}textarea{width:100%;min-height:72px;margin-top:7px;resize:vertical}.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}.toggle{font-weight:700}</style></head><body>
<header><h1>Codec GCX 전체 수정기</h1><div class="bar"><input id="q" type="search" placeholder="영문·한글·GCX 검색"><button id="prev">← 이전 GCX</button><button id="next">다음 GCX →</button><button id="all">전체 선택</button><button id="none">전체 해제</button><button class="primary" id="save">적용 JSON 저장</button></div><div class="meta">한 GCX의 모든 대사를 함께 수정합니다. 체크 해제하면 번역에서 제외됩니다. 목표: 글리프 ≤ 100, 남는 용량 ≥ 0B.</div></header><main id="main"></main>
<script>const D=__DATA__,$=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const STORE='mgs3d-whole-gcx-editor-v1';let at=0;const saved=JSON.parse(localStorage.getItem(STORE)||'{}');D.gcxs.forEach(g=>g.rows.forEach(r=>{const x=saved[`${g.gcx}:${r.resource}`];if(x)Object.assign(r,x)}));
function hs(s){return new Set([...s].filter(c=>c>='가'&&c<='힣'))}function enc(s){let n=0;for(let i=0;i<s.length;){if(s[i]==='<'&&/^<[0-9A-Fa-f]{2}>/.test(s.slice(i,i+4))){n++;i+=4}else{const cp=s.codePointAt(i);n+=cp>127?2:1;i+=cp>65535?2:1}}return n}function metric(g){const on=g.rows.filter(r=>r.enabled),glyph=new Set;on.forEach(r=>hs(r.text).forEach(c=>glyph.add(c)));const stringSavings=g.donor_savings+on.reduce((n,r)=>n+r.original_size-enc(r.text),0),fontCost=Math.max(0,glyph.size-g.free_slots)*64,net=stringSavings-fontCost;return{count:on.length,glyph:glyph.size,stringSavings,fontCost,net,fit:glyph.size<=g.glyph_limit&&net>=0}}
function persist(){const x={};D.gcxs.forEach(g=>g.rows.forEach(r=>x[`${g.gcx}:${r.resource}`]={text:r.text,enabled:r.enabled}));localStorage.setItem(STORE,JSON.stringify(x))}function matches(g){const q=$('#q').value.toLowerCase();return!q||String(g.gcx).includes(q)||g.rows.some(r=>(r.english+r.text).toLowerCase().includes(q))}function visible(){return D.gcxs.filter(matches)}
function render(){const gs=visible();at=Math.max(0,Math.min(at,gs.length-1));const g=gs[at];if(!g){$('#main').innerHTML='<p>검색 결과가 없습니다.</p>';return}const m=metric(g);$('#main').innerHTML=`<section class="gcxhead"><div class="meta">GCX ${g.gcx} · 검색 결과 ${at+1}/${gs.length}</div><div class="metrics"><strong class="${m.fit?'ok':'bad'}">${m.fit?'적용 가능':'조정 필요'}</strong><span class="${m.glyph<=g.glyph_limit?'ok':'bad'}">글리프 ${m.glyph}/${g.glyph_limit}</span><span class="${m.net>=0?'ok':'bad'}">남는 용량 ${m.net}B</span><span>문자열 잔액 ${m.stringSavings}B</span><span>폰트 비용 ${m.fontCost}B</span><span>선택 ${m.count}/${g.rows.length}</span></div></section>`+g.rows.map((r,i)=>`<article class="row ${r.focus?'target':''} ${r.enabled?'':'off'}" data-i="${i}"><label class="toggle"><input type="checkbox" data-enable="${i}" ${r.enabled?'checked':''}> ${r.focus?'누락 목표':'기존 적용'} · resource ${r.resource}</label><div class="english">${esc(r.english)}</div><textarea data-text="${i}">${esc(r.text)}</textarea></article>`).join('')}
function rerenderKeep(id,pos){render();requestAnimationFrame(()=>{const t=document.querySelector(`[data-text="${id}"]`);if(t){t.focus();t.setSelectionRange(pos,pos)}})}$('#main').oninput=e=>{const g=visible()[at];if(e.target.dataset.text!==undefined){const i=+e.target.dataset.text,pos=e.target.selectionStart;g.rows[i].text=e.target.value;persist();rerenderKeep(i,pos)}else if(e.target.dataset.enable!==undefined){g.rows[+e.target.dataset.enable].enabled=e.target.checked;persist();render()}};function jump(n){const gs=visible();at=Math.max(0,Math.min(gs.length-1,at+n));render()}$('#prev').onclick=()=>jump(-1);$('#next').onclick=()=>jump(1);$('#q').oninput=()=>{at=0;render()};$('#all').onclick=()=>{visible()[at].rows.forEach(r=>r.enabled=true);persist();render()};$('#none').onclick=()=>{visible()[at].rows.forEach(r=>r.enabled=false);persist();render()};document.addEventListener('keydown',e=>{if(e.target.matches('textarea,input'))return;if(e.key==='ArrowRight')jump(1);if(e.key==='ArrowLeft')jump(-1)});
$('#save').onclick=()=>{const units=[];D.gcxs.forEach(g=>{g.donors.forEach(resource=>units.push({gcx:g.gcx,resource,kind:'string',text:'<00>'}));g.rows.filter(r=>r.enabled).forEach(r=>units.push({gcx:g.gcx,resource:r.resource,kind:'string',text:r.text}))});const doc={format:'mgs3d-codec-translation-v1',character_map:{},units},b=new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=D.filename;a.click();URL.revokeObjectURL(a.href)};render();</script></body></html>'''


if __name__ == "__main__":
    raise SystemExit(main())
