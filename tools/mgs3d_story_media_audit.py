#!/usr/bin/env python3
"""Audit stage scenario assets before extracting movie/demo playback order.

This deliberately distinguishes structured hits from raw byte coincidences.
The legacy tools-mgs hash 0xA242 (demo) is accepted only inside a decrypted
GCX script resource; native procedure regions are counted separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, GcxRecord  # noqa: E402


LEGACY_DEMO_HASH = bytes.fromhex("a242")
MEDIA_STRINGS = (
    b"ANewMpegPssMovieStrProg",
    b"CODEC_REQ_MOVIE_START",
    b"NewRadioMovie",
    b"NewStreamIpuDriver",
    b"NewDemoCamera",
)


def audit_scenarios(root: Path) -> dict:
    files = sorted(root.glob("*/scenerio.gcx")) + sorted(root.glob("*/*.02"))
    parsed = 0
    resources = 0
    script_resources = 0
    structured_demo_hits: list[dict] = []
    native_demo_hits: list[dict] = []
    failures: list[dict] = []
    for path in files:
        try:
            record = GcxRecord(path.read_bytes())
            parsed += 1
        except (CodecError, OSError) as exc:
            failures.append({"file": str(path), "error": str(exc)})
            continue
        items = record.resources()
        resources += len(items)
        for index, resource in enumerate(items):
            if not resource.is_script:
                continue
            script_resources += 1
            cursor = 0
            while (offset := resource.data.find(LEGACY_DEMO_HASH, cursor)) >= 0:
                structured_demo_hits.append({
                    "stage": path.parent.name,
                    "script_file": str(path),
                    "resource_index": index,
                    "resource_offset": offset,
                })
                cursor = offset + 1
        proc_start = record.block_start + record.proc_offset
        blob = record.raw[proc_start:]
        cursor = 0
        while (offset := blob.find(LEGACY_DEMO_HASH, cursor)) >= 0:
            native_demo_hits.append({
                "stage": path.parent.name,
                "script_file": str(path),
                "file_offset": proc_start + offset,
            })
            cursor = offset + 1
    return {
        "scenario_files": len(files),
        "parsed": parsed,
        "resources": resources,
        "script_resources": script_resources,
        "structured_legacy_demo_hash_hits": structured_demo_hits,
        "native_region_raw_hash_hits": native_demo_hits,
        "parse_failures": failures,
    }


def audit_overlays(root: Path) -> dict:
    counts: Counter[str] = Counter()
    stages: dict[str, list[str]] = {}
    files = sorted(root.glob("*/*.01"))
    for path in files:
        data = path.read_bytes()
        found = []
        for token in MEDIA_STRINGS:
            if token in data:
                name = token.decode("ascii")
                counts[name] += 1
                found.append(name)
        if found:
            stages[path.parent.name] = found
    return {"overlay_files": len(files), "string_counts": counts, "stages": stages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--overlay-root", type=Path)
    args = parser.parse_args()
    report = {"scenarios": audit_scenarios(args.scenario_root)}
    if args.overlay_root:
        report["overlays"] = audit_overlays(args.overlay_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    scenarios = report["scenarios"]
    print(f"wrote {args.output}: parsed={scenarios['parsed']}/{scenarios['scenario_files']} "
          f"structured_demo_hits={len(scenarios['structured_legacy_demo_hash_hits'])} "
          f"native_raw_hits={len(scenarios['native_region_raw_hash_hits'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
