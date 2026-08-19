#!/usr/bin/env python3
"""movie/demo register + address + MT-literal QA candidate extractor.

The codec register pass could lean on an external script that named the speaker
for each line. movie.dat/demo.dat have no speaker field and no external script
keyed to their offsets, so the unit of review here is the **record**: one record
is one cutscene, and its entries are in playback order. That gives the
surrounding dialogue a flat string search cannot.

READ-ONLY. It reads the masters and writes candidate/context CSVs. It never
rewrites Korean, never touches a build, never stages anything. Machine judgement
stops at "this is worth a human/AI look in context"; the actual verdict is made
against the printed context, not by these regexes.

Detectors:

  INTRA_LINE_MIXED   one line mixes 존댓말 and 반말 with itself
  RECORD_REGISTER_SPLIT
                     a record carries both registers -- normal for a two-speaker
                     scene, drift for a monologue, so it is a *candidate* only
  ADDRESS_TERM       competing address/kinship terms for one referent
                     (아버지/아빠, 어머니/엄마, 당신/너/자네/그대)
  NAME_SCRIPT_SPLIT  one proper noun written both in Latin and in Hangul
  MT_LITERAL         literal-translation markers (그것은/그는 openers, ~에 의해,
                     ~하고 있다, possessive 나의/너의/그의, 중 하나 ...)
  PUNCT_SPACING      space before sentence punctuation ("이군 .")
  ENGLISH_RESIDUE    ordinary English vocabulary left inside a Korean line

Usage:
  python tools/mgs3d_media_register_qa.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mgs3d_confirmed_register_qa import classify_register, clean_korean  # noqa: E402

csv.field_size_limit(10 ** 9)

# The codec classifier deliberately leaves `-해.`-class endings `unknown`: for the
# codec pass that was the safe direction, because an unknown line was simply not
# proposed. Here the same gap costs recall on subtitle text, which is short and
# leans on exactly those endings, so the media classifier layers two extra reads
# on top of it *without* touching the codec one.
#
# 하오체 gets its own class rather than being folded into 존댓말: Ocelot and The
# Boss use it, and a speaker sliding between 하오체 and 반말 is drift worth seeing,
# while 하오체 next to 존댓말 usually is not.
ARCHAIC = re.compile(
    r"(?:하오|이오|되오|(?<!십)시오|겠소|았소|었소|보오|주오|구려|그렇소|맞소|없소|있소|"
    r"아니오|말이오|것이오)(?:[.!?…\"']|$)")
# 하오체 also contracts to a bare `-요` after a noun ("전차요", "볼긴은 올 거요"),
# which the 해요체 `-요` rule reads as 존댓말. The two are only separable in
# context, so a bare `-요`/`-오`/`-소` ending is re-read as 하오체 *only* inside a
# record that already speaks 하오체 -- see refine_archaic().
BARE_HAOCHE = re.compile(r"(?<![아어에여지네으세])[요오소](?:[.!?…\"']|$)")
PLAIN_EXTRA = re.compile(
    r"(?:해|돼|봐|줘|와|마|래|건가|는가|은가|을까|ㄹ까|거야|거든|잖아|더군|는군|누구냐|"
    r"뭐야|그래)(?:[.!?…\"']|$)")


def classify_register_media(text: str) -> str:
    """`polite` | `archaic` | `plain` | `mixed` | `unknown` for one subtitle line."""
    cleaned_first = clean_korean(text)
    if cleaned_first and ARCHAIC.search(cleaned_first):
        return "archaic"
    base = classify_register(text)
    if base != "unknown":
        return base
    cleaned = clean_korean(text)
    if not cleaned:
        return "unknown"
    clauses = [c.strip() for c in re.split(r"(?<=[.!?…])\s+", cleaned) if c.strip()]
    archaic = plain = 0
    for clause in clauses or [cleaned]:
        if ARCHAIC.search(clause):
            archaic += 1
        elif PLAIN_EXTRA.search(clause):
            plain += 1
    if archaic and plain:
        return "mixed"
    if archaic:
        return "archaic"
    if plain:
        return "plain"
    return "unknown"

ROOT = Path(__file__).resolve().parent.parent
MASTERS = ROOT / "translation/10_master/current"
CONTEXT = 3          # lines of surrounding dialogue carried into the candidate row

# --- address / kinship terms that must not compete inside one referent -------
ADDRESS_SETS = {
    "father": ("아버지", "아빠", "부친"),
    "mother": ("어머니", "엄마", "모친"),
    "second_person": ("당신", "자네", "그대"),
}

# --- MT-literal markers ------------------------------------------------------
MT_PATTERNS = [
    ("opener_it_he_she", re.compile(r"(?:^|[.!?…]\s*)(그것은|그것이|그는|그녀는|그들은)\s")),
    ("passive_by", re.compile(r"에\s*의해")),
    ("progressive", re.compile(r"하고\s*있(?:다|었다|습니다)")),
    ("possessive_pronoun", re.compile(r"(?:나의|너의|그의|그녀의|우리의|당신의)\s")),
    ("one_of", re.compile(r"중\s*하나")),
    ("about_that", re.compile(r"에\s*대(?:해서|하여|한)\s")),
    ("have_got", re.compile(r"을\s*가지고\s*있")),
    ("conj_opener", re.compile(r"^(?:그리고|그러나|그래서)\s")),
]

PUNCT_SPACE = re.compile(r"\s+[.!?,…]")
HANGUL = re.compile(r"[가-힣]")
LATIN_NAME = re.compile(r"\b[A-Z][A-Za-z'\-]{2,}\b")
LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")

# Latin words that are not proper nouns of the kind we track.
LATIN_STOP = {"END", "The", "And", "But", "Not", "You", "Yes", "This", "That", "What"}


def load_master(name: str) -> list[dict]:
    with io.open(MASTERS / f"{name}.csv", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["media"] = name
        row["record_i"] = int(row["record"])
        row["entry_i"] = int(row["entry"])
        row["ko"] = clean_korean(row.get("korean") or "")
        # `clean_korean` normalises away a space before . ! ? …, which is exactly
        # the defect PUNCT_SPACING looks for, so keep an un-normalised view too.
        raw = re.sub(r"<[^>]*>", " ", row.get("korean") or "")
        row["ko_raw"] = re.sub(r"[ \t]+", " ", raw.replace("|", " ")).strip()
        row["en"] = re.sub(r"<[^>]*>", " ", row.get("preview") or "").replace("|", " ")
        row["en"] = re.sub(r"\s+", " ", row["en"]).strip()
        row["register"] = classify_register_media(row.get("korean") or "")
    rows.sort(key=lambda r: (r["record_i"], r["entry_i"]))
    return rows


def common_english_words(rows: list[dict]) -> set[str]:
    """English words that are ordinary vocabulary rather than proper nouns.

    A word counts as ordinary if the English subtitles ever write it lowercase
    mid-sentence. `Snake`/`Sokolov`/`KGB` never do, so they stay out and a Korean
    line keeping them is a script-consistency question, not untranslated text."""
    lower: Counter[str] = Counter()
    upper: Counter[str] = Counter()
    for row in rows:
        for match in LATIN_WORD.finditer(row["en"]):
            (lower if match.group().islower() else upper)[match.group().lower()] += 1
    return {w for w, n in lower.items() if n >= 2 and len(w) > 1}


def refine_archaic(records: dict) -> int:
    """Second pass: inside a record that already speaks 하오체, a `polite` line whose
    only politeness marker is a bare `-요`/`-오`/`-소` is the same 하오체 speaker, not
    a 존댓말 one. Sokolov is the reason this exists -- his whole introduction reads
    as 하오체 and half of it was landing in the 존댓말 bucket."""
    changed = 0
    for block in records.values():
        if sum(1 for r in block if r["register"] == "archaic") < 2:
            continue
        for row in block:
            if row["register"] == "polite" and BARE_HAOCHE.search(row["ko"]):
                row["register"] = "archaic"
                changed += 1
    return changed


def name_script_conflicts(rows: list[dict]) -> dict[str, set[str]]:
    """Proper nouns that appear in Latin in one line and in Hangul in another.

    The Hangul side is found by looking at the English line's proper nouns: if a
    name is Latin in one Korean line and simply absent (transliterated) in
    another Korean line whose English carries the same name, the two lines
    disagree about script. That is the only evidence available without a
    romanisation table, and it is reported, not acted on."""
    latin_lines: dict[str, set[str]] = defaultdict(set)
    hangul_lines: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for name in LATIN_NAME.findall(row["en"]):
            if name in LATIN_STOP:
                continue
            tag = f"{row['media']}:{row['record_i']}:{row['entry_i']}"
            if re.search(r"\b" + re.escape(name) + r"\b", row["ko"]):
                latin_lines[name].add(tag)
            elif HANGUL.search(row["ko"]):
                hangul_lines[name].add(tag)
    return {n: latin_lines[n] | hangul_lines[n]
            for n in latin_lines if latin_lines[n] and hangul_lines[n]}


def flag_line(row: dict, conflict_names: set[str], common: set[str]) -> list[str]:
    flags: list[str] = []
    korean = row["ko"]
    # A Korean line still carrying ordinary English vocabulary ("그게 real weapon.",
    # "US family 보고 싶었어...") is untranslated text, not a naming choice. These
    # read as capacity-forced abbreviations rather than translation decisions.
    residue = sorted({w.group().lower() for w in LATIN_WORD.finditer(korean)
                      if w.group().lower() in common})
    if residue and HANGUL.search(korean):
        flags.append("ENGLISH_RESIDUE:" + ",".join(residue[:3]))
    if row["register"] == "mixed":
        flags.append("INTRA_LINE_MIXED")
    for group, terms in ADDRESS_SETS.items():
        hits = [t for t in terms if t in korean]
        if len(hits) > 1:
            flags.append(f"ADDRESS_TERM:{group}")
    for label, pattern in MT_PATTERNS:
        if pattern.search(korean):
            flags.append(f"MT_LITERAL:{label}")
    if PUNCT_SPACE.search(row["ko_raw"]):
        flags.append("PUNCT_SPACING")
    for name in LATIN_NAME.findall(row["en"]):
        if name in conflict_names and re.search(r"\b" + re.escape(name) + r"\b", korean):
            flags.append(f"NAME_SCRIPT_SPLIT:{name}")
            break
    return flags


def corpus_address_conflicts(rows: list[dict]) -> dict[str, Counter]:
    """Which competing terms the corpus actually uses, and how often."""
    result: dict[str, Counter] = {}
    for group, terms in ADDRESS_SETS.items():
        counter = Counter()
        for row in rows:
            for term in terms:
                counter[term] += row["ko"].count(term)
        if sum(1 for t in terms if counter[t]) > 1:
            result[group] = counter
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    rows = load_master("movie") + load_master("demo")
    conflicts = name_script_conflicts(rows)
    conflict_names = set(conflicts)
    common = common_english_words(rows)

    records: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        records[(row["media"], row["record_i"])].append(row)
    reclassified = refine_archaic(records)

    # A record carrying two registers is normal when two people are talking. What
    # is worth reading is the *minority* side: one or two 존댓말 lines inside an
    # otherwise 반말 scene is what register drift looks like. Flagging all 485
    # lines of every split record buries that, so only the minority lines are
    # flagged and the rest of the record travels with them as context.
    split_records = {}
    for key, block in records.items():
        counts = Counter(r["register"] for r in block
                         if r["register"] in ("polite", "plain", "archaic"))
        if len(counts) > 1:
            majority = counts.most_common(1)[0][0]
            split_records[key] = (majority, counts)

    for row in rows:
        row["flags"] = flag_line(row, conflict_names, common)
        key = (row["media"], row["record_i"])
        if key in split_records:
            majority, counts = split_records[key]
            if row["register"] in counts and row["register"] != majority:
                row["flags"].append(
                    f"RECORD_REGISTER_SPLIT:{row['register']}_in_{majority}")

    context_fields = ["media", "record", "entry", "register", "flags", "english", "korean"]
    with (args.outdir / "media-register-context.csv").open("w", encoding="utf-8-sig",
                                                           newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=context_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({"media": row["media"], "record": row["record_i"],
                             "entry": row["entry_i"], "register": row["register"],
                             "flags": ";".join(row["flags"]),
                             "english": row["en"], "korean": row.get("korean") or ""})

    candidate_fields = ["media", "record", "entry", "flags", "register", "english", "korean",
                        "context_before", "context_after", "verdict", "korean_new", "reason"]
    candidates = []
    for key, block in records.items():
        for position, row in enumerate(block):
            if not row["flags"]:
                continue
            before = block[max(0, position - CONTEXT):position]
            after = block[position + 1:position + 1 + CONTEXT]

            def render(lines):
                return " || ".join(
                    f"[{l['register'][:2]}] {l['en'][:60]} => {l['ko'][:60]}" for l in lines)

            candidates.append({
                "media": row["media"], "record": row["record_i"], "entry": row["entry_i"],
                "flags": ";".join(row["flags"]), "register": row["register"],
                "english": row["en"], "korean": row.get("korean") or "",
                "context_before": render(before), "context_after": render(after),
                "verdict": "", "korean_new": "", "reason": "",
            })
    candidates.sort(key=lambda c: (c["media"], c["record"], c["entry"]))
    with (args.outdir / "media-register-candidates.csv").open("w", encoding="utf-8-sig",
                                                              newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=candidate_fields)
        writer.writeheader()
        writer.writerows(candidates)

    flag_counts: Counter = Counter()
    for row in rows:
        for flag in row["flags"]:
            flag_counts[flag.split(":")[0]] += 1
    summary = {
        "lines": len(rows),
        "movie_lines": sum(1 for r in rows if r["media"] == "movie"),
        "demo_lines": sum(1 for r in rows if r["media"] == "demo"),
        "records": len(records),
        "register_distribution": dict(Counter(r["register"] for r in rows).most_common()),
        "records_with_both_registers": len(split_records),
        "haoche_reclassified": reclassified,
        "flagged_lines": len(candidates),
        "flag_counts": dict(flag_counts.most_common()),
        "address_term_usage": {g: dict(c) for g, c in corpus_address_conflicts(rows).items()},
        "name_script_conflicts": {n: len(v) for n, v in sorted(
            conflicts.items(), key=lambda kv: -len(kv[1]))},
    }
    (args.outdir / "media-register-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
