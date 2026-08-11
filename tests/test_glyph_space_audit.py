import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from mgs3d_glyph_space_audit import (  # noqa: E402
    glyph_usage_rows,
    movie_slot_owners,
    verify_resident,
)
from mgs3d_movie_tool import page3_token  # noqa: E402


class GlyphSpaceAuditTests(unittest.TestCase):
    def test_common_hangul_has_zero_local_glyph_row(self) -> None:
        units = [{"row_id": "r1", "english": "A", "korean": "가각"}]
        rows = glyph_usage_rows(units, {"가"}, "movie", 1)
        self.assertEqual([row["glyph"] for row in rows], ["각"])
        self.assertEqual(rows[0]["cost_bytes"], 64)

    def test_movie_dead_slot_is_based_on_page3_token_owners(self) -> None:
        record = SimpleNamespace(
            font=b"F" * 128,
            subtitles=[
                SimpleNamespace(raw=page3_token(0) + b"\0"),
                SimpleNamespace(raw=b"ASCII\0"),
            ],
        )
        self.assertEqual(movie_slot_owners(record), [{0}, set()])

    def test_resident_proof_requires_hash_and_same_character_map(self) -> None:
        resident = Path(__file__).resolve()
        digest = hashlib.sha256(resident.read_bytes()).hexdigest()
        allocation = {"characters": {"가": "8101"}}
        proof = {"characters": {"가": "8101"},
                 "archive": {"output_sha256": digest}}
        result = verify_resident(allocation, [resident], [proof])[0]
        self.assertTrue(result["allocation_sha256_match"])
        self.assertTrue(result["same_character_map"])


if __name__ == "__main__":
    unittest.main()
