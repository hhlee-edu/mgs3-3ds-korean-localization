#!/usr/bin/env python3
"""Derive a byte-capacity-safe codec translation from the accepted master.

`build-korean --preserve-record-layout` refuses to grow a GCX's fixed string
region, so any record whose accepted Korean is larger than the original English
must give some rows back. This is the step that produced
`translation/40_build_input/v0.69-safe/codec-safe.csv`; its generator was never
committed, so this reconstructs it.

Policy, per failing GCX only: drop accepted rows in descending
`encoded_korean_bytes - original_bytes` order until the record fits. Those rows
fall back to the original English on screen. Nothing outside a failing GCX is
touched, and the fit test is the shipped
`GcxRecord.replace_resources(preserve_layout=True)` rather than a re-model.

    python tools/mgs3d_codec_safe_select.py \
        --codec <clean codec.dat> \
        --translation <codec_natural_full_global_page.json> \
        --out-doc <safe translation json> \
        --out-excluded <excluded-rows.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import CodecError, parse_codec, parse_rendered  # noqa: E402

DEFAULT_CODEC = ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat"
DEFAULT_DOC = ROOT / "translation/40_build_input/global_page_v2/codec_natural_full_global_page.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--codec", type=Path, default=DEFAULT_CODEC)
    ap.add_argument("--translation", type=Path, default=DEFAULT_DOC)
    ap.add_argument("--out-doc", type=Path, required=True)
    ap.add_argument("--out-excluded", type=Path, required=True)
    args = ap.parse_args()

    doc = json.loads(args.translation.read_text(encoding="utf-8"))
    cmap = {c: bytes.fromhex(t) for c, t in doc["character_map"].items()}
    records = parse_codec(args.codec.read_bytes())

    by_gcx: dict[int, list[dict]] = {}
    for unit in doc["units"]:
        by_gcx.setdefault(int(unit["gcx"]), []).append(unit)

    dropped: list[dict] = []
    kept_units: list[dict] = []
    failing = fixed = 0

    for gcx, units in sorted(by_gcx.items()):
        record = records[gcx]
        originals = {i: len(r.data) for i, r in enumerate(record.resources())}

        def encode(subset):
            return {int(u["resource"]): parse_rendered(u["text"], cmap) for u in subset}

        def fits(subset) -> bool:
            try:
                record.replace_resources(encode(subset), preserve_layout=True)
                return True
            except CodecError:
                return False

        try:
            ok = fits(units)
        except CodecError as exc:            # an encode failure is not a capacity problem
            raise SystemExit(f"gcx {gcx}: {exc}")
        if ok:
            kept_units.extend(units)
            continue

        failing += 1
        remaining = list(units)
        removed: list[dict] = []
        while remaining and not fits(remaining):
            encoded = encode(remaining)
            # give back the row that overshoots its original slot the most
            worst = max(remaining, key=lambda u: len(encoded[int(u["resource"])])
                        - originals.get(int(u["resource"]), 0))
            remaining.remove(worst)
            removed.append(worst)
        if not remaining:
            # Legitimate: some records have zero slack in their string region,
            # so every accepted row has to fall back to English (gcx 44 is one:
            # its two Korean strings are 10 bytes over a region that is already
            # exactly full). replace_resources({}) returns the record untouched,
            # so this always converges.
            if not fits([]):
                raise SystemExit(f"gcx {gcx}: record does not fit even with no replacements")
        fixed += 1
        kept_units.extend(remaining)
        for u in removed:
            index = int(u["resource"])
            dropped.append({
                "gcx": gcx,
                "resource": index,
                "reason": "MUST_SHORTEN",
                "original_bytes": originals.get(index),
                "korean_bytes": len(parse_rendered(u["text"], cmap)),
            })

    out_doc = dict(doc)
    out_doc["units"] = kept_units
    out_doc["note"] = (doc.get("note", "") +
                       " | byte-capacity safe subset via mgs3d_codec_safe_select.py").strip(" |")
    args.out_doc.parent.mkdir(parents=True, exist_ok=True)
    args.out_doc.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    args.out_excluded.write_text(json.dumps({
        "format": "mgs3d-codec-safe-exclusions-v1",
        "source_translation": args.translation.relative_to(ROOT).as_posix(),
        "units_in": len(doc["units"]),
        "units_kept": len(kept_units),
        "units_dropped": len(dropped),
        "gcx_failing": failing,
        "gcx_resolved": fixed,
        "rows": dropped,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"units {len(doc['units'])} -> {len(kept_units)}  dropped {len(dropped)}")
    print(f"GCX failing {failing}, all resolved: {failing == fixed}")
    print(f"doc      -> {args.out_doc}")
    print(f"excluded -> {args.out_excluded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
