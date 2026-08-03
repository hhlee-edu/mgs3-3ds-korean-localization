#!/usr/bin/env python3
"""Create a 3DS-order codec translation status catalog."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, render_bytes  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402


WORDS = re.compile(r"[a-z]+")
LANGUAGE_WORDS = {
    "en": {"a", "an", "and", "are", "aren", "but", "can", "did", "do", "does", "for", "good", "have", "he", "how", "i", "in", "is", "it", "know", "me", "my", "no", "not", "of", "on", "right", "she", "that", "the", "they", "this", "to", "was", "we", "what", "who", "why", "with", "you", "your"},
    "es": {"bueno", "buenos", "como", "con", "de", "del", "el", "en", "es", "hecho", "la", "las", "lo", "los", "me", "mi", "no", "para", "pero", "por", "que", "saber", "se", "son", "te", "tu", "una", "y"},
    "fr": {"au", "avec", "bien", "ce", "dans", "de", "des", "du", "elle", "elles", "en", "est", "il", "je", "la", "le", "les", "mais", "non", "nous", "ouais", "pas", "pour", "quoi", "sais", "sont", "sur", "tu", "un", "une", "vous"},
}


def load_units(path: Path) -> dict[tuple[int, int], dict]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        (int(unit["gcx"]), int(unit["resource"])): unit
        for unit in obj.get("units", [])
        if unit.get("kind") == "string"
    }


def load_review(path: Path) -> dict[tuple[int, int], dict[str, str]]:
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            result[(int(row["gcx"]), int(row["resource"]))] = row
    return result


def accepted(value: str) -> bool:
    return value.strip().casefold() in {"yes", "y", "1", "true", "on"}


def strict_western(raw: bytes) -> bool:
    """Reject Japanese/binary resources that decode_western only renders as gaps."""
    cursor = 0
    letters = 0
    while cursor < len(raw) and raw[cursor]:
        value = raw[cursor]
        if value == 0x0A or 0x20 <= value <= 0x7E:
            if 0x41 <= value <= 0x5A or 0x61 <= value <= 0x7A:
                letters += 1
            cursor += 1
        elif value == 0x80 and cursor + 1 < len(raw) and raw[cursor + 1] == 0x7C:
            cursor += 2
        elif value == 0x1F and cursor + 1 < len(raw):
            cursor += 2
        else:
            return False
    return letters >= 2


def direct_language(raw: bytes) -> str | None:
    words = WORDS.findall(decode_western(raw).casefold())
    if len(words) < 3:
        return None
    scores = {lang: sum(word in vocab for word in words) for lang, vocab in LANGUAGE_WORDS.items()}
    ordered = sorted(scores, key=lambda lang: (-scores[lang], lang))
    return ordered[0] if scores[ordered[0]] >= 2 and scores[ordered[0]] > scores[ordered[1]] else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("selected", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("remaining", type=Path)
    parser.add_argument("requested_result", type=Path)
    parser.add_argument("full_output", type=Path)
    parser.add_argument("action_output", type=Path)
    args = parser.parse_args()

    candidates = load_units(args.candidate)
    selected = load_units(args.selected)
    review = load_review(args.review)
    remaining = load_review(args.remaining)
    requested_result = load_review(args.requested_result)
    fields = [
        "accept", "priority", "status", "language", "is_donor", "text_kind", "blocker", "occurrences", "locations", "gcx", "resource",
        "english", "korean", "replacement", "missing_count",
        "missing_glyphs", "record_headroom", "raw_text", "note",
    ]
    rows = []
    counts: dict[str, int] = {}
    for gcx, record in enumerate(parse_codec(args.codec.read_bytes())):
        resources = record.resources()
        protected = {resource for (unit_gcx, resource) in candidates if unit_gcx == gcx}
        anchors: list[tuple[int, str]] = []
        for index, resource_item in enumerate(resources):
            if resource_item.is_script:
                continue
            language = "en" if index in protected else direct_language(resource_item.data)
            if language:
                anchors.append((index, language))
        for resource, item in enumerate(resources):
            if item.is_script:
                continue
            english = decode_western(item.data)
            if not english:
                continue
            key = (gcx, resource)
            language = "en" if key in candidates else direct_language(item.data)
            if language is None and anchors:
                previous = [anchor for anchor in anchors if anchor[0] < resource]
                following = [anchor for anchor in anchors if anchor[0] > resource]
                before = previous[-1] if previous else None
                after = following[0] if following else None
                # Western GCX branches are contiguous. When the surrounding
                # anchors differ, the first unanchored row after EN belongs to
                # the following ES/FR branch rather than to the nearest text.
                if before and after and before[1] != after[1]:
                    language = after[1]
                else:
                    language = min(anchors, key=lambda anchor: (abs(anchor[0] - resource), anchor[0]))[1]
            language = language or "unknown"
            is_donor = language in {"fr", "es"} and key not in candidates
            cand = candidates.get(key)
            sel = selected.get(key)
            rev = review.get(key, {})
            rem = remaining.get(key, {})
            request_outcome = requested_result.get(key, {})
            wanted = accepted(rev.get("accept", ""))
            blocker = rem.get("reason", "")
            if wanted and key not in selected and "문자열 공간 부족" in request_outcome.get("result", ""):
                blocker = "string_capacity"
            if sel:
                status = "적용완료"
            elif cand and wanted and blocker == "string_capacity":
                status = "문자열초과"
            elif cand and wanted and blocker == "static_glyph":
                status = "글리프부족"
            elif cand:
                status = "미선택"
            else:
                if not strict_western(item.data):
                    continue
                if is_donor:
                    status = "외국어분기"
                    blocker = "영어런타임검토제외"
                else:
                    status = "PS2대응없음"
                    blocker = "직접번역필요"
            counts[status] = counts.get(status, 0) + 1
            korean = (sel or cand or {}).get("text", "")
            if rev.get("korean", "").strip():
                korean = rev["korean"]
            rows.append({
                "accept": rev.get("accept", ""),
                "priority": rev.get("priority", ""),
                "status": status,
                "language": language,
                "is_donor": "yes" if is_donor else "no",
                "text_kind": "identifier" if re.fullmatch(r"[A-Za-z0-9_./:-]+", english) else "display_text",
                "blocker": blocker,
                "occurrences": 1,
                "locations": f"{gcx}:{resource}",
                "gcx": gcx,
                "resource": resource,
                "english": english,
                "korean": korean,
                "replacement": rev.get("replacement", ""),
                "missing_count": rem.get("missing_count", ""),
                "missing_glyphs": rem.get("missing_glyphs", ""),
                "record_headroom": rem.get("record_headroom", ""),
                "raw_text": render_bytes(item.data),
                "note": rev.get("note", ""),
            })

    grouped: dict[tuple, dict] = {}
    for row in rows:
        if row["status"] in {"적용완료", "외국어분기"}:
            continue
        key = (row["status"], row["language"], row["is_donor"], row["blocker"], row["english"], row["korean"], row["replacement"], row["missing_glyphs"])
        if key not in grouped:
            grouped[key] = dict(row)
        else:
            grouped[key]["occurrences"] += 1
            if grouped[key]["locations"].count(";") < 19:
                grouped[key]["locations"] += ";" + row["locations"]
    action_rows = sorted(grouped.values(), key=lambda row: (row["status"], int(row["priority"] or 999999), row["english"]))
    for path, chosen in ((args.full_output, rows), (args.action_output, action_rows)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(chosen)
    print(json.dumps({"rows": len(rows), "actionable_positions": sum(r["status"] not in {"적용완료", "외국어분기"} for r in rows), "actionable_unique": len(action_rows), "status": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
