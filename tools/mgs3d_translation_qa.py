"""Cross-file Korean translation QA for codec.dat / movie.dat / demo.dat masters.

Checks that are cheap, deterministic, and have a low false-positive rate. Each
check reports rows so a human can adjudicate; nothing is auto-fixed here.

Checks
------
josa            Korean particle after an English proper noun / glyph term must
                agree with the *pronunciation's* final consonant
                (MISSION -> 미션, ends in ㄴ -> 을/이/은/과/으로;
                 CAMO -> 카모, open syllable -> 를/가/는/와/로).
pronoun         Literal "당신 / 귀하" second-person pronouns, which this
                project treats as machine-translation residue.
register        Formal (합쇼체/해요체) and informal (반말/해라체) endings
                colliding inside one line. Plain 해라체 + 반말 together is
                NORMAL here and is not reported.
glyphcase       Glyph-budget terms must stay uppercase ASCII (MISSION, CAMO,
                LIFE, ...) and must not appear in a half-translated form.
control         Trailing control-code sequence must be preserved relative to
                the reference file, and must never be invented where the
                reference had none.
donor           Leftover Spanish/French/German/Italian source text that should
                never have been translated.
empty           Rows whose English is present but whose Korean is blank or is
                only punctuation/ellipsis.

Usage
-----
    python tools/mgs3d_translation_qa.py                    # all three files
    python tools/mgs3d_translation_qa.py --only codec
    python tools/mgs3d_translation_qa.py --checks josa,pronoun
    python tools/mgs3d_translation_qa.py --report out.txt
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

ROOT = Path(__file__).resolve().parent.parent

TARGETS = {
    "codec": {
        "path": ROOT / "translation/10_master/current/codec.csv",
        "reference": ROOT / "translation/10_master/archive/codec-older/codec-3ds-INTEGRATED-review-direct-v1.csv",
        "korean": "korean",
        "english": "english",
        "key": ("gcx", "resource"),
        "encoding": "utf-8-sig",
        # Most of codec.dat's 22k rows were never selected for translation.
        # Only rows that already carry Korean are in scope for the "empty"
        # check; otherwise it reports the entire untranslated remainder.
        "empty_scope": lambda r: bool((r.get("korean") or "").strip()),
    },
    "movie": {
        "path": ROOT / "translation/10_master/current/movie.csv",
        "reference": None,
        "korean": "korean",
        "english": "raw_text",
        "key": ("index",),
        "encoding": "utf-8-sig",
    },
    "demo": {
        "path": ROOT / "translation/10_master/current/demo.csv",
        "reference": None,
        "korean": "korean",
        "english": "raw_text",
        "key": ("index",),
        "encoding": "utf-8-sig",
    },
}

CTRL = re.compile(r"<[0-9A-Fa-f]{2}>")
TRAIL = re.compile(r"((?:<[0-9A-Fa-f]{2}>)+)[\"'\s]*$")

# --- josa -------------------------------------------------------------------
# Terms kept in English by project rule, with the Korean reading's final
# consonant state. True = reading ends in a consonant (받침 있음).
TERM_HAS_BATCHIM = {
    # closed syllable (받침 있음) -> 을/은/이/과/으로
    "MISSION": True,    # 미션   (ㄴ)
    "ITEM": True,       # 아이템 (ㅁ)
    "MAP": True,        # 맵     (ㅂ)
    "BACKPACK": True,   # 백팩   (ㄱ)
    "Volgin": True,     # 볼긴   (ㄴ)
    "Ocelot": True,     # 오셀롯 (ㅅ)
    # open syllable (받침 없음) -> 를/는/가/와/로
    "CAMO": False,      # 카모
    "LIFE": False,      # 라이프
    "STAMINA": False,   # 스태미나
    "FOOD": False,      # 푸드
    "KNIFE": False,     # 나이프
    "CURE": False,      # 큐어
    "START": False,     # 스타트
    "CIGAR": False,     # 시가
    "C3": False,        # 씨쓰리
    "WIG": False,       # 위그
    "RPG": False,       # 알피지
    "SVD": False,       # 에스브이디
    "Snake": False,     # 스네이크
    "EVA": False,       # 에바
    "Sokolov": False,   # 소콜로프
    "Raikov": False,    # 라이코프
    "Shagohod": False,  # 샤고호드
}

JOSA_PAIRS = [
    # (after-consonant form, after-vowel form)
    ("을", "를"), ("은", "는"), ("이", "가"), ("과", "와"),
    ("으로", "로"), ("이에요", "예요"), ("이야", "야"), ("이라", "라"),
]

# --- register ---------------------------------------------------------------
FORMAL = re.compile(r"(습니다|읍니다|십시오|시오|입니다|합니다|니까|세요|어요|아요|예요|이에요|죠)\s*[.!?…]*\s*$")
INFORMAL = re.compile(r"(?<![가-힣])(다|야|어|아|지|군|네|라|자|해|거다|건가|는가|잖아|잖나)\s*[.!?…]*\s*$")

GLYPH_TERMS = ["MISSION", "CAMO", "LIFE", "STAMINA", "ITEM", "KNIFE", "MAP",
               "BACKPACK", "CURE", "START", "CIGAR", "SUPPRESSOR", "CHAFF"]

# The codec extractor renders accented donor-language characters as <1fXX>
# tokens; their presence is a far stronger signal than any word list, because
# words like "die", "para", "pour", "sono" are also ordinary English or part of
# a character name (Para-Medic).
ACCENT_TOKEN = re.compile(r"<1f[0-9A-Fa-f]{2}>")
DONOR_WORDS = re.compile(
    r"[¿¡]|\b(qué|cómo|está|pero|muy|así|vale|entonces|nadie|"
    r"est-ce|qu'est|c'est|être|dans|avec|très|déjà|alors|voilà|ferais|"
    r"nicht|und|der|das|sehr|warum|"
    r"molto|perché|anche|questo)\b",
    re.IGNORECASE,
)


def has_hangul(s: str) -> bool:
    return any(0xAC00 <= ord(c) <= 0xD7A3 for c in s)


def strip_ctrl(s: str) -> str:
    return CTRL.sub("", s)


QUOTED = re.compile(r"['\"“”‘’].*?['\"“”‘’]")
# Standalone interjections / affirmatives carry no register signal: "네.",
# "예.", "아...", "음...", "저, 어...". Counting them as informal makes almost
# every polite line look like a register clash.
NEUTRAL_FRAGMENT = re.compile(
    r"^[\s,.…!?~-]*(네|예|아|어|음|흠|저|그|아니|응|글쎄|뭐|허|하)"
    r"[\s,.…!?~-]*$"
)


def sentences(korean: str) -> list[str]:
    # Quoted speech deliberately carries the *quoted speaker's* register and
    # must not be compared against the narrator's.
    text = QUOTED.sub(" ", CTRL.sub(" ", korean))
    parts = re.split(r"(?<=[.!?…])\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p or NEUTRAL_FRAGMENT.match(p):
            continue
        if len(re.findall(r"[가-힣]", p)) < 3:
            continue
        out.append(p)
    return out


def check_josa(ko: str) -> list[str]:
    problems = []
    for term, has_batchim in TERM_HAS_BATCHIM.items():
        for cons_form, vowel_form in JOSA_PAIRS:
            wrong = cons_form if not has_batchim else vowel_form
            right = vowel_form if not has_batchim else cons_form
            # match term immediately followed by the wrong particle
            if re.search(re.escape(term) + re.escape(wrong) + r"(?![가-힣])", ko):
                problems.append(f"{term}{wrong} -> {term}{right}")
    return problems


def check_pronoun(ko: str) -> list[str]:
    hits = []
    for m in re.finditer(r"당신|귀하", ko):
        # 귀하 as an adjective (귀하게/귀하신) is not a pronoun
        tail = ko[m.end():m.end() + 1]
        if m.group() == "귀하" and tail in ("게", "신", "다"):
            continue
        hits.append(m.group())
    return hits


def check_register(ko: str) -> list[str]:
    formal, informal = [], []
    for s in sentences(ko):
        if FORMAL.search(s):
            formal.append(s)
        elif INFORMAL.search(s):
            informal.append(s)
    if formal and informal:
        return [f"formal={formal[0]!r} vs informal={informal[0]!r}"]
    return []


def check_glyphcase(ko: str) -> list[str]:
    problems = []
    for term in GLYPH_TERMS:
        for m in re.finditer(term, ko, re.IGNORECASE):
            if m.group() != term:
                problems.append(f"{m.group()} -> {term}")
    return problems


def check_donor(en: str, ko: str) -> list[str]:
    """Donor-language source that nonetheless carries a Korean translation."""
    if not has_hangul(ko):
        return []
    if ACCENT_TOKEN.search(en):
        return [f"donor source (accent tokens) translated: {en[:60]!r}"]
    words = DONOR_WORDS.findall(en)
    if len(set(w.lower() for w in words if w)) >= 2:
        return [f"donor source (words {sorted(set(words))}) translated"]
    return []


def check_empty(en: str, ko: str) -> list[str]:
    if not strip_ctrl(en).strip():
        return []
    body = strip_ctrl(ko).strip()
    if not body:
        return ["korean empty"]
    if not re.search(r"[0-9A-Za-z가-힣]", body):
        return [f"korean is punctuation only: {body!r}"]
    return []


CHECKS = {
    "josa": lambda en, ko: check_josa(ko),
    "pronoun": lambda en, ko: check_pronoun(ko),
    "register": lambda en, ko: check_register(ko),
    "glyphcase": lambda en, ko: check_glyphcase(ko),
    "donor": check_donor,
    "empty": check_empty,
}


def check_control(rows, ref_rows, spec) -> list[tuple[str, str]]:
    """Trailing control codes must match the reference file row-for-row."""
    if ref_rows is None:
        return []
    kc, keyc = spec["korean"], spec["key"]
    ref_by_key = {tuple(r[k] for k in keyc): r for r in ref_rows}
    problems = []
    for r in rows:
        key = tuple(r[k] for k in keyc)
        ref = ref_by_key.get(key)
        if ref is None:
            continue
        cur_m = TRAIL.search(r[kc] or "")
        ref_m = TRAIL.search(ref[kc] or "")
        cur = cur_m.group(1) if cur_m else ""
        ref_t = ref_m.group(1) if ref_m else ""
        # a row that was empty in the reference legitimately gains <0A><00>
        if not (ref[kc] or "").strip() and cur:
            continue
        if cur != ref_t:
            problems.append(("/".join(key), f"trail {ref_t!r} -> {cur!r}"))
    return problems


def run(name: str, spec: dict, checks: list[str], out) -> dict:
    with open(spec["path"], encoding=spec["encoding"]) as f:
        rows = list(csv.DictReader(f))
    ref_rows = None
    if spec["reference"] and spec["reference"].exists():
        with open(spec["reference"], encoding=spec["encoding"]) as f:
            ref_rows = list(csv.DictReader(f))

    kc, ec, keyc = spec["korean"], spec["english"], spec["key"]
    counts = {c: 0 for c in checks}
    out.write(f"\n{'=' * 70}\n{name}: {len(rows)} rows  ({spec['path'].name})\n{'=' * 70}\n")

    for check in checks:
        if check == "control":
            problems = check_control(rows, ref_rows, spec)
            counts[check] = len(problems)
            out.write(f"\n--- {check}: {len(problems)} ---\n")
            for key, msg in problems[:60]:
                out.write(f"  {key}: {msg}\n")
            continue

        fn = CHECKS[check]
        scope = spec.get(f"{check}_scope")
        found = []
        for r in rows:
            ko = r.get(kc) or ""
            en = r.get(ec) or ""
            if not ko.strip() and check != "empty":
                continue
            if scope and not scope(r):
                continue
            hits = fn(en, ko)
            if hits:
                key = "/".join(str(r[k]) for k in keyc)
                found.append((key, hits, en, ko))
        counts[check] = len(found)
        out.write(f"\n--- {check}: {len(found)} ---\n")
        for key, hits, en, ko in found[:60]:
            out.write(f"  {key}: {hits}\n")
            out.write(f"     en={strip_ctrl(en)[:90]!r}\n")
            out.write(f"     ko={ko[:110]!r}\n")
        if len(found) > 60:
            out.write(f"  ... and {len(found) - 60} more\n")
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="comma-separated subset of: " + ",".join(TARGETS))
    ap.add_argument("--checks", default="josa,pronoun,register,glyphcase,control,donor,empty")
    ap.add_argument("--report", type=Path, help="write full report to this file")
    args = ap.parse_args()

    names = args.only.split(",") if args.only else list(TARGETS)
    checks = args.checks.split(",")

    out = open(args.report, "w", encoding="utf-8") if args.report else sys.stdout
    summary = {}
    try:
        for name in names:
            summary[name] = run(name, TARGETS[name], checks, out)
    finally:
        if args.report:
            out.close()

    print(f"{'file':8} " + " ".join(f"{c:>10}" for c in checks))
    for name, counts in summary.items():
        print(f"{name:8} " + " ".join(f"{counts.get(c, 0):>10}" for c in checks))
    if args.report:
        print(f"\nfull report: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
