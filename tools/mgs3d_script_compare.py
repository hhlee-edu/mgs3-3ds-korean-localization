#!/usr/bin/env python3
"""Extract the script reference MGS3 script and make a loose codec.dat comparison CSV."""

from __future__ import annotations

import argparse
from array import array
import csv
import hashlib
import html
import json
import math
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# The codec master legitimately carries very large cells -- `locations` lists every
# duplicate position of a string, and one `raw_text` reaches 551,512 characters.
# Python's 131,072-char default makes csv.reader raise on those rows, which
# silently blocked `make-translation` from ever seeing the edited master.
csv.field_size_limit(10 ** 9)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import TOKEN, decode_mgs_preview, parse_codec, render_bytes  # noqa: E402


SPACE = re.compile(r"\s+")
SPEAKER = re.compile(r"^([^:：]{1,24}?)\s*[:：]\s*(.+)$")
LATIN_NUMBER = re.compile(r"[A-Za-z][A-Za-z0-9.-]*|\d+(?:[.:/]\d+)*")
TOKEN = re.compile(r"<[^>]+>")
CODEC_METADATA = re.compile(r"^No:\d+/\d+\s+page:\d+\|", re.IGNORECASE)
ENGLISH_SPEAKER = re.compile(r"^([A-Za-z][A-Za-z .'-]{0,36}(?:\s*\([^)]*\))?):\s*(.+)$")

SPEAKER_ALIASES = {
    "소령": "zero", "제로": "zero", "zero": "zero", "tom": "zero", "major zero": "zero",
    "스네이크": "snake", "잭": "snake", "snake": "snake", "jack": "snake",
    "패러메딕": "paramedic", "para-medic": "paramedic", "para medic": "paramedic",
    "시긴토": "sigint", "sigint": "sigint", "에바": "eva", "eva": "eva",
    "더 보스": "boss", "보스": "boss", "the boss": "boss", "boss": "boss",
    "오셀롯": "ocelot", "ocelot": "ocelot", "소코로프": "sokolov", "sokolov": "sokolov",
    "볼긴": "volgin", "volgin": "volgin", "라이코프": "raikov", "raikov": "raikov",
    "파일럿": "pilot", "pilot": "pilot", "병사": "soldier", "soldier": "soldier",
}


def clean(text: str) -> str:
    return SPACE.sub(" ", html.unescape(text).replace("\xa0", " ")).strip()


def is_codec_metadata_preview(text: str) -> bool:
    plain = TOKEN.sub("", text).strip()
    return bool(
        CODEC_METADATA.match(plain)
        or "|radio_picture" in plain.lower()
        or re.fullmatch(r"[a-z0-9_./|:-]+", plain, re.IGNORECASE)
    )


def anchor_sentence_fragment(text: str, shared_anchors: str) -> str:
    """Return the smallest Korean sentence span containing every shared anchor."""
    wanted = {token.upper() for token in shared_anchors.split() if token}
    if not wanted:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    for sentence in sentences:
        present = {token.upper() for token in anchors(sentence)}
        if wanted <= present:
            return sentence
    return ""


def extract_page(path: Path, page: int) -> list[dict[str, object]]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    content = soup.select_one(".contents_style")
    if content is None:
        raise ValueError(f"article body not found: {path}")
    heading = next(
        (tag for tag in content.find_all("h2") if "한글대사" in tag.get_text()), None
    )
    if heading is None:
        raise ValueError(f"script heading not found: {path}")
    output: list[dict[str, object]] = []
    started = False
    sequence = 0
    for tag in content.find_all(["h2", "h3", "h4", "p"]):
        if tag is heading:
            started = True
            continue
        if not started or tag.find_parent("blockquote") is not None:
            continue
        text = clean(tag.get_text(" ", strip=True))
        if not text:
            continue
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
        output.append(
            {
                "page": page,
                "sequence": sequence,
                "kind": kind,
                "speaker": speaker,
                "text": body,
                "source_file": path.name,
            }
        )
        sequence += 1
    return output


def command_extract(args: argparse.Namespace) -> None:
    pages: list[dict[str, object]] = []
    for page in range(1, 21):
        matches = sorted(args.html_dir.glob(f"page_{page:02d}_*.html"))
        if len(matches) != 1:
            raise ValueError(f"expected one HTML file for page {page}, found {len(matches)}")
        pages.extend(extract_page(matches[0], page))
    dialogues = [item for item in pages if item["kind"] == "dialogue"]
    document = {
        "format": "script_ref-mgs3-script-v1",
        "source": "(reference site) through /238",
        "segment_count": len(pages),
        "dialogue_count": len(dialogues),
        "segments": pages,
    }
    args.output_json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("page", "sequence", "kind", "speaker", "text", "source_file")
        )
        writer.writeheader()
        writer.writerows(pages)
    print(f"extracted {len(pages)} segments ({len(dialogues)} speaker-labelled dialogues)")


def canonical_speaker(name: str) -> str:
    plain = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip().lower()
    return SPEAKER_ALIASES.get(plain, plain)


def command_extract_english(args: argparse.Namespace) -> None:
    lines = args.text.read_text(encoding="utf-8-sig").splitlines()
    starts = [i for i, line in enumerate(lines) if clean(line) == "2. Script - Virtuous Mission"]
    if not starts:
        raise ValueError("main script section not found")
    start = starts[-1]
    ends = [i for i, line in enumerate(lines[start + 1 :], start + 1) if clean(line) == "6. Credits and Copyright Notice"]
    end = ends[-1] if ends else len(lines)
    paragraphs: list[tuple[int, str]] = []
    current: list[str] = []
    first_line = 0
    for line_number, line in enumerate(lines[start + 1 : end], start + 2):
        stripped = clean(line)
        if not stripped:
            if current:
                paragraphs.append((first_line, " ".join(current)))
                current = []
            continue
        if not current:
            first_line = line_number
        current.append(stripped)
    if current:
        paragraphs.append((first_line, " ".join(current)))
    dialogues: list[dict[str, object]] = []
    for line_number, paragraph in paragraphs:
        match = ENGLISH_SPEAKER.match(paragraph)
        if not match:
            continue
        speaker, text = clean(match.group(1)), clean(match.group(2))
        dialogues.append(
            {
                "sequence": len(dialogues),
                "line": line_number,
                "speaker": speaker,
                "speaker_key": canonical_speaker(speaker),
                "text": text,
            }
        )
    document = {
        "format": "gamefaqs-mgs3-english-script-v1",
        "source_file": args.text.name,
        "dialogue_count": len(dialogues),
        "dialogues": dialogues,
    }
    args.output_json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=dialogues[0].keys())
        writer.writeheader()
        writer.writerows(dialogues)
    print(f"extracted {len(dialogues)} English speaker-labelled dialogues")


