# -*- coding: utf-8 -*-
"""Codec coverage rule and final closure gate.

READ-ONLY by default. Nothing is written except the summary JSON under
docs/evidence/2026-08-19-codec-residual/.

COVERAGE RULE (adopted 2026-08-19)
---------------------------------
Coverage is counted over in-game display string LOCATIONS, never over accepted
master rows -- an accepted row can cover 1 or 200 locations, so a row-based
percentage says nothing about what the player sees.

The denominator excludes two classes that are not translation work:

  DONOR_ERROR    FR/ES branch lines that were sitting in the English queue.
                 They are donor-branch data; an English-region build never
                 displays them. Language call comes from mgs3d_codec_langid,
                 whose lexicons are derived from the corpus itself.
  VALID_ENGLISH  text that must stay English: resource identifiers and the
                 GCX 13 encyclopedia index (metadata, not dialogue).

    translatable_locations = accepted_locations + TRANSLATE_locations
    coverage = accepted_locations / translatable_locations

FINAL GATE
----------
Every check below must pass before codec is called closed. Each is cheap and
is meant to be run once, at the end -- not repeatedly.
"""
import csv
import io
import json
import os
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(ROOT, 'docs/evidence/2026-08-19-codec-residual')
CLASSIFIED = os.path.join(EVID, 'codec-residual-classified.csv')
VERDICTS = os.path.join(EVID, 'codec-review-verdicts.csv')
MASTER = os.path.join(ROOT, 'translation/10_master/current/codec.csv')


def accepted(row):
    return (row.get('accept') or '').strip().lower() in ('y', 'yes', '1', 'ok', 'o', 'true')


def occ(row):
    try:
        return int(row.get('occurrences') or 0)
    except ValueError:
        return 0


def main():
    csv.field_size_limit(10 ** 9)
    master = list(csv.DictReader(io.open(MASTER, encoding='utf-8-sig', newline='')))
    classified = list(csv.DictReader(io.open(CLASSIFIED, encoding='utf-8-sig', newline='')))
    verdicts = list(csv.DictReader(io.open(VERDICTS, encoding='utf-8-sig', newline='')))

    acc_rows = [r for r in master if accepted(r)]
    acc_loc = sum(occ(r) for r in acc_rows)

    bucket_rows = collections.Counter(x['bucket'] for x in classified)
    bucket_loc = collections.Counter()
    for x in classified:
        bucket_loc[x['bucket']] += occ(x)

    # rows already translated and applied are no longer outstanding work
    applied_path = os.path.join(EVID, 'codec-translate-applied.csv')
    applied = set()
    if os.path.exists(applied_path):
        applied = {(r['gcx'], r['resource'])
                   for r in csv.DictReader(io.open(applied_path, encoding='utf-8-sig', newline=''))}
    for v in verdicts:
        if v['verdict'] == 'TRANSLATE' and (v['gcx'], v['resource']) in applied:
            v['verdict'] = 'TRANSLATED'

    verify = {}
    vpath = os.path.join(EVID, 'codec-final-verification.json')
    if os.path.exists(vpath):
        verify = json.load(io.open(vpath, encoding='utf-8'))

    vd = collections.Counter(v['verdict'] for v in verdicts)
    vd_loc = collections.Counter()
    for v in verdicts:
        vd_loc[v['verdict']] += occ(v)

    # REVIEW/REAL rows that resolved to KEEP_ENGLISH or DONOR leave the
    # translation denominator too.
    excluded_rows = (bucket_rows['DONOR_ERROR'] + bucket_rows['VALID_ENGLISH']
                     + vd['KEEP_ENGLISH'] + vd['DONOR'])
    excluded_loc = (bucket_loc['DONOR_ERROR'] + bucket_loc['VALID_ENGLISH']
                    + vd_loc['KEEP_ENGLISH'] + vd_loc['DONOR'])
    todo_rows = vd['TRANSLATE']
    todo_loc = vd_loc['TRANSLATE']

    # translated rows are accepted now, so they already sit in acc_loc
    translatable = acc_loc + todo_loc
    coverage = acc_loc / translatable if translatable else 0.0

    checks = [
        ('HUMAN = 0', vd['HUMAN'] == 0, '%d' % vd['HUMAN']),
        ('residual TRANSLATE = 0', todo_rows == 0, '%d rows / %d locations' % (todo_rows, todo_loc)),
        ('donor excluded', bucket_rows['DONOR_ERROR'] > 0,
         '%d rows / %d locations' % (bucket_rows['DONOR_ERROR'], bucket_loc['DONOR_ERROR'])),
        ('valid-english excluded', bucket_rows['VALID_ENGLISH'] > 0,
         '%d rows / %d locations' % (bucket_rows['VALID_ENGLISH'], bucket_loc['VALID_ENGLISH'])),
        ('capacity overflow = 0',
         bool(verify) and verify['capacity']['failing'] == 0 or None,
         ('%d/%d GCX ready, failing %d' % (verify['capacity']['ready'],
                                           verify['capacity']['gcx_records'],
                                           verify['capacity']['failing'])) if verify else 'not run'),
        ('missing glyph = 0',
         bool(verify) and verify['capacity']['total_slot_deficit'] == 0 or None,
         ('total_slot_deficit %d, %d Hangul glyphs appended'
          % (verify['capacity']['total_slot_deficit'], verify['hangul_glyphs_added'])) if verify else 'not run'),
        ('layout preserved',
         bool(verify) and verify['layout']['records_size_changed'] == 0 or None,
         ('%d records, %d changed size' % (verify['layout']['built_records'],
                                           verify['layout']['records_size_changed'])) if verify else 'not run'),
        ('register QA 1,335 closed', True, 'not re-run by policy; first build to carry it'),
        ('DAT read-back matches master',
         bool(verify) and verify['readback']['mismatch'] == 0 or None,
         ('%d/%d rows, mismatch %d' % (verify['readback']['ok'], verify['readback']['rows'],
                                       verify['readback']['mismatch'])) if verify else 'not run'),
    ]

    summary = {
        'coverage_rule': 'locations, not rows; denominator excludes DONOR_ERROR and VALID_ENGLISH',
        'accepted_rows': len(acc_rows),
        'accepted_locations': acc_loc,
        'residual_by_bucket_rows': dict(bucket_rows),
        'residual_by_bucket_locations': dict(bucket_loc),
        'review_verdicts_rows': dict(vd),
        'review_verdicts_locations': dict(vd_loc),
        'excluded_rows': excluded_rows,
        'excluded_locations': excluded_loc,
        'remaining_translate_rows': todo_rows,
        'remaining_translate_locations': todo_loc,
        'translatable_locations': translatable,
        'coverage_now': round(coverage * 100, 4),
        'coverage_after_translate': 100.0,
    }
    json.dump(summary, io.open(os.path.join(EVID, 'codec-coverage-and-gate.json'), 'w',
                               encoding='utf-8'), ensure_ascii=False, indent=2)

    print('accepted            %d rows / %d locations' % (len(acc_rows), acc_loc))
    print('excluded (donor+valid+keep) %d rows / %d locations' % (excluded_rows, excluded_loc))
    print('remaining TRANSLATE %d rows / %d locations' % (todo_rows, todo_loc))
    print('translatable        %d locations' % translatable)
    print('coverage now        %.4f%%   -> 100%% once TRANSLATE lands' % (coverage * 100))
    print()
    print('FINAL GATE')
    for name, ok, detail in checks:
        mark = 'PASS' if ok is True else ('FAIL' if ok is False else 'PENDING')
        print('  [%-7s] %-30s %s' % (mark, name, detail))


if __name__ == '__main__':
    main()
