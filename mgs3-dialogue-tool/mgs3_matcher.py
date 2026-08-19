#!/usr/bin/env python3
"""MGS3 broken Japanese dialogue matching helper.

The program builds a local searchable corpus from an English GameFAQs script
and the Korean script-reference pages, cleans control codes from extracted Japanese
records, and creates a review CSV. Translation and final semantic matching are
left to the reviewer/LLM because the three languages cannot be matched safely
with plain string similarity.
"""

from __future__ import annotations

import argparse
import csv
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import sys
import urllib.request


DEFAULT_ENGLISH_URL = (
    "https://gamefaqs.gamespot.com/ps2/914828-metal-gear-solid-3-snake-eater/"
    "faqs/34684"
)
# The Korean script-reference pages are not named here; pass --korean-json
# with a locally parsed file instead.
DEFAULT_KOREAN_URLS = []
CONTROL_CODE_RE = re.compile(r"<[^>]*>")
RECORD_RE = re.compile(r"(?ms)^\s*(\d+)\s*:\s*(.*?)(?=^\s*\d+\s*:|\Z)")
SPACE_RE = re.compile(r"[ \t\u00a0]+")


class RegionTextExtractor(HTMLParser):
    """Extract text from a <pre> or a div whose class contains a target name."""

    BLOCK_TAGS = {
        "p", "br", "div", "tr", "td", "li", "h1", "h2", "h3", "h4", "h5",
        "h6", "blockquote", "section", "article",
    }

    def __init__(self, mode: str) -> None:
        super().__init__(convert_charrefs=True)
        self.mode = mode
        self.active = False
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if not self.active:
            if self.mode == "pre" and tag == "pre":
                self.active, self.depth = True, 1
                return
            classes = (attrs_dict.get("class") or "").split()
            if self.mode == "contents_style" and "contents_style" in classes:
                self.active, self.depth = True, 1
                return
        else:
            self.depth += 1
            if tag in self.BLOCK_TAGS:
                self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.active and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self.active:
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        self.depth -= 1
        if self.depth == 0:
            self.active = False

    def handle_data(self, data: str) -> None:
        if self.active:
            self.parts.append(data)

    def text(self) -> str:
        return html.unescape("".join(self.parts))


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 MGS3-dialogue-research/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_region(page_html: str, mode: str) -> str:
    parser = RegionTextExtractor(mode)
    parser.feed(page_html)
    result = parser.text()
    if not result.strip():
        raise ValueError(f"HTML에서 {mode!r} 본문을 찾지 못했습니다.")
    return result


def normalized_lines(text: str) -> list[str]:
    result: list[str] = []
    previous = None
    for raw in text.replace("\r", "\n").splitlines():
        line = SPACE_RE.sub(" ", raw).strip()
        if not line or line == previous:
            continue
        result.append(line)
        previous = line
    return result