def bilingual_score(korean: dict[str, object], english: dict[str, object], expected: float, index: int, window: int) -> float:
    ks = canonical_speaker(str(korean["speaker"]))
    es = str(english["speaker_key"])
    speaker_cost = 0.0 if ks == es else 3.0
    kl, el = max(1, len(str(korean["text"]))), max(1, len(str(english["text"])))
    length_cost = abs(math.log((kl * 1.8) / el)) * 0.35
    shared = anchors(str(korean["text"])) & anchors(str(english["text"]))
    return speaker_cost + length_cost + abs(index - expected) / max(1, window) - len(shared) * 2.0


def command_align_bilingual(args: argparse.Namespace) -> None:
    korean_doc = json.loads(args.korean.read_text(encoding="utf-8"))
    korean = [item for item in korean_doc["segments"] if item["kind"] == "dialogue"]
    english = json.loads(args.english.read_text(encoding="utf-8"))["dialogues"]
    rows: list[dict[str, object]] = []
    for ki, item in enumerate(korean):
        expected = ki * (len(english) - 1) / max(1, len(korean) - 1)
        low = max(0, int(expected) - args.window)
        high = min(len(english), int(expected) + args.window + 1)
        choices = list(range(low, high))
        if not choices:
            continue
        same_speaker = [i for i in choices if canonical_speaker(str(item["speaker"])) == english[i]["speaker_key"]]
        pool = same_speaker or choices
        best = min(pool, key=lambda i: bilingual_score(item, english[i], expected, i, args.window))
        score = bilingual_score(item, english[best], expected, best, args.window)
        en = english[best]
        shared = anchors(str(item["text"])) & anchors(str(en["text"]))
        confidence = "high" if shared else ("medium" if canonical_speaker(str(item["speaker"])) == en["speaker_key"] and score < 1.0 else "low")
        rows.append(
            {
                "accept": "",
                "confidence": confidence,
                "page": item["page"],
                "korean_sequence": item["sequence"],
                "korean_speaker": item["speaker"],
                "korean": item["text"],
                "english_sequence": en["sequence"],
                "english_line": en["line"],
                "english_speaker": en["speaker"],
                "english": en["text"],
            }
        )
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"aligned {len(rows)} Korean/English dialogue pairs")


def command_align_bilingual_dp(args: argparse.Namespace) -> None:
    """Globally align dialogue while preventing many unrelated duplicate targets."""
    korean_doc = json.loads(args.korean.read_text(encoding="utf-8"))
    korean = [item for item in korean_doc["segments"] if item["kind"] == "dialogue"]
    english = json.loads(args.english.read_text(encoding="utf-8"))["dialogues"]
    n, m = len(korean), len(english)
    gap = args.gap_cost
    previous = array("f", (j * gap for j in range(m + 1)))
    directions = bytearray((n + 1) * (m + 1))
    directions[1:m + 1] = b"\x02" * m  # left: skip English

    for i, ko in enumerate(korean, 1):
        current = array("f", [i * gap])
        directions[i * (m + 1)] = 1  # up: skip Korean
        ks = canonical_speaker(str(ko["speaker"]))
        ka = anchors(str(ko["text"]))
        kl = max(1, len(str(ko["text"])))
        row_base = i * (m + 1)
        for j, en in enumerate(english, 1):
            same = ks == str(en["speaker_key"])
            shared = ka & anchors(str(en["text"]))
            el = max(1, len(str(en["text"])))
            match_cost = (
                previous[j - 1]
                + (-2.2 if same else 2.8)
                + abs(math.log((kl * 1.8) / el)) * 0.35
                - len(shared) * 5.0
            )
            up = previous[j] + gap
            left = current[j - 1] + gap
            if match_cost <= up and match_cost <= left:
                current.append(match_cost)
                directions[row_base + j] = 0
            elif up <= left:
                current.append(up)
                directions[row_base + j] = 1
            else:
                current.append(left)
                directions[row_base + j] = 2
        previous = current

    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i and j:
        direction = directions[i * (m + 1) + j]
        if direction == 0:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif direction == 1:
            i -= 1
        else:
            j -= 1
    pairs.reverse()

    rows: list[dict[str, object]] = []
    for ki, ei in pairs:
        item, en = korean[ki], english[ei]
        same = canonical_speaker(str(item["speaker"])) == en["speaker_key"]
        shared = anchors(str(item["text"])) & anchors(str(en["text"]))
        confidence = "high" if shared else ("medium" if same else "low")
        rows.append({
            "accept": "",
            "confidence": confidence,
            "page": item["page"],
            "korean_sequence": item["sequence"],
            "korean_speaker": item["speaker"],
            "korean": item["text"],
            "english_sequence": en["sequence"],
            "english_line": en["line"],
            "english_speaker": en["speaker"],
            "english": en["text"],
            "shared_anchors": " ".join(sorted(shared)),
        })
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"globally aligned {len(rows)} one-to-one Korean/English dialogue pairs")


def visible_length(preview: str) -> int:
    return len(TOKEN.sub("X", preview).replace("<END>", ""))


def game_candidates(codec: Path) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for gcx, record in enumerate(parse_codec(codec.read_bytes())):
        for resource_index, resource in enumerate(record.resources()):
            if resource.is_script or not resource.data or resource.data[-1] != 0:
                continue
            preview = decode_mgs_preview(resource.data)
            # Exclude plain internal identifiers while retaining actual Latin dialogue.
            has_encoded_text = any(
                byte in (0x81, 0x82, 0x83, 0x8C, 0x8D, 0x8E, 0x8F)
                for byte in resource.data
            )
            if not has_encoded_text and visible_length(preview) < 16:
                continue
            candidates.append(
                {
                    "gcx": gcx,
                    "resource": resource_index,
                    "preview": preview,
                    "raw_text": render_bytes(resource.data),
                    "length": visible_length(preview),
                }
            )
    return candidates


