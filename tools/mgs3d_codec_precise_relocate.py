#!/usr/bin/env python3
"""Precise byte-level GCX relocation tool for root-causing the codec.dat
GCX-position-dependency crash. Unlike mgs3d_gcx_font_tool.py build-korean,
this never touches actual dialogue/glyph content — it only pads or trims a
GCX's string-region size by an EXACT byte count (replacing a resource with
itself, just changing string_region_size), giving byte-precise control over
how far a later GCX's start offset shifts. Read-only against the source;
writes only to the given output path.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec, GcxRecord, CodecError  # noqa: E402


def grow_gcx_padding(record: GcxRecord, delta: int) -> bytes:
    """Grow this GCX's string region by exactly `delta` bytes of trailing
    null padding. Content is 100% unchanged (always safe: padding only)."""
    resources = record.resources()
    old_string_size = record.font_data_offset - record.string_resources_offset
    new_size = old_string_size + delta
    replacements = {0: resources[0].data}  # content-neutral, just triggers the resize path
    return record.replace_resources(replacements, string_region_size=new_size)


def shrink_gcx_via_donor(record: GcxRecord, donor_resource: int, delta: int) -> bytes:
    """Shrink this GCX's string region by exactly `delta` bytes, freed by
    truncating `donor_resource` (assumed to be mostly/all null padding) down
    to a 1-byte placeholder, then padding back up to the exact target size."""
    resources = record.resources()
    old_string_size = record.font_data_offset - record.string_resources_offset
    replacements = {donor_resource: b"\x00"}
    natural = record.replace_resources(replacements)  # natural (shrunk) size, no target
    natural_record = GcxRecord(natural, record.source_offset)
    natural_plain = natural_record.font_data_offset - natural_record.string_resources_offset
    target = old_string_size - delta
    if target < natural_plain:
        raise CodecError(
            f"shrink_gcx_via_donor: need {delta} bytes but donor only frees "
            f"{old_string_size - natural_plain} bytes")
    return record.replace_resources(replacements, string_region_size=target)


def build(source: Path, grow_gcx: int, grow_delta: int,
         shrink_gcx: int, shrink_donor_resource: int, output: Path) -> dict:
    data = source.read_bytes()
    records = parse_codec(data)

    outputs = list(r.raw for r in records)
    outputs[grow_gcx] = grow_gcx_padding(records[grow_gcx], grow_delta)

    # recompute natural sizes so far to find the exact shrink needed
    natural_total = sum(len(r) for r in outputs)
    original_total = len(data)
    deficit = natural_total - original_total  # bytes we must remove somewhere at/after shrink_gcx

    outputs[shrink_gcx] = shrink_gcx_via_donor(records[shrink_gcx], shrink_donor_resource, deficit)

    output_bytes = b"".join(outputs)
    if len(output_bytes) != len(data):
        raise CodecError(f"total size mismatch: {len(output_bytes)} vs {len(data)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(output_bytes)

    new_records = parse_codec(output_bytes)
    if len(new_records) != len(records):
        raise CodecError("GCX count changed")

    shifted = [i for i, (o, n) in enumerate(zip(records, new_records))
              if o.source_offset != n.source_offset or len(o.raw) != len(n.raw)]

    return {
        "output": str(output),
        "sha256": hashlib.sha256(output_bytes).hexdigest(),
        "total_size": len(output_bytes),
        "grow_gcx": grow_gcx,
        "grow_delta": grow_delta,
        "shrink_gcx": shrink_gcx,
        "shrink_delta": -deficit,
        "gcx_with_offset_or_size_change": shifted,
    }


if __name__ == "__main__":
    raise SystemExit(0)
