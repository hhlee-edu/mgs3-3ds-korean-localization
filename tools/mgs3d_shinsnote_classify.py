#!/usr/bin/env python3
"""Reclassify the Shinsnote MGS3 script by dialogue-box background color.

Consumes the fine-grained ``shinsnote_mgs3_full.json`` scrape (one segment
per styled <span>, color-tagged codec/movie_demo/unknown) and reconstructs
paragraph-level dialogue lines the same way ``mgs3d_script_compare.py
extract-site`` does, but additionally tags each line with the game target
(``movie_demo`` / ``codec`` / ``unknown``) inferred from the nearest
ancestor element's ``background-color`` style. This replaces guessing the
movie/demo-vs-codec destination via anchor matching with the color coding
the original author used to mark cutscene (gray) vs radio (green) boxes.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_script_compare import SPEAKER, clean  # noqa: E402

RGB = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
HEX = re.compile(r"#([0-9a-fA-F]{6})\b")

# Observed reference colors from the source blog's box legend: gray boxes
# hold cutscene/event ("movie_demo") lines, green boxes hold radio
# ("codec") lines. Small tolerance absorbs the #ebebeb/#def7e5 hex
# equivalents seen alongside the rgb() forms.
MOVIE_DEMO_RGB = (235, 235, 235)
CODEC_RGB = (222, 247, 229)
# Tight on purpose: plain white (255,255,255) is only ~20/channel from the
# gray reference, and a loose per-channel tolerance made it (and the green
# reference) both register as "close enough" to gray, so gray always won.
TOLERANCE = 10


def parse_rgb(style_value: str) -> tuple[int, int, int] | None:
    match = RGB.search(style_value)
    if match:
        return tuple(int(part) for part in match.groups())  # type: ignore[return-value]
    match = HEX.search(style_value)
    if match:
        value = match.group(1)
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    return None


def distance(rgb: tuple[int, int, int], reference: tuple[int, int, int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(rgb, reference)) ** 0.5


def classify_color(style_value: str | None) -> str:
    if not style_value:
        return "unknown"
    rgb = parse_rgb(style_value)
    if rgb is None:
        return "unknown"
    candidates = {"movie_demo": MOVIE_DEMO_RGB, "codec": CODEC_RGB}
    best_label, best_distance = min(
        ((label, distance(rgb, reference)) for label, reference in candidates.items()),
        key=lambda item: item[1],
    )
    return best_label if best_distance <= TOLERANCE else "unknown"


def find_background(tag) -> str | None:
    node = tag
    while node is not None:
        style = node.get("style", "") if hasattr(node, "get") else ""
        if style and "background-color" in style:
            match = re.search(r"background-color\s*:\s*([^;]+)", style)
            if match:
                return match.group(1).strip()
        node = node.parent
    return None


def extract_page(article_html: str, page_number: int) -> list[dict[str, object]]:
    soup = BeautifulSoup(article_html, "html.parser")
    heading = next(
        (tag for tag in soup.find_all("h2") if "한글대사" in tag.get_text()), None
    )
    if heading is None:
        raise ValueError(f"script heading not found on page {page_number}")
    output: list[dict[str, object]] = []
    started = False
    sequence = 0
    for tag in soup.find_all(["h2", "h3", "h4", "p"]):
        if tag is heading:
            started = True
            continue
        if not started or tag.find_parent("blockquote") is not None:
            continue
        text = clean(tag.get_text(" ", strip=True))
        if not text:
            continue
        background = find_background(tag)
        target = classify_color(background)
        match = SPEAKER.match(text)
        if match and not re.search(r"\d", match.group(1)):
            kind = "dialogue"
            speaker, body = clean(match.group(1)), clean(match.group(2))
        elif text.startswith("(") and text.endswith(")"):
            kind, speaker, body = "stage", "", text
        elif tag.name in ("h3", "h4") or not re.search(r"[가-힣]", text):
            kind, speaker, body = "heading", "", text
        else:
            kind, speaker, body = "narration", "", text
        output.append({
            "page": page_number,
            "sequence": sequence,
            "kind": kind,
            "speaker": speaker,
            "text": body,
            "target": target,
            "background_color": background or "",
        })
        sequence += 1
    return output


def command_classify(args: argparse.Namespace) -> None:
    document = json.loads(args.full_scrape.read_text(encoding="utf-8-sig"))
    all_segments: list[dict[str, object]] = []
    for page in document["pages"]:
        all_segments.extend(extract_page(page["articleHtml"], int(page["part"])))
    dialogues = [item for item in all_segments if item["kind"] == "dialogue"]
    out_document = {
        "format": "shinsnote-mgs3-script-classified-v1",
        "source": document.get("metadata", {}).get("sourcePage", ""),
        "segment_count": len(all_segments),
        "dialogue_count": len(dialogues),
        "segments": all_segments,
    }
    args.output_json.write_text(
        json.dumps(out_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("page", "sequence", "kind", "speaker", "text", "target", "background_color"),
        )
        writer.writeheader()
        writer.writerows(all_segments)
    from collections import Counter
    target_counts = Counter(item["target"] for item in dialogues)
    print(f"extracted {len(all_segments)} segments, {len(dialogues)} dialogue lines")
    print(f"dialogue target breakdown: {dict(target_counts)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full_scrape", type=Path, help="shinsnote_mgs3_full.json")
    parser.add_argument("output_json", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.set_defaults(function=command_classify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.function(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
