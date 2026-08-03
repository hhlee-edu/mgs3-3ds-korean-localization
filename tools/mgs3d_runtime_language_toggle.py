#!/usr/bin/env python3
"""Toggle selected MGS3D translations back to their original English text."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


class ToggleError(ValueError):
    pass


HANGUL = re.compile(r"[\uac00-\ud7a3]")
ENGLISH_ACTIONS = {"english", "en", "영어", "exclude", "off", "no", "0"}
KOREAN_ACTIONS = {"", "korean", "ko", "한글", "include", "on", "yes", "1"}
FIELDS = ("media", "id", "gcx", "resource", "offset", "action", "korean", "note")


def is_codec_translation(unit: dict[str, object]) -> bool:
    """Distinguish selected source translations from selector-injected donors."""
    return str(unit.get("text", "")) != "<00>"


def read_codec(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if document.get("format") != "mgs3d-codec-translation-v1":
        raise ToggleError(f"unsupported codec translation format: {path}")
    if not isinstance(document.get("units"), list):
        raise ToggleError(f"codec translation has no units array: {path}")
    return document


def codec_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for unit in read_codec(path)["units"]:
        text = str(unit.get("text", ""))
        if not is_codec_translation(unit):
            continue
        gcx, resource = int(unit["gcx"]), int(unit["resource"])
        rows.append({
            "media": "codec", "id": f"codec:{gcx}:{resource}",
            "gcx": str(gcx), "resource": str(resource), "offset": "",
            "action": "한글", "korean": text, "note": "",
        })
    return rows


def media_rows(media: str, path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"offset", "korean"}.issubset(reader.fieldnames):
            raise ToggleError(f"{media} CSV requires offset and korean columns: {path}")
        for source in reader:
            if "accept" in source and source["accept"].strip().lower() not in {"yes", "1", "true", "on"}:
                continue
            offset = int(source["offset"])
            rows.append({
                "media": media, "id": f"{media}:{offset}",
                "gcx": "", "resource": "", "offset": str(offset),
                "action": "한글", "korean": source["korean"], "note": "",
            })
    return rows


def make_catalog(codec: Path | None, movie: Path | None, demo: Path | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if codec:
        rows.extend(codec_rows(codec))
    if movie:
        rows.extend(media_rows("movie", movie))
    if demo:
        rows.extend(media_rows("demo", demo))
    identifiers = [row["id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ToggleError("duplicate translation identifiers in catalog inputs")
    return rows


def write_catalog(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_english_decisions(path: Path) -> tuple[set[str], int]:
    excluded: set[str] = set()
    total = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"id", "action"}.issubset(reader.fieldnames):
            raise ToggleError("decision CSV requires id and action columns")
        for line, row in enumerate(reader, 2):
            identifier = row["id"].strip()
            action = row["action"].strip().lower()
            if not identifier:
                raise ToggleError(f"empty id at decision CSV line {line}")
            if action in ENGLISH_ACTIONS:
                excluded.add(identifier)
            elif action not in KOREAN_ACTIONS:
                raise ToggleError(f"unknown action {row['action']!r} at decision CSV line {line}")
            total += 1
    return excluded, total


def filter_codec(source: Path, target: Path, excluded: set[str]) -> tuple[int, int]:
    document = read_codec(source)
    units = document["units"]
    kept = []
    removed = 0
    for unit in units:
        identifier = f"codec:{int(unit['gcx'])}:{int(unit['resource'])}"
        if identifier in excluded and is_codec_translation(unit):
            removed += 1
        else:
            kept.append(unit)
    document["units"] = kept
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed, len(kept)


def filter_media(media: str, source: Path, target: Path, excluded: set[str]) -> tuple[int, int]:
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"offset", "korean"}.issubset(reader.fieldnames):
            raise ToggleError(f"{media} CSV requires offset and korean columns: {source}")
        rows = list(reader)
        fieldnames = reader.fieldnames
    if "accept" not in fieldnames:
        fieldnames = ["accept", *fieldnames]
        for row in rows:
            row["accept"] = "yes"
    removed = 0
    for row in rows:
        identifier = f"{media}:{int(row['offset'])}"
        if identifier in excluded:
            row["accept"] = ""
            removed += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return removed, len(rows) - removed


def command_catalog(args: argparse.Namespace) -> None:
    rows = make_catalog(args.codec, args.movie, args.demo)
    if not rows:
        raise ToggleError("select at least one non-empty translation input")
    write_catalog(args.output, rows)
    counts = {media: sum(row["media"] == media for row in rows) for media in ("codec", "movie", "demo")}
    print(f"wrote {args.output}: codec={counts['codec']}, movie={counts['movie']}, demo={counts['demo']}")


def command_apply(args: argparse.Namespace) -> None:
    excluded, decision_count = read_english_decisions(args.decisions)
    excluded.update(args.english or [])
    known = {row["id"] for row in make_catalog(args.codec, args.movie, args.demo)}
    unknown = sorted(excluded - known)
    if unknown:
        sample = ", ".join(unknown[:5])
        raise ToggleError(f"English decisions not present in inputs: {sample}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "format": "mgs3d-runtime-language-toggle-v1",
        "decisions": decision_count,
        "english": len(excluded),
        "outputs": {},
    }
    if args.codec:
        target = args.output_dir / "codec_translation.json"
        removed, kept = filter_codec(args.codec, target, excluded)
        summary["outputs"]["codec"] = {"path": target.name, "english": removed, "units_kept": kept}
    for media, source in (("movie", args.movie), ("demo", args.demo)):
        if source:
            target = args.output_dir / f"{media}_translation.csv"
            removed, kept = filter_media(media, source, target, excluded)
            summary["outputs"][media] = {"path": target.name, "english": removed, "accepted": kept}
    report = args.output_dir / "language-toggle-report.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output_dir}: {len(excluded)} rows restored to original English")


def add_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--codec", type=Path)
    parser.add_argument("--movie", type=Path)
    parser.add_argument("--demo", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)
    catalog = sub.add_parser("catalog", help="make an editable Korean/English decision CSV")
    catalog.add_argument("output", type=Path)
    add_inputs(catalog)
    catalog.set_defaults(function=command_catalog)
    apply = sub.add_parser("apply", help="apply English decisions without changing source files")
    apply.add_argument("decisions", type=Path)
    apply.add_argument("output_dir", type=Path)
    apply.add_argument(
        "--english", action="append",
        help="restore one stable id to English without editing the CSV (repeatable)",
    )
    add_inputs(apply)
    apply.set_defaults(function=command_apply)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        if not any((args.codec, args.movie, args.demo)):
            raise ToggleError("provide at least one of --codec, --movie, or --demo")
        args.function(args)
        return 0
    except (OSError, json.JSONDecodeError, ToggleError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
