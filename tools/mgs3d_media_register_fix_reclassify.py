# -*- coding: utf-8 -*-
"""Re-classify the 91 movie/demo register FIX proposals against current master.

READ-ONLY. Classifies only -- it never rewrites a proposal, never invents a
sentence, and never applies anything.

Buckets:
  STILL_VALID     master text is still exactly what the FIX was drafted against
  ALREADY_RESOLVED the defect the FIX targeted is gone from the current text
  CONFLICT        this session's misplacement REPLACE rewrote the line, so the
                  FIX's korean_new is stale AND the defect may still be present
  NEEDS_REVIEW    the line is still awaiting a position fix (overflow / HUMAN /
                  NO_SOURCE), or master drifted for some other reason
"""
import csv
import io
import os
import re
import sys
import collections
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location(
    'ctx', os.path.join(HERE, 'mgs3d_media_misplaced_context.py'))
ctx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctx)

EVID = os.path.join(ROOT, 'docs/evidence/2026-08-19-media-misplaced-recovery')
PROPOSALS = os.path.join(ROOT, 'output/media-register-qa/media-qa-proposals.csv')
PLAN = os.path.join(EVID, 'media-recovery-patch-plan.csv')
RECOVERY = os.path.join(EVID, 'media-misplaced-recovery.csv')

PUNCT = re.compile(r' [.,!?]')
LATIN = re.compile(r'[A-Za-z]{2,}')


def defect_present(flags, text):
    """Can the flagged defect still be seen in this text?

    Only the mechanically checkable flags are decided here. Register and
    machine-translation flags are judgement calls, so they are reported as
    'unknown' rather than guessed at.
    """
    checks = []
    if 'PUNCT_SPACING' in flags:
        checks.append(bool(PUNCT.search(text)))
    if 'ENGLISH_RESIDUE' in flags or 'NAME_SCRIPT_SPLIT' in flags:
        checks.append(bool(LATIN.search(text)))
    if 'RECORD_REGISTER_SPLIT' in flags or 'MT_LITERAL' in flags or not flags.strip():
        return None                      # not mechanically decidable
    if not checks:
        return None
    return any(checks)


def main():
    master = {}
    for media, path in ctx.MASTER.items():
        for r in ctx.read_csv(path):
            master[(media, r['record'], r['entry'])] = r

    plan = ctx.read_csv(PLAN)
    applied = {(p['media'], p['record'], p['entry']) for p in plan
               if p['apply_status'] == 'APPLY_NOW'}
    overflow = {(p['media'], p['record'], p['entry']) for p in plan
                if p['apply_status'] != 'APPLY_NOW'}
    recovery = ctx.read_csv(RECOVERY)
    pending = {(r['media'], r['record'], r['entry']) for r in recovery
               if r['action'] in ('HUMAN', 'NO_SOURCE')}
    # the three rows whose verdict was settled back to KEEP are not pending
    pending -= {('demo', '29', '13'), ('demo', '61', '30'), ('movie', '18', '4')}

    fixes = [r for r in ctx.read_csv(PROPOSALS) if r['verdict'] == 'FIX']
    out = []
    for f in fixes:
        key = (f['media'], f['record'], f['entry'])
        m = master.get(key)
        now = (m or {}).get('korean', '')
        defect = defect_present(f['flags'], now)

        if key in applied:
            bucket = 'ALREADY_RESOLVED' if defect is False else 'CONFLICT'
            why = ('the misplacement REPLACE rewrote this line; '
                   + ('the flagged defect is gone from the new text'
                      if defect is False else
                      'korean_new is drafted against the old, wrong line and must be re-derived'))
        elif key in overflow or key in pending:
            bucket = 'NEEDS_REVIEW'
            why = 'line is still awaiting a position fix (overflow / HUMAN / NO_SOURCE) - re-run after that lands'
        elif now == f['korean']:
            bucket = 'STILL_VALID'
            why = 'master text is unchanged and still matches the text the FIX was drafted against'
        elif now == f['korean_new']:
            bucket = 'ALREADY_RESOLVED'
            why = 'master already carries the proposed text'
        elif defect is False:
            bucket = 'ALREADY_RESOLVED'
            why = 'master drifted but the flagged defect is no longer present'
        else:
            bucket = 'NEEDS_REVIEW'
            why = 'master text differs from both the FIX source and its proposal'

        out.append({
            'media': f['media'], 'record': f['record'], 'entry': f['entry'],
            'flags': f['flags'], 'english': f['english'],
            'fix_source_korean': f['korean'], 'fix_proposed_korean': f['korean_new'],
            'master_korean_now': now,
            'defect_still_present': {True: 'YES', False: 'NO'}.get(defect, 'UNKNOWN'),
            'bytes_now': f['bytes_now'], 'bytes_new': f['bytes_new'], 'byte_fit': f['byte_fit'],
            'reclassification': bucket, 'why': why, 'original_reason': f['reason'],
        })

    out.sort(key=lambda r: (r['reclassification'], r['media'], int(r['record']), int(r['entry'])))
    cols = list(out[0].keys())
    dest = os.path.join(EVID, 'media-register-fix-reclassified.csv')
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(out)

    tally = collections.Counter(r['reclassification'] for r in out)
    print('FIX rows re-classified %d' % len(out))
    for k in ('STILL_VALID', 'ALREADY_RESOLVED', 'CONFLICT', 'NEEDS_REVIEW'):
        print('  %-17s %d' % (k, tally.get(k, 0)))
    print()
    print('by media  %s' % dict(collections.Counter(r['media'] for r in out)))
    print('defect    %s' % dict(collections.Counter(r['defect_still_present'] for r in out)))
    print('-> %s' % os.path.relpath(dest, ROOT))


if __name__ == '__main__':
    main()
