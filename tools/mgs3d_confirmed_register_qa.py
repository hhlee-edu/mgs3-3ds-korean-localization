#!/usr/bin/env python3
"""
MGS3D confirmed-speaker register QA / proposal generator.

READ-ONLY with respect to master/build/staging. It reads the final verdict/review
CSV plus codec-speaker-match.csv, classifies Korean speech level conservatively,
and emits audit/proposal CSVs only.

Confirmed register policy (derived from PS2 Korean corpus):
  Para-Medic, EVA -> polite
  Zero, Sigint, Snake, The Boss -> plain

Important:
- Speaker is NEVER inferred from Korean endings.
- Only externally confirmed speaker matches are actionable by default.
- mixed/unknown Korean is not auto-proposed.
- This tool does NOT apply translations.
"""

import argparse, csv, re
from pathlib import Path
from collections import Counter

REGISTER = {
    "Para-Medic": "polite",
    "EVA": "polite",
    "Zero": "plain",
    "Sigint": "plain",
    "Snake": "plain",
    "The Boss": "plain",
}
ALIASES = {
    "Para Medic": "Para-Medic", "Paramedic": "Para-Medic", "PARA-MEDIC": "Para-Medic",
    "Eva": "EVA", "Major Zero": "Zero", "Major Tom": "Zero", "Tom": "Zero",
    "Boss": "The Boss", "TheBoss": "The Boss", "Jack": "Snake",
}
# Require an externally evidenced method. Add project-specific labels with --trusted-method.
DEFAULT_TRUSTED = {
    "substring_unique", "substring_same_speaker", "sequence_confirmed",
    "exact", "exact_unique", "external", "gamefaqs", "fandom",
    "partial_unique", "partial_same_speaker",
}

CTRL = re.compile(r"<[^>]+>")
ICON = re.compile(r"#\s*\{\s*\d+\s*\}\s*#")
SPACE_PUNCT = re.compile(r"\s+([.!?…])")
ONLY_INTERJECTION = re.compile(
    r"^(?:네|예|아|아아|어|응|음|흠|오|와|뭐|그래|그렇군|그렇구나|정말|잠깐)[.!?…]*$"
)
POLITE = [
    re.compile(r"(?:요|죠)(?:[.!?…]|$)"),
    # `-ㅂ니다`/`-ㅂ니까` are handled by has_hapnida(): as a bare jamo `ㅂ` can
    # never match composed Hangul (겁니다 = 겁+니+다), and a plain `니다`/`니까`
    # would swallow 아니다 and the connective -으니까.
    re.compile(r"(?:십시오|시오)(?:[.!?…]|$)"),
    re.compile(r"(?:세요|셔요)(?:[.!?…]|$)"),
]
PLAIN = [
    re.compile(r"(?:다|야|어|아|지|군|네|나|냐|라|자|거든|잖아|겠어|했어|한다|했다|인가|일세|걸세|하게)(?:[.!?…]|$)")
]

JONGSEONG_B = 17          # index of final ㅂ in the Hangul syllable formula

def has_hapnida(clause):
    """True for the `-ㅂ니다 / -ㅂ니까` polite ending (합니다, 겁니다, 아닙니다).

    The syllable before `니다`/`니까` must carry a final ㅂ. Plain `아니다` and
    the connective `-으니까` (그러니까, 싶으니까) do not, so they stay plain.
    """
    for m in re.finditer(r"니(?:다|까)(?=[.!?…]|$)", clause):
        i = m.start() - 1
        if i >= 0 and "가" <= clause[i] <= "힣" and (ord(clause[i]) - 0xAC00) % 28 == JONGSEONG_B:
            return True
    return False

def norm_speaker(s):
    s=(s or "").strip()
    return ALIASES.get(s,s)

def clean_korean(s):
    s = CTRL.sub(" ", s or "")
    s = ICON.sub(" ", s)
    s = s.replace("\\n", " ").replace("\r", " ").replace("\n", " ")
    s = SPACE_PUNCT.sub(r"\1", s)
    return re.sub(r"\s+", " ", s).strip()

def classify_register(text):
    t=clean_korean(text)
    if not t:
        return "unknown"
    # Slash is not a delimiter; split only on sentence punctuation.
    clauses=[x.strip() for x in re.split(r"(?<=[.!?…])\s+", t) if x.strip()]
    p=q=0
    for c in clauses or [t]:
        if ONLY_INTERJECTION.fullmatch(c):
            continue
        # POLITE must win per clause: `-습니다` also ends in `-다`, so scoring
        # both lists independently made every polite sentence come out "mixed".
        if has_hapnida(c) or any(rx.search(c) for rx in POLITE):
            p += 1
        elif any(rx.search(c) for rx in PLAIN):
            q += 1
    if p and q: return "mixed"
    if p: return "polite"
    if q: return "plain"
    return "unknown"

