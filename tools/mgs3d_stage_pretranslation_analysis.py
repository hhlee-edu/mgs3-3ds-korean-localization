#!/usr/bin/env python3
"""Build non-translating analysis artifacts for the stage worklist.

All inputs are read-only.  This produces analysis CSV/JSON files only; it never
writes a master, scenerio.gcx, staging tree, build, or CCI.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10**9)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from mgs3d_codec_tool import GcxRecord  # noqa: E402
from mgs3d_gcx_font_tool import font_region, glyph_slot_owners  # noqa: E402
from mgs3d_stage_worklist_classify import classify  # noqa: E402
from mgs3d_stage_text_scan import stage_records  # noqa: E402

CTRL = re.compile(r"<[^>]+>|#\s*\{[^}]+\}#")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9'/-]*")
TAG = re.compile(r"<[^>]+>")
PS2 = {"I see him!!": "있다!!", "Who's that!": "누구냐!", "Speak!": "말해!"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def norm_case_punct(text: str) -> str:
    text = CTRL.sub(" ", text).lower()
    text = re.sub(r"\d+", "{n}", text)
    text = re.sub(r"[^a-z0-9{}]+", " ", text)
    return " ".join(text.split())


def norm_template(text: str) -> str:
    text = CTRL.sub(" ", text).lower()
    text = re.sub(r"\d+", "{n}", text)
    text = re.sub(r"\b(?:ak[- ]?47|c3|mk22|object|snake|eva|the boss|the end)\b", "{term}", text)
    text = re.sub(r"[^a-z0-9{}]+", " ", text)
    return " ".join(text.split())


def category(text: str, old: str, kind: str, stages: set[str], resources: set[int]) -> tuple[str, str]:
    if old != "OTHER":
        return old, "existing stage classifier"
    t = text.strip()
    u = t.upper()
    if re.match(r"^PERSONAL DATA\b", u):
        return "PERSONAL_DATA", "profile/status panel"
    if re.search(r"\b(?:SAVE|LOAD|SAVING|LOADING|MEMORY CARD|NO RESPONSE|READY TO SAVE)\b", u):
        return "SYSTEM_UI", "save/load/system prompt"
    if re.search(r"\b(?:MISSION|OPERATION)\b.*\b(?:COMPLETED|COMPLETE)\b", u):
        return "STATUS_MESSAGE", "mission completion/status message"
    if "/" in t and kind in {"label", "prose"} and len(t) < 80:
        return "MUSIC_TITLE", "title/artist-style slash pair; verify before translation"
    if re.search(r"\b(?:YES|NO|CANCEL|CONTINUE|BACK|RETURN|OK|SELECT|OPTION)\b", u) and len(t) < 80:
        return "SYSTEM_UI", "short system option"
    if kind == "label" and len(WORD.findall(t)) <= 2 and len(t) <= 32:
        return "SHORT_LABEL", "short label retained separately; meaning not guessed"
    return "OTHER", "no safe semantic rule"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worklist", type=Path, default=ROOT / "docs/evidence/2026-08-19-stage-translation-worklist/stage-translation-worklist.csv")
    ap.add_argument("--locations", type=Path, default=ROOT / "docs/evidence/2026-08-19-stage-text-scan/stage-text-locations.csv")
    ap.add_argument("--romfs", type=Path, default=ROOT / "experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs")
    ap.add_argument("--out", type=Path, default=ROOT / "docs/evidence/2026-08-19-stage-pretranslation-analysis")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    work = read_csv(args.worklist)
    locs = read_csv(args.locations)

    by_raw = defaultdict(list)
    for row in locs:
        by_raw[row["raw_hex"]].append(row)
    work_by_raw = {r["raw_hex"]: r for r in work}

    # Context examples and resource/capacity facts from every EN-resolved location.
    contexts = defaultdict(list)
    sequence = defaultdict(list)
    for row in locs:
        if row["raw_hex"] in work_by_raw and row["language"] == "english":
            sequence[(row["stage"], row["record"])].append(row)
    for seq in sequence.values():
        seq.sort(key=lambda r: int(r["resource"]))
        for i, row in enumerate(seq):
            before = seq[i - 1]["text"] if i else ""
            after = seq[i + 1]["text"] if i + 1 < len(seq) else ""
            contexts[row["raw_hex"]].append(
                f"{row['stage']}:{row['record']}:{row['resource']} | BEFORE={before} | AFTER={after}"
            )

    # Record facts are cached once per stage file/record.
    facts = {}
    for path in sorted(args.romfs.glob("stage/**/scenerio.gcx")):
        stage = path.parent.name
        for ri, record in enumerate(stage_records(path)):
            resources = record.resources()
            try:
                _, glyph_count = font_region(record)
                owners = glyph_slot_owners(resources, glyph_count)
                glyph_used = sum(bool(refs) for refs in owners)
                glyph_free = glyph_count - glyph_used
            except Exception:
                glyph_count = glyph_used = glyph_free = -1
            string_region = record.font_data_offset - record.string_resources_offset
            string_used = sum(len(r.data) for r in resources)
            facts[(stage, str(ri))] = {
                "string_region_bytes": string_region,
                "string_used_bytes": string_used,
                "record_slack_bytes": string_region - string_used,
                "glyph_slots": glyph_count,
                "glyph_used": glyph_used,
                "glyph_free": glyph_free,
            }

    # Exact current-master reuse candidates only.  No fuzzy matching is emitted.
    master_sources = []
    for name in ("codec", "movie", "demo"):
        p = ROOT / "translation/10_master/current" / f"{name}.csv"
        if not p.is_file():
            continue
        for row in read_csv(p):
            for field in ("english", "preview", "raw_text"):
                text = (row.get(field) or "").strip()
                korean = (row.get("korean") or "").strip()
                if text and korean:
                    master_sources.append((name, field, text, korean))
    exact = defaultdict(list)
    for name, field, text, korean in master_sources:
        exact[text].append((name, field, korean))

    # Groups are generated from visible EN.  Case/punctuation-only groups are
    # safe; number/term-template groups require context review.
    group_keys = defaultdict(list)
    template_keys = defaultdict(list)
    for r in work:
        group_keys[norm_case_punct(r["english"])].append(r)
        template_keys[norm_template(r["english"])].append(r)
    group_id_by_raw = {}
    group_rows = []
    gid = 0
    for key, members in sorted(group_keys.items()):
        if len(members) < 2:
            continue
        gid += 1
        group_id = f"TG-{gid:04d}"
        for m in members:
            group_id_by_raw[m["raw_hex"]] = group_id
        group_rows.append({
            "translation_group": group_id,
            "group_type": "CASE_PUNCT_SAFE",
            "safety": "SAFE_AUTO_REUSE",
            "normal_form": key,
            "member_count": len(members),
            "members": " || ".join(m["english"] for m in members),
        })
    for key, members in sorted(template_keys.items()):
        if len(members) < 2 or len({norm_case_punct(m["english"]) for m in members}) < 2:
            continue
        gid += 1
        group_id = f"TG-{gid:04d}"
        for m in members:
            group_id_by_raw.setdefault(m["raw_hex"], group_id)
        group_rows.append({
            "translation_group": group_id,
            "group_type": "NUMBER_TERM_TEMPLATE",
            "safety": "REVIEW_CONTEXT",
            "normal_form": key,
            "member_count": len(members),
            "members": " || ".join(m["english"] for m in members),
        })

    expanded = []
    risk_counts = Counter()
    category_counts = Counter()
    for r in work:
        raw = r["raw_hex"]
        loc_rows = by_raw[raw]
        cat, cat_basis = category(r["english"], r["category"], r["kind"], {x["stage"] for x in loc_rows}, {int(x["resource"]) for x in loc_rows})
        capacities = []
        record_slacks = []
        glyph_frees = []
        control = False
        for x in loc_rows:
            if x["language"] != "english":
                continue
            data = bytes.fromhex(raw)
            capacities.append(len(data))
            fact = facts.get((x["stage"], x["record"]), {})
            record_slacks.append(int(fact.get("record_slack_bytes", -1)))
            glyph_frees.append(int(fact.get("glyph_free", -1)))
            # High-byte values are ordinary encoded glyphs in this format.
            # Only the known escape/icon sequences are controls.
            control |= b"\x1f" in data or b"\xa0\x7b" in data or b"\xc0\x7d" in data
        if not capacities:
            capacities = [len(bytes.fromhex(raw))]
        min_cap, max_cap = min(capacities), max(capacities)
        min_slack = min(record_slacks) if record_slacks else -1
        min_glyph = min(glyph_frees) if glyph_frees else -1
        reasons = []
        if len(set(capacities)) > 1:
            reasons.append("capacity differs by location")
        if min_cap <= 12:
            reasons.append("small resource slot")
        if min_slack >= 0 and min_slack < 256:
            reasons.append("small record string slack")
        if min_glyph >= 0 and min_glyph < 16:
            reasons.append("small free glyph pool")
        if control:
            reasons.append("special/control bytes present")
        if int(r["occurrences"]) >= 100:
            reasons.append("high occurrence fan-out")
        risk = "HIGH" if len(reasons) >= 2 or min_cap <= 8 else "MEDIUM" if reasons else "LOW"
        risk_counts[risk] += 1
        category_counts[cat] += 1
        existing = exact.get(r["english"], [])
        expanded.append({
            **r,
            "category": cat,
            "category_basis": cat_basis,
            "translation_group": group_id_by_raw.get(raw, ""),
            "group_safety": next((g["safety"] for g in group_rows if g["translation_group"] == group_id_by_raw.get(raw)), ""),
            "context_examples": " || ".join(contexts[raw][:6]),
            "existing_translation_candidate": " || ".join(f"{a}:{b} => {c}" for a,b,c in existing),
            "capacity_min_bytes": min_cap,
            "capacity_max_bytes": max_cap,
            "current_used_bytes": min_cap,
            "available_bytes_fixed_layout": 0,
            "record_slack_min_bytes": min_slack,
            "glyph_free_min": min_glyph,
            "has_special_control": "YES" if control else "NO",
            "risk_level": risk,
            "risk_reason": " | ".join(reasons),
        })

    # Repeated glossary candidates: no Korean is invented. Existing references
    # are attached only for exact source text matches.
    token_occ = Counter()
    token_rows = defaultdict(set)
    for r in work:
        for token in WORD.findall(r["english"]):
            if len(token) >= 3:
                token_occ[token.lower()] += int(r["occurrences"])
                token_rows[token.lower()].add(r["id"])
    glossary = []
    for token, occ in token_occ.most_common():
        if len(token_rows[token]) < 3:
            continue
        rows_for_token = [r for r in work if r["id"] in token_rows[token]]
        cats = Counter(r["category"] for r in rows_for_token)
        refs = []
        for r in rows_for_token:
            refs.extend(exact.get(r["english"], []))
        glossary.append({
            "term": token,
            "occurrences": occ,
            "unique_rows": len(token_rows[token]),
            "category": cats.most_common(1)[0][0],
            "existing_reference": " || ".join(f"{a}:{b} => {c}" for a,b,c in refs[:8]),
        })

    fields = list(expanded[0].keys())
    with (args.out / "stage-worklist-expanded.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader(); w.writerows(expanded)
    with (args.out / "stage-translation-groups.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fields2 = ["translation_group", "group_type", "safety", "normal_form", "member_count", "members"]
        w = csv.DictWriter(fh, fieldnames=fields2, lineterminator="\r\n")
        w.writeheader(); w.writerows(group_rows)
    with (args.out / "stage-glossary-candidates.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fields3 = ["term", "occurrences", "unique_rows", "category", "existing_reference"]
        w = csv.DictWriter(fh, fieldnames=fields3, lineterminator="\r\n")
        w.writeheader(); w.writerows(glossary)
    candidate_rows = []
    for r in expanded:
        if r["existing_translation_candidate"]:
            candidate_rows.append({"id": r["id"], "english": r["english"], "candidate": r["existing_translation_candidate"], "evidence": "EXACT"})
    with (args.out / "stage-existing-translation-candidates.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "english", "candidate", "evidence"], lineterminator="\r\n")
        w.writeheader(); w.writerows(candidate_rows)

    summary = {
        "source_worklist_sha256": sha(args.worklist),
        "unique_rows": len(expanded),
        "occurrences": sum(int(r["occurrences"]) for r in expanded),
        "ready_rows": sum(r["status"] == "READY" for r in expanded),
        "new_translation_rows": sum(r["status"] != "READY" for r in expanded),
        "category_counts": dict(category_counts),
        "other_before": sum(r["category"] == "OTHER" for r in work),
        "other_after": category_counts["OTHER"],
        "translation_group_count": len(group_rows),
        "grouped_rows": sum(1 for r in expanded if r["translation_group"]),
        "safe_group_count": sum(g["safety"] == "SAFE_AUTO_REUSE" for g in group_rows),
        "review_group_count": sum(g["safety"] == "REVIEW_CONTEXT" for g in group_rows),
        "existing_exact_candidate_rows": len(candidate_rows),
        "glossary_candidate_count": len(glossary),
        "risk_counts": dict(risk_counts),
        "analysis_only": True,
        "translation_performed": False,
    }
    (args.out / "stage-pretranslation-analysis-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
