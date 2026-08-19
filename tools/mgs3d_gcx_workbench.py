#!/usr/bin/env python3
"""Drive the per-GCX capacity-review HTML workbench end to end.

`mgs3d_codec_capacity_review_html.py` already renders an offline HTML page
that recalculates a GCX's remaining donor/glyph budget live as you edit
text. What was missing was a driver that feeds it *correct* inputs for the
current state of the master review CSV, and a way to fold an edited
capacity-review JSON back into that CSV. This script adds two subcommands:

    prepare  -- regenerate the translation JSON + a capacity report for a
                chosen set of GCX (or the next N GCX from the leftover
                worklist), patched against the known-good production
                report so it never understates budget the live build
                already proved, then render the review HTML.
    apply    -- take the "codec_compact_reviewed.json" the HTML page's
                "빌드 JSON 저장" button downloads and merge its `text`
                values back into the master review CSV's `korean` column.

See docs/session-handoff-2026-08-05.md ("방법론적 함정") for why a bare
2-flag rerun of mgs3d_codec_size_neutral_select.py must never be trusted
blindly over the recorded production report -- this script always takes
max(production, fresh) per GCX, whole rows (never mixed fields).
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent

DEFAULT_REVIEW = REPO_ROOT / "translation/10_master/current/codec.csv"
DEFAULT_WORKLIST = REPO_ROOT / "translation/30_shortened/translator_worklist_4994.csv"
DEFAULT_BASELINE_CODEC = (
    REPO_ROOT / "archive/old-data/script_ref/romforge_codec.dat.before-ps2none-donor-build-2026-08-05.bak"
)
DEFAULT_PROTECT_REVIEW = REPO_ROOT / "analysis/script_ref/codec_ps2none_protect_review.csv"
DEFAULT_PRODUCTION_REPORT = REPO_ROOT / "analysis/script_ref/full_build/select_report_r2.json"
DEFAULT_SCRATCH_DIR = REPO_ROOT / "analysis/script_ref/full_build/_scratch"

STATUS_PS2NONE = "대사집 대응 없음"


def run(args: list[str]) -> None:
    print(f"$ {' '.join(str(a) for a in args)}")
    subprocess.run([sys.executable, *args], check=True, cwd=REPO_ROOT)


def gcx_list_from_worklist(worklist: Path, count: int) -> list[int]:
    csv.field_size_limit(2 ** 31 - 1)
    with worklist.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        ordered: list[int] = []
        seen: set[int] = set()
        for row in reader:
            gcx = int(row["gcx"])
            if gcx not in seen:
                seen.add(gcx)
                ordered.append(gcx)
                if len(ordered) >= count:
                    break
        return ordered


def load_report_rows(path: Path) -> dict[int, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return {int(row["gcx"]): row for row in document["records"]}


def render_batch(target_gcx: list[int], output: Path, translation_json: Path,
                 args: argparse.Namespace, production_rows: dict[int, dict]) -> None:
    scratch = args.scratch_dir
    tag = f"{target_gcx[0]}-{target_gcx[-1]}_{len(target_gcx)}"

    fresh_report = scratch / f"report_fresh_{tag}.json"
    fresh_selected = scratch / f"selected_fresh_{tag}.json"
    select_cmd = [
        str(TOOLS_DIR / "mgs3d_codec_size_neutral_select.py"),
        str(args.baseline_codec), str(translation_json), str(fresh_selected),
        "--reclaim-non-english", "--reclaim-language-blocks",
        "--protect-review", str(args.protect_review),
        "--report", str(fresh_report),
    ]
    for gcx in target_gcx:
        select_cmd += ["--include-gcx", str(gcx)]
    run(select_cmd)

    fresh_rows = load_report_rows(fresh_report)

    merged_records = []
    for gcx in target_gcx:
        fresh_row = fresh_rows.get(gcx)
        prod_row = production_rows.get(gcx)
        if prod_row is None and fresh_row is None:
            print(f"  GCX {gcx}: not found in either report, skipping")
            continue
        if prod_row is None:
            winner = fresh_row
        elif fresh_row is None:
            winner = prod_row
        elif int(fresh_row["donor_savings"]) > int(prod_row["donor_savings"]):
            winner = fresh_row
        else:
            winner = prod_row
        merged_records.append(winner)

    merged_report = scratch / f"report_merged_{tag}.json"
    merged_report.write_text(json.dumps({"records": merged_records}, indent=2) + "\n", encoding="utf-8")

    html_cmd = [
        str(TOOLS_DIR / "mgs3d_codec_capacity_review_html.py"),
        str(args.baseline_codec), str(translation_json), str(output),
        "--capacity-report", str(merged_report),
    ]
    for gcx in target_gcx:
        html_cmd += ["--gcx", str(gcx)]
    run(html_cmd)

    total_lines = sum(int(row["candidates"]) for row in merged_records)
    remaining = sum(int(row["donor_savings"]) for row in merged_records)
    print(f"  -> {output.name}: {len(target_gcx)} GCX / {total_lines} lines, "
          f"GCX {target_gcx[0]}~{target_gcx[-1]}, donor_savings sum={remaining}B")


def split_chunks(items: list[int], count: int) -> list[list[int]]:
    count = min(count, len(items))
    base, extra = divmod(len(items), count)
    chunks = []
    cursor = 0
    for index in range(count):
        size = base + (1 if index < extra else 0)
        chunks.append(items[cursor:cursor + size])
        cursor += size
    return chunks


def cmd_prepare(args: argparse.Namespace) -> int:
    scratch = args.scratch_dir
    scratch.mkdir(parents=True, exist_ok=True)

    translation_json = scratch / "translation.json"
    flagged_json = scratch / "translation_flagged.json"
    run([str(TOOLS_DIR / "mgs3d_codec_ps2none_translation_build.py"),
         str(args.review), str(translation_json), "--flagged-output", str(flagged_json)])

    production_rows = load_report_rows(args.production_report) if args.production_report.exists() else {}

    if args.split_into:
        all_gcx = gcx_list_from_worklist(args.worklist, count=10 ** 9)
        chunks = split_chunks(all_gcx, args.split_into)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        width = len(str(len(chunks)))
        print(f"splitting {len(all_gcx)} GCX from {args.worklist.name} into {len(chunks)} files:")
        for index, chunk in enumerate(chunks, start=1):
            output = args.output_dir / f"gcx_batch_{index:0{width}d}_of_{len(chunks)}.html"
            render_batch(chunk, output, translation_json, args, production_rows)
        print(f"\nopen files in {args.output_dir} one at a time, edit, then run "
              f"'apply <downloaded codec_compact_reviewed.json>' after each to fold changes back")
        return 0

    if args.gcx:
        target_gcx = list(dict.fromkeys(args.gcx))
    elif args.from_worklist:
        target_gcx = gcx_list_from_worklist(args.worklist, args.from_worklist)
        print(f"picked {len(target_gcx)} GCX from worklist: {target_gcx}")
    else:
        raise SystemExit("prepare needs --gcx, --from-worklist, or --split-into")
    if not target_gcx:
        raise SystemExit("no target GCX resolved")
    if not args.output:
        raise SystemExit("--output is required unless using --split-into")

    render_batch(target_gcx, args.output, translation_json, args, production_rows)
    print(f"\nopen {args.output} in a browser, edit, then run "
          f"'apply <downloaded codec_compact_reviewed.json>' to fold changes back")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    document = json.loads(args.input.read_text(encoding="utf-8"))
    units = document.get("units", [])
    if not units:
        raise SystemExit("input JSON has no units")

    csv.field_size_limit(2 ** 31 - 1)
    with args.review.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    index: dict[tuple[int, int], dict] = {}
    for row in rows:
        try:
            key = (int(row["gcx"]), int(row["resource"]))
        except (KeyError, ValueError):
            continue
        index[key] = row

    updated = 0
    missing: list[tuple[int, int]] = []
    for unit in units:
        key = (int(unit["gcx"]), int(unit["resource"]))
        row = index.get(key)
        if row is None:
            missing.append(key)
            continue
        row["korean"] = str(unit["text"])
        updated += 1

    if missing:
        print(f"ERROR: {len(missing)} unit(s) had no matching (gcx,resource) row in {args.review}:")
        for gcx, resource in missing[:20]:
            print(f"  gcx={gcx} resource={resource}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        return 1

    backup = args.review.with_name(
        f"{args.review.name}.bak-{datetime.now():%Y-%m-%d-%H%M%S}-gcx-workbench-apply")
    backup.write_bytes(args.review.read_bytes())

    with args.review.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"backed up {args.review} -> {backup}")
    print(f"updated {updated}/{len(units)} rows in {args.review}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="render a live capacity-review HTML for chosen GCX")
    prepare.add_argument("--gcx", type=int, nargs="+", help="explicit GCX to include, space-separated")
    prepare.add_argument("--from-worklist", type=int,
                         help="instead of --gcx, take the next N distinct GCX from the leftover worklist")
    prepare.add_argument("--split-into", type=int,
                         help="instead of --gcx/--from-worklist, split the ENTIRE worklist's GCX into this "
                              "many batch HTML files (written to --output-dir)")
    prepare.add_argument("--output", type=Path, help="required unless using --split-into")
    prepare.add_argument("--output-dir", type=Path, default=DEFAULT_SCRATCH_DIR.parent / "gcx_batches",
                         help="directory for batch files when using --split-into")
    prepare.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    prepare.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    prepare.add_argument("--baseline-codec", type=Path, default=DEFAULT_BASELINE_CODEC)
    prepare.add_argument("--protect-review", type=Path, default=DEFAULT_PROTECT_REVIEW)
    prepare.add_argument("--production-report", type=Path, default=DEFAULT_PRODUCTION_REPORT)
    prepare.add_argument("--scratch-dir", type=Path, default=DEFAULT_SCRATCH_DIR)
    prepare.set_defaults(func=cmd_prepare)

    apply_ = sub.add_parser("apply", help="merge an edited capacity-review JSON back into the master CSV")
    apply_.add_argument("input", type=Path, help="codec_compact_reviewed.json downloaded from the HTML page")
    apply_.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    apply_.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
