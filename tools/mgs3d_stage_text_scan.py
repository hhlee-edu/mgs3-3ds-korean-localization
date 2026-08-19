#!/usr/bin/env python3
"""Full text inventory of stage/<name>/scenerio.gcx -- the in-game text path.

codec.dat / movie.dat / demo.dat are the three containers the translation
pipeline has always known about. They hold codec conversations and cutscene
subtitles. They do *not* hold in-game enemy/NPC barks ("Who's that!",
"I see him!!"), item / food / medicine descriptions, area names, tutorial and
control help, the RESULTS screen, or the title-award text. All of that lives in
the per-stage `scenerio.gcx`, which is a GCX container in exactly the same
format as one codec.dat record: an encrypted string region addressed by a
resource table, with per-record 16x16 2bpp custom glyphs.

Language layout, measured rather than assumed:

* The stage files carry **three** Western branches -- English, French, Spanish.
  German and Italian are absent (they exist in movie.dat/demo.dat but not here).
* The branches are laid out as consecutive equal-length blocks, one per
  language, repeated with a *variable* block length (1, 2, 4, 8 ... lines) and
  no fixed language order. A naive period-3 assumption explains only 81% of the
  corpus; the block segmentation below explains it properly.

So a raw string count over these files is meaningless until the branches are
separated. Two independent signals do that here:

  vocabulary  -- the 0x1F extended-character escape appears only in the
                 French/Spanish branches, which seeds a donor lexicon straight
                 from this corpus; movie.csv/demo.csv previews seed a clean
                 English lexicon (the codec master's `english` column is not
                 used: it is known to be donor-contaminated).
  structure   -- the EN/FR/ES block triples above.

The two are cross-checked against each other and must not disagree.

Read-only. It never writes to the game tree.

Usage:
  python tools/mgs3d_stage_text_scan.py --out docs/evidence/<dated-dir>
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

from mgs3d_codec_tool import CodecError, GcxRecord, align  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402
from mgs3d_codec_status_catalog import strict_western  # noqa: E402

csv.field_size_limit(10 ** 9)

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs"
MASTERS = ROOT / "translation/10_master/current"

STRING_FLAG = 0x80000000
ACCENT = re.compile(rb"\x1f[\x20-\x7f]")
WORD = re.compile(r"[A-Za-z][A-Za-z']*")
# `#<A07B>..<C07D>#` wraps a button-icon glyph: control help text, not dialogue.
ICON = re.compile(rb"\xa0\x7b|\xc0\x7d")
# Longest language block observed is 8; 96 leaves generous headroom.
MAX_BLOCK = 96


def stage_records(path: Path) -> list[GcxRecord]:
    """Parse one scenerio.gcx. The file is not padded to the GCX alignment on
    disk, so pad a copy before handing it to the shared parser."""
    data = path.read_bytes()
    data += b"\x00" * (align(len(data)) - len(data))
    records: list[GcxRecord] = []
    cursor = 0
    while cursor < len(data):
        record, cursor = GcxRecord.from_codec(data, cursor)
        records.append(record)
    return records


def kind_of(raw: bytes, text: str) -> str:
    """Coarse content class. Deliberately conservative: anything that reads as a
    sentence stays `prose` and is triaged by a human, not by this heuristic."""
    if ICON.search(raw):
        return "ui_help"
    letters = [c for c in text if c.isalpha()]
    words = WORD.findall(text)
    if not letters or not words:
        return "symbol"
    if len(words) == 1 or (all(c.isupper() for c in letters) and len(words) <= 4):
        return "label"
    return "prose"


def words_of(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text) if len(w) > 1]


def read_locations(romfs: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(romfs.glob("stage/**/scenerio.gcx")):
        stage = path.parent.name
        for record_index, record in enumerate(stage_records(path)):
            try:
                resources = record.resources()
            except CodecError:
                continue
            for resource_index, resource in enumerate(resources):
                raw = resource.data
                if not raw or resource.table_word & 0xFF000000 != STRING_FLAG:
                    continue
                rows.append({
                    "stage": stage,
                    "record": record_index,
                    "resource": resource_index,
                    "table_word": f"{resource.table_word:08X}",
                    "bytes": len(raw),
                    "western": strict_western(raw),
                    "accent": bool(ACCENT.search(raw)),
                    "kind": kind_of(raw, decode_western(raw)),
                    "raw_hex": raw.hex(),
                    "text": decode_western(raw),
                })
    return rows


def lexicons(rows: list[dict]) -> tuple[set[str], set[str]]:
    donor: Counter[str] = Counter()
    for row in rows:
        if row["accent"]:
            donor.update(words_of(row["text"]))
    english: Counter[str] = Counter()
    for name in ("movie", "demo"):
        with io.open(MASTERS / f"{name}.csv", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                english.update(words_of(row.get("preview") or ""))
    donor_only = {w for w, n in donor.items() if n >= 3 and english[w] == 0}
    english_only = {w for w, n in english.items() if n >= 2 and donor[w] == 0}
    return donor_only, english_only


def vocabulary_evidence(row: dict, donor_only: set[str], english_only: set[str]) -> str:
    """-> 'd' (donor), 'e' (English) or '?' (no separating vocabulary)."""
    if row["accent"]:
        return "d"
    tokens = words_of(row["text"])
    donor_hits = sum(1 for w in tokens if w in donor_only)
    english_hits = sum(1 for w in tokens if w in english_only)
    if donor_hits > english_hits:
        return "d"
    if english_hits > donor_hits:
        return "e"
    return "?"


def segment(sequence: list[dict]) -> None:
    """Assign `structural` on one record's Western strings by locating EN/FR/ES
    block triples. Each triple is three equal-length consecutive blocks in which
    exactly one block carries no donor evidence and the other two carry donor
    evidence but no English evidence. The best-scoring block length wins, so one
    bad short match cannot desynchronise everything after it."""
    evidence = [row["evidence"] for row in sequence]
    total = len(evidence)
    cursor = 0
    while cursor < total:
        best = None
        for size in range(1, min(MAX_BLOCK, (total - cursor) // 3) + 1):
            blocks = [evidence[cursor + i * size: cursor + (i + 1) * size] for i in range(3)]
            for index in range(3):
                if "d" in blocks[index]:
                    continue
                others = [blocks[i] for i in range(3) if i != index]
                if any("e" in block for block in others):
                    continue
                score = sum(block.count("d") for block in others) + blocks[index].count("e")
                if score >= 2 and (best is None or score > best[0]):
                    best = (score, size, index)
        if best is None:
            cursor += 1
            continue
        _, size, index = best
        for i in range(3):
            language = "english" if i == index else "donor"
            for j in range(size):
                sequence[cursor + i * size + j]["structural"] = language
        cursor += 3 * size


def resolve(rows: list[dict]) -> dict[str, int]:
    donor_only, english_only = lexicons(rows)
    for row in rows:
        row["evidence"] = vocabulary_evidence(row, donor_only, english_only) if row["western"] else "?"
        row["structural"] = None

    records: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        if row["western"]:
            records[(row["stage"], row["record"])].append(row)
    for sequence in records.values():
        segment(sequence)

    conflicts = 0
    for row in rows:
        structural, evidence = row["structural"], row["evidence"]
        if not row["western"]:
            row["language"], row["basis"] = "non_western", "container"
        elif structural:
            row["language"], row["basis"] = structural, "structure"
            if evidence != "?" and (evidence == "d") != (structural == "donor"):
                conflicts += 1
                row["basis"] = "conflict"
        elif evidence == "d":
            row["language"], row["basis"] = "donor", "vocabulary"
        elif evidence == "e":
            row["language"], row["basis"] = "english", "vocabulary"
        else:
            row["language"], row["basis"] = "unknown", "none"
    return {"conflicts": conflicts,
            "donor_only_tokens": len(donor_only),
            "english_only_tokens": len(english_only)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--romfs", type=Path, default=CLEAN,
                        help="romfs root to scan (default: the English clean tree)")
    parser.add_argument("--out", type=Path, required=True,
                        help="output directory for the locations/unique/summary files")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rows = read_locations(args.romfs)
    diagnostics = resolve(rows)

    fields = ["stage", "record", "resource", "table_word", "bytes", "language", "basis",
              "kind", "accent", "text", "raw_hex"]
    with (args.out / "stage-text-locations.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Dedupe on the raw bytes, not the decoded text: two strings that decode the
    # same can differ in control tokens, and a build has to replace bytes.
    groups: dict[str, dict] = {}
    stages: dict[str, set[str]] = defaultdict(set)
    branches: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        key = row["raw_hex"]
        entry = groups.get(key)
        if entry is None:
            entry = groups[key] = {
                "language": row["language"], "basis": row["basis"], "kind": row["kind"],
                "bytes": row["bytes"], "text": row["text"], "raw_hex": key,
                "words": len(WORD.findall(row["text"])), "locations": 0,
                "first_stage": row["stage"], "first_record": row["record"],
                "first_resource": row["resource"],
            }
        entry["locations"] += 1
        # A string can be reached through both a resolved and an unresolved slot;
        # prefer the structurally resolved label for the deduplicated row.
        if entry["basis"] != "structure" and row["basis"] == "structure":
            entry["language"], entry["basis"] = row["language"], row["basis"]
        stages[key].add(row["stage"])
        if row["basis"] == "structure":
            branches[key].add(row["language"])
    unique = []
    for key, entry in groups.items():
        seen = branches.get(key, set())
        # A proper noun ("Rassvet", "AK-47") occupies a slot in every branch, so it
        # is on screen whatever language the player picked. That is still Latin text
        # a Korean build has to deal with, so it is called out rather than folded
        # into either branch.
        if len(seen) > 1:
            span = "shared"
        elif seen:
            span = next(iter(seen))
        elif entry["language"] in ("english", "donor"):
            span = entry["language"]
        else:
            span = entry["language"]
        unique.append(dict(entry, stages=len(stages[key]), branch_span=span))
    unique.sort(key=lambda e: (-e["locations"], e["text"]))

    unique_fields = ["language", "branch_span", "basis", "kind", "locations", "stages",
                     "bytes", "words", "text", "first_stage", "first_record",
                     "first_resource", "raw_hex"]
    with (args.out / "stage-text-unique.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=unique_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(unique)

    # Everything a Korean player would still see in Latin script: the English
    # branch, the strings shared by all three branches, and the handful with no
    # separating evidence either way (which read as English on inspection).
    scope = [e for e in unique if e["branch_span"] in ("english", "shared", "unknown")]
    with (args.out / "stage-text-english-worklist.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=unique_fields + ["korean"],
                                extrasaction="ignore")
        writer.writeheader()
        for entry in sorted(scope, key=lambda e: (-e["locations"], e["text"])):
            writer.writerow(dict(entry, korean=""))

    def tally(items, key):
        return dict(Counter(item[key] for item in items).most_common())

    def bucket(name, field="language"):
        selected = [e for e in unique if e[field] == name]
        return {
            "unique": len(selected),
            "locations": sum(e["locations"] for e in selected),
            "unique_bytes": sum(e["bytes"] for e in selected),
            "by_kind": tally(selected, "kind"),
            "by_basis": tally(selected, "basis"),
        }

    summary = {
        "romfs": str(args.romfs),
        "stage_files": len(sorted(args.romfs.glob("stage/**/scenerio.gcx"))),
        "string_locations": len(rows),
        "unique_strings": len(unique),
        "diagnostics": diagnostics,
        "locations_by_language": tally(rows, "language"),
        "locations_by_basis": tally(rows, "basis"),
        "unique_by_language": tally(unique, "language"),
        "unique_by_branch_span": tally(unique, "branch_span"),
        "english": bucket("english"),
        "donor": bucket("donor"),
        "unknown": bucket("unknown"),
        "non_western": bucket("non_western"),
        "korean_scope": {
            "english_branch": bucket("english", "branch_span"),
            "shared_all_branches": bucket("shared", "branch_span"),
            "no_evidence": bucket("unknown", "branch_span"),
            "total_unique": len(scope),
            "total_locations": sum(e["locations"] for e in scope),
            "total_unique_bytes": sum(e["bytes"] for e in scope),
            "prose_unique": sum(1 for e in scope if e["kind"] == "prose"),
        },
    }
    (args.out / "stage-text-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
