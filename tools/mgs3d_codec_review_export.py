#!/usr/bin/env python3
"""Export a review worklist for codec text: what still needs translating, and
what is already translated but should still be re-reviewed.

Read-only. Never writes to translation/10_master/current/.

Why there is no `speaker` value filled in: the game data carries none. codec.csv
has no speaker column, `text_kind='identifier'` turned out to be short
interjections rather than names, and the only speaker-tagged artefact
(`translation/20_matching/codec_korean_anchor_review.csv`) covers 299 of ~9,300
rows at `confidence=review` with visibly mismatched pairs. Guessing a speaker
per line would mislead a reviewer, so the column is emitted empty and the
reviewable evidence is provided instead:

  * `ctx_prev2/1`, `ctx_next1/2` -- the surrounding lines of the same GCX
    conversation, donor-language rows filtered out, in resource order. This is
    what actually lets a human or an LLM decide who is speaking.
  * `addressed_to` -- filled ONLY when the English line contains a vocative for
    a known character ("Snake, ...", "..., Major"). Evidence from the line
    itself, not inference.

Usage:
    python tools/mgs3d_codec_review_export.py --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 8)

ROOT = Path(__file__).resolve().parent.parent
CODEC = ROOT / "translation/10_master/current/codec.csv"

# Characters that appear as vocatives in MGS3 codec dialogue.
NAMES = ("Snake", "Boss", "Major", "Zero", "EVA", "Eva", "Para-Medic", "Sigint",
         "Ocelot", "Volgin", "Sokolov", "Adam", "Jack", "Granin", "Raikov")
VOCATIVE = re.compile(r"(?:^|[.!?]\s+)(" + "|".join(NAMES) + r")\s*,|,\s*(" +
                      "|".join(NAMES) + r")\s*[.!?]")
# crude non-English signal: the accent escapes the donor rows carry, plus a few
# high-frequency FR/ES function words that basically never appear in the English
# script on their own.
NON_EN = re.compile(
    r"<1f[0-9a-f]{2}>|\b(?:que|qui|pero|pour|avec|dans|para|como|est|una|eres|"
    r"c'est|d'un|n'est|vous|nous|les|des|une|pourquoi|alors|venga|sin|respuesta|"
    r"aucune|reponse|cuidado|traje|sentinelles|raisons|commence|utiliza|utilise|"
    r"oui|non|merci|gracias|entendido|exactement|nada|nunca|ouais|mais|entonces|"
    r"igual|sigue|esperando|jalo|bien|fais|toi|tirer|dessus|voyons|voir|oublia)\b",
    re.I)
HANGUL = re.compile(r"[가-힣]")
# rows that are engine identifiers / index entries rather than dialogue
IDENTIFIER = re.compile(r"No:\d+/\d+|radio_picture|rd_ani_|radiotest|^[a-z0-9_]+$")


def content_class(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "empty"
    if NON_EN.search(t):
        return "donor_language"
    if IDENTIFIER.search(t):
        return "internal_identifier"
    if len(t) < 6 or " " not in t:
        return "short_token"
    return "dialogue"


def is_donor(row: dict) -> bool:
    return (row.get("is_donor") or "").strip().lower() == "yes"


def accepted(row: dict) -> bool:
    return (row.get("accept") or "").strip().lower() == "yes"


def has_korean(row: dict) -> bool:
    return bool((row.get("korean") or "").strip())


def addressed_to(text: str) -> str:
    found = [g for m in VOCATIVE.finditer(text or "") for g in m.groups() if g]
    seen, out = set(), []
    for name in found:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            out.append(name)
    return "|".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path,
                    default=ROOT / "translation/10_master/review")
    ap.add_argument("--context", type=int, default=2)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(CODEC.open(newline="", encoding="utf-8-sig")))
    real = [r for r in rows if not is_donor(r)]

    # conversation order per GCX, donor rows removed so context stays readable
    by_gcx: dict[str, list[dict]] = defaultdict(list)
    for r in real:
        by_gcx[str(r.get("gcx"))].append(r)
    for g in by_gcx:
        by_gcx[g].sort(key=lambda r: int(r.get("resource") or 0))
    position = {(str(r.get("gcx")), str(r.get("resource"))): i
                for g, lst in by_gcx.items() for i, r in enumerate(lst)}

    def ctx(row: dict, delta: int) -> str:
        g = str(row.get("gcx"))
        i = position[(g, str(row.get("resource")))] + delta
        lst = by_gcx[g]
        if 0 <= i < len(lst):
            return (lst[i].get("english") or "").strip()
        return ""

    out_rows = []
    for r in real:
        korean = (r.get("korean") or "").strip()
        english = (r.get("english") or "").strip()
        if korean and accepted(r):
            state = "translated_in_build"
        elif korean:
            state = "translated_not_approved"
        else:
            state = "needs_translation"
        out_rows.append({
            "state": state,
            "reviewed": "direct-v2" if (r.get("note") or "").strip() else "",
            "gcx": r.get("gcx"),
            "resource": r.get("resource"),
            "speaker": "",
            "addressed_to": addressed_to(english),
            "english": english,
            "korean": korean,
            "ctx_prev2": ctx(r, -2),
            "ctx_prev1": ctx(r, -1),
            "ctx_next1": ctx(r, 1),
            "ctx_next2": ctx(r, 2),
            "prior_source": (r.get("status") or "").strip(),
            "blocker": (r.get("blocker") or "").strip(),
            "record_headroom": (r.get("record_headroom") or "").strip(),
            "content_class": content_class(english),
            "english_looks_non_english": "yes" if NON_EN.search(english) else "",
            "korean_chars": len(HANGUL.findall(korean)),
            "note": (r.get("note") or "").strip(),
        })

    order = {"needs_translation": 0, "translated_not_approved": 1,
             "translated_in_build": 2}
    out_rows.sort(key=lambda r: (order[r["state"]], int(r["gcx"] or 0),
                                 int(r["resource"] or 0)))

    path = args.out / "codec-review-worklist.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    tally = Counter(r["state"] for r in out_rows)
    print(f"codec.csv rows            {len(rows)}")
    print(f"donor rows skipped        {len(rows) - len(real)}")
    print(f"exported                  {len(out_rows)} -> {path}")
    for k in ("needs_translation", "translated_not_approved", "translated_in_build"):
        print(f"  {k:26s} {tally.get(k, 0)}")
    print(f"  marked reviewed (direct-v2) {sum(1 for r in out_rows if r['reviewed'])}")
    from collections import Counter as _C
    print("  content_class among needs_translation:")
    for k, v in _C(r["content_class"] for r in out_rows
                   if r["state"] == "needs_translation").most_common():
        print(f"    {k:22s} {v}")
    print(f"  addressed_to filled         {sum(1 for r in out_rows if r['addressed_to'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
