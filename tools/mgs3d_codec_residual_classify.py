# -*- coding: utf-8 -*-
"""Classify the codec residual (still-English) rows into the four work buckets.

READ-ONLY. Reads translation/10_master/current/codec.csv and writes only into
docs/evidence/2026-08-19-codec-residual/.

The language call is delegated to tools/mgs3d_codec_langid.py, whose lexicons
are derived from the corpus itself (donor vocabulary from <1F..> accent escapes,
English vocabulary from is_donor=no rows). Hand-written stopword lists were
already shown to leak short donor lines such as "Ouais." / "Exacto." into the
English queue, so they are not used here.

Buckets
  DONOR_ERROR       langid says donor - a FR/ES line sitting in the English queue
  VALID_ENGLISH     English that must stay English: resource identifiers and the
                    GCX 13 encyclopedia index
  REAL_UNTRANSLATED langid says english, real display text, no Korean yet
  REVIEW            langid cannot separate it (neutral) - needs a human read
"""
import csv
import io
import json
import os
import sys
import collections
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
_spec = importlib.util.spec_from_file_location(
    'langid', os.path.join(ROOT, 'tools/mgs3d_codec_langid.py'))
langid = importlib.util.module_from_spec(_spec)
sys.modules['langid'] = langid
_spec.loader.exec_module(langid)

MASTER = os.path.join(ROOT, 'translation/10_master/current/codec.csv')
OUT = os.path.join(ROOT, 'docs/evidence/2026-08-19-codec-residual')
GCX_ENCYCLOPEDIA = '13'

COLS = ['bucket', 'reason', 'gcx', 'resource', 'occurrences', 'text_kind',
        'language', 'is_donor', 'translate', 'status', 'english', 'korean',
        'langid', 'donor_hits', 'english_hits', 'record_headroom', 'note']


def accepted(row):
    return (row.get('accept') or '').strip().lower() in ('y', 'yes', '1', 'ok', 'o', 'true')


def main():
    csv.field_size_limit(10 ** 9)
    os.makedirs(OUT, exist_ok=True)

    with io.open(MASTER, encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))

    # Residual = rows that still carry English into the build: not accepted and
    # not already known to be a donor-branch entry.
    residual = [r for r in rows
                if not accepted(r) and (r.get('is_donor') or '') != 'yes']

    donor_only, eng_only = langid.build()

    out = []
    for r in residual:
        verdict, d, e = langid.classify(r.get('english') or '', donor_only, eng_only)
        if verdict == 'donor':
            bucket, reason = 'DONOR_ERROR', 'langid: donor vocabulary only'
        elif r.get('text_kind') == 'identifier':
            bucket, reason = 'VALID_ENGLISH', 'resource identifier - not display text'
        elif r.get('gcx') == GCX_ENCYCLOPEDIA:
            bucket, reason = 'VALID_ENGLISH', 'GCX 13 encyclopedia index - metadata'
        elif verdict == 'english':
            if (r.get('korean') or '').strip():
                bucket, reason = 'REVIEW', 'English but a Korean draft already exists'
            else:
                bucket, reason = 'REAL_UNTRANSLATED', 'langid: English vocabulary only'
        else:
            bucket, reason = 'REVIEW', 'langid: neutral - no separating vocabulary'
        out.append({
            'bucket': bucket, 'reason': reason,
            'gcx': r.get('gcx'), 'resource': r.get('resource'),
            'occurrences': r.get('occurrences'), 'text_kind': r.get('text_kind'),
            'language': r.get('language'), 'is_donor': r.get('is_donor'),
            'translate': r.get('translate'), 'status': r.get('status'),
            'english': r.get('english'), 'korean': r.get('korean'),
            'langid': verdict, 'donor_hits': d, 'english_hits': e,
            'record_headroom': r.get('record_headroom'), 'note': r.get('note'),
        })

    order = {'REVIEW': 0, 'REAL_UNTRANSLATED': 1, 'VALID_ENGLISH': 2, 'DONOR_ERROR': 3}
    out.sort(key=lambda x: (order[x['bucket']], -int(x['occurrences'] or 0)))
    with io.open(os.path.join(OUT, 'codec-residual-classified.csv'), 'w',
                 encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator='\r\n')
        w.writeheader()
        w.writerows(out)

    tally = collections.Counter(x['bucket'] for x in out)
    occ = collections.Counter()
    for x in out:
        try:
            occ[x['bucket']] += int(x['occurrences'] or 0)
        except ValueError:
            pass
    summary = {
        'master_rows': len(rows),
        'accepted_rows': sum(1 for r in rows if accepted(r)),
        'residual_rows': len(out),
        'by_bucket': dict(tally),
        'occurrences_by_bucket': dict(occ),
        'langid_lexicon': {'donor_only_tokens': len(donor_only),
                           'english_only_tokens': len(eng_only)},
    }
    json.dump(summary, io.open(os.path.join(OUT, 'codec-residual-summary.json'), 'w',
                               encoding='utf-8'), ensure_ascii=False, indent=2)

    print('residual rows %d' % len(out))
    for b in ('REVIEW', 'REAL_UNTRANSLATED', 'VALID_ENGLISH', 'DONOR_ERROR'):
        print('  %-18s %5d   (%d locations)' % (b, tally.get(b, 0), occ.get(b, 0)))
    print()
    print('langid lexicon: donor-only %d / english-only %d'
          % (len(donor_only), len(eng_only)))


if __name__ == '__main__':
    main()
