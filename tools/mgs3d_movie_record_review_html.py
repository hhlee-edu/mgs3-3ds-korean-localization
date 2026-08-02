#!/usr/bin/env python3
"""Build an offline whole-record capacity editor for movie.dat or demo.dat."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import render_bytes  # noqa: E402
from mgs3d_movie_tool import (  # noqa: E402
    maximal_size_neutral_subset, parse_records, read_replacements,
)


def source_weights(raw: bytes) -> list[int]:
    lines = raw.rstrip(b"\0").split(b"\x80|")
    result = []
    for line in lines:
        units = cursor = 0
        while cursor < len(line):
            cursor += 2 if line[cursor] >= 0x80 and cursor + 1 < len(line) else 1
            units += 1
        result.append(max(1, units))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dat", type=Path)
    parser.add_argument("translation_csv", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="Movie/Demo 레코드 전체 수정기")
    parser.add_argument("--font-size", type=int, default=15)
    args = parser.parse_args()

    replacements = read_replacements(args.translation_csv)
    font = ImageFont.truetype(str(args.font), args.font_size)
    _, records, _ = parse_records(args.dat.read_bytes())
    payload_records = []
    found = set()
    for record in records:
        local = {s.offset: replacements[s.offset] for s in record.subtitles if s.offset in replacements}
        if not local:
            continue
        found.update(local)
        donors = {s.offset for s in record.subtitles if s.entry_type in {2, 3, 4, 5}}
        chosen = maximal_size_neutral_subset(record, local, donors, font)
        rows = []
        for subtitle in record.subtitles:
            if subtitle.offset not in local:
                continue
            rows.append({
                "offset": subtitle.offset, "english": render_bytes(subtitle.raw),
                "text": local[subtitle.offset], "original_text": local[subtitle.offset],
                "enabled": subtitle.offset in chosen, "original_len": len(subtitle.original),
                "tail_len": len(subtitle.tail), "weights": source_weights(subtitle.raw),
            })
        payload_records.append({
            "record": record.index, "target": len(record.raw), "old_font": len(record.font),
            "rows": rows,
            "entries": [{"offset": s.offset, "type": s.entry_type,
                         "original_len": len(s.original), "tail_len": len(s.tail)}
                        for s in record.subtitles],
        })
    missing = sorted(set(replacements) - found)
    if missing:
        raise ValueError(f"{len(missing)} offsets were not found")
    payload = json.dumps({"records": payload_records, "title": args.title,
                          "filename": args.output.stem + "_translations.csv"},
                         ensure_ascii=False).replace("</", "<\\/")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    print(f"wrote {len(payload_records)} records / {len(replacements)} candidates: {args.output}")
    return 0


TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Movie/Demo 레코드 수정기</title><style>:root{--bg:#0d1319;--card:#18212b;--line:#3b4b5c;--text:#eef4fa;--muted:#a9bac9;--ok:#66d596;--bad:#ff707c}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 system-ui,sans-serif}header{position:sticky;top:0;z-index:3;background:#0d1319f5;border-bottom:1px solid var(--line);padding:12px 18px}h1{font-size:20px;margin:0 0 8px}.bar,.metrics{display:flex;gap:9px;flex-wrap:wrap;align-items:center}input,button,textarea{background:#101820;color:var(--text);border:1px solid var(--line);border-radius:7px;padding:8px}input[type=search]{min-width:240px;flex:1}button{cursor:pointer}.primary{border-color:var(--ok)}main{max-width:1100px;margin:auto;padding:14px 18px 70px}.head,.row{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:12px;margin-bottom:10px}.row.off{opacity:.55}.english{font-size:16px;white-space:pre-wrap}.meta{color:var(--muted);font-size:12px}textarea{width:100%;min-height:76px;margin-top:7px}.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}</style></head><body><header><h1 id="title"></h1><div class="bar"><input id="q" type="search" placeholder="영문·한글·레코드 검색"><button id="prev">← 이전</button><button id="next">다음 →</button><button id="all">전체 선택</button><button id="none">전체 해제</button><button class="primary" id="save">CSV 저장</button></div><div class="meta">레코드 단위로 함께 수정합니다. 목표는 남는 용량 0B 이상입니다. 선택한 문장의 고유 한글마다 64B가 필요합니다.</div></header><main id="main"></main><script>const D=__DATA__,$=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));$('#title').textContent=D.title;const STORE='mgs3d-record-editor-'+D.filename;let at=0,S=JSON.parse(localStorage.getItem(STORE)||'{}');D.records.forEach(g=>g.rows.forEach(r=>{if(S[r.offset])Object.assign(r,S[r.offset])}));function align(n,a){return(n+a-1)&~(a-1)}function glyphs(s){return new Set([...s].filter(c=>c>='가'&&c<='힣'))}function wrap(text,w){if(text.includes('\n')||w.length<2)return text;let words=text.trim().split(/\s+/).filter(Boolean),out=[];if(words.length<w.length){let b=[0],u=0,t=w.reduce((a,b)=>a+b,0);for(let i=0;i<w.length-1;i++){u+=w[i];b.push(Math.round(u/t*text.length))}b.push(text.length);for(let i=0;i<w.length;i++)out.push(text.slice(b[i],b[i+1]));return out.join('\n')}let b=[0],u=0,t=w.reduce((a,b)=>a+b,0);for(let i=0;i<w.length-1;i++){u+=w[i];b.push(Math.max(b.at(-1)+1,Math.min(words.length-1,Math.round(u/t*words.length))))}b.push(words.length);for(let i=0;i<w.length;i++)out.push(words.slice(b[i],b[i+1]).join(' '));return out.join('\n')}function enc(s){let n=1;for(const c of s)n+=c==='\n'?2:(c.charCodeAt(0)>127?2:1);return n}function metric(g){let on=g.rows.filter(r=>r.enabled);if(!on.length)return{fit:true,glyph:0,natural:g.target,free:0,count:0};let gm=new Set;on.forEach(r=>glyphs(r.text).forEach(c=>gm.add(c)));let map=new Map(g.rows.map(r=>[r.offset,r])),body=32;for(const e of g.entries){let r=map.get(e.offset);if(e.type>=2&&e.type<=5)body+=align(4+1+e.tail_len,4);else if(r&&r.enabled)body+=align(4+enc(wrap(r.text,r.weights))+e.tail_len,4);else body+=e.original_len}body+=4+g.old_font+gm.size*64;let natural=align(body,16);return{fit:natural<=g.target,glyph:gm.size,natural,free:g.target-natural,count:on.length}}function persist(){let x={};D.records.forEach(g=>g.rows.forEach(r=>x[r.offset]={text:r.text,enabled:r.enabled}));localStorage.setItem(STORE,JSON.stringify(x))}function visible(){let q=$('#q').value.toLowerCase();return D.records.filter(g=>!q||String(g.record).includes(q)||g.rows.some(r=>(r.english+r.text).toLowerCase().includes(q)))}function render(){let gs=visible();at=Math.max(0,Math.min(at,gs.length-1));let g=gs[at];if(!g){$('#main').innerHTML='<p>검색 결과 없음</p>';return}let m=metric(g);$('#main').innerHTML=`<section class="head"><div class="meta">record ${g.record} · ${at+1}/${gs.length}</div><div class="metrics"><strong class="${m.fit?'ok':'bad'}">${m.fit?'적용 가능':'용량 초과'}</strong><span class="${m.fit?'ok':'bad'}">남는 용량 ${m.free}B</span><span>글리프 ${m.glyph}개 / ${m.glyph*64}B</span><span>선택 ${m.count}/${g.rows.length}</span></div></section>`+g.rows.map((r,i)=>`<article class="row ${r.enabled?'':'off'}"><label><input data-on="${i}" type="checkbox" ${r.enabled?'checked':''}> 적용 · offset ${r.offset}</label><div class="english">${esc(r.english)}</div><textarea data-text="${i}">${esc(r.text)}</textarea></article>`).join('')}function keep(i,p){render();requestAnimationFrame(()=>{let t=document.querySelector(`[data-text="${i}"]`);if(t){t.focus();t.setSelectionRange(p,p)}})}$('#main').oninput=e=>{let g=visible()[at];if(e.target.dataset.text!==undefined){let i=+e.target.dataset.text,p=e.target.selectionStart;g.rows[i].text=e.target.value;persist();keep(i,p)}else if(e.target.dataset.on!==undefined){g.rows[+e.target.dataset.on].enabled=e.target.checked;persist();render()}};function jump(n){at=Math.max(0,Math.min(visible().length-1,at+n));render()}$('#prev').onclick=()=>jump(-1);$('#next').onclick=()=>jump(1);$('#q').oninput=()=>{at=0;render()};$('#all').onclick=()=>{visible()[at].rows.forEach(r=>r.enabled=true);persist();render()};$('#none').onclick=()=>{visible()[at].rows.forEach(r=>r.enabled=false);persist();render()};$('#save').onclick=()=>{let lines=['accept,offset,korean'],q=s=>'"'+String(s).replaceAll('"','""')+'"';D.records.forEach(g=>g.rows.filter(r=>r.enabled).forEach(r=>lines.push(`yes,${r.offset},${q(r.text)}`)));let b=new Blob(['\ufeff'+lines.join('\r\n')+'\r\n'],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=D.filename;a.click();URL.revokeObjectURL(a.href)};render();</script></body></html>'''


if __name__ == "__main__":
    raise SystemExit(main())
