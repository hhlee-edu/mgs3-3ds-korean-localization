#!/usr/bin/env python3
"""Match 3DS codec English rows to the Metal Gear Wiki MGS3 radio transcripts.

The script deliberately treats fuzzy matches as review candidates only.  It never
infers a speaker from Korean grammar or from a guessed character voice.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

URL = "https://metalgear.fandom.com/api.php?action=parse&page=Metal_Gear_Solid_3_radio_conversations&prop=wikitext&format=json"
SHORT_WORDS = {"yes", "no", "yeah", "yup", "yep", "what", "huh", "ok", "okay", "...", "?"}


def clean_markup(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.I | re.S)
    s = re.sub(r"\[\[([^\]|]+)\|([^]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^]]+)\]\]", r"\1", s)
    s = re.sub(r"\[https?://[^ ]+ ([^]]+)\]", r"\1", s)
    s = re.sub(r"'{2,5}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize(s: str) -> str:
    s = clean_markup(s).replace("\u00a0", " ")
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}))
    s = re.sub(r"^[-–—]\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s


def short_text(s: str) -> bool:
    n = normalize(s)
    return n in SHORT_WORDS or len(n.split()) <= 2 or len(n) <= 12


def fetch_wikitext(cache: Path) -> tuple[str, str]:
    if cache.exists():
        obj = json.loads(cache.read_text(encoding="utf-8"))
    else:
        req = Request(URL, headers={"User-Agent": "mgs3d-wiki-codec-matcher/1.0"})
        with urlopen(req, timeout=60) as response:
            obj = json.loads(response.read().decode("utf-8"))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    text = obj["parse"]["wikitext"]["*"]
    return text, obj.get("parse", {}).get("title", "Metal Gear Solid 3 radio conversations")


def parse_wiki(wikitext: str) -> list[dict]:
    rows: list[dict] = []
    section = ""
    conversation = ""
    current: dict | None = None
    for line_no, raw in enumerate(wikitext.splitlines(), 1):
        line = raw.strip()
        m = re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", line)
        if m:
            current = None
            title = clean_markup(m.group(2))
            level = len(m.group(1))
            if level == 2:
                section, conversation = title, ""
            elif level >= 3:
                conversation = title
            continue
        if not section or not conversation or not line or line.startswith(("{{", "}}", "<!--", "*", "#")):
            continue
        # Parenthetical editorial instructions are not transcript utterances.
        if (line.startswith("(") and line.endswith(")")) or line.startswith("To "):
            continue
        sm = re.match(r"^\s*([^:]{1,60}):\s*(.*?)\s*$", line)
        if sm:
            speaker, text = clean_markup(sm.group(1)), clean_markup(sm.group(2))
            if not text:
                continue
            current = {"speaker": speaker, "english": text, "section": section,
                       "conversation": conversation, "wiki_line": line_no}
            rows.append(current)
        elif current and not line.startswith(("==", "---")):
            # Wikitext wraps long utterances; preserve it as one utterance.
            current["english"] = clean_markup(current["english"] + " " + line)
    for i, row in enumerate(rows):
        row["order"] = i + 1
        row["prev_english"] = rows[i - 1]["english"] if i and rows[i - 1]["conversation"] == row["conversation"] else ""
        row["next_english"] = rows[i + 1]["english"] if i + 1 < len(rows) and rows[i + 1]["conversation"] == row["conversation"] else ""
    return rows


def read_master(path: Path) -> list[dict]:
    csv.field_size_limit(50_000_000)
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("accept", "").strip().lower() == "yes"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", type=Path, default=Path("translation/10_master/current/codec.csv"))
    ap.add_argument("--out-dir", type=Path, default=Path("output/mgs3d-wiki-codec"))
    ap.add_argument("--human", nargs="*", default=["178:10", "239:21", "239:37", "239:41", "239:42", "1044:17"])
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cache = args.out_dir / "metal_gear_solid_3_radio_conversations.api.json"
    wiki_text, title = fetch_wikitext(cache)
    wiki = parse_wiki(wiki_text)
    (args.out_dir / "wiki_conversations.json").write_text(json.dumps({"source_url": URL, "title": title, "utterances": wiki}, ensure_ascii=False, indent=2), encoding="utf-8")
    master = read_master(args.master)
    exact = defaultdict(list); norm = defaultdict(list)
    token_index = defaultdict(set)
    for i, w in enumerate(wiki):
        exact[clean_markup(w["english"])].append(i)
        norm[normalize(w["english"])].append(i)
        for token in set(re.findall(r"[a-z0-9']{3,}", normalize(w["english"]))):
            token_index[token].add(i)
    by_gcx: defaultdict[str, list[tuple[int, dict]]] = defaultdict(list)
    for i, row in enumerate(master):
        by_gcx[row.get("gcx", "")].append((i, row))
    for values in by_gcx.values():
        values.sort(key=lambda x: int(x[1].get("resource", "-1")) if x[1].get("resource", "").isdigit() else -1)
    results = []
    for i, row in enumerate(master):
        text = row.get("english", "").strip()
        candidates = list(exact.get(text, []))
        method = "exact"
        if not candidates:
            candidates = list(norm.get(normalize(text), []))
            method = "normalized exact" if candidates else "UNKNOWN"
        evidence = []
        # Resolve duplicate/short hits only when neighboring accepted rows also
        # occur next to the candidate in the same Wiki conversation.
        neighbors = []
        group = by_gcx.get(row.get("gcx", ""), [])
        pos = next((p for p, (idx, _) in enumerate(group) if idx == i), None)
        if pos is not None:
            for delta in (-2, -1, 1, 2):
                q = pos + delta
                if 0 <= q < len(group):
                    neighbors.append((delta, group[q][1].get("english", "")))
        scored = []
        for ci in candidates:
            score = 0; ev = []
            for delta, nt in neighbors:
                key = normalize(nt)
                target = ci + delta
                if 0 <= target < len(wiki) and wiki[target]["conversation"] == wiki[ci]["conversation"] and key == normalize(wiki[target]["english"]):
                    score += 1; ev.append(f"{delta:+d}: {wiki[target]['speaker']} — {wiki[target]['english']}")
            scored.append((score, ci, ev))
        scored.sort(reverse=True)
        selected = None; speaker_confirmed = False; confidence = "none"; conflict = ""
        if scored:
            best = scored[0]; tied = [x for x in scored if x[0] == best[0]]
            if best[0] > 0 and len(tied) == 1:
                selected, evidence = best[1], best[2]; method = "context"; speaker_confirmed = True; confidence = "high" if best[0] >= 2 else "medium"
            elif len(candidates) == 1 and not short_text(text):
                selected = candidates[0]; evidence = best[2]; speaker_confirmed = True; confidence = "high" if method == "exact" else "medium"
            elif len(candidates) == 1:
                selected = candidates[0]; evidence = best[2]; method += " (short; speaker unconfirmed)"; confidence = "low"
            else:
                method = "ambiguous"; confidence = "low"
        fuzzy = []
        if selected is None:
            # Fuzzy is review-only.  Restrict comparisons to Wiki utterances
            # sharing a substantive word so the 8,948-row run stays bounded.
            words = set(re.findall(r"[a-z0-9']{3,}", normalize(text)))
            # Rare-token union avoids spending the run on generic words such
            # as "the", while still providing useful review candidates.
            rare = sorted(words, key=lambda t: len(token_index.get(t, set())))[:4]
            pool = set().union(*(token_index.get(t, set()) for t in rare)) if rare else set()
            if len(pool) > 500:
                pool = set(sorted(pool)[:500])
            scored_f = sorted(((difflib.SequenceMatcher(None, normalize(text), normalize(wiki[j]["english"])).ratio(), j) for j in pool), reverse=True)[:5]
            fuzzy = [f"{s:.3f}: {wiki[j]['speaker']} — {wiki[j]['english']}" for s, j in scored_f if s >= 0.78]
            # A codec record can split a Wiki speaker line into sentences.  An
            # inclusion is useful review evidence, but is never a match.
            nt = normalize(text)
            contained = [(j, wiki[j]) for j in pool if nt and nt in normalize(wiki[j]["english"])]
            for j, candidate in contained[:5]:
                item = f"containment-only: {candidate['speaker']} — {candidate['english']}"
                if item not in fuzzy:
                    fuzzy.append(item)
            if fuzzy: method = "fuzzy candidates only"
        w = wiki[selected] if selected is not None else {}
        results.append({"gcx": row.get("gcx", ""), "resource": row.get("resource", ""), "English": text,
                        "wiki speaker": w.get("speaker", "") if speaker_confirmed else "", "conversation": w.get("conversation", ""),
                        "match method": method, "confidence": confidence,
                        "context evidence": " || ".join(evidence) if evidence else " || ".join(fuzzy),
                        "wiki english": w.get("english", "") if selected is not None else "",
                        "speaker confirmed": "yes" if speaker_confirmed else "no", "existing speaker conflict": conflict})
    out = args.out_dir / "codec_wiki_matches.csv"
    fields = list(results[0])
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader(); wr.writerows(results)
    human_keys = set(args.human)
    human = [r for r in results if f"{r['gcx']}:{r['resource']}" in human_keys]
    with (args.out_dir / "human_6_verification.csv").open("w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields); wr.writeheader(); wr.writerows(human)
    counts = Counter()
    for r in results:
        counts["exact" if r["match method"] == "exact" else "normalized_exact" if r["match method"] == "normalized exact" else "context_confirmed" if r["match method"] == "context" else "ambiguous" if r["match method"] == "ambiguous" else "unknown" if r["match method"] == "UNKNOWN" or r["match method"].startswith("fuzzy") else "other"] += 1
    summary = {"source_url": URL, "master": str(args.master), "master_accept_yes_rows": len(master), "wiki_utterances": len(wiki),
               "exact_match_count": counts["exact"], "normalized_exact_match_count": counts["normalized_exact"],
               "context_confirmed_count": counts["context_confirmed"], "speaker_confirmed_count": sum(r["speaker confirmed"] == "yes" for r in results),
               "unknown_count": sum(r["match method"] == "UNKNOWN" for r in results), "fuzzy_candidates_only_count": sum(r["match method"] == "fuzzy candidates only" for r in results), "ambiguous_count": counts["ambiguous"],
               "existing_speaker_conflict_count": 0, "existing_speaker_note": "master CSV has no existing speaker field; conflict is not assessable",
               "human_6": {f"{r['gcx']}:{r['resource']}": {k: r[k] for k in ["English", "wiki speaker", "conversation", "match method", "confidence", "context evidence"]} for r in human}}
    (args.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
