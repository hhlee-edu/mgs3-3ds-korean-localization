#!/usr/bin/env python3
"""Batch-translate movie.dat/demo.dat cards with no the script reference match via a
local Ollama (Qwen) API, using the same scene/context data the scene-match
review tool already computes.

Only cards whose aligned GameFAQs (PS2) script line has no the script reference
Korean are sent for translation — cards that already have a the script reference
match are left alone (handled separately as "matched" rows, not this
script's job). Each request includes full context: the 3DS card's own
English text, the PS2/GameFAQs reference line for the same position,
neighboring lines for tone, the speaker, and the remaining byte budget so
the model can aim for a length that will actually fit.

Requires an Ollama server reachable over HTTP (e.g. `ollama serve` on a
LAN machine with `OLLAMA_HOST=0.0.0.0` set) with a Qwen model pulled.
Uses only the standard library (urllib) — no new dependency.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_scene_match_html import build_container, load_script  # noqa: E402

SYSTEM_PROMPT = """당신은 메탈기어 솔리드 3(스네이크 이터)를 3DS로 이식한 \
한국어 팬 로컬라이제이션의 번역가입니다. 게임 자막 한 줄을 자연스러운 \
구어체 한국어로 번역하세요.

규칙:
- 번역 대상은 오직 [번역 대상] 표시가 붙은 한 줄뿐입니다. [PS2 참고 대사]는 \
어투/문맥 참고용으로만 쓰고 그 줄 자체를 번역하지 마세요.
- [같은 장면의 대사집 참고 대사]가 있다면, 그 안의 인명/지명/조직명/기술 \
용어의 기존 한글 표기를 최대한 그대로 재사용하세요 (예: 소코로프, 가가린, \
보스토크 로켓). 그 줄들 자체를 번역 결과로 베끼지는 마세요 — 다른 내용의 \
대사입니다.
- 대사 톤은 밀리터리/스파이 스릴러이고, 화자 간 관계(상관-부하, 동료 등)를 \
말투에 반영하세요.
- 참고 대사집 문체(있다면)와 어투를 최대한 맞추세요.
- 결과는 한글(및 필요한 경우 영문 고유명사/숫자)만 사용하세요. 키릴 문자 등 \
다른 문자 체계를 섞지 마세요.
- 결과는 오직 번역된 한국어 대사 한 줄만 출력하세요. 설명, 따옴표, \
원문 반복 없이 번역문만 출력합니다.
- 주어진 글자 예산을 넘지 않도록 간결하게 쓰세요. 예산이 빠듯하면 \
자연스러움을 해치지 않는 선에서 축약하세요."""


def build_prompt(card: dict, context: list[dict]) -> str:
    lines = [f"[캐릭터] {card.get('speaker', '알 수 없음')}"]
    if context:
        lines.append("[앞뒤 문맥 (PS2 원문, 참고용)]")
        for c in context:
            lines.append(f"  {c['speaker']}: {c['text']}")
    script_ref_context = card.get("script_ref_context") or []
    if script_ref_context:
        lines.append("[같은 장면의 대사집 참고 대사 — 용어/고유명사 참고용, "
                     "이 줄들을 그대로 베끼지 마세요]")
        for s in script_ref_context:
            lines.append(f"  {s['speaker']}: {s['text']}")
    lines.append(f"[PS2 참고 대사 — 어투 참고용, 번역 대상 아님] {card['ref_en']}")
    lines.append(f"[번역 대상 — 이 줄만 한국어로 번역] {card['source_en']}")
    lines.append(f"[글자 예산] 한글 기준 약 {card['char_budget']}자 이내")
    lines.append("\n번역:")
    return "\n".join(lines)


def load_bilingual_by_line(bilingual: Path) -> dict[int, list[dict]]:
    by_line: dict[int, list[dict]] = {}
    with bilingual.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                line = int(row.get("english_line", ""))
            except ValueError:
                continue
            if not row.get("korean", "").strip():
                continue
            by_line.setdefault(line, []).append(row)
    return by_line


def nearby_script_ref_context(idx: int, by_line: dict[int, list[dict]],
                             window: int = 10, limit: int = 4) -> list[dict]:
    rank = {"high": 0, "medium": 1, "low": 2}
    candidates = []
    for offset in range(-window, window + 1):
        for row in by_line.get(idx + offset, []):
            candidates.append((abs(offset), rank.get(row.get("confidence", ""), 3), row))
    candidates.sort(key=lambda item: (item[0], item[1]))
    seen: set[str] = set()
    picked: list[dict] = []
    for _, _, row in candidates:
        text = row["korean"].strip()
        if text in seen:
            continue
        seen.add(text)
        picked.append({"speaker": row.get("korean_speaker", ""), "text": text})
        if len(picked) >= limit:
            break
    return picked


def call_ollama(host: str, model: str, prompt: str, timeout: float) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body.get("response", "").strip()


def load_batch(gamefaqs: Path, bilingual: Path, dat: Path, kind: str,
               seed: Path | None) -> list[dict]:
    script = load_script(gamefaqs, bilingual)
    by_index = {r["index"]: r for r in script}
    by_line = load_bilingual_by_line(bilingual)
    container = build_container(kind, dat, script, seed)
    rows: list[dict] = []
    for scene in container["scenes"]:
        anchor = scene["anchor"]
        if anchor is None:
            continue
        for pos, card in enumerate(scene["cards"]):
            idx = anchor + pos
            line = by_index.get(idx)
            if not line or line["korean"]:
                continue  # already has a the script reference match; not this script's job
            if card.get("hasExisting"):
                continue  # already has embedded glyphs; don't overwrite blindly
            context = [by_index[j] for j in range(idx - 2, idx + 3)
                      if j != idx and j in by_index and by_index[j]["text"]]
            rows.append({
                "id": f"{kind}-{card['record']}-{card['entry']}",
                "container": kind,
                "scene": scene["index"],
                "record": card["record"],
                "entry": card["entry"],
                "offset": card["offset"],
                "speaker": line["speaker"],
                "source_en": card["english"],
                "ref_en": line["text"],
                "char_budget": max(1, card["capacity"] // 2),
                "context": context,
                "script_ref_context": nearby_script_ref_context(idx, by_line),
                "target_ko": "",
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="output CSV")
    parser.add_argument("--gamefaqs", type=Path, required=True)
    parser.add_argument("--bilingual", type=Path, required=True)
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--movie-seed", type=Path)
    parser.add_argument("--demo-seed", type=Path)
    parser.add_argument("--host", default="http://localhost:11434",
                        help="Ollama API base URL, e.g. http://192.168.x.x:11434")
    parser.add_argument("--model", default="qwen2.5:14b-instruct")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--limit", type=int, help="only process the first N rows (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the batch and print prompts without calling Ollama")
    parser.add_argument("--prepare-only", type=Path,
                        help="write the batch (with context, no .dat files needed downstream) "
                             "to this JSON path instead of calling Ollama — hand the JSON plus "
                             "mgs3d_llm_translate_worker.py to a machine that can reach Ollama")
    args = parser.parse_args()

    rows: list[dict] = []
    if args.movie:
        rows += load_batch(args.gamefaqs, args.bilingual, args.movie, "movie", args.movie_seed)
    if args.demo:
        rows += load_batch(args.gamefaqs, args.bilingual, args.demo, "demo", args.demo_seed)
    if not rows:
        parser.error("provide --movie and/or --demo")

    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} cards need translation (no the script reference match, no existing glyphs)")

    if args.dry_run:
        for row in rows[:3]:
            print("=" * 40)
            print(build_prompt(row, row["context"]))
        print(f"... ({len(rows)} total, showing first 3)")
        return 0

    if args.prepare_only:
        batch = [{
            "id": row["id"], "container": row["container"], "scene": row["scene"],
            "record": row["record"], "entry": row["entry"], "offset": row["offset"],
            "speaker": row["speaker"], "source_en": row["source_en"], "ref_en": row["ref_en"],
            "char_budget": row["char_budget"],
            "context": [{"speaker": c["speaker"], "text": c["text"]} for c in row["context"]],
            "script_ref_context": row["script_ref_context"],
        } for row in rows]
        args.prepare_only.parent.mkdir(parents=True, exist_ok=True)
        args.prepare_only.write_text(
            json.dumps({"system_prompt": SYSTEM_PROMPT, "rows": batch}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"wrote {len(batch)}-row batch to {args.prepare_only} "
              f"(no further .dat access needed, run mgs3d_llm_translate_worker.py on it)")
        return 0

    fields = ["id", "container", "scene", "record", "entry", "offset", "speaker",
             "source_en", "ref_en", "char_budget", "target_ko"]
    done = 0
    failed = 0
    t0 = time.time()
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            prompt = build_prompt(row, row["context"])
            try:
                result = call_ollama(args.host, args.model, prompt, args.timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"  [{row['id']}] FAILED: {exc}")
                result = ""
                failed += 1
            row["target_ko"] = result
            writer.writerow({k: row[k] for k in fields})
            stream.flush()
            done += 1
            if done % 25 == 0 or done == len(rows):
                elapsed = time.time() - t0
                print(f"  {done}/{len(rows)} done ({failed} failed), "
                      f"{elapsed:.0f}s elapsed, ~{elapsed/done:.1f}s/card")

    print(f"wrote {args.output}: {done - failed}/{len(rows)} translated, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
