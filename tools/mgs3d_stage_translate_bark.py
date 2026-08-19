# -*- coding: utf-8 -*-
"""Write the ENEMY_BARK / NPC_DIALOGUE Korean into a stage working sheet.

READ-ONLY with respect to scenerio.gcx, staging and the authority worklist.
It copies docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-worklist-expanded.csv
to a separate working sheet and fills `current_korean` there, so the analysis
authority stays untouched and mgs3d_stage_apply.py can be pointed at the copy.

Budget model, matching tools/mgs3d_stage_apply.py exactly:
    encoded = parse_rendered(text, global-page character map)
    gate    = len(encoded) <= len(original resource slot)
Hangul costs 2 bytes through the resident global page, ASCII 1, plus the NUL
terminator. Characters outside character-map.json would need a NEW glyph, so
they are counted and reported rather than silently accepted.

The three PS2_OFFICIAL rows are left exactly as the analysis recorded them.
"""
import csv
import io
import json
import os
import shutil
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')
SRC = os.path.join(ANALYSIS, 'stage-worklist-expanded.csv')
WORK = os.path.join(ANALYSIS, 'stage-translation-working.csv')
CHARMAP = os.path.join(ROOT, 'translation/40_build_input/global_page_v2/character-map.json')

# english -> (korean, origin, note)
# Barks flash on screen for a moment, so these are short and instantly readable
# without dropping meaning. Shouts stay shouts.
T = {
    'Answer me!': ('대답해!', 'NEW',
                   'PS2 line is 대<L229>하라! but L229 is UNRESOLVED, so this is written fresh, not claimed as recovery'),
    "Who's there!": ('거기 누구냐!', 'NEW',
                     'kept distinct from "Who\'s that!" (누구냐!) by carrying the "there"'),
    'Who the...!!': ('뭐야...!!', 'NEW', 'cut-off surprise, ellipsis preserved'),
    'Hyaaaah!': ('으아아!', 'NEW', 'battle shout'),
    # 얍 is not in the 1,120-glyph global page; 야압 is, and reads the same
    'Hyahya!': ('야압!', 'NEW', 'short attack shout; avoids a new glyph (얍 is not in the page)'),
    'Hyeeei!': ('에잇!', 'NEW', 'short attack shout'),
    'Hyuuh!': ('흡!', 'NEW', 'sharp exhale'),
    'Gwoah!': ('으악!', 'NEW', 'pain shout'),
    'Huuuuhya!': ('우와아!', 'NEW', 'long shout'),
    "You Were Lucky. We'll Meet Again!": ('운이 좋았군. 다음에 또 보자!', 'NEW',
                                          'Ocelot parting line; plain register as elsewhere for Ocelot'),
}


def enc_len(text, cmap):
    """Bytes the apply tool's encoder would emit, including the terminator."""
    n = 0
    for ch in text:
        if ch in cmap:
            n += len(cmap[ch])
        elif ord(ch) < 0x80:
            n += 1
        else:
            return None          # would need a new glyph
    return n + 1


def main():
    csv.field_size_limit(10 ** 9)
    cmap = {k: bytes.fromhex(v) for k, v in
            json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].items()}

    with io.open(SRC, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames

    report, fails, newglyph = [], [], set()
    filled = reused = 0
    for r in rows:
        en = r['english']
        if r['category'] not in ('ENEMY_BARK', 'NPC_DIALOGUE'):
            continue
        if (r.get('current_korean') or '').strip():
            origin, note = 'PS2_OFFICIAL', 'already established; left untouched'
            ko = r['current_korean'].strip()
            reused += 1
        elif en in T:
            ko, origin, note = T[en]
            r['current_korean'] = ko
            r['source'] = 'STAGE_NEW_2026-08-19'
            filled += 1
        else:
            continue
        cap = int(r['capacity_min_bytes'])
        need = enc_len(ko, cmap)
        miss = [c for c in ko if ord(c) > 0x7f and c not in cmap]
        newglyph.update(miss)
        ok = need is not None and need <= cap and not miss
        report.append({
            'english': en, 'korean': ko, 'origin': origin,
            'occurrences': r['occurrences'],
            'needed_bytes': need if need is not None else '',
            'capacity_bytes': cap,
            'headroom': (cap - need) if need is not None else '',
            'new_glyphs': ''.join(miss),
            'gate': 'PASS' if ok else 'FAIL', 'note': note,
        })
        if not ok:
            fails.append((en, ko, need, cap, miss))

    shutil.copy2(SRC, WORK) if not os.path.exists(WORK) else None
    with io.open(WORK, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)

    dest = os.path.join(ANALYSIS, 'stage-bark-translations.csv')
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
        w.writeheader()
        w.writerows(report)

    print('bark/NPC rows      %d  (new %d, PS2 official reused %d)'
          % (len(report), filled, reused))
    print('byte gate          PASS %d / FAIL %d' % (len(report) - len(fails), len(fails)))
    print('NEW glyphs needed  %d %s' % (len(newglyph), ''.join(sorted(newglyph)) or '(none)'))
    for x in sorted(report, key=lambda y: -int(y['occurrences'])):
        print('  %-4s occ%-5s %2s/%-2s  %-13s %-28r %s'
              % (x['gate'], x['occurrences'], x['needed_bytes'], x['capacity_bytes'],
                 x['origin'], x['korean'], x['english'][:30]))
    for f in fails:
        print('  FAIL %r -> %r need %s cap %s miss=%s' % f)
    print()
    print('working sheet -> %s' % os.path.relpath(WORK, ROOT))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
