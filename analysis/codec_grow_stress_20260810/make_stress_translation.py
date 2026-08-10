#!/usr/bin/env python3
"""Create the reproducible, distributed codec grow stress selection."""

from __future__ import annotations

import json
from pathlib import Path


SOURCE = Path(
    "analysis/ps2_korean/full_build/rebuild_2026-08-08/"
    "translation_no243_443.json"
)
OUTPUT = Path("analysis/codec_grow_stress_20260810/stress_translation.json")
SELECTED_GCX = {13, 100, 500, 1000, 1501, 1990, 2200}


document = json.loads(SOURCE.read_text(encoding="utf-8"))
document["note"] = (
    "Distributed codec grow stress: small pre-GCX53 displacement plus six "
    "widely separated later growth sites."
)
document["units"] = [
    unit for unit in document["units"] if int(unit["gcx"]) in SELECTED_GCX
]
OUTPUT.write_text(
    json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"wrote {OUTPUT}: {len(document['units'])} units, GCX={sorted(SELECTED_GCX)}")
