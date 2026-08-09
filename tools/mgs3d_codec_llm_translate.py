#!/usr/bin/env python3
"""Prepare a batch-translation job for codec.dat lines with no PS2 match and
no Korean text yet (`is_donor=no`, `korean` empty in the master review CSV),
for translation via a local Ollama (Qwen) API — same worker as the
movie/demo pipeline (`mgs3d_llm_translate_worker.py`).

Unlike movie/demo, these lines have no PS2/GameFAQs reference line by
definition (`PS2대응없음` means there was never a PS2 match) and no scene
structure, so the prompt is simpler: just the display text and a speaker
placeholder. No byte/glyph budget is enforced at this stage — get a
natural, complete Korean draft first; fitting it into each GCX's actual
capacity is a separate later pass (see the GCX shortening workflow already
used for codec's other leftover translations).

Language tagging in the master CSV is known to be unreliable for a chunk of
these rows (some `is_donor=no` rows actually contain French/Spanish text,
not English) — rows that look French/Spanish/German/Italian after accent
decoding are filtered out entirely rather than translated. Per an explicit
2026-08-08 project rule, only English and Korean matter; non-English/
non-Korean donor-language text is disposable (it gets stripped for byte
capacity regardless) and not worth spending translation effort on.

Usage:
    python3 mgs3d_codec_llm_translate.py \\
        --review analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv \\
        --prepare-only analysis/ps2_korean/full_build/rebuild_2026-08-08/codec_llm_batch.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

csv.field_size_limit(2**31 - 1)

SYSTEM_PROMPT = """당신은 메탈기어 솔리드 3(스네이크 이터)를 3DS로 이식한 \
한국어 팬 로컬라이제이션의 번역가입니다. 게임 코덱(무전) 대사 한 줄을 \
자연스러운 구어체 한국어로 번역하세요.

