#!/usr/bin/env python3
"""Flat two-list dialogue picker for movie.dat / demo.dat.

No scene/anchor logic — just every remaining (unmatched) 3DS English card
in one scrollable list, every candidate Korean line in another, both
searchable. Click a Korean line to select it, then click an English card
to assign it (or click cards first to multi-select, then one Korean line
to assign to all of them at once, splitting words proportionally).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_english_korean_match import decode_western  # noqa: E402
from mgs3d_movie_tool import page3_indices, parse_records  # noqa: E402


def load_remaining_cards(kind: str, dat: Path, already_matched_offsets: set[int]) -> list[dict]:
    data = dat.read_bytes()
    _, records, _ = parse_records(data)
    cards = []
    for record in records:
        for entry, subtitle in enumerate(record.subtitles):
            if subtitle.entry_type != 1:
                continue
            if subtitle.offset in already_matched_offsets:
                continue
            english = decode_western(subtitle.raw)
            has_existing = bool(page3_indices(subtitle.raw))
            if not english.strip() and not has_existing:
                continue
            capacity = len(subtitle.original) - 4 - len(subtitle.tail)
            cards.append({
                "container": kind,
                "record": record.index,
                "entry": entry,
                "offset": subtitle.offset,
                "english": english,
                "capacity": capacity,
                "hasExisting": has_existing,
            })
    return cards


def matched_offsets(seed_csv: Path | None) -> set[int]:
    offsets: set[int] = set()
    if not seed_csv or not seed_csv.exists():
        return offsets
    with seed_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("korean", "").strip() and row.get("offset"):
                offsets.add(int(row["offset"]))
    return offsets


def load_korean_pool(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("kind") != "dialogue":
                continue
            if row.get("target") == "codec":
                continue
            rows.append({
                "page": int(row["page"]),
                "speaker": row.get("speaker", ""),
                "text": row.get("text", "").strip(),
                "target": row.get("target", ""),
            })
    return rows


PAGE_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MGS3D 대사 고르기 (평면 목록)</title><style>
:root{--bg:#11151b;--panel:#1b222c;--line:#364251;--text:#e8edf3;--muted:#9ba9b8;
--good:#75d69c;--warn:#ffd166;--sel:#2c4a6b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.45 system-ui,'Malgun Gothic',sans-serif;height:100vh;display:flex;flex-direction:column}
header{padding:8px 14px;border-bottom:1px solid var(--line);display:flex;gap:10px;
align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0}
select,input,button{background:var(--panel);color:var(--text);border:1px solid var(--line);
border-radius:5px;padding:5px 8px;font:inherit}
button{cursor:pointer}button.primary{border-color:#40916c;color:var(--good)}
#stats{color:var(--muted);font-size:12px;margin-left:auto}
main{flex:1;display:flex;overflow:hidden}
.pane{flex:1;display:flex;flex-direction:column;border-right:1px solid var(--line);min-width:0}
.pane:last-child{border-right:none}
.panehead{padding:8px 12px;border-bottom:1px solid var(--line);display:flex;gap:6px}
.panehead input{flex:1}
.rows{flex:1;overflow:auto}
.row{padding:7px 12px;border-bottom:1px solid #202834;cursor:pointer}
.row:hover{background:#182029}
.row.sel{background:var(--sel)}
.row.used{opacity:.35}
.row .meta{color:var(--muted);font-size:11px;display:block}
.row .existing{color:var(--warn);font-size:11px}
.assign{padding:10px 14px;border-top:1px solid var(--line);background:var(--panel)}
.assign textarea{width:100%;min-height:50px;background:#0d1218;color:var(--text);
border:1px solid var(--line);border-radius:5px;padding:6px;font:inherit}
.assign .row2{display:flex;gap:8px;margin-top:6px;align-items:center}
.spk{color:#9cd3ff}
</style></head><body>
<header>
<h1>MGS3D 대사 고르기</h1>
<select id="container"></select>
<span id="stats"></span>
<button class="primary" id="save">할당된 것 CSV 저장</button>
</header>
<main>
<div class="pane" id="enpane">
  <div class="panehead"><input type="search" id="enq" placeholder="영문 카드 검색 (복수 선택: 클릭 여러 개)">
  <label><input type="checkbox" id="hideused"> 완료 숨기기</label></div>
  <div class="rows" id="enrows"></div>
</div>
<div class="pane" id="kopane">
  <div class="panehead"><input type="search" id="koq" placeholder="한글 대사 검색"></div>
  <div class="rows" id="korows"></div>
</div>
</main>
<div class="assign" id="assignbox" style="display:none">
  <div class="meta" id="assigninfo"></div>
  <textarea id="assigntext"></textarea>
  <div class="row2">
    <button class="primary" id="confirm">선택한 카드에 배정</button>
    <button id="cancel">선택 해제</button>
    <span class="meta">여러 카드를 선택했으면 단어 수 비례로 자동 분배됩니다. 나눈 후 직접 다듬으세요.</span>
  </div>
</div>
<script>
const CONTAINERS = __CONTAINERS__;
const KOREAN = __KOREAN__;
let active = 0;
const selectedCards = new Set();
let selectedKorean = null;
const assigned = {}; // container -> {offset: text}
CONTAINERS.forEach(c => assigned[c.name] = {});

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function renderEn(){
  const c = CONTAINERS[active];
  const q = $('#enq').value.trim().toLowerCase();
  const hideUsed = $('#hideused').checked;
  const box = $('#enrows');
  box.innerHTML = '';
  let shown = 0;
  c.cards.forEach(card => {
    const used = assigned[c.name][card.offset] !== undefined;
    if (hideUsed && used) return;
    if (q && !card.english.toLowerCase().includes(q)) return;
    shown++;
    const div = document.createElement('div');
    div.className = 'row' + (selectedCards.has(card.offset) ? ' sel' : '') + (used ? ' used' : '');
    div.dataset.offset = card.offset;
    div.innerHTML = `${esc(card.english) || '<span class="meta">(디코드 안 됨)</span>'}
      <span class="meta">rec ${card.record}/e${card.entry} · ${card.capacity}B${used ? ' · 배정됨' : ''}</span>
      ${card.hasExisting ? '<div class="existing">⚠ 이미 글리프 있음</div>' : ''}`;
    box.appendChild(div);
  });
  $('#stats').textContent = `${c.name} · 카드 ${shown}/${c.cards.length} 표시 · `
    + `배정 완료 ${Object.keys(assigned[c.name]).length}`;
}

function renderKo(){
  const q = $('#koq').value.trim().toLowerCase();
  const box = $('#korows');
  box.innerHTML = '';
  let n = 0;
  for (const line of KOREAN) {
    if (q && !line.text.toLowerCase().includes(q)) continue;
    if (++n > 300) break;
    const div = document.createElement('div');
    div.className = 'row' + (selectedKorean === line ? ' sel' : '');
    div.dataset.idx = KOREAN.indexOf(line);
    div.innerHTML = `<span class="spk">${esc(line.speaker)}</span> ${esc(line.text)}
      <span class="meta">p${line.page} · ${line.target || 'unknown'}</span>`;
    box.appendChild(div);
  }
}

$('#enrows').addEventListener('click', e => {
  const row = e.target.closest('.row');
  if (!row) return;
  const off = row.dataset.offset;
  if (selectedCards.has(off)) selectedCards.delete(off); else selectedCards.add(off);
  renderEn();
  updateAssignBox();
});
$('#korows').addEventListener('click', e => {
  const row = e.target.closest('.row');
  if (!row) return;
  selectedKorean = KOREAN[+row.dataset.idx];
  renderKo();
  updateAssignBox();
});

function updateAssignBox(){
  const box = $('#assignbox');
  if (selectedCards.size === 0) { box.style.display = 'none'; return; }
  box.style.display = 'block';
  $('#assigninfo').textContent = `선택된 카드 ${selectedCards.size}개`
    + (selectedKorean ? ` · 한글: ${selectedKorean.speaker} "${selectedKorean.text.slice(0,40)}..."` : ' · 한글 미선택');
  if (selectedKorean && !$('#assigntext').dataset.dirty) {
    $('#assigntext').value = selectedKorean.text;
  }
}
$('#assigntext').addEventListener('input', () => { $('#assigntext').dataset.dirty = '1'; });

$('#confirm').addEventListener('click', () => {
  const c = CONTAINERS[active];
  const text = $('#assigntext').value.trim();
  if (!text || selectedCards.size === 0) return;
  const offsets = [...selectedCards];
  if (offsets.length === 1) {
    assigned[c.name][offsets[0]] = text;
  } else {
    const words = text.split(/\\s+/).filter(Boolean);
    const cardsByOffset = Object.fromEntries(c.cards.map(x => [String(x.offset), x]));
    const weights = offsets.map(o => Math.max(1, (cardsByOffset[o]?.capacity) || 1));
    const total = weights.reduce((a,b)=>a+b,0);
    let used = 0, start = 0;
    offsets.forEach((o, i) => {
      used += weights[i];
      const end = i === offsets.length - 1 ? words.length : Math.round(used/total*words.length);
      assigned[c.name][o] = words.slice(start, end).join(' ');
      start = end;
    });
  }
  selectedCards.clear(); selectedKorean = null;
  $('#assigntext').value = ''; $('#assigntext').dataset.dirty = '';
  renderEn(); renderKo(); updateAssignBox();
});
$('#cancel').addEventListener('click', () => {
  selectedCards.clear(); selectedKorean = null;
  $('#assigntext').value = ''; $('#assigntext').dataset.dirty = '';
  renderEn(); renderKo(); updateAssignBox();
});

$('#enq').addEventListener('input', renderEn);
$('#hideused').addEventListener('change', renderEn);
$('#koq').addEventListener('input', renderKo);
$('#container').addEventListener('change', e => {
  active = +e.target.value; selectedCards.clear(); renderEn(); updateAssignBox();
});

function csvCell(v){ v = String(v ?? ''); return /[",\\r\\n]/.test(v) ? '"' + v.replaceAll('"','""') + '"' : v; }
$('#save').addEventListener('click', () => {
  const c = CONTAINERS[active];
  const fields = ['accept','record','entry','offset','capacity','english','korean'];
  const lines = [fields.join(',')];
  c.cards.forEach(card => {
    const t = assigned[c.name][card.offset];
    if (t === undefined) return;
    lines.push(['yes',card.record,card.entry,card.offset,card.capacity,card.english,t].map(csvCell).join(','));
  });
  const blob = new Blob(['\\ufeff'+lines.join('\\r\\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = c.name + '_flat_picked.csv';
  a.click(); URL.revokeObjectURL(a.href);
});

CONTAINERS.forEach((c,i) => $('#container').insertAdjacentHTML('beforeend',
  `<option value="${i}">${esc(c.name)} (${c.cards.length}장 남음)</option>`));
renderEn(); renderKo();
</script></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--korean-script", type=Path, required=True,
                        help="script_ref_mgs3_classified.csv")
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--movie-matched", type=Path,
                        help="CSV of already-matched movie cards to exclude")
    parser.add_argument("--demo-matched", type=Path,
                        help="CSV of already-matched demo cards to exclude")
    args = parser.parse_args()

    korean = load_korean_pool(args.korean_script)
    containers = []
    if args.movie:
        offsets = matched_offsets(args.movie_matched)
        containers.append({"name": "movie",
                          "cards": load_remaining_cards("movie", args.movie, offsets)})
    if args.demo:
        offsets = matched_offsets(args.demo_matched)
        containers.append({"name": "demo",
                          "cards": load_remaining_cards("demo", args.demo, offsets)})
    if not containers:
        parser.error("provide --movie and/or --demo")

    page = (PAGE_TEMPLATE
            .replace("__CONTAINERS__", json.dumps(containers, ensure_ascii=False))
            .replace("__KOREAN__", json.dumps(korean, ensure_ascii=False)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")

    for c in containers:
        print(f"{c['name']}: {len(c['cards'])} remaining cards")
    print(f"korean pool: {len(korean)} lines")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