def command_game(args: argparse.Namespace) -> None:
    candidates = game_candidates(args.codec)
    args.output.write_text(
        json.dumps(
            {"format": "mgs3d-game-dialogue-candidates-v1", "candidates": candidates},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"exported {len(candidates)} game string candidates")


def anchors(text: str) -> set[str]:
    visible = TOKEN.sub(" ", text)
    return {token.upper() for token in LATIN_NUMBER.findall(visible) if len(token) > 1}


def match_score(source: str, candidate: dict[str, object], expected: float, index: int, span: int) -> float:
    source_length = max(1, len(source))
    target_length = max(1, int(candidate["length"]))
    length_cost = abs(math.log(source_length / target_length))
    position_cost = abs(index - expected) / max(1, span)
    source_anchors = anchors(source)
    target_anchors = anchors(str(candidate["preview"]))
    anchor_bonus = len(source_anchors & target_anchors) * 1.5
    return length_cost + position_cost * 0.7 - anchor_bonus


def command_compare(args: argparse.Namespace) -> None:
    source_doc = json.loads(args.script.read_text(encoding="utf-8"))
    source = [item for item in source_doc["segments"] if item["kind"] == "dialogue"]
    game_doc = json.loads(args.game.read_text(encoding="utf-8"))
    game = game_doc["candidates"]
    if not source or not game:
        raise ValueError("source dialogue or game candidate list is empty")
    rows: list[dict[str, object]] = []
    previous = -1
    for source_index, item in enumerate(source):
        expected = source_index * (len(game) - 1) / max(1, len(source) - 1)
        low = max(previous + 1, int(expected) - args.window)
        high = min(len(game), int(expected) + args.window + 1)
        if low >= high:
            low, high = min(previous + 1, len(game) - 1), len(game)
        best = min(
            range(low, high),
            key=lambda index: match_score(str(item["text"]), game[index], expected, index, args.window),
        )
        score = match_score(str(item["text"]), game[best], expected, best, args.window)
        previous = best
        candidate = game[best]
        confidence = "medium" if score < 0.55 else "low"
        if anchors(str(item["text"])) & anchors(str(candidate["preview"])):
            confidence = "high"
        rows.append(
            {
                "accept": "",
                "confidence": confidence,
                "page": item["page"],
                "source_sequence": item["sequence"],
                "speaker": item["speaker"],
                "korean": item["text"],
                "gcx": candidate["gcx"],
                "resource": candidate["resource"],
                "game_preview": candidate["preview"],
                "game_raw_text": candidate["raw_text"],
            }
        )
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} loose matches to {args.output}")
    print("review rule: set accept=y to use; leave blank or set n to skip")


def validate_accepted_review_row(
    row: dict[str, str], records: list[object] | None
) -> tuple[int, int]:
    key = (int(row["gcx"]), int(row["resource"]))
    if row.get("contradictions", "").strip():
        raise ValueError(
            f"accepted target has unresolved contradictions: GCX {key[0]}, resource {key[1]}"
        )
    expected_hash = row.get("game_raw_sha256", "").strip().lower()
    if expected_hash:
        if records is None:
            raise ValueError("review contains game_raw_sha256; provide --codec for provenance validation")
        try:
            raw = records[key[0]].resources()[key[1]].data  # type: ignore[attr-defined]
        except IndexError as exc:
            raise ValueError(f"accepted target is outside codec: GCX {key[0]}, resource {key[1]}") from exc
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError(f"raw game hash changed: GCX {key[0]}, resource {key[1]}")
    return key


def escape_stray_brackets(text: str) -> str:
    """Escape '<'/'>' that are not part of a well-formed <HH> control token
    (the render_bytes()/parse_rendered() notation), leaving already-valid
    tokens untouched. The `korean` review column stores final,
    control-code-annotated text -- see wiki/Translation.md -- so this must
    not re-derive line wrapping or re-escape tokens the reviewer already
    placed deliberately (that previously corrupted every accepted row's
    trailing <0A><00>; see docs/codec-review-csv-escaping-bug-2026-08-14.md)."""
    out: list[str] = []
    cursor = 0
    while cursor < len(text):
        match = TOKEN.match(text, cursor)
        if match:
            out.append(match.group(0))
            cursor = match.end()
            continue
        char = text[cursor]
        if char == "<":
            out.append("<3C>")
        elif char == ">":
            out.append("<3E>")
        else:
            out.append(char)
        cursor += 1
    return "".join(out)


def command_make_translation(args: argparse.Namespace) -> None:
    units: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    records = parse_codec(args.codec.read_bytes()) if args.codec else None
    with args.comparison.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("accept", "").strip().lower() not in ("y", "yes", "1", "ok"):
                continue
            key = validate_accepted_review_row(row, records)
            if key in seen:
                raise ValueError(f"duplicate accepted target: GCX {key[0]}, resource {key[1]}")
            seen.add(key)
            korean_plain = row["korean"].strip().translate(str.maketrans({
                "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...",
            }))
            korean = escape_stray_brackets(korean_plain)
            if not korean.endswith("<00>"):
                korean += "<00>"
            units.append(
                {
                    "gcx": key[0],
                    "resource": key[1],
                    "kind": "string",
                    "source_page": int(row.get("page") or row.get("korean_page") or 0),
                    "speaker": row.get("speaker") or row.get("korean_speaker", ""),
                    "text": korean,
                }
            )
    character_map: dict[str, str] = {}
    if args.character_map:
        character_map = json.loads(args.character_map.read_text(encoding="utf-8-sig"))["characters"]
    document = {
        "format": "mgs3d-codec-translation-v1",
        "character_map": character_map,
        "note": "Generated only from comparison rows explicitly marked accept=y.",
        "units": units,
    }
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(units)} accepted replacements to {args.output}")


def command_merge(args: argparse.Namespace) -> None:
    with args.bilingual.open(encoding="utf-8-sig", newline="") as stream:
        bilingual = list(csv.DictReader(stream))
    with args.game_comparison.open(encoding="utf-8-sig", newline="") as stream:
        game_rows = list(csv.DictReader(stream))
    game_index = {
        (row["page"], row["source_sequence"]): row for row in game_rows
    }
    rows: list[dict[str, object]] = []
    for row in bilingual:
        game = game_index.get((row["page"], row["korean_sequence"]), {})
        rows.append(
            {
                "accept": "",
                "bilingual_confidence": row["confidence"],
                "game_confidence": game.get("confidence", ""),
                "page": row["page"],
                "korean_sequence": row["korean_sequence"],
                "korean_speaker": row["korean_speaker"],
                "korean": row["korean"],
                "english_sequence": row["english_sequence"],
                "english_speaker": row["english_speaker"],
                "english": row["english"],
                "gcx": game.get("gcx", ""),
                "resource": game.get("resource", ""),
                "game_preview": game.get("game_preview", ""),
                "game_raw_text": game.get("game_raw_text", ""),
            }
        )
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"merged {len(rows)} Korean/English/game rows into {args.output}")


