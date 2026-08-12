from tools.mgs3d_story_sequence_dp import align_segment, monotonic_anchor_run, similarity


def test_monotonic_dp_supports_one_script_to_multiple_cards():
    media = [{"english": "Spread your wings"}, {"english": "and fly"}]
    script = [{"english": "Spread your wings and fly"}]
    steps = align_segment(media, script)
    assert any(step[0] == "match" and step[3:5] == (2, 1) for step in steps)


def test_similarity_does_not_override_unrelated_story_position():
    assert similarity("Spread your wings", "Spread your wings and fly") > 0.7
    assert similarity("Spread your wings", "Nuclear launch detected") < 0.4


def test_anchor_expansion_keeps_longest_monotonic_run():
    anchors = [(10, 100), (20, 102), (30, 101), (40, 200), (50, 201)]
    assert monotonic_anchor_run(anchors) == [100, 102]
