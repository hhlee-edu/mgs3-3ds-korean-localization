#!/usr/bin/env python3
"""Experimental conservative PS2/HD <-> MGS3D N:M English window matcher."""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


CONTROL_RE = re.compile(r"<[^>]+>")
TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ThreeDSCard:
    id: str
    type: str
    group: int
    local_index: int
    offset: int
    record: int | None
    entry: int | None
    english: str
    normalized_english: str
    baseline_status: str


@dataclass(frozen=True)
class PS2Line:
    sequence: int
    speaker: str
    english: str
    normalized_english: str


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = CONTROL_RE.sub(" ", text)
    text = (text.replace("’", "'").replace("‘", "'")
            .replace("“", '"').replace("”", '"')
            .replace("–", "-").replace("—", "-"))
    text = re.sub(r"\bu\s*\.\s*s\s*\.?\b", "us", text)
    text = text.replace("'", "")
    return " ".join(TOKEN_RE.findall(text))


def join_window(texts: list[str]) -> str:
    return " ".join(t.strip() for t in texts if t.strip())


def token_metrics(a: str, b: str) -> tuple[float, float, float]:
    ca, cb = Counter(a.split()), Counter(b.split())
    overlap = sum((ca & cb).values())
    precision = overlap / sum(ca.values()) if ca else 0.0
    recall = overlap / sum(cb.values()) if cb else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def ngrams(text: str, n: int = 3) -> set[str]:
    compact = text.replace(" ", "")
    return {compact[i:i+n] for i in range(max(0, len(compact)-n+1))}


def ngram_score(a: str, b: str) -> float:
    aa, bb = ngrams(a), ngrams(b)
    return 2 * len(aa & bb) / (len(aa) + len(bb)) if aa or bb else 0.0


def score_window(ds_text: str, ps2_text: str, pc: int, dc: int, config: dict) -> dict:
    a, b = normalize(ds_text), normalize(ps2_text)
    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    precision, recall, f1 = token_metrics(a, b)
    ng = ngram_score(a, b)
    coverage = min(len(a), len(b)) / max(len(a), len(b)) if a and b else 0.0
    weights = config["weights"]
    base = (weights["sequence_ratio"] * ratio + weights["token_f1"] * f1
            + weights["char_ngram"] * ng + weights["coverage"] * coverage)
    penalty = ((pc - 1) + (dc - 1)) * config["window_penalty"]
    exact_bonus = config["exact_bonus"] if a and a == b else 0.0
    final = max(0.0, min(1.0, base - penalty + exact_bonus))
    return {"normalized_ds": a, "normalized_ps2": b, "sequence_ratio": ratio,
            "token_precision": precision, "token_recall": recall, "token_f1": f1,
            "ngram_score": ng, "coverage": coverage, "size_penalty": penalty,
            "exact_bonus": exact_bonus, "final_score": final}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def extract_js_value(path: Path, name: str):
    text = path.read_text(encoding="utf-8")
    marker = name + "="
    pos = text.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(text[pos:])[0]


def load_cards(matches_path: Path, review_path: Path) -> dict[tuple[str, int], list[ThreeDSCard]]:
    merged: dict[tuple[str, int, int], dict] = {}
    for status, path in (("dp_match", matches_path), ("review", review_path)):
        for order, row in enumerate(read_csv(path)):
            key = (row["type"], int(row["group"]), int(row["offset"]))
            item = dict(row); item["_status"] = status; item["_order"] = order
            merged[key] = item
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for (media, group, _), row in merged.items():
        groups[(media, group)].append(row)
    output = {}
    for key, rows in groups.items():
        def order_key(row):
            record = row.get("record", "")
            entry = row.get("entry", "")
            if str(record).isdigit() and str(entry).isdigit():
                return (0, int(record), int(entry), int(row["offset"]))
            return (1, int(row["offset"]), row["_order"], 0)
        rows.sort(key=order_key)
        output[key] = [ThreeDSCard(
            id=f"{key[0]}:{key[1]}:{row['offset']}", type=key[0], group=key[1],
            local_index=i, offset=int(row["offset"]),
            record=int(row["record"]) if str(row.get("record", "")).isdigit() else None,
            entry=int(row["entry"]) if str(row.get("entry", "")).isdigit() else None,
            english=row["english"], normalized_english=normalize(row["english"]),
            baseline_status=row["_status"]) for i, row in enumerate(rows)]
    return output


def load_script(html: Path) -> list[PS2Line]:
    rows = extract_js_value(html, "SCRIPT")
    return [PS2Line(int(r.get("index", i)), r.get("speaker", ""), r["english"],
                    normalize(r["english"])) for i, r in enumerate(rows)]


