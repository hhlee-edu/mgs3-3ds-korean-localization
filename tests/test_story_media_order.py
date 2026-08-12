from tools.mgs3d_story_media_order import canonical, hd_candidates, stage_key


def test_hd_alias_normalization_preserves_candidates():
    hd = {"demo": ["v020_010_p0", "m030_010_p010"]}
    assert hd_candidates("demo", "v020_010_p011", hd) == ["v020_010_p0"]
    assert hd_candidates("demo", "M030_010_P010_POLYDEMO", hd) == ["m030_010_p010"]


def test_story_stage_mission_order():
    assert stage_key("v006a_0") < stage_key("s000a_0") < stage_key("s201a_0")
    assert canonical("M030_010_P010_POLYDEMO") == "m030_010_p010"
