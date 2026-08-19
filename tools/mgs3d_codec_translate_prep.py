# -*- coding: utf-8 -*-
"""Prepare the codec TRANSLATE rows for a later translation pass.

READ-ONLY. No translation is written here and master is not touched. It only
assembles, per row, everything the translator will need:

  draft state   contaminated / blank / recoverable
  context       the neighbouring resources in the same GCX
  speaker       from the MHamlin English game script, when the line is in it
  recovery      an existing accepted Korean for the same English elsewhere in
                master, and any the script reference line that matches
  budget        the resource's own byte capacity and the GCX glyph-slot headroom
  grouping      rows that share an English string translate once

Byte capacity is the resource's current length in the clean-tree codec.dat,
which is the ceiling a fixed-layout rebuild has to stay inside. Glyph headroom
is the number of font slots the GCX frees when its replaced resources are
blanked -- the same quantity tools/mgs3d_gcx_font_tool.py capacity reports as
freed_slots.
"""
import csv
import io
import json
import os
import re
import sys
import collections
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

EVID = os.path.join(ROOT, 'docs/evidence/2026-08-19-codec-residual')
VERDICTS = os.path.join(EVID, 'codec-review-verdicts.csv')
MASTER = os.path.join(ROOT, 'translation/10_master/current/codec.csv')
CODEC = os.path.join(ROOT, 'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat')
SCRIPT = os.path.join(ROOT, 'translation/00_source/english_script/mgs3-game-script.txt')

_s = importlib.util.spec_from_file_location(
    'ctx', os.path.join(ROOT, 'tools/mgs3d_media_misplaced_context.py'))
ctx = importlib.util.module_from_spec(_s)
sys.modules['ctx'] = ctx
_s.loader.exec_module(ctx)

from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_gcx_font_tool import freed_font_slots  # noqa: E402

COLS = ['group_id', 'gcx', 'resource', 'english', 'draft_state', 'korean_draft',
        'occurrences', 'capacity_bytes', 'gcx_record_headroom', 'candidate_needed_bytes',
        'capacity_risk', 'missing_glyphs', 'glyph_risk', 'speaker', 'speaker_source',
        'prev_english', 'next_english', 'master_recovery_korean',
        'master_recovery_basis', 'script_ref_candidate', 'recovery_confidence', 'notes']

# Hangul reaches codec through the resident global page, not through per-GCX
# font slots, so the glyph question is whether a character is in this map.
CHARMAP = os.path.join(ROOT, 'translation/40_build_input/global_page_v2/character-map.json')


def enc_bytes(text):
    body = (text or '').replace('<0A>', '').replace('<00>', '')
    return sum(1 if ord(c) < 0x80 else 2 for c in body) + 1


def accepted(row):
    return (row.get('accept') or '').strip().lower() in ('y', 'yes', '1', 'ok', 'o', 'true')


def norm_en(s):
    return ' '.join((s or '').replace('<0A>', ' ').replace('<00>', ' ').split()).strip().lower()


def load_script_speakers():
    """english line (normalised) -> speaker, from the MHamlin script."""
    out = {}
    if not os.path.exists(SCRIPT):
        return out
    cur = None
    for line in io.open(SCRIPT, encoding='utf-8', errors='replace'):
        s = line.strip()
        m = re.match(r'^([A-Z][A-Za-z \-\.]{1,18}):\s*(.*)$', s)
        if m:
            cur = m.group(1).strip()
            body = m.group(2)
        else:
            body = s
        if not cur or not body:
            continue
        for sent in re.split(r'(?<=[.!?])\s+', body):
            k = norm_en(sent)
            if len(k) >= 6:
                out.setdefault(k, cur)
    return out


