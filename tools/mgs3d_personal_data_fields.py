# -*- coding: utf-8 -*-
"""Dump the clean-English field structure of the PERSONAL DATA rows.

READ-ONLY. The clean English resource is the layout authority: its control
stream is 0A x 9 + 00, i.e. 10 display lines. The current Korean collapsed all
of them onto one line, so this prints the English fields in order next to the
current Korean tokens, which is the input for the field split.
"""
import csv
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from mgs3d_codec_tool import parse_codec  # noqa: E402

CLEAN = os.path.join(ROOT, 'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat')
MASTER = os.path.join(ROOT, 'translation/10_master/current/codec.csv')


def rows():
    csv.field_size_limit(10 ** 9)
    recs = parse_codec(open(CLEAN, 'rb').read())
    out = []
    for r in csv.DictReader(io.open(MASTER, encoding='utf-8-sig', newline='')):
        if 'PERSONAL DATA' not in (r.get('english') or ''):
            continue
        ko = (r.get('korean') or '').strip()
        gi, gj = int(r['gcx']), int(r['resource'])
        body = recs[gi].resources()[gj].data.split(b'\x00', 1)[0]
        fields = [f.decode('latin1') for f in body.split(b'\x0A')]
        nloc = len([p for p in (r.get('locations') or '').split(';') if ':' in p])
        out.append({'gcx': gi, 'resource': gj, 'locations': nloc, 'korean': ko,
                    'fields': fields, 'is_donor': r.get('is_donor'),
                    'lf': body.count(b'\x0A')})
    return out


if __name__ == '__main__':
    only_ko = '--with-korean' in sys.argv
    for i, r in enumerate(rows()):
        if only_ko and not r['korean']:
            continue
        print('=== %d  gcx %d / res %d   loc %d   donor=%s   clean 0A=%d' %
              (i, r['gcx'], r['resource'], r['locations'], r['is_donor'], r['lf']))
        for k, f in enumerate(r['fields']):
            print('   L%-2d %r' % (k, f))
        print('   KO  %s' % r['korean'])