def load_manual(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def candidate(cards, lines, i, j, dc, pc, config) -> dict:
    ds = join_window([x.english for x in cards[i:i+dc]])
    ps = join_window([x.english for x in lines[j:j+pc]])
    metrics = score_window(ds, ps, pc, dc, config)
    return {"ds_start": i, "ds_end": i+dc-1, "ps2_start_index": j,
            "ps2_end_index": j+pc-1, "ds_count": dc, "ps2_count": pc,
            "ds_text": ds, "ps2_text": ps, "relation": f"{pc}:{dc}", **metrics}


def align(cards: list[ThreeDSCard], lines: list[PS2Line], config: dict):
    n, m = len(cards), len(lines)
    neg = -1e30
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    steps = [[10**9] * (m + 1) for _ in range(n + 1)]
    prev = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0], steps[0][0] = 0.0, 0
    candidates = []
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == neg: continue
            transitions = []
            if i < n: transitions.append((i+1, j, -config["skip_penalty_3ds"], "3ds_only", None))
            if j < m: transitions.append((i, j+1, -config["skip_penalty_ps2"], "ps2_only", None))
            for dc in range(1, min(config["max_3ds_window"], n-i)+1):
                for pc in range(1, min(config["max_ps2_window"], m-j)+1):
                    c = candidate(cards, lines, i, j, dc, pc, config)
                    candidates.append(c)
                    # Center around zero so weak fuzzy links lose to explicit skips.
                    value = c["final_score"] - config["match_score_center"]
                    transitions.append((i+dc, j+pc, value, "match", c))
            for ni, nj, value, kind, payload in transitions:
                score, count = dp[i][j] + value, steps[i][j] + 1
                if score > dp[ni][nj] + 1e-12 or (abs(score-dp[ni][nj]) <= 1e-12 and count < steps[ni][nj]):
                    dp[ni][nj], steps[ni][nj] = score, count
                    prev[ni][nj] = (i, j, kind, payload)
    path=[];i,j=n,m
    while i or j:
        item=prev[i][j]
        if item is None: raise RuntimeError(f"no DP path at {i},{j}")
        pi,pj,kind,payload=item
        if kind=="match": path.append(payload)
        else: path.append({"kind":kind,"ds_start":pi if kind=="3ds_only" else None,
                           "ps2_start_index":pj if kind=="ps2_only" else None})
        i,j=pi,pj
    path.reverse()
    by_start=defaultdict(list)
    for c in candidates: by_start[(c['ds_start'],c['ps2_start_index'])].append(c)
    by_bounds={(c['ds_start'],c['ds_end'],c['ps2_start_index'],c['ps2_end_index']):c
               for c in candidates}
    for p in path:
        if "final_score" not in p: continue
        rivals=sorted((c["final_score"] for c in by_start[(p['ds_start'],p['ps2_start_index'])]
                       if c is not p),reverse=True)
        p["margin"] = p["final_score"] - (rivals[0] if rivals else 0.0)
        boundary_rivals=[]
        for ds0 in range(max(0,p['ds_start']-1),min(n-1,p['ds_start']+1)+1):
            for ds1 in range(max(ds0,p['ds_end']-1),min(n-1,p['ds_end']+1)+1):
                for ps0 in range(max(0,p['ps2_start_index']-1),min(m-1,p['ps2_start_index']+1)+1):
                    for ps1 in range(max(ps0,p['ps2_end_index']-1),min(m-1,p['ps2_end_index']+1)+1):
                        if (ds0,ds1,ps0,ps1)==(p['ds_start'],p['ds_end'],p['ps2_start_index'],p['ps2_end_index']):continue
                        q=by_bounds.get((ds0,ds1,ps0,ps1))
                        if q and not (ds1<p['ds_start'] or ds0>p['ds_end'] or ps1<p['ps2_start_index'] or ps0>p['ps2_end_index']):
                            boundary_rivals.append(q['final_score'])
        p['boundary_margin']=p['final_score']-(max(boundary_rivals) if boundary_rivals else 0.0)
    return path,candidates


def relation_key(left_ids, right_sequences):
    return (tuple(left_ids), tuple(int(x) for x in right_sequences))


def select_pilot(manual: dict, groups,
                 wanted=("movie:0", "movie:2", "demo:96", "demo:49", "demo:15"),
                 target_limit=47):
    by_group=defaultdict(list)
    for r in manual["relations"]:
        if r.get("decision") != "match" or not r.get("left_ids"): continue
        if len(r["left_ids"]) > 4 or len(r["right_sequences"]) > 3: continue
        key=":".join(r["left_ids"][0].split(":")[:2]);by_group[key].append(r)
    segments=[]
    for name in wanted:
        rels=sorted(by_group[name],key=lambda r:(min(r["right_sequences"]),r["left_ids"][0]))
        if len(rels)<3: continue
        left,right=rels[0],rels[-1]
        targets=rels[1:-1]
        media,group=name.split(":"); cards=groups[(media,int(group))]
        index={c.id:c.local_index for c in cards}
        ds_lo=max(index[x] for x in left["left_ids"])+1
        ds_hi=min(index[x] for x in right["left_ids"])
        ps_lo=max(left["right_sequences"])+1
        ps_hi=min(right["right_sequences"])
        targets=[r for r in targets if all(ds_lo<=index[x]<ds_hi for x in r["left_ids"])
                 and all(ps_lo<=int(x)<ps_hi for x in r["right_sequences"])]
        segments.append({"name":name,"media":media,"group":int(group),"ds_lo":ds_lo,
                         "ds_hi":ds_hi,"ps_lo":ps_lo,"ps_hi":ps_hi,"targets":targets,
                         "left_anchor":left["id"],"right_anchor":right["id"]})
    # Keep the evaluation set inside the requested 30..50 range. Relations
    # beyond the cap remain hidden from the matcher; they are simply not scored.
    kept = 0
    for segment in segments:
        room = max(0, target_limit - kept)
        segment["targets"] = segment["targets"][:room]
        kept += len(segment["targets"])
    return segments