규칙:
- 번역 대상은 오직 [번역 대상] 표시가 붙은 한 줄뿐입니다.
- 대사 톤은 밀리터리/스파이 스릴러이고, 무전 통신(코덱) 특유의 간결한 \
말투를 씁니다.
- 결과는 한글(및 필요한 경우 영문 고유명사/숫자)만 사용하세요. 키릴 문자 등 \
다른 문자 체계를 섞지 마세요.
- 결과는 오직 번역된 한국어 대사 한 줄만 출력하세요. 설명, 따옴표, \
원문 반복 없이 번역문만 출력합니다.
- 이 단계에서는 글자수 제한이 없습니다. 뜻이 자연스럽게 전달되도록 \
완전한 문장으로 번역하세요."""

# `raw_text` encodes Western accented characters as `<1F>` followed by one
# literal suffix byte (not to be confused with the `english` column's
# already-corrupted `<1f6a>`-style rendering, which pads the character with
# spaces and destroys word boundaries). Mapping inferred empirically from
# ~30 suffix bytes' worth of surrounding French/Spanish word context
# (e.g. "D<1F>jsol<1F>j" = "Désolé", "S<1F>n" = "Sí", "<1F>@Qu<1F>" = "¿Qu...").
ACCENT_MAP = {
    "j": "é", "J": "É",
    "b": "á", "B": "Á",
    "n": "í", "N": "Í",
    "a": "à",
    "t": "ó",
    "i": "è",
    "k": "ê",
    "h": "ç", "H": "Ç",
    "{": "ú", "[": "Ú",
    "r": "ñ",
    "u": "ô",
    "|": "û",
    "z": "ù",
    "c": "â",
    "o": "î",
    "@": "¿",
    '"': "¡",
}
ACCENT_TOKEN = re.compile(r"<1F>(.)")
OTHER_TOKEN = re.compile(r"<[0-9A-Za-z]{1,4}>")


def clean_text(raw: str) -> str:
    text = raw.split("<00>")[0]
    text = text.replace("<0A>", " ")
    text = ACCENT_TOKEN.sub(lambda m: ACCENT_MAP.get(m.group(1), ""), text)
    text = OTHER_TOKEN.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


# Only English/Korean matter (2026-08-08 project rule) — anything that
# decodes to French/Spanish/German/Italian is skipped rather than
# translated. High recall matters more than precision here: the cost of
# wrongly skipping a genuine English line is low (it just waits for a later
# pass), while translating donor-language text wastes Ollama time on text
# that gets discarded anyway.
FOREIGN_ACCENTS = re.compile("[éÉáÁíÍóÓúÚàÀèÈêÊçÇñÑôÔûÛùÙâÂîÎ¿¡]")
FOREIGN_WORDS = set("""
le la les un une des du de et a au aux ce ces cette cet il elle ils elles je tu
nous vous on que qui quoi ou mais donc car pas ne pour par sur sous dans avec
sans chez entre vers depuis pendant avant apres alors ca ceci cela mon ton son
ma ta sa mes tes ses notre votre leur est sont suis es etes sommes avoir etre
fais fait faire tres plus moins bien bon oui non merci aussi encore deja
toujours jamais rien tout tous toute toutes quelque quelques comme si crois
dessus toi moi lui meme beaucoup peu assez trop
el los las una unos unas del al y o quien donde porque como ni se su sus mi
mis nuestro nuestra vuestro vuestra yo ella nosotros vosotros ellos ellas son
soy eres somos estar ser mas buena si gracias tambien siempre nunca nada
todo todos toda todas algo alguna algunas esto eso esta este aqui alli ahora
entonces cuando hasta desde para con sin sobre dame vuelvas espero eh
""".split())
FOREIGN_TOKEN = re.compile(r"[a-zA-Z]+")


def looks_foreign(text: str) -> bool:
    if FOREIGN_ACCENTS.search(text):
        return True
    words = set(FOREIGN_TOKEN.findall(text.casefold()))
    return bool(words & FOREIGN_WORDS)


def build_prompt(row: dict) -> str:
    lines = [
        "[캐릭터] 코덱 통신 (화자 불명)",
        f"[번역 대상 — 이 줄만 한국어로 번역] {row['source_en']}",
        "\n번역:",
    ]
    return "\n".join(lines)


def load_rows(review: Path) -> list[dict]:
    with review.open(encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        candidates = [r for r in reader
                     if r.get("is_donor") == "no" and not r.get("korean", "").strip()]

    rows: list[dict] = []
    skipped_foreign = 0
    for r in candidates:
        text = clean_text(r["raw_text"])
        if not text:
            continue
        if looks_foreign(text):
            skipped_foreign += 1
            continue
        rows.append({
            "id": f"codec-{r['gcx']}-{r['resource']}",
            "container": "codec",
            "gcx": r["gcx"],
            "resource": r["resource"],
            "speaker": "코덱 통신",
            "source_en": text,
            "ref_en": "",
            "char_budget": max(1, len(text)),
            "context": [],
        })
    print(f"skipped {skipped_foreign} non-English (French/Spanish/German/Italian) rows")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True,
                        help="codec-3ds-INTEGRATED-review.csv")
    parser.add_argument("--prepare-only", type=Path, required=True,
                        help="write the batch JSON here for mgs3d_llm_translate_worker.py")
    parser.add_argument("--limit", type=int, help="only include the first N rows (testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the first 3 prompts and exit without writing")
    args = parser.parse_args()

    rows = load_rows(args.review)
    if args.limit:
        rows = rows[:args.limit]
    print(f"{len(rows)} codec rows need translation (is_donor=no, korean empty)")

    if args.dry_run:
        for row in rows[:3]:
            print("=" * 40)
            print(build_prompt(row))
        return 0

    args.prepare_only.parent.mkdir(parents=True, exist_ok=True)
    args.prepare_only.write_text(
        json.dumps({"system_prompt": SYSTEM_PROMPT, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"wrote {len(rows)}-row batch to {args.prepare_only} — "
          f"run mgs3d_llm_translate_worker.py against it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
