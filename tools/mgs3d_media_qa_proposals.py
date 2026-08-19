#!/usr/bin/env python3
"""Turn the movie/demo QA candidates plus the hand-authored verdicts into one
proposal sheet, with a byte check on every proposed rewrite.

READ-ONLY with respect to master/build/staging. It writes a proposal CSV and
nothing else; applying is a separate, approved step.

Inputs:
  output/media-register-qa/media-register-context.csv  (from mgs3d_media_register_qa.py)
  docs/evidence/2026-08-19-media-qa/verdicts.py        (the contextual judgements)

Byte check: movie/demo subtitle entries are fixed-layout, so a rewrite is only
safe if it encodes to no more bytes than the line already there. The proposal is
encoded exactly as the builder would -- `wrap_like_source` first so the card's
`80 7C` line breaks are preserved, then `encode_translation` against the same
global-page character map -- and compared against the current line.

Usage:
  python tools/mgs3d_media_qa_proposals.py --outdir output/media-register-qa
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mgs3d_movie_tool as mt  # noqa: E402

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parent.parent
MASTERS = ROOT / "translation/10_master/current"
CHARMAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
VERDICTS = ROOT / "docs/evidence/2026-08-19-media-qa/verdicts.py"

PUNCT_SPACE = re.compile(r"[ \t]+(?=[.!?,…])")
OPEN_QUOTE = re.compile(r'(["“\'])[ \t]+')
CLOSE_QUOTE = re.compile(r'[ \t]+(["”\'])')


def load_verdicts():
    spec = importlib.util.spec_from_file_location("media_qa_verdicts", VERDICTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tighten(text: str) -> str:
    """Remove the space the script reference-sourced lines carry before punctuation."""
    out = PUNCT_SPACE.sub("", text)
    out = OPEN_QUOTE.sub(r"\1", out)
    out = CLOSE_QUOTE.sub(r"\1", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--outdir", type=Path, default=ROOT / "output/media-register-qa")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    verdicts = load_verdicts()
    charmap = mt.load_static_character_map(CHARMAP)

    context = {}
    with io.open(args.outdir / "media-register-context.csv", encoding="utf-8-sig",
                 newline="") as handle:
        for row in csv.DictReader(handle):
            context[(row["media"], int(row["record"]), int(row["entry"]))] = row

    master = {}
    source = {}
    for media in ("movie", "demo"):
        with io.open(MASTERS / f"{media}.csv", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (media, int(row["record"]), int(row["entry"]))
                master[key] = row["korean"] or ""
                source[key] = row["translation_source"]

    # The subtitle bytes each line has to fit into, straight from the DAT.
    raw: dict[tuple, bytes] = {}
    clean = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs"
    for media in ("movie", "demo"):
        _, records, _ = mt.parse_records((clean / f"{media}.dat").read_bytes())
        for record in records:
            for index, subtitle in enumerate(record.subtitles):
                raw[(media, record.index, index)] = subtitle.original

    def encoded_length(key, text):
        if not text:
            return None
        try:
            return len(mt.encode_translation(mt.wrap_like_source(text, raw[key]), charmap))
        except Exception:
            return None

    mismapped = set(verdicts.MISMAPPED)
    keep = {key: reason for reason, keys in verdicts.REGISTER_KEEP.items() for key in keys}
    register = {(m, r, e): rest for m, r, e, *rest in verdicts.REGISTER_FIX}
    register_human = getattr(verdicts, "REGISTER_HUMAN", {})
    mt_fix = {(m, r, e): rest for m, r, e, *rest in getattr(verdicts, "MT_FIX", [])}

    rows = []
    for key, row in sorted(context.items()):
        flags = row["flags"]
        current = master.get(key, "")
        verdict = reason = proposal = ""
        if key in mismapped:
            verdict, reason = "HUMAN", (
                "Korean belongs to a different line; the English at this position was "
                "verified against the DAT. Needs re-alignment, not a reword.")
        elif key in register:
            speaker, change, proposal = register[key]
            verdict = "FIX"
            reason = f"{speaker}: {change} (confirmed-speaker register policy)"
        elif key in register_human:
            verdict, reason = "HUMAN", register_human[key]
        elif key in mt_fix:
            note, proposal = mt_fix[key]
            verdict, reason = "FIX", note
        elif key in keep:
            verdict, reason = "KEEP", keep[key]
        elif "ENGLISH_RESIDUE" in flags:
            verdict, reason = "HUMAN", (
                "English vocabulary left inside the Korean line; reads as a "
                "capacity-forced abbreviation. Needs a translator with the byte budget.")
        elif "NAME_SCRIPT_SPLIT" in flags:
            verdict, reason = "HUMAN", (
                "Proper noun written in Latin here and transliterated elsewhere. "
                "Project-wide romanisation policy call, not a per-line fix.")
        elif "PUNCT_SPACING" in flags:
            tightened = tighten(current)
            if tightened != current:
                verdict, proposal = "FIX", tightened
                reason = "space before punctuation, inherited from the script reference table"
        elif "MT_LITERAL" in flags:
            verdict, reason = "REVIEW", (
                "literal-translation marker; read in context and left alone. Most are "
                "ordinary Korean -- a 그는/그녀는 opener marks a referent the sentence "
                "needs. Worth a translator's style pass over the Ocelot epilogue "
                "(demo r274-r320), which leans on 그녀는 where a name or a dropped "
                "subject would read better.")
        if not verdict:
            continue
        before = encoded_length(key, current)
        after = encoded_length(key, proposal) if proposal else None
        if verdict == "FIX" and after is not None and before is not None and after > before:
            # A subtitle entry is a fixed byte slot, so a rewrite that does not fit
            # is not a proposal -- it is a request for a shorter wording. Several of
            # these turn out to explain the defect: the line is missing its final
            # period because there was never a byte for one.
            verdict = "HUMAN"
            reason = f"{reason}; rewrite is {after - before} byte(s) over the fixed slot"
        rows.append({
            "media": key[0], "record": key[1], "entry": key[2],
            "verdict": verdict, "flags": flags, "register": row["register"],
            "translation_source": source.get(key, ""),
            "english": row["english"], "korean": current, "korean_new": proposal,
            "bytes_now": before if before is not None else "",
            "bytes_new": after if after is not None else "",
            "byte_fit": "" if after is None or before is None else
                        ("OK" if after <= before else f"OVER by {after - before}"),
            "reason": reason,
        })

    fields = ["media", "record", "entry", "verdict", "flags", "register",
              "translation_source", "english", "korean", "korean_new",
              "bytes_now", "bytes_new", "byte_fit", "reason"]
    out = args.outdir / "media-qa-proposals.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(r["verdict"] for r in rows)
    fits = Counter(r["byte_fit"] for r in rows if r["korean_new"])
    print(f"{out}  ({len(rows)} rows)")
    for verdict, count in counts.most_common():
        print(f"  {verdict:<8} {count}")
    print("  byte check on proposed rewrites:", dict(fits))
    by_source = defaultdict(Counter)
    for row in rows:
        by_source[row["verdict"]][row["translation_source"]] += 1
    for verdict, counter in sorted(by_source.items()):
        print(f"  {verdict} by source: {dict(counter)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
