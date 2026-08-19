# -*- coding: utf-8 -*-
"""Line-composed batch for the template-heavy stage categories.

FLORA_FAUNA and the other survival-viewer text are built from a small set of
repeated lines (name / description / taste verdict) recombined per species:
921 line instances over only 382 distinct lines. Translating whole strings
would re-author the same sentence dozens of times, so this runner translates
per line and recomposes the row, preserving the raw line structure exactly.

The row's slot is still the gate -- the composed Korean, not the individual
line, must fit.
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

# Rows already given a terminal state are never re-opened by a batch.
TERMINAL = ('KEEP_ENGLISH', 'DONOR_MISCLASSIFIED', 'HUMAN')


def escape(text):
    return ''.join('<%02X>' % ord(c) if ord(c) < 0x20 or c in '<>' else c for c in text)


def lines_of(raw_hex):
    segs, tail = au.decompose(bytes.fromhex(raw_hex))
    if any(k in ('C', 'G') for k, _ in segs):
        return None, None
    return ''.join(v for k, v in segs if k == 'T'), tail


def inventory(category):
    """Distinct lines of a category, most frequent first, with byte budgets."""
    csv.field_size_limit(10 ** 9)
    freq = collections.Counter()
    tight = {}
    for r in csv.DictReader(io.open(WORK, encoding='utf-8-sig', newline='')):
        if r['category'] != category or (r.get('current_korean') or '').strip():
            continue
        if (r.get('status') or '').strip() in TERMINAL:
            continue
        text, _ = lines_of(r['raw_hex'])
        if text is None:
            continue
        slot = len(bytes.fromhex(r['raw_hex']))
        slack = slot - 1 - len(text)          # spare bytes for the whole row
        for x in text.split('\n'):
            if not x.strip():
                continue
            freq[x] += 1
            tight[x] = min(tight.get(x, 10 ** 9), len(x) + slack)
    return freq, tight


def run_batch(category, table, label, limit=None):
    """table maps one source line -> Korean. Rows compose from it."""
    csv.field_size_limit(10 ** 9)
    cmap = {k: bytes.fromhex(v) for k, v in
            json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].items()}
    with io.open(WORK, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    report = []
    done = 0
    missing = collections.Counter()
    newglyph = set()
    for r in rows:
        if r['category'] != category or (r.get('current_korean') or '').strip():
            continue
        if (r.get('status') or '').strip() in TERMINAL:
            continue
        raw = bytes.fromhex(r['raw_hex'])
        text, tail = lines_of(r['raw_hex'])
        if text is None:
            report.append({'id': r['id'], 'state': 'NEEDS_CONTROL_PATH', 'slot': len(raw),
                           'need': '', 'detail': ''})
            continue
        parts = text.split('\n')
        out, miss = [], []
        for x in parts:
            if not x.strip():
                out.append(x)
                continue
            ko = table.get(x)
            if ko is None:
                miss.append(x)
                out.append(x)
            else:
                out.append(ko)
        if miss:
            for x in miss:
                missing[x] += 1
            report.append({'id': r['id'], 'state': 'MISSING_LINE', 'slot': len(raw),
                           'need': '', 'detail': repr(miss[0][:60])})
            continue
        ko_text = '\n'.join(out)
        bad = [c for c in ko_text if ord(c) > 0x7F and c not in cmap]
        if bad:
            newglyph.update(bad)
            report.append({'id': r['id'], 'state': 'NEW_GLYPH', 'slot': len(raw),
                           'need': '', 'detail': ''.join(sorted(set(bad)))})
            continue
        src = escape(ko_text) + au.esc_bytes(tail)
        enc = parse_rendered(src, cmap)
        if len(enc) > len(raw):
            report.append({'id': r['id'], 'state': 'SLOT_OVERFLOW', 'slot': len(raw),
                           'need': len(enc), 'detail': repr(text[:70])})
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
    if report:
        dest = os.path.join(ANALYSIS, 'stage-line-batch-%s.csv' % category.lower())
        with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
            w.writeheader()
            w.writerows(report)

    t = collections.Counter(x['state'] for x in report)
    print('%s: %d rows considered' % (category, len(report)))
    print('  OK                 %d' % done)
    for k in ('MISSING_LINE', 'SLOT_OVERFLOW', 'NEW_GLYPH', 'NEEDS_CONTROL_PATH'):
        if t.get(k):
            print('  %-18s %d' % (k, t[k]))
    print('  new glyphs         %d %s' % (len(newglyph), ''.join(sorted(newglyph))))
    shown = 0
    for x in report:
        if x['state'] == 'SLOT_OVERFLOW' and shown < (limit or 20):
            print('   OVER slot=%s need=%s %s' % (x['slot'], x['need'], x['detail']))
            shown += 1
    if missing:
        print('  lines without Korean: %d distinct' % len(missing))
        for s, n in missing.most_common(limit or 40):
            print('   x%-3d %r' % (n, s))
    return t


if __name__ == '__main__':
    freq, tight = inventory(sys.argv[1])
    off = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
    print('# %s : %d distinct lines, %d instances' % (sys.argv[1], len(freq), sum(freq.values())))
    for s, n in freq.most_common()[off:off + lim]:
        print('x%-4d b=%-4d %r' % (n, tight[s], s))
