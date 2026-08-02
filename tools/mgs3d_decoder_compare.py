#!/usr/bin/env python3
"""Build a fixed, provenance-rich comparison corpus for MGS3D decoders."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import decode_mgs_preview, render_bytes  # noqa: E402
from mgs3d_text_reassembler import (  # noqa: E402
    TOOL_VERSION, classify, static_character, tokenize,
)


CONTROL_CODE_RE = re.compile(r"<[^>]*>")


def matcher_clean(preview: str) -> str:
    """Mirror mgs3_matcher.py's game-preview cleanup operation."""
    return CONTROL_CODE_RE.sub("", preview).strip()


def conservative_render(data: bytes) -> str:
    pieces: list[str] = []
    for token in tokenize(data):
        raw_hex = token.raw.hex().upper()
        if token.token_class == "ascii":
            pieces.append(chr(token.value))
        elif static_character(token.raw) is not None:
            pieces.append(static_character(token.raw) or "")
        elif token.token_class == "terminator":
            pieces.append("<END>")
        elif token.token_class == "line-feed":
            pieces.append("<LF>")
        else:
            pieces.append(f"<{token.token_class}:{raw_hex}>")
    return "".join(pieces)


def compare_bytes(data: bytes) -> dict[str, object]:
    legacy = decode_mgs_preview(data)
    shared = {
        "codec": legacy,
        "movie": legacy,
        "demo": legacy,
        "script_compare": legacy,
    }
    clean = matcher_clean(legacy)
    outputs = {**shared, "matcher_clean": clean,
               "lossless": render_bytes(data), "conservative": conservative_render(data)}
    disagreements = []
    if len(set(shared.values())) == 1:
        shared_disposition = "confirmed-same-function"
    else:  # Kept as an audit assertion if adapters diverge later.
        shared_disposition = "unresolved"
        disagreements.append("legacy decoder adapters disagree")
    if clean != legacy:
        disagreements.append("matcher removes angle-bracket token output")
        matcher_disposition = "unsupported-as-decoder"
    else:
        matcher_disposition = "confirmed-no-cleaning-change"
    mapped = static_character(data)
    if mapped is not None and legacy != mapped:
        disagreements.append("legacy preview differs from confirmed static-page mapping")
        legacy_semantic_disposition = "corrected"
    elif mapped is not None:
        legacy_semantic_disposition = "confirmed"
    else:
        legacy_semantic_disposition = "unsupported-or-unresolved"
    return {
        "outputs": outputs,
        "shared_decoder_disposition": shared_disposition,
        "matcher_disposition": matcher_disposition,
        "legacy_semantic_disposition": legacy_semantic_disposition,
        "disagreements": disagreements,
    }


def load_inventory(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format") != TOOL_VERSION or not isinstance(document.get("tokens"), list):
        raise ValueError(f"not a {TOOL_VERSION} inventory: {path}")
    return document


def build_corpus(paths: list[Path]) -> dict[str, object]:
    inventories = [(path, load_inventory(path)) for path in paths]
    values: dict[str, dict[str, object]] = {}
    for path, document in inventories:
        container = str(document["container"])
        for item in document["tokens"]:
            raw_hex = str(item["raw_hex"])
            row = values.setdefault(raw_hex, {
                "raw_hex": raw_hex, "width": int(item["width"]),
                "class": item["class"], "status": item["status"],
                "counts": {}, "examples": [],
            })
            row["counts"][container] = int(item["count"])
            for example in item.get("examples", []):
                row["examples"].append({"container": container, **example})
    rows = []
    disposition_counts: dict[str, int] = {}
    semantic_disposition_counts: dict[str, int] = {}
    for raw_hex in sorted(values, key=lambda value: int(value, 16)):
        row = values[raw_hex]
        comparison = compare_bytes(bytes.fromhex(raw_hex))
        row.update(comparison)
        disposition = str(comparison["shared_decoder_disposition"])
        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        semantic = str(comparison["legacy_semantic_disposition"])
        semantic_disposition_counts[semantic] = semantic_disposition_counts.get(semantic, 0) + 1
        rows.append(row)
    sources = [{"inventory": str(path), "container": doc["container"],
                "source": doc["source"], "source_sha256": doc["source_sha256"]}
               for path, doc in inventories]
    fingerprint_input = json.dumps(sources, sort_keys=True).encode("utf-8")
    return {
        "format": "mgs3d-decoder-comparison-v1",
        "reassembly_format": TOOL_VERSION,
        "sources": sources,
        "corpus_fingerprint": hashlib.sha256(fingerprint_input).hexdigest(),
        "decoder_provenance": {
            "codec": "tools/mgs3d_codec_tool.py:decode_mgs_preview",
            "movie": "imports codec decode_mgs_preview",
            "demo": "movie parser imports codec decode_mgs_preview",
            "script_compare": "imports codec decode_mgs_preview",
            "matcher_clean": "mgs3-dialogue-tool/mgs3_matcher.py:CONTROL_CODE_RE.sub",
            "conservative": "tools/mgs3d_decoder_compare.py:conservative_render",
        },
        "token_value_count": len(rows),
        "disposition_counts": disposition_counts,
        "legacy_semantic_disposition_counts": semantic_disposition_counts,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("inventories", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        document = build_corpus(args.inventories)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"comparison corpus: {document['token_value_count']} token values")
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