def select_independent_holdouts(manual: dict, groups, excluded: set[str], limit=75):
    by_group=defaultdict(list)
    for r in manual['relations']:
        if r.get('decision')!='match' or not r.get('left_ids'):continue
        if len(r['left_ids'])>4 or len(r['right_sequences'])>3:continue
        name=':'.join(r['left_ids'][0].split(':')[:2])
        if name not in excluded:by_group[name].append(r)
    segments=[]
    for name in sorted(by_group):
        media,group=name.split(':');cards=groups[(media,int(group))]
        index={c.id:c.local_index for c in cards}
        rels=sorted(by_group[name],key=lambda r:(min(r['right_sequences']),min(index[x] for x in r['left_ids'])))
        for pos,target in enumerate(rels):
            left=rels[pos-1] if pos else None;right=rels[pos+1] if pos+1<len(rels) else None
            target_ds=[index[x] for x in target['left_ids']];target_ps=list(map(int,target['right_sequences']))
            ds_lo=(max(index[x] for x in left['left_ids'])+1 if left else max(0,min(target_ds)-20))
            ds_hi=(min(index[x] for x in right['left_ids']) if right else min(len(cards),max(target_ds)+21))
            ps_lo=(max(map(int,left['right_sequences']))+1 if left else max(0,min(target_ps)-30))
            ps_hi=(min(map(int,right['right_sequences'])) if right else min(2164,max(target_ps)+31))
            anchor_count=int(left is not None)+int(right is not None)
            if (not all(ds_lo<=x<ds_hi for x in target_ds)
                    or not all(ps_lo<=x<ps_hi for x in target_ps)):
                # Conflicting/non-monotonic neighboring manual relations cannot
                # serve as bounds. Keep the case as exploratory radius-only
                # evaluation, which is never eligible for high confidence.
                ds_lo=max(0,min(target_ds)-20);ds_hi=min(len(cards),max(target_ds)+21)
                ps_lo=max(0,min(target_ps)-30);ps_hi=min(2164,max(target_ps)+31)
                anchor_count=0
            segments.append({'name':f"{name}:{target['id']}",'media':media,'group':int(group),
                'ds_lo':ds_lo,'ds_hi':ds_hi,'ps_lo':ps_lo,'ps_hi':ps_hi,'targets':[target],
                'left_anchor':left['id'] if left else '', 'right_anchor':right['id'] if right else '',
                'anchor_count':anchor_count})
            if len(segments)>=limit:return segments
    return segments


def classify_high(p: dict, config: dict, context_supported: bool = False,
                  adjacent_ps2_skip: bool = False) -> tuple[str,str]:
    tokens=p["normalized_ds"].split(); short=len(tokens)<=2
    discourse={"hmm","yes","no","what","well","right","okay","ok"}
    edge_tokens=[]
    if p['ds_count']>1:
        normalized_tokens=normalize(p['ds_text']).split()
        edge_tokens=([normalized_tokens[0],normalized_tokens[-1]]
                     if normalized_tokens else [""])
    unstable_edge=any(x in discourse for x in edge_tokens)
    high=(p["final_score"]>=config["high_score_threshold"]
          and p.get("margin",-1)>=config["high_margin_threshold"]
          and p.get("boundary_margin",-1)>=config["high_margin_threshold"]
          and p["token_recall"]>=config["high_token_recall"]
          and (not short or context_supported) and not adjacent_ps2_skip
          and not unstable_edge)
    reason = "score+margin+recall+bilateral_context" if short else "score+margin+recall"
    return ("high",reason) if high else ("review","conservative_gate")


def old_relation_for(gt, baseline_rows, group_cards):
    mapping={f"{r['type']}:{r['group']}:{r['offset']}":
             tuple(range(int(r['english_sequence_start']),int(r['english_sequence_end'])+1))
             for r in baseline_rows if r['english_sequence_start']}
    ids=tuple(gt["left_ids"]);seq=tuple(int(x) for x in gt["right_sequences"])
    if ids and all(mapping.get(x)==seq for x in ids): return "exact"
    if any(set(mapping.get(x,())) & set(seq) for x in ids): return "partial"
    return "wrong"


