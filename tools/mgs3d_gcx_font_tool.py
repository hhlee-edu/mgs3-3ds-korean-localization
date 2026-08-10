#!/usr/bin/env python3
"""Extract and replace the 16x16, 2-bpp custom glyphs embedded in GCX files."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import (  # noqa: E402
    CodecError,
    GcxRecord,
    align,
    decode_mgs_preview,
    parse_codec,
    parse_rendered,
    relocate_gcx53_inner_offsets,
    render_bytes,
    sha256,
)
from mgs3d_translation import validate_codec_translation  # noqa: E402


GLYPH_SIZE = 64
WIDTH = HEIGHT = 16
LEVELS = (0, 85, 170, 255)


def morton(x: int, y: int) -> int:
    result = 0
    for bit in range(3):
        result |= ((x >> bit) & 1) << (bit * 2)
        result |= ((y >> bit) & 1) << (bit * 2 + 1)
    return result


def pixel_index(x: int, y: int, layout: str) -> int:
    if layout == "linear":
        return y * WIDTH + x
    tile = (y // 8) * 2 + x // 8
    return tile * 64 + morton(x & 7, y & 7)


def decode_glyph(data: bytes, layout: str) -> Image.Image:
    if len(data) != GLYPH_SIZE:
        raise CodecError(f"glyph must be {GLYPH_SIZE} bytes")
    image = Image.new("L", (WIDTH, HEIGHT))
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            index = pixel_index(x, y, layout)
            shift = 6 - (index & 3) * 2
            pixels[x, y] = LEVELS[(data[index >> 2] >> shift) & 3]
    return image


def encode_glyph(image: Image.Image, layout: str) -> bytes:
    image = image.convert("L")
    if image.size != (WIDTH, HEIGHT):
        raise CodecError(f"replacement image must be {WIDTH}x{HEIGHT} pixels")
    output = bytearray(GLYPH_SIZE)
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            index = pixel_index(x, y, layout)
            value = min(3, (pixels[x, y] + 42) // 85)
            output[index >> 2] |= value << (6 - (index & 3) * 2)
    return bytes(output)


def custom_token(index: int) -> bytes:
    """Encode the renderer's page-2 glyph index, skipping each xx00 token."""
    if not 0 <= index < 1020:
        raise CodecError(f"custom glyph index exceeds page capacity: {index}")
    token = 0x8C01 + index + index // 255
    return token.to_bytes(2, "big")


