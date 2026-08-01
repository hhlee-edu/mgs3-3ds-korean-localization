#!/usr/bin/env python3
"""Shared validation for editable MGS3D codec translation documents."""

from __future__ import annotations

from typing import Any


FORMAT = "mgs3d-codec-translation-v1"


class TranslationError(ValueError):
    pass


def _index(value: Any, field: str, unit_index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TranslationError(f"unit {unit_index} {field} must be an integer")
    if value < 0:
        raise TranslationError(f"unit {unit_index} {field} must be nonnegative")
    return value


def validate_codec_translation(
    document: Any,
) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    if not isinstance(document, dict):
        raise TranslationError("translation document must be a JSON object")
    if document.get("format") != FORMAT:
        raise TranslationError(f"unsupported translation format: {document.get('format')!r}")

    raw_map = document.get("character_map", {})
    if not isinstance(raw_map, dict):
        raise TranslationError("character_map must be an object")
    character_map: dict[str, bytes] = {}
    for character, encoded in raw_map.items():
        if not isinstance(character, str) or len(character) != 1:
            raise TranslationError(
                f"character-map key must be one character: {character!r}"
            )
        if not isinstance(encoded, str):
            raise TranslationError(f"character mapping for {character!r} must be hex text")
        try:
            value = bytes.fromhex(encoded)
        except ValueError as exc:
            raise TranslationError(
                f"invalid hex mapping for {character!r}: {encoded!r}"
            ) from exc
        if not value:
            raise TranslationError(f"empty character mapping for {character!r}")
        character_map[character] = value

    raw_units = document.get("units")
    if not isinstance(raw_units, list):
        raise TranslationError("units must be an array")
    units: list[dict[str, object]] = []
    seen: dict[tuple[int, int], int] = {}
    for unit_index, unit in enumerate(raw_units):
        if not isinstance(unit, dict):
            raise TranslationError(f"unit {unit_index} must be an object")
        for field in ("gcx", "resource", "text"):
            if field not in unit:
                raise TranslationError(f"unit {unit_index} is missing {field!r}")
        gcx = _index(unit["gcx"], "gcx", unit_index)
        resource = _index(unit["resource"], "resource", unit_index)
        if not isinstance(unit["text"], str):
            raise TranslationError(f"unit {unit_index} text must be a string")
        if "kind" in unit and unit["kind"] not in ("string", "script"):
            raise TranslationError(
                f"unit {unit_index} kind must be 'string' or 'script'"
            )
        key = (gcx, resource)
        if key in seen:
            raise TranslationError(
                f"duplicate resource GCX {gcx}, resource {resource} "
                f"in units {seen[key]} and {unit_index}"
            )
        seen[key] = unit_index
        units.append(unit)
    return character_map, units
