import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mgs3d_static_allocation_optimize import optimize
from mgs3d_hpk_static_korean import token_for_allocation_slot


class StaticAllocationOptimizeTests(unittest.TestCase):
    def test_extended_page_skips_runtime_cleared_8301(self):
        self.assertEqual(token_for_allocation_slot(164), b"\x82\x54")
        self.assertEqual(token_for_allocation_slot(165), b"\x83\x02")
        self.assertEqual(token_for_allocation_slot(190), b"\x83\x1b")

    def test_prefers_character_that_unlocks_more_rows(self):
        translation = {"units": [
            {"gcx": 1, "resource": 0, "text": "\uac00\ub098"},
            {"gcx": 1, "resource": 1, "text": "\uac00\ub2e4"},
        ]}
        report = {"records": [{
            "gcx": 1,
            "glyph_limit": 1,
            "candidate_resources": [0, 1],
        }]}
        required = {"required_hangul": ["\ub098", "\ub2e4"]}
        result = optimize(translation, report, required)
        self.assertIn("\uac00", result["characters"])
        self.assertEqual(result["individually_feasible_codec_rows"], 2)

    def test_swap_improves_greedy_static_allocation(self):
        filler = [chr(0xAC00 + index) for index in range(163)]
        a, b, c, x, y, u, v = [chr(0xB000 + index) for index in range(7)]
        edges = ([{a, b}] * 2 + [{a, c}] * 2 + [{a, x}, {a, y}]
                 + [{b, u}] * 3 + [{c, v}] * 3)
        translation = {"units": [
            {"gcx": 1, "resource": index, "text": "".join(sorted(edge))}
            for index, edge in enumerate(edges)
        ]}
        report = {"records": [{
            "gcx": 1,
            "glyph_limit": 1,
            "candidate_resources": list(range(len(edges))),
        }]}
        safe = optimize(translation, report, {"required_hangul": filler})
        self.assertEqual(safe["individually_feasible_codec_rows"], 9)
        self.assertEqual(safe["swap_trace"], [])
        result = optimize(translation, report, {"required_hangul": filler},
                          allow_feasible_regressions=True)
        self.assertEqual(result["individually_feasible_codec_rows"], 10)
        self.assertEqual(len(result["swap_trace"]), 1)


if __name__ == "__main__":
    unittest.main()
