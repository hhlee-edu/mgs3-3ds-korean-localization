#!/usr/bin/env python3
"""Cross-check the codec master against the Shinsnote script, in one review file.

Shinsnote is the only material in the project that carries a **speaker** for codec
dialogue -- the game data has no speaker field at all -- so it is the practical
basis for reviewing register (존댓말/반말) as well as wording. It is used here as an
independent QA reference and is never written into the master.

Two structural facts drive the matching:

* Shinsnote merges what the game splits. `p1 s74` holds both `gcx 15 res 14` and
  `res 15`, so a master line is usually a *substring* of a Shinsnote line, not
  equal to it. Matching is therefore containment-based, not 1:1.
* Short interjections (`What?`, `But...`, `That's right.`) repeat hundreds of
  times and cannot be resolved by text alone. They are only accepted when a
  neighbouring line in the same GCX also matches, and are otherwise reported as
  AMBIGUOUS rather than guessed.

Confirmed anchors from `codec_korean_anchor_review.csv` (`accept=yes`) are carried
through untouched; nothing already confirmed is downgraded here.

    python tools/mgs3d_codec_shinsnote_review.py
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

MASTER = ROOT / "translation/10_master/current/codec.csv"
SHINS = ROOT / "translation/20_matching/shinsnote/shinsnote_mgs3_classified.csv"
ANCHORS = ROOT / "translation/20_matching/codec_korean_anchor_review.csv"
CHARMAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
OUT = ROOT / "translation/10_master/review/codec-shinsnote-review.csv"

TOKEN = re.compile(r"<[0-9A-Fa-f]{2}>")
MIN_ANCHORABLE = 8          # normalised Korean chars below which text alone is not proof


def kstrip(text: str) -> str:
    """Normalise Korean for comparison: drop control tokens, spaces, punctuation."""
    t = TOKEN.sub("", text or "")
    return re.sub(r"[\s.,!?…\"'\-~·:;()\[\]]", "", t)


def has_hangul(text: str) -> bool:
    return any("가" <= c <= "힣" for c in text or "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    csv.field_size_limit(10 ** 9)
    charmap = json.loads(CHARMAP.read_text(encoding="utf-8"))["characters"]
    master = list(csv.DictReader(io.open(MASTER, encoding="utf-8-sig", newline="")))
    shins = [r for r in csv.DictReader(io.open(SHINS, encoding="utf-8-sig", newline=""))
             if r.get("target") == "codec" and has_hangul(r.get("text"))]

    confirmed = set()
    if ANCHORS.exists():
        for r in csv.DictReader(io.open(ANCHORS, encoding="utf-8-sig", newline="")):
            if (r.get("accept") or "").strip().lower() in ("y", "yes", "1", "ok"):
                try:
                    confirmed.add((int(r["gcx"]), int(r["resource"])))
                except (KeyError, ValueError):
                    pass

    # Shinsnote index: normalised text -> entries, plus a haystack for containment
    sh_entries = []
    for r in shins:
        sh_entries.append({
            "page": r.get("page", ""), "seq": r.get("sequence", ""),
            "speaker": r.get("speaker", ""), "text": (r.get("text") or "").strip(),
            "norm": kstrip(r.get("text")),
        })

    def accepted(r):
        return (r.get("accept") or "").strip().lower() in ("y", "yes", "1", "ok")

    # master rows keyed by gcx for neighbour corroboration
    by_gcx = defaultdict(list)
    for r in master:
        if r.get("is_donor") == "yes" or r.get("text_kind") != "display_text":
            continue
        try:
            by_gcx[int(r["gcx"])].append(r)
        except (KeyError, ValueError):
            pass
    for lst in by_gcx.values():
        lst.sort(key=lambda r: int(r["resource"]))

    def match_row(korean):
        """Return (entry, kind) for the best Shinsnote containment match."""
        n = kstrip(korean)
        if not n:
            return None, ""
        exact = [e for e in sh_entries if e["norm"] == n]
        if exact:
            return exact[0], "exact"
        contained = [e for e in sh_entries if n in e["norm"]]
        if contained:
            return min(contained, key=lambda e: len(e["norm"])), "contained"
        return None, ""

    # First pass: which GCX does Shinsnote actually cover, and how strongly.
    anchored_gcx: Counter[int] = Counter()
    for r in master:
        if r.get("is_donor") == "yes" or r.get("text_kind") != "display_text":
            continue
        k = (r.get("korean") or "").strip()
        if not has_hangul(k) or len(kstrip(k)) < MIN_ANCHORABLE:
            continue
        if match_row(k)[0] is not None:
            try:
                anchored_gcx[int(r["gcx"])] += 1
            except (KeyError, ValueError):
                pass

    rows = []
    stats = Counter()
    for r in master:
        if r.get("is_donor") == "yes" or r.get("text_kind") != "display_text":
            continue
        korean = (r.get("korean") or "").strip()
        english = (r.get("english") or "").strip()
        note = r.get("note") or ""
        recovered = "recovered from" in note
        try:
            gcx, res = int(r["gcx"]), int(r["resource"])
        except (KeyError, ValueError):
            continue

        entry, kind = (None, "")
        if has_hangul(korean):
            entry, kind = match_row(korean)

        n = kstrip(korean)
        short = len(n) < MIN_ANCHORABLE

        if not has_hangul(korean):
            status, reason = "ENGLISH_REMAINS", "no Korean in master"
        elif entry is None:
            # Shinsnote covers only 414 codec lines against ~9,500 master rows, so
            # "no match" is usually just absence of a reference, not a defect. Only
            # call it a mismatch when Shinsnote clearly covers the same beat.
            status, reason = ("NO_SHINSNOTE_REF",
                              "Shinsnote has no line for this dialogue")
        elif (gcx, res) in confirmed:
            status, reason = "SHINSNOTE_MATCH", "confirmed anchor (preserved)"
        elif short:
            # corroborate with a neighbour in the same GCX before trusting it
            neigh = [x for x in by_gcx.get(gcx, []) if x is not r
                     and has_hangul(x.get("korean") or "")
                     and abs(int(x["resource"]) - res) <= 2]
            ok = any(match_row(x.get("korean"))[0] is not None
                     and len(kstrip(x.get("korean"))) >= MIN_ANCHORABLE for x in neigh)
            status = "SHINSNOTE_MATCH" if ok else "AMBIGUOUS"
            reason = ("short line, corroborated by a neighbouring match" if ok
                      else "short/repeated line -- text alone is not proof")
        else:
            status, reason = "SHINSNOTE_MATCH", "Shinsnote %s match" % kind

        if recovered and status != "ENGLISH_REMAINS":
            status_out = "RECOVERED"
        else:
            status_out = status

        # Divergence is only meaningful inside a GCX Shinsnote demonstrably covers.
        # Shinsnote carries no English, so "these texts differ" is not by itself
        # evidence of anything -- the pair has to be anchored first. A row is a
        # mismatch candidate when its own GCX has >= 2 matched lines (so the beat
        # is anchored) yet this row matches none of them.
        info_card = res < 14 or re.search(r"PERSONAL DATA|PROFILE \[", english or "")
        if (status == "NO_SHINSNOTE_REF" and has_hangul(korean) and not short
                and not info_card):
            if anchored_gcx.get(gcx, 0) >= 2:
                status_out = "SHINSNOTE_MISMATCH"
                reason = ("GCX has %d Shinsnote matches but this line matches none"
                          % anchored_gcx[gcx])

        idx = by_gcx.get(gcx, [])
        pos = next((i for i, x in enumerate(idx) if x is r), None)
        prev_en = (idx[pos - 1].get("english") or "").strip()[:60] if pos else ""
        next_en = (idx[pos + 1].get("english") or "").strip()[:60] if pos is not None and pos + 1 < len(idx) else ""

        miss = sorted({c for c in korean if "가" <= c <= "힣" and c not in charmap})
        rows.append({
            "status": status_out,
            "gcx": gcx, "resource": res,
            "occurrences": r.get("occurrences", ""),
            "accept": r.get("accept", ""),
            "english": english,
            "korean_current": korean,
            "recovered": "yes" if recovered else "",
            "source": (note.split("recovered from ")[1].split(" ")[0] if recovered else ""),
            "shinsnote_speaker": entry["speaker"] if entry else "",
            "shinsnote_korean": entry["text"] if entry else "",
            "shinsnote_page_seq": ("%s:%s" % (entry["page"], entry["seq"])) if entry else "",
            "match_kind": kind,
            "unencodable_glyphs": "".join(miss),
            "ctx_prev_english": prev_en,
            "ctx_next_english": next_en,
            "review_reason": reason,
        })
        stats[status_out] += 1

    # Shinsnote lines nothing in the master matched -- candidate exposed dialogue
    matched_norms = {kstrip(r["shinsnote_korean"]) for r in rows if r["shinsnote_korean"]}
    for e in sh_entries:
        if e["norm"] in matched_norms:
            continue
        rows.append({
            "status": "UNMATCHED_SHINSNOTE", "gcx": "", "resource": "", "occurrences": "",
            "accept": "", "english": "", "korean_current": "", "recovered": "", "source": "",
            "shinsnote_speaker": e["speaker"], "shinsnote_korean": e["text"],
            "shinsnote_page_seq": "%s:%s" % (e["page"], e["seq"]), "match_kind": "",
            "unencodable_glyphs": "", "ctx_prev_english": "", "ctx_next_english": "",
            "review_reason": "Shinsnote codec line with no master counterpart",
        })
        stats["UNMATCHED_SHINSNOTE"] += 1

    order = {"RECOVERED": 0, "SHINSNOTE_MISMATCH": 1, "AMBIGUOUS": 2, "ENGLISH_REMAINS": 3,
             "UNMATCHED_SHINSNOTE": 4, "SHINSNOTE_MATCH": 5, "NO_SHINSNOTE_REF": 6}
    rows.sort(key=lambda r: (order.get(r["status"], 9), str(r["gcx"]), str(r["resource"])))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print("shinsnote codec lines            : %d" % len(sh_entries))
    print("confirmed anchors preserved      : %d" % len(confirmed))
    print("review rows                      : %d -> %s" % (len(rows), args.out))
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print("   %-22s %6d" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
