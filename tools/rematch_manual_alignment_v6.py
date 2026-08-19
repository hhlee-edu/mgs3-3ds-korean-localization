#!/usr/bin/env python3
"""Apply corrected Korean anchors and conservative exact rematches to V6 state."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def js_json(source: str, marker: str, opener: str, closer: str):
    start = source.index(marker) + len(marker)
    depth = 0
    quoted = escaped = False
    for pos in range(start, len(source)):
        char = source[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return json.loads(source[start : pos + 1]), start, pos + 1
    raise ValueError(f"unterminated JSON after {marker!r}")


def norm(text: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", (text or "").casefold(), re.UNICODE))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("state", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    html_text = args.html.read_text(encoding="utf-8")
    rows, _, _ = js_json(html_text, "ROWS=", "[", "]")
    script, _, _ = js_json(html_text, "SCRIPT=", "[", "]")
    default, default_start, default_end = js_json(
        html_text, "const V5_DEFAULT_STATE=", "{", "}"
    )
    state = json.loads(args.state.read_text(encoding="utf-8"))
    if state["dataset_key"] != default["dataset_key"]:
        raise ValueError("dataset_key mismatch")

    row_by_id = {row["id"]: row for row in rows}
    overrides = {int(key): value for key, value in state["script_ref_overrides"].items()}
    promoted = []
    for relation in state["relations"]:
        if relation.get("decision") != "match":
            continue
        sequences = [int(value) for value in relation.get("right_sequences", [])]
        if not sequences or not any(seq in overrides for seq in sequences):
            continue
        left = " ".join(row_by_id[row_id]["english"] for row_id in relation["left_ids"])
        right = " ".join(script[seq]["english"] for seq in sequences)
        if norm(left) != norm(right):
            continue
        relation.update(
            authority="manual_confirmed_2nd",
            review_stage="second_confirmed",
            anchor_status="safe_manual_anchor",
            order_status="locally_monotonic",
        )
        promoted.append(relation["id"])

    # Use only two-sided anchors in the same media group. Exact text must also
    # occur at only one PS2 sequence globally; this excludes short repetitions.
    anchors = defaultdict(list)
    covered_left = set()
    used_right = set()
    for relation in state["relations"]:
        covered_left.update(relation.get("left_ids", []))
        used_right.update(int(seq) for seq in relation.get("right_sequences", []))
        if relation.get("anchor_status") != "safe_manual_anchor":
            continue
        relation_rows = [row_by_id[row_id] for row_id in relation["left_ids"]]
        groups = {(row["type"], int(row["group"])) for row in relation_rows}
        if len(groups) != 1:
            continue
        group = next(iter(groups))
        anchors[group].append(
            (min(int(row["offset"]) for row in relation_rows),
             min(int(seq) for seq in relation["right_sequences"]))
        )

    script_exact = defaultdict(list)
    for item in script:
        script_exact[norm(item["english"])].append(int(item["index"]))

    additions = []
    for group, points in anchors.items():
        points.sort()
        if len(points) < 2:
            continue
        group_rows = sorted(
            (row for row in rows if (row["type"], int(row["group"])) == group),
            key=lambda row: int(row["offset"]),
        )
        for row in group_rows:
            if row["id"] in covered_left:
                continue
            before = [point for point in points if point[0] < int(row["offset"])]
            after = [point for point in points if point[0] > int(row["offset"])]
            if not before or not after:
                continue
            lo, hi = before[-1][1], after[0][1]
            candidates = script_exact[norm(row["english"])]
            if len(candidates) != 1:
                continue
            seq = candidates[0]
            if not (lo < seq < hi) or seq in used_right:
                continue
            now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            relation = {
                "id": f"rematch_exact_{row['type']}_{row['group']}_{row['offset']}_{seq}",
                "decision": "match",
                "relation_type": "1↔1",
                "left_ids": [row["id"]],
                "right_sequences": [seq],
                "ps2_english_bundle": [script[seq]["english"]],
                "script_ref_bundle": [overrides.get(seq, script[seq].get("korean", ""))],
                "note": "two-sided corrected anchors; globally unique exact English rematch",
                "created_at": now,
                "override_baseline": False,
                "authority": "auto_high_confidence",
                "order_status": "locally_monotonic",
                "anchor_status": "not_anchor_auto_exact",
                "supersedes_auto": False,
                "review_stage": "auto_exact_between_corrected_anchors",
                "previous_anchor_status": "",
            }
            additions.append(relation)
            covered_left.add(row["id"])
            used_right.add(seq)

    state["relations"].extend(additions)
    state["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    state.setdefault("v6_meta", {})["corrected_anchor_rematch"] = {
        "promoted_safe_anchors": len(promoted),
        "added_unique_exact_relations": len(additions),
        "policy": "corrected Korean override + exact English; rematch only between two anchors",
    }
    print(json.dumps(state["v6_meta"]["corrected_anchor_rematch"], ensure_ascii=False))
    if not args.apply:
        return 0

    state_text = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    args.state.write_text(state_text, encoding="utf-8")
    html_text = html_text[:default_start] + state_text + html_text[default_end:]
    args.html.write_text(html_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
