#!/usr/bin/env python3
"""One prioritised file of the codec text that still needs a translator.

After duplicate propagation, a row's `occurrences` count *is* its on-screen
visibility -- a row with 63 locations is seen 63 times. Priority is therefore
occurrence-weighted, which was not true before v0.82.

Two kinds of work end up in one file:

  ENGLISH   the row has no Korean at all. Most of what looks like residual
            English in-game is **donor** French/Spanish, which must not be
            translated (English/Korean only), so each row is classified from the
            *game bytes* at its own positions and donors are excluded.
  TONE      the Korean was rewritten mechanically to fit a byte budget during the
            v0.81 fitting round and never had a translator's read. Found by
            diffing against `codec.csv.bak-pre-shorten`, not by guessing.

Donor detection is deliberately aggressive: any French/Spanish function word with
no English one, or a `<1fXX>` accent escape anywhere in the row's game text, marks
the row donor. A missed donor wastes a translator's time; a donor wrongly kept is
visible immediately and can be skipped.

    python tools/mgs3d_codec_quality_worklist.py
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_codec  # noqa: E402

DEFAULT_CODEC = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
DEFAULT_MASTER = ROOT / "translation/10_master/current/codec.csv"
DEFAULT_PRESHORTEN = ROOT / "translation/10_master/current/codec.csv.bak-pre-shorten"
DEFAULT_OUT = ROOT / "translation/10_master/review/quality-worklist.csv"

ACCENT = re.compile(rb"\x1f[\x20-\x7f]")
FR = re.compile(r"\b(je|tu|il|elle|le|la|les|des|une|un|est|es|et|ne|pas|que|qui|se|son|sa"
                r"|ses|au|aux|du|en|dans|pour|avec|vous|nous|mais|plus|tout|tous|sur|donc"
                r"|alors|comme|bien|fait|faire|peut|dois|moi|toi|oui|non|c'est|j'ai|d'un"
                r"|merci|sais|vais|veux|rien|encore|jamais|toujours|quoi|ici)\b", re.I)
ES = re.compile(r"\b(yo|tu|el|la|los|las|una|es|son|para|con|en|no|si|que|quien|su|sus|del"
                r"|y|como|hacer|puede|debe|esto|esta|eso|muy|hay|ser|esta|pero|mas|todo"
                r"|todos|sobre|vale|hacia|primero|luego|bien|nada|nunca|siempre|aqui)\b", re.I)
EN = re.compile(r"\b(the|is|are|you|your|to|of|and|that|this|it|in|on|for|with|have|has|will"
                r"|can|not|but|be|do|does|was|were|they|we|he|she|there|what|when|yeah|okay"
                r"|right|just|know|get|got|about|from|all|out|up|no|so|my|me|i'm|don't|it's)\b",
                re.I)


def is_donor_text(raw: bytes) -> bool:
    if ACCENT.search(raw):
        return True
    text = raw.decode("latin-1").replace("\x00", "").replace("\x80", "")
    fr, es, en = len(FR.findall(text)), len(ES.findall(text)), len(EN.findall(text))
    return max(fr, es) > 0 and en == 0


def parse_locations(value: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for item in (value or "").split(";"):
        gcx, _, resource = item.strip().partition(":")
        try:
            out.append((int(gcx), int(resource)))
        except ValueError:
            continue
    return out


def has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text or "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codec", type=Path, default=DEFAULT_CODEC)
    ap.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    ap.add_argument("--pre-shorten", type=Path, default=DEFAULT_PRESHORTEN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    payloads = [[r.data for r in rec.resources()]
                for rec in parse_codec(args.codec.read_bytes())]

    def raw(key: tuple[int, int]) -> bytes | None:
        gcx, resource = key
        if not 0 <= gcx < len(payloads) or not 0 <= resource < len(payloads[gcx]):
            return None
        return payloads[gcx][resource]

    csv.field_size_limit(10 ** 9)
    with args.master.open(encoding="utf-8-sig", newline="") as stream:
        master = list(csv.DictReader(stream))

    before: dict[tuple[str, str], str] = {}
    if args.pre_shorten.exists():
        with args.pre_shorten.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                before[(row.get("gcx", ""), row.get("resource", ""))] = row.get("korean", "")

    rows = []
    for row in master:
        if (row.get("is_donor") or "") == "yes":
            continue
        if (row.get("text_kind") or "") != "display_text":
            continue
        locations = parse_locations(row.get("locations", ""))
        if not locations:
            continue
        if any((b := raw(k)) is not None and is_donor_text(b) for k in locations):
            continue                                   # donor branch -- out of scope

        korean = row.get("korean", "")
        key = (row.get("gcx", ""), row.get("resource", ""))
        if not has_hangul(korean):
            kind, was = "ENGLISH", ""
        elif key in before and before[key] and before[key] != korean:
            kind, was = "TONE", before[key]
        else:
            continue

        rows.append({
            "kind": kind,
            "occurrences": len(locations),
            "gcx": row.get("gcx", ""),
            "resource": row.get("resource", ""),
            "english": (row.get("english") or "").strip(),
            "korean": korean,
            "korean_before_shortening": was,
            "korean_new": "",
            "status": row.get("status", ""),
        })

    rows.sort(key=lambda r: (r["kind"], -r["occurrences"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    english = [r for r in rows if r["kind"] == "ENGLISH"]
    tone = [r for r in rows if r["kind"] == "TONE"]
    print(f"quality worklist: {len(rows)} rows -> {args.out}")
    print(f"  ENGLISH  {len(english):5d} rows, {sum(r['occurrences'] for r in english):6d} on-screen locations")
    print(f"  TONE     {len(tone):5d} rows, {sum(r['occurrences'] for r in tone):6d} on-screen locations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
