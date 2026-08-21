#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract, verify and re-insert the `romfs/vox.dat` subtitle table.

`vox.dat` is a fifth text container, alongside codec.dat / movie.dat / demo.dat
and stage/*/scenerio.gcx. It had never been in the translation pipeline: it is
124 MB and named like an audio file, and every earlier note about it recorded
only that it was "byte-identical to clean", meaning *our changes did not touch
it* -- which was read as *there is nothing in it*.

Record format (16-byte header, little-endian)

    u32 t0      subtitle cue start time
    u32 t1      subtitle cue end time
    u32 rsv     always 0 -- used here as a structural gate
    u16 length  total record length, header included, multiple of 4
    u16 lang    1=EN 2=FR 3=DE 4=IT 5=ES
    u8  text[]  NUL-terminated, remainder of the record is NUL padding

A cue is the run of records sharing one (t0,t1). Both orders occur in the file:
EN->ES in 3,497 cues and ES->EN in 331, so a cue must never be identified by
member order. (t0,t1) alone is not a key either -- timings repeat across voice
blocks, and grouping on them globally merges hundreds of unrelated records. A
cue is therefore a run in offset order that shares (t0,t1) and introduces no
language twice.

`lang` is an explicit field, so English identification is the file's own
declaration, not an inference. It is cross-checked anyway: measured over the
whole file, EN text contains zero 0x1F accent escapes against 9,395 in donor
text, and EN encodes its line break as the two-byte token 0x80 0x7C while donor
text uses 0x0A.

Text is carried through CSV as ASCII with one escape, `\n` for 0x80 0x7C.
That is lossless here and checked to be so: EN text contains no backslash, no
standalone 0x7C, and no CR or TAB.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VOX = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/vox.dat"
DEFAULT_OUT = ROOT / "translation/vox"

# Language codes as measured over the whole file, not assumed. 7 is a second
# English slot sitting at the HEAD of a cue, ahead of the 5-language block: in
# 22 of its 27 cues the lang-1 record carries byte-identical text. It has to be
# written too -- leaving it English is enough to keep English on screen. Codes
# 16 and 32 also parse structurally, but their payloads are binary and the token
# gate in is_text() is what rejects them.
LANGS = {1: "EN", 2: "FR", 3: "DE", 4: "IT", 5: "ES", 7: "EN_ALT"}
ENGLISH = (1, 7)
BREAK = bytes([0x80, 0x7C])       # EN line break token
ESCAPED_BREAK = chr(92) + "n"      # how BREAK is spelled inside the CSV
NULB = bytes([0])                 # string terminator


# --------------------------------------------------------------------------- parse

def _candidate(blob: bytes, off: int) -> dict | None:
    """A structurally valid record at `off`, or None.

    The reserved u32 is the cheap gate and runs first; it rejects almost
    everything before the costlier checks. Note what is NOT required here: that
    the slack after the terminator be NUL. Measured 2026-08-21, real records
    carry stale bytes there -- leftovers of longer text previously in the slot,
    e.g. `...mission.` then a NUL then a stray `os`. Demanding clean padding silently drops
    those records, and with them 51 English lines of the ending cutscene.
    """
    n = len(blob)
    if off < 0 or off + 16 > n:
        return None
    if blob[off + 8] or blob[off + 9] or blob[off + 10] or blob[off + 11]:
        return None
    t0, t1, _rsv = struct.unpack_from("<III", blob, off)
    length, lang = struct.unpack_from("<HH", blob, off + 12)
    if lang not in LANGS or length < 17 or length % 4 or off + length > n:
        return None
    body = blob[off + 16:off + length]
    end = body.find(NULB)
    if end < 0 or not is_text(body[:end]):
        return None
    return {"off": off, "t0": t0, "t1": t1, "length": length, "lang": lang,
            "text": body[:end], "clean_pad": not any(body[end:])}


def parse_records(blob: bytes) -> list[dict]:
    """Chain-validated record walk.

    Accepting every structurally valid offset would admit 21,873 records with
    2,644 of them overlapping -- a "record" that begins inside another record's
    text passes the same field checks. So records with clean NUL padding seed
    the parse, and the set grows only along adjacency: a candidate is accepted
    when it starts exactly where an accepted record ends, or ends exactly where
    one begins, and overlaps nothing already accepted. Boundaries are decided by
    the chain, never guessed.

    The result is its own check. The five shipped languages come out at
    3,937-3,939 records each, which is the file's ~3,938 cues seen five times.
    """
    cands = {}
    for off in range(0, len(blob) - 16, 4):
        rec = _candidate(blob, off)
        if rec is not None:
            cands[off] = rec
    accepted = {off: rec for off, rec in cands.items() if rec["clean_pad"]}
    by_end = defaultdict(list)
    for off, rec in cands.items():
        by_end[off + rec["length"]].append(off)

    def spans() -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for s, e in sorted((o, o + r["length"]) for o, r in accepted.items()):
            if out and s <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], e))
            else:
                out.append((s, e))
        return out

    def clashes(off: int, length: int, occ: list[tuple[int, int]]) -> bool:
        lo, hi = 0, len(occ) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            s, e = occ[mid]
            if off + length <= s:
                hi = mid - 1
            elif off >= e:
                lo = mid + 1
            else:
                return True
        return False

    changed = True
    while changed:
        changed = False
        occ = spans()
        for off, rec in list(accepted.items()):
            for nb in [off + rec["length"], *by_end.get(off, [])]:
                if nb in cands and nb not in accepted                         and not clashes(nb, cands[nb]["length"], occ):
                    accepted[nb] = cands[nb]
                    occ = spans()
                    changed = True
    return [accepted[o] for o in sorted(accepted)]


def group_cues(records: list[dict]) -> list[list[dict]]:
    """Runs sharing (t0,t1) that never repeat a language. Order-agnostic."""
    cues: list[list[dict]] = []
    cur: list[dict] = []
    seen: set[int] = set()
    for rec in records:
        if cur and (rec["t0"], rec["t1"]) == (cur[-1]["t0"], cur[-1]["t1"]) \
                and rec["lang"] not in seen:
            cur.append(rec)
            seen.add(rec["lang"])
            continue
        if cur:
            cues.append(cur)
        cur = [rec]
        seen = {rec["lang"]}
    if cur:
        cues.append(cur)
    return cues


# --------------------------------------------------------------------------- text

def is_text(text: bytes) -> bool:
    """Every byte belongs to a known token: printable ASCII, 0x0A, the two-byte
    line break 0x80 0x7C, or a 0x1F accent escape pair."""
    i = 0
    while i < len(text):
        c = text[i]
        if 0x20 <= c < 0x7F or c == 0x0A:
            i += 1
        elif c == 0x80 and i + 1 < len(text) and text[i + 1] == 0x7C:
            i += 2
        elif 0x81 <= c <= 0x87 and i + 1 < len(text):
            # Global-page Korean token. Needed so the tool can re-parse a file it
            # wrote: without it every translated record fails the gate and the
            # output cannot be verified against its own map. Lead bytes 0x81-0x87
            # are exactly the range the character map uses. Checked against the
            # clean file: admitting them changes the record count by 0.
            i += 2
        elif c == 0x1F and i + 1 < len(text):
            i += 2
        else:
            return False
    return True


def encode_for_csv(text: bytes) -> str:
    return text.replace(BREAK, b"\n").decode("ascii")


def decode_from_csv(s: str) -> bytes:
    return s.encode("ascii").replace(b"\n", BREAK)


def is_structural(text: bytes) -> bool:
    """No letter survives once the line break is removed -- digits, '!!', dots."""
    return not re.search(rb"[A-Za-z]", text.replace(BREAK, b""))


def make_id(text: bytes) -> str:
    """Permanent, order-independent, recomputable from the `english` column."""
    return "vox-" + hashlib.sha256(text).hexdigest()[:12]


# --------------------------------------------------------------------------- extract

def classify(cues: list[list[dict]]) -> tuple[list[dict], list[dict]]:
    """Split English records into translation targets and held-back ones.

    Every held record carries the reason it was held, so the count can be
    audited later without re-deriving it.
    """
    targets, held = [], []
    for ci, cue in enumerate(cues):
        langs = {r["lang"] for r in cue}
        complete = {1, 2, 3, 4, 5} <= langs
        for rec in cue:
            if rec["lang"] not in ENGLISH:
                continue
            row = dict(rec, cue=ci, cue_langs=sorted(langs), complete_cue=complete)
            if not rec["text"]:
                row["reason"] = "empty text"
                held.append(row)
            elif is_structural(rec["text"]):
                row["reason"] = "no letters -- structural or punctuation only"
                held.append(row)
            else:
                # `lang` is an explicit field, so an incomplete cue is a
                # grouping observation, not doubt about the language. It is
                # recorded so the decision stays reversible.
                row["note"] = "" if complete else \
                    "incomplete cue: langs " + "".join(LANGS[x] for x in sorted(langs))
                targets.append(row)
    return targets, held


def cmd_extract(args) -> int:
    # Re-extraction rewrites vox-translation.csv with an empty `korean` column.
    # Once the file has come back translated that is a destructive act, and the
    # translation lives nowhere else, so refuse unless the caller says so.
    existing = args.out / "vox-translation.csv"
    if existing.is_file() and not args.force:
        with existing.open(encoding="utf-8-sig", newline="") as fh:
            done = sum(1 for row in csv.DictReader(fh) if (row.get("korean") or "").strip())
        if done:
            raise SystemExit(
                f"{existing} already holds {done} translated rows; extracting would "
                f"erase them. Move it aside first, or pass --force.")
    blob = args.vox.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    records = parse_records(blob)
    cues = group_cues(records)
    targets, held = classify(cues)

    en_total = sum(1 for r in records if r["lang"] in ENGLISH)
    donor_total = len(records) - en_total
    complete_cues = sum(1 for c in cues
                        if {1, 2, 3, 4, 5} <= {r["lang"] for r in c})

    # Dedupe on the exact English bytes. Identical lines are translated once
    # and propagated back to every occurrence at re-insertion.
    by_text: dict[bytes, list[dict]] = defaultdict(list)
    for row in targets:
        by_text[row["text"]].append(row)

    ids = {}
    for text in by_text:
        vid = make_id(text)
        if vid in ids:
            raise SystemExit(f"id collision: {vid}")
        ids[vid] = text

    # Round-trip gate: the CSV form must reproduce the original bytes exactly,
    # for every distinct string, before anything is written.
    for text in by_text:
        if decode_from_csv(encode_for_csv(text)) != text:
            raise SystemExit(f"escape round-trip failed: {text!r}")

    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for text, occ in by_text.items():
        # The tightest slot wins: one Korean string is written to every
        # occurrence, so it has to fit the smallest of them.
        budget = min(o["length"] - 16 - 1 for o in occ)
        notes = sorted({o["note"] for o in occ if o.get("note")})
        rows.append({
            "id": make_id(text),
            "english": encode_for_csv(text),
            "korean": "",
            "occurrences": len(occ),
            "max_bytes": budget,
            "notes": "; ".join(notes),
        })
    rows.sort(key=lambda r: (-r["occurrences"], r["english"]))

    csv_path = args.out / "vox-translation.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "english", "korean",
                                           "occurrences", "max_bytes", "notes"])
        w.writeheader()
        w.writerows(rows)

    mapping = {
        "format": "mgs3d-vox-map-v1",
        "source": {"path": str(args.vox), "size": len(blob), "sha256": sha},
        "record_format": "u32 t0, u32 t1, u32 rsv=0, u16 length, u16 lang, "
                         "NUL-terminated text, NUL padding to length",
        "languages": LANGS,
        "text_escape": {"\\n": "0x80 0x7C (EN line break)"},
        "summary": {
            "records_parsed": len(records),
            "records_by_language": {LANGS[k]: v for k, v in
                                    sorted(Counter(r["lang"] for r in records).items())},
            "cues": len(cues),
            "complete_5_language_cues": complete_cues,
            "incomplete_cues": len(cues) - complete_cues,
            "en_records_total": en_total,
            "donor_records_total": donor_total,
            "en_held": len(held),
            "en_held_by_reason": dict(Counter(h["reason"] for h in held)),
            "en_translatable_occurrences": len(targets),
            "unique_en_strings": len(rows),
        },
        # id -> every byte location that string occupies. This is what makes a
        # returned CSV re-insertable: the external PC never sees an offset.
        "strings": {
            make_id(text): {
                "english": encode_for_csv(text),
                "source_bytes": len(text),
                "occurrences": [
                    {"offset": o["off"], "text_offset": o["off"] + 16,
                     "length": o["length"], "capacity": o["length"] - 16 - 1,
                     "cue": o["cue"], "t0": o["t0"], "t1": o["t1"],
                     "cue_langs": [LANGS[x] for x in o["cue_langs"]]}
                    for o in sorted(occ, key=lambda x: x["off"])
                ],
            }
            for text, occ in by_text.items()
        },
    }
    (args.out / "vox-map.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if held:
        with (args.out / "irregular-records.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["offset", "cue", "t0", "t1", "length",
                                               "cue_langs", "raw_hex", "reason"])
            w.writeheader()
            for h in sorted(held, key=lambda x: x["off"]):
                w.writerow({"offset": "0x%X" % h["off"], "cue": h["cue"],
                            "t0": h["t0"], "t1": h["t1"], "length": h["length"],
                            "cue_langs": "".join(LANGS[x] for x in h["cue_langs"]),
                            "raw_hex": h["text"].hex(), "reason": h["reason"]})

    print(json.dumps(mapping["summary"], ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- verify

def load_charmap() -> dict[str, bytes] | None:
    p = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8")).get("characters", {})
    return {k: bytes.fromhex(v) for k, v in data.items() if isinstance(v, str)}


def encode_korean(s: str, cmap: dict[str, bytes] | None) -> tuple[bytes | None, str]:
    """Best-effort target encoding. Returns (bytes, error)."""
    if cmap is None:
        return None, "character map not available"
    # The CSV spells the line break as the two characters backslash-n -- the same
    # escape encode_for_csv() writes -- so it has to be turned back into a real
    # newline before encoding. Missing this wrote a literal 0x5C 0x6E into 1,068
    # slots and the game drew it as visible text instead of breaking the line.
    s = s.replace(ESCAPED_BREAK, chr(10))
    # Any backslash left after that conversion is an escape the CSV was not
    # supposed to carry. Checking the input rather than the encoded bytes matters:
    # four map tokens (845C 855C 865C 875C) use 0x5C as their trail byte, so a
    # payload-side test flags legitimate Korean.
    if chr(92) in s:
        return None, "unconverted escape: backslash in " + repr(s)
    out = bytearray()
    for ch in s:
        if ch == "\n":
            out += BREAK
            continue
        if ch in cmap:
            out += cmap[ch]
        elif ord(ch) < 0x80:
            out.append(ord(ch))
        else:
            return None, f"no glyph for {ch!r}"
    return bytes(out), ""


def cmd_verify(args) -> int:
    mapping = json.loads((args.out / "vox-map.json").read_text(encoding="utf-8"))
    strings = mapping["strings"]
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    cmap = load_charmap()

    errors, warnings, translated = [], [], 0
    seen = set()
    for i, row in enumerate(rows, 2):
        vid = (row.get("id") or "").strip()
        eng = row.get("english") or ""
        if vid in seen:
            errors.append(f"row {i}: duplicate id {vid}")
            continue
        seen.add(vid)
        if vid not in strings:
            errors.append(f"row {i}: unknown id {vid}")
            continue
        # The id is sha256 of the English bytes, so this catches any edit to
        # the english column -- including one a spreadsheet made silently.
        if make_id(decode_from_csv(eng)) != vid:
            errors.append(f"row {i}: english column no longer matches id {vid}")
            continue
        if eng != strings[vid]["english"]:
            errors.append(f"row {i}: english differs from the extracted source ({vid})")
            continue
        kor = (row.get("korean") or "").strip()
        if not kor:
            continue
        translated += 1
        budget = min(o["capacity"] for o in strings[vid]["occurrences"])
        enc, err = encode_korean(kor, cmap)
        if enc is None:
            warnings.append(f"row {i}: {vid}: {err}")
        elif len(enc) > budget:
            errors.append(f"row {i}: {vid}: {len(enc)} bytes > {budget} available")

    missing = set(strings) - seen
    if missing:
        errors.append(f"{len(missing)} ids from the map are absent from the CSV")

    result = {"rows": len(rows), "known_ids": len(strings), "translated": translated,
              "errors": errors[:40], "error_count": len(errors),
              "warnings": warnings[:10], "warning_count": len(warnings),
              "pass": not errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


# --------------------------------------------------------------------------- apply

def cmd_apply(args) -> int:
    """Write Korean into every occurrence. Dry-run unless --apply is given, and
    never in place -- the rebuilt file always goes to --output."""
    mapping = json.loads((args.out / "vox-map.json").read_text(encoding="utf-8"))
    blob = bytearray(args.vox.read_bytes())
    if hashlib.sha256(bytes(blob)).hexdigest() != mapping["source"]["sha256"]:
        raise SystemExit("vox.dat does not match the sha256 the map was built from")
    strings = mapping["strings"]
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig", newline="")))
    cmap = load_charmap()

    writes, errors = 0, []
    for i, row in enumerate(rows, 2):
        vid = (row.get("id") or "").strip()
        kor = (row.get("korean") or "").strip()
        if not kor or vid not in strings:
            continue
        if make_id(decode_from_csv(row.get("english") or "")) != vid:
            errors.append(f"row {i}: english no longer matches id {vid}")
            continue
        enc, err = encode_korean(kor, cmap)
        if enc is None:
            errors.append(f"row {i}: {vid}: {err}")
            continue
        for occ in strings[vid]["occurrences"]:
            if len(enc) > occ["capacity"]:
                errors.append(f"{vid} @0x{occ['offset']:X}: {len(enc)}>{occ['capacity']}")
                continue
            if args.apply:
                start = occ["text_offset"]
                # Length is fixed: the payload is written, then the rest of the
                # slot is cleared to NUL so no tail of the English survives.
                blob[start:start + occ["capacity"] + 1] = \
                    enc + b"\x00" * (occ["capacity"] + 1 - len(enc))
            writes += 1

    if errors:
        print(json.dumps({"pass": False, "errors": errors[:40],
                          "error_count": len(errors)}, ensure_ascii=False, indent=2))
        return 1
    if args.apply:
        if len(blob) != mapping["source"]["size"]:
            raise SystemExit("length changed -- refusing to write")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(bytes(blob))
    print(json.dumps({"pass": True, "occurrences_written": writes,
                      "dry_run": not args.apply,
                      "output": str(args.output) if args.apply else None},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vox", type=Path, default=DEFAULT_VOX)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--force", action="store_true",
                   help="overwrite vox-translation.csv even if it holds translations")
    e.set_defaults(func=cmd_extract)
    v = sub.add_parser("verify")
    v.add_argument("--csv", type=Path, default=DEFAULT_OUT / "vox-translation.csv")
    v.set_defaults(func=cmd_verify)
    a = sub.add_parser("apply")
    a.add_argument("--csv", type=Path, default=DEFAULT_OUT / "vox-translation.csv")
    a.add_argument("--output", type=Path, required=True, help="rebuilt vox.dat; never in place")
    a.add_argument("--apply", action="store_true", help="write; otherwise dry-run")
    a.set_defaults(func=cmd_apply)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
