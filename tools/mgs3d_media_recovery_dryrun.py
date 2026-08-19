# -*- coding: utf-8 -*-
"""Dry-run patch plan for the movie/demo misplaced-line recovery.

READ-ONLY. Writes nothing into master, *.dat, staging or the reviewed verdict
CSV. It produces:

  * the change set (one row per DAT location that would be written)
  * capacity-check input CSVs -- a copy of master with the proposed Korean
    substituted in, which is exactly what a real build would encode
  * nothing else; applying is a separate, approved step

The byte check is delegated to the real encoder:
    tools/mgs3d_movie_tool.py capacity <dat> <csv> <json> --static-allocation ...
which reports needed_bytes / capacity_bytes per entry and font_deficit per
record, using the same encode_translation() / wrap_like_source() path the
builder uses.
"""
import csv
import io
import json
import os
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
RECOVERY = os.path.join(EVID, 'media-misplaced-recovery.csv')

# The clean-tree romfs is the reference build the master offsets were captured
# against. originals/3ds_pristine is a DIFFERENT, smaller region build -- see
# the note at the top of tools/mgs3d_capacity_recheck.py.
CLEAN = os.path.join(ROOT, 'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs')
DAT = {'movie': os.path.join(CLEAN, 'movie.dat'),
       'demo': os.path.join(CLEAN, 'demo.dat')}

# Verdicts settled in the pre-apply review (2026-08-19 evening).
# The four extra suspects were KEEP in the reviewed CSV but read as MISPLACED
# against the transcript; their recovered Korean is recorded here.
SUSPECT_PROMOTIONS = {
    ('demo', '141', '3'): ('그만둬!!', 'shinsnote p14 seq2845', '소코로프 (Sokolov)'),
    ('demo', '154', '4'): ('이제 알겠지. 너무 늦었다는 의미를.', 'shinsnote p14 seq2869', '소코로프 (Sokolov)'),
    ('demo', '156', '29'): ('에바?', 'shinsnote p14 seq2881', '스네이크 (Snake)'),
    ('demo', '240', '21'): ('처음으로 당신의 약한 소릴 들었어.', 'shinsnote p19 seq3793', '스네이크 (Snake)'),
}

# HUMAN rows whose position was confirmed correct -- they are NOT patched.
KEEP_REVERTS = {('demo', '29', '13'), ('demo', '61', '30'), ('movie', '18', '4')}

PLAN_COLS = ['media', 'record', 'entry', 'offset', 'english', 'current_korean',
             'new_korean', 'replacement_source', 'speaker', 'origin',
             'duplicate_group', 'typo_fix']

# Proposals that silently correct an obvious typo in the transcript source.
TYPO_FIXES = {
    ('demo', '82', '6'): ('2족 보행전자?', '2족 보행전차?', 'shinsnote p11 seq2168'),
    ('demo', '203', '5'): ('예, 그게 임무니가요', '예, 그게 임무니까요.', 'shinsnote p16 seq3318'),
    ('demo', '101', '24'): ('아니, 나도 마찬가지로.. 상처 투성이다.', '아니, 나도 마찬가지로.. 상처 투성이다.', 'shinsnote p13 seq2510'),
}


def load_master():
    master, byoffset = {}, {}
    for media, path in ctx.MASTER.items():
        for r in ctx.read_csv(path):
            master.setdefault((media, r['record']), []).append(r)
            byoffset[(media, r['record'], r['entry'])] = r
    for v in master.values():
        v.sort(key=lambda r: int(r['entry']))
    return master, byoffset


def preview(e):
    return (e['preview'] or '').replace('<END>', '').strip()


