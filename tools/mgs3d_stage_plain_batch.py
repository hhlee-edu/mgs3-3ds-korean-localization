# -*- coding: utf-8 -*-
"""Translate a batch of plain-text stage rows and validate them against slots.

READ-ONLY except the working sheet and its report. scenerio.gcx, staging and
the analysis authority are never written.

Plain rows carry no control tokens, so the whole resource text is one unit.
Line breaks are real 0x0A bytes and are preserved as <0A> escapes; the source's
own line structure is kept because these strings are laid out per line on a
fixed-width screen.

Checks per row, in order:
  1. the row really is plain (no control tokens) -- otherwise it must go through
     mgs3d_stage_control_author.py instead
  2. every character is in the resident global page (new glyphs = 0)
  3. assembled resource bytes <= original slot
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


def escape(text):
    """Korean text -> parse_rendered source.

    Control bytes become <hh>. A literal '<' or '>' must also be escaped:
    parse_rendered() reads them as escape delimiters and refuses them raw
    (hit 2026-08-19 by the RESULTS breadcrumb 'DATA > TOTAL').
    """
    return ''.join('<%02X>' % ord(c) if ord(c) < 0x20 or c in '<>' else c
                   for c in text)


def run_batch(category, table, label):
    """table maps the resource's plain English text -> Korean."""
    csv.field_size_limit(10 ** 9)
    cmap = {k: bytes.fromhex(v) for k, v in
            json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].items()}
    with io.open(WORK, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    report = []
    done = skipped = 0
    newglyph = set()
    for r in rows:
        if r['category'] != category or (r.get('current_korean') or '').strip():
            continue
        raw = bytes.fromhex(r['raw_hex'])
        segs, tail = au.decompose(raw)
        if any(k in ('C', 'G') for k, _ in segs):
            report.append({'state': 'NEEDS_CONTROL_PATH', 'slot': len(raw), 'need': '',
                           'english': r['english'][:70], 'korean': ''})
            continue
        text = ''.join(v for k, v in segs if k == 'T')
        ko = table.get(text)
        if ko is None:
            skipped += 1
            report.append({'state': 'NOT_IN_BATCH', 'slot': len(raw), 'need': '',
                           'english': r['english'][:70], 'korean': ''})
            continue
        src = escape(ko) + au.esc_bytes(tail)
        bad = [c for c in ko if ord(c) > 0x7F and c not in cmap]
        if bad:
            newglyph.update(bad)
            report.append({'state': 'NEW_GLYPH', 'slot': len(raw), 'need': '',
                           'english': r['english'][:70], 'korean': ''.join(sorted(set(bad)))})
            continue
        enc = parse_rendered(src, cmap)
        if len(enc) > len(raw):
            report.append({'state': 'SLOT_OVERFLOW', 'slot': len(raw), 'need': len(enc),
                           'english': r['english'][:70], 'korean': ko[:60]})
            continue
        r['current_korean'] = src
        r['source'] = label
        done += 1
        report.append({'state': 'OK', 'slot': len(raw), 'need': len(enc),
                       'english': r['english'][:70], 'korean': ko[:60]})

    with io.open(WORK, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)
    if not report:
        print('%s: nothing left to do' % category)
        return collections.Counter()
    dest = os.path.join(ANALYSIS, 'stage-batch-%s.csv' % category.lower())
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
        w.writeheader()
        w.writerows(report)

    t = collections.Counter(x['state'] for x in report)
    print('%s: %d rows considered' % (category, len(report)))
    print('  OK                 %d' % done)
    for k in ('SLOT_OVERFLOW', 'NEW_GLYPH', 'NOT_IN_BATCH', 'NEEDS_CONTROL_PATH'):
        if t.get(k):
            print('  %-18s %d' % (k, t[k]))
    print('  new glyphs         %d %s' % (len(newglyph), ''.join(sorted(newglyph))))
    for x in report:
        if x['state'] == 'SLOT_OVERFLOW':
            print('   OVER slot=%s need=%s  %r' % (x['slot'], x['need'], x['english'][:56]))
        if x['state'] == 'NEW_GLYPH':
            print('   GLYPH %s  %r' % (x['korean'], x['english'][:56]))
    return t
