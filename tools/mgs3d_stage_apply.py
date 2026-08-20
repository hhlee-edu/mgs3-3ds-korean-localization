#!/usr/bin/env python3
"""Validate or safely apply a future stage translation CSV.

Dry-run is the default.  --apply writes only to a separate output root and
never overwrites the source tree.  The tool accepts the expanded worklist's
``current_korean`` column (or an explicit ``korean``/``translation`` column).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10**9)
# Locations that must never be translated, with the evidence that put them here.
# Keyed by (stage, record, resource).
PERMANENT_EXCLUSIONS = {
    ("r_sna01", 0, 479): (
        "clean 'SAVE\0' -- the codec SAVE channel label. 2026-08-20 resource-level "
        "bisection on hardware: restoring this one resource to clean ASCII, and "
        "nothing else, is what makes the SAVE label render again. Padding, the "
        "appended glyph page and the line-break structure were all cleared first."
    ),
}

NUL = bytes([0])          # string terminator
PAD = bytes([0x20])       # slack filler: a space, never a terminator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import CodecError, GcxRecord, parse_rendered  # noqa: E402
from mgs3d_stage_text_scan import stage_records  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def controls(data: bytes) -> list[str]:
    """Return actual control tokens, excluding high-byte text glyphs.

    The engine consumes any byte >= 0x80 as the start of a 2-byte token, so the
    scan must skip those wholesale. Walking byte-by-byte instead lands inside a
    glyph and can read its payload as a control prefix -- e.g. the global-page
    tokens for 것/긋/명/봐/찍/켠 end in 0x1F and used to fabricate a 1Fxx token.
    Audited 2026-08-19 over all 828,396 pristine stage resources: the two models
    disagree on 950, every one of them a false control invented by the old scan,
    and the corrected scan drops no token the engine would honour (0 cases).
    """
    out = []
    i = 0
    while i < len(data):
        if data[i] == 0:
            break
        if data[i:i + 2] in (b"\xA0\x7B", b"\xC0\x7D"):
            out.append(data[i:i + 2].hex().upper()); i += 2; continue
        if data[i] == 0x1F and i + 1 < len(data):
            out.append(data[i:i + 2].hex().upper()); i += 2; continue
        if data[i] >= 0x80 and i + 1 < len(data):
            i += 2; continue
        i += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--romfs", type=Path, default=ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs")
    ap.add_argument("--worklist", type=Path, default=ROOT / "docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-worklist-expanded.csv")
    ap.add_argument("--locations", type=Path, default=ROOT / "docs/evidence/2026-08-19-stage-text-scan/stage-text-locations.csv")
    ap.add_argument("--character-map", type=Path, default=ROOT / "translation/40_build_input/global_page_v2/character-map.json")
    ap.add_argument("--report", type=Path, default=ROOT / "docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-apply-dryrun.json")
    ap.add_argument("--apply", action="store_true", help="write changed files under --output-root")
    ap.add_argument("--output-root", type=Path, help="separate output romfs root; required with --apply")
    args = ap.parse_args()
    if args.apply and not args.output_root:
        ap.error("--output-root is required with --apply")

    work = read_csv(args.worklist)
    locs = read_csv(args.locations)
    cmap_data = json.loads(args.character_map.read_text(encoding="utf-8")) if args.character_map.is_file() else {}
    cmap = {k: bytes.fromhex(v) for k, v in cmap_data.get("characters", {}).items() if isinstance(v, str)}
    translations = {}
    for row in work:
        text = (row.get("current_korean") or row.get("korean") or row.get("translation") or "").strip()
        if text:
            translations[row["raw_hex"]] = text

    targets = defaultdict(list)
    for row in locs:
        # Only structurally/vocabulary-resolved English locations are eligible.
        # Shared/unknown rows are intentionally held for explicit review.
        if row["language"] == "english" and row["raw_hex"] in translations:
            targets[(row["stage"], int(row["record"]), int(row["resource"]))].append(row)

    errors = []
    changes = []
    excluded = []
    changed_by_file = defaultdict(dict)
    for path in sorted(args.romfs.glob("stage/**/scenerio.gcx")):
        stage = path.parent.name
        records = stage_records(path)
        for (s, ri, resource), loc_rows in list(targets.items()):
            if s != stage:
                continue
            if ri >= len(records):
                errors.append(f"{stage}:{ri}:{resource}: record missing")
                continue
            record = records[ri]
            resources = record.resources()
            if resource >= len(resources):
                errors.append(f"{stage}:{ri}:{resource}: resource missing")
                continue
            reason = PERMANENT_EXCLUSIONS.get((stage, ri, resource))
            if reason is not None:
                excluded.append({"stage": stage, "record": ri, "resource": resource,
                                 "reason": reason})
                continue
            source = resources[resource].data
            expected = loc_rows[0]["raw_hex"]
            if source.hex() != expected:
                errors.append(f"{stage}:{ri}:{resource}: source raw mismatch")
                continue
            try:
                encoded = parse_rendered(translations[expected], cmap)
            except Exception as exc:
                errors.append(f"{stage}:{ri}:{resource}: encode gate: {exc}")
                continue
            if len(encoded) > len(source):
                errors.append(f"{stage}:{ri}:{resource}: overflow {len(encoded)}>{len(source)}")
                continue
            if controls(encoded) != controls(source):
                errors.append(f"{stage}:{ri}:{resource}: control-code stream changed")
                continue
            # Pad back to the resource's original length. Without this the
            # bytes freed by a shorter Korean string are redistributed by
            # replace_resources() and pile up as trailing NULs on the record's
            # LAST resource, which the final gate correctly reports as an
            # unexpected non-EN change (measured 2026-08-19: 89 extra resources,
            # one per touched stage).
            #
            # 2026-08-20: the padding BYTE matters. This used to fill the slack
            # with NUL, on the assumption that "strings are NUL-terminated, so
            # padding is invisible to the reader". Hardware disproved that:
            # v001a built this way reproduced The Boss showing EVA and Major
            # Tom's missing name, and the byte-identical build with only the
            # surplus NULs replaced (diagnostic P1) rendered both correctly.
            # Korean is shorter than English, so this was adding 17,269 extra
            # terminators to v001a alone: 9,424 NUL bytes in clean became
            # 26,693. Keep exactly the terminator run the clean resource had
            # and fill the rest with spaces, which cannot read as another empty
            # string. The resource length is still preserved exactly.
            slack = len(source) - len(encoded)
            if slack > 0:
                keep = max(1, len(source) - len(source.rstrip(NUL)))
                core = encoded.rstrip(NUL)
                if len(core) + keep <= len(source):
                    encoded = (core + NUL * keep
                               + PAD * (len(source) - len(core) - keep))
                else:
                    encoded = encoded + NUL * slack
            changed_by_file[path][(ri, resource)] = encoded
            changes.append({"stage": stage, "record": ri, "resource": resource, "old_bytes": len(source), "new_bytes": len(encoded), "occurrences": len(loc_rows)})

    report = {
        "format": "mgs3d-stage-apply-dryrun-v1",
        "permanently_excluded": excluded,
        "dry_run": not args.apply,
        "source_root": str(args.romfs),
        "changed_resources": len(changes),
        "errors": errors,
        "fr_es_write_policy": "never target non-English locations",
        "control_code_gate": "exact token stream",
        "capacity_gate": "encoded bytes <= original resource slot",
        "output_root": str(args.output_root) if args.output_root else None,
        "changes": changes,
    }
    if errors or not args.apply:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("dry_run", "changed_resources", "errors", "output_root")}, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    # Only after every file/resource passed all gates, write to a separate root.
    out_root = args.output_root
    for src in sorted(args.romfs.glob("stage/**/scenerio.gcx")):
        rel = src.relative_to(args.romfs)
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        records = stage_records(src)
        original = src.read_bytes()
        output = bytearray(original)
        for ri, record in enumerate(records):
            repl = {resource: data for (record_i, resource), data in changed_by_file[src].items() if record_i == ri}
            if repl:
                rebuilt = GcxRecord(record.replace_resources(repl, preserve_layout=True), record.source_offset).raw
                output[record.source_offset:record.source_offset + len(rebuilt)] = rebuilt
        # Keep the file's byte length exactly. replace_resources() trims the
        # rebuilt record to its logical size and then re-pads it to the record
        # alignment; the shipped stage files are not padded at EOF, so the last
        # record came back 1-15 bytes longer in 146 of 169 files. Those bytes
        # are all NUL (verified), but the length change matters downstream: the
        # RomForge staging tree appends a resident Korean glyph page at EOF,
        # anchored 65,275 bytes from the end of the file, so any change in file
        # length moves it. Trim the NUL surplus back.
        if len(output) > len(original) and not any(output[len(original):]):
            del output[len(original):]
        if len(output) != len(original):
            raise SystemExit(f"{rel}: rebuilt length {len(output)} != original {len(original)}")
        dst.write_bytes(bytes(output))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("dry_run", "changed_resources", "errors", "output_root")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