def init_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS corpus (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            part INTEGER,
            seq INTEGER NOT NULL,
            url TEXT NOT NULL,
            text TEXT NOT NULL,
            UNIQUE(source, part, seq)
        );
        CREATE INDEX IF NOT EXISTS corpus_source_part_seq
            ON corpus(source, part, seq);
        CREATE INDEX IF NOT EXISTS corpus_text
            ON corpus(text);
        """
    )
    return connection


def replace_part(
    connection: sqlite3.Connection,
    source: str,
    part: int | None,
    url: str,
    lines: list[str],
) -> None:
    if part is None:
        connection.execute("DELETE FROM corpus WHERE source=? AND part IS NULL", (source,))
    else:
        connection.execute("DELETE FROM corpus WHERE source=? AND part=?", (source, part))
    connection.executemany(
        "INSERT INTO corpus(source, part, seq, url, text) VALUES (?, ?, ?, ?, ?)",
        ((source, part, seq, url, line) for seq, line in enumerate(lines, start=1)),
    )


def korean_segments_by_part(segments: object) -> dict[int, list[str]]:
    if not isinstance(segments, list):
        raise ValueError("한글 JSON에 segments 배열이 없습니다.")
    parts: dict[int, list[str]] = {}
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        part = segment.get("page")
        segment_text = str(segment.get("text", "")).strip()
        if isinstance(part, int) and segment_text:
            speaker = str(segment.get("speaker", "")).strip()
            parts.setdefault(part, []).append(
                f"{speaker}: {segment_text}" if speaker else segment_text
            )
    return parts


def build_command(args: argparse.Namespace) -> int:
    db_path = Path(args.db).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = init_db(db_path)
    try:
        if not args.skip_english:
            if args.english_file:
                english_path = Path(args.english_file).resolve()
                english_raw = english_path.read_text(encoding="utf-8-sig")
                if "<pre" in english_raw.lower():
                    english_raw = extract_region(english_raw, "pre")
                english_origin = english_path.as_uri()
            else:
                try:
                    english_raw = extract_region(fetch(args.english_url), "pre")
                except OSError as exc:
                    raise OSError(
                        "GameFAQs가 자동 접속을 차단했습니다. 브라우저에서 FAQ를 "
                        "HTML 또는 TXT로 저장한 뒤 --english-file 경로를 지정하세요."
                    ) from exc
                english_origin = args.english_url
            english_lines = normalized_lines(english_raw)
            replace_part(connection, "english", None, english_origin, english_lines)
            print(f"영문 스크립트: {len(english_lines):,}줄")

        if not args.skip_korean and args.korean_json:
            korean_path = Path(args.korean_json).resolve()
            payload = json.loads(korean_path.read_text(encoding="utf-8-sig"))
            parts = korean_segments_by_part(payload.get("segments"))
            for part, lines in sorted(parts.items()):
                replace_part(connection, "korean", part, korean_path.as_uri(), lines)
                print(f"한글 {part:02d}편: {len(lines):,}줄")
        elif not args.skip_korean:
            for part, url in enumerate(DEFAULT_KOREAN_URLS, start=1):
                korean_html = fetch(url)
                korean_lines = normalized_lines(
                    extract_region(korean_html, "contents_style")
                )
                # Remove the common introduction/navigation area and footer notes.
                start = next(
                    (i for i, line in enumerate(korean_lines) if "현재글" in line),
                    -1,
                ) + 1
                body = korean_lines[start:] if start > 0 else korean_lines
                body = [line for line in body if not line.startswith("#")]
                replace_part(connection, "korean", part, url, body)
                print(f"한글 {part:02d}편: {len(body):,}줄")
        connection.commit()
    finally:
        connection.close()
    print(f"검색 DB 생성 완료: {db_path}")
    return 0


def search_rows(
    connection: sqlite3.Connection,
    query: str,
    source: str,
    part: int | None,
) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    clauses = ["text LIKE ?"]
    params: list[object] = [f"%{query}%"]
    if source != "all":
        clauses.append("source=?")
        params.append(source)
    if part is not None:
        clauses.append("part=?")
        params.append(part)
    sql = "SELECT * FROM corpus WHERE " + " AND ".join(clauses) + " ORDER BY source, part, seq"
    return list(connection.execute(sql, params))


def context_rows(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    context: int,
) -> list[sqlite3.Row]:
    part_clause = "part IS NULL" if row["part"] is None else "part=?"
    params: list[object] = [row["source"]]
    if row["part"] is not None:
        params.append(row["part"])
    params.extend([row["seq"] - context, row["seq"] + context])
    return list(
        connection.execute(
            f"SELECT * FROM corpus WHERE source=? AND {part_clause} "
            "AND seq BETWEEN ? AND ? ORDER BY seq",
            params,
        )
    )


def search_command(args: argparse.Namespace) -> int:
    connection = sqlite3.connect(Path(args.db).resolve())
    connection.row_factory = sqlite3.Row
    try:
        matches = search_rows(connection, args.query, args.source, args.part)
        if not matches:
            print("검색 결과가 없습니다.")
            return 1
        for match in matches[: args.limit]:
            part = "-" if match["part"] is None else str(match["part"])
            print(f"\n[{match['source']} part={part} seq={match['seq']}] {match['url']}")
            for row in context_rows(connection, match, args.context):
                marker = ">" if row["id"] == match["id"] else " "
                print(f"{marker} {row['seq']:04d}: {row['text']}")
    finally:
        connection.close()
    return 0


def clean_japanese(raw: str) -> str:
    clean = CONTROL_CODE_RE.sub("", raw)
    clean = clean.replace("|", " ")
    return SPACE_RE.sub(" ", clean).strip()


def parse_records(text: str) -> list[tuple[int, str, str]]:
    records = []
    for match in RECORD_RE.finditer(text):
        record_id = int(match.group(1))
        raw = " ".join(line.strip() for line in match.group(2).splitlines()).strip()
        records.append((record_id, raw, clean_japanese(raw)))
    return records


def batch_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    records = parse_records(input_path.read_text(encoding="utf-8-sig"))
    if not records:
        print("'번호: 대사' 형식의 레코드를 찾지 못했습니다.", file=sys.stderr)
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "record_id", "raw_japanese", "clean_japanese", "english_match",
                "korean_reference", "korean_translation", "confidence", "status",
                "notes",
            ],
        )
        writer.writeheader()
        for record_id, raw, clean in records:
            writer.writerow(
                {
                    "record_id": record_id,
                    "raw_japanese": raw,
                    "clean_japanese": clean,
                    "status": "pending",
                }
            )
    print(f"검토 CSV 생성: {output_path} ({len(records)}개 레코드)")
    return 0


def batch_game_json_command(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("게임 후보 JSON에 candidates 배열이 없습니다.")
    selected = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        gcx = item.get("gcx")
        resource = item.get("resource")
        if args.gcx is not None and gcx != args.gcx:
            continue
        if args.start is not None and (not isinstance(resource, int) or resource < args.start):
            continue
        if args.end is not None and (not isinstance(resource, int) or resource > args.end):
            continue
        selected.append(item)
    if not selected:
        print("선택 조건에 맞는 게임 대사가 없습니다.", file=sys.stderr)
        return 2
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "accept", "gcx", "resource", "game_preview", "raw_japanese", "clean_japanese",
            "english", "english_match", "korean", "korean_reference",
            "korean_translation", "confidence", "status", "notes",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in selected:
            raw = str(item.get("preview", ""))
            writer.writerow({
                "gcx": item.get("gcx", ""),
                "resource": item.get("resource", ""),
                "game_preview": raw,
                "raw_japanese": raw,
                "clean_japanese": clean_japanese(raw),
                "status": "pending",
            })
    print(f"게임 후보 검토 CSV 생성: {output_path} ({len(selected)}개 레코드)")
    return 0


def apply_anchor_evidence_command(args: argparse.Namespace) -> int:
    review_path = Path(args.review).resolve()
    evidence_path = Path(args.evidence).resolve()
    output_path = Path(args.output).resolve()
    with evidence_path.open(encoding="utf-8-sig", newline="") as stream:
        evidence_rows = list(csv.DictReader(stream))
    evidence = {
        (row.get("gcx", ""), row.get("resource", "")): row
        for row in evidence_rows
        if row.get("shared_anchors")
    }
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for name in ("shared_anchors", "english_sequence", "contradictions"):
        if name not in fieldnames:
            fieldnames.append(name)
    matched = usable = blocked = 0
    for row in rows:
        source = evidence.get((row.get("gcx", ""), row.get("resource", "")))
        if source is None:
            continue
        matched += 1
        row["shared_anchors"] = source.get("shared_anchors", "")
        row["english_sequence"] = source.get("english_sequence", "")
        row["english_match"] = source.get("english", "")
        row["english"] = source.get("english", "")
        row["korean_reference"] = source.get("korean_full", "")
        korean = source.get("korean", "").strip()
        contradiction = source.get("contradictions", "").strip()
        row["contradictions"] = contradiction
        if korean and not contradiction:
            row["korean_translation"] = korean
            row["korean"] = korean
            row["confidence"] = "high"
            row["status"] = "review"
            row["notes"] = "영문·한글 공통 앵커로 동일 문장 확인; 승인 전 검토"
            usable += 1
        else:
            row["confidence"] = "low"
            row["status"] = "blocked"
            row["notes"] = contradiction or "한글 문장 분리 근거 없음"
            blocked += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"앵커 근거 병합: {output_path} "
        f"(일치 {matched}, 번역 후보 {usable}, 차단 {blocked})"
    )
    return 0


def apply_curated_map_command(args: argparse.Namespace) -> int:
    review_path = Path(args.review).resolve()
    mapping_path = Path(args.mapping).resolve()
    output_path = Path(args.output).resolve()
    mappings = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
    if not isinstance(mappings, list):
        raise ValueError("매핑 JSON은 배열이어야 합니다.")
    keyed = {(str(m["gcx"]), str(m["resource"])): m for m in mappings}
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    applied = 0
    for row in rows:
        mapping = keyed.get((row.get("gcx", ""), row.get("resource", "")))
        if mapping is None:
            continue
        row["korean"] = str(mapping["korean"])
        row["korean_translation"] = str(mapping["korean"])
        row["korean_reference"] = str(mapping.get("korean_reference", ""))
        row["english"] = str(mapping.get("english", row.get("english", "")))
        row["english_match"] = row["english"]
        row["confidence"] = str(mapping.get("confidence", "medium"))
        row["status"] = "review"
        row["notes"] = str(mapping.get("notes", "주제·대화 순서·원문 의미 일치; 승인 전 검토"))
        row["contradictions"] = ""
        applied += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"선별 매핑 적용: {output_path} ({applied}개)")
    return 0


def propagate_exact_command(args: argparse.Namespace) -> int:
    paths = [Path(value).resolve() for value in args.files]
    tables = []
    translations: dict[str, set[str]] = {}
    evidence: dict[tuple[str, str], dict[str, str]] = {}
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        tables.append((path, fields, rows))
        for row in rows:
            raw = row.get("game_raw_text") or row.get("raw_text") or row.get("raw_japanese") or ""
            korean = (row.get("korean") or row.get("korean_translation") or "").strip()
            if raw and korean and not (row.get("contradictions") or "").strip():
                translations.setdefault(raw, set()).add(korean)
                evidence[(raw, korean)] = row
    safe = {raw: next(iter(values)) for raw, values in translations.items() if len(values) == 1}
    total = 0
    for path, fields, rows in tables:
        changed = 0
        for row in rows:
            if (row.get("korean") or row.get("korean_translation") or "").strip():
                continue
            raw = row.get("game_raw_text") or row.get("raw_text") or row.get("raw_japanese") or ""
            korean = safe.get(raw)
            if not korean:
                continue
            source = evidence[(raw, korean)]
            if "korean" in row:
                row["korean"] = korean
            if "korean_translation" in row:
                row["korean_translation"] = korean
            for name in ("english", "english_sequence", "korean_full"):
                if name in row and not row.get(name):
                    row[name] = source.get(name, "")
            if "confidence" in row and not row.get("confidence"):
                row["confidence"] = "exact-duplicate"
            if "status" in row:
                row["status"] = "review"
            if "notes" in row:
                row["notes"] = "동일 원문 바이트의 기존 번역을 자동 전파; 승인 전 검토"
            changed += 1
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        total += changed
        print(f"{path.name}: {changed}개 전파")
    print(f"동일 원문 번역 전파 합계: {total}개")
    return 0


def stats_command(args: argparse.Namespace) -> int:
    connection = sqlite3.connect(Path(args.db).resolve())
    try:
        rows = connection.execute(
            "SELECT source, COALESCE(part, 0), COUNT(*) FROM corpus "
            "GROUP BY source, part ORDER BY source, part"
        ).fetchall()
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    finally:
        connection.close()
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MGS3 대사 번역 자료 검색·검토 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="영문·한글 자료로 검색 DB 구축")
    build.add_argument("--db", default="mgs3_sources.sqlite3")
    build.add_argument("--english-url", default=DEFAULT_ENGLISH_URL)
    build.add_argument("--english-file", help="브라우저에서 저장한 GameFAQs HTML/TXT")
    build.add_argument("--korean-json", help="로컬 대사집 파싱 JSON")
    build.add_argument("--skip-english", action="store_true")
    build.add_argument("--skip-korean", action="store_true")
    build.set_defaults(func=build_command)

    search = sub.add_parser("search", help="DB에서 문구 검색 및 앞뒤 문맥 출력")
    search.add_argument("query")
    search.add_argument("--db", default="mgs3_sources.sqlite3")
    search.add_argument("--source", choices=["all", "english", "korean"], default="all")
    search.add_argument("--part", type=int)
    search.add_argument("--context", type=int, default=3)
    search.add_argument("--limit", type=int, default=10)
    search.set_defaults(func=search_command)

    batch = sub.add_parser("batch", help="일본어 덤프를 검토용 CSV로 변환")
    batch.add_argument("input")
    batch.add_argument("--output", default="translation_review.csv")
    batch.set_defaults(func=batch_command)

    batch_game = sub.add_parser("batch-game-json", help="게임 후보 JSON을 검토용 CSV로 변환")
    batch_game.add_argument("input")
    batch_game.add_argument("--output", default="translation_review.csv")
    batch_game.add_argument("--gcx", type=int)
    batch_game.add_argument("--start", type=int, help="최소 resource 번호")
    batch_game.add_argument("--end", type=int, help="최대 resource 번호")
    batch_game.set_defaults(func=batch_game_json_command)

    anchor = sub.add_parser("apply-anchor-evidence", help="검토 CSV에 검증된 앵커 근거 병합")
    anchor.add_argument("review")
    anchor.add_argument("evidence")
    anchor.add_argument("--output", default="translation_review_with_evidence.csv")
    anchor.set_defaults(func=apply_anchor_evidence_command)

    curated = sub.add_parser("apply-curated-map", help="검증한 GCX/resource 매핑 JSON 적용")
    curated.add_argument("review")
    curated.add_argument("mapping")
    curated.add_argument("--output", default="translation_review_curated.csv")
    curated.set_defaults(func=apply_curated_map_command)

    propagate = sub.add_parser("propagate-exact", help="여러 검토 CSV 사이의 동일 원문 번역 전파")
    propagate.add_argument("files", nargs="+")
    propagate.set_defaults(func=propagate_exact_command)

    stats = sub.add_parser("stats", help="DB 수록 현황 확인")
    stats.add_argument("--db", default="mgs3_sources.sqlite3")
    stats.set_defaults(func=stats_command)
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
