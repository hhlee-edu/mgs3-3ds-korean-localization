#!/usr/bin/env python3
"""Prepare and validate the 191-static + 928-global Korean character map.

This is deliberately non-destructive: it reads MASTER material and writes only
versioned metadata under translation/40_build_input. It does not rebuild DAT,
HPK, GCX, or CCI files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import parse_rendered  # noqa: E402
from mgs3d_movie_tool import encode_translation  # noqa: E402
FIXED = ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/sna01-allocation-report.json"
FIXED_HPKS = [
    ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/stage/r_sna01/resident.hpk",
    ROOT / "experiments/shared_glyph_optimized_build_2026-08-12/stage/r_sna02/resident.hpk",
]
GLOBAL = ROOT / "glyph/pages/global_korean_page_v2/korean_token_map_full.csv"
PAGE = ROOT / "glyph/pages/global_korean_page_v2/korean_page_full.bin"
MASTER = ROOT / "translation/10_master/bundle_natural_full"
SOURCES = [
    MASTER / "movie_natural_full.csv",
    MASTER / "demo_natural_full.csv",
    MASTER / "codec_natural_full.json",
    MASTER / "mgs3d_review_v10_natural_full.json",
]
OUT = ROOT / "translation/40_build_input/global_page_v2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hangul_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from hangul_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from hangul_strings(value)


def source_characters(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                # Korean is the build-authoring field. Scanning only this field
                # avoids treating notes and source-path metadata as game text.
                text = row.get("korean", "")
                counts.update(ch for ch in text if "가" <= ch <= "힣")
    else:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        for text in hangul_strings(document):
            counts.update(ch for ch in text if "가" <= ch <= "힣")
    return counts


def main() -> int:
    fixed_doc = json.loads(FIXED.read_text(encoding="utf-8-sig"))
    fixed = {character: bytes.fromhex(token) for character, token in fixed_doc["characters"].items()}
    with GLOBAL.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    global_map = {row["character"]: bytes.fromhex(row["bytes"]) for row in rows}
    combined = {**fixed, **global_map}

    fixed_tokens = set(fixed.values())
    global_tokens = set(global_map.values())
    source_reports = []
    corpus: Counter[str] = Counter()
    for source in SOURCES:
        counts = source_characters(source)
        corpus.update(counts)
        missing = sorted(set(counts) - set(combined))
        source_reports.append({
            "path": source.relative_to(ROOT).as_posix(),
            "sha256": sha(source),
            "unique_hangul": len(counts),
            "hangul_occurrences": sum(counts.values()),
            "missing_count": len(missing),
            "missing_characters": "".join(missing),
        })

    # Prove that the actual authoring fields can be consumed by the existing
    # encoders. Size overflow is reported separately: the global page removes
    # glyph cost, not each container's string-region boundary.
    encoding_reports = []
    for media in ("movie", "demo"):
        source = MASTER / f"{media}_natural_full.csv"
        accepted = encoded = over_original_size = 0
        failures = []
        with source.open(encoding="utf-8-sig", newline="") as stream:
            for line, row in enumerate(csv.DictReader(stream), 2):
                if row.get("accept", "").lower() not in ("yes", "y", "1", "true"):
                    continue
                accepted += 1
                try:
                    payload = encode_translation(row.get("korean", ""), combined)
                    encoded += 1
                    over_original_size += len(payload) > int(row["size"])
                except Exception as exc:  # report source row without mutating it
                    failures.append({"line": line, "error": str(exc)})
        encoding_reports.append({
            "media": media,
            "accepted_rows": accepted,
            "encoded_rows": encoded,
            "encoding_failures": failures,
            "rows_larger_than_original_slot": over_original_size,
        })

    codec_source = MASTER / "codec_natural_full.json"
    codec_document = json.loads(codec_source.read_text(encoding="utf-8-sig"))
    codec_failures = []
    for index, unit in enumerate(codec_document["units"]):
        try:
            parse_rendered(unit["text"], combined)
        except Exception as exc:
            codec_failures.append({"unit": index, "gcx": unit.get("gcx"),
                                   "resource": unit.get("resource"), "error": str(exc)})
    encoding_reports.append({
        "media": "codec",
        "units": len(codec_document["units"]),
        "encoded_units": len(codec_document["units"]) - len(codec_failures),
        "encoding_failures": codec_failures,
        "note": "GCX layout/capacity is a separate build gate.",
    })

    encoded_to_character = {token.hex().upper(): character for character, token in combined.items()}
    round_trip_ok = all(encoded_to_character[token.hex().upper()] == character
                        for character, token in combined.items())
    checks = {
        "fixed_characters_191": len(fixed) == 191,
        "global_characters_929": len(global_map) == 929,
        "combined_characters_1120": len(combined) == 1120,
        "character_sets_disjoint": not (set(fixed) & set(global_map)),
        "fixed_tokens_unique": len(fixed_tokens) == len(fixed),
        "global_tokens_unique": len(global_tokens) == len(global_map),
        "token_sets_disjoint": not (fixed_tokens & global_tokens),
        "global_tokens_valid": all(0x8401 <= int.from_bytes(token, "big") <= 0x87FF
                                   and token[1] != 0 for token in global_tokens),
        "corpus_covered": all(not report["missing_count"] for report in source_reports),
        "round_trip": round_trip_ok,
        "page_size_0xff00": PAGE.stat().st_size == 0xFF00,
        "fixed_hpks_present": all(path.is_file() for path in FIXED_HPKS),
        "all_authoring_text_encodes": all(not item["encoding_failures"]
                                           for item in encoding_reports),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    OUT.mkdir(parents=True, exist_ok=True)

    character_map = {
        "format": "mgs3d-global-korean-character-map-v1",
        "status": status,
        "characters": {character: token.hex().upper()
                       for character, token in sorted(combined.items(), key=lambda item: item[1])},
        "fixed_character_count": len(fixed),
        "global_character_count": len(global_map),
        "source_fixed_allocation": FIXED.relative_to(ROOT).as_posix(),
        "source_global_token_map": GLOBAL.relative_to(ROOT).as_posix(),
    }
    (OUT / "character-map.json").write_text(
        json.dumps(character_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dependencies = {
        "format": "mgs3d-global-page-build-dependencies-v1",
        "status": status,
        "korean_page": {"path": PAGE.relative_to(ROOT).as_posix(), "sha256": sha(PAGE)},
        "global_token_map": {"path": GLOBAL.relative_to(ROOT).as_posix(), "sha256": sha(GLOBAL)},
        "fixed_allocation": {"path": FIXED.relative_to(ROOT).as_posix(), "sha256": sha(FIXED)},
        "fixed_hpk": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
                      for path in FIXED_HPKS],
        "required_code_patch": "experiments/2026-08-13-clean-glyph-baseline/V2-build-manifest.json",
        "warning": "The 928-glyph page is not standalone; both 191-glyph HPKs and this exact combined map are required.",
    }
    (OUT / "dependencies.json").write_text(
        json.dumps(dependencies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "format": "mgs3d-global-page-coverage-v1",
        "status": status,
        "checks": checks,
        "corpus_unique_hangul": len(corpus),
        "corpus_hangul_occurrences": sum(corpus.values()),
        "sources": source_reports,
        "encoding_preflight": encoding_reports,
    }
    (OUT / "coverage-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Versioned build inputs. MASTER remains untouched. Movie/demo CSV content
    # is copied byte-for-byte; codec differs only in character_map plus a
    # provenance note, leaving every authored unit unchanged.
    derived = []
    for media in ("movie", "demo"):
        source = MASTER / f"{media}_natural_full.csv"
        target = OUT / f"{media}_natural_full_global_page.csv"
        shutil.copy2(source, target)
        derived.append({"path": target.relative_to(ROOT).as_posix(), "sha256": sha(target),
                        "source_sha256": sha(source), "transformation": "byte-identical copy"})
    codec_target = OUT / "codec_natural_full_global_page.json"
    codec_document["character_map"] = character_map["characters"]
    codec_document["global_page_build_input"] = {
        "version": "v2", "fixed_characters": len(fixed), "global_characters": len(global_map),
        "coverage_report": "coverage-report.json"
    }
    codec_target.write_text(json.dumps(codec_document, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    derived.append({"path": codec_target.relative_to(ROOT).as_posix(), "sha256": sha(codec_target),
                    "source_sha256": sha(codec_source),
                    "transformation": "character_map replaced; units unchanged"})
    (OUT / "build-input-manifest.json").write_text(json.dumps({
        "format": "mgs3d-global-page-derived-build-input-v1", "status": status,
        "outputs": derived,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
