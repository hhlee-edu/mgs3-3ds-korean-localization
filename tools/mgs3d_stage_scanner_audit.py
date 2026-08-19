# -*- coding: utf-8 -*-
"""Audit every resource where the old and new control-token scanners disagree.

READ-ONLY. Writes only its report.

The old scanner (mgs3d_stage_apply.controls / mgs3d_stage_final_gate.token_stream)
walks byte by byte and only ever skips 2 bytes for a recognised control token.
It therefore lands *inside* multi-byte glyph tokens and can read their payload
as a control prefix.

The engine consumes any byte >= 0x80 as the start of a 2-byte token, so the
correct scanner skips those wholesale. This tool classifies every disagreement:

  GLYPH_SECOND_BYTE_FALSE_CONTROL  old scanner invented a token from the second
                                   byte of a 2-byte glyph/game token
  REAL_CONTROL_DIFFERENCE          a genuine control token is read differently
  AMBIGUOUS                        neither of the above can be shown
"""
import io
import json
import os
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from mgs3d_stage_text_scan import stage_records  # noqa: E402
from pathlib import Path  # noqa: E402

STAGE = Path(ROOT) / 'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/stage'
OUT = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')
CONTROL_PAIRS = (b'\xA0\x7B', b'\xC0\x7D')


def old_scan(data):
    out, i = [], 0
    while i < len(data):
        if data[i] == 0:
            break
        if data[i] == 0x1F and i + 1 < len(data):
            out.append((i, data[i:i + 2])); i += 2; continue
        if data[i:i + 2] in CONTROL_PAIRS:
            out.append((i, data[i:i + 2])); i += 2; continue
        i += 1
    return out


def new_scan(data):
    """Engine model: control pairs first, then any >=0x80 byte is a 2-byte token."""
    out, i = [], 0
    while i < len(data):
        if data[i] == 0:
            break
        if data[i:i + 2] in CONTROL_PAIRS:
            out.append((i, data[i:i + 2])); i += 2; continue
        if data[i] == 0x1F and i + 1 < len(data):
            out.append((i, data[i:i + 2])); i += 2; continue
        if data[i] >= 0x80 and i + 1 < len(data):
            i += 2; continue
        i += 1
    return out


def token_spans(data):
    """Offsets the engine would treat as the START of a 2-byte token."""
    starts, i = set(), 0
    while i < len(data):
        if data[i] == 0:
            break
        if data[i:i + 2] in CONTROL_PAIRS or data[i] == 0x1F:
            starts.add(i); i += 2; continue
        if data[i] >= 0x80 and i + 1 < len(data):
            starts.add(i); i += 2; continue
        i += 1
    return starts


def classify(data, o, n):
    """Why do the two scanners disagree on this resource?"""
    starts = token_spans(data)
    only_old = [t for t in o if t not in n]
    only_new = [t for t in n if t not in o]
    # every token the old scanner saw that the new one did not: was it read
    # from a position the engine never treats as a token start?
    if only_old and not only_new and all(off not in starts for off, _ in only_old):
        return 'GLYPH_SECOND_BYTE_FALSE_CONTROL', only_old, only_new
    if only_new:
        return 'REAL_CONTROL_DIFFERENCE', only_old, only_new
    return 'AMBIGUOUS', only_old, only_new


def main():
    tally = collections.Counter()
    examples = collections.defaultdict(list)
    total = diff = 0
    lost_real = 0
    for path in sorted(STAGE.glob('*/scenerio.gcx')):
        for rec in stage_records(path):
            for ri, res in enumerate(rec.resources()):
                total += 1
                d = res.data
                o, n = old_scan(d), new_scan(d)
                if o == n:
                    continue
                diff += 1
                kind, only_old, only_new = classify(d, o, n)
                tally[kind] += 1
                # does the new scanner ever LOSE a token the engine would honour?
                starts = token_spans(d)
                if any(off in starts for off, _ in only_old):
                    lost_real += 1
                if len(examples[kind]) < 4:
                    examples[kind].append({
                        'stage': path.parent.name, 'resource': ri,
                        'old_only': [(off, b.hex().upper()) for off, b in only_old][:4],
                        'new_only': [(off, b.hex().upper()) for off, b in only_new][:4],
                        'bytes': d[:48].hex().upper(),
                    })
    print('resources scanned            %d' % total)
    print('scanners disagree            %d' % diff)
    for k, v in tally.most_common():
        print('  %-32s %d' % (k, v))
    print()
    print('cases where the NEW scanner drops a token the engine WOULD honour: %d' % lost_real)
    for k, ex in examples.items():
        print()
        print('--- %s ---' % k)
        for e in ex[:2]:
            print('  %s res%d' % (e['stage'], e['resource']))
            print('    old-only %s' % e['old_only'])
            print('    new-only %s' % e['new_only'])
            print('    bytes    %s' % e['bytes'])
    json.dump({'resources': total, 'disagree': diff, 'by_class': dict(tally),
               'new_scanner_drops_real_token': lost_real,
               'examples': {k: v for k, v in examples.items()}},
              io.open(os.path.join(OUT, 'stage-scanner-audit.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