def main():
    csv.field_size_limit(10 ** 9)
    verdicts = list(csv.DictReader(io.open(VERDICTS, encoding='utf-8-sig', newline='')))
    targets = [v for v in verdicts if v['verdict'] == 'TRANSLATE']

    with io.open(MASTER, encoding='utf-8-sig', newline='') as fh:
        master = list(csv.DictReader(fh))
    by_gcx = collections.defaultdict(dict)
    for r in master:
        by_gcx[r['gcx']][r['resource']] = r

    # existing accepted Korean for the same English, anywhere in codec master
    recovery = {}
    for r in master:
        if not accepted(r):
            continue
        ko = (r.get('korean') or '').strip()
        if not ko:
            continue
        k = norm_en(r.get('english'))
        if len(k) >= 3:
            recovery.setdefault(k, []).append(ko)

    charmap = set(json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].keys())
    headroom = {}
    for r in master:
        v = (r.get('record_headroom') or '').strip()
        if v and r['gcx'] not in headroom:
            headroom[r['gcx']] = v
    records = parse_codec(io.open(CODEC, 'rb').read())
    speakers = load_script_speakers()
    shin = ctx.load_script_ref()

    # glyph headroom per GCX, assuming every target resource in it is replaced
    per_gcx = collections.defaultdict(set)
    for v in targets:
        per_gcx[int(v['gcx'])].add(int(v['resource']))
    freed = {}
    capacity = {}
    for gcx, res_set in per_gcx.items():
        rec = records[gcx]
        resources = rec.resources()
        freed[gcx] = len(freed_font_slots(rec, res_set))
        for idx in res_set:
            capacity[(gcx, idx)] = len(resources[idx].data) if idx < len(resources) else None

    groups = {}
    for v in targets:
        groups.setdefault(norm_en(v['english']), []).append(v)
    gid = {}
    for i, k in enumerate(sorted(groups), 1):
        gid[k] = 'G%02d' % i

    out = []
    for v in targets:
        g, r = v['gcx'], v['resource']
        gi, ri = int(g), int(r)
        draft = (v.get('korean_draft') or '').strip()
        state = ('CONTAMINATED' if draft and v.get('draft_status') else
                 ('HAS_DRAFT' if draft else 'BLANK'))
        cap = capacity.get((gi, ri))
        row_master = by_gcx.get(g, {}).get(r, {})

        prev_en = next_en = ''
        for delta, slot in ((-1, 'prev'), (1, 'next')):
            nb = by_gcx.get(g, {}).get(str(ri + delta))
            if nb:
                txt = ' '.join((nb.get('english') or '').split())[:70]
                if slot == 'prev':
                    prev_en = txt
                else:
                    next_en = txt

        k = norm_en(v['english'])
        cand = recovery.get(k, [])
        rec_ko = cand[0] if len(set(cand)) == 1 else ''
        rec_basis = ('same English already accepted elsewhere in codec master (%d rows, identical Korean)' % len(cand)) if rec_ko else (
            'same English accepted elsewhere but with %d different Korean values - not safe' % len(set(cand)) if cand else '')

        sn = ''
        if rec_ko:
            n = ctx.norm(rec_ko)
            if len(n) >= 6 and any(n == c['norm'] or n in c['norm'] for c in shin):
                sn = rec_ko

        need = enc_bytes(rec_ko) if rec_ko else ''
        miss = sorted({c for c in (rec_ko or '').replace('<0A>', '').replace('<00>', '')
                       if ord(c) > 0x7f and c not in charmap})
        if rec_ko and cap is not None:
            crisk = 'ok' if need <= cap else 'OVER by %d' % (need - cap)
        else:
            crisk = 'unknown until translated'
        conf = 'EXACT' if rec_ko and sn else ('HIGH' if rec_ko else 'UNRESOLVED')
        out.append({
            'group_id': gid[k], 'gcx': g, 'resource': r,
            'english': ' '.join((v['english'] or '').split()),
            'draft_state': state, 'korean_draft': draft,
            'occurrences': v['occurrences'],
            'capacity_bytes': cap if cap is not None else '',
            'gcx_record_headroom': headroom.get(g, ''),
            'candidate_needed_bytes': need,
            'capacity_risk': crisk,
            'missing_glyphs': ''.join(miss),
            'glyph_risk': 'MISSING' if miss else ('ok' if rec_ko else 'check after translation'),
            'speaker': speakers.get(k, ''),
            'speaker_source': 'MHamlin English game script' if speakers.get(k) else '',
            'prev_english': prev_en, 'next_english': next_en,
            'master_recovery_korean': rec_ko, 'master_recovery_basis': rec_basis,
            'script_ref_candidate': sn,
            'recovery_confidence': conf,
            'notes': row_master.get('note') or '',
        })

    out.sort(key=lambda x: (x['group_id'], int(x['gcx']), int(x['resource'])))
    dest = os.path.join(EVID, 'codec-translate-prep.csv')
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS, lineterminator='\r\n')
        w.writeheader()
        w.writerows(out)

    st = collections.Counter(x['draft_state'] for x in out)
    cf = collections.Counter(x['recovery_confidence'] for x in out)
    print('TRANSLATE rows        %d' % len(out))
    print('  draft state         %s' % dict(st))
    print('  independent groups  %d' % len(groups))
    print('  recovery confidence %s' % dict(cf))
    print('  speaker known       %d' % sum(1 for x in out if x['speaker']))
    print('  candidate over cap  %d' % sum(1 for x in out if str(x['capacity_risk']).startswith('OVER')))
    print('  missing glyphs      %d' % sum(1 for x in out if x['glyph_risk'] == 'MISSING'))
    tight = [x for x in out if x['capacity_bytes'] != '' and int(x['capacity_bytes']) < 16]
    print('  very tight (<16B)   %d' % len(tight))
    print('  -> %s' % os.path.relpath(dest, ROOT))


if __name__ == '__main__':
    main()
