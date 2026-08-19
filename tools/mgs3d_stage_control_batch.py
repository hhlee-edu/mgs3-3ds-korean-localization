# -*- coding: utf-8 -*-
"""Generic control-aware batch for any stage category.

Same contract as mgs3d_stage_control_assemble.py (which stays pinned to the
already-finished TUTORIAL_CONTROL set) but parameterised, so later categories
can reuse the authoring path without touching completed data.

READ-ONLY except the working sheet and this batch's own report.

Per row, in order:
  1. identity regression -- the row must re-encode byte-identically from its
     own raw bytes before any Korean is substituted
  2. donor runs are refused outright (FR/ES branch text)
  3. every alphabetic run needs Korean, or the row is HUMAN
  4. control/glyph bytes reproduced verbatim
  5. assembled length <= original slot
  6. no character outside the resident global page
"""
import csv
import io
import json
import os
import sys
import importlib.util
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from mgs3d_codec_tool import parse_rendered  # noqa: E402

_s = importlib.util.spec_from_file_location(
    'au', os.path.join(ROOT, 'tools/mgs3d_stage_control_author.py'))
au = importlib.util.module_from_spec(_s)
sys.modules['au'] = au
_s.loader.exec_module(au)

ANALYSIS = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')
WORK = os.path.join(ANALYSIS, 'stage-translation-working.csv')
CHARMAP = os.path.join(ROOT, 'translation/40_build_input/global_page_v2/character-map.json')


def escape_ctrl(text):
    return ''.join('<%02X>' % ord(c) if ord(c) < 0x20 else c for c in text)


def list_runs(category):
    """Print every translatable run of a category -- the authoring input."""
    csv.field_size_limit(10 ** 9)
    runs = collections.Counter()
    for r in csv.DictReader(io.open(WORK, encoding='utf-8-sig', newline='')):
        if r['category'] != category or (r.get('current_korean') or '').strip():
            continue
        segs, _ = au.decompose(bytes.fromhex(r['raw_hex']))
        if not any(k in ('C', 'G') for k, _ in segs):
            continue
        for kind, val in segs:
            if kind == 'T' and any(c.isalpha() for c in val):
                runs[val] += 1
    for s, n in runs.most_common():
        print('x%-4d %r' % (n, s))
    return runs


def run_batch(category, runs, label, donor_runs=()):
    csv.field_size_limit(10 ** 9)
    cmap = {k: bytes.fromhex(v) for k, v in
            json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].items()}
    with io.open(WORK, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    KO = {en: escape_ctrl(ko) for en, ko in runs.items()}
    report = []
    ident_ok = done = human = donor = 0
    missing = collections.Counter()
    newglyph = set()

    for r in rows:
        if r['category'] != category or (r.get('current_korean') or '').strip():
            continue
        raw = bytes.fromhex(r['raw_hex'])
        segs, tail = au.decompose(raw)
        if not any(k in ('C', 'G') for k, _ in segs):
            continue                       # plain rows belong to the plain path

        if parse_rendered(au.compose(segs, tail), cmap) != raw:
            report.append({'id': r['id'], 'state': 'IDENTITY_FAIL', 'slot': len(raw),
                           'need': '', 'detail': 'does not re-encode'})
            continue
        ident_ok += 1

        texts = [v for k, v in segs if k == 'T']
        if any(t in donor_runs for t in texts):
            donor += 1
            r['status'] = 'DONOR_MISCLASSIFIED'
            report.append({'id': r['id'], 'state': 'DONOR_MISCLASSIFIED', 'slot': len(raw),
                           'need': '', 'detail': 'FR/ES branch text; not translated'})
            continue

        miss = [t for t in texts if any(c.isalpha() for c in t) and t not in runs]
        if miss:
            human += 1
            for t in miss:
                missing[t] += 1
            report.append({'id': r['id'], 'state': 'HUMAN', 'slot': len(raw), 'need': '',
                           'detail': 'no Korean for %d run(s): %r' % (len(miss), miss[0][:40])})
            continue

        src = au.compose(segs, tail, KO)
        bad = [c for c in src if ord(c) > 0x7F and c not in cmap]
        if bad:
            newglyph.update(bad)
            report.append({'id': r['id'], 'state': 'NEW_GLYPH', 'slot': len(raw), 'need': '',
                           'detail': ''.join(sorted(set(bad)))})
            continue
        enc = parse_rendered(src, cmap)
        if len(enc) > len(raw):
            report.append({'id': r['id'], 'state': 'SLOT_OVERFLOW', 'slot': len(raw),
                           'need': len(enc), 'detail': 'over by %d' % (len(enc) - len(raw))})
            continue
        if [v for k, v in au.decompose(enc)[0] if k == 'C'] != [v for k, v in segs if k == 'C']:
            report.append({'id': r['id'], 'state': 'CONTROL_CHANGED', 'slot': len(raw),
                           'need': len(enc), 'detail': 'control stream differs'})
            continue

        r['current_korean'] = src
        r['source'] = label
        done += 1
        report.append({'id': r['id'], 'state': 'OK', 'slot': len(raw), 'need': len(enc),
                       'detail': ''})

    with io.open(WORK, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)
    dest = os.path.join(ANALYSIS, 'stage-control-batch-%s.csv' % category.lower())
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
        w.writeheader()
        w.writerows(report)

    t = collections.Counter(x['state'] for x in report)
    print('%s control rows      : %d' % (category, len(report)))
    print('  identity regression: %d' % ident_ok)
    print('  OK                 : %d' % done)
    for k in ('SLOT_OVERFLOW', 'HUMAN', 'DONOR_MISCLASSIFIED', 'NEW_GLYPH',
              'CONTROL_CHANGED', 'IDENTITY_FAIL'):
        if t.get(k):
            print('  %-19s: %d' % (k, t[k]))
    print('  new glyphs         : %d %s' % (len(newglyph), ''.join(sorted(newglyph))))
    for s, n in missing.most_common(10):
        print('   no Korean x%-3d %r' % (n, s[:60]))
    for x in report:
        if x['state'] == 'SLOT_OVERFLOW':
            print('   OVER id=%s slot=%s need=%s' % (x['id'], x['slot'], x['need']))
    return t


if __name__ == '__main__':
    list_runs(sys.argv[1])
