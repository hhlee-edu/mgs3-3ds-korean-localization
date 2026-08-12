from tools.mgs3d_story_movie_map import load_movie_names, media_position


def test_load_movie_namespace_only(tmp_path):
    path = tmp_path / "filelist.txt"
    path.write_text(
        "1\\tus\\movie\\_bp\\m010_020_m010.sdt\n"
        "2\\tus\\vox\\_bp\\m010_020_m010.sdt\n",
        encoding="utf-8",
    )
    assert load_movie_names(path) == ["m010_020_m010"]


def test_media_position_uses_story_prefix_and_sequence():
    assert media_position("m600_040_m030") == ("m600", 40)
    assert media_position("V080_010_P010_POLYDEMO") == ("v080", 10)
