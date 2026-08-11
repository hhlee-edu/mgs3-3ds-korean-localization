import unittest

from tools.mgs3d_nm_window_matcher import PS2Line, ThreeDSCard, align, normalize, score_window


CONFIG = {
    "weights": {"sequence_ratio": .4, "token_f1": .35, "char_ngram": .15, "coverage": .1},
    "window_penalty": .02, "exact_bonus": .1,
    "max_ps2_window": 3, "max_3ds_window": 4,
    "skip_penalty_ps2": .2, "skip_penalty_3ds": .2,
    "match_score_center": .5,
}


class WindowScoreTests(unittest.TestCase):
    def test_1_to_1(self):
        self.assertEqual(normalize("A B C"), normalize("A B C"))

    def test_1_to_2(self):
        a = "Don't get cocky. This isn't a training op."
        b = "Don't get cocky. " + "This isn't a training op."
        self.assertEqual(normalize(a), normalize(b))

    def test_2_to_1(self):
        a = "Sokolov is ours. Now get out of here."
        b = "Sokolov is ours. " + "Now get out of here."
        self.assertEqual(normalize(a), normalize(b))

    def test_short_duplicate_not_intrinsically_unique(self):
        score = score_window("Yes.", "Yes.", 1, 1, CONFIG)
        self.assertEqual(len(score["normalized_ds"].split()), 1)

    def test_normalization(self):
        self.assertEqual(normalize("U. S. isn’t <00> here—now"), "us isnt here now")

    def card(self, index, text):
        return ThreeDSCard(str(index), "demo", 0, index, index, 0, index,
                           text, normalize(text), "review")

    def line(self, index, text):
        return PS2Line(index, "", text, normalize(text))

    def test_skip_3ds(self):
        path, _ = align([self.card(0, "Alpha."), self.card(1, "3DS only."),
                         self.card(2, "Omega.")],
                        [self.line(0, "Alpha."), self.line(1, "Omega.")], CONFIG)
        self.assertTrue(any(x.get("kind") == "3ds_only" for x in path))

    def test_skip_ps2(self):
        path, _ = align([self.card(0, "Alpha."), self.card(1, "Omega.")],
                        [self.line(0, "Alpha."), self.line(1, "PS2 only."),
                         self.line(2, "Omega.")], CONFIG)
        self.assertTrue(any(x.get("kind") == "ps2_only" for x in path))

    def test_monotonic(self):
        path, _ = align([self.card(0, "Alpha."), self.card(1, "Omega.")],
                        [self.line(0, "Alpha."), self.line(1, "Omega.")], CONFIG)
        points = [(x["ds_start"], x["ps2_start_index"]) for x in path if "final_score" in x]
        self.assertEqual(points, sorted(points))


if __name__ == "__main__":
    unittest.main()