def command_align_dat(args: argparse.Namespace) -> None:
    english = json.loads(args.english.read_text(encoding="utf-8"))["dialogues"]
    dat_doc = json.loads(args.dat_candidates.read_text(encoding="utf-8"))
    # Heuristic DAT scans use ``candidates``; the structural movie/demo parser
    # emits the complete, patchable set as ``subtitles``.
    candidates = dat_doc.get("subtitles", dat_doc.get("candidates"))
    if candidates is None:
        raise ValueError("DAT document has neither subtitles nor candidates")
    anchor_index: dict[str, set[int]] = {}
    for index, item in enumerate(english):
        for token in anchors(str(item["text"])):
            if len(token) >= 3:
                anchor_index.setdefault(token, set()).add(index)
    rows: list[dict[str, object]] = []
    for ci, candidate in enumerate(candidates):
        expected = ci * (len(english) - 1) / max(1, len(candidates) - 1)
        candidate_anchors = {x for x in anchors(str(candidate["preview"])) if len(x) >= 3}
        anchored: set[int] = set()
        for token in candidate_anchors:
            anchored.update(anchor_index.get(token, set()))
        if anchored:
            pool = sorted(anchored)
        else:
            low = max(0, int(expected) - args.window)
            high = min(len(english), int(expected) + args.window + 1)
            pool = list(range(low, high))
        def score(index: int) -> float:
            en = english[index]
            shared = candidate_anchors & anchors(str(en["text"]))
            jl = max(1, int(candidate["size"]) // 2)
            el = max(1, len(str(en["text"])))
            return abs(math.log((jl * 1.8) / el)) + abs(index - expected) / max(1, args.window) - len(shared) * 2.0
        best = min(pool, key=score)
        en = english[best]
        shared = candidate_anchors & anchors(str(en["text"]))
        confidence = "high" if shared else ("medium" if score(best) < 0.75 else "low")
        rows.append(
            {
                "accept": "",
                "confidence": confidence,
                "dat": dat_doc.get("source", ""),
                "dat_index": candidate["index"],
                "record": candidate.get("record", ""),
                "entry": candidate.get("entry", ""),
                "offset": candidate["offset"],
                "japanese_preview": candidate["preview"],
                "english_sequence": en["sequence"],
                "english_line": en["line"],
                "english_speaker": en["speaker"],
                "english": en["text"],
                "shared_anchors": " ".join(sorted(shared)),
                "raw_text": candidate["raw_text"],
            }
        )
    # A movie/demo record is one local subtitle unit and commonly splits one
    # English transcript paragraph across several on-screen entries.  Strong
    # Latin/number anchors inside the same record therefore provide much better
    # context than the archive-wide position estimate.
    by_record: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        if row["record"] != "":
            by_record.setdefault(str(row["record"]), []).append(index)
    for indices in by_record.values():
        strong = [i for i in indices if rows[i]["confidence"] == "high"]
        for position in indices:
            if rows[position]["confidence"] == "high" or not strong:
                continue
            before = [i for i in strong if i < position]
            after = [i for i in strong if i > position]
            inferred: int | None = None
            if before and after:
                left, right = before[-1], after[0]
                le, re_ = int(rows[left]["english_sequence"]), int(rows[right]["english_sequence"])
                fraction = (position - left) / (right - left)
                inferred = round(le + (re_ - le) * fraction)
            elif strong:
                nearest = min(strong, key=lambda i: abs(i - position))
                if abs(nearest - position) <= 4:
                    inferred = int(rows[nearest]["english_sequence"])
            if inferred is None or not 0 <= inferred < len(english):
                continue
            en = english[inferred]
            rows[position].update({
                "confidence": "context",
                "english_sequence": en["sequence"],
                "english_line": en["line"],
                "english_speaker": en["speaker"],
                "english": en["text"],
            })
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"aligned {len(rows)} {dat_doc.get('source', 'DAT')} candidates to English")


def command_merge_dat_korean(args: argparse.Namespace) -> None:
    with args.bilingual.open(encoding="utf-8-sig", newline="") as stream:
        bilingual = list(csv.DictReader(stream))
    by_english: dict[str, list[dict[str, str]]] = {}
    for row in bilingual:
        by_english.setdefault(row["english_sequence"], []).append(row)
    with args.dat_alignment.open(encoding="utf-8-sig", newline="") as stream:
        dat_rows = list(csv.DictReader(stream))
    output: list[dict[str, object]] = []
    for dat in dat_rows:
        choices = by_english.get(dat["english_sequence"], [])
        if choices:
            def cost(row: dict[str, str]) -> tuple[int, int]:
                rank = {"high": 0, "medium": 1, "low": 2}.get(row["confidence"], 3)
                expected = max(1, len(dat["english"]))
                return rank, abs(len(row["korean"]) * 2 - expected)
            korean = min(choices, key=cost)
        else:
            korean = {}
        output.append(
            {
                "accept": "",
                "dat_confidence": dat["confidence"],
                "bilingual_confidence": korean.get("confidence", ""),
                "dat": dat["dat"],
                "dat_index": dat["dat_index"],
                "record": dat.get("record", ""),
                "entry": dat.get("entry", ""),
                "offset": dat["offset"],
                "japanese_preview": dat["japanese_preview"],
                "english_sequence": dat["english_sequence"],
                "english_speaker": dat["english_speaker"],
                "english": dat["english"],
                "korean_page": korean.get("page", ""),
                "korean_speaker": korean.get("korean_speaker", ""),
                "korean": korean.get("korean", ""),
                "korean_full": korean.get("korean", ""),
                "raw_text": dat["raw_text"],
            }
        )
    # Transcript paragraphs are frequently split over consecutive subtitle
    # entries.  Divide the Korean suggestion by word boundaries, weighted by
    # each Japanese entry's visible length, instead of duplicating the complete
    # paragraph on every card.
    cursor = 0
    while cursor < len(output):
        first = output[cursor]
        end = cursor + 1
        while (
            end < len(output)
            and output[end]["record"] == first["record"]
            and output[end]["english_sequence"] == first["english_sequence"]
            and output[end]["korean_full"] == first["korean_full"]
            and first["korean_full"]
        ):
            end += 1
        group = output[cursor:end]
        if len(group) > 1:
            words = str(first["korean_full"]).split()
            weights = [max(1, visible_length(str(row["japanese_preview"]))) for row in group]
            total_weight = sum(weights)
            boundaries = [0]
            for index in range(1, len(group)):
                target = round(sum(weights[:index]) / total_weight * len(words))
                boundaries.append(max(boundaries[-1], min(len(words), target)))
            boundaries.append(len(words))
            for index, row in enumerate(group):
                row["korean"] = " ".join(words[boundaries[index]:boundaries[index + 1]])
        cursor = end
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    matched = sum(bool(row["korean"]) for row in output)
    print(f"merged {len(output)} DAT rows; {matched} received Korean suggestions")


