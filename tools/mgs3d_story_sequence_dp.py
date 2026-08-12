#!/usr/bin/env python3
"""Monotonic N:M subtitle alignment inside already anchored story segments."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_english_korean_match import normalized
from mgs3d_movie_sequence_match import split_korean
from mgs3d_story_sequence_join import boundaries, cards


def transcript(path: Path) -> list[dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("english_sequence") or not row.get("english") or not row.get("korean"):
                continue
            seq = int(row["english_sequence"])
            rows.setdefault(seq, row)
    return [rows[key] for key in sorted(rows)]


def similarity(left: str, right: str) -> float:
    a, b = normalized(left), normalized(right)
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
    aw, bw = set(a.split()), set(b.split())
    overlap = len(aw & bw) / max(1, len(aw | bw))
    return ratio * 0.75 + overlap * 0.25


def align_segment(media: list[dict[str, object]], script: list[dict[str, str]]):
    n, m = len(media), len(script)
    neg = -10**9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            base = dp[i][j]
            if base <= neg / 2:
                continue
            if i < n and base - 0.42 > dp[i + 1][j]:
                dp[i + 1][j] = base - 0.42; back[i + 1][j] = (i, j, "skip_card", 1, 0, 0.0)
            if j < m and base - 0.24 > dp[i][j + 1]:
                dp[i][j + 1] = base - 0.24; back[i][j + 1] = (i, j, "skip_script", 0, 1, 0.0)
            for nc in range(1, min(6, n - i) + 1):
                left = " ".join(str(media[i + k]["english"]) for k in range(nc))
                for ns in range(1, min(3, m - j) + 1):
                    right = " ".join(script[j + k]["english"] for k in range(ns))
                    sim = similarity(left, right)
                    # Position is supplied by the monotonic path; similarity
                    # must still clear a conservative floor.
                    if sim < 0.58:
                        continue
                    score = base + sim * 2.4 - 0.12 * (nc + ns - 2)
                    if score > dp[i + nc][j + ns]:
                        dp[i + nc][j + ns] = score
                        back[i + nc][j + ns] = (i, j, "match", nc, ns, sim)
    steps = []
    i, j = n, m
    while i or j:
        step = back[i][j]
        if step is None:
            break
        pi, pj, kind, nc, ns, sim = step
        steps.append((kind, pi, pj, nc, ns, sim))
        i, j = pi, pj
    return list(reversed(steps))


def monotonic_anchor_run(values: list[tuple[int, int]]) -> list[int]:
    """Return the longest locally monotonic sequence-anchor run."""
    runs: list[list[int]] = []
    run: list[int] = []
    previous = None
    for _, sequence in sorted(set(values)):
        if previous is None or 0 <= sequence - previous <= 12:
            run.append(sequence)
        else:
            if run:
                runs.append(run)
            run = [sequence]
        previous = sequence
    if run:
        runs.append(run)
    return max(runs, key=len, default=[])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("movie_dat", type=Path); p.add_argument("demo_dat", type=Path)
    p.add_argument("direct_movie", type=Path); p.add_argument("direct_demo", type=Path)
    p.add_argument("alignment", type=Path); p.add_argument("existing_matches", type=Path)
    p.add_argument("prior_dp_matches", type=Path)
    p.add_argument("output_csv", type=Path); p.add_argument("review_csv", type=Path)
    p.add_argument("summary_json", type=Path)
    args = p.parse_args()
    script_all = transcript(args.alignment)
    by_seq = {int(row["english_sequence"]): row for row in script_all}
    existing_rows = list(csv.DictReader(args.existing_matches.open(encoding="utf-8-sig", newline="")))
    prior_rows = list(csv.DictReader(args.prior_dp_matches.open(encoding="utf-8-sig", newline="")))
    existing = {(row["type"], int(row["offset"])) for row in existing_rows + prior_rows}
    accepted = []; review = []; category_rows = {k: 0 for k in
        ("split_merge", "expression_modified", "addition_deletion", "anchor_order_unresolved")}
    anchored_mismatch = {"below_auto_threshold": 0, "dp_card_gap": 0,
                         "empty_korean_partition": 0}
    total_cards = 0
    added_anchor_points = 0
    baseline_two_anchor_segments = 0
    expanded_two_anchor_segments = 0
    total_segments = 0
    for kind, dat, direct_path in (("movie", args.movie_dat, args.direct_movie),
                                   ("demo", args.demo_dat, args.direct_demo)):
        data, media, records = cards(dat); total_cards += len(media)
        starts = boundaries(kind, data, records)
        groups: dict[int, list[dict[str, object]]] = {}
        for card in media:
            groups.setdefault(bisect.bisect_right(starts, int(card["offset"])) - 1, []).append(card)
        anchors: dict[int, list[tuple[int, int]]] = {}
        with direct_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["match_status"] != "exact-unique-korean" or not row["english_sequence"]:
                    continue
                g = bisect.bisect_right(starts, int(row["offset"])) - 1
                anchors.setdefault(g, []).append((int(row["offset"]), int(row["english_sequence"])))
        baseline_anchors = {g: list(values) for g, values in anchors.items()}
        direct_anchor_set = {(g, off, seq) for g, values in anchors.items() for off, seq in values}
        for row in existing_rows:
            if row["type"] != kind or not row.get("english_sequence"):
                continue
            off, seq = int(row["offset"]), int(row["english_sequence"])
            g = bisect.bisect_right(starts, off) - 1
            anchors.setdefault(g, []).append((off, seq))
        for row in prior_rows:
            if row["type"] != kind or not row.get("english_sequence_start"):
                continue
            off = int(row["offset"]); g = bisect.bisect_right(starts, off) - 1
            anchors.setdefault(g, []).append((off, int(row["english_sequence_start"])))
            if row.get("english_sequence_end") != row.get("english_sequence_start"):
                anchors[g].append((off, int(row["english_sequence_end"])))
        expanded_anchor_set = {(g, off, seq) for g, values in anchors.items() for off, seq in values}
        added_anchor_points += len(expanded_anchor_set - direct_anchor_set)
        total_segments += len(groups)
        baseline_two_anchor_segments += sum(
            len(monotonic_anchor_run(baseline_anchors.get(group, []))) >= 2 for group in groups
        )
        expanded_two_anchor_segments += sum(
            len(monotonic_anchor_run(anchors.get(group, []))) >= 2 for group in groups
        )
        for group, group_cards in groups.items():
            seqs = monotonic_anchor_run(anchors.get(group, []))
            gaps_here = [card for card in group_cards if (kind, int(card["offset"])) not in existing]
            if len(seqs) < 2:
                category_rows["anchor_order_unresolved"] += len(gaps_here)
                review.extend({"type": kind, "group": group, "offset": card["offset"],
                               "english": card["english"], "category": "anchor_order_unresolved",
                               "note": "fewer than two independent sequence anchors"} for card in gaps_here)
                continue
            lo, hi = max(0, min(seqs) - 2), max(seqs) + 2
            script = [by_seq[s] for s in range(lo, hi + 1) if s in by_seq]
            steps = align_segment(group_cards, script)
            matched_offsets = set()
            low_confidence_offsets = set()
            skipped_offsets = set()
            empty_partition_offsets = set()
            for step_kind, i, j, nc, ns, sim in steps:
                if step_kind == "skip_card":
                    skipped_offsets.add(int(group_cards[i]["offset"]))
                    continue
                if step_kind != "match":
                    continue
                cards_part = group_cards[i:i + nc]; script_part = script[j:j + ns]
                # DP order is the primary constraint, but weak text still does
                # not auto-promote. Multi-line context permits 0.72; isolated
                # 1:1 remains at 0.84.
                threshold = 0.84 if nc == ns == 1 else 0.72
                if sim < threshold:
                    low_confidence_offsets.update(int(card["offset"]) for card in cards_part)
                    continue
                korean_full = " ".join(row["korean"].strip() for row in script_part)
                pieces = split_korean(korean_full, [len(normalized(str(c["english"]))) for c in cards_part])
                relation = "1:1"
                if nc > 1 and ns == 1: relation = "1:N"
                elif nc == 1 and ns > 1: relation = "N:1"
                elif nc > 1 and ns > 1: relation = "N:M"
                combined_left = " ".join(str(c["english"]) for c in cards_part)
                combined_right = " ".join(row["english"] for row in script_part)
                category = "split_merge" if normalized(combined_left) == normalized(combined_right) or relation != "1:1" else "expression_modified"
                for card, korean in zip(cards_part, pieces):
                    key = (kind, int(card["offset"]))
                    if not korean.strip():
                        empty_partition_offsets.add(int(card["offset"]))
                        continue
                    matched_offsets.add(int(card["offset"]))
                    if key in existing:
                        continue
                    category_rows[category] += 1
                    accepted.append({"type": kind, "group": group, "offset": card["offset"],
                                     "record": card["record"], "entry": card["entry"],
                                     "english": card["english"], "korean": korean,
                                     "english_sequence_start": script_part[0]["english_sequence"],
                                     "english_sequence_end": script_part[-1]["english_sequence"],
                                     "relation": relation, "similarity": f"{sim:.4f}",
                                     "confidence": "high_monotonic_dp", "category": category,
                                     "note": f"anchored sequence window {lo}..{hi}"})
            for card in gaps_here:
                if int(card["offset"]) not in matched_offsets:
                    offset = int(card["offset"])
                    if offset in low_confidence_offsets:
                        reason = "below_auto_threshold"
                    elif offset in empty_partition_offsets:
                        reason = "empty_korean_partition"
                    else:
                        reason = "dp_card_gap"
                    anchored_mismatch[reason] += 1
                    category_rows["addition_deletion"] += 1
                    review.append({"type": kind, "group": group, "offset": card["offset"],
                                   "english": card["english"], "category": "addition_deletion",
                                   "note": f"{reason}; unmatched inside anchored window {lo}..{hi}"})
    fields = ["type", "group", "offset", "record", "entry", "english", "korean",
              "english_sequence_start", "english_sequence_end", "relation", "similarity",
              "confidence", "category", "note"]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(accepted)
    review_fields=["type","group","offset","english","category","note"]
    with args.review_csv.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=review_fields);w.writeheader();w.writerows(review)
    existing_count=len(existing); new_offsets={(r["type"],int(r["offset"])) for r in accepted}
    combined=existing|new_offsets
    summary={"existing_high_confidence":existing_count,"new_high_confidence":len(new_offsets),
             "combined_high_confidence":len(combined),"total_rows":total_cards,
             "combined_match_rate":round(len(combined)/total_cards,6),
             "gap_reduction":len(new_offsets),"remaining_gaps":total_cards-len(combined),
             "relations":{x:sum(r["relation"]==x for r in accepted) for x in ("1:1","1:N","N:1","N:M")},
             "gap_analysis_rows":category_rows,
             "anchored_mismatch_analysis":anchored_mismatch,
             "anchor_order_unresolved_rows":sum(
                 1 for r in review if r["category"] == "anchor_order_unresolved"
             ),
             "anchor_expansion":{"added_anchor_points":added_anchor_points,
                 "total_segments":total_segments,
                 "baseline_two_or_more_segments":baseline_two_anchor_segments,
                 "expanded_two_or_more_segments":expanded_two_anchor_segments,
                 "newly_eligible_segments":expanded_two_anchor_segments-baseline_two_anchor_segments}}
    args.summary_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
