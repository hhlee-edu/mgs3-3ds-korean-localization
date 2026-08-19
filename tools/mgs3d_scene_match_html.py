#!/usr/bin/env python3
"""Scene-bundled dialogue matching workbench for movie.dat / demo.dat.

Dialogue is inherently sequential: within one cutscene the speakers just
alternate and the order never changes. So instead of matching 2,900+
subtitle cards one at a time, this groups the cards by *scene* (the
container structure decoded 2026-08-08: a scene is one contiguous
cutscene, and its cards are already in playback order) and asks the
reviewer for a single decision per scene — "which script line does this
scene start at?" — then fills the rest of the scene sequentially from
that anchor.

Output is a self-contained offline HTML page with three columns, as
requested: 3DS dialogue (+ remaining capacity), the Korean script line
auto-aligned from the anchor, and an editable field for the reviewer.
Per-row nudge controls re-sync the alignment when the game splits or
merges a line relative to the script.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import html
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import decode_mgs_preview  # noqa: E402
from mgs3d_demo_scene_compact import trailing_pad_run, walk_blocks  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402
from mgs3d_movie_tool import page3_indices, parse_records  # noqa: E402

SCENE_SIGNATURE = 0x00110001


def scene_starts(data: bytes, blocks: list[tuple[int, int, int]]) -> list[int]:
    """A scene begins at a type-16 tag immediately followed by the 0x110001 tag.

    movie.dat and demo.dat use different values in the first tag (14 vs 2),
    so keying off the second, shared tag detects scenes in both files.
    """
    starts = []
    for i, (off, kind, _) in enumerate(blocks):
        if (kind & 0xFFFF) != 16 or i + 1 >= len(blocks):
            continue
        nxt_off, nxt_kind, _ = blocks[i + 1]
        if (nxt_kind & 0xFFFF) != 16:
            continue
        _, nxt_f3 = struct.unpack_from("<II", data, nxt_off + 8)
        if nxt_f3 == SCENE_SIGNATURE:
            starts.append(off)
    return starts


def load_script(gamefaqs_path: Path, bilingual_path: Path) -> list[dict[str, object]]:
    """Ordered PS2/GameFAQs English lines, each carrying whatever Korean the
    existing English<->the script reference alignment found for it (may be blank).

    English-to-English is the anchor axis (same language as the 3DS card,
    trivial for a human to eyeball-verify) instead of English-to-Korean.
    """
    document = json.loads(gamefaqs_path.read_text(encoding="utf-8"))
    korean_by_seq: dict[int, dict[str, str]] = {}
    if bilingual_path.exists():
        with bilingual_path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                seq = row.get("english_sequence", "").strip()
                korean = row.get("korean", "").strip()
                if not seq or not korean:
                    continue
                seq_i = int(seq)
                existing = korean_by_seq.get(seq_i)
                # Prefer higher-confidence rows if more than one aligns here.
                rank = {"high": 0, "medium": 1, "low": 2}.get(row.get("confidence", ""), 3)
                if existing is None or rank < existing["_rank"]:
                    korean_by_seq[seq_i] = {
                        "korean": korean,
                        "korean_speaker": row.get("korean_speaker", ""),
                        "confidence": row.get("confidence", ""),
                        "_rank": rank,
                    }

    rows = []
    for item in document["dialogues"]:
        seq = int(item["sequence"])
        korean = korean_by_seq.get(seq, {})
        rows.append({
            "index": seq,
            "speaker": item.get("speaker", ""),
            "text": str(item.get("text", "")).strip(),
            "korean": korean.get("korean", ""),
            "korean_speaker": korean.get("korean_speaker", ""),
            "korean_confidence": korean.get("confidence", ""),
        })
    return rows


def build_container(kind: str, dat: Path, script: list[dict[str, object]],
                    seed_csv: Path | None) -> dict[str, object]:
    data = dat.read_bytes()
    blocks = walk_blocks(data)
    starts = scene_starts(data, blocks)
    _, records, _ = parse_records(data)

    bounds = [(s, starts[i + 1] if i + 1 < len(starts) else len(data))
              for i, s in enumerate(starts)]

    # Existing align-dat matches seed each scene's suggested anchor directly
    # via the english_sequence they were already matched to (no back-solving
    # through text needed — this is the same anchor axis as the script).
    seeded: dict[int, int] = {}
    if seed_csv and seed_csv.exists():
        with seed_csv.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                seq = (row.get("english_sequence") or "").strip()
                if seq and row.get("offset"):
                    seeded[int(row["offset"])] = int(seq)

    scenes = []
    for scene_index, (start, end) in enumerate(bounds):
        cards = []
        for record in records:
            if not (start <= record.offset < end):
                continue
            for entry, subtitle in enumerate(record.subtitles):
                if subtitle.entry_type != 1:
                    continue
                english = decode_western(subtitle.raw)
                has_existing = bool(page3_indices(subtitle.raw))
                if not english.strip() and not has_existing:
                    continue
                capacity = len(subtitle.original) - 4 - len(subtitle.tail)
                cards.append({
                    "record": record.index,
                    "entry": entry,
                    "offset": subtitle.offset,
                    "english": english,
                    "preview": decode_mgs_preview(subtitle.raw),
                    "capacity": capacity,
                    "hasExisting": has_existing,
                })
        if not cards:
            continue
        # Suggest the anchor: for each already-matched card, back-calculate
        # what GameFAQs sequence this scene would have started at (using the
        # english_sequence align-dat already found for it), then take the
        # most common answer.
        votes: dict[int, int] = {}
        for position, card in enumerate(cards):
            script_index = seeded.get(int(card["offset"]))
            if script_index is None:
                continue
            guess = script_index - position
            votes[guess] = votes.get(guess, 0) + 1
        anchor = max(votes, key=lambda k: votes[k]) if votes else None
        scenes.append({
            "index": scene_index,
            "start": start,
            "budget": trailing_pad_run(data, end),
            "anchor": anchor,
            "votes": votes.get(anchor, 0) if anchor is not None else 0,
            "cards": cards,
        })
    return {"name": kind, "file": dat.name, "scenes": scenes}


PAGE_TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MGS3D 씬 단위 대사 매칭</title><style>
:root{--bg:#11151b;--panel:#1b222c;--line:#364251;--text:#e8edf3;--muted:#9ba9b8;
--good:#75d69c;--warn:#ffd166;--bad:#ff7b72;--accent:#7cc7ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.5 system-ui,'Malgun Gothic',sans-serif}
header{position:sticky;top:0;z-index:5;background:#11151bf5;border-bottom:1px solid var(--line);padding:10px 16px}
h1{font-size:16px;margin:0 0 8px}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
select,input,button{background:var(--panel);color:var(--text);border:1px solid var(--line);
border-radius:5px;padding:6px 9px;font:inherit}
button{cursor:pointer}button.primary{border-color:#40916c;color:var(--good)}
#stats{color:var(--muted);margin-top:6px;font-size:12px}
main{padding:12px 16px 60px}
.scene{background:var(--panel);border:1px solid var(--line);border-radius:8px;margin:12px 0;padding:12px}
.scene.done{border-color:#40916c}
.scenehead{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.scenehead h2{font-size:15px;margin:0}
.badge{font-size:12px;color:var(--muted);background:#0d1218;border:1px solid var(--line);
border-radius:4px;padding:2px 7px}
.badge.ok{color:var(--good);border-color:#2f6b4f}
.badge.over{color:var(--bad);border-color:#7a3b37}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;color:var(--muted);font-weight:600;padding:4px 6px;
border-bottom:1px solid var(--line)}
td{vertical-align:top;padding:5px 6px;border-bottom:1px solid #232c38}
.en{width:34%;color:#c8d6e3;white-space:pre-wrap}
.ko{width:30%;color:#b8e0c4;white-space:pre-wrap;font-size:13px}
.ko .spk{color:var(--muted);font-size:11px;display:block}
.autoko{color:var(--good);margin-top:3px;padding-top:3px;border-top:1px dashed var(--line)}
.hit .autoko{font-size:12px}
.mine{width:30%}
.mine textarea{width:100%;min-height:46px;background:#0d1218;color:var(--text);
border:1px solid var(--line);border-radius:4px;padding:5px;font:inherit;resize:vertical}
.mine textarea.over{border-color:var(--bad)}
.meta{font-size:11px;color:var(--muted)}
.nudge{width:6%;white-space:nowrap}
.nudge button{padding:1px 6px;font-size:12px;line-height:1.2}
.anchorbox{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.anchorbox input[type=search]{min-width:260px}
.block{border:1px solid #232c38;border-radius:6px;margin:8px 0;padding:8px}
.blockhead{display:flex;gap:8px;align-items:center;margin-bottom:6px}
.blocklabel{font-size:12px;color:var(--accent);font-weight:600}
.blockhead button{font-size:12px;padding:2px 8px}
.hits,.rowhits{max-height:150px;overflow:auto;border:1px solid var(--line);border-radius:5px;
background:#0d1218;width:100%;margin-top:4px}
.hit{padding:5px 8px;cursor:pointer;border-bottom:1px solid #202834;font-size:13px}
.hit:hover{background:#182029}
.hit .spk{color:var(--muted);font-size:11px}
.existing{color:var(--warn);font-size:12px;margin:3px 0}
.usebtn{margin-left:6px;padding:0 6px;font-size:11px;cursor:pointer;
background:#173a2a;color:var(--good);border:1px solid #2f6b4f;border-radius:4px}
</style></head><body>
<header>
<h1>MGS3D 씬 단위 대사 매칭 — 씬마다 첫 대사만 맞추면 나머지는 자동</h1>
<div class="controls">
<select id="container"></select>
<select id="filter">
<option value="">모든 씬</option>
<option value="todo">미완료 씬만</option>
<option value="done">완료 씬만</option>
</select>
<input id="find" type="search" placeholder="영어 대사 검색으로 씬 찾기">
<button class="primary" id="save">현재 표 CSV 저장</button>
<button id="export">진행상황 저장(JSON)</button>
<label class="badge" style="cursor:pointer">진행상황 불러오기
<input id="import" type="file" accept=".json" style="display:none"></label>
</div>
<div id="stats"></div>
</header>
<main id="list"></main>
<script>
const DATA = __DATA__;
const SCRIPT = __SCRIPT__;
let active = 0;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// state[container][sceneIndex] = {anchor:int|null, shifts:{cardPos:int}, text:{offset:str}}
const state = DATA.map(c => c.scenes.map(s => ({anchor: s.anchor, shifts: {}, text: {}})));

const isHangul = ch => ch >= '\\uAC00' && ch <= '\\uD7A3';
function encodedLen(t){ let n = 0; for (const ch of t) n += isHangul(ch) ? 2 : 1; return n + 1; }

// Script line assigned to card `pos` = anchor + pos + accumulated shifts up to pos.
function getBlocks(scene){
  const blocks = [];
  scene.cards.forEach((card, pos) => {
    const last = blocks[blocks.length - 1];
    if (last && last.record === card.record) last.items.push([card, pos]);
    else blocks.push({record: card.record, items: [[card, pos]]});
  });
  return blocks;
}

function scriptIndexFor(st, pos){
  if (st.anchor === null || st.anchor === undefined) return null;
  let extra = 0;
  for (const k in st.shifts) if (+k <= pos) extra += st.shifts[k];
  return st.anchor + pos + extra;
}

function sceneCost(scene, st){
  // Estimate: bytes past each card's own capacity, plus 64 per new unique
  // Hangul character per record. Real gate is the build; this is guidance.
  let over = 0;
  const perRecord = {};
  scene.cards.forEach(card => {
    const t = (st.text[card.offset] || '').trim();
    if (!t) return;
    over += Math.max(0, encodedLen(t) - card.capacity);
    (perRecord[card.record] = perRecord[card.record] || new Set());
    for (const ch of t) if (isHangul(ch)) perRecord[card.record].add(ch);
  });
  let glyphs = 0;
  for (const r in perRecord) glyphs += perRecord[r].size;
  return over + glyphs * 64;
}

function filledCount(scene, st){
  return scene.cards.filter(c => (st.text[c.offset] || '').trim()).length;
}

function render(){
  const container = DATA[active];
  const sts = state[active];
  const mode = $('#filter').value;
  const q = $('#find').value.trim().toLowerCase();
  const list = $('#list');
  list.innerHTML = '';

  let totalCards = 0, totalFilled = 0, doneScenes = 0;
  container.scenes.forEach((scene, i) => {
    totalCards += scene.cards.length;
    const f = filledCount(scene, sts[i]);
    totalFilled += f;
    if (f === scene.cards.length) doneScenes++;
  });
  $('#stats').textContent =
    `${container.file} · 씬 ${container.scenes.length}개 · 완료 씬 ${doneScenes}`
    + ` · 카드 ${totalFilled}/${totalCards} 채움`;

  container.scenes.forEach((scene, i) => {
    const st = sts[i];
    const f = filledCount(scene, st);
    const done = f === scene.cards.length;
    if (mode === 'todo' && done) return;
    if (mode === 'done' && !done) return;
    if (q && !scene.cards.some(c => c.english.toLowerCase().includes(q))) return;

    const cost = sceneCost(scene, st);
    const over = cost > scene.budget;
    const box = document.createElement('section');
    box.className = 'scene' + (done ? ' done' : '');
    box.innerHTML =
      `<div class="scenehead">
        <h2>씬 #${scene.index}</h2>
        <span class="badge">카드 ${f}/${scene.cards.length}</span>
        <span class="badge ${over ? 'over' : 'ok'}">여유 ${scene.budget}B · 예상 사용 ${cost}B</span>
        ${scene.votes ? `<span class="badge">자동제안 근거 ${scene.votes}줄</span>` : ''}
       </div>
       <div class="anchorbox">
         <span class="meta">시작 대사:</span>
         <input type="search" class="anchorfind" data-s="${i}" placeholder="영문 대사(3DS 카드와 비교)로 검색해서 이 씬의 첫 대사 지정">
         <span class="badge">${st.anchor === null || st.anchor === undefined
            ? '미지정' : '스크립트 #' + st.anchor}</span>
         <button data-clear="${i}">해제</button>
         <div class="hits" data-hits="${i}" style="display:none"></div>
       </div>`;

    // Group this scene's cards by record ("block") — records are already in
    // scene order, so consecutive same-record cards form a natural chunk.
    const blocks = getBlocks(scene);

    blocks.forEach((block, blockIndex) => {
      const blockFilled = block.items.filter(([c]) => (st.text[c.offset] || '').trim()).length;
      const blockDiv = document.createElement('div');
      blockDiv.className = 'block';
      blockDiv.innerHTML = `<div class="blockhead">
        <span class="blocklabel">블록 (레코드 ${block.record})</span>
        <span class="badge">${blockFilled}/${block.items.length}</span>
        <button data-fillblock="${i}:${blockIndex}">이 블록만 대사집대로 채우기</button>
      </div>`;
      const table = document.createElement('table');
      table.innerHTML =
        `<thead><tr><th class="en">3DS 영문 대사 (잔여용량)</th><th class="nudge">맞춤</th>
         <th class="ko">PS2 영문(GameFAQs) · 자동 한글</th><th class="mine">넣을 한글</th></tr></thead>`;
      const tbody = document.createElement('tbody');
      block.items.forEach(([card, pos]) => {
        const si = scriptIndexFor(st, pos);
        const line = (si !== null && si >= 0 && si < SCRIPT.length) ? SCRIPT[si] : null;
        const mine = st.text[card.offset] || '';
        const cardOver = mine && encodedLen(mine) > card.capacity;
        const tr = document.createElement('tr');
        let koCell = '<span class="meta">—</span>';
        if (line) {
          koCell = `<span class="spk">${esc(line.speaker)} · #${si}</span>${esc(line.text)}`;
          if (line.korean) {
            koCell += `<div class="autoko">${esc(line.korean)}`
              + ` <span class="meta">(${esc(line.korean_confidence)})</span>`
              + ` <button class="usebtn" data-use="${i}:${card.offset}:${si}">이걸로 채우기</button></div>`;
          } else {
            koCell += `<div class="meta">한글 매칭 없음</div>`;
          }
        }
        const enText = card.english.trim()
          ? esc(card.english)
          : `<span class="meta">(영문 디코드 안 됨)</span>`;
        tr.innerHTML =
          `<td class="en">${enText}
             ${card.hasExisting ? '<div class="existing">⚠ 이미 글리프 있음 — 원문: '
               + esc(card.preview) + '</div>' : ''}
             <span class="meta">rec ${card.record}/e${card.entry} · ${card.capacity}B</span></td>
           <td class="nudge">
             <button data-shift="${i}:${pos}:-1" title="이 줄부터 대본을 한 줄 위로">▲</button>
             <button data-shift="${i}:${pos}:1" title="이 줄부터 대본을 한 줄 아래로">▼</button>
             <button data-rowfind="${i}:${pos}" title="영문 검색해서 이 줄부터 정렬">🔍</button></td>
           <td class="ko">${koCell}
             <div class="rowhits" data-rowhits="${i}:${pos}" style="display:none"></div></td>
           <td class="mine"><textarea data-t="${i}:${card.offset}"
              class="${cardOver ? 'over' : ''}">${esc(mine)}</textarea></td>`;
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      blockDiv.appendChild(table);
      box.appendChild(blockDiv);
    });

    const fill = document.createElement('button');
    fill.textContent = '이 씬 전체 대사집대로 채우기';
    fill.dataset.fill = i;
    fill.style.marginTop = '8px';
    box.appendChild(fill);
    list.appendChild(box);
  });
}

$('#list').addEventListener('input', e => {
  const t = e.target;
  if (t.matches('[data-t]')) {
    const [si, off] = t.dataset.t.split(':');
    state[active][+si].text[off] = t.value;
    const scene = DATA[active].scenes[+si];
    const st = state[active][+si];
    const badge = t.closest('.scene').querySelector('.badge.ok, .badge.over');
    const cost = sceneCost(scene, st);
    if (badge) {
      badge.textContent = `여유 ${scene.budget}B · 예상 사용 ${cost}B`;
      badge.className = 'badge ' + (cost > scene.budget ? 'over' : 'ok');
    }
    const card = scene.cards.find(c => String(c.offset) === off);
    t.classList.toggle('over', !!t.value && encodedLen(t.value) > card.capacity);
  }
  if (t.matches('.anchorfind')) {
    const si = +t.dataset.s;
    const hits = document.querySelector(`[data-hits="${si}"]`);
    const q = t.value.trim().toLowerCase();
    if (!q) { hits.style.display = 'none'; return; }
    const found = [];
    for (let i = 0; i < SCRIPT.length && found.length < 40; i++)
      if (SCRIPT[i].text.toLowerCase().includes(q)) found.push(i);
    hits.innerHTML = found.map(i =>
      `<div class="hit" data-pick="${si}:${i}">
        <span class="spk">${esc(SCRIPT[i].speaker)} · #${i}</span>${esc(SCRIPT[i].text)}
        ${SCRIPT[i].korean ? `<div class="autoko">${esc(SCRIPT[i].korean)}</div>` : ''}</div>`
    ).join('') || '<div class="hit meta">결과 없음</div>';
    hits.style.display = 'block';
  }
  if (t.matches('.rowsearch')) {
    const [si, pos] = t.dataset.pos.split(':').map(Number);
    const results = t.nextElementSibling;
    const q = t.value.trim().toLowerCase();
    if (!q) { results.innerHTML = ''; return; }
    const found = [];
    for (let i = 0; i < SCRIPT.length && found.length < 40; i++)
      if (SCRIPT[i].text.toLowerCase().includes(q)) found.push(i);
    results.innerHTML = found.map(i =>
      `<div class="hit" data-rowpick="${si}:${pos}:${i}">
        <span class="spk">${esc(SCRIPT[i].speaker)} · #${i}</span>${esc(SCRIPT[i].text)}
        ${SCRIPT[i].korean ? `<div class="autoko">${esc(SCRIPT[i].korean)}</div>` : ''}</div>`
    ).join('') || '<div class="hit meta">결과 없음</div>';
  }
});

function setRowAnchor(sceneIndex, pos, targetScriptIndex){
  const st = state[active][sceneIndex];
  let priorShift = 0;
  for (const k in st.shifts) if (+k < pos) priorShift += st.shifts[k];
  st.shifts[pos] = targetScriptIndex - st.anchor - pos - priorShift;
}

$('#list').addEventListener('click', e => {
  const t = e.target;
  if (t.dataset.pick) {
    const [si, idx] = t.dataset.pick.split(':').map(Number);
    state[active][si].anchor = idx;
    state[active][si].shifts = {};
    render();
  }
  if (t.dataset.clear !== undefined) {
    state[active][+t.dataset.clear].anchor = null;
    render();
  }
  if (t.dataset.shift) {
    const [si, pos, d] = t.dataset.shift.split(':').map(Number);
    const sh = state[active][si].shifts;
    sh[pos] = (sh[pos] || 0) + d;
    render();
  }
  if (t.dataset.fill !== undefined) {
    const si = +t.dataset.fill;
    const scene = DATA[active].scenes[si];
    const st = state[active][si];
    scene.cards.forEach((card, pos) => {
      const idx = scriptIndexFor(st, pos);
      if (idx !== null && idx >= 0 && idx < SCRIPT.length && SCRIPT[idx].korean)
        st.text[card.offset] = SCRIPT[idx].korean;
    });
    render();
  }
  if (t.dataset.fillblock) {
    const [si, blockIndex] = t.dataset.fillblock.split(':').map(Number);
    const scene = DATA[active].scenes[si];
    const st = state[active][si];
    const block = getBlocks(scene)[blockIndex];
    block.items.forEach(([card, pos]) => {
      const idx = scriptIndexFor(st, pos);
      if (idx !== null && idx >= 0 && idx < SCRIPT.length && SCRIPT[idx].korean)
        st.text[card.offset] = SCRIPT[idx].korean;
    });
    render();
  }
  if (t.dataset.use) {
    const [si, off, idx] = t.dataset.use.split(':');
    state[active][+si].text[off] = SCRIPT[+idx].korean;
    render();
  }
  if (t.dataset.rowfind) {
    const box = t.closest('tr').querySelector('.rowhits');
    const already = box.dataset.open === '1';
    box.style.display = already ? 'none' : 'block';
    box.dataset.open = already ? '0' : '1';
    if (!already) {
      box.innerHTML = '<input type="search" class="rowsearch" data-pos="'
        + t.dataset.rowfind + '" placeholder="영문 검색" autofocus>'
        + '<div></div>';
    }
  }
  if (t.dataset.rowpick) {
    const [si, pos, idx] = t.dataset.rowpick.split(':').map(Number);
    setRowAnchor(si, pos, idx);
    render();
  }
});

$('#container').addEventListener('change', e => { active = +e.target.value; render(); });
['filter', 'find'].forEach(id => $('#' + id).addEventListener('input', render));

function csvCell(v){
  v = String(v ?? '');
  return /[",\\r\\n]/.test(v) ? '"' + v.replaceAll('"', '""') + '"' : v;
}
$('#save').addEventListener('click', () => {
  const container = DATA[active];
  const sts = state[active];
  const fields = ['accept','scene','record','entry','offset','capacity','english','korean'];
  const lines = [fields.join(',')];
  container.scenes.forEach((scene, i) => {
    scene.cards.forEach(card => {
      const t = (sts[i].text[card.offset] || '').trim();
      if (!t) return;
      lines.push([ 'yes', scene.index, card.record, card.entry, card.offset,
        card.capacity, card.english, t ].map(csvCell).join(','));
    });
  });
  const blob = new Blob(['\\ufeff' + lines.join('\\r\\n')], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = container.name + '_scene_matched.csv';
  a.click(); URL.revokeObjectURL(a.href);
});

$('#export').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(state)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'scene_match_progress.json';
  a.click(); URL.revokeObjectURL(a.href);
});
$('#import').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  file.text().then(txt => {
    const loaded = JSON.parse(txt);
    loaded.forEach((c, i) => { if (state[i]) state[i] = c; });
    render();
  });
});

DATA.forEach((c, i) => $('#container').insertAdjacentHTML('beforeend',
  `<option value="${i}">${esc(c.name)} (씬 ${c.scenes.length})</option>`));
render();
</script></body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gamefaqs", type=Path, required=True,
                        help="gamefaqs_mgs3_english.json")
    parser.add_argument("--bilingual", type=Path, required=True,
                        help="GameFAQs-English<->the script reference-Korean alignment CSV "
                             "(e.g. movie_demo_only_bilingual.csv)")
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--movie-seed", type=Path)
    parser.add_argument("--demo-seed", type=Path)
    args = parser.parse_args()

    script = load_script(args.gamefaqs, args.bilingual)
    containers = []
    if args.movie:
        containers.append(build_container("movie", args.movie, script, args.movie_seed))
    if args.demo:
        containers.append(build_container("demo", args.demo, script, args.demo_seed))
    if not containers:
        parser.error("provide --movie and/or --demo")

    page = (PAGE_TEMPLATE
            .replace("__DATA__", json.dumps(containers, ensure_ascii=False))
            .replace("__SCRIPT__", json.dumps(script, ensure_ascii=False)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")

    for container in containers:
        anchored = sum(1 for s in container["scenes"] if s["anchor"] is not None)
        cards = sum(len(s["cards"]) for s in container["scenes"])
        print(f"{container['name']}: {len(container['scenes'])} scenes, {cards} cards, "
              f"{anchored} scenes pre-anchored from existing matches")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
