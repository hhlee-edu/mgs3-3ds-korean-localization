# -*- coding: utf-8 -*-
"""Assemble the TUTORIAL_CONTROL Korean and check it against the real slots.

READ-ONLY except for the working sheet and its own reports. scenerio.gcx,
staging and the analysis authority are never written.

Order of checks, all against the resource's real bytes:
  1. identity regression -- every row must re-encode byte-identically before
     any translation is applied (the permanent gate)
  2. every translatable run must have Korean, or the row is HUMAN
  3. control/glyph bytes reproduced verbatim
  4. final assembled resource length <= original slot
  5. no character outside the resident global page
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

_g = importlib.util.spec_from_file_location(
    'gl', os.path.join(ROOT, 'tools/mgs3d_stage_control_glossary.py'))
gl = importlib.util.module_from_spec(_g)
sys.modules['gl'] = gl
_g.loader.exec_module(gl)

ANALYSIS = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')
WORK = os.path.join(ANALYSIS, 'stage-translation-working.csv')
CHARMAP = os.path.join(ROOT, 'translation/40_build_input/global_page_v2/character-map.json')


def main():
    csv.field_size_limit(10 ** 9)
    cmap = {k: bytes.fromhex(v) for k, v in
            json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].items()}
    with io.open(WORK, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    # parse_rendered() only accepts printable ASCII literally; the game's own
    # line break (0x0A) has to be written as an <0A> escape.
    def escape_ctrl(text):
        out = []
        for ch in text:
            out.append('<%02X>' % ord(ch) if ord(ch) < 0x20 else ch)
        return ''.join(out)

    KO = {en: escape_ctrl(ko) for en, ko in gl.RUNS.items()}

    report = []
    ident_ok = 0
    done = human = donor = 0
    missing_runs = collections.Counter()
    newglyph = set()

    for r in rows:
        if r['category'] != 'TUTORIAL_CONTROL':
            continue
        raw = bytes.fromhex(r['raw_hex'])
        segs, tail = au.decompose(raw)

        # 1. identity regression
        if parse_rendered(au.compose(segs, tail), cmap) != raw:
            report.append({'id': r['id'], 'state': 'IDENTITY_FAIL', 'slot': len(raw),
                           'need': '', 'headroom': '', 'detail': 'does not re-encode'})
            continue
        ident_ok += 1

        texts = [v for k, v in segs if k == 'T']
        if any(t in gl.DONOR_RUNS for t in texts):
            donor += 1
            report.append({'id': r['id'], 'state': 'DONOR_MISCLASSIFIED', 'slot': len(raw),
                           'need': '', 'headroom': '',
                           'detail': 'FR/ES branch text mis-scanned as english; not translated'})
            continue

        miss = [t for t in texts if any(c.isalpha() for c in t) and t not in gl.RUNS]
        if miss:
            human += 1
            for t in miss:
                missing_runs[t] += 1
            report.append({'id': r['id'], 'state': 'HUMAN', 'slot': len(raw), 'need': '',
                           'headroom': '',
                           'detail': 'no Korean for %d run(s): %r' % (len(miss), miss[0][:40])})
            continue

        src = au.compose(segs, tail, KO)
        bad = [c for c in src if ord(c) > 0x7F and c not in cmap]
        if bad:
            newglyph.update(bad)
            report.append({'id': r['id'], 'state': 'NEW_GLYPH', 'slot': len(raw), 'need': '',
                           'headroom': '', 'detail': 'chars outside global page: %s' % ''.join(sorted(set(bad)))})
            continue
        enc = parse_rendered(src, cmap)
        if len(enc) > len(raw):
            report.append({'id': r['id'], 'state': 'SLOT_OVERFLOW', 'slot': len(raw),
                           'need': len(enc), 'headroom': len(raw) - len(enc),
                           'detail': 'over by %d bytes' % (len(enc) - len(raw))})
            continue

        # control stream must be untouched
        if au.decompose(enc)[0].__len__() and \
           [v for k, v in au.decompose(enc)[0] if k == 'C'] != [v for k, v in segs if k == 'C']:
            report.append({'id': r['id'], 'state': 'CONTROL_CHANGED', 'slot': len(raw),
                           'need': len(enc), 'headroom': '', 'detail': 'control stream differs'})
            continue

        r['current_korean'] = src
        r['source'] = 'STAGE_CONTROL_2026-08-19'
        done += 1
        report.append({'id': r['id'], 'state': 'OK', 'slot': len(raw), 'need': len(enc),
                       'headroom': len(raw) - len(enc), 'detail': ''})

    with io.open(WORK, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)
    with io.open(os.path.join(ANALYSIS, 'stage-control-assemble.csv'), 'w',
                 encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
        w.writeheader()
        w.writerows(report)

    t = collections.Counter(x['state'] for x in report)
    print('identity regression : %d / %d' % (ident_ok, len(report)))
    print('rows OK             : %d' % done)
    for k in ('SLOT_OVERFLOW', 'HUMAN', 'DONOR_MISCLASSIFIED', 'NEW_GLYPH',
              'CONTROL_CHANGED', 'IDENTITY_FAIL'):
        if t.get(k):
            print('  %-20s %d' % (k, t[k]))
    print('new glyphs needed   : %d %s' % (len(newglyph), ''.join(sorted(newglyph))))
    if missing_runs:
        print('runs without Korean : %d' % len(missing_runs))
        for s, n in missing_runs.most_common(8):
            print('   x%-3d %r' % (n, s[:60]))
    over = [x for x in report if x['state'] == 'SLOT_OVERFLOW']
    for x in sorted(over, key=lambda y: y['headroom'])[:12]:
        print('   OVERFLOW id=%s slot=%s need=%s (%s)' % (x['id'], x['slot'], x['need'], x['detail']))


if __name__ == '__main__':
    main()
