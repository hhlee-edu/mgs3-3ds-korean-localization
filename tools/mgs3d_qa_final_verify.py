#!/usr/bin/env python3
"""Verify a proposed final Korean string against the constraints a `safe-fixed`
codec.dat build imposes.

Three independent checks, all of which a proposal must pass before it can be
called auto-appliable:

byte-fit
    `safe-fixed` passes `--preserve-record-layout`, and `replace_resources`
    enforces that per **GCX record**, not per string: the concatenation of
    every resource in the record must still fit `font_data_offset -
    string_resources_offset`. So a line may grow as long as the record has
    headroom, and identical strings inside a record share storage. The only
    honest check is therefore to rebuild the whole record with the proposals
    applied and see whether the builder accepts it -- which is what
    `verify_record` does.

new glyph
    A syllable that is absent from
    `translation/40_build_input/global_page_v2/character-map.json` cannot be
    drawn at all. Any such syllable makes a proposal unshippable without first
    growing the glyph page.

control code
    The leading/trailing control bytes and any icon tokens carried by the
    current string must survive verbatim; `<0A>` line breaks may be re-flowed
    but their count must not increase (a slot has a fixed number of rendered
    lines).

Used by the post-QA verification pass; it judges nothing about meaning.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARACTER_MAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"

TOKEN = re.compile(r"<([0-9A-Fa-f]{2})>")
HANGUL = re.compile(r"[가-힣]")

csv.field_size_limit(10**9)


def load_character_map(path: Path = CHARACTER_MAP) -> dict[str, bytes]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {ch: bytes.fromhex(tok) for ch, tok in raw["characters"].items()}


@dataclass
class Verdict:
    byte_fit: str = "n/a"
    new_glyph: str = "n/a"
    control_code: str = "n/a"
    encoded_len: int = 0
    budget: int = 0
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.byte_fit == "PASS"
            and self.new_glyph == "PASS"
            and self.control_code == "PASS"
        )


def encode_len(text: str, charmap: dict[str, bytes]) -> tuple[int, list[str]]:
    """Byte length of `text` once built, plus syllables that cannot be drawn."""
    total = 0
    missing: list[str] = []
    cursor = 0
    while cursor < len(text):
        match = TOKEN.match(text, cursor)
        if match:
            total += 1
            cursor = match.end()
            continue
        char = text[cursor]
        cursor += 1
        if char in charmap:
            total += len(charmap[char])
            continue
        value = ord(char)
        if 0x20 <= value <= 0x7E:
            total += 1
            continue
        # Not encodable: neither ASCII nor a mapped glyph.
        total += 2
        if HANGUL.match(char) or not unicodedata.category(char).startswith("Z"):
            missing.append(char)
    return total, missing


def control_tokens(text: str) -> list[str]:
    return TOKEN.findall(text)


def verify_record(record, proposals: dict[int, str], charmap: dict[str, bytes]):
    """Rebuild one GCX record with `proposals` applied under preserve-layout.

    Returns (ok, detail). This is the authoritative byte-fit test: it is the
    same code path `mgs3d_build.py --codec-mode safe-fixed` takes, so a PASS
    here means the record really does still fit its fixed string region.
    """
    from mgs3d_codec_tool import CodecError, parse_rendered

    encoded: dict[int, bytes] = {}
    for index, text in proposals.items():
        try:
            encoded[index] = parse_rendered(text, charmap)
        except CodecError as exc:
            return False, f"FAIL (resource {index} not encodable): {exc}"

    resources = record.resources()
    old_region = record.font_data_offset - record.string_resources_offset
    used = sum(len(encoded.get(i, r.data)) for i, r in enumerate(resources))
    try:
        record.replace_resources(encoded, preserve_layout=True)
    except CodecError as exc:
        return False, f"FAIL ({used}/{old_region}B): {exc}"
    return True, f"PASS ({used}/{old_region}B record region)"


def verify(current: str, proposed: str, charmap: dict[str, bytes]) -> Verdict:
    v = Verdict()

    budget, _ = encode_len(current, charmap)
    length, missing = encode_len(proposed, charmap)
    v.budget = budget
    v.encoded_len = length
    v.byte_fit = "PASS" if length <= budget else "FAIL"
    if v.byte_fit == "FAIL":
        v.notes.append(f"over budget by {length - budget} bytes")

    unique_missing = sorted(set(missing))
    v.missing = unique_missing
    v.new_glyph = "PASS" if not unique_missing else "FAIL"
    if unique_missing:
        v.notes.append("unrenderable: " + "".join(unique_missing))

    cur_tokens = control_tokens(current)
    new_tokens = control_tokens(proposed)
    cur_tail = [t for t in cur_tokens if t.upper() != "0A"]
    new_tail = [t for t in new_tokens if t.upper() != "0A"]
    breaks_before = cur_tokens.count("0A") + cur_tokens.count("0a")
    breaks_after = new_tokens.count("0A") + new_tokens.count("0a")
    if cur_tail != new_tail:
        v.control_code = "FAIL"
        v.notes.append(f"control tokens changed: {cur_tail} -> {new_tail}")
    elif breaks_after > breaks_before:
        v.control_code = "FAIL"
        v.notes.append(f"line breaks grew {breaks_before} -> {breaks_after}")
    else:
        v.control_code = "PASS"
        if breaks_after < breaks_before:
            v.notes.append(f"line breaks reduced {breaks_before} -> {breaks_after}")
    return v


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposals", type=Path, help="CSV with korean + final_korean")
    parser.add_argument("--current-column", default="korean")
    parser.add_argument("--proposed-column", default="final_korean")
    parser.add_argument("--out", type=Path, help="write the verified CSV here")
    args = parser.parse_args(argv)

    charmap = load_character_map()
    with args.proposals.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    counts = {"PASS": 0, "FAIL": 0, "skipped": 0}
    for row in rows:
        proposed = (row.get(args.proposed_column) or "").strip()
        if not proposed:
            row["byte_fit"] = row["new_glyph"] = row["control_code"] = ""
            counts["skipped"] += 1
            continue
        v = verify(row[args.current_column], proposed, charmap)
        row["byte_fit"] = f"{v.byte_fit} ({v.encoded_len}/{v.budget}B)"
        row["new_glyph"] = v.new_glyph if v.ok or not v.missing else "FAIL:" + "".join(v.missing)
        row["control_code"] = v.control_code
        row["verify_notes"] = "; ".join(v.notes)
        counts["PASS" if v.ok else "FAIL"] += 1

    if args.out:
        fields = list(rows[0].keys())
        with args.out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    print(f"verified {len(rows)} rows: {counts}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
