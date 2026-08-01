from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_verify_build import (  # noqa: E402
    validate_capacity_provenance,
    validate_output_paths,
)
from mgs3d_build import (  # noqa: E402
    BuildError,
    acquire_build_lock,
    allocation_report_path,
    preserved_output_metadata,
    select_codec_mode,
    temporary_path,
)


class ManifestOutputTests(unittest.TestCase):
    def test_partial_build_is_valid_by_default(self) -> None:
        declared = validate_output_paths([{"path": "romfs/movie.dat"}], False)
        self.assertEqual(declared, {"romfs/movie.dat"})

    def test_complete_build_is_valid_in_release_mode(self) -> None:
        outputs = [
            {"path": "romfs/codec.dat"},
            {"path": "romfs/movie.dat"},
            {"path": "romfs/demo.dat"},
        ]
        self.assertEqual(len(validate_output_paths(outputs, True)), 3)

    def test_partial_build_fails_in_release_mode(self) -> None:
        with self.assertRaisesRegex(SystemExit, "complete build is missing"):
            validate_output_paths([{"path": "romfs/movie.dat"}], True)

    def test_duplicate_output_is_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "duplicate output"):
            validate_output_paths(
                [{"path": "romfs/movie.dat"}, {"path": "romfs/movie.dat"}],
                False,
            )

    def test_unknown_output_is_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "unsupported outputs"):
            validate_output_paths([{"path": "romfs/other.dat"}], False)

    def test_empty_outputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "nonempty array"):
            validate_output_paths([], False)


class IncrementalManifestTests(unittest.TestCase):
    def test_temporary_and_allocation_paths_are_deterministic(self) -> None:
        target = Path("romfs/movie.dat")
        temporary = temporary_path(target)
        self.assertEqual(temporary, Path("romfs/movie.dat.tmp"))
        self.assertEqual(
            allocation_report_path(temporary),
            Path("romfs/movie.dat.tmp.hangul.json"),
        )

    def test_unchanged_output_preserves_capacity_metadata(self) -> None:
        previous = {
            "romfs/codec.dat": {
                "path": "romfs/codec.dat",
                "size": 100,
                "sha256": "abc",
                "capacity_report": "codec-capacity.json",
                "capacity_report_sha256": "def",
            }
        }
        result = preserved_output_metadata(
            "romfs/codec.dat", 100, "abc", previous
        )
        self.assertEqual(result["capacity_report_sha256"], "def")

    def test_changed_output_discards_stale_metadata(self) -> None:
        previous = {
            "romfs/codec.dat": {
                "path": "romfs/codec.dat",
                "size": 100,
                "sha256": "old",
                "capacity_report": "codec-capacity.json",
            }
        }
        result = preserved_output_metadata(
            "romfs/codec.dat", 101, "new", previous
        )
        self.assertNotIn("capacity_report", result)
        self.assertEqual(result["sha256"], "new")

    def test_incremental_build_preserves_previous_codec_mode(self) -> None:
        self.assertEqual(
            select_codec_mode(False, "safe-fixed", True, "diagnostic-fixed"),
            "diagnostic-fixed",
        )

    def test_new_codec_uses_requested_mode(self) -> None:
        self.assertEqual(
            select_codec_mode(True, "safe-fixed", True, "diagnostic-fixed"),
            "safe-fixed",
        )

    def test_untracked_existing_codec_has_unknown_mode(self) -> None:
        self.assertEqual(select_codec_mode(False, "safe-fixed", True, None), "unknown")

    def test_movie_only_build_has_no_codec_mode(self) -> None:
        self.assertIsNone(select_codec_mode(False, "safe-fixed", False, None))

    def test_existing_build_lock_is_rejected(self) -> None:
        root = MagicMock()
        lock = MagicMock()
        root.__truediv__.return_value = lock
        lock.open.side_effect = FileExistsError
        with self.assertRaisesRegex(BuildError, "another build is active"):
            acquire_build_lock(root)
        root.mkdir.assert_called_once_with(parents=True, exist_ok=True)


class CapacityProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec_item = {
            "source_codec_sha256": "source",
            "translation_sha256": "translation",
        }
        self.report = {
            "format": "mgs3d-codec-capacity-v1",
            "source_codec_sha256": "source",
            "translation_sha256": "translation",
            "summary": {
                "gcx_records": 1,
                "failing_records": 0,
                "total_slot_deficit": 0,
            },
            "records": [{"gcx": 1, "slot_deficit": 0}],
        }

    def test_matching_provenance_is_valid(self) -> None:
        self.assertEqual(
            validate_capacity_provenance(self.report, self.codec_item, "source"), 1
        )

    def test_wrong_source_hash_is_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "source hash mismatch"):
            validate_capacity_provenance(self.report, self.codec_item, "other")

    def test_wrong_translation_hash_is_rejected(self) -> None:
        self.codec_item["translation_sha256"] = "other"
        with self.assertRaisesRegex(SystemExit, "translation hash mismatch"):
            validate_capacity_provenance(self.report, self.codec_item, "source")

    def test_nonzero_deficit_is_rejected(self) -> None:
        self.report["records"][0]["slot_deficit"] = 1
        with self.assertRaisesRegex(SystemExit, "has 1 deficits"):
            validate_capacity_provenance(self.report, self.codec_item, "source")

    def test_summary_count_mismatch_is_rejected(self) -> None:
        self.report["summary"]["gcx_records"] = 2
        with self.assertRaisesRegex(SystemExit, "summary mismatch"):
            validate_capacity_provenance(self.report, self.codec_item, "source")


if __name__ == "__main__":
    unittest.main()
