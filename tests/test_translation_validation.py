from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path
from types import SimpleNamespace


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_translation import (  # noqa: E402
    TranslationError,
    validate_codec_translation,
)
from mgs3d_codec_tool import CodecError, command_validate_translation  # noqa: E402


def document(units: object, character_map: object | None = None) -> dict[str, object]:
    return {
        "format": "mgs3d-codec-translation-v1",
        "character_map": {} if character_map is None else character_map,
        "units": units,
    }


class MemoryPath:
    def __init__(self, content: str = "", name: str = "memory.json") -> None:
        self.content = content
        self.name = name

    @property
    def parent(self) -> "MemoryPath":
        return self

    def mkdir(self, **_kwargs: object) -> None:
        pass

    def read_text(self, **_kwargs: object) -> str:
        return self.content

    def write_text(self, content: str, **_kwargs: object) -> int:
        self.content = content
        return len(content)

    def __str__(self) -> str:
        return self.name


class TranslationValidationTests(unittest.TestCase):
    def test_valid_document_returns_decoded_map_and_units(self) -> None:
        source = document(
            [{"gcx": 1, "resource": 2, "kind": "string", "text": "한<00>"}],
            {"한": "8C01"},
        )
        character_map, units = validate_codec_translation(source)
        self.assertEqual(character_map, {"한": b"\x8c\x01"})
        self.assertEqual(len(units), 1)

    def test_duplicate_resource_is_rejected(self) -> None:
        source = document([
            {"gcx": 1, "resource": 2, "text": "A<00>"},
            {"gcx": 1, "resource": 2, "text": "B<00>"},
        ])
        with self.assertRaisesRegex(TranslationError, "duplicate resource"):
            validate_codec_translation(source)

    def test_missing_required_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationError, "missing 'text'"):
            validate_codec_translation(document([{"gcx": 1, "resource": 2}]))

    def test_string_index_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationError, "gcx must be an integer"):
            validate_codec_translation(
                document([{"gcx": "1", "resource": 2, "text": "A<00>"}])
            )

    def test_negative_index_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationError, "must be nonnegative"):
            validate_codec_translation(
                document([{"gcx": 1, "resource": -1, "text": "A<00>"}])
            )

    def test_non_string_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationError, "text must be a string"):
            validate_codec_translation(
                document([{"gcx": 1, "resource": 2, "text": None}])
            )

    def test_bad_kind_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationError, "kind must be"):
            validate_codec_translation(
                document([{"gcx": 1, "resource": 2, "kind": "bad", "text": "A"}])
            )

    def test_bad_character_map_is_rejected(self) -> None:
        with self.assertRaisesRegex(TranslationError, "invalid hex mapping"):
            validate_codec_translation(document([], {"한": "XYZ"}))

    def test_missing_units_array_is_rejected(self) -> None:
        source = {"format": "mgs3d-codec-translation-v1", "character_map": {}}
        with self.assertRaisesRegex(TranslationError, "units must be an array"):
            validate_codec_translation(source)

    def test_standalone_validation_writes_summary_without_game_files(self) -> None:
        source = document([{"gcx": 1, "resource": 2, "text": "한<00>"}])
        translation = MemoryPath(json.dumps(source), "translation.json")
        report = MemoryPath(name="report.json")
        command_validate_translation(SimpleNamespace(translation=translation, json=report))
        result = json.loads(report.content)
        self.assertTrue(result["valid"])
        self.assertEqual(result["units"], 1)
        self.assertEqual(result["unique_hangul"], 1)

    def test_standalone_validation_rejects_malformed_tokens(self) -> None:
        source = document([{"gcx": 1, "resource": 2, "text": "bad<ZZ>"}])
        translation = MemoryPath(json.dumps(source), "translation.json")
        with self.assertRaisesRegex(CodecError, "not encodable"):
            command_validate_translation(
                SimpleNamespace(translation=translation, json=None)
            )


if __name__ == "__main__":
    unittest.main()
