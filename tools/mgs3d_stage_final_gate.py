#!/usr/bin/env python3
"""Final read-only gate for a future stage translation output tree."""
from __future__ import annotations
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path
csv.field_size_limit(10**9)
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'tools'))
from mgs3d_stage_text_scan import stage_records
from mgs3d_stage_apply import PERMANENT_EXCLUSIONS, load_resolved_english

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def token_stream(b):
    """Control tokens only. Any byte >= 0x80 starts a 2-byte token and is
    skipped whole -- walking byte-by-byte lands inside a glyph and reads its
    payload as a control prefix (e.g. 것/긋/명/봐/찍/켠 end in 0x1F).
    Audited over 828,396 pristine stage resources 2026-08-19: 950 disagreements,
    all false controls invented by the old scan, 0 real tokens lost."""
    out=[];i=0
    while i<len(b) and b[i]:
        if b[i:i+2] in (b'\xa0\x7b',b'\xc0\x7d'):out.append(b[i:i+2]);i+=2
        elif b[i]==0x1f and i+1<len(b):out.append(b[i:i+2]);i+=2
        elif b[i]>=0x80 and i+1<len(b):i+=2
        else:i+=1
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('before',type=Path);ap.add_argument('after',type=Path)
    ap.add_argument('--locations',type=Path,default=ROOT/'docs/evidence/2026-08-19-stage-text-scan/stage-text-locations.csv')
    ap.add_argument('--worklist',type=Path,default=ROOT/'docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-worklist-expanded.csv')
    ap.add_argument('--resolved-english',type=Path,default=ROOT/'docs/evidence/2026-08-21-stage-unknown-language-adjudication/resolved-english.csv')
    ap.add_argument('--report',type=Path,default=ROOT/'docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-final-gate.json');a=ap.parse_args()
    locs=read(a.locations); work=read(a.worklist); ready={r['raw_hex'] for r in work if (r.get('current_korean') or r.get('korean') or '').strip()}
    # Sanctioned targets = English locations, plus the `unknown` locations that
    # structural adjudication resolved to the English branch (2026-08-21). The
    # gate has to know the same set the writer knows, or every newly-corrected
    # location reads as an unexpected change. Donor stays out, and the
    # donor_locs check below is untouched.
    resolved=load_resolved_english(a.resolved_english)
    allowed={(r['stage'],int(r['record']),int(r['resource'])) for r in locs
             if r['raw_hex'] in ready and (r['language']=='english'
                or (r['language']=='unknown' and r['raw_hex'] in resolved))}
    # A permanently excluded location must come out byte-identical. The gate did
    # not check this before, which is why r_sna02:0:479 shipped translated while
    # r_sna01:0:479 was correctly held: the exclusion lived only in the writer.
    excluded_locs=set(PERMANENT_EXCLUSIONS)
    # Donor locations as a set. The original inner "for lr in locs" rescanned
    # every location row for every changed resource: 93,784 changed resources
    # against 828,396 location rows is ~7.8e10 comparisons and never returns.
    donor_locs={(r['stage'],int(r['record']),int(r['resource'])) for r in locs if r['language']=='donor'}
    errors=[]; changed=[]; files=sorted((a.before/'stage').glob('**/scenerio.gcx')); after_files=sorted((a.after/'stage').glob('**/scenerio.gcx'))
    if len(files)!=169 or len(after_files)!=169:errors.append(f'stage file count before/after {len(files)}/{len(after_files)}')
    for src in files:
        dst=a.after/src.relative_to(a.before)
        if not dst.is_file():errors.append(f'missing after file {dst}');continue
        br=stage_records(src); ar=stage_records(dst)
        if len(br)!=len(ar):errors.append(f'{src.parent.name}: record count changed');continue
        for ri,(brec,arec) in enumerate(zip(br,ar)):
            try:bs=brec.resources();rs=arec.resources()
            except Exception as e:errors.append(f'{src.parent.name}:{ri}: parse {e}');continue
            if len(bs)!=len(rs):errors.append(f'{src.parent.name}:{ri}: resource count changed');continue
            for j,(old,new) in enumerate(zip(bs,rs)):
                if old.data==new.data:continue
                key=(src.parent.name,ri,j);changed.append(key)
                if key in excluded_locs:errors.append(f'permanently excluded location changed {key}')
                elif key not in allowed:errors.append(f'unexpected/non-EN change {key}')
                if token_stream(old.data)!=token_stream(new.data):errors.append(f'control stream changed {key}')
                # Any location that is structurally donor must remain byte-identical.
                if key in donor_locs:errors.append(f'donor location changed {key}')
    result={'format':'mgs3d-stage-final-gate-v1','stage_files_before':len(files),'stage_files_after':len(after_files),'parse_169_pass':len(files)==169 and len(after_files)==169 and not any('parse' in e for e in errors),'changed_resources':len(changed),'errors':errors,'fr_es_unchanged':not any('donor location changed' in e for e in errors),'control_code_preserved':not any('control stream changed' in e for e in errors),'unexpected_changes':not any('unexpected' in e for e in errors),'permanent_exclusions_intact':not any('permanently excluded' in e for e in errors),'resolved_english_admitted':len(resolved),'overflow':'requires apply dry-run report with zero encode/overflow errors','missing_glyphs':'requires apply dry-run report with zero encode errors','pass':not errors}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if not errors else 1
if __name__=='__main__':raise SystemExit(main())
