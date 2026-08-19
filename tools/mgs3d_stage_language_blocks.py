# -*- coding: utf-8 -*-
"""Decide, structurally, which stage resources belong to the English branch.

Why this exists
---------------
The stage scanner's `language` column is not trustworthy for short labels. A
GCX record lays the same string list out once per language, and many medical /
loan words are spelled identically in English and Spanish, so the scanner marks
them english wherever they appear. Measured in stage hx001a record 0:

    6160 'Gastrite\\n'   <- French block
    6454 'Proctitis\\n'  <- Spanish block (neighbours: 'Herida de bala',
    6470 'Hypoxia\\n'        'Golpe recibido', 'Dolor de est<1f>tmago')
    6808 'Gastritis\\n'  <- English block
    6794 'Hypoxia\\n'    <- English block

Translating 6454/6470 would write Korean straight into the Spanish branch while
the final gate's fr_es_unchanged check still passed, because that check only
looks at locations the scanner already labelled donor.

How it decides
--------------
Per record, each resource votes: +1 if it carries unmistakably English function
words, -1 if it carries an accent escape (0x1F) or unmistakably Romance/German
function words, 0 otherwise. A resource's branch is the sign of the vote sum
over a +/-60 resource window, so a short ambiguous label inherits the language
of the block it physically sits in. Votes are structural evidence about
neighbours, never about the label itself.
"""
import io
import json
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from mgs3d_stage_text_scan import stage_records  # noqa: E402
from pathlib import Path  # noqa: E402

STAGE = Path(ROOT) / 'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/stage'
OUT = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')

EN = re.compile(
    r'\b(the|and|you|your|with|that|this|from|will|have|been|when|not|but|are|'
    r'was|were|for|its|use|used|using|can|only|found|native|large|small|Select|'
    r'Press|Touch|Wound|Sustained|Yes|No|Continue|memory card|failed|Insert)\b')
NON_EN = re.compile(
    r'\b(de|del|la|el|los|las|una|uno|con|sin|para|por|que|se|su|est|al|'
    r'le|les|du|des|une|dans|pour|avec|sur|est|sont|vous|votre|ne|pas|'
    r'der|die|das|und|mit|nicht|ist|sie|ein|eine|den|dem|'
    r'il|lo|gli|una|per|non|sono|che|del|nel|alla)\b')


def vote(text):
    """+1 English, -1 non-English, 0 no evidence.

    An accent escape (0x1F) only counts against English when the line has no
    English function words at all. English menus here are full of accented
    loanwords -- 'Saut<1f>ed in Apple Sauce', 'Caf<1f>' -- and treating the
    escape as decisive put the English food menu in the donor bucket.
    """
    e = len(EN.findall(text))
    n = len(NON_EN.findall(text))
    if '\x1f' in text and not e:
        n += 2
    if e > n:
        return 1
    if n > e:
        return -1
    return 0


def branch_map():
    """(stage, record, resource) -> 'english' | 'donor' | 'unknown'.

    Nearest-signal with a distance cap. Uncapped nearest-signal reaches across
    block boundaries and mislabels whole runs of bare item names; a windowed
    sum is worse still, because four of the five language blocks are non-English
    and the sum drowns the English block. Capping the search means a resource
    with no signalling neighbour is reported 'unknown' instead of guessed.
    """
    out = {}
    for path in sorted(STAGE.glob('*/scenerio.gcx')):
        stage = path.parent.name
        for ri, rec in enumerate(stage_records(path)):
            res = rec.resources()
            n = len(res)
            sig = [vote(r.data.split(bytes(1), 1)[0].decode('latin1')) for r in res]
            left, last = [None] * n, None
            for i in range(n):
                if sig[i]:
                    last = (i, sig[i])
                left[i] = None if last is None else (i - last[0], last[1])
            right, last = [None] * n, None
            for i in range(n - 1, -1, -1):
                if sig[i]:
                    last = (i, sig[i])
                right[i] = None if last is None else (last[0] - i, last[1])
            for i in range(n):
                l, r = left[i], right[i]
                verdict = 'unknown'
                for cap in (8, 25, 60):
                    cl = l if l and l[0] <= cap else None
                    cr = r if r and r[0] <= cap else None
                    if not cl and not cr:
                        continue
                    if not cl:
                        pick = cr
                    elif not cr:
                        pick = cl
                    elif cl[0] != cr[0]:
                        pick = cl if cl[0] < cr[0] else cr
                    else:
                        pick = cl if abs(cl[1]) >= abs(cr[1]) else cr
                    verdict = 'english' if pick[1] > 0 else 'donor'
                    break
                out[(stage, ri, i)] = verdict
    return out


def main():
    import csv
    csv.field_size_limit(10 ** 9)
    bm = branch_map()
    locs = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-text-scan/stage-text-locations.csv')
    per_row = collections.defaultdict(collections.Counter)
    for r in csv.DictReader(io.open(locs, encoding='utf-8-sig', newline='')):
        if r['language'] != 'english':
            continue
        key = (r['stage'], int(r['record']), int(r['resource']))
        per_row[r['raw_hex']][bm.get(key, 'donor')] += 1
    doc = {k: dict(v) for k, v in per_row.items()}
    dest = os.path.join(OUT, 'stage-branch-map.json')
    io.open(dest, 'w', encoding='utf-8').write(json.dumps(doc, ensure_ascii=False))
    tot = collections.Counter()
    for v in per_row.values():
        tot['rows'] += 1
        if not v.get('english'):
            tot['rows_entirely_in_donor_blocks'] += 1
        elif v.get('donor'):
            tot['rows_mixed'] += 1
    print(json.dumps(dict(tot), indent=2))
    print('-> %s' % os.path.relpath(dest, ROOT))


if __name__ == '__main__':
    main()
