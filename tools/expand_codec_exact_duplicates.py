#!/usr/bin/env python3
"""Expand approved codec translations to byte-identical game candidates."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re


CONTROL = re.compile(r"<[^>]+>")


def visible_key(preview: str) -> str:
    return re.sub(r"[\s#、。,.!?！？・'\"‘’“”]", "", CONTROL.sub("", preview))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    candidates = json.loads(args.candidates.read_text(encoding="utf-8-sig"))["candidates"]
    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    by_target = {(int(row["gcx"]), int(row["resource"])): row for row in candidates}
    translations_by_raw: dict[str, set[str]] = defaultdict(set)
    translations_by_visible: dict[str, set[str]] = defaultdict(set)
    template_by_raw: dict[str, dict[str, object]] = {}
    template_by_visible: dict[str, dict[str, object]] = {}
    for unit in document["units"]:
        candidate = by_target[(int(unit["gcx"]), int(unit["resource"]))]
        raw = str(candidate["raw_text"])
        translations_by_raw[raw].add(str(unit["text"]))
        template_by_raw[raw] = unit
        visible = visible_key(str(candidate["preview"]))
        if len(visible) >= 8:
            translations_by_visible[visible].add(str(unit["text"]))
            template_by_visible[visible] = unit

    safe = {raw: next(iter(texts)) for raw, texts in translations_by_raw.items() if len(texts) == 1}
    ambiguous = {raw for raw, texts in translations_by_raw.items() if len(texts) > 1}
    safe_visible = {
        key: next(iter(texts))
        for key, texts in translations_by_visible.items()
        if len(texts) == 1
    }
    units = []
    seen = set()
    for candidate in candidates:
        raw = str(candidate["raw_text"])
        visible = visible_key(str(candidate["preview"]))
        if raw in safe:
            translated = safe[raw]
            template = template_by_raw[raw]
        elif visible in safe_visible:
            translated = safe_visible[visible]
            template = template_by_visible[visible]
        else:
            continue
        key = (int(candidate["gcx"]), int(candidate["resource"]))
        if key in seen:
            continue
        seen.add(key)
        units.append({
            "gcx": key[0],
            "resource": key[1],
            "kind": template.get("kind", "string"),
            "source_page": template.get("source_page", 0),
            "speaker": template.get("speaker", ""),
            "text": translated,
        })

    output = dict(document)
    output["units"] = units
    output["exact_duplicate_expansion"] = {
        "source_units": len(document["units"]),
        "safe_unique_raw": len(safe),
        "ambiguous_raw_excluded": len(ambiguous),
        "safe_visible_keys": len(safe_visible),
        "expanded_units": len(units),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["exact_duplicate_expansion"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
