from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from extract_archives import parse_darc


DEFAULT_LINES = (
    "제2차 세계대전이 끝난 후,",
    "세계는 동서로 양분되었다.",
    "이로써 냉전이라 불리는 시대가 시작되었다.",
)


def morton(x: int, y: int) -> int:
    return ((x & 1) | ((y & 1) << 1) | ((x & 2) << 1) | ((y & 2) << 2)
            | ((x & 4) << 2) | ((y & 4) << 3))


def decode_a4_bclim(path: Path) -> Image.Image:
    data = path.read_bytes()
    if data[-40:-36] != b"CLIM" or data[-20:-16] != b"imag":
        raise ValueError("not a footer-header BCLIM")
    width, height, fmt, image_size = struct.unpack_from("<HHII", data, len(data) - 12)
    if fmt != 10 or image_size != len(data) - 40:
        raise ValueError("expected A4 BCLIM")
    storage_width = width
    image = Image.new("L", (storage_width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(storage_width):
            tile = (y // 8) * (storage_width // 8) + x // 8
            nibble = tile * 64 + morton(x & 7, y & 7)
            value = (data[nibble // 2] >> (4 * (nibble & 1))) & 15
            pixels[x, y] = value * 17
    return image


def encode_l4_bclim(template: bytes, image: Image.Image) -> bytes:
    width, height, fmt, image_size = struct.unpack_from("<HHII", template, len(template) - 12)
    if fmt != 10 or image.size != (width, height):
        raise ValueError(f"expected {width}x{height} L4 image")
    output = bytearray(template)
    pixels = image.convert("L").load()
    for y in range(height):
        for x in range(width):
            tile = (y // 8) * (width // 8) + x // 8
            nibble = tile * 64 + morton(x & 7, y & 7)
            value = (pixels[x, y] + 8) // 17
            shift = 4 * (nibble & 1)
            output[nibble // 2] = (output[nibble // 2] & (0xF0 >> shift)) | (value << shift)
    if len(output) - 40 != image_size:
        raise ValueError("BCLIM image-size mismatch")
    return bytes(output)


def render_native(size: tuple[int, int], font_path: Path, font_size: int) -> Image.Image:
    image = Image.new("L", size, 0)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), font_size)
    for line, y in zip(DEFAULT_LINES, (1, 22, 43)):
        box = draw.textbbox((0, 0), line, font=font)
        width = box[2] - box[0]
        draw.text(((image.width - width) // 2, y), line, font=font, fill=190)
    return image


def patch_hpk(source: Path, output: Path, font: Path, font_size: int) -> dict[str, object]:
    hpk = bytearray(source.read_bytes())
    target = None
    for offset in range(len(hpk) - 14):
        if hpk[offset:offset + 4].hex() != "309d745f":
            continue
        unpacked_size, packed_size = struct.unpack_from("<II", hpk, offset + 4)
        try:
            unpacked = zlib.decompress(hpk[offset + 12:offset + 12 + packed_size])
        except zlib.error:
            continue
        if len(unpacked) == unpacked_size and unpacked[:4] == b"darc":
            target = (offset, packed_size, unpacked)
            break
    if target is None:
        raise ValueError("verified 309d745f DARC entry not found")
    offset, old_packed_size, darc = target
    _, entries = parse_darc(darc)
    entry = next((item for item in entries if item.path == "timg/cold_war_text_eng_alp_ovl.bclim"), None)
    if entry is None:
        raise ValueError("Cold War BCLIM member not found")
    template = darc[entry.offset:entry.offset + entry.size]
    width, height = struct.unpack_from("<HH", template, len(template) - 12)
    native = render_native((width, height), font, font_size)
    replacement = encode_l4_bclim(template, native)
    patched_darc = bytearray(darc)
    patched_darc[entry.offset:entry.offset + entry.size] = replacement
    packed = zlib.compress(bytes(patched_darc), 9)
    if len(packed) > old_packed_size:
        raise ValueError(f"compressed entry grew: {len(packed)} > {old_packed_size}")
    struct.pack_into("<II", hpk, offset + 4, len(patched_darc), len(packed))
    start = offset + 12
    hpk[start:start + old_packed_size] = packed.ljust(old_packed_size, b"\0")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(hpk)
    return {
        "format": "mgs3d-opening-history-texture-v1",
        "source": str(source),
        "output": str(output),
        "hpk_entry_offset": offset,
        "old_packed_size": old_packed_size,
        "new_packed_size": len(packed),
        "member": entry.path,
        "dimensions": [width, height],
        "text": list(DEFAULT_LINES),
        "sha256": hashlib.sha256(hpk).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the opening Cold War history texture.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\malgun.ttf"))
    parser.add_argument("--size", type=int, default=12)
    parser.add_argument("--decode-bclim", action="store_true")
    parser.add_argument("--patch-hpk", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if args.patch_hpk:
        report = patch_hpk(args.source, args.output, args.font, args.size)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if args.decode_bclim:
        decode_a4_bclim(args.source).save(args.output)
        return
    source = Image.open(args.source).convert("RGBA")
    image = Image.new("RGBA", source.size, (0, 0, 0, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(args.font), args.size)
    color = (190, 188, 169, 255)
    y_positions = (2, 24, 46)

    for line, y in zip(DEFAULT_LINES, y_positions):
        box = draw.textbbox((0, 0), line, font=font)
        width = box[2] - box[0]
        draw.text(((image.width - width) // 2, y), line, font=font, fill=color)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)


if __name__ == "__main__":
    main()
