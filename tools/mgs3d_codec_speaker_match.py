#!/usr/bin/env python3
"""Assign a speaker to codec.dat rows by matching their English against an
external speaker-labelled transcript.

Rewritten from the draft at `output/mgs3d_codec_speaker_match.py`. Four things
in the draft made it unusable against this corpus:

1. It required the master's English to *equal* a transcript utterance. Both
   available transcripts merge a character's whole speech into one labelled
   utterance, while codec.dat splits the same speech across consecutive
   resources. Matching must therefore be "game string is a verbatim substring
   of one transcript utterance".
2. Its sequence disambiguation compared master row `i±1` with transcript
   `idx±1`. Master row order is not utterance order. The real neighbours are
   the same `gcx` at `resource±1`.
3. It accepted a unique match at >=12 normalised characters, which is short
   enough for accidental uniqueness.
4. It read the live master, which has no `speaker` column, so the
   agree/conflict comparison could never run.

Sources are pluggable; `--source` may be given more than once. Each source is
a JSON list of `{"speaker","text","order","conv"}`. Nothing here reads Korean:
speaker is decided from English and utterance order only.

Transcript text is treated as read-only input and is never copied into the
output; only the derived `gcx:resource -> speaker` assignment is written.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
csv.field_size_limit(10**9)

MIN_STANDALONE = 25   # normalised chars needed to trust a unique match on its own
MIN_ANY = 8           # below this a row is never matched at all
NEIGHBOUR_RATIO = 0.90

CANON = {
    "major": "Zero", "major zero": "Zero", "major tom": "Zero", "zero": "Zero",
    "snake": "Snake", "naked snake": "Snake", "naked snake (big boss)": "Snake",
    "para-medic": "Para-Medic", "paramedic": "Para-Medic",
    "sigint": "Sigint", "eva": "EVA",
    "the boss": "The Boss", "boss": "The Boss",
    "ocelot": "Ocelot",
}

DONOR = re.compile(
    r"<1f[0-9a-f]{2}>|\b(le|la|les|des|une|un|est|vous|tu|que|qui|con|los|las|para|como|pero)\b",
    re.I)


def canon(name: str) -> str:
    return CANON.get((name or "").strip().lower(), (name or "").strip())


def norm(s: str) -> str:
    """Normalise for matching: drop control tokens and button glyphs, fold
    punctuation and case, keep word characters and apostrophes."""
    s = (s or "").replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = re.sub(r"<[0-9A-Fa-f]{2,4}>", " ", s)
    s = re.sub(r"#\s*\{\s*\d+\s*\}\s*#", " ", s)
    s = re.sub(r"[^a-z0-9']+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def load_master(review: Path, recovered: Path | None):
    with review.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if recovered and recovered.exists():
        rec = {(r["gcx"], r["resource"]): r["english_plain"]
               for r in json.loads(recovered.read_text(encoding="utf-8"))}
        for r in rows:
            key = (r["gcx"], r["resource"])
            if key in rec:
                r["english"] = rec[key]
                r["english_recovered"] = "yes"
    rows.sort(key=lambda r: (int(r["gcx"]), int(r["resource"])))
    return rows


def load_source(path: Path):
    utts = json.loads(path.read_text(encoding="utf-8"))
    for i, u in enumerate(utts):
        u["idx"] = i
        u["n"] = norm(u["text"])
        u["speaker"] = canon(u["speaker"])
    return [u for u in utts if u["n"]]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--review", type=Path,
                    default=ROOT / "translation/10_master/review/codec-full-contextual-review.csv")
    ap.add_argument("--recovered", type=Path,
                    default=ROOT / "translation/10_master/review/full-qa-final/_recovered166.json")
    ap.add_argument("--source", type=Path, action="append", required=True,
                    metavar="NAME=PATH.json")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    rows = load_master(args.review, args.recovered)
    # index rows by gcx so neighbours are resource-adjacent, not row-adjacent
    by_gcx: dict[str, dict[int, dict]] = collections.defaultdict(dict)
    for r in rows:
        by_gcx[r["gcx"]][int(r["resource"])] = r

    sources = {}
    for spec in args.source:
        name, _, p = str(spec).partition("=")
        sources[name] = load_source(Path(p))
        print(f"source {name}: {len(sources[name])} utterances", file=sys.stderr)

    stats = collections.Counter()
    out = []
    for r in rows:
        en = norm(r["english"])
        rec = {"gcx": r["gcx"], "resource": r["resource"], "english": r["english"],
               "existing_speaker": r.get("speaker", ""),
               "existing_speaker_confidence": r.get("speaker_confidence", ""),
               "existing_verdict": r.get("verdict", ""),
               "existing_issue_type": r.get("issue_type", ""),
               "matched_speaker": "", "match_method": "", "match_source": "",
               "match_conv": "", "candidate_count": "", "context_evidence": "",
               "agreement": ""}
        if DONOR.search(r["english"]):
            stats["skipped_donor"] += 1
            rec["match_method"] = "skipped:donor"
            out.append(rec); continue
        if len(en) < MIN_ANY:
            stats["skipped_too_short"] += 1
            rec["match_method"] = "skipped:too_short"
            out.append(rec); continue

        best = None
        for sname, utts in sources.items():
            cands = [u for u in utts if en in u["n"]]
            if not cands:
                continue
            speakers = {u["speaker"] for u in cands}
            if len(cands) == 1 and len(en) >= MIN_STANDALONE:
                best = (sname, cands[0], "substring_unique", "", len(cands))
                break
            if len(speakers) == 1 and len(en) >= MIN_STANDALONE:
                # several utterances but they all belong to one speaker
                best = (sname, cands[0], "substring_speaker_unanimous", "", len(cands))
                break
            # ambiguous or short: require resource-adjacent corroboration
            scored = []
            for c in cands:
                score, bits = 0, []
                for d in (-2, -1, 1, 2):
                    nb = by_gcx[r["gcx"]].get(int(r["resource"]) + d)
                    ti = c["idx"] + (1 if d > 0 else -1)
                    if not nb or not (0 <= ti < len(utts)):
                        continue
                    nbn = norm(nb["english"])
                    if len(nbn) < MIN_ANY:
                        continue
                    if nbn and nbn in utts[ti]["n"]:
                        score += 2; bits.append(f"{d:+}:contained")
                    else:
                        q = SequenceMatcher(None, nbn, utts[ti]["n"]).ratio()
                        if q >= NEIGHBOUR_RATIO:
                            score += 1; bits.append(f"{d:+}:{q:.2f}")
                scored.append((score, c, ",".join(bits)))
            scored.sort(key=lambda z: z[0], reverse=True)
            if scored and scored[0][0] >= 2 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                best = (sname, scored[0][1], "context_sequence", scored[0][2], len(cands))
                break
            stats[f"ambiguous:{sname}"] += 1

        if best:
            sname, u, method, ev, ncand = best
            rec.update({"matched_speaker": u["speaker"], "match_method": method,
                        "match_source": sname, "match_conv": u.get("conv", "") or "",
                        "candidate_count": ncand, "context_evidence": ev})
            stats["confirmed"] += 1
            stats[f"method:{method}"] += 1
            old = canon(r.get("speaker", ""))
            if not old:
                rec["agreement"] = "NEW"; stats["new_from_unknown"] += 1
            elif old == u["speaker"]:
                rec["agreement"] = "AGREE"; stats["agree"] += 1
            else:
                rec["agreement"] = "CONFLICT"; stats["conflict"] += 1
        else:
            stats["unmatched"] += 1
            if not rec["match_method"]:
                rec["match_method"] = "no_match"
        out.append(rec)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)

    print(f"master rows {len(rows)}", file=sys.stderr)
    for k, v in sorted(stats.items()):
        print(f"  {k} {v}", file=sys.stderr)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