def render_character(character: str, font: ImageFont.FreeTypeFont) -> bytes:
    image = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    box = draw.textbbox((0, 0), character, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    x = (WIDTH - width) // 2 - box[0]
    y = (HEIGHT - height) // 2 - box[1]
    draw.text((x, y), character, fill=255, font=font)
    return encode_glyph(image, "linear")


def append_font(record: GcxRecord, glyphs: bytes) -> bytes:
    if not glyphs:
        return record.raw
    if len(glyphs) % GLYPH_SIZE:
        raise CodecError("appended font data is not glyph-aligned")
    font_start = record.block_start + record.font_data_offset
    proc_start = record.block_start + record.proc_offset
    _, old_count = font_region(record)
    output = bytearray(record.raw)
    if old_count:
        old_payload = old_count * GLYPH_SIZE
        struct.pack_into("<I", output, font_start, old_payload + len(glyphs))
        output[proc_start:proc_start] = glyphs
        delta = len(glyphs)
    else:
        # Empty records still reserve the four-byte font-size word; its value
        # is ignored until glyph data exists.
        struct.pack_into("<I", output, font_start, len(glyphs))
        output[proc_start:proc_start] = glyphs
        delta = len(glyphs)
    struct.pack_into("<I", output, record.block_start, record.proc_offset + delta)
    updated = GcxRecord(bytes(output), record.source_offset)
    del output[updated.logical_size():]
    output.extend(b"\0" * (align(len(output)) - len(output)))
    return bytes(output)


def overwrite_font(record: GcxRecord, glyphs: bytes) -> bytes:
    """Diagnostic mode: replace existing slots without growing the GCX."""
    if len(glyphs) % GLYPH_SIZE:
        raise CodecError("replacement font data is not glyph-aligned")
    start, count = font_region(record)
    needed = len(glyphs) // GLYPH_SIZE
    if needed > count:
        raise CodecError(
            f"diagnostic font replacement needs {needed} slots but record has {count}"
        )
    output = bytearray(record.raw)
    output[start : start + len(glyphs)] = glyphs
    return bytes(output)


def overwrite_font_slots(record: GcxRecord, slots: list[int], glyphs: bytes) -> bytes:
    """Replace selected existing glyph slots without changing record layout."""
    if len(glyphs) != len(slots) * GLYPH_SIZE:
        raise CodecError("slot list and replacement glyph count do not match")
    start, count = font_region(record)
    output = bytearray(record.raw)
    for offset, slot in enumerate(slots):
        if not 0 <= slot < count:
            raise CodecError(f"font slot out of range: {slot} (count {count})")
        glyph = glyphs[offset * GLYPH_SIZE : (offset + 1) * GLYPH_SIZE]
        target = start + slot * GLYPH_SIZE
        output[target : target + GLYPH_SIZE] = glyph
    return bytes(output)


def freed_font_slots(record: GcxRecord, replaced_resources: set[int]) -> list[int]:
    """Slots no longer referenced after all selected resources are replaced."""
    _, count = font_region(record)
    remaining = b"".join(
        resource.data
        for index, resource in enumerate(record.resources())
        if index not in replaced_resources
    )
    return [index for index in range(count) if custom_token(index) not in remaining]


def glyph_slot_owners(resources: list, count: int) -> list[set[int]]:
    """Per-resource, boundary-respecting scan of which resources reference
    which of this record's own custom-glyph slots (this GCX's own 0x8C-page
    tokens only -- structurally cannot match another GCX's tokens, the HPK
    static-font pages, or movie/demo's page-3 tokens, since those numeric
    ranges are never produced by this record's own custom_token()).

    More precise than freed_font_slots(): stops at each resource's null
    terminator and treats 0x1F as its own two-byte accent-escape (matching
    decode_mgs_preview's `0x1F <suffix>` handling in mgs3d_codec_tool.py)
    instead of a token lead byte, so an accent escape whose argument byte is
    >= 0x80 can no longer misalign the scan and hide a real reference.
    """
    token_slots = {custom_token(index): index for index in range(count)}
    owners: list[set[int]] = [set() for _ in range(count)]
    for resource_index, resource in enumerate(resources):
        data = resource.data
        cursor = 0
        while cursor < len(data) and data[cursor]:
            if data[cursor] == 0x1F and cursor + 1 < len(data):
                cursor += 2
                continue
            if data[cursor] >= 0x80 and cursor + 1 < len(data):
                slot = token_slots.get(data[cursor : cursor + 2])
                if slot is not None:
                    owners[slot].add(resource_index)
                cursor += 2
            else:
                cursor += 1
    return owners


def dead_font_slots(
    record: GcxRecord, ignore_resources: set[int] = frozenset()
) -> list[int]:
    """Slots referenced by zero resources once ignore_resources are excluded,
    using glyph_slot_owners' exact-parse scan rather than freed_font_slots'
    raw cross-resource substring join. dead_font_slots(record, set()) is
    "every slot with zero live references right now" -- the primitive for
    finding pre-existing dead slots independent of any particular build.
    """
    _, count = font_region(record)
    owners = glyph_slot_owners(record.resources(), count)
    return [slot for slot, refs in enumerate(owners) if refs <= ignore_resources]


def freed_glyphs(
    owners: list[frozenset[int]], selected: set[int]
) -> set[int]:
    return {glyph for glyph, resources in enumerate(owners) if resources <= selected}


def plan_capacity_resources(
    owners: list[frozenset[int]],
    mandatory: set[int],
    target: int,
    allowed: set[int],
) -> set[int]:
    """Find a compact resource set with a deterministic greedy heuristic."""
    selected = set(mandatory)
    while len(freed_glyphs(owners, selected)) < target:
        before = freed_glyphs(owners, selected)
        best: tuple[tuple[float, int, int, int, int], set[int]] | None = None
        for glyph, resources in enumerate(owners):
            if glyph in before or not resources or not resources <= allowed:
                continue
            trial = selected | set(resources)
            gain = len(freed_glyphs(owners, trial)) - len(before)
            added = len(trial) - len(selected)
            if gain <= 0:
                continue
            key = (added / gain, added, -gain, len(resources), glyph)
            if best is None or key < best[0]:
                best = (key, trial)
        if best is None:
            raise CodecError(f"cannot free {target} glyph slots in the allowed range")
        selected = best[1]

    changed = True
    while changed:
        changed = False
        for resource in sorted(selected - mandatory):
            trial = selected - {resource}
            if len(freed_glyphs(owners, trial)) >= target:
                selected = trial
                changed = True
    return selected


def unit_is_changed(
    unit: dict[str, object], original: bytes, character_map: dict[str, bytes]
) -> bool:
    """Conservatively decide whether a translation unit changes its resource."""
    text = str(unit["text"])
    try:
        rendered = parse_rendered(text, character_map)
    except CodecError:
        if any(0xAC00 <= ord(character) <= 0xD7A3 for character in text):
            return True
        raise
    return rendered != original


def font_region(record: GcxRecord) -> tuple[int, int]:
    start = record.block_start + record.font_data_offset
    end = record.block_start + record.proc_offset
    size = end - start
    if size <= 4:
        return start, 0
    payload_size = struct.unpack_from("<I", record.raw, start)[0]
    if payload_size != size - 4 or payload_size % GLYPH_SIZE:
        raise CodecError(
            f"unexpected GCX font region: section={size:#x}, header={payload_size:#x}"
        )
    return start + 4, payload_size // GLYPH_SIZE


def command_list(args: argparse.Namespace) -> None:
    records = parse_codec(args.codec.read_bytes())
    populated = []
    total = 0
    for index, record in enumerate(records):
        _, count = font_region(record)
        if count:
            populated.append({"gcx": index, "glyphs": count})
            total += count
    print(f"GCX records with custom glyphs: {len(populated)}/{len(records)}")
    print(f"custom glyphs: {total}")
    for item in populated if args.all else populated[: args.limit]:
        print(f"GCX {item['gcx']:4}: {item['glyphs']:3} glyphs")


def command_select_diagnostic(args: argparse.Namespace) -> None:
    records = parse_codec(args.codec.read_bytes())
    document = json.loads(args.translation.read_text(encoding="utf-8-sig"))
    groups: dict[int, list[dict[str, object]]] = {}
    for unit in document.get("units", []):
        groups.setdefault(int(unit["gcx"]), []).append(unit)
    selected: list[dict[str, object]] = []
    report = []
    for gcx, units in sorted(groups.items()):
        _, slots = font_region(records[gcx])
        hangul = {character for unit in units for character in str(unit["text"]) if "가" <= character <= "힣"}
        fits = len(hangul) <= slots
        if fits:
            selected.extend(units)
        report.append({"gcx": gcx, "units": len(units), "hangul": len(hangul), "slots": slots, "selected": fits})
    output = dict(document)
    output["units"] = selected
    output["diagnostic_subset"] = report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"diagnostic subset: {len(selected)}/{sum(len(v) for v in groups.values())} units, "
          f"{sum(1 for row in report if row['selected'])}/{len(report)} GCX records")


