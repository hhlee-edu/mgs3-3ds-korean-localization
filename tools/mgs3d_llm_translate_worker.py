#!/usr/bin/env python3
"""Standalone Ollama batch-translation worker — no MGS3D dependencies.

Reads a batch JSON produced by `mgs3d_llm_translate.py --prepare-only`
(context, English source/reference lines, speaker, byte budget per row —
no game .dat files needed) and calls a remote Ollama API for each row,
writing results to a CSV as it goes. Pure standard library — safe to copy
to any machine with Python 3.8+ (e.g. a Synology NAS) with no pip install.

Usage:
    python3 mgs3d_llm_translate_worker.py batch.json output.csv \\
        --host http://192.168.1.206:11434 --model qwen3:8b
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def build_prompt(row: dict) -> str:
    lines = [f"[캐릭터] {row.get('speaker', '알 수 없음')}"]
    if row.get("context"):
        lines.append("[앞뒤 문맥 (PS2 원문, 참고용)]")
        for c in row["context"]:
            lines.append(f"  {c['speaker']}: {c['text']}")
    if row.get("script_ref_context"):
        lines.append("[같은 장면의 대사집 참고 대사 — 용어/고유명사 참고용, "
                     "이 줄들을 그대로 베끼지 마세요]")
        for s in row["script_ref_context"]:
            lines.append(f"  {s['speaker']}: {s['text']}")
    lines.append(f"[PS2 참고 대사 — 어투 참고용, 번역 대상 아님] {row['ref_en']}")
    lines.append(f"[번역 대상 — 이 줄만 한국어로 번역] {row['source_en']}")
    lines.append(f"[글자 예산] 한글 기준 약 {row['char_budget']}자 이내")
    lines.append("\n번역:")
    return "\n".join(lines)


def call_ollama(host: str, model: str, system: str, prompt: str, timeout: float) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
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


def already_done(output: Path) -> set[str]:
    if not output.exists():
        return set()
    with output.open(encoding="utf-8-sig", newline="") as stream:
        return {row["id"] for row in csv.DictReader(stream) if row.get("target_ko")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--resume", action="store_true",
                        help="skip rows already present with a non-empty target_ko in output")
    args = parser.parse_args()

    document = json.loads(args.batch.read_text(encoding="utf-8"))
    rows = document["rows"]
    system = document["system_prompt"]
    print(f"{len(rows)} rows in batch")

    skip = already_done(args.output) if args.resume else set()
    if skip:
        print(f"resuming: {len(skip)} rows already done, skipping")

    fields = ["id", "container", "scene", "record", "entry", "offset", "speaker",
             "source_en", "ref_en", "char_budget", "target_ko"]
    mode = "a" if (args.resume and args.output.exists()) else "w"
    write_header = not (args.resume and args.output.exists())
    args.output.parent.mkdir(parents=True, exist_ok=True)

    done = failed = 0
    t0 = time.time()
    with args.output.open(mode, encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        if write_header:
            writer.writeheader()
        for row in rows:
            if row["id"] in skip:
                continue
            prompt = build_prompt(row)
            result = ""
            for attempt in range(args.retries + 1):
                try:
                    result = call_ollama(args.host, args.model, system, prompt, args.timeout)
                    break
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    if attempt < args.retries:
                        print(f"  [{row['id']}] retry {attempt+1} after error: {exc}")
                        time.sleep(3)
                    else:
                        print(f"  [{row['id']}] FAILED after {args.retries+1} attempts: {exc}")
                        failed += 1
            writer.writerow({**{k: row.get(k, "") for k in fields[:-1]}, "target_ko": result})
            stream.flush()
            done += 1
            if done % 10 == 0 or done == len(rows) - len(skip):
                elapsed = time.time() - t0
                print(f"  {done}/{len(rows)-len(skip)} done ({failed} failed), "
                      f"{elapsed:.0f}s elapsed, ~{elapsed/done:.1f}s/row")

    print(f"wrote {args.output}: {done - failed}/{done} translated this run, {failed} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
