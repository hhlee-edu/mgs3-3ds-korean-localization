#!/usr/bin/env python3
"""One file with every line that still renders English, and what it needs.

The English left on screen is almost never "untranslated" -- it is translated
text that was dropped because it does not fit its fixed byte slot. This gathers
those lines from all three media into a single worklist so shortening happens in
one place instead of three.

Per row it gives the exact byte budget, how many bytes are over, roughly how many
Hangul syllables that is, the surrounding lines for context, and any character
the glyph page cannot render.

`speaker` is filled only where the dialogue itself carries evidence: a codec call
is one GCX between Snake and one partner, so a vocative names the *other* party
and aggregating vocatives across a GCX names the partner. There is no speaker
field anywhere in the game data -- `radio_picture` ids exist only in the
encyclopedia index, and `translation/20_matching/mgs3d_script_comparison.csv` is
keyed to stale parser offsets (2,719 of its 3,031 keys are not in the master and
the text similarity of the rest is ~0.10). So roughly 30% of codec rows get a
partner and the rest are left blank rather than guessed.

    python tools/mgs3d_dialogue_worklist.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 8)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_rendered  # noqa: E402
import mgs3d_movie_tool  # noqa: E402

MASTER = ROOT / "translation/10_master/current"
BUILD = ROOT / "translation/40_build_input/v0.81"
CHARMAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
OUT = ROOT / "translation/10_master/review"
CLEAN_ROMFS = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs"

PARTNER = {
    "Snake": "스네이크", "Jack": "스네이크", "Boss": "더 보스",
    "Major": "소령", "Zero": "소령", "Tom": "소령",
    "Para-Medic": "패러메딕", "Sigint": "시긴토", "EVA": "에바", "Eva": "에바",
    "Ocelot": "오셀롯", "Volgin": "볼긴", "Sokolov": "소콜로프",
    "Granin": "그라닌", "Raikov": "라이코프", "Adam": "아담",
}
VOC = re.compile(r"(?:^|[.!?,]\s+|\s)(" +
                 "|".join(map(re.escape, sorted(PARTNER, key=len, reverse=True))) +
                 r")\s*[,!?.]")
# Korean-side names, used as weaker "mentioned in this conversation" evidence.
KO_NAMES = {
    "스네이크": "스네이크", "더 보스": "더 보스", "보스": "더 보스",
    "소령": "소령", "제로": "소령", "패러메딕": "패러메딕", "시긴토": "시긴토",
    "에바": "에바", "오셀롯": "오셀롯", "볼긴": "볼긴", "소콜로프": "소콜로프",
    "그라닌": "그라닌", "라이코프": "라이코프", "아담": "아담",
}
EN_MENTION = re.compile("|".join(map(re.escape, sorted(PARTNER, key=len, reverse=True))))
KO_MENTION = re.compile("|".join(map(re.escape, sorted(KO_NAMES, key=len, reverse=True))))
HANGUL = re.compile(r"[가-힣]")


def infer_partner(lines):
    """(name, evidence) for a conversation. Vocatives are strong evidence;
    a name merely appearing anywhere in the same conversation is weak."""
    strong, weak = Counter(), Counter()
    for english, korean in lines:
        for m in VOC.finditer(english or ""):
            strong[PARTNER[m.group(1)]] += 1
        for m in EN_MENTION.finditer(english or ""):
            weak[PARTNER[m.group(0)]] += 1
        for m in KO_MENTION.finditer(korean or ""):
            weak[KO_NAMES[m.group(0)]] += 1
    for pool, label in ((strong, "vocative"), (weak, "mentioned")):
        others = {k: v for k, v in pool.items() if k != "스네이크"}
        if others:
            return max(others, key=others.get), label
    return "", ""


def load_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def accepted(row):
    return (row.get("accept") or "").strip().lower() in ("yes", "y", "1", "true")


def encoded_len(text, cmap):
    try:
        return len(parse_rendered(text, cmap)), ""
    except Exception as exc:
        return None, str(exc)[:60]


def bad_chars(text, cmap):
    out = []
    for ch in text or "":
        if HANGUL.match(ch) and ch not in cmap:
            if ch not in out:
                out.append(ch)
    return "".join(out)


def codec_rows(cmap):
    excluded = json.loads((BUILD / "codec-excluded-rows.json").read_text(encoding="utf-8"))
    dropped = {(str(r["gcx"]), str(r["resource"])): r for r in excluded["rows"]}
    master = load_csv(MASTER / "codec.csv")
    real = [r for r in master
            if (r.get("is_donor") or "").strip().lower() != "yes"
            or (str(r.get("gcx")), str(r.get("resource"))) in dropped]

    by_gcx = defaultdict(list)
    for r in real:
        by_gcx[str(r.get("gcx"))].append(r)
    for lst in by_gcx.values():
        lst.sort(key=lambda r: int(r.get("resource") or 0))

    partner = {}
    for gcx, lst in by_gcx.items():
        name, why = infer_partner([(r.get("english"), r.get("korean")) for r in lst])
        if name:
            partner[gcx] = (name, why)

    position = {(str(r.get("gcx")), str(r.get("resource"))): i
                for g, lst in by_gcx.items() for i, r in enumerate(lst)}

    def ctx(row, delta):
        g = str(row.get("gcx"))
        i = position[(g, str(row.get("resource")))] + delta
        lst = by_gcx[g]
        return (lst[i].get("english") or "").strip() if 0 <= i < len(lst) else ""

    out = []
    for r in real:
        key = (str(r.get("gcx")), str(r.get("resource")))
        korean = (r.get("korean") or "").strip()
        english = (r.get("english") or "").strip()
        drop = dropped.get(key)
        if drop:
            status, budget = "CAPACITY", drop.get("original_bytes")
            used = drop.get("korean_bytes")
        elif accepted(r) or not korean:
            continue                       # shipping in Korean, or nothing to shorten
        else:
            status = "HELD"                # translated but deliberately not approved
            budget, _ = encoded_len(english, cmap)
            used, _ = encoded_len(korean, cmap)
        over = (used - budget) if (used is not None and budget is not None) else None
        g = str(r.get("gcx"))
        out.append({
            "media": "codec",
            "key": f"gcx{g}/res{r.get('resource')}",
            "gcx": g,
            "resource": r.get("resource"),
            "status": status,
            # codec capacity is a whole-record gate, not a per-row slot, so the
            # media-only budget columns stay blank rather than carrying a number
            # that would invite the same "shorten to exactly budget" mistake.
            "budget_source": "codec-record",
            "wrap_overhead": "",
            "raw_budget": "",
            "speaker": partner.get(g, ("", ""))[0],
            "speaker_evidence": partner.get(g, ("", ""))[1],
            "english": english,
            "korean": korean,
            "korean_new": "",
            "bytes_budget": budget,
            "bytes_used": used,
            "bytes_over": over,
            "hangul_to_cut": math.ceil(over / 2) if over and over > 0 else 0,
            "unusable_chars": bad_chars(korean, cmap),
            "ctx_prev": ctx(r, -1),
            "ctx_next": ctx(r, 1),
        })
    return out


def media_capacity(media):
    """Per-offset budget as the *encoder* computes it, not as the CSV `size` says.

    Two independent errors came from using `size`. The budget is really
    `len(original) - 4 - len(tail)`, and the used size is measured *after*
    `wrap_like_source` re-inserts the source's line breaks, which costs bytes the
    raw encoded length does not show. A row shortened to land exactly on `size`
    was therefore still over -- the 17 rows v0.81 shortened and failed anyway
    (docs/v0.82-plan-2026-08-16.md).

    Returns {offset: (capacity_bytes, needed_bytes, deficit_bytes)}; empty when
    the clean media file is unavailable, so callers fall back with a warning
    rather than silently reverting to the wrong model.
    """
    source = CLEAN_ROMFS / f"{media}.dat"
    translation = MASTER / f"{media}.csv"
    if not source.exists():
        return {}
    _, records, _ = mgs3d_movie_tool.parse_records(source.read_bytes())
    replacements = mgs3d_movie_tool.read_replacements(translation)
    # The combined fixed+global map, exactly as the media build uses it. Passing
    # None here silently reverts to the pre-global-page per-record font model,
    # which reports every Hangul character as missing and every needed_bytes as
    # None -- the failure mode this function exists to avoid.
    static_map = mgs3d_movie_tool.load_static_character_map(CHARMAP)
    out = {}
    for record in records:
        local = {s.offset: replacements[s.offset]
                 for s in record.subtitles if s.offset in replacements}
        if not local:
            continue
        for entry in mgs3d_movie_tool.fixed_capacity(record, local, static_map)["entries"]:
            out[entry["offset"]] = (entry["capacity_bytes"],
                                    entry["needed_bytes"],
                                    entry["deficit_bytes"])
    return out


def media_rows(media, cmap):
    master = load_csv(MASTER / f"{media}.csv")
    capacity = media_capacity(media)
    if not capacity:
        print(f"WARNING: no encoder capacity for {media}; "
              f"falling back to the CSV size column, which under-reports by "
              f"the line-wrap overhead", file=sys.stderr)
    safe = {(r.get("offset"), r.get("index")): r for r in load_csv(BUILD / f"{media}-safe.csv")}
    ordered = sorted(master, key=lambda r: int(r.get("offset") or 0))
    position = {(r.get("offset"), r.get("index")): i for i, r in enumerate(ordered)}
    by_record = defaultdict(list)
    for r in master:
        by_record[str(r.get("record"))].append(r)
    partner = {}
    for rec, lst in by_record.items():
        name, why = infer_partner([(r.get("preview") or r.get("raw_text"), r.get("korean"))
                                   for r in lst])
        if name:
            partner[rec] = (name, why)

    def ctx(row, delta):
        i = position[(row.get("offset"), row.get("index"))] + delta
        if 0 <= i < len(ordered):
            return (ordered[i].get("preview") or ordered[i].get("raw_text") or "").strip()
        return ""

    out = []
    for r in master:
        if not accepted(r):
            continue
        s = safe.get((r.get("offset"), r.get("index")))
        if s is not None and accepted(s):
            continue                       # made it into the build
        korean = (r.get("korean") or "").strip()
        raw_used, err = encoded_len(korean, cmap)
        measured = capacity.get(int(r.get("offset") or -1))
        if measured is not None:
            budget, used, over = measured
            if used is None:                    # unencodable: no byte verdict
                used, over = raw_used, None
            budget_source = "encoder"
        else:
            budget = int(r.get("size") or 0)
            used = raw_used
            over = (used - budget) if used is not None else None
            budget_source = "csv-size"
        # What a rewrite must fit in its own raw encoded length: the wrap step
        # adds bytes the translator never sees in the text they type.
        overhead = (used - raw_used) if (used is not None and raw_used is not None) else None
        out.append({
            "media": media,
            "key": f"{media}@{r.get('offset')}",
            "gcx": "",
            "resource": r.get("index"),
            "status": "CAPACITY",
            "budget_source": budget_source,
            "wrap_overhead": overhead,
            "raw_budget": (budget - overhead) if (budget is not None and overhead is not None) else None,
            "speaker": partner.get(str(r.get("record")), ("", ""))[0],
            "speaker_evidence": partner.get(str(r.get("record")), ("", ""))[1],
            "english": (r.get("preview") or r.get("raw_text") or "").strip(),
            "korean": korean,
            "korean_new": "",
            "bytes_budget": budget,
            "bytes_used": used,
            "bytes_over": over,
            "hangul_to_cut": math.ceil(over / 2) if over and over > 0 else 0,
            "unusable_chars": bad_chars(korean, cmap) or err,
            "ctx_prev": ctx(r, -1),
            "ctx_next": ctx(r, 1),
        })
    return out


def main() -> int:
    global BUILD
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--build-input", type=Path, default=BUILD,
                    help="directory holding the current safe-subset outputs")
    args = ap.parse_args()
    BUILD = args.build_input
    args.out.mkdir(parents=True, exist_ok=True)

    cmap = {c: bytes.fromhex(t)
            for c, t in json.loads(CHARMAP.read_text(encoding="utf-8"))["characters"].items()}

    rows = codec_rows(cmap) + media_rows("movie", cmap) + media_rows("demo", cmap)
    rows.sort(key=lambda r: (r["media"], -(r["bytes_over"] or 0)))

    # An empty worklist means every accepted line now fits -- the goal state, not
    # an error. Write the header alone so the file stays readable and diffable
    # instead of indexing rows[0] and raising.
    FIELDS = ["media", "key", "gcx", "resource", "status", "budget_source",
              "wrap_overhead", "raw_budget", "speaker", "speaker_evidence",
              "english", "korean", "korean_new", "bytes_budget", "bytes_used",
              "bytes_over", "hangul_to_cut", "unusable_chars", "ctx_prev", "ctx_next"]
    path = args.out / "dialogue-worklist.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else FIELDS)
        w.writeheader()
        w.writerows(rows)

    glyphs = args.out / "allowed-glyphs.txt"
    hangul = sorted(c for c in cmap if HANGUL.match(c))
    glyphs.write_text(
        "MGS3D에서 쓸 수 있는 한글 " + str(len(hangul)) + "자.\n"
        "여기 없는 글자는 화면에 빈칸으로 나온다. 한 줄에 50자씩.\n"
        "ASCII(영문/숫자/기호)는 전부 사용 가능하다.\n\n"
        + "\n".join("".join(hangul[i:i + 50]) for i in range(0, len(hangul), 50)) + "\n",
        encoding="utf-8")

    tally = Counter((r["media"], r["status"]) for r in rows)
    print(f"worklist: {len(rows)} rows -> {path}")
    for k, v in sorted(tally.items()):
        print(f"  {k[0]:6s} {k[1]:10s} {v}")
    print(f"  with a speaker: {sum(1 for r in rows if r['speaker'])}")
    print(f"  unusable chars: {sum(1 for r in rows if r['unusable_chars'])}")
    print(f"allowed glyphs: {len(hangul)} -> {glyphs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
