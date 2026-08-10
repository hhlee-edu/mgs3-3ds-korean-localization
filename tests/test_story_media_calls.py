from tools.mgs3d_story_media_calls import COMMAND_MARKERS, decode_tagged_argument


def test_decode_u24_immediate_matches_guest_little_endian_load():
    value = decode_tagged_argument(bytes.fromhex("06 c0 3b"), 0)
    assert value.value == 0x3BC006
    assert value.size == 3
    assert value.kind == "u24_immediate"


def test_decode_compact_constants():
    assert decode_tagged_argument(b"\xC0", 0).value == -1
    assert decode_tagged_argument(b"\xC1", 0).value == 0
    assert decode_tagged_argument(b"\xC4", 0).value == 3


def test_dynamic_form_remains_unresolved():
    value = decode_tagged_argument(b"\x90", 0)
    assert value.value is None
    assert value.kind == "dynamic_or_reference"


def test_confirmed_command_marker_families():
    assert COMMAND_MARKERS == (0x06, 0x64)
