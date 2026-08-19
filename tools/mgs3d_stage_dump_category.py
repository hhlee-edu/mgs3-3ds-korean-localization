# -*- coding: utf-8 -*-
"""Dump the untranslated rows of a stage category from the RAW resource.

The worklist's `english` column is display-only: its line breaks and control
structure are flattened. Production authoring must key on the raw resource, so
this dumps exactly what mgs3d_stage_plain_batch.py will use as the lookup key.
"""
import csv, io, os, sys, importlib.util, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_s = importlib.util.spec_from_file_location('au', os.path.join(ROOT, 'tools/mgs3d_stage_control_author.py'))
au = importlib.util.module_from_spec(_s); sys.modules['au'] = au; _s.loader.exec_module(au)
WORK = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-translation-working.csv')


def rows(category=None, todo_only=True):
    csv.field_size_limit(10**9)
    out = []
    for r in csv.DictReader(io.open(WORK, encoding='utf-8-sig', newline='')):
        if category and r['category'] != category:
            continue
        if todo_only and (r.get('current_korean') or '').strip():
            continue
        raw = bytes.fromhex(r['raw_hex'])
        segs, tail = au.decompose(raw)
        r['_raw'] = raw
        r['_text'] = ''.join(v for k, v in segs if k == 'T')
        r['_ctrl'] = [k for k, _ in segs if k in ('C', 'G')]
        r['_slot'] = len(raw)
        out.append(r)
    return out


if __name__ == '__main__':
    cat = sys.argv[1] if len(sys.argv) > 1 else None
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
    off = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    rs = rows(cat)
    print('# %s : %d untranslated rows (showing %d from %d)' % (cat, len(rs), min(lim, max(0, len(rs) - off)), off))
    nc = sum(1 for r in rs if r['_ctrl'])
    print('# rows carrying control tokens: %d' % nc)
    for r in rs[off:off + lim]:
        print('%s\tslot=%d\tocc=%s\tctrl=%s\t%r' % (r['id'], r['_slot'], r['occurrences'], ''.join(r['_ctrl']) or '-', r['_text']))