def load_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def key(row):
    # Prefer explicit gcx/resource; otherwise location-ish key.
    g=(row.get("gcx") or row.get("GCX") or "").strip()
    r=(row.get("resource") or row.get("res") or row.get("RESOURCE") or "").strip()
    if g and r: return (g,r)
    loc=(row.get("location") or row.get("canonical_location") or row.get("gcx_res") or "").strip()
    if ":" in loc:
        a,b=loc.split(":",1); return (a.strip(),b.strip())
    return None

def pick(row,*names):
    for n in names:
        if n in row and row[n] not in (None,""):
            return row[n]
    return ""

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--review", required=True, help="8,948-row final verdict/review CSV")
    ap.add_argument("--speaker-match", required=True, help="codec-speaker-match.csv")
    ap.add_argument("--outdir", default="output/speaker-register-actionable")
    ap.add_argument("--trusted-method", action="append", default=[])
    args=ap.parse_args()

    review=load_csv(args.review)
    matches=load_csv(args.speaker_match)
    trusted={x.lower() for x in DEFAULT_TRUSTED}|{x.lower() for x in args.trusted_method}

    mi={}
    for m in matches:
        k=key(m)
        if not k: continue
        sp=norm_speaker(pick(m,"matched_speaker","speaker_confirmed","speaker"))
        method=pick(m,"method","match_method").strip()
        source=pick(m,"source","match_source").strip()
        agreement=pick(m,"agreement","status").strip()
        confirmed = bool(sp in REGISTER and (
            method.lower() in trusted or
            any(x in source.lower() for x in ("gamefaq","fandom")) or
            agreement.lower() in ("confirmed","agree","agreement","match")
        ))
        mi[k]=(sp,method,source,agreement,confirmed)

    audit=[]
    actionable=[]
    for i,row in enumerate(review):
        k=key(row)
        if not k or k not in mi: continue
        sp,method,source,agreement,confirmed=mi[k]
        if sp not in REGISTER: continue
        ko=pick(row,"final_korean","korean","current_korean")
        observed=classify_register(ko)
        expected=REGISTER[sp]
        status=("MATCH" if observed==expected else
                "MISMATCH" if observed in ("polite","plain") else
                observed.upper())
        rec={
            "index":i, "gcx":k[0], "resource":k[1],
            "speaker":sp, "expected_register":expected,
            "observed_register":observed, "status":status,
            "speaker_confirmed":"yes" if confirmed else "no",
            "match_method":method, "match_source":source, "agreement":agreement,
            "english":pick(row,"english","recovered_english"),
            "korean":ko,
            "prior_verdict":pick(row,"final_verdict","verdict","decision"),
            "prior_issue":pick(row,"issue_type"),
        }
        audit.append(rec)
        if confirmed and status=="MISMATCH":
            rec2=dict(rec)
            # Do NOT machine-rewrite Korean. Produce a tightly scoped review task.
            rec2["action"]="REWRITE_REGISTER"
            rec2["instruction"]=(
                f"{sp} 화자 확정. 의미/용어/제어코드는 유지하고 "
                + ("존댓말로 자연스럽게 재작성" if expected=="polite"
                   else "반말로 자연스럽게 재작성")
                + ". byte-fit/glyph/control-code 검증 후에만 적용."
            )
            actionable.append(rec2)

    out=Path(args.outdir)
    fields=["index","gcx","resource","speaker","expected_register","observed_register",
            "status","speaker_confirmed","match_method","match_source","agreement",
            "english","korean","prior_verdict","prior_issue"]
    write_csv(out/"codec-register-audit.csv",audit,fields)
    write_csv(out/"codec-register-actionable.csv",actionable,fields+["action","instruction"])

    counts=Counter((r["speaker"],r["status"],r["speaker_confirmed"]) for r in audit)
    summary=[]
    for sp in REGISTER:
        rows=[r for r in audit if r["speaker"]==sp]
        summary.append({
            "speaker":sp,"expected_register":REGISTER[sp],"matched_rows":len(rows),
            "confirmed_rows":sum(r["speaker_confirmed"]=="yes" for r in rows),
            "match":sum(r["status"]=="MATCH" and r["speaker_confirmed"]=="yes" for r in rows),
            "mismatch":sum(r["status"]=="MISMATCH" and r["speaker_confirmed"]=="yes" for r in rows),
            "mixed":sum(r["status"]=="MIXED" and r["speaker_confirmed"]=="yes" for r in rows),
            "unknown":sum(r["status"]=="UNKNOWN" and r["speaker_confirmed"]=="yes" for r in rows),
        })
    write_csv(out/"codec-register-summary.csv",summary,
              ["speaker","expected_register","matched_rows","confirmed_rows","match","mismatch","mixed","unknown"])

    print(f"audit={len(audit)} actionable={len(actionable)}")
    for x in summary: print(x)

if __name__=="__main__":
    main()