def command_approve_review(args: argparse.Namespace) -> None:
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    allowed_dat = {"high", "context"} if args.include_context else {"high"}
    accepted = 0
    for row in rows:
        approve = (
            bool(row.get("korean", "").strip())
            and row.get("bilingual_confidence") == "high"
            and row.get("dat_confidence") in allowed_dat
        )
        row["accept"] = "yes" if approve else ""
        accepted += int(approve)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"approved {accepted}/{len(rows)} conservative review rows")


def command_align_codec_anchors(args: argparse.Namespace) -> None:
    game = json.loads(args.game.read_text(encoding="utf-8"))["candidates"]
    english = json.loads(args.english.read_text(encoding="utf-8"))["dialogues"]
    with args.bilingual.open(encoding="utf-8-sig", newline="") as stream:
        bilingual_rows = list(csv.DictReader(stream))
    korean_by_english = {
        int(row["english_sequence"]): row
        for row in bilingual_rows if row["confidence"] == "high"
    }
    anchor_index: dict[str, set[int]] = {}
    for index, item in enumerate(english):
        for token in anchors(str(item["text"])):
            if len(token) >= 3:
                anchor_index.setdefault(token, set()).add(index)

    # Determine a match once per unique plaintext, then fan it back out to all
    # GCX copies because common radio resources are duplicated extensively.
    match_by_raw: dict[str, tuple[int, set[str], float, dict[str, str]]] = {}
    for candidate in game:
        raw = str(candidate["raw_text"])
        if raw in match_by_raw:
            continue
        preview = str(candidate["preview"])
        if is_codec_metadata_preview(preview):
            continue
        candidate_anchors = {x for x in anchors(preview) if len(x) >= 3}
        choices: set[int] = set()
        for token in candidate_anchors:
            choices.update(anchor_index.get(token, set()))
        scored = sorted(
            ((len(candidate_anchors & anchors(str(english[i]["text"]))), i,
              candidate_anchors & anchors(str(english[i]["text"]))) for i in choices),
            reverse=True,
        )
        if not scored or scored[0][0] < 2:
            continue
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            continue
        _, english_index, shared = scored[0]
        korean = korean_by_english.get(english_index)
        if not korean:
            continue
        ratio = visible_length(preview) / max(1, len(korean["korean"]))
        match_by_raw[raw] = (english_index, shared, ratio, korean)

    rows: list[dict[str, object]] = []
    for candidate in game:
        match = match_by_raw.get(str(candidate["raw_text"]))
        if not match:
            continue
        english_index, shared, ratio, korean = match
        en = english[english_index]
        has_unique_anchor = any(len(anchor_index.get(token, ())) == 1 for token in shared)
        conservative = (
            len(shared) >= 3
            and has_unique_anchor
            and 0.45 <= ratio <= 2.2
            and not str(candidate["preview"]).startswith("No:")
        )
        rows.append({
            "accept": "yes" if conservative else "",
            "confidence": "high" if conservative else "review",
            "page": korean["page"],
            "speaker": korean["korean_speaker"],
            "korean": korean["korean"],
            "english_sequence": en["sequence"],
            "english_speaker": en["speaker"],
            "english": en["text"],
            "shared_anchors": " ".join(sorted(shared)),
            "unique_anchor": "yes" if has_unique_anchor else "",
            "length_ratio": f"{ratio:.3f}",
            "gcx": candidate["gcx"],
            "resource": candidate["resource"],
            "game_preview": candidate["preview"],
            "game_raw_text": candidate["raw_text"],
        })
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    accepted = sum(row["accept"] == "yes" for row in rows)
    print(f"wrote {len(rows)} two-anchor codec targets; {accepted} conservatively approved")


def command_codec_context(args: argparse.Namespace) -> None:
    """Add same-GCX neighboring resources to a codec review table."""
    game = json.loads(args.game.read_text(encoding="utf-8"))["candidates"]
    with args.review.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames or []
    by_gcx: dict[int, list[dict[str, object]]] = {}
    duplicate_counts: dict[str, int] = {}
    for candidate in game:
        by_gcx.setdefault(int(candidate["gcx"]), []).append(candidate)
        raw = str(candidate["raw_text"])
        duplicate_counts[raw] = duplicate_counts.get(raw, 0) + 1
    for candidates in by_gcx.values():
        candidates.sort(key=lambda item: int(item["resource"]))

    output_rows = []
    for row in rows:
        gcx, resource = int(row["gcx"]), int(row["resource"])
        candidates = by_gcx.get(gcx, [])
        position = next((i for i, item in enumerate(candidates)
                         if int(item["resource"]) == resource), None)
        context = []
        if position is not None:
            start = max(0, position - args.radius)
            end = min(len(candidates), position + args.radius + 1)
            for index in range(start, end):
                item = candidates[index]
                marker = ">" if index == position else " "
                context.append(f"{marker} {item['resource']}: {item['preview']}")
        enriched = dict(row)
        full_korean = row.get("korean", "").strip()
        fragment = anchor_sentence_fragment(full_korean, row.get("shared_anchors", ""))
        enriched["korean_full"] = full_korean
        enriched["korean"] = fragment
        enriched["segmentation"] = "anchor-sentence" if fragment else "unsegmented"
        if not fragment:
            enriched["contradictions"] = "shared anchors could not isolate one Korean sentence"
        enriched["conversation_key"] = f"EN-{row.get('english_sequence', '')}"
        enriched["duplicate_count"] = duplicate_counts.get(row.get("game_raw_text", ""), 0)
        enriched["game_context"] = "\n".join(context)
        output_rows.append(enriched)
    extra = ("korean_full", "segmentation", "contradictions", "conversation_key", "duplicate_count", "game_context")
    output_fields = fields + [name for name in extra if name not in fields]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"wrote {len(output_rows)} codec review rows with +/-{args.radius} same-GCX context")


