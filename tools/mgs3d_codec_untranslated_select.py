#!/usr/bin/env python3
"""Review untranslated codec rows and safely prioritize them in a 191-glyph build."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402


class ReviewError(ValueError):
    pass


FIELDS = (
    "accept", "priority", "gcx", "resource", "reason", "missing_count",
    "missing_glyphs", "record_headroom", "english", "korean", "replacement", "note",
)


def key(unit: dict[str, object]) -> tuple[int, int]:
    return int(unit["gcx"]), int(unit["resource"])


def hangul(text: str) -> set[str]:
    return {character for character in text if 0xAC00 <= ord(character) <= 0xD7A3}


def translation_keys(document: dict[str, object]) -> set[tuple[int, int]]:
    return {
        key(unit) for unit in document.get("units", [])
        if str(unit.get("text", "")) != "<00>"
    }


def fit_priority_rows(
    required: set[str], rows: list[dict[str, object]], slots: int
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    chosen: list[dict[str, object]] = []
    overflow: list[dict[str, object]] = []
    characters = set(required)
    for row in rows:
        trial = characters | hangul(str(row["text"]))
        if len(trial) <= slots:
            chosen.append(row)
            characters = trial
        else:
            overflow.append(row)
    return chosen, overflow


def priority_preserving_allocation(
    current_allocation: dict[str, object],
    baseline: dict[str, object],
    requested: list[dict[str, object]],
) -> tuple[dict[str, object], list[tuple[str, str]]]:
    """Replace the least damaging optional glyphs while retaining token addresses."""
    current = dict(current_allocation["characters"])
    required = set(current_allocation.get("required_hangul", []))
    incoming = sorted(
        set().union(*(hangul(str(unit["text"])) for unit in requested)) - set(current)
        if requested else set()
    )
    optional = set(current) - required
    if len(incoming) > len(optional):
        raise ReviewError("requested rows require more glyphs than the optional static slots")
    baseline_rows = [
        hangul(str(unit.get("text", "")))
        for unit in baseline.get("units", [])
        if str(unit.get("text", "")) != "<00>"
    ]
    frequency = {
        character: sum(character in characters for characters in baseline_rows)
        for character in optional
    }
    removed: set[str] = set()
    swaps: list[tuple[str, str]] = []
    for new_character in incoming:
        choices = []
        for old_character in optional - removed:
            trial = removed | {old_character}
            lost = sum(bool(characters & trial) for characters in baseline_rows)
            choices.append((lost, frequency[old_character], ord(old_character), old_character))
        _, _, _, old_character = min(choices)
        token = current.pop(old_character)
        current[new_character] = token
        removed.add(old_character)
        swaps.append((old_character, new_character))
    ordered = dict(sorted(current.items(), key=lambda item: int(item[1], 16)))
    allocation = {
        "format": "mgs3d-static-korean-allocation-priority-v1",
        "characters": ordered,
        "required_hangul": list(current_allocation.get("required_hangul", [])),
        "glyph_swaps": [{"out": old, "in": new} for old, new in swaps],
    }
    return allocation, swaps


def read_document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def command_catalog(args: argparse.Namespace) -> None:
    candidate = read_document(args.candidate)
    selected = read_document(args.selected)
    report = read_document(args.report)
    records = parse_codec(args.codec.read_bytes())
    selected_keys = translation_keys(selected)
    static_map = set(candidate.get("character_map", {}))
    report_by_gcx = {int(row["gcx"]): row for row in report["records"]}
    rows: list[dict[str, object]] = []
    priority = 1
    for unit in candidate.get("units", []):
        gcx, resource = key(unit)
        if (gcx, resource) in selected_keys:
            continue
        text = str(unit["text"])
        missing = sorted(hangul(text) - static_map)
        reason = "static_glyph" if missing else "string_capacity"
        resources = records[gcx].resources()
        english = decode_western(resources[resource].data)
        rows.append({
            "accept": "", "priority": priority, "gcx": gcx,
            "resource": resource, "reason": reason,
            "missing_count": len(missing), "missing_glyphs": "".join(missing),
            "record_headroom": int(report_by_gcx[gcx]["headroom"]),
            "english": english, "korean": text, "replacement": "", "note": "",
        })
        priority += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    glyph_rows = sum(row["reason"] == "static_glyph" for row in rows)
    print(
        f"wrote {args.output}: {len(rows)} untranslated rows "
        f"({glyph_rows} static-glyph, {len(rows) - glyph_rows} string-capacity)"
    )


def accepted_review_rows(path: Path, units: dict[tuple[int, int], dict[str, object]]) -> list[dict[str, object]]:
    accepted: list[tuple[int, int, dict[str, object]]] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"accept", "priority", "gcx", "resource"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ReviewError(f"review CSV requires columns: {', '.join(sorted(required))}")
        for line, row in enumerate(reader, 2):
            if row["accept"].strip().lower() not in {"yes", "y", "1", "true", "한글"}:
                continue
            item_key = int(row["gcx"]), int(row["resource"])
            if item_key not in units:
                raise ReviewError(f"unknown candidate {item_key} at line {line}")
            unit = dict(units[item_key])
            replacement = row.get("replacement", "").strip()
            edited_korean = row.get("korean", "").strip()
            if not replacement and edited_korean and edited_korean != str(unit.get("text", "")):
                replacement = edited_korean
            if replacement:
                if "<00>" not in replacement:
                    raise ReviewError(f"replacement must preserve <00> at line {line}")
                unit["text"] = replacement
            accepted.append((int(row["priority"]), line, unit))
    accepted.sort(key=lambda item: (item[0], item[1]))
    return [unit for _, _, unit in accepted]


def apply_allocation(document: dict[str, object], allocation: dict[str, object]) -> dict[str, object]:
    result = dict(document)
    result["character_map"] = dict(allocation["characters"])
    result["static_korean_allocation"] = "static_allocation.json"
    return result


def command_select(args: argparse.Namespace) -> None:
    candidate = read_document(args.candidate)
    baseline = read_document(args.baseline_selected)
    fixed_report = read_document(args.baseline_report)
    required_allocation = read_document(args.required_allocation)
    units = {key(unit): unit for unit in candidate.get("units", [])}
    requested = accepted_review_rows(args.review, units)
    requested_by_key = {key(unit): unit for unit in requested}
    working_candidate = dict(candidate)
    working_candidate["units"] = [
        requested_by_key.get(key(unit), unit) for unit in candidate.get("units", [])
    ]
    required = set(required_allocation.get("required_hangul", []))
    feasible, glyph_overflow = fit_priority_rows(required, requested, args.slots)

    if len(required_allocation.get("characters", {})) != args.slots:
        raise ReviewError("required allocation character count does not match --slots")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    allocation_path = args.output_dir / "static_allocation.json"
    mapped_path = args.output_dir / "codec_candidate.json"
    priority_path = args.output_dir / "codec_priority.json"
    selected_path = args.output_dir / "codec_selected.json"
    selector_report_path = args.output_dir / "codec_selection_report.json"
    selector = Path(__file__).resolve().parent / "mgs3d_codec_size_neutral_select.py"
    active = list(feasible)
    rejected_by_string: set[tuple[int, int]] = set()
    swaps: list[tuple[str, str]] = []
    for _ in range(len(feasible) + 1):
        allocation, swaps = priority_preserving_allocation(
            required_allocation, baseline, active
        )
        mapped = apply_allocation(working_candidate, allocation)
        priority_document = {
            "format": "mgs3d-codec-translation-v1",
            "character_map": allocation["characters"],
            "units": active,
        }
        allocation_path.write_text(json.dumps(allocation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        mapped_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        priority_path.write_text(json.dumps(priority_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        command = [
            sys.executable, str(selector), str(args.codec), str(mapped_path), str(selected_path),
            "--report", str(selector_report_path),
            "--donor-report", str(args.baseline_report),
            "--priority-translation", str(priority_path),
            "--max-new-glyphs", "0",
        ]
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            raise ReviewError(f"size-neutral selector failed with exit code {completed.returncode}")
        selected = read_document(selected_path)
        selected_keys_now = translation_keys(selected)
        kept = [unit for unit in active if key(unit) in selected_keys_now]
        dropped = {key(unit) for unit in active if key(unit) not in selected_keys_now}
        rejected_by_string.update(dropped)
        if len(kept) == len(active):
            break
        active = kept
    else:
        raise ReviewError("priority selection did not converge")

    selected_keys = translation_keys(selected)
    baseline_keys = translation_keys(baseline)
    requested_keys = {key(unit) for unit in requested}
    overflow_keys = {key(unit) for unit in glyph_overflow}
    selected_requested = requested_keys & selected_keys
    string_overflow = (requested_keys - selected_requested - overflow_keys) | rejected_by_string
    result = {
        "format": "mgs3d-codec-priority-selection-v1",
        "requested": len(requested),
        "selected_requested": len(selected_requested),
        "kept_english_static_glyph_capacity": len(overflow_keys),
        "kept_english_string_capacity": len(string_overflow),
        "total_selected": len(selected_keys),
        "baseline_selected": len(baseline_keys),
        "newly_korean": [f"{gcx}:{resource}" for gcx, resource in sorted(selected_keys - baseline_keys)],
        "returned_to_english": [f"{gcx}:{resource}" for gcx, resource in sorted(baseline_keys - selected_keys)],
        "requested_not_selected": [f"{gcx}:{resource}" for gcx, resource in sorted(requested_keys - selected_keys)],
        "glyph_swaps": [{"out": old, "in": new} for old, new in swaps],
    }
    (args.output_dir / "priority-selection-report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (args.output_dir / "requested-result.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        fields = ("gcx", "resource", "result", "text")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for unit in requested:
            item_key = key(unit)
            if item_key in selected_requested:
                status = "한글 적용"
            elif item_key in overflow_keys:
                status = "영어 유지: 정적 글자 191개 초과"
            else:
                status = "영어 유지: GCX 문자열 공간 부족"
            writer.writerow({
                "gcx": item_key[0], "resource": item_key[1],
                "result": status, "text": unit["text"],
            })
    print(
        f"priority result: requested={len(requested)}, selected={len(selected_requested)}, "
        f"English(static)={len(overflow_keys)}, English(string)={len(string_overflow)}, "
        f"total Korean={len(selected_keys)}"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise ReviewError(f"builder failed with exit code {completed.returncode}")


def command_build_files(args: argparse.Namespace) -> None:
    tools = Path(__file__).resolve().parent
    codec_target = args.output_dir / "codec.dat"
    sna01_target = args.output_dir / "stage" / "r_sna01" / "resident.hpk"
    sna02_target = args.output_dir / "stage" / "r_sna02" / "resident.hpk"
    for path in (codec_target, sna01_target, sna02_target):
        path.parent.mkdir(parents=True, exist_ok=True)
    run([
        sys.executable, str(tools / "mgs3d_gcx_font_tool.py"), "build-korean",
        str(args.codec), str(args.selected), str(args.font), str(codec_target),
        "--font-size", str(args.font_size), "--reuse-freed-font", "--preserve-record-layout",
    ])
    for source, target, allocation_report in (
        (args.sna01, sna01_target, args.output_dir / "sna01-allocation-report.json"),
        (args.sna02, sna02_target, args.output_dir / "sna02-allocation-report.json"),
    ):
        run([
            sys.executable, str(tools / "mgs3d_hpk_static_korean.py"),
            str(source), str(args.selected), str(args.font), str(target),
            str(allocation_report), "--font-size", str(args.font_size),
            "--character-allocation", str(args.allocation),
        ])
        if target.stat().st_size != source.stat().st_size:
            raise ReviewError(f"HPK size changed: {target}")
    if codec_target.stat().st_size != args.codec.stat().st_size:
        raise ReviewError("codec.dat size changed")
    source_records = parse_codec(args.codec.read_bytes())
    built_records = parse_codec(codec_target.read_bytes())
    mismatches = [
        index for index, (source, built) in enumerate(zip(source_records, built_records))
        if (
            source.source_offset != built.source_offset
            or len(source.raw) != len(built.raw)
            or source.string_resources_offset != built.string_resources_offset
            or source.font_data_offset != built.font_data_offset
            or source.proc_offset != built.proc_offset
        )
    ]
    if len(source_records) != len(built_records) or mismatches:
        raise ReviewError(f"codec fixed-layout mismatch: {mismatches[:10]}")
    manifest = {
        "format": "mgs3d-codec-priority-files-v1",
        "fixed_codec_records": len(built_records),
        "outputs": [
            {"path": str(path.relative_to(args.output_dir)).replace("\\", "/"),
             "size": path.stat().st_size, "sha256": sha256(path)}
            for path in (codec_target, sna01_target, sna02_target)
        ],
    }
    (args.output_dir / "build-files-report.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"built fixed-size codec + 2 HPKs in {args.output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)
    catalog = sub.add_parser("catalog", help="write all currently untranslated candidates")
    catalog.add_argument("codec", type=Path)
    catalog.add_argument("candidate", type=Path)
    catalog.add_argument("selected", type=Path)
    catalog.add_argument("report", type=Path)
    catalog.add_argument("output", type=Path)
    catalog.set_defaults(function=command_catalog)
    select = sub.add_parser("select", help="prioritize accepted rows without exceeding fixed capacity")
    select.add_argument("codec", type=Path)
    select.add_argument("candidate", type=Path)
    select.add_argument("baseline_selected", type=Path)
    select.add_argument("baseline_report", type=Path)
    select.add_argument("required_allocation", type=Path)
    select.add_argument("review", type=Path)
    select.add_argument("output_dir", type=Path)
    select.add_argument("--slots", type=int, default=191)
    select.set_defaults(function=command_select)
    build = sub.add_parser("build-files", help="build codec.dat and both fixed-size static HPKs")
    build.add_argument("codec", type=Path)
    build.add_argument("selected", type=Path)
    build.add_argument("allocation", type=Path)
    build.add_argument("sna01", type=Path)
    build.add_argument("sna02", type=Path)
    build.add_argument("output_dir", type=Path)
    build.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\malgun.ttf"))
    build.add_argument("--font-size", type=int, default=15)
    build.set_defaults(function=command_build_files)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (OSError, json.JSONDecodeError, ReviewError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
