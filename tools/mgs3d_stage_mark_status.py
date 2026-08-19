# -*- coding: utf-8 -*-
"""Record a terminal state for stage rows that are not going to be translated.

Writes only the working sheet's `status` and `note` columns; `current_korean`
stays empty so the apply path never targets these rows.

States:
  KEEP_ENGLISH         deliberately left in the source script (jukebox track
                       and artist names, romanized Russian proper nouns)
  DONOR_MISCLASSIFIED  the string is FR/ES branch text the scanner labelled
                       english; translating it would corrupt the donor branch
  HUMAN                needs a human decision (no Korean fits the slot without
                       losing meaning)
"""
import csv
import io
import os
import sys
import importlib.util
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location(
    'au', os.path.join(ROOT, 'tools/mgs3d_stage_control_author.py'))
au = importlib.util.module_from_spec(_s)
sys.modules['au'] = au
_s.loader.exec_module(au)

ANALYSIS = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')
WORK = os.path.join(ANALYSIS, 'stage-translation-working.csv')


def _plain(raw_hex):
    segs, _ = au.decompose(bytes.fromhex(raw_hex))
    return ''.join(v for k, v in segs if k == 'T')


def mark(entries, verbose=True):
    """entries: iterable of (category, texts|None, status, note).

    texts=None marks every still-untranslated row of that category.
    """
    csv.field_size_limit(10 ** 9)
    with io.open(WORK, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    tally = collections.Counter()
    unmatched = []
    for category, texts, status, note in entries:
        want = None if texts is None else set(texts)
        hit = set()
        for r in rows:
            if r['category'] != category or (r.get('current_korean') or '').strip():
                continue
            text = _plain(r['raw_hex'])
            if want is not None and text not in want:
                continue
            r['status'] = status
            r['note'] = note
            tally[(category, status)] += 1
            hit.add(text)
        if want is not None:
            for t in want - hit:
                unmatched.append((category, status, t))

    with io.open(WORK, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)

    if verbose:
        for (cat, st), n in sorted(tally.items()):
            print('  %-16s %-20s %d' % (cat, st, n))
        for cat, st, t in unmatched:
            print('  UNMATCHED %s %s %r' % (cat, st, t[:60]))
    return tally, unmatched
