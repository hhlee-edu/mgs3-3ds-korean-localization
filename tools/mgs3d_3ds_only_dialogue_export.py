#!/usr/bin/env python3
"""Export the manually translated 3DS-only movie/demo dialogue as one JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "experiments/translation_checkpoints/01_mgs3d_original_3ds_english_full_korean_audit.csv"
PARTS = [
    ROOT / "experiments/story_media_order/mgs3d_raw_unmatched_manual_part1.csv",
    ROOT / "experiments/story_media_order/mgs3d_raw_unmatched_manual_part2.csv",
]
OUTPUT = ROOT / "translation/10_master/3ds_only/3ds_only_movie_demo_english_korean.json"
CODEC_OFFICIAL = ROOT / "experiments/translation_checkpoints/04_selected_translation.json"
CODEC_3DS_TRANSLATION = ROOT / "experiments/translation_checkpoints/05_translation.json"
CODEC_ORIGINAL = ROOT / "translation/00_source/codec_3ds_english/codec_3ds_english_original_resources.json"
CODEC_OUTPUT = ROOT / "translation/10_master/3ds_only/3ds_only_codec_english_korean.json"
ALL_OUTPUT = ROOT / "translation/10_master/3ds_only/3ds_only_all_english_korean.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    audit = read_csv(AUDIT)
    by_key: dict[tuple[str, int], dict[str, str]] = {}
    for row in audit:
        try:
            key = (row["media"].strip(), int(row["offset"]))
        except (KeyError, ValueError):
            continue
        if key in by_key:
            raise ValueError(f"duplicate audit key: {key}")
        by_key[key] = row

    output_rows = []
    seen: set[tuple[str, int]] = set()
    missing = []
    for part_number, path in enumerate(PARTS, 1):
        for source_row in read_csv(path):
            key = (source_row["media"].strip(), int(source_row["offset"]))
            if key in seen:
                raise ValueError(f"duplicate 3DS-only row: {key}")
            seen.add(key)
            matched = by_key.get(key)
            if not matched:
                missing.append(key)
                continue
            english = (matched.get("preview") or matched.get("raw_text") or "").replace("<END>", "").strip()
            output_rows.append({
                "id": f"{key[0]}:{key[1]}",
                "media": key[0],
                "offset": key[1],
                "record": int(matched["record"]) if matched.get("record", "").isdigit() else None,
                "entry": int(matched["entry"]) if matched.get("entry", "").isdigit() else None,
                "english_3ds": english,
                "korean_natural": source_row["korean"].strip(),
                "ps2_shinsnote_match": None,
                "classification": "3ds_only_unmatched",
                "translation_status": "translated_manual",
                "source_part": part_number,
            })
    if missing:
        raise ValueError(f"3DS-only offsets missing from authority audit: {missing[:10]} ({len(missing)} total)")

    output_rows.sort(key=lambda row: (row["media"], row["offset"]))
    counts = {media: sum(row["media"] == media for row in output_rows) for media in ("movie", "demo")}
    document = {
        "format": "mgs3d-3ds-only-dialogue-translation-v1",
        "scope": "Movie/Demo rows left unmatched by the PS2/Shinsnote alignment and manually translated from the original 3DS English",
        "authority": {
            "english": str(AUDIT.relative_to(ROOT)),
            "translations": [str(path.relative_to(ROOT)) for path in PARTS],
        },
        "summary": {
            "total": len(output_rows),
            "movie": counts["movie"],
            "demo": counts["demo"],
            "all_have_english": all(bool(row["english_3ds"]) for row in output_rows),
            "all_have_korean": all(bool(row["korean_natural"]) for row in output_rows),
        },
        "rows": output_rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(output_rows)} rows (movie={counts['movie']}, demo={counts['demo']}): {OUTPUT}")

    official = json.loads(CODEC_OFFICIAL.read_text(encoding="utf-8-sig"))
    translated = json.loads(CODEC_3DS_TRANSLATION.read_text(encoding="utf-8-sig"))
    original = json.loads(CODEC_ORIGINAL.read_text(encoding="utf-8-sig"))
    official_keys = {(int(row["gcx"]), int(row["resource"])) for row in official["units"]}
    original_by_key = {(int(row["gcx"]), int(row["resource"])): row for row in original["units"]}
    codec_rows = []
    for row in translated["units"]:
        key = (int(row["gcx"]), int(row["resource"]))
        if key in official_keys:
            continue
        source = original_by_key.get(key)
        if source is None:
            raise ValueError(f"3DS Codec resource missing from original dump: {key}")
        codec_rows.append({
            "id": f"codec:{key[0]}:{key[1]}",
            "media": "codec",
            "gcx": key[0],
            "resource": key[1],
            "kind": row.get("kind", source.get("kind", "string")),
            "original_size": int(source["original_size"]),
            "english_3ds": source["text"],
            "korean_natural": row["text"],
            "ps2_official_translation": None,
            "classification": "3ds_only_not_in_ps2_official_codec_set",
            "translation_status": "translated_3ds",
        })
    codec_rows.sort(key=lambda row: (row["gcx"], row["resource"]))
    codec_document = {
        "format": "mgs3d-3ds-only-codec-translation-v1",
        "scope": "Codec resources translated from the original 3DS English and absent from the PS2 official Korean unit set",
        "authority": {
            "ps2_official_keys": str(CODEC_OFFICIAL.relative_to(ROOT)),
            "3ds_translation": str(CODEC_3DS_TRANSLATION.relative_to(ROOT)),
            "3ds_english": str(CODEC_ORIGINAL.relative_to(ROOT)),
        },
        "summary": {
            "total": len(codec_rows),
            "expected_merge_added": 5304,
            "count_matches_merge_summary": len(codec_rows) == 5304,
            "all_have_english": all(bool(row["english_3ds"]) for row in codec_rows),
            "all_have_korean": all(bool(row["korean_natural"]) for row in codec_rows),
        },
        "rows": codec_rows,
    }
    CODEC_OUTPUT.write_text(json.dumps(codec_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(codec_rows)} Codec 3DS-only resources: {CODEC_OUTPUT}")
    combined = {
        "format": "mgs3d-3ds-only-all-translation-v1",
        "scope_note": "Movie/Demo are alignment-unmatched dialogue. Codec rows are resources absent from the PS2 official unit set and may include UI/metadata strings; use kind/text when reviewing.",
        "summary": {
            "total": len(output_rows) + len(codec_rows),
            "movie": counts["movie"], "demo": counts["demo"], "codec": len(codec_rows),
        },
        "rows": output_rows + codec_rows,
    }
    ALL_OUTPUT.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote combined {combined['summary']['total']} rows: {ALL_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