def command_export_codec_range(args: argparse.Namespace) -> None:
    """Export every resource in one GCX range for sequential conversation review."""
    records = parse_codec(args.codec.read_bytes())
    if not 0 <= args.gcx < len(records):
        raise ValueError(f"GCX out of range: {args.gcx}")
    resources = records[args.gcx].resources()
    start = max(0, args.start)
    end = len(resources) - 1 if args.end is None else min(args.end, len(resources) - 1)
    if start > end:
        raise ValueError(f"empty resource range: {start}..{end}")

    translations: dict[tuple[int, int], dict[str, object]] = {}
    if args.translation:
        document = json.loads(args.translation.read_text(encoding="utf-8"))
        translations = {
            (int(unit["gcx"]), int(unit["resource"])): unit
            for unit in document.get("units", [])
        }
    selected: set[int] = set()
    mandatory: set[int] = set()
    if args.capacity_plan:
        plan = json.loads(args.capacity_plan.read_text(encoding="utf-8"))
        if int(plan["gcx"]) != args.gcx:
            raise ValueError("capacity plan GCX does not match requested GCX")
        selected = {int(value) for value in plan.get("selected_resources", [])}
        mandatory = {int(value) for value in plan.get("mandatory_resources", [])}

    rows = []
    for resource_index in range(start, end + 1):
        resource = resources[resource_index]
        translation = translations.get((args.gcx, resource_index), {})
        rows.append({
            "accept": "",
            "gcx": args.gcx,
            "resource": resource_index,
            "kind": "script" if resource.is_script else "string",
            "original_size": len(resource.data),
            "mandatory": "yes" if resource_index in mandatory else "",
            "capacity_selected": "yes" if resource_index in selected else "",
            "speaker": translation.get("speaker", ""),
            "korean": translation.get("text", ""),
            "game_preview": decode_mgs_preview(resource.data),
            "game_raw_text": render_bytes(resource.data),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"exported GCX {args.gcx} resources {start}..{end}: {len(rows)} review rows")


def split_words_by_weights(text: str, weights: list[int]) -> list[str]:
    """Split one translation across consecutive resources without losing words."""
    if not weights:
        return []
    words = text.split()
    total = max(1, sum(weights))
    boundaries = [0]
    running = 0
    for weight in weights[:-1]:
        running += weight
        boundaries.append(max(boundaries[-1], min(len(words), round(running / total * len(words)))))
    boundaries.append(len(words))
    return [" ".join(words[boundaries[i]:boundaries[i + 1]]) for i in range(len(weights))]


def sequence_map_indices(game_weights: list[int], transcript_weights: list[int]) -> list[int]:
    """Map ordered game resources to ordered transcript rows by cumulative length."""
    if not game_weights or not transcript_weights:
        return []
    game_total = max(1, sum(game_weights))
    transcript_total = max(1, sum(transcript_weights))
    ends = []
    running = 0
    for weight in transcript_weights:
        running += weight
        ends.append(running / transcript_total)
    result = []
    running = 0
    transcript_index = 0
    for weight in game_weights:
        midpoint = (running + weight / 2) / game_total
        running += weight
        while transcript_index + 1 < len(ends) and midpoint > ends[transcript_index]:
            transcript_index += 1
        result.append(transcript_index)
    return result


def command_batch_map_codec(args: argparse.Namespace) -> None:
    """Map one ordered GCX range to one ordered whole-transcript range."""
    records = parse_codec(args.codec.read_bytes())
    if not 0 <= args.gcx < len(records):
        raise ValueError(f"GCX out of range: {args.gcx}")
    resources = records[args.gcx].resources()
    start = max(0, args.start)
    end = min(args.end, len(resources) - 1)
    if start > end:
        raise ValueError(f"empty resource range: {start}..{end}")

    with args.bilingual.open(encoding="utf-8-sig", newline="") as stream:
        source = list(csv.DictReader(stream))
    transcript = [
        row for row in source
        if row.get("korean", "").strip()
        and args.english_start <= int(row["english_sequence"]) <= args.english_end
    ]
    transcript.sort(key=lambda row: int(row["english_sequence"]))
    if not transcript:
        raise ValueError("no Korean/English transcript rows in requested sequence range")

    game = [(index, resources[index]) for index in range(start, end + 1)
            if not resources[index].is_script]
    if not game:
        raise ValueError("requested range contains no string resources")
    game_weights = [max(1, visible_length(decode_mgs_preview(resource.data))) for _, resource in game]
    transcript_weights = [max(1, len(row.get("english", ""))) for row in transcript]
    assignments = sequence_map_indices(game_weights, transcript_weights)

    # Split each complete Korean paragraph over every game resource assigned to it.
    korean_parts: dict[int, list[str]] = {}
    for transcript_index in sorted(set(assignments)):
        positions = [i for i, value in enumerate(assignments) if value == transcript_index]
        weights = [game_weights[i] for i in positions]
        korean_parts[transcript_index] = split_words_by_weights(
            transcript[transcript_index].get("korean", ""), weights)

    used_in_group: dict[int, int] = {}
    rows = []
    for position, ((resource_index, resource), transcript_index) in enumerate(zip(game, assignments)):
        source_row = transcript[transcript_index]
        part_index = used_in_group.get(transcript_index, 0)
        used_in_group[transcript_index] = part_index + 1
        preview = decode_mgs_preview(resource.data)
        shared = anchors(preview) & anchors(source_row.get("english", ""))
        confidence = "anchor" if len(shared) >= 2 else "sequence"
        contradictions = []
        if anchors(preview) and not shared:
            contradictions.append("game anchors disagree with assigned English row")
        rows.append({
            "accept": "",
            "confidence": confidence,
            "conversation_key": f"GCX-{args.gcx}:{start}-{end}/EN-{args.english_start}-{args.english_end}",
            "gcx": args.gcx,
            "resource": resource_index,
            "game_raw_sha256": hashlib.sha256(resource.data).hexdigest(),
            "game_preview": preview,
            "english_sequence": source_row.get("english_sequence", ""),
            "english_speaker": source_row.get("english_speaker", ""),
            "english": source_row.get("english", ""),
            "korean_page": source_row.get("page", ""),
            "korean_sequence": source_row.get("korean_sequence", ""),
            "korean_speaker": source_row.get("korean_speaker", ""),
            "korean": korean_parts[transcript_index][part_index],
            "korean_full": source_row.get("korean", ""),
            "shared_anchors": " ".join(sorted(shared)),
            "contradictions": "; ".join(contradictions),
            "game_raw_text": render_bytes(resource.data),
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    covered = len(set(assignments))
    print(f"batch-mapped {len(rows)} GCX resources to {covered}/{len(transcript)} transcript rows; review required")


def command_expand_codec_anchors(args: argparse.Namespace) -> None:
    """Retired: adjacency in a GCX resource bank does not establish one conversation."""
    raise ValueError(
        "expand-codec-anchors is retired: fixed-radius neighbors can be metadata or unrelated dialogue; "
        "use align-codec-anchors followed by codec-context"
    )
    # Kept below temporarily for forensic comparison with rejected v1 artifacts.
    records = parse_codec(args.codec.read_bytes())
    with args.anchors.open(encoding="utf-8-sig", newline="") as stream:
        seeds = list(csv.DictReader(stream))
    if args.gcx is not None:
        seeds = [row for row in seeds if int(row["gcx"]) == args.gcx]
    if args.start is not None:
        seeds = [row for row in seeds if int(row["resource"]) >= args.start]
    if args.end is not None:
        seeds = [row for row in seeds if int(row["resource"]) <= args.end]
    grouped: dict[tuple[int, int], list[dict[str, str]]] = {}
    for row in seeds:
        if is_codec_metadata_preview(row.get("game_preview", "")):
            continue
        if not row.get("korean", "").strip() or not row.get("english_sequence", "").strip():
            continue
        grouped.setdefault((int(row["gcx"]), int(row["english_sequence"])), []).append(row)
    if not grouped:
        raise ValueError("no anchored Korean mappings to expand")

    proposals: dict[tuple[int, int], list[tuple[int, int]]] = {}
    group_ranges: dict[tuple[int, int], tuple[int, int]] = {}
    for key, group in grouped.items():
        gcx, _ = key
        if not 0 <= gcx < len(records):
            continue
        resources = records[gcx].resources()
        seed_resources = [int(row["resource"]) for row in group]
        low_limit = 0 if args.start is None else args.start
        high_limit = len(resources) - 1 if args.end is None else args.end
        low = max(low_limit, min(seed_resources) - args.radius)
        high = min(high_limit, max(seed_resources) + args.radius)
        group_ranges[key] = (low, high)
        for resource in range(low, high + 1):
            preview = decode_mgs_preview(resources[resource].data)
            if not resources[resource].is_script and not is_codec_metadata_preview(preview):
                proposals.setdefault((gcx, resource), []).append(key)

    output = []
    for key in sorted(grouped):
        gcx, english_sequence = key
        low, high = group_ranges[key]
        resources = records[gcx].resources()
        targets = [
            index for index in range(low, high + 1)
            if not resources[index].is_script
            and not is_codec_metadata_preview(decode_mgs_preview(resources[index].data))
        ]
        source = grouped[key][0]
        parts = split_words_by_weights(
            source["korean"],
            [max(1, visible_length(decode_mgs_preview(resources[index].data))) for index in targets],
        )
        seed_resources = {int(row["resource"]) for row in grouped[key]}
        for resource_index, korean in zip(targets, parts):
            resource = resources[resource_index]
            owners = proposals[(gcx, resource_index)]
            contradictions = []
            if len(owners) > 1:
                labels = ", ".join(f"EN-{owner[1]}" for owner in owners)
                contradictions.append(f"overlapping anchor groups: {labels}")
            output.append({
                "accept": "",
                "confidence": "anchor-seed" if resource_index in seed_resources else "anchor-context",
                "conversation_key": f"GCX-{gcx}/EN-{english_sequence}",
                "gcx": gcx,
                "resource": resource_index,
                "group_start": low,
                "group_end": high,
                "game_raw_sha256": hashlib.sha256(resource.data).hexdigest(),
                "game_preview": decode_mgs_preview(resource.data),
                "english_sequence": source.get("english_sequence", ""),
                "english_speaker": source.get("english_speaker", ""),
                "english": source.get("english", ""),
                "korean_page": source.get("page", ""),
                "korean_speaker": source.get("speaker", source.get("korean_speaker", "")),
                "korean": korean,
                "korean_full": source.get("korean", ""),
                "anchor_resources": " ".join(str(value) for value in sorted(seed_resources)),
                "shared_anchors": source.get("shared_anchors", ""),
                "contradictions": "; ".join(contradictions),
                "game_raw_text": render_bytes(resource.data),
            })
    duplicate_counts: dict[tuple[str, str, str], int] = {}
    for row in output:
        duplicate_key = (
            str(row["english_sequence"]), str(row["game_raw_sha256"]), str(row["korean"])
        )
        duplicate_counts[duplicate_key] = duplicate_counts.get(duplicate_key, 0) + 1
    for row in output:
        duplicate_key = (
            str(row["english_sequence"]), str(row["game_raw_sha256"]), str(row["korean"])
        )
        row["duplicate_mapping_count"] = duplicate_counts[duplicate_key]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)
    conflicts = sum(bool(row["contradictions"]) for row in output)
    print(f"expanded {len(grouped)} anchor groups to {len(output)} rows; {conflicts} overlapping rows require review")


def propagate_duplicate_approvals(rows: list[dict[str, str]]) -> int:
    """Propagate explicit approval only to byte- and translation-identical copies."""
    approved_keys = {
        (row.get("english_sequence", ""), row.get("game_raw_sha256", ""), row.get("korean", ""))
        for row in rows
        if row.get("accept", "").strip().lower() in ("y", "yes", "1", "ok")
        and not row.get("contradictions", "").strip()
        and row.get("game_raw_sha256", "").strip()
    }
    changed = 0
    for row in rows:
        key = (row.get("english_sequence", ""), row.get("game_raw_sha256", ""), row.get("korean", ""))
        if key in approved_keys and not row.get("contradictions", "").strip():
            if row.get("accept", "").strip().lower() not in ("y", "yes", "1", "ok"):
                row["accept"] = "yes"
                changed += 1
    return changed


def command_propagate_codec_approvals(args: argparse.Namespace) -> None:
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames or []
    if not rows:
        raise ValueError("empty codec review table")
    changed = propagate_duplicate_approvals(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    accepted = sum(row.get("accept", "").strip().lower() in ("y", "yes", "1", "ok") for row in rows)
    print(f"propagated {changed} duplicate approvals; {accepted}/{len(rows)} rows accepted")


def command_apply_review_corrections(args: argparse.Namespace) -> None:
    """Apply explicit offset-keyed semantic corrections without rewriting raw provenance."""
    with args.input.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames or []
    document = json.loads(args.corrections.read_text(encoding="utf-8"))
    corrections = {str(item["offset"]): item for item in document.get("corrections", [])}
    found: set[str] = set()
    for row in rows:
        correction = corrections.get(row.get("offset", ""))
        if not correction:
            continue
        found.add(row["offset"])
        if args.accept_corrected:
            row["accept"] = "yes"
        for field, value in correction.items():
            if field != "offset":
                if field not in fields:
                    raise ValueError(f"correction field not present in CSV: {field}")
                row[field] = str(value)
    missing = set(corrections) - found
    if missing:
        raise ValueError(f"correction offsets not found: {', '.join(sorted(missing))}")
    if args.corrected_only:
        rows = [row for row in rows if row.get("offset", "") in found]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"applied {len(found)} semantic corrections: {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract-site")
    extract.add_argument("html_dir", type=Path)
    extract.add_argument("output_json", type=Path)
    extract.add_argument("output_csv", type=Path)
    extract.set_defaults(function=command_extract)
    english = commands.add_parser("extract-english")
    english.add_argument("text", type=Path)
    english.add_argument("output_json", type=Path)
    english.add_argument("output_csv", type=Path)
    english.set_defaults(function=command_extract_english)
    bilingual = commands.add_parser("align-bilingual")
    bilingual.add_argument("korean", type=Path)
    bilingual.add_argument("english", type=Path)
    bilingual.add_argument("output", type=Path)
    bilingual.add_argument("--window", type=int, default=120)
    bilingual.set_defaults(function=command_align_bilingual)
    bilingual_dp = commands.add_parser("align-bilingual-dp")
    bilingual_dp.add_argument("korean", type=Path)
    bilingual_dp.add_argument("english", type=Path)
    bilingual_dp.add_argument("output", type=Path)
    bilingual_dp.add_argument("--gap-cost", type=float, default=0.65)
    bilingual_dp.set_defaults(function=command_align_bilingual_dp)
    game = commands.add_parser("export-game")
    game.add_argument("codec", type=Path)
    game.add_argument("output", type=Path)
    game.set_defaults(function=command_game)
    compare = commands.add_parser("compare")
    compare.add_argument("script", type=Path)
    compare.add_argument("game", type=Path)
    compare.add_argument("output", type=Path)
    compare.add_argument("--window", type=int, default=250)
    compare.set_defaults(function=command_compare)
    make = commands.add_parser("make-translation")
    make.add_argument("comparison", type=Path)
    make.add_argument("output", type=Path)
    make.add_argument("--codec", type=Path, help="validate accepted raw-resource hashes against this codec")
    make.add_argument("--character-map", type=Path,
                       help="global-page character-map.json; embeds its \"characters\" "
                            "map as the translation document's character_map so "
                            "build-korean encodes Hangul via the resident global page "
                            "instead of appending new per-GCX glyphs")
    make.set_defaults(function=command_make_translation)
    merge = commands.add_parser("merge-comparison")
    merge.add_argument("bilingual", type=Path)
    merge.add_argument("game_comparison", type=Path)
    merge.add_argument("output", type=Path)
    merge.set_defaults(function=command_merge)
    dat_align = commands.add_parser("align-dat")
    dat_align.add_argument("english", type=Path)
    dat_align.add_argument("dat_candidates", type=Path)
    dat_align.add_argument("output", type=Path)
    dat_align.add_argument("--window", type=int, default=180)
    dat_align.set_defaults(function=command_align_dat)
    dat_merge = commands.add_parser("merge-dat-korean")
    dat_merge.add_argument("bilingual", type=Path)
    dat_merge.add_argument("dat_alignment", type=Path)
    dat_merge.add_argument("output", type=Path)
    dat_merge.set_defaults(function=command_merge_dat_korean)
    approve = commands.add_parser("approve-review")
    approve.add_argument("input", type=Path)
    approve.add_argument("output", type=Path)
    approve.add_argument("--include-context", action="store_true")
    approve.set_defaults(function=command_approve_review)
    codec_anchor = commands.add_parser("align-codec-anchors")
    codec_anchor.add_argument("game", type=Path)
    codec_anchor.add_argument("english", type=Path)
    codec_anchor.add_argument("bilingual", type=Path)
    codec_anchor.add_argument("output", type=Path)
    codec_anchor.set_defaults(function=command_align_codec_anchors)
    codec_context = commands.add_parser("codec-context", help="add same-GCX neighbors to codec review CSV")
    codec_context.add_argument("game", type=Path)
    codec_context.add_argument("review", type=Path)
    codec_context.add_argument("output", type=Path)
    codec_context.add_argument("--radius", type=int, default=3)
    codec_context.set_defaults(function=command_codec_context)
    codec_range = commands.add_parser("export-codec-range", help="export a sequential GCX resource range")
    codec_range.add_argument("codec", type=Path)
    codec_range.add_argument("output", type=Path)
    codec_range.add_argument("--gcx", type=int, required=True)
    codec_range.add_argument("--start", type=int, default=0)
    codec_range.add_argument("--end", type=int)
    codec_range.add_argument("--translation", type=Path)
    codec_range.add_argument("--capacity-plan", type=Path)
    codec_range.set_defaults(function=command_export_codec_range)
    batch_codec = commands.add_parser(
        "batch-map-codec", help="map an ordered GCX range to an ordered Korean/English transcript range")
    batch_codec.add_argument("codec", type=Path)
    batch_codec.add_argument("bilingual", type=Path)
    batch_codec.add_argument("output", type=Path)
    batch_codec.add_argument("--gcx", type=int, required=True)
    batch_codec.add_argument("--start", type=int, required=True)
    batch_codec.add_argument("--end", type=int, required=True)
    batch_codec.add_argument("--english-start", type=int, required=True)
    batch_codec.add_argument("--english-end", type=int, required=True)
    batch_codec.set_defaults(function=command_batch_map_codec)
    expand_codec = commands.add_parser(
        "expand-codec-anchors", help="RETIRED unsafe fixed-radius experiment")
    expand_codec.add_argument("codec", type=Path)
    expand_codec.add_argument("anchors", type=Path)
    expand_codec.add_argument("output", type=Path)
    expand_codec.add_argument("--gcx", type=int)
    expand_codec.add_argument("--start", type=int)
    expand_codec.add_argument("--end", type=int)
    expand_codec.add_argument("--radius", type=int, default=8)
    expand_codec.set_defaults(function=command_expand_codec_anchors)
    propagate = commands.add_parser(
        "propagate-codec-approvals", help="copy approvals to byte- and translation-identical GCX duplicates")
    propagate.add_argument("input", type=Path)
    propagate.add_argument("output", type=Path)
    propagate.set_defaults(function=command_propagate_codec_approvals)
    corrections = commands.add_parser(
        "apply-review-corrections", help="apply explicit offset-keyed corrections to a review CSV")
    corrections.add_argument("input", type=Path)
    corrections.add_argument("corrections", type=Path)
    corrections.add_argument("output", type=Path)
    corrections.add_argument(
        "--accept-corrected", action="store_true",
        help="mark corrected offsets accepted for an explicit capacity probe")
    corrections.add_argument(
        "--corrected-only", action="store_true",
        help="write only corrected rows for focused human review")
    corrections.set_defaults(function=command_apply_review_corrections)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.function(args)
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
