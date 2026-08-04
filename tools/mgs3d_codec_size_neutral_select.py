#!/usr/bin/env python3
"""Select a deterministic size-neutral subset of codec Korean translations."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import CodecError, parse_codec, parse_rendered  # noqa: E402
from mgs3d_gcx_font_tool import custom_token, font_region  # noqa: E402
from mgs3d_translation import validate_codec_translation  # noqa: E402
from mgs3d_english_korean_match import decode_western  # noqa: E402


WORDS = re.compile(r"[a-z]+")
LANGUAGE_WORDS = {
    "en": {"the", "and", "you", "your", "is", "are", "to", "of", "that", "this", "it", "for", "with", "have", "not", "what", "we"},
    "es": {"el", "los", "las", "del", "que", "una", "para", "con", "por", "como", "pero", "est", "tu", "te", "se", "lo", "nos"},
    "fr": {"le", "les", "des", "du", "que", "qu", "un", "une", "pour", "avec", "est", "vous", "pas", "mais", "dans", "nous", "sur", "ce", "il", "sa", "ses", "qui", "au", "aux", "ennemi", "intrus", "ma", "ville", "natale", "famille", "copine", "vieux", "cole"},
    "de": {"der", "die", "das", "den", "dem", "des", "und", "ist", "nicht", "ein", "eine", "mit", "auf", "ich", "sie", "wir"},
    "it": {"il", "gli", "della", "che", "una", "per", "con", "non", "sono", "questo", "come", "ma", "nel", "dei", "alla"},
}


def language_scores(raw: bytes) -> tuple[list[str], dict[str, int]]:
    words = WORDS.findall(decode_western(raw).casefold())
    return words, {language: sum(word in vocabulary for word in words)
                   for language, vocabulary in LANGUAGE_WORDS.items()}


def confident_non_english_language(raw: bytes) -> str | None:
    words, scores = language_scores(raw)
    if len(words) < 6:
        return None
    languages = ("es", "fr", "de", "it")
    language = max(languages, key=lambda item: (scores[item], -languages.index(item)))
    return language if scores[language] >= 3 and scores[language] >= scores["en"] + 2 else None


def confident_non_english(raw: bytes) -> bool:
    return confident_non_english_language(raw) is not None


def confident_english(raw: bytes) -> bool:
    words, scores = language_scores(raw)
    return (len(words) >= 6 and scores["en"] >= 3
            and scores["en"] >= max(scores[language] for language in ("es", "fr", "de", "it")) + 2)


def language_block_donors(resources: list[object], protected: set[int]) -> list[int]:
    """Return a structurally bounded Spanish/French resource block.

    Western codec GCXs store English followed by Spanish and French copies.
    Short foreign strings cannot be classified safely in isolation, so anchor
    the block at the first and last confident Spanish/French or Western
    accent-control resource. Every unprotected string inside that structural
    language block is reclaimable.
    """
    anchors = [index for index, resource in enumerate(resources)
               if not resource.is_script and (
                   confident_non_english_language(resource.data) in {"es", "fr"}
                   or b"\x1f" in resource.data)]
    if not anchors:
        return []
    start, end = min(anchors), max(anchors)
    return [index for index in range(start, end + 1)
            if index not in protected and not resources[index].is_script]


def hangul(text: str, base_map: dict[str, bytes] | None = None) -> frozenset[str]:
    base_map = base_map or {}
    return frozenset(ch for ch in text
                     if 0xAC00 <= ord(ch) <= 0xD7A3 and ch not in base_map)


def encoded_size(text: str, old_count: int,
                 base_map: dict[str, bytes] | None = None) -> int:
    base_map = base_map or {}
    chars = sorted(hangul(text, base_map))
    mapping = dict(base_map)
    mapping.update({ch: custom_token(old_count + index) for index, ch in enumerate(chars)})
    return len(parse_rendered(text, mapping))


def glyph_slot_owners(resources: list[object], count: int) -> list[set[int]]:
    token_slots = {custom_token(index): index for index in range(count)}
    owners = [set() for _ in range(count)]
    for resource_index, resource in enumerate(resources):
        data = resource.data
        cursor = 0
        while cursor + 1 < len(data) and data[cursor]:
            if data[cursor] >= 0x80:
                slot = token_slots.get(data[cursor:cursor + 2])
                if slot is not None:
                    owners[slot].add(resource_index)
                cursor += 2
            else:
                cursor += 1
    return owners


def free_slots(items: list[dict[str, object]], selected: set[int],
               base_free_slots: int | set[int] = 0) -> set[int]:
    if items and "slot_owners" in items[0]:
        replaced = set(items[0].get("donor_resources", set()))
        replaced.update(int(items[index]["resource"]) for index in selected)
        return {
            slot for slot, references in enumerate(items[0]["slot_owners"])
            if references <= replaced
        }
    slots = (set(base_free_slots) if isinstance(base_free_slots, set)
             else set(range(-base_free_slots, 0)))
    for index in selected:
        slots.update(items[index].get("freed_slots", set()))
    return slots


def balance(items: list[dict[str, object]], selected: set[int], base_savings: int = 0,
            base_free_slots: int | set[int] = 0) -> tuple[int, int, int]:
    savings = base_savings + sum(int(items[index]["saving"]) for index in selected)
    glyphs = set().union(*(items[index]["glyphs"] for index in selected)) if selected else set()
    cost = max(0, len(glyphs) - len(free_slots(items, selected, base_free_slots))) * 64
    return savings - cost, savings, len(glyphs)


def select_subset(items: list[dict[str, object]], base_savings: int = 0,
                  base_free_slots: int | set[int] = 0,
                  max_new_glyphs: int | None = None,
                  fixed_font_slots: bool = False) -> set[int]:
    selected = set(range(len(items)))
    def fits(indices: set[int]) -> bool:
        net, _, glyph_count = balance(items, indices, base_savings, base_free_slots)
        available = len(free_slots(items, indices, base_free_slots))
        return (net >= 0
                and (max_new_glyphs is None or glyph_count <= max_new_glyphs)
                and (not fixed_font_slots or glyph_count <= available))

    if fits(selected):
        return selected
    while selected:
        counts = Counter(ch for index in selected for ch in items[index]["glyphs"])
        choices = []
        for index in selected:
            exclusive = sum(counts[ch] == 1 for ch in items[index]["glyphs"])
            improvement = exclusive * 64 - int(items[index]["saving"])
            # Prefer the removal that most improves capacity, then the largest
            # glyph footprint and finally the stable resource order.
            # Supplemental/manual split rows are coverage priorities.  Remove
            # ordinary matcher rows first; if priorities alone still do not
            # fit, retain earlier supplemental resources before later ones.
            ordinary = not bool(items[index].get("priority"))
            if ordinary:
                choices.append((1, improvement, len(items[index]["glyphs"]), index, index))
            else:
                choices.append((0, index, improvement, len(items[index]["glyphs"]), index))
        selected.remove(max(choices)[4])
        if fits(selected):
            break
    # Removal can overshoot. Refill remaining capacity deterministically while
    # retaining priority rows, then ordinary rows in source-resource order.
    excluded = sorted((index for index in range(len(items)) if index not in selected),
                      key=lambda index: (not bool(items[index].get("priority")), index))
    for index in excluded:
        trial = selected | {index}
        if fits(trial):
            selected = trial
    return selected


def select_subset_exact(items: list[dict[str, object]], base_savings: int = 0,
                        base_free_slots: int | set[int] = 0,
                        max_new_glyphs: int | None = None,
                        fixed_font_slots: bool = False) -> set[int]:
    """Maximize translated row count exactly for small GCXs."""
    if len(items) > 16:
        return select_subset(items, base_savings, base_free_slots, max_new_glyphs,
                             fixed_font_slots)
    best_key: tuple[object, ...] | None = None
    best: set[int] = set()
    for mask in range(1 << len(items)):
        selected = {index for index in range(len(items)) if mask & (1 << index)}
        net, _, glyph_count = balance(items, selected, base_savings, base_free_slots)
        available = len(free_slots(items, selected, base_free_slots))
        if (net < 0
                or (max_new_glyphs is not None and glyph_count > max_new_glyphs)
                or (fixed_font_slots and glyph_count > available)):
            continue
        key = (
            len(selected),
            sum(bool(items[index].get("priority")) for index in selected),
            -sum(int(items[index].get("resource", index)) for index in selected),
            -sum(index for index in selected),
            -mask,
        )
        if best_key is None or key > best_key:
            best_key, best = key, selected
    return best


def zero_slot_cardinality_bound(items: list[dict[str, object]],
                                base_savings: int) -> int:
    """Exact row-count upper bound when no local glyph slot can be used."""
    savings = sorted(
        (int(item["saving"]) for item in items if not item["glyphs"]),
        reverse=True,
    )
    balance_bytes = base_savings
    best = 0
    for count, saving in enumerate(savings, 1):
        balance_bytes += saving
        if balance_bytes >= 0:
            best = count
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", type=Path)
    parser.add_argument("translation", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--supplement", type=Path, action="append",
                        help="additional validated codec translation JSON (may be repeated)")
    parser.add_argument("--priority-translation", type=Path, action="append",
                        help="existing translation keys that receive selection priority")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--reclaim-non-english", action="store_true")
    parser.add_argument("--reclaim-language-blocks", action="store_true",
                        help="reclaim short Spanish/French strings inside structurally anchored language blocks")
    parser.add_argument("--global-balance", action="store_true",
                        help="select every translation and defer capacity balancing across GCX boundaries")
    parser.add_argument("--max-new-glyphs", type=int,
                        help="runtime-safe maximum unique Hangul glyphs per GCX")
    parser.add_argument(
        "--fixed-font-slots", action="store_true",
        help="select only rows whose local glyphs fit slots freed in the unchanged font region",
    )
    parser.add_argument("--alias-savings-report", type=Path,
                        help="adjacent-alias report whose stable savings may fund more rows")
    parser.add_argument(
        "--donor-report", type=Path,
        help="reuse donor resource lists from a previously verified selection report",
    )
    parser.add_argument("--protect-review", type=Path,
                        help="combined review CSV whose codec targets may never be donors")
    parser.add_argument("--include-gcx", type=int, action="append",
                        help="limit selection and donor reclamation to these GCX indices")
    args = parser.parse_args()
    records = parse_codec(args.codec.read_bytes())
    document = json.loads(args.translation.read_text(encoding="utf-8"))
    base_map, units = validate_codec_translation(document)
    priority_keys: set[tuple[int, int]] = set()
    for priority_path in args.priority_translation or []:
        _, priority_units = validate_codec_translation(
            json.loads(priority_path.read_text(encoding="utf-8")))
        priority_keys.update(
            (int(unit["gcx"]), int(unit["resource"])) for unit in priority_units
        )
    for supplement in args.supplement or []:
        extra_map, extra_units = validate_codec_translation(
            json.loads(supplement.read_text(encoding="utf-8")))
        if extra_map:
            raise CodecError("size-neutral selector expects an empty supplemental character map")
        priority_keys.update((int(unit["gcx"]), int(unit["resource"])) for unit in extra_units)
        units.extend(extra_units)
    keys = [(int(unit["gcx"]), int(unit["resource"])) for unit in units]
    if len(keys) != len(set(keys)):
        raise CodecError("duplicate GCX/resource across primary and supplemental translations")
    by_gcx: dict[int, list[dict[str, object]]] = {}
    for unit in units:
        gcx = int(unit["gcx"])
        if args.include_gcx is None or gcx in args.include_gcx:
            by_gcx.setdefault(gcx, []).append(unit)
    protected: dict[int, set[int]] = {}
    if args.protect_review:
        with args.protect_review.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("container") == "codec" and row.get("gcx") and row.get("resource"):
                    protected.setdefault(int(row["gcx"]), set()).add(int(row["resource"]))
    alias_records: dict[int, list[dict[str, object]]] = {}
    if args.alias_savings_report:
        alias_doc = json.loads(args.alias_savings_report.read_text(encoding="utf-8"))
        alias_records = {int(row["gcx"]): list(row.get("groups", []))
                         for row in alias_doc.get("records", [])}

    fixed_donors: dict[int, list[int]] | None = None
    if args.donor_report:
        donor_document = json.loads(args.donor_report.read_text(encoding="utf-8-sig"))
        fixed_donors = {
            int(row["gcx"]): [int(resource) for resource in row["donor_resources"]]
            for row in donor_document.get("records", [])
        }
        if len(fixed_donors) != len(donor_document.get("records", [])):
            raise CodecError("duplicate GCX rows in donor report")
    selected_units: list[dict[str, object]] = []
    report = []
    for gcx in sorted(by_gcx):
        record = records[gcx]
        resources = record.resources()
        _, old_count = font_region(record)
        items: list[dict[str, object]] = []
        foreign_block = (set(language_block_donors(resources, protected.get(gcx, set())))
                         if args.reclaim_language_blocks else set())
        eligible_units = [unit for unit in by_gcx[gcx]
                          if int(unit["resource"]) not in foreign_block]
        foreign_excluded = sorted({int(unit["resource"]) for unit in by_gcx[gcx]}
                                  & foreign_block)
        candidate_resources = ({int(unit["resource"]) for unit in eligible_units}
                               | (protected.get(gcx, set()) - foreign_block))
        donors = []
        block_donors: list[int] = []
        if fixed_donors is not None:
            donors = list(fixed_donors.get(gcx, []))
            if any(index < 0 or index >= len(resources) or resources[index].is_script
                   for index in donors):
                raise CodecError(f"invalid donor resource in report for GCX {gcx}")
            overlap = set(donors) & candidate_resources
            if overlap:
                raise CodecError(f"donor report overlaps candidate resources in GCX {gcx}")
        elif args.reclaim_language_blocks:
            block_donors = sorted(foreign_block)
            donors = sorted(set(block_donors) | {
                index for index, resource in enumerate(resources)
                if index not in candidate_resources and not resource.is_script
                and confident_non_english(resource.data)
            })
        elif args.reclaim_non_english:
            donors = [index for index, resource in enumerate(resources)
                      if index not in candidate_resources and not resource.is_script
                      and confident_non_english(resource.data)]
        donor_savings = sum(max(0, len(resources[index].data) - 1) for index in donors)
        all_translation_resources = {int(unit["resource"]) for unit in eligible_units}
        stable_alias_savings = 0
        for group in alias_records.get(gcx, []):
            members = [int(index) for index in group.get(
                "resources", range(int(group["first"]), int(group["last"]) + 1))]
            stable = [index for index in members if index not in all_translation_resources]
            copies = int(group.get("copies", len(members)))
            unit_size = (int(group["bytes_saved"]) // (copies - 1)
                         if copies > 1 else 0)
            stable_alias_savings += max(0, len(stable) - 1) * unit_size
        donor_savings += stable_alias_savings
        owners = glyph_slot_owners(resources, old_count)
        donor_set = set(donors)
        donor_slot_ids = {
            slot for slot, references in enumerate(owners)
            if references <= donor_set
        }
        for unit in eligible_units:
            resource = int(unit["resource"])
            text = str(unit["text"])
            items.append({
                "unit": unit,
                "resource": resource,
                "glyphs": hangul(text, base_map),
                "saving": len(resources[resource].data) - encoded_size(text, old_count, base_map),
                "priority": (gcx, resource) in priority_keys,
                "slot_owners": owners,
                "donor_resources": donor_set,
                "freed_slots": {
                    slot for slot, references in enumerate(owners)
                    if references - donor_set <= {resource}
                } - donor_slot_ids,
            })
        if args.global_balance and args.max_new_glyphs is None and not args.fixed_font_slots:
            chosen = set(range(len(items)))
        else:
            # Global balancing may defer byte capacity across records, but the
            # runtime font buffer remains a per-GCX constraint.  Give the
            # subset selector effectively unlimited byte savings in that mode.
            savings = donor_savings + (1 << 60 if args.global_balance else 0)
            chosen = select_subset_exact(
                items, savings, donor_slot_ids, args.max_new_glyphs,
                args.fixed_font_slots)
        net, savings, glyph_count = balance(items, chosen, donor_savings, donor_slot_ids)
        available_slot_ids = free_slots(items, chosen, donor_slot_ids)
        zero_slot_bound = (zero_slot_cardinality_bound(items, donor_savings)
                           if args.fixed_font_slots
                           and not available_slot_ids
                           and not any(owners) else None)
        selected_units.extend({"gcx": gcx, "resource": resource, "kind": "string",
                               "original_size": len(resources[resource].data), "text": "<00>"}
                              for resource in donors)
        selected_units.extend(items[index]["unit"] for index in sorted(chosen))
        report.append({
            "gcx": gcx, "candidates": len(items), "selected": len(chosen),
            "excluded": len(items) - len(chosen), "string_savings": savings,
            "new_glyphs": glyph_count, "glyph_bytes": glyph_count * 64,
            "glyph_limit": (len(available_slot_ids) if args.fixed_font_slots
                            else args.max_new_glyphs),
            "excluded_translations": len(items) - len(chosen),
            "exact_zero_slot_cardinality_bound": zero_slot_bound,
            "reused_glyph_slots": min(glyph_count, len(available_slot_ids)),
            "appended_glyph_bytes": max(0, glyph_count - len(available_slot_ids)) * 64,
            "headroom": net,
            "donor_resources": donors, "donor_savings": donor_savings,
            "stable_alias_savings": stable_alias_savings,
            "language_block": ([min(block_donors), max(block_donors)] if block_donors else None),
            "foreign_block_excluded_resources": foreign_excluded,
            "candidate_resources": sorted(candidate_resources),
            "donor_language_counts": dict(Counter(
                confident_non_english_language(resources[index].data) for index in donors
            )),
            "excluded_resources": [items[index]["resource"] for index in range(len(items))
                                   if index not in chosen],
        })
    output = {"format": "mgs3d-codec-translation-v1",
              "character_map": {character: token.hex().upper()
                                for character, token in base_map.items()},
              "units": selected_units}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report:
        args.report.write_text(json.dumps({"records": report}, indent=2) + "\n", encoding="utf-8")
    translated = sum(int(row["selected"]) for row in report)
    donors = sum(len(row["donor_resources"]) for row in report)
    print(f"selected {translated}/{len(units)} translations plus {donors} donor resources in "
          f"{sum(bool(row['selected']) for row in report)}/{len(report)} GCX records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