def duplicate_links(master):
    """(media, record, entry) -> group id, for entries that share both their
    English text and their immediate neighbours' English text."""
    byen = collections.defaultdict(list)
    for (media, rec), ents in master.items():
        for i, e in enumerate(ents):
            byen[(media, preview(e))].append((rec, i))

    def win(media, rec, i):
        ents = master[(media, rec)]
        return tuple(preview(ents[j]) if 0 <= j < len(ents) else None
                     for j in (i - 1, i, i + 1))

    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (media, rec), ents in master.items():
        for i, e in enumerate(ents):
            key = (media, rec, e['entry'])
            parent.setdefault(key, key)
            for rr, jj in byen[(media, preview(e))]:
                if (rr, jj) == (rec, i):
                    continue
                if win(media, rr, jj) != win(media, rec, i):
                    continue
                other = (media, rr, master[(media, rr)][jj]['entry'])
                parent.setdefault(other, other)
                union(key, other)
    groups = collections.defaultdict(list)
    for k in parent:
        groups[find(k)].append(k)
    out = {}
    gid = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        gid += 1
        for m in sorted(members):
            out[m] = 'DUP%02d' % gid
    return out


def main():
    outdir = os.path.join(EVID, 'dryrun')
    os.makedirs(outdir, exist_ok=True)
    master, byoffset = load_master()
    dupmap = duplicate_links(master)

    recovery = ctx.read_csv(RECOVERY)
    plan = []
    for r in recovery:
        key = (r['media'], r['record'], r['entry'])
        if key in KEEP_REVERTS or r['action'] != 'REPLACE':
            continue
        m = byoffset[key]
        plan.append({
            'media': r['media'], 'record': r['record'], 'entry': r['entry'],
            'offset': m['offset'], 'english': preview(m),
            'current_korean': m['korean'], 'new_korean': r['replacement_korean'],
            'replacement_source': r['replacement_source'], 'speaker': r['speaker'],
            'origin': 'reviewed-MISPLACED', 'duplicate_group': dupmap.get(key, ''),
            'typo_fix': 'YES' if key in TYPO_FIXES else '',
        })
    for key, (ko, src, spk) in SUSPECT_PROMOTIONS.items():
        m = byoffset[key]
        plan.append({
            'media': key[0], 'record': key[1], 'entry': key[2],
            'offset': m['offset'], 'english': preview(m),
            'current_korean': m['korean'], 'new_korean': ko,
            'replacement_source': src, 'speaker': spk,
            'origin': 'extra-suspect-promoted', 'duplicate_group': dupmap.get(key, ''),
            'typo_fix': '',
        })
    plan.sort(key=lambda r: (r['media'], int(r['record']), int(r['entry'])))

    with io.open(os.path.join(outdir, 'media-recovery-patch-plan.csv'), 'w',
                 encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=PLAN_COLS, lineterminator='\r\n')
        w.writeheader()
        w.writerows(plan)

    # capacity-check input: master with the proposed Korean substituted in
    changes = dict(((p['media'], p['record'], p['entry']), p['new_korean']) for p in plan)
    for media, path in ctx.MASTER.items():
        rows = ctx.read_csv(path)
        n = 0
        for r in rows:
            k = (media, r['record'], r['entry'])
            if k in changes:
                r['korean'] = changes[k]
                r['accept'] = 'yes'
                n += 1
        dest = os.path.join(outdir, '%s-with-recovery.csv' % media)
        with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator='\r\n')
            w.writeheader()
            w.writerows(rows)
        print('%-6s capacity input: %d rows, %d substituted -> %s'
              % (media, len(rows), n, os.path.basename(dest)))

    bym = collections.Counter(p['media'] for p in plan)
    byo = collections.Counter(p['origin'] for p in plan)
    ingroup = [p for p in plan if p['duplicate_group']]
    print()
    print('patch plan locations   %d  %s' % (len(plan), dict(bym)))
    print('origin                 %s' % dict(byo))
    print('inside duplicate group %d across %d groups'
          % (len(ingroup), len(set(p['duplicate_group'] for p in ingroup))))
    print('keep-reverts excluded  %d' % len(KEEP_REVERTS))
    print()
    print('next: run tools/mgs3d_movie_tool.py capacity for each media')
    for media in ('movie', 'demo'):
        print('  %s -> %s' % (media, DAT[media]))


if __name__ == '__main__':
    main()
