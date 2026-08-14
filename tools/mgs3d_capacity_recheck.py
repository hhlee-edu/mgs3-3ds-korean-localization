"""Recompute real byte/structural capacity for the FINAL natural translation.

Purpose (explicit user instruction, 2026-08-14): the global Korean glyph page
means per-GCX/per-record glyph-slot scarcity is no longer a real constraint
(verified separately, see docs/v0.68-release-notes.md section 3 and
translation/40_build_input/global_page_v2/coverage-report.json:
corpus_covered=true against the 1120-character map). What remains unverified
is the OTHER constraint: does each GCX record's / each subtitle entry's fixed
byte region actually fit the CURRENT, natural, unshortened Korean text?

This script answers exactly that, against the CURRENT final master CSVs
(codec-3ds-INTEGRATED-review-direct-v2.csv, movie_natural_full.csv,
demo_natural_full.csv) -- not any historical shortened variant -- and reuses
the real build-time formulas rather than re-deriving them:

  codec   -- GcxRecord.replace_resources' preserve_layout check
             (tools/mgs3d_codec_tool.py:282-300): budget is the WHOLE GCX's
             string region (font_data_offset - string_resources_offset),
             shared by every resource in that GCX, not just the translated
             ones.
  movie/demo -- tools/mgs3d_movie_tool.py's fixed_capacity(): budget is each
             individual subtitle entry's own slot
             (len(subtitle.original) - 4 - len(subtitle.tail)), independent
             of its neighbours. Invoked as the real `capacity` subcommand
             against the pristine .dat, so there is no reimplementation risk
             on that side.

Glyph availability is NOT re-checked here (that is the solved half); a
membership check against character-map.json is done only to confirm no row
uses a Hangul character outside the 1120-entry map (which would be a glyph
regression, not a byte-capacity question).

Classification
--------------
  PASS          -- fits in the original region as-is.
  REVIEW        -- does not fit, but donor/reclaimable bytes in the SAME
                   structural unit could cover the gap. Text unmodified.
  MUST_SHORTEN  -- does not fit even after reclaim; the only remaining lever
                   is shortening the Korean text itself.

For codec, "reclaimable" bytes are the current byte length of OTHER resources
in the same GCX tagged is_donor=yes that are not themselves being kept (a
literal, existing byte count -- not a promise that blanking them is risk-free;
that judgement belongs to the existing donor-reclaim tooling
(mgs3d_codec_size_neutral_select.py) and is not re-litigated here).

For movie/demo, no such lever exists: fixed_capacity()'s per-entry budget is
never resized by the existing reclaim tooling (rebuild_record_fixed_reclaim
only ever grows the record's *font* table, never a subtitle's *text* slot --
confirmed by reading the function). So movie/demo REVIEW is structurally
impossible; every non-PASS row is MUST_SHORTEN by construction.

This is READ-ONLY analysis. No translation text and no .dat file is modified.

Usage
-----
    python tools/mgs3d_capacity_recheck.py --report out.md --json out.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import GcxRecord, parse_codec, parse_rendered, CodecError  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

ROOT = Path(__file__).resolve().parent.parent
# NOTE: originals/3ds_pristine/romfs/codec.dat is ALSO a different region/
# build than the one the review CSV's (gcx,resource) indices were captured
# against -- GCX count matches (2326) but ~40% of resource indices are out of
# range against it. Verified 0/22,362 out-of-range against the clean-tree copy
# below instead; use that one.
CODEC_DAT = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
# NOTE: originals/3ds_pristine/romfs/movie.dat and demo.dat are a DIFFERENT,
# smaller region build (movie.dat: 227,328B/93 records/558 subtitles) than the
# one translation/10_master/current/{movie,demo}.csv's `offset`
# column was captured against (movie.dat: 229,376B/108 records/3480 subtitles;
# demo.dat: 772,935,680B/333 records/11,296 subtitles -- matching
# analysis/en_movie_inspect.json / en_demo_inspect.json exactly). The correct
# reference copy, verified by 100% offset-set overlap (689/689 movie,
# 2228/2228 demo) against the CSV, is the one preserved under
# experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/ -- do not swap
# this back to originals/3ds_pristine without re-verifying the offset overlap.
MOVIE_DAT = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/movie.dat"
DEMO_DAT = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/demo.dat"
CODEC_CSV = ROOT / "translation/10_master/current/codec.csv"
CODEC_CSV_V1 = ROOT / "translation/10_master/archive/codec-older/codec-3ds-INTEGRATED-review-direct-v1.csv"
MOVIE_CSV = ROOT / "translation/10_master/current/movie.csv"
DEMO_CSV = ROOT / "translation/10_master/current/demo.csv"
CHAR_MAP = ROOT / "translation/40_build_input/global_page_v2/character-map.json"
MOVIE_SAFE_HISTORICAL = ROOT / "translation/40_build_input/global_page_v2/movie-safe.csv"
MOVIE_MAXSAFE_HISTORICAL = ROOT / "translation/40_build_input/global_page_v2/movie-max-safe.csv"
DEMO_SAFE_HISTORICAL = ROOT / "translation/40_build_input/global_page_v2/demo-safe.csv"
DEMO_MAXSAFE_HISTORICAL = ROOT / "translation/40_build_input/global_page_v2/demo-max-safe.csv"

CTRL = re.compile(r"<[0-9A-Fa-f]{2}>")


def load_char_map() -> dict[str, bytes]:
    doc = json.loads(CHAR_MAP.read_text(encoding="utf-8-sig"))
    return {c: bytes.fromhex(h) for c, h in doc["characters"].items()}


def is_accepted(row: dict) -> bool:
    return (row.get("accept") or "").strip().lower() in ("y", "yes", "1", "ok")


# ---------------------------------------------------------------------------
# codec.dat
# ---------------------------------------------------------------------------
def encoded_len(text: str, char_map: dict[str, bytes]) -> tuple[int, list[str]]:
    """Byte length parse_rendered() would produce, plus any glyphs missing
    from the map (a real regression, reported separately from byte capacity)."""
    n = 0
    missing: list[str] = []
    i = 0
    while i < len(text):
        m = CTRL.match(text, i)
        if m:
            n += 1
            i = m.end()
            continue
        ch = text[i]
        if ch in char_map:
            n += len(char_map[ch])
        elif 0x20 <= ord(ch) <= 0x7E:
            n += 1
        else:
            missing.append(ch)
            n += 2  # assume 2 bytes so capacity numbers stay meaningful
        i += 1
    return n, missing


def analyse_codec(char_map: dict[str, bytes]) -> list[dict]:
    records = parse_codec(CODEC_DAT.read_bytes())

    def load_csv(path: Path) -> dict[tuple[int, int], dict]:
        with open(path, encoding="utf-8-sig") as f:
            return {(int(r["gcx"]), int(r["resource"])): r for r in csv.DictReader(f)}

    v2 = load_csv(CODEC_CSV)
    v1 = load_csv(CODEC_CSV_V1) if CODEC_CSV_V1.exists() else {}

    by_gcx: dict[int, dict[int, dict]] = defaultdict(dict)
    for (gcx, res), row in v2.items():
        by_gcx[gcx][res] = row

    out = []
    for gcx_index, record in enumerate(records):
        rows = by_gcx.get(gcx_index)
        if not rows:
            continue
        try:
            resources = record.resources()
        except CodecError as exc:
            out.append({"gcx": gcx_index, "error": str(exc)})
            continue

        budget = record.font_data_offset - record.string_resources_offset
        translated_here = {r for r, row in rows.items() if is_accepted(row) and (row.get("korean") or "").strip()}

        used = 0
        missing_glyphs: list[str] = []
        donor_reclaimable = 0
        per_resource = []
        for idx, resource in enumerate(resources):
            row = rows.get(idx)
            if idx in translated_here:
                n, missing = encoded_len(row["korean"], char_map)
                missing_glyphs.extend(missing)
                used += n
                per_resource.append({"resource": idx, "role": "translated", "bytes": n})
            else:
                used += len(resource.data)
                is_donor = bool(row and (row.get("is_donor") or "").strip().lower() == "yes")
                if is_donor:
                    donor_reclaimable += len(resource.data)
                per_resource.append({
                    "resource": idx, "role": "donor" if is_donor else "unchanged",
                    "bytes": len(resource.data),
                })

        deficit = max(0, used - budget)
        after_reclaim = max(0, deficit - donor_reclaimable)

        was_deficit = None
        v1_rows = {r: v1.get((gcx_index, r)) for r in rows}
        if v1 and all(v1_rows.values()):
            v1_used = 0
            for idx, resource in enumerate(resources):
                vrow = v1_rows.get(idx) if idx in rows else None
                if vrow and is_accepted(vrow) and (vrow.get("korean") or "").strip():
                    n, _ = encoded_len(vrow["korean"], char_map)
                    v1_used += n
                else:
                    v1_used += len(resource.data)
            was_deficit = max(0, v1_used - budget)

        status = "PASS" if deficit == 0 else ("REVIEW" if after_reclaim == 0 else "MUST_SHORTEN")
        out.append({
            "gcx": gcx_index,
            "resources_translated": sorted(translated_here),
            "available_bytes": budget,
            "korean_encoded_bytes": used,
            "donor_reclaimable_bytes": donor_reclaimable,
            "deficit_bytes": deficit,
            "deficit_after_reclaim_bytes": after_reclaim,
            "status": status,
            "missing_glyphs": sorted(set(missing_glyphs)),
            "was_deficit_bytes_v1": was_deficit,
            "relocation_note": (
                "movable only via --codec-mode experimental-relocate "
                "(shifts every following GCX; not evaluated here, higher risk)"
            ) if deficit else "n/a",
        })
    return out


# ---------------------------------------------------------------------------
# movie.dat / demo.dat
# ---------------------------------------------------------------------------
def analyse_media(name: str, dat: Path, csv_path: Path, out_dir: Path) -> dict:
    out_json = out_dir / f"{name}-capacity-recheck.json"
    cmd = [sys.executable, str(ROOT / "tools/mgs3d_movie_tool.py"), "capacity",
           str(dat), str(csv_path), str(out_json), "--static-allocation", str(CHAR_MAP)]
    subprocess.run(cmd, check=True, cwd=ROOT)
    result = json.loads(out_json.read_text(encoding="utf-8"))

    rows = []
    for record in result["records"]:
        for entry in record["entries"]:
            if entry.get("needed_bytes") is None:
                # missing_characters nonempty -> a genuine glyph-map regression,
                # not a byte-capacity question. Flag distinctly, don't silently
                # count as PASS or MUST_SHORTEN.
                rows.append({
                    "record": record.get("record"), "offset": entry["offset"],
                    "available_bytes": entry.get("capacity_bytes"),
                    "korean_encoded_bytes": None, "donor_reclaimable_bytes": 0,
                    "deficit_bytes": None, "deficit_after_reclaim_bytes": None,
                    "status": "GLYPH_MISSING",
                    "missing_characters": entry.get("missing_characters"),
                    "relocation_note": "n/a",
                })
                continue
            deficit = entry["deficit_bytes"]
            rows.append({
                "record": record.get("record"),
                "offset": entry["offset"],
                "available_bytes": entry.get("capacity_bytes"),
                "korean_encoded_bytes": entry.get("needed_bytes"),
                "donor_reclaimable_bytes": 0,
                "deficit_bytes": deficit,
                "deficit_after_reclaim_bytes": deficit,
                "status": "PASS" if deficit == 0 else "MUST_SHORTEN",
                "relocation_note": (
                    "no lever: rebuild_record_fixed_reclaim only grows the "
                    "font table, never a subtitle's own text slot"
                ) if deficit else "n/a",
            })

    historical = {}
    hist_paths = {
        "movie": (MOVIE_SAFE_HISTORICAL, MOVIE_MAXSAFE_HISTORICAL),
        "demo": (DEMO_SAFE_HISTORICAL, DEMO_MAXSAFE_HISTORICAL),
    }.get(name, (None, None))
    for label, path in zip(("safe", "max_safe"), hist_paths):
        if path and path.exists():
            with open(path, encoding="utf-8-sig") as f:
                historical[label] = {
                    int(r["offset"]) for r in csv.DictReader(f) if is_accepted(r)
                }

    now_pass = {r["offset"] for r in rows if r["status"] == "PASS"}
    freed = {}
    for label, offsets in historical.items():
        was_excluded_before = now_pass - offsets
        freed[label] = len(was_excluded_before)

    return {"summary": result, "rows": rows, "historically_excluded_now_pass": freed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", type=Path, default=Path("capacity_recheck_report.md"))
    ap.add_argument("--json", type=Path, default=Path("capacity_recheck.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    char_map = load_char_map()
    print("codec: parsing GCX records and computing per-GCX byte budgets...")
    codec_rows = analyse_codec(char_map)
    print(f"  {len(codec_rows)} GCX with translated content analysed")

    print("movie: invoking real fixed_capacity() via mgs3d_movie_tool.py capacity...")
    movie = analyse_media("movie", MOVIE_DAT, MOVIE_CSV, args.out_dir)
    print("demo: invoking real fixed_capacity() via mgs3d_movie_tool.py capacity...")
    demo = analyse_media("demo", DEMO_DAT, DEMO_CSV, args.out_dir)

    def tally(rows):
        c = {"PASS": 0, "REVIEW": 0, "MUST_SHORTEN": 0, "GLYPH_MISSING": 0}
        for r in rows:
            key = r.get("status", "MUST_SHORTEN")
            c[key] = c.get(key, 0) + 1
        return c

    codec_tally = tally([r for r in codec_rows if "status" in r])
    movie_tally = tally(movie["rows"])
    demo_tally = tally(demo["rows"])

    codec_must = [r for r in codec_rows if r.get("status") == "MUST_SHORTEN"]
    codec_review = [r for r in codec_rows if r.get("status") == "REVIEW"]
    movie_must = [r for r in movie["rows"] if r["status"] == "MUST_SHORTEN"]
    demo_must = [r for r in demo["rows"] if r["status"] == "MUST_SHORTEN"]

    codec_freed_v1 = sum(
        1 for r in codec_rows
        if r.get("was_deficit_bytes_v1") not in (None, 0) and r.get("deficit_bytes") == 0
    )

    payload = {
        "codec": {"units": "GCX", "rows": codec_rows, "tally": codec_tally},
        "movie": movie, "movie_tally": movie_tally,
        "demo": demo, "demo_tally": demo_tally,
    }
    (args.out_dir / args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Capacity recheck against the FINAL natural translation (2026-08-14)\n")
    lines.append("Analysis only. No translation text or .dat file was modified.\n")
    lines.append("## Summary\n")
    lines.append("| file | unit | total analysed | PASS | REVIEW | MUST_SHORTEN |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(f"| codec | GCX | {sum(codec_tally.values())} | {codec_tally['PASS']} | {codec_tally['REVIEW']} | {codec_tally['MUST_SHORTEN']} |")
    lines.append(f"| movie | subtitle entry | {sum(movie_tally.values())} | {movie_tally['PASS']} | {movie_tally['REVIEW']} | {movie_tally['MUST_SHORTEN']} |")
    lines.append(f"| demo | subtitle entry | {sum(demo_tally.values())} | {demo_tally['PASS']} | {demo_tally['REVIEW']} | {demo_tally['MUST_SHORTEN']} |")
    lines.append("")
    lines.append(f"codec rows that WERE over budget under v1 and are now PASS: **{codec_freed_v1}**\n")
    for name, freed in (("movie", movie["historically_excluded_now_pass"]),
                        ("demo", demo["historically_excluded_now_pass"])):
        for label, n in freed.items():
            lines.append(f"{name}: entries excluded from the old `{label}` selection that PASS now: **{n}**")
    lines.append("")

    lines.append("## codec.dat -- MUST_SHORTEN GCX (byte overage)\n")
    lines.append("| GCX | budget | used | deficit | donor-reclaimable | deficit after reclaim |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(codec_must, key=lambda r: -r["deficit_after_reclaim_bytes"]):
        lines.append(f"| {r['gcx']} | {r['available_bytes']} | {r['korean_encoded_bytes']} | "
                     f"{r['deficit_bytes']} | {r['donor_reclaimable_bytes']} | {r['deficit_after_reclaim_bytes']} |")
    if not codec_must:
        lines.append("| (none) | | | | | |")
    lines.append("")

    lines.append("## codec.dat -- REVIEW GCX (over budget, donor reclaim in-GCX covers it)\n")
    lines.append("| GCX | budget | used | deficit | donor-reclaimable |")
    lines.append("|---|---|---|---|---|")
    for r in sorted(codec_review, key=lambda r: -r["deficit_bytes"]):
        lines.append(f"| {r['gcx']} | {r['available_bytes']} | {r['korean_encoded_bytes']} | "
                     f"{r['deficit_bytes']} | {r['donor_reclaimable_bytes']} |")
    if not codec_review:
        lines.append("| (none) | | | | |")
    lines.append("")

    for label, rows in (("movie", movie_must), ("demo", demo_must)):
        lines.append(f"## {label}.dat -- MUST_SHORTEN entries (byte overage, no reclaim lever exists)\n")
        lines.append("| record | offset | budget | needed | deficit |")
        lines.append("|---|---|---|---|---|")
        for r in sorted(rows, key=lambda r: -r["deficit_bytes"])[:200]:
            lines.append(f"| {r['record']} | {r['offset']} | {r['available_bytes']} | "
                         f"{r['korean_encoded_bytes']} | {r['deficit_bytes']} |")
        if len(rows) > 200:
            lines.append(f"| ... | {len(rows) - 200} more rows in the JSON | | | |")
        if not rows:
            lines.append("| (none) | | | | |")
        lines.append("")

    (args.out_dir / args.report).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {args.out_dir / args.report}")
    print(f"wrote {args.out_dir / args.json}")
    print(f"\ncodec  PASS={codec_tally['PASS']} REVIEW={codec_tally['REVIEW']} MUST_SHORTEN={codec_tally['MUST_SHORTEN']}")
    print(f"movie  PASS={movie_tally['PASS']} MUST_SHORTEN={movie_tally['MUST_SHORTEN']}")
    print(f"demo   PASS={demo_tally['PASS']} MUST_SHORTEN={demo_tally['MUST_SHORTEN']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
