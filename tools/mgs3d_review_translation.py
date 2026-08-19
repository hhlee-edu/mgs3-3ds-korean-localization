#!/usr/bin/env python3
"""Prepare, apply, and audit Korean overrides for an MGS3D v10 review save."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


DATA_RE = re.compile(r"const DATA=(\{.*?\});\s*const", re.DOTALL)


def load_html(path: Path) -> dict:
    match = DATA_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"embedded DATA object not found in {path}")
    return json.loads(match.group(1))


def active_relation_map(state: dict) -> tuple[dict[str, dict], dict[str, list[str]]]:
    selected: dict[str, dict] = {}
    seen: dict[str, list[str]] = defaultdict(list)
    for relation in state.get("relations", []):
        if relation.get("active") is False or relation.get("decision") != "match":
            continue
        for row_id in relation.get("left_ids", []):
            seen[row_id].append(str(relation.get("id", "")))
            # The review UI rebuilds relLeft in array order; the last active
            # relation therefore owns a duplicated left ID.
            selected[row_id] = relation
    return selected, {key: value for key, value in seen.items() if len(value) > 1}


def script_ref(script_row: dict, overrides: dict[str, str]) -> str:
    key = str(script_row.get("index"))
    if key in overrides:
        return str(overrides[key] or "")
    values = script_row.get("dp_korean") or []
    return " / ".join(values) if values else str(script_row.get("korean") or "")


def target_rows(html: dict, state: dict, *, all_untranslated: bool = False) -> tuple[list[dict], dict[str, list[str]]]:
    rows = html["ROWS"]
    row_by_id = {row["id"]: row for row in rows}
    row_position = {row["id"]: index for index, row in enumerate(rows)}
    script = {int(row["index"]): row for row in html["SCRIPT"]}
    relations, duplicates = active_relation_map(state)
    existing = state.get("translation_overrides", {})
    ps2_overrides = state.get("script_ref_overrides", {})
    output = []
    candidates = ((row["id"], relations.get(row["id"], {})) for row in rows) if all_untranslated else relations.items()
    for row_id, relation in candidates:
        row = row_by_id.get(row_id)
        if (not row or not str(row.get("english") or "").strip()
                or row.get("korean") or existing.get(row_id)):
            continue
        right = [script[index] for index in map(int, relation.get("right_sequences", []))
                 if index in script]
        pos = row_position[row_id]
        neighbors = rows[max(0, pos - 2):pos] + rows[pos + 1:pos + 3]
        output.append({
            "id": row_id,
            "container": row["type"],
            "scene": row["group"],
            "record": row.get("record", ""),
            "entry": row.get("entry", ""),
            "offset": row["offset"],
            "speaker": "",
            "source_en": row["english"],
            "ref_en": " / ".join(item.get("english", "") for item in right),
            "ref_ko": " / ".join(filter(None, (script_ref(item, ps2_overrides)
                                                   for item in right))),
            "context": [{"speaker": "", "text": item.get("english", "")}
                        for item in neighbors],
            "char_budget": max(4, len(row["english"])),
            "relation_id": relation.get("id", ""),
            "relation_type": relation.get("relation_type", ""),
            "duplicate_relations": "|".join(duplicates.get(row_id, [])),
        })
    output.sort(key=lambda row: (row["container"], int(row["offset"])))
    return output, duplicates


def command_prepare(args: argparse.Namespace) -> None:
    html = load_html(args.html)
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    rows, duplicates = target_rows(html, state, all_untranslated=args.all_untranslated)
    if args.limit is not None:
        rows = rows[:args.limit]
    document = {
        "format": "mgs3d-review-v10-translation-batch-v1",
        "system_prompt": (
            "Metal Gear Solid 3 자막을 자연스러운 한국어로 번역한다. 대사집 참고문이 "
            "있으면 고유명사와 말투를 따르되, source_en 한 줄에 해당하는 내용만 출력한다. "
            "설명, 따옴표, 접두어 없이 번역문만 출력하고 앞뒤 자막과 말투를 연결한다. "
            "영문 정보를 생략하거나 임의로 추가하지 않는다."
        ),
        "rows": rows,
        "summary": {"target_rows": len(rows), "duplicate_left_ids": len(duplicates)},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"prepared {len(rows)} rows; {len(duplicates)} duplicated active left IDs")


def command_apply(args: argparse.Namespace) -> None:
    html = load_html(args.html)
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    targets, _ = target_rows(html, state, all_untranslated=args.all_untranslated)
    if args.limit is not None:
        targets = targets[:args.limit]
    target_by_id = {row["id"]: row for row in targets}
    with args.translations.open(encoding="utf-8-sig", newline="") as stream:
        translated = {row["id"]: row.get("target_ko", "").strip()
                      for row in csv.DictReader(stream) if row.get("target_ko", "").strip()}
    missing = sorted(set(target_by_id) - set(translated))
    extra = sorted(set(translated) - set(target_by_id))
    if (missing and not args.allow_partial) or extra:
        raise ValueError(f"translation coverage mismatch: missing={len(missing)}, extra={len(extra)}")
    overrides = dict(state.get("translation_overrides", {}))
    overrides.update(translated)
    state["translation_overrides"] = overrides
    state["translation_application"] = {
        "format": "mgs3d-review-v10-translation-application-v1",
        "applied_rows": len(translated),
        "total_overrides": len(overrides),
        "remaining_target_rows": len(missing),
        "policy": "active matched empty rows only; existing Korean preserved",
    }
    args.output_json.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    fields = ["id", "container", "scene", "record", "entry", "offset",
              "relation_id", "relation_type", "duplicate_relations", "source_en",
              "ref_en", "ref_ko", "target_ko", "translation_source"]
    args.audit_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.audit_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in targets:
            if row["id"] not in translated:
                continue
            writer.writerow({**{key: row.get(key, "") for key in fields},
                             "target_ko": translated[row["id"]],
                             "translation_source": "ps2_reference" if row["ref_ko"] else "new"})
    print(f"applied and audited {len(translated)} translations")


def command_reuse(args: argparse.Namespace) -> None:
    html = load_html(args.html)
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    overrides = dict(state.get("translation_overrides", {}))
    known: dict[str, list[str]] = defaultdict(list)
    for row in html["ROWS"]:
        korean = str(overrides.get(row["id"]) or row.get("korean") or "").strip()
        english = str(row.get("english") or "").strip()
        if english and korean:
            known[english].append(korean)
    targets, _ = target_rows(html, state, all_untranslated=True)
    reused = {}
    for row in targets:
        choices = known.get(row["source_en"].strip(), [])
        if choices:
            reused[row["id"]] = Counter(choices).most_common(1)[0][0]
    overrides.update(reused)
    state["translation_overrides"] = overrides
    args.output_json.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    fields = ["id", "container", "scene", "record", "entry", "offset", "source_en",
              "target_ko", "translation_source"]
    by_id = {row["id"]: row for row in targets}
    with args.audit_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row_id, korean in reused.items():
            row = by_id[row_id]
            writer.writerow({**{key: row.get(key, "") for key in fields},
                             "target_ko": korean, "translation_source": "exact_english_reuse"})
    print(f"reused {len(reused)} exact-English translations")


def command_raw_audit(args: argparse.Namespace) -> None:
    html = load_html(args.html)
    state = json.loads(args.state.read_text(encoding="utf-8-sig"))
    overrides = state.get("translation_overrides", {})
    normalize = lambda value: re.sub(
        r"[^a-z0-9]+", "", re.sub(r"<[^>]*>", "", value).replace("|", " ").lower())
    translated_by_text = {}
    translated_by_entry = {}
    for row in html["ROWS"]:
        korean = str(overrides.get(row["id"]) or row.get("korean") or "").strip()
        if korean and normalize(str(row.get("english") or "")):
            translated_by_text[normalize(row["english"])] = korean
            translated_by_entry[(str(row["type"]), str(row.get("record", "")),
                                 str(row.get("entry", "")))] = korean
    translated_by_id = {}
    for path in args.matches:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("korean", "").strip():
                    translated_by_id[(row["container"], row["offset"])] = row["korean"].strip()
    for path in args.manual:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                translated_by_id[(row["media"], row["offset"])] = row["korean"].strip()
    output = []
    with args.raw.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if args.media and row["media"] != args.media:
                continue
            if row["entry_type"] != "1" or not normalize(row["preview"]):
                continue
            korean = translated_by_entry.get((row["media"], row["record"], row["entry"]), "")
            source = "review_record_entry"
            if not korean:
                korean = translated_by_id.get((row["media"], row["offset"]), "")
                source = "offset"
            if not korean:
                korean = translated_by_text.get(normalize(row["preview"]), "")
                source = "normalized_english"
            korean = korean.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
            output.append({**row, "accept": "yes" if korean else "", "korean": korean,
                           "translation_source": source if korean else "missing"})
    fields = list(output[0])
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    missing = sum(not row["korean"] for row in output)
    print(f"audited {len(output)} raw dialogue rows; missing={missing}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("html", type=Path)
    prepare.add_argument("state", type=Path)
    prepare.add_argument("output", type=Path)
    prepare.add_argument("--all-untranslated", action="store_true")
    prepare.add_argument("--limit", type=int)
    prepare.set_defaults(function=command_prepare)
    apply = commands.add_parser("apply")
    apply.add_argument("html", type=Path)
    apply.add_argument("state", type=Path)
    apply.add_argument("translations", type=Path)
    apply.add_argument("output_json", type=Path)
    apply.add_argument("audit_csv", type=Path)
    apply.add_argument("--all-untranslated", action="store_true")
    apply.add_argument("--limit", type=int)
    apply.add_argument(
        "--allow-partial", action="store_true",
        help="apply a reviewed tranche without requiring every current target row",
    )
    apply.set_defaults(function=command_apply)
    reuse = commands.add_parser("reuse")
    reuse.add_argument("html", type=Path)
    reuse.add_argument("state", type=Path)
    reuse.add_argument("output_json", type=Path)
    reuse.add_argument("audit_csv", type=Path)
    reuse.set_defaults(function=command_reuse)
    audit = commands.add_parser("raw-audit")
    audit.add_argument("html", type=Path)
    audit.add_argument("state", type=Path)
    audit.add_argument("raw", type=Path)
    audit.add_argument("output", type=Path)
    audit.add_argument("--matches", type=Path, action="append", default=[])
    audit.add_argument("--manual", type=Path, action="append", default=[])
    audit.add_argument("--media", choices=("movie", "demo"))
    audit.set_defaults(function=command_raw_audit)
    return result


def main() -> int:
    args = parser().parse_args()
    args.function(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