def run_pilot(args):
    config=json.loads(args.config.read_text(encoding="utf-8"))
    groups=load_cards(args.matches,args.review);script=load_script(args.script_html)
    manual=load_manual(args.manual);baseline=read_csv(args.matches)
    if getattr(args, "blind2", False):
        excluded={"movie:0","movie:2","demo:96","demo:49","demo:15","demo:127",
          "demo:60","demo:105","demo:12","movie:3","demo:44","demo:13","demo:36",
          "demo:63","demo:18","demo:24","demo:28","demo:93","demo:22","demo:37"}
        segments=select_independent_holdouts(manual,groups,excluded,75)
        prefix="blind2"
    elif getattr(args, "blind", False):
        segments=select_pilot(manual,groups,
            wanted=("demo:127","demo:60","demo:105","demo:12","movie:3",
                    "demo:44","demo:13","demo:36","demo:63","demo:18",
                    "demo:24","demo:28","demo:93","demo:22","demo:37"),
            target_limit=75)
        prefix="blind"
    else:
        segments=select_pilot(manual,groups)
        prefix="pilot"
    out=args.output;out.mkdir(parents=True,exist_ok=True);(out/"debug").mkdir(exist_ok=True)
    comparisons=[];candidate_rows=[];alignment=[]
    for seg in segments:
        all_cards=groups[(seg["media"],seg["group"])]
        cards=all_cards[seg["ds_lo"]:seg["ds_hi"]]
        lines=[x for x in script if seg["ps_lo"]<=x.sequence<seg["ps_hi"]]
        path,candidates=align(cards,lines,config)
        proposed={}
        for path_index,p in enumerate(path):
            if "final_score" not in p: continue
            ids=[cards[i].id for i in range(p["ds_start"],p["ds_end"]+1)]
            seq=[lines[i].sequence for i in range(p["ps2_start_index"],p["ps2_end_index"]+1)]
            before = path[path_index-1] if path_index else None
            after = path[path_index+1] if path_index+1 < len(path) else None
            context_supported = all(q and "final_score" in q
                                    and q["normalized_ds"] == q["normalized_ps2"]
                                    for q in (before, after))
            adjacent_ps2_skip = any(q and q.get('kind')=='ps2_only' for q in (before,after))
            conf,reason=classify_high(p,config,context_supported,adjacent_ps2_skip);key=relation_key(ids,seq)
            if seg.get('anchor_count',2)==0:
                conf,reason='review','exploratory_no_anchor'
            proposed[key]=p|{"ids":ids,"sequences":seq,"confidence":conf,"reason":reason}
            alignment.append({"segment":seg["name"],**proposed[key]})
        for gt in seg["targets"]:
            key=relation_key(gt["left_ids"],gt["right_sequences"]);p=proposed.get(key)
            overlap=[q for k,q in proposed.items() if set(k[0])&set(key[0])]
            best=p or (max(overlap,key=lambda x:(len(set(x["ids"])&set(key[0])),x["final_score"])) if overlap else None)
            if p:
                result="exact"
            elif best:
                ds_delta=len(set(best["ids"]) ^ set(key[0]))
                actual=best["sequences"]; expected=list(key[1])
                ps_near=(bool(set(actual)&set(expected)) and
                         abs(min(actual)-min(expected))<=1 and
                         abs(max(actual)-max(expected))<=1)
                result="boundary_partial" if ds_delta<=2 and ps_near else "wrong"
            else:
                result="abstain"
            comparisons.append({"case_id":gt["id"],"segment":seg["name"],
                "ground_truth_ds":"|".join(gt["left_ids"]),"ground_truth_ps2":"|".join(map(str,gt["right_sequences"])),
                "old_result":old_relation_for(gt,baseline,all_cards),"new_result":result,
                "new_ds":"|".join(best["ids"]) if best else "","new_ps2":"|".join(map(str,best["sequences"])) if best else "",
                "score":f"{best['final_score']:.6f}" if best else "","margin":f"{best.get('margin',0):.6f}" if best else "",
                "confidence":best["confidence"] if best else "abstain","reason":best["reason"] if best else "no_match"})
        for c in candidates:
            candidate_rows.append({"segment":seg["name"],**c,
                "ds_ids":"|".join(cards[i].id for i in range(c["ds_start"],c["ds_end"]+1)),
                "ps2_sequences":"|".join(str(lines[i].sequence) for i in range(c["ps2_start_index"],c["ps2_end_index"]+1))})
    write_csv(out/f"{prefix}_comparison.csv",comparisons)
    write_csv(out/f"{prefix}_candidates.csv",[x for x in alignment if x["confidence"]=="high"])
    write_csv(out/"debug"/"candidate_scores.csv",candidate_rows)
    write_csv(out/"debug"/"ambiguous_cases.csv",[x for x in alignment if x["confidence"]!="high"])
    write_csv(out/"debug"/"rejected_candidates.csv",[x for x in candidate_rows
              if x["final_score"] < config["high_score_threshold"]])
    write_csv(out/"debug"/"normalized_samples.csv",[{
        "segment":x["segment"],"ds_text":x["ds_text"],"ps2_text":x["ps2_text"],
        "normalized_ds":x["normalized_ds"],"normalized_ps2":x["normalized_ps2"]}
        for x in candidate_rows[:200]])
    write_csv(out/"baseline_conflicts.csv",[r for r in comparisons
              if r["confidence"]=="high" and r["old_result"]!="exact"])
    (out/f"{prefix}_alignment.json").write_text(json.dumps(alignment,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report=make_report(comparisons,segments,config,args)
    (out/f"{prefix}_report.md").write_text(report,encoding="utf-8")
    print(report)


def write_csv(path: Path, rows: list[dict]):
    if not rows: path.write_text("",encoding="utf-8");return
    fields=[]
    for row in rows:
        for k in row:
            if k not in fields:fields.append(k)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore");w.writeheader();w.writerows(rows)


def make_report(rows,segments,config,args):
    total=len(rows);old=Counter(r["old_result"] for r in rows);new=Counter(r["new_result"] for r in rows)
    high=[r for r in rows if r["confidence"]=="high"]
    high_correct=sum(r["new_result"]=="exact" for r in high);wrong=sum(r["new_result"] not in {"exact","abstain"} for r in high)
    precision=high_correct/len(high) if high else 0;coverage=len(high)/total if total else 0
    improved = new["exact"] > old["exact"] and new["wrong"] < old["wrong"]
    verdict="GO" if total>=30 and high and precision>=.95 and improved else ("CONDITIONAL" if precision>=.90 and high else "NO-GO")
    return f"""# N:M Window Matcher Pilot\n\n- Input matches: `{args.matches}`\n- Input review: `{args.review}`\n- Canonical PS2 SCRIPT: `{args.script_html}` (2,164 lines)\n- Ground truth: {total} hidden relations\n- Pilot segments: {', '.join(s['name'] for s in segments)}\n- Windows: PS2 1..{config['max_ps2_window']}, 3DS 1..{config['max_3ds_window']}\n- Weights: `{json.dumps(config['weights'],sort_keys=True)}`\n- Skip penalties: PS2 {config['skip_penalty_ps2']}, 3DS {config['skip_penalty_3ds']}\n- Window penalty: {config['window_penalty']}\n- High thresholds: score {config['high_score_threshold']}, margin {config['high_margin_threshold']}, recall {config['high_token_recall']}\n\n## Old matcher\n\n- exact: {old['exact']}\n- partial: {old['partial']}\n- wrong: {old['wrong']}\n\n## New matcher\n\n- exact: {new['exact']}\n- boundary partial: {new['boundary_partial']}\n- wrong: {new['wrong']}\n- abstain: {new['abstain']}\n\n## High confidence\n\n- proposed: {len(high)}\n- exact correct: {high_correct}\n- wrong/partial: {wrong}\n- precision: {precision:.1%}\n- coverage: {coverage:.1%}\n\n## Verdict\n\n**{verdict}**\n\nThis pilot hides the evaluated manual relations. Only the first and last manual relations in each segment are retained as bounding anchors. No existing CSV is modified.\n"""


def inspect(args):
    groups=load_cards(args.matches,args.review);script=load_script(args.script_html);manual=load_manual(args.manual)
    result={"matches":len(read_csv(args.matches)),"review":len(read_csv(args.review)),
            "groups":len(groups),"cards":sum(map(len,groups.values())),"ps2_lines":len(script),
            "ps2_min":min(x.sequence for x in script),"ps2_max":max(x.sequence for x in script),
            "manual_relations":len(manual["relations"]),"manual_matches":sum(r.get("decision")=="match" for r in manual["relations"]),
            "script_sha256":hashlib.sha256(json.dumps([asdict(x) for x in script],sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    print(json.dumps(result,ensure_ascii=False,indent=2))


def _assist_bounds(review_rows: list[dict], card: ThreeDSCard,
                   anchors: dict[tuple[str, int], list[tuple[int, int, int]]],
                   script: list[PS2Line]) -> tuple[int, int, str] | None:
    """Return inclusive PS2 sequence bounds without falling back to global search."""
    review_by_id = {f"{r['type']}:{r['group']}:{r['offset']}": r for r in review_rows}
    row = review_by_id.get(card.id, {})
    note = row.get("note", "")
    found = re.search(r"(?:window|range)\s+(\d+)\.\.(\d+)", note, re.I)
    if found:
        return int(found.group(1)), int(found.group(2)), "anchor_segment"
    nearby = anchors.get((card.type, card.group), [])
    before = [x for x in nearby if x[0] < card.local_index]
    after = [x for x in nearby if x[0] > card.local_index]
    seq_min, seq_max = script[0].sequence, script[-1].sequence
    if before and after:
        return before[-1][2], after[0][1], "anchor_segment"
    if before:
        center = before[-1][2]
        return center, min(seq_max, center + 30), "adjacent_expansion"
    if after:
        center = after[0][1]
        return max(seq_min, center - 30), center, "adjacent_expansion"
    return None


def _cluster_assist_candidates(candidates: list[dict], limit: int = 5) -> list[dict]:
    """Keep distinct story locations; nearby boundary variants remain alternatives."""
    ordered = sorted(candidates, key=lambda x: (-x["score"], x["ps2_start"], x["ps2_end"]))
    clusters: list[list[dict]] = []
    for item in ordered:
        cluster = next((c for c in clusters
                        if abs(c[0]["ps2_start"] - item["ps2_start"]) <= 2), None)
        if cluster is None:
            clusters.append([item])
        else:
            cluster.append(item)
    representatives = sorted((c[0] | {
        "boundary_alternatives": [
            {k: x[k] for k in ("ps2_start", "ps2_end", "relation", "score")}
            for x in c[1:4]
        ]} for c in clusters), key=lambda x: (-x["score"], x["ps2_start"]))[:limit]
    for rank, item in enumerate(representatives, 1):
        item["rank"] = rank
        next_score = representatives[rank]["score"] if rank < len(representatives) else 0.0
        item["margin"] = item["score"] - next_score
    return representatives


def generate_assist(args):
    config = json.loads(args.config.read_text(encoding="utf-8"))
    groups = load_cards(args.matches, args.review)
    review_rows, match_rows = read_csv(args.review), read_csv(args.matches)
    script = load_script(args.script_html)
    line_by_seq = {x.sequence: x for x in script}
    anchors: dict[tuple[str, int], list[tuple[int, int, int]]] = defaultdict(list)
    local_by_id = {c.id: c for cards in groups.values() for c in cards}
    for row in match_rows:
        card = local_by_id.get(f"{row['type']}:{row['group']}:{row['offset']}")
        if card and row.get("english_sequence_start") and row.get("english_sequence_end"):
            anchors[(card.type, card.group)].append(
                (card.local_index, int(row["english_sequence_start"]), int(row["english_sequence_end"])))
    for values in anchors.values():
        values.sort()

    windows, skipped = {}, 0
    for cards in groups.values():
        for start, first in enumerate(cards):
            if first.baseline_status != "review":
                continue
            bounds = _assist_bounds(review_rows, first, anchors, script)
            for dc in range(1, min(config["max_3ds_window"], len(cards) - start) + 1):
                selected = cards[start:start + dc]
                key = "|".join(x.id for x in selected)
                if bounds is None:
                    skipped += 1
                    continue
                lo, hi, scope = bounds
                ds_text = join_window([x.english for x in selected])
                scored = []
                for ps_start in range(lo, hi + 1):
                    for pc in range(1, config["max_ps2_window"] + 1):
                        seqs = list(range(ps_start, ps_start + pc))
                        if seqs[-1] > hi or any(s not in line_by_seq for s in seqs):
                            continue
                        ps_text = join_window([line_by_seq[s].english for s in seqs])
                        metrics = score_window(ds_text, ps_text, pc, dc, config)
                        token_count = len(normalize(ds_text).split())
                        scored.append({"ps2_start": ps_start, "ps2_end": seqs[-1],
                            "ps2_count": pc, "relation": f"{pc}:{dc}",
                            "score": metrics["final_score"], "scope": scope,
                            "ps2_english_bundle": ps_text,
                            "short_repeat_risk": token_count <= 2})
                windows[key] = {"status": "ready", "candidates": _cluster_assist_candidates(scored)}
    payload = {"format": "mgs3d-manual-assist-candidates-v1",
        "proposal_only": True, "scoring_config": config,
        "source": {"matches": str(args.matches), "review": str(args.review),
                   "script_html": str(args.script_html)},
        "query_windows": len(windows), "requires_global_search": skipped, "windows": windows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "query_windows": len(windows),
                      "requires_global_search": skipped}, ensure_ascii=False, indent=2))


ASSIST_CSS = r'''
/* ===== V6.5 READ-ONLY ASSIST ===== */
#assistBox{margin:8px 0;padding:9px;border:1px solid #285c91;border-radius:7px;background:#101d2b}
.assist-title{display:flex;justify-content:space-between;align-items:center;color:#a9d7ff;font-weight:700}
.assist-card{margin-top:7px;padding:7px;border-left:3px solid #318bd5;background:#15283a;border-radius:4px;cursor:pointer}
.assist-card:hover{background:#19344c}.assist-actions{display:flex;gap:5px}.assist-preview{outline:2px solid #2795ef!important;background:#123b5d!important}
.assist-lines{font-size:11px;color:#b9c9d8;margin-top:4px;max-height:105px;overflow:auto}
.assist-lines .hit{color:#d7efff;font-weight:700}.assist-warn{color:#ffc66d}.assist-muted{color:#91a3b4}
'''


ASSIST_JS = r'''
/* ===== V6.5 READ-ONLY ASSIST ===== */
const ASSIST_CANDIDATES=__ASSIST_DATA__;
let assistExpanded=false,assistPreview=null;
const assistRowsById=new Map(ROWS.map((r,i)=>[r.id,{r,i}]));
function assistWindowKey(){
  const a=[...selectedLeft].map(id=>assistRowsById.get(id)).filter(Boolean).sort((x,y)=>x.i-y.i);
  if(!a.length||a.length>4)return null;
  if(a.some((x,i)=>i&&(x.r.type!==a[0].r.type||x.r.group!==a[0].r.group||x.i!==a[i-1].i+1)))return null;
  return a.map(x=>x.r.id).join("|");
}
function assistConflict(c){
  const kinds=new Set();for(let i=c.ps2_start;i<=c.ps2_end;i++){const u=ps2UseInfo(i);if(u.kind==="strong")kinds.add("수동확정과 충돌");else if(u.kind==="first")kinds.add("기존 관계 사용 중");}
  return [...kinds];
}
function renderAssist(){
  const box=document.getElementById("assistBox");if(!box)return;
  const key=assistWindowKey(),entry=key&&ASSIST_CANDIDATES.windows[key];
  if(!key){box.innerHTML='<div class="assist-title">추천 후보</div><div class="assist-muted">같은 장면의 연속 1~4개 3DS 카드를 선택하세요.</div>';return;}
  if(!entry||entry.status!=="ready"){box.innerHTML='<div class="assist-title">추천 후보</div><div class="assist-muted">이 window는 고정 anchor 검색 범위가 없어 자동 전체검색하지 않습니다.</div>';return;}
  const list=entry.candidates.slice(0,assistExpanded?5:3);
  box.innerHTML=`<div class="assist-title"><span>추천 후보 · 카드를 누르면 위치만 표시</span><span class="assist-actions"><button class="small" id="assistRefresh">추천 새로 받기</button><button class="small" id="assistMore">${assistExpanded?'3개만 보기':'5개 보기'}</button></span></div>`+
    list.map(c=>{const conflicts=assistConflict(c),risk=c.short_repeat_risk?'⚠ 짧은/반복 대사 — 문맥 확인 필수':'';
      const range=c.ps2_start===c.ps2_end?`#${c.ps2_start}`:`#${c.ps2_start}~${c.ps2_end}`;
      let lines='';for(let i=Math.max(1,c.ps2_start-2);i<=Math.min(SCRIPT.length,c.ps2_end+2);i++){const x=scriptByIndex[i];if(x)lines+=`<div class="${i>=c.ps2_start&&i<=c.ps2_end?'hit':''}">#${i} ${esc(x.english)}</div>`;}
      return `<div class="assist-card" data-assist-view="${c.rank}"><b>${c.rank}. PS2 ${range}</b> · 예상 ${c.relation} · ${Math.round(c.score*100)}
        <div>${esc(c.ps2_english_bundle)}</div><div class="assist-lines">${lines}</div>
        ${(risk||conflicts.length)?`<div class="assist-warn">${risk} ${conflicts.map(x=>'⚠ '+x).join(' ')}</div>`:''}</div>`}).join('');
  const more=document.getElementById('assistMore');if(more)more.onclick=e=>{e.stopPropagation();assistExpanded=!assistExpanded;renderAssist();};
  const refresh=document.getElementById('assistRefresh');if(refresh)refresh.onclick=e=>{e.stopPropagation();clearAssistPreview(false);renderAssist();toast('현재 선택의 추천을 다시 표시했습니다.');};
  box.querySelectorAll('[data-assist-view]').forEach(b=>b.onclick=()=>viewAssist(+b.dataset.assistView));
}
function paintAssistPreview(){
  document.querySelectorAll('.assist-preview').forEach(e=>e.classList.remove('assist-preview'));
  if(!assistPreview)return;for(let i=assistPreview.start;i<=assistPreview.end;i++)document.querySelector(`[data-right="${i}"]`)?.classList.add('assist-preview');
}
function clearAssistPreview(rerender=true){const had=!!assistPreview;assistPreview=null;if(had&&rerender)renderRight(state);else paintAssistPreview();}
function viewAssist(rank){
  const e=ASSIST_CANDIDATES.windows[assistWindowKey()];const c=e?.candidates.find(x=>x.rank===rank);if(!c)return;
  if(assistPreview&&assistPreview.start===c.ps2_start&&assistPreview.end===c.ps2_end){clearAssistPreview();return;}
  assistPreview={start:c.ps2_start,end:c.ps2_end};manualRightFocus=c.ps2_start;renderRight(state);paintAssistPreview();
  setTimeout(()=>document.querySelector(`[data-right="${c.ps2_start}"]`)?.scrollIntoView({block:'center',behavior:'smooth'}),0);
}
const _assistRightRange=rightRange;rightRange=function(s){
  let [lo,hi]=_assistRightRange(s);if(assistPreview){lo=Math.max(1,Math.min(lo,assistPreview.start-2));hi=Math.min(SCRIPT.length,Math.max(hi,assistPreview.end+2));}return [lo,hi];
};
const _assistRenderRight=renderRight;renderRight=function(s){_assistRenderRight(s);paintAssistPreview();};
const _assistRender=render;render=function(){_assistRender();renderAssist();};
const _assistLoadRelation=loadRelationForReview;loadRelationForReview=function(id,announce=true){
  if(currentReviewRelId===id){currentReviewRelId=null;selectedLeft.clear();selectedRight.clear();manualRightFocus=null;clearAssistPreview(false);render();if(announce)toast('관계 표시를 닫았습니다.');return;}
  clearAssistPreview(false);_assistLoadRelation(id,announce);
};
const _assistRelationBadge=relationBadge;relationBadge=function(id){let html=_assistRelationBadge(id);const rel=latestLeftRelation(id);
  if(rel&&(rel.left_ids||[])[0]!==id)html=html.replace(/\s*<button[^>]*data-open-rel="[^"]+"[^>]*>[^<]*<\/button>/,'');
  return currentReviewRelId?html.replace(`data-open-rel="${currentReviewRelId}">관계 불러오기`,`data-open-rel="${currentReviewRelId}">관계 닫기`):html;
};
document.querySelector('#rightHead')?.insertAdjacentHTML('beforebegin','<div id="assistBox"></div>');
document.addEventListener('click',e=>{if(e.target.closest('[data-left]')){clearAssistPreview(false);setTimeout(renderAssist,0);}else if(e.target.closest('[data-right]'))clearAssistPreview(false);});
document.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,select'))return;if(['1','2','3'].includes(e.key))viewAssist(+e.key);if(e.key==='Escape')clearAssistPreview();});
renderAssist();
'''


def build_assist_html(args):
    source = args.source_html.read_text(encoding="utf-8")
    payload = json.loads(args.assist_json.read_text(encoding="utf-8"))
    if "V6.5 READ-ONLY ASSIST" in source:
        raise SystemExit("source HTML already contains the assist integration")
    script = ASSIST_JS.replace("__ASSIST_DATA__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    source = source.replace("</style>", ASSIST_CSS + "\n</style>", 1)
    pos = source.rfind("</script>")
    if pos < 0:
        raise SystemExit("source HTML has no closing script tag")
    source = source[:pos] + script + "\n" + source[pos:]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    print(json.dumps({"output": str(args.output), "bytes": args.output.stat().st_size},
                     ensure_ascii=False, indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="command",required=True)
    def common(q):
        q.add_argument("--matches",type=Path,default=Path("analysis/story_media_order/story_sequence_dp_matches.csv"))
        q.add_argument("--review",type=Path,default=Path("analysis/story_media_order/story_sequence_dp_review.csv"))
        q.add_argument("--script-html",type=Path,default=Path("analysis/story_media_order/html/mgs3_manual_nm_alignment_review_v6.html"))
        q.add_argument("--manual",type=Path,default=Path("analysis/story_media_order/html/mgs3d_manual_alignment_review_v6.json"))
    q=sub.add_parser("inspect");common(q);q.set_defaults(fn=inspect)
    q=sub.add_parser("pilot");common(q);q.add_argument("--config",type=Path,default=Path("analysis/nm_window_matcher/config.json"));q.add_argument("--output",type=Path,default=Path("analysis/nm_window_matcher/output"));q.set_defaults(fn=run_pilot)
    q=sub.add_parser("evaluate");common(q);q.add_argument("--config",type=Path,default=Path("analysis/nm_window_matcher/config.json"));q.add_argument("--output",type=Path,default=Path("analysis/nm_window_matcher/output"));q.set_defaults(fn=run_pilot)
    q=sub.add_parser("blind");common(q);q.add_argument("--config",type=Path,default=Path("analysis/nm_window_matcher/config.json"));q.add_argument("--output",type=Path,default=Path("analysis/nm_window_matcher/output"));q.set_defaults(fn=run_pilot,blind=True)
    q=sub.add_parser("blind2");common(q);q.add_argument("--config",type=Path,default=Path("analysis/nm_window_matcher/config.json"));q.add_argument("--output",type=Path,default=Path("analysis/nm_window_matcher/output"));q.set_defaults(fn=run_pilot,blind2=True)
    q=sub.add_parser("assist");common(q);q.add_argument("--config",type=Path,default=Path("analysis/nm_window_matcher/config.json"));q.add_argument("--output",type=Path,default=Path("analysis/nm_window_matcher/output/manual_assist_candidates.json"));q.set_defaults(fn=generate_assist)
    q=sub.add_parser("assist-html");q.add_argument("--source-html",type=Path,default=Path("analysis/story_media_order/html/mgs3_manual_nm_alignment_review_v6_4_4_all_scenes_space_safe.html"));q.add_argument("--assist-json",type=Path,default=Path("analysis/nm_window_matcher/output/manual_assist_candidates.json"));q.add_argument("--output",type=Path,default=Path("analysis/story_media_order/html/mgs3_manual_nm_alignment_review_v6_5_assist.html"));q.set_defaults(fn=build_assist_html)
    q=sub.add_parser("run");q.set_defaults(fn=lambda _: (_ for _ in ()).throw(SystemExit("full run disabled until pilot verdict is GO")))
    a=p.parse_args();a.fn(a)


if __name__=="__main__": main()
