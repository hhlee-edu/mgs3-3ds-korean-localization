# -*- coding: utf-8 -*-
"""Apply the approved movie/demo misplaced-line recovery to master.

Scope approved 2026-08-19: apply_status=APPLY_NOW rows only, plus typo fixes
T1/T2/T3. OVERFLOW_HOLD / HUMAN / NO_SOURCE rows are left untouched.

Touches ONLY translation/10_master/current/{demo,movie}.csv. It does not
rebuild any .dat, does not touch staging, and does not commit.
"""
import csv
import io
import os
import shutil
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
PLAN = os.path.join(EVID, 'media-recovery-patch-plan.csv')
STAMP = 'bak-pre-misplaced-recovery-20260819'

# T3: approved 2026-08-19. The transcript's two-dot ellipsis is normalised to
# three dots. Must be applied to BOTH members of duplicate pair DUP11.
T3 = {
    ('demo', '101', '24'): ('아니, 나도 마찬가지로.. 상처 투성이다.',
                            '아니, 나도 마찬가지로... 상처 투성이다.'),
    ('demo', '107', '28'): ('아니, 나도 마찬가지로.. 상처 투성이다.',
                            '아니, 나도 마찬가지로... 상처 투성이다.'),
}


def main():
    plan = ctx.read_csv(PLAN)
    apply_rows = [r for r in plan if r['apply_status'] == 'APPLY_NOW']
    hold_rows = [r for r in plan if r['apply_status'] != 'APPLY_NOW']

    changes = {}
    for r in apply_rows:
        key = (r['media'], r['record'], r['entry'])
        text = r['new_korean']
        if key in T3:
            before, after = T3[key]
            if text != before:
                raise SystemExit('T3 precondition failed for %s: plan holds %r' % (key, text))
            text = after
        changes[key] = text

    # every T3 location must be inside the approved apply set
    for key in T3:
        if key not in changes:
            raise SystemExit('T3 location %s is not in the APPLY_NOW set' % (key,))

    # duplicate-pair integrity: groups must not be split across apply/hold
    groups = collections.defaultdict(set)
    for r in plan:
        if r['duplicate_group']:
            groups[r['duplicate_group']].add(r['apply_status'])
    split = [g for g, v in groups.items() if len(v) > 1]
    if split:
        raise SystemExit('duplicate group split across apply/hold: %s' % split)

    total = 0
    for media, path in ctx.MASTER.items():
        wanted = {k: v for k, v in changes.items() if k[0] == media}
        if not wanted:
            print('%-6s no approved changes -- file untouched' % media)
            continue
        backup = '%s.%s' % (path, STAMP)
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        with io.open(path, encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            cols = reader.fieldnames
        applied, unchanged = 0, []
        for r in rows:
            key = (media, r['record'], r['entry'])
            if key in wanted:
                if r['korean'] == wanted[key]:
                    unchanged.append(key)
                r['korean'] = wanted[key]
                r['accept'] = 'yes'
                r['translation_source'] = 'the script reference-recovery-2026-08-19'
                applied += 1
        if applied != len(wanted):
            raise SystemExit('%s: expected %d rows, matched %d' % (media, len(wanted), applied))
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
            w.writeheader()
            w.writerows(rows)
        total += applied
        print('%-6s applied %d rows (backup: %s)' % (media, applied, os.path.basename(backup)))
        if unchanged:
            print('       %d row(s) already held the target text' % len(unchanged))

    print()
    print('applied total     %d' % total)
    print('typo T1/T2        included in the plan text')
    print('typo T3           %d location(s) normalised' % len(T3))
    print('held back         %d (overflow)' % len(hold_rows))


if __name__ == '__main__':
    main()