def command_extract(args: argparse.Namespace) -> None:
    records = parse_codec(args.codec.read_bytes())
    if not 0 <= args.gcx < len(records):
        raise CodecError(f"GCX index out of range: {args.gcx}")
    record = records[args.gcx]
    start, count = font_region(record)
    if not count:
        raise CodecError(f"GCX {args.gcx} has no custom glyphs")
    columns = min(args.columns, count)
    rows = (count + columns - 1) // columns
    sheet = Image.new("L", (columns * WIDTH, rows * HEIGHT))
    for index in range(count):
        data = record.raw[start + index * GLYPH_SIZE : start + (index + 1) * GLYPH_SIZE]
        sheet.paste(decode_glyph(data, args.layout), ((index % columns) * WIDTH, (index // columns) * HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    manifest = {
        "format": "mgs3d-gcx-custom-font-v1",
        "gcx": args.gcx,
        "glyph_count": count,
        "glyph_size": [WIDTH, HEIGHT],
        "bits_per_pixel": 2,
        "layout": args.layout,
        "escape": "1F nn selects glyph nn (zero-based)",
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"extracted {count} glyphs to {args.output}")


def command_patch(args: argparse.Namespace) -> None:
    original = args.codec.read_bytes()
    records = parse_codec(original)
    if not 0 <= args.gcx < len(records):
        raise CodecError(f"GCX index out of range: {args.gcx}")
    record = records[args.gcx]
    start, count = font_region(record)
    if not 0 <= args.glyph < count:
        raise CodecError(f"glyph index out of range: {args.glyph} (count {count})")
    replacement = encode_glyph(Image.open(args.image), args.layout)
    record_data = bytearray(record.raw)
    offset = start + args.glyph * GLYPH_SIZE
    record_data[offset : offset + GLYPH_SIZE] = replacement
    output = bytearray(original)
    absolute = record.source_offset + offset
    output[absolute : absolute + GLYPH_SIZE] = replacement
    args.output.write_bytes(output)
    # Structural verification catches accidental record damage.
    reparsed = parse_codec(bytes(output))
    if len(reparsed) != len(records):
        raise CodecError("patched codec failed record-count verification")
    print(f"patched GCX {args.gcx} glyph {args.glyph} -> {args.output}")
    print(f"sha256={sha256(output)}")


def command_plan_capacity(args: argparse.Namespace) -> None:
    records = parse_codec(args.codec.read_bytes())
    if not 0 <= args.gcx < len(records):
        raise CodecError(f"GCX index out of range: {args.gcx}")
    if args.target <= 0:
        raise CodecError("target must be positive")
    record = records[args.gcx]
    resources = record.resources()
    mandatory = set(args.resources)
    if any(index < 0 or index >= len(resources) for index in mandatory):
        raise CodecError("mandatory resource index out of range")
    maximum = len(resources) - 1 if args.max_resource is None else args.max_resource
    if args.min_resource < 0 or maximum >= len(resources) or args.min_resource > maximum:
        raise CodecError("invalid allowed resource range")
    allowed = set(range(args.min_resource, maximum + 1))
    if not mandatory <= allowed:
        raise CodecError("mandatory resources fall outside allowed range")

    _, glyph_count = font_region(record)
    owners = [
        frozenset(
            index
            for index, resource in enumerate(resources)
            if custom_token(glyph) in resource.data
        )
        for glyph in range(glyph_count)
    ]
    selected = plan_capacity_resources(owners, mandatory, args.target, allowed)
    freed = freed_glyphs(owners, selected)
    result = {
        "format": "mgs3d-codec-capacity-plan-v1",
        "algorithm": "greedy-owner-union-with-redundancy-pruning",
        "optimality_proven": False,
        "gcx": args.gcx,
        "target_freed_slots": args.target,
        "mandatory_resources": sorted(mandatory),
        "allowed_resource_range": [args.min_resource, maximum],
        "selected_resources": sorted(selected),
        "selected_resource_count": len(selected),
        "freed_slots": len(freed),
        "freed_glyphs": sorted(freed),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.template:
        units = []
        for resource_index in sorted(selected):
            resource = resources[resource_index]
            units.append({
                "gcx": args.gcx,
                "resource": resource_index,
                "kind": "script" if resource.is_script else "string",
                "original_size": len(resource.data),
                "required": resource_index in mandatory,
                "preview": decode_mgs_preview(resource.data),
                "text": render_bytes(resource.data),
            })
        template = {
            "format": "mgs3d-codec-translation-v1",
            "note": (
                "Capacity-plan template. Verify every mapping and edit text only; "
                "<HH> tokens preserve exact original bytes. Remove preview/required "
                "metadata if desired; builders ignore it."
            ),
            "character_map": {},
            "capacity_plan": result,
            "units": units,
        }
        args.template.parent.mkdir(parents=True, exist_ok=True)
        args.template.write_text(
            json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"translation template: {args.template}")


def command_capacity(args: argparse.Namespace) -> None:
    codec_data = args.codec.read_bytes()
    translation_data = args.translation.read_bytes()
    records = parse_codec(codec_data)
    document = json.loads(translation_data.decode("utf-8"))
    base_map, validated_units = validate_codec_translation(document)
    units_by_gcx: dict[int, list[dict[str, object]]] = {}
    for unit in validated_units:
        gcx = int(unit["gcx"])
        if not 0 <= gcx < len(records):
            raise CodecError(f"GCX index out of range: {gcx}")
        units_by_gcx.setdefault(gcx, []).append(unit)
    report: list[dict[str, object]] = []
    for gcx, units in sorted(units_by_gcx.items()):
        record = records[gcx]
        resources = record.resources()
        listed = {int(unit["resource"]) for unit in units}
        if any(index < 0 or index >= len(resources) for index in listed):
            raise CodecError(f"resource out of range in GCX {gcx}")
        active_units = [
            unit
            for unit in units
            if unit_is_changed(
                unit, resources[int(unit["resource"])].data, base_map
            )
        ]
        replaced = {int(unit["resource"]) for unit in active_units}
        korean = {
            character
            for unit in active_units
            for character in str(unit["text"])
            if 0xAC00 <= ord(character) <= 0xD7A3
        }
        free = freed_font_slots(record, replaced)
        old_string_bytes = sum(len(resources[index].data) for index in replaced)
        item = {
            "gcx": gcx,
            "listed_resources": len(listed),
            "resources": len(replaced),
            "unique_hangul": len(korean),
            "freed_slots": len(free),
            "slot_deficit": max(0, len(korean) - len(free)),
            "old_string_bytes": old_string_bytes,
        }
        report.append(item)
        print(
            f"GCX {gcx:4}: resources={len(replaced):3}/{len(listed):3} "
            f"Hangul={len(korean):3} freed={len(free):3} "
            f"deficit={item['slot_deficit']:3}"
        )
    passing = sum(not int(item["slot_deficit"]) for item in report)
    print(f"fixed-layout ready: {passing}/{len(report)} GCX records")
    capacity_document = {
        "format": "mgs3d-codec-capacity-v1",
        "source_codec_sha256": sha256(codec_data),
        "translation_sha256": sha256(translation_data),
        "summary": {
            "gcx_records": len(report),
            "ready_records": passing,
            "failing_records": len(report) - passing,
            "listed_resources": sum(int(item["listed_resources"]) for item in report),
            "changed_resources": sum(int(item["resources"]) for item in report),
            "total_slot_deficit": sum(int(item["slot_deficit"]) for item in report),
        },
        "records": report,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(capacity_document, indent=2) + "\n",
            encoding="utf-8",
        )
    failing = len(report) - passing
    if args.check and failing:
        total_deficit = sum(int(item["slot_deficit"]) for item in report)
        raise CodecError(
            f"fixed-layout capacity check failed: {failing}/{len(report)} "
            f"GCX records have a total deficit of {total_deficit} glyph slots"
        )


def command_build_korean(args: argparse.Namespace) -> None:
    original = args.codec.read_bytes()
    records = parse_codec(original)
    document = json.loads(args.translation.read_text(encoding="utf-8"))
    base_map, validated_units = validate_codec_translation(document)
    existing_allocations: dict[int, dict[str, bytes]] = {}
    if args.existing_allocation:
        allocation_document = json.loads(
            args.existing_allocation.read_text(encoding="utf-8")
        )
        for gcx_text, mapping in allocation_document.get("allocations", {}).items():
            gcx = int(gcx_text)
            existing_allocations[gcx] = {
                str(character): bytes.fromhex(str(token))
                for character, token in mapping.items()
            }
    try:
        font = ImageFont.truetype(str(args.font), args.font_size)
    except OSError as exc:
        raise CodecError(f"cannot load TrueType font {args.font}: {exc}") from exc
    if args.reuse_existing_font and args.reuse_freed_font:
        raise CodecError("select only one font reuse mode")
    if args.preserve_file_size and args.reuse_existing_font:
        raise CodecError("--preserve-file-size cannot use diagnostic existing-font reuse")
    if args.preserve_file_size and args.preserve_total_file_size:
        raise CodecError("select per-GCX or total-file size preservation, not both")
    if args.preserve_total_file_size and (args.reuse_existing_font or args.preserve_record_layout):
        raise CodecError("total-file reflow cannot preserve individual record layout")
    if args.reuse_freed_font and not (args.preserve_record_layout or args.preserve_file_size):
        raise CodecError("--reuse-freed-font requires --preserve-record-layout or --preserve-file-size")
    if args.preserve_record_layout and not (
        args.reuse_existing_font or args.reuse_freed_font
    ):
        raise CodecError("fixed record layout requires an existing-font reuse mode")
    if args.reuse_existing_dead_font and not args.reuse_freed_font:
        raise CodecError("--reuse-existing-dead-font requires --reuse-freed-font")

    units_by_gcx: dict[int, list[dict[str, object]]] = {}
    for unit in validated_units:
        gcx = int(unit["gcx"])
        if not 0 <= gcx < len(records):
            raise CodecError(f"GCX index out of range: {gcx}")
        units_by_gcx.setdefault(gcx, []).append(unit)

    record_outputs: list[bytes] = []
    changed_records = 0
    added_total = 0
    allocation_report: dict[str, dict[str, str]] = {}
    reuse_summary_records: list[dict[str, object]] = []
    for gcx, record in enumerate(records):
        units = units_by_gcx.get(gcx, [])
        if not units:
            record_outputs.append(record.raw)
            continue
        _, old_count = font_region(record)
        resources = record.resources()
        listed_resource_ids = {int(unit["resource"]) for unit in units}
        for resource in listed_resource_ids:
            if not 0 <= resource < len(resources):
                raise CodecError(f"resource out of range: GCX {gcx}, resource {resource}")
        units = [
            unit
            for unit in units
            if unit_is_changed(
                unit, resources[int(unit["resource"])].data, base_map
            )
        ]
        if not units:
            record_outputs.append(record.raw)
            continue
        replaced_resource_ids = {int(unit["resource"]) for unit in units}
        existing_map = existing_allocations.get(gcx, {})
        korean: list[str] = []
        seen: set[str] = set()
        for unit in units:
            for character in str(unit["text"]):
                if (0xAC00 <= ord(character) <= 0xD7A3
                        and character not in base_map
                        and character not in existing_map
                        and character not in seen):
                    seen.add(character)
                    korean.append(character)
        existing_dead: list[int] = []
        newly_freed: list[int] = []
        if args.reuse_existing_dead_font:
            existing_dead = dead_font_slots(record, set())
            freed_by_this_run = dead_font_slots(record, replaced_resource_ids)
            newly_freed = [slot for slot in freed_by_this_run if slot not in existing_dead]
            available_slots = sorted(existing_dead) + sorted(newly_freed)
        elif args.reuse_freed_font:
            newly_freed = freed_font_slots(record, replaced_resource_ids)
            available_slots = list(newly_freed)
        else:
            available_slots = []
        reserved_slots = {
            index
            for token in existing_map.values()
            for index in range(old_count)
            if custom_token(index) == token
        }
        available_slots = [slot for slot in available_slots if slot not in reserved_slots]
        reused_count = min(len(available_slots), len(korean))
        appended_count = 0 if args.reuse_existing_font else len(korean) - reused_count
        if old_count + appended_count > 1020:
            raise CodecError(
                f"GCX {gcx} needs {appended_count} appended Hangul glyphs but only "
                f"{1020 - old_count} custom slots remain"
            )
        local_map = dict(base_map)
        local_map.update(existing_map)
        allocation: dict[str, str] = {}
        glyph_data = bytearray()
        if args.reuse_freed_font:
            if args.preserve_record_layout and len(available_slots) < len(korean):
                raise CodecError(
                    f"GCX {gcx} fixed-layout font capacity: needs {len(korean)}, "
                    f"only {len(available_slots)} slots become free; "
                    f"translate more resources in this GCX or reduce unique Hangul"
                )
            selected_slots = (available_slots[:reused_count]
                              + list(range(old_count, old_count + appended_count)))
        elif args.reuse_existing_font:
            if len(korean) > old_count:
                raise CodecError(
                    f"GCX {gcx} diagnostic reuse needs {len(korean)} slots, has {old_count}"
                )
            selected_slots = list(range(len(korean)))
        else:
            selected_slots = list(range(old_count, old_count + len(korean)))
        if selected_slots[:reused_count] != available_slots[:reused_count]:
            raise CodecError(
                f"GCX {gcx}: reused slot indices do not match overwrite target "
                f"-- internal allocation bug"
            )
        reused_slots_used = set(selected_slots[:reused_count])
        reused_existing_dead = len(reused_slots_used & set(existing_dead))
        reused_newly_freed = len(reused_slots_used & set(newly_freed))
        for index, character in zip(selected_slots, korean):
            encoded = custom_token(index)
            local_map[character] = encoded
            allocation[character] = encoded.hex().upper()
            glyph_data.extend(render_character(character, font))

        replacements: dict[int, bytes] = {}
        for unit in units:
            resource = int(unit["resource"])
            replacement = parse_rendered(str(unit["text"]), local_map)
            if replacement != resources[resource].data:
                replacements[resource] = replacement
        target_string_size = None
        if args.preserve_file_size:
            old_string_size = record.font_data_offset - record.string_resources_offset
            target_string_size = old_string_size - appended_count * GLYPH_SIZE
        try:
            replaced_raw = record.replace_resources(
                replacements,
                preserve_layout=args.preserve_record_layout,
                string_region_size=target_string_size,
                alias_adjacent=args.alias_adjacent_strings,
                alias_all=args.alias_all_strings,
            )
        except CodecError as exc:
            raise CodecError(f"GCX {gcx}: {exc}") from exc
        rebuilt = GcxRecord(replaced_raw, record.source_offset)
        reused_bytes = bytes(glyph_data[:reused_count * GLYPH_SIZE])
        appended_bytes = bytes(glyph_data[reused_count * GLYPH_SIZE:])
        rebuilt_raw = replaced_raw
        if reused_bytes:
            rebuilt_raw = overwrite_font_slots(GcxRecord(rebuilt_raw, record.source_offset),
                                               selected_slots[:reused_count], reused_bytes)
        if appended_bytes:
            rebuilt_raw = append_font(GcxRecord(rebuilt_raw, record.source_offset), appended_bytes)
        if args.preserve_file_size and len(rebuilt_raw) != len(record.raw):
            raise CodecError(
                f"GCX {gcx} size-neutral rebuild changed size: "
                f"{len(record.raw)} -> {len(rebuilt_raw)}"
            )
        record_outputs.append(rebuilt_raw)
        if replacements or glyph_data:
            changed_records += 1
        added_total += len(korean)
        if allocation:
            allocation_report[str(gcx)] = allocation
        if glyph_data:
            reuse_summary_records.append({
                "gcx": gcx,
                "reused_existing_dead": reused_existing_dead,
                "reused_newly_freed": reused_newly_freed,
                "newly_appended": appended_count,
                "final_gcx_size_delta": len(rebuilt_raw) - len(record.raw),
            })

    natural_size = sum(len(raw) for raw in record_outputs)
    reflow_padding = 0
    if args.preserve_total_file_size:
        if natural_size > len(original):
            raise CodecError(
                f"global codec capacity deficit: natural build exceeds source by "
                f"{natural_size - len(original)} bytes"
            )
        remaining_padding = len(original) - natural_size
        for index, (source, raw) in enumerate(zip(records, record_outputs)):
            if not remaining_padding:
                break
            padding = min(max(0, len(source.raw) - len(raw)), remaining_padding)
            if not padding:
                continue
            built = GcxRecord(raw, source.source_offset)
            resources = built.resources()
            if not resources:
                raise CodecError(f"GCX {index} cannot absorb global reflow padding")
            old_string_size = built.font_data_offset - built.string_resources_offset
            padded = built.replace_resources(
                {0: resources[0].data}, string_region_size=old_string_size + padding)
            if len(padded) != len(raw) + padding:
                raise CodecError(f"GCX {index} did not absorb {padding} padding bytes")
            record_outputs[index] = padded
            reflow_padding += padding
            remaining_padding -= padding
        if remaining_padding or sum(len(raw) for raw in record_outputs) != len(original):
            raise CodecError(
                f"global reflow did not converge: remaining={remaining_padding}, "
                f"size={sum(len(raw) for raw in record_outputs)}/{len(original)}"
            )
    output = b"".join(record_outputs)
    reparsed = parse_codec(output)
    if len(reparsed) != len(records):
        raise CodecError("Korean build failed record-count verification")
    gcx53_delta = (
        reparsed[53].source_offset - records[53].source_offset
        if len(records) > 53
        else 0
    )
    if gcx53_delta:
        patched_gcx53 = relocate_gcx53_inner_offsets(reparsed[53], gcx53_delta)
        patched_output = bytearray(output)
        start = reparsed[53].source_offset
        patched_output[start:start + len(patched_gcx53)] = patched_gcx53
        output = bytes(patched_output)
        reparsed = parse_codec(output)
    if args.preserve_record_layout:
        mismatches = [
            index
            for index, (source, built) in enumerate(zip(records, reparsed))
            if (
                source.source_offset != built.source_offset
                or len(source.raw) != len(built.raw)
                or source.string_resources_offset != built.string_resources_offset
                or source.font_data_offset != built.font_data_offset
                or source.proc_offset != built.proc_offset
            )
        ]
        if mismatches:
            raise CodecError(
                f"fixed-layout verification failed in {len(mismatches)} GCX records: "
                f"{mismatches[:10]}"
            )
    if args.preserve_file_size:
        mismatches = [
            index
            for index, (source, built) in enumerate(zip(records, reparsed))
            if source.source_offset != built.source_offset or len(source.raw) != len(built.raw)
        ]
        if len(output) != len(original) or mismatches:
            raise CodecError(
                f"size-neutral verification failed: file {len(original)} -> {len(output)}, "
                f"record mismatches {mismatches[:10]}"
            )
    if args.preserve_total_file_size and len(output) != len(original):
        raise CodecError(f"total-file size changed: {len(original)} -> {len(output)}")
    reuse_summary = {
        "reused_existing_dead": sum(r["reused_existing_dead"] for r in reuse_summary_records),
        "reused_newly_freed": sum(r["reused_newly_freed"] for r in reuse_summary_records),
        "newly_appended": sum(r["newly_appended"] for r in reuse_summary_records),
        "final_gcx_size_delta": sum(r["final_gcx_size_delta"] for r in reuse_summary_records),
        "records": reuse_summary_records,
    }
    print(
        f"reuse summary: reused_existing_dead={reuse_summary['reused_existing_dead']} "
        f"reused_newly_freed={reuse_summary['reused_newly_freed']} "
        f"newly_appended={reuse_summary['newly_appended']} "
        f"final_gcx_size_delta={reuse_summary['final_gcx_size_delta']}"
    )
    if args.dry_run:
        print(
            f"dry-run: would write {args.output} "
            f"({changed_records} GCX records changed, {added_total} Hangul glyphs added)"
        )
        return
    args.output.write_bytes(output)
    report_path = args.output.with_suffix(args.output.suffix + ".hangul.json")
    report_path.write_text(
        json.dumps(
            {
                "format": "mgs3d-hangul-allocation-v1",
                "font": str(args.font),
                "font_size": args.font_size,
                "added_glyphs": added_total,
                "natural_file_size": natural_size,
                "final_file_size": len(output),
                "reflow_padding": reflow_padding,
                "allocations": allocation_report,
                "reuse_summary": reuse_summary,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output}: {changed_records} GCX records changed, "
        f"{added_total} Hangul glyphs added, sha256={sha256(output)}"
    )
    print(f"allocation report: {report_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list GCX custom-font counts")
    listing.add_argument("codec", type=Path)
    listing.add_argument("--limit", type=int, default=30)
    listing.add_argument("--all", action="store_true")
    listing.set_defaults(function=command_list)
    diagnostic = commands.add_parser(
        "select-diagnostic", help="select GCX groups that fit existing glyph slots"
    )
    diagnostic.add_argument("codec", type=Path)
    diagnostic.add_argument("translation", type=Path)
    diagnostic.add_argument("output", type=Path)
    diagnostic.set_defaults(function=command_select_diagnostic)
    extract = commands.add_parser("extract", help="extract one GCX font sheet")
    extract.add_argument("codec", type=Path)
    extract.add_argument("gcx", type=int)
    extract.add_argument("output", type=Path)
    extract.add_argument("--layout", choices=("linear", "tiled8"), default="linear")
    extract.add_argument("--columns", type=int, default=16)
    extract.set_defaults(function=command_extract)
    patch = commands.add_parser("patch", help="replace one glyph from a 16x16 image")
    patch.add_argument("codec", type=Path)
    patch.add_argument("gcx", type=int)
    patch.add_argument("glyph", type=int)
    patch.add_argument("image", type=Path)
    patch.add_argument("output", type=Path)
    patch.add_argument("--layout", choices=("linear", "tiled8"), default="linear")
    patch.set_defaults(function=command_patch)
    planner = commands.add_parser(
        "plan-capacity",
        help="select resources that can free a target number of fixed-layout slots",
    )
    planner.add_argument("codec", type=Path)
    planner.add_argument("gcx", type=int)
    planner.add_argument("target", type=int)
    planner.add_argument(
        "resources",
        type=int,
        nargs="+",
        help="mandatory resource indices that must remain in the plan",
    )
    planner.add_argument("--min-resource", type=int, default=0)
    planner.add_argument("--max-resource", type=int)
    planner.add_argument("--json", type=Path, help="write the machine-readable plan")
    planner.add_argument(
        "--template",
        type=Path,
        help="write selected resources as an editable translation JSON",
    )
    planner.set_defaults(function=command_plan_capacity)
    capacity = commands.add_parser(
        "capacity", help="report safe fixed-layout Hangul capacity by GCX"
    )
    capacity.add_argument("codec", type=Path)
    capacity.add_argument("translation", type=Path)
    capacity.add_argument("--json", type=Path)
    capacity.add_argument(
        "--check",
        action="store_true",
        help="exit with an error if any changed GCX has a nonzero slot deficit",
    )
    capacity.set_defaults(function=command_capacity)
    korean = commands.add_parser(
        "build-korean",
        help="encode Hangul, allocate per-GCX glyphs, and rebuild codec.dat",
    )
    korean.add_argument("codec", type=Path)
    korean.add_argument("translation", type=Path)
    korean.add_argument("font", type=Path)
    korean.add_argument("output", type=Path)
    korean.add_argument("--font-size", type=int, default=15)
    korean.add_argument(
        "--existing-allocation",
        type=Path,
        help="reuse a previous build's per-GCX Hangul allocation sidecar",
    )
    korean.add_argument(
        "--reuse-existing-font",
        action="store_true",
        help="diagnostic: overwrite existing glyph slots instead of growing GCX",
    )
    korean.add_argument(
        "--reuse-freed-font",
        action="store_true",
        help="safe fixed-layout mode: use only slots freed by translated resources",
    )
    korean.add_argument(
        "--reuse-existing-dead-font",
        action="store_true",
        help="safe fixed-layout mode: also reuse glyph slots already dead from past "
             "builds (regardless of this run's own resource replacements) before "
             "appending; requires --reuse-freed-font",
    )
    korean.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report reuse/append counts without writing any files",
    )
    korean.add_argument(
        "--preserve-record-layout",
        action="store_true",
        help="keep every GCX string/font/procedure boundary at its original offset",
    )
    korean.add_argument(
        "--preserve-file-size",
        action="store_true",
        help="fund appended glyphs by shrinking strings so every GCX and codec.dat keep their size",
    )
    korean.add_argument(
        "--preserve-total-file-size",
        action="store_true",
        help="allow GCX boundaries to move while keeping total codec.dat size exact",
    )
    korean.add_argument(
        "--alias-adjacent-strings",
        action="store_true",
        help="store adjacent identical resources once while preserving table entries",
    )
    korean.add_argument(
        "--alias-all-strings",
        action="store_true",
        help="store every identical flags+bytes resource once per GCX",
    )
    korean.set_defaults(function=command_build_korean)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (CodecError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
