"""Rebuild the opening Cold War history card as a correct ETC1 BCLIM.

Supersedes the texture half of `mgs3d_history_texture.py`, which wrote raw
4-bit luminance nibbles into a format-10 member. Format 10 is ETC1
(block-compressed), so the GPU decoded those nibbles as compressed blocks and
rendered noise -- the 2026-08-14 "history card glyphs are all corrupted"
hardware defect. See `tools/mgs3d_bclim.py` for the format derivation and
`docs/evidence/2026-08-14-history-texture-corruption/`.

This tool renders the Korean lines into an RGB image that matches the pristine
English card's geometry and colour, encodes it with the verified ETC1 encoder,
and splices it back into the HPK entry -- reusing the *fixed* HPK packing rule
(header size field untouched, payload zero-padded to the original slot length).

    python tools/mgs3d_history_texture_v2.py <in cache.hpk> <out cache.hpk>
    python tools/mgs3d_history_texture_v2.py <in> <out> --preview out.png
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_archives import parse_darc                      # noqa: E402
import mgs3d_bclim as bclim                                   # noqa: E402

ENTRY_KEY = "309d745f"
MEMBER = "timg/cold_war_text_eng_alp_ovl.bclim"

DEFAULT_LINES = (
    "제2차 세계대전이 끝난 후,",
    "세계는 동서로 양분되었다.",
    "이로써 냉전이라 불리는 시대가 시작되었다.",
)
# Baselines measured from the decoded pristine English card (text occupies
# rows 5-14, 26-36, 48-58) and its dominant glyph colour.
LINE_TOPS = (4, 25, 47)
TEXT_RGB = (162, 162, 145)


def render_card(size: tuple[int, int], lines, font_path: Path, font_size: int) -> Image.Image:
    image = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), font_size)
    for text, top in zip(lines, LINE_TOPS):
        box = draw.textbbox((0, 0), text, font=font)
        width = box[2] - box[0]
        draw.text(((size[0] - width) // 2 - box[0], top), text, font=font, fill=TEXT_RGB)
    return image


def patch(source: Path, output: Path, font: Path, font_size: int,
          preview: Path | None) -> dict[str, object]:
    hpk = bytearray(source.read_bytes())

    target = None
    for offset in range(len(hpk) - 14):
        if hpk[offset:offset + 4].hex() != ENTRY_KEY:
            continue
        unpacked_size, packed_size = struct.unpack_from("<II", hpk, offset + 4)
        try:
            blob = zlib.decompress(hpk[offset + 12:offset + 12 + packed_size])
        except zlib.error:
            continue
        if len(blob) == unpacked_size and blob[:4] == b"darc":
            target = (offset, packed_size, blob)
            break
    if target is None:
        raise SystemExit("verified 309d745f DARC entry not found")
    offset, slot_size, darc = target

    _, entries = parse_darc(darc)
    entry = next((e for e in entries if e.path == MEMBER), None)
    if entry is None:
        raise SystemExit(f"{MEMBER} not found in DARC")

    original = darc[entry.offset:entry.offset + entry.size]
    width, height, fmt, _ = bclim.read_header(original)
    if fmt != bclim.FMT_ETC1:
        raise SystemExit(f"expected ETC1 (10), member reports format {fmt}")

    card = render_card((width, height), DEFAULT_LINES, font, font_size)
    if preview:
        card.save(preview)
    replacement = bclim.encode(original, card)
    if len(replacement) != len(original):
        raise SystemExit("encoded member changed size")

    patched = bytearray(darc)
    patched[entry.offset:entry.offset + entry.size] = replacement

    packed = zlib.compress(bytes(patched), 9)
    if len(packed) > slot_size:
        raise SystemExit(f"compressed entry grew: {len(packed)} > {slot_size}")

    # Same rule as tools/mgs3d_hpk_static_korean.py: pad the payload back to the
    # original slot length and LEAVE THE HEADER SIZE FIELD ALONE. Rewriting it
    # is what desynchronised the archive and caused the 2026-08-14 Data Abort.
    start = offset + 12
    hpk[start:start + slot_size] = packed.ljust(slot_size, b"\0")

    check_unpacked, check_packed = struct.unpack_from("<II", hpk, offset + 4)
    if (check_unpacked, check_packed) != (len(darc), slot_size):
        raise AssertionError("entry header changed; archive chain would desynchronise")
    if zlib.decompress(hpk[start:start + slot_size]) != bytes(patched):
        raise AssertionError("padded slot does not decompress back to the patched DARC")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(hpk)
    return {
        "format": "mgs3d-opening-history-texture-v3-etc1",
        "source": str(source),
        "output": str(output),
        "hpk_entry_offset": offset,
        "declared_packed_size": slot_size,
        "zlib_stream_size": len(packed),
        "slot_padding": slot_size - len(packed),
        "member": MEMBER,
        "member_format": "ETC1 (10)",
        "dimensions": [width, height],
        "text": list(DEFAULT_LINES),
        "sha256": hashlib.sha256(hpk).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\malgun.ttf"))
    ap.add_argument("--font-size", type=int, default=12)
    ap.add_argument("--preview", type=Path)
    args = ap.parse_args()
    info = patch(args.source, args.output, args.font, args.font_size, args.preview)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
