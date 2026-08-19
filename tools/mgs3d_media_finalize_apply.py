# -*- coding: utf-8 -*-
"""Finalize the movie/demo pass: register FIX, overflow shortening, HUMAN and
NO_SOURCE resolution.

Approved 2026-08-19 evening. Touches ONLY
translation/10_master/current/{demo,movie}.csv. No DAT, no staging, no commit.

Byte sizing uses the encoder's own rule, verified against the capacity report:
    2 bytes per non-ASCII glyph, 1 byte per ASCII char, +1 NUL terminator.
Every new or shortened string is checked against its entry capacity BEFORE it
is written, so the capacity gate only has to run once afterwards.
"""
import csv
import io
import json
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
PROPOSALS = os.path.join(ROOT, 'output/media-register-qa/media-qa-proposals.csv')
CAPJSON = os.path.join(EVID, 'dryrun/demo-capacity-postapply.json')
STAMP = 'bak-pre-finalize-20260819'

# --- 2. overflow: minimal shortening, meaning and register preserved ---------
# Duplicate pairs get byte-identical strings.
OVERFLOW = {
    ('demo', '192', '15'): ('당신도요.', 'drop the 그렇게 말하는 lead-in; EVA is simply turning Snake\'s remark back on him'),
    ('demo', '193', '15'): ('당신도요.', 'duplicate of r192 e15 - identical string'),
    ('demo', '148', '31'): ('악마의 병기군...', 'drop the 말 그대로 intensifier; the noun phrase carries the line'),
    ('demo', '100', '30'): ('알아챈 건가?', 'drop the 설마 opener; the question itself is unchanged'),
    ('demo', '106', '34'): ('알아챈 건가?', 'duplicate of r100 e30 - identical string'),
    ('demo', '225', '5'): ('속도를 내!', 'drop 더; still an order to speed up'),
    ('demo', '115', '1'): ('한가지 문제가 있어요.', 'drop the 그런데 connector only'),
    ('demo', '226', '16'): ('날 기다린다고?', '나를 -> 날 contraction, same meaning and register'),
}

# --- 3. HUMAN resolved on authority ----------------------------------------
HUMAN_RESOLVED = {
    ('demo', '15', '29'): (
        '흠...',
        'MHamlin script line 991: "Ocelot: Hmm... You are not The Boss, are you?" - '
        'speaker and slot confirmed. Matches the 흠... already applied at r125 e0.'),
    ('demo', '146', '2'): (
        '그 괴물이 시속 300마일 이상이라고...?',
        'MHamlin script: "Sokolov: ...a land speed of over 300 miles per hour." / '
        '"Snake: That monster can go more than 300 miles per hour?" - the English is '
        'imperial and this record\'s neighbours were re-translated from English '
        '(e37 uses 2,500마일에서 6,000마일로), so imperial is the record convention.'),
}

# --- 4. NO_SOURCE: new Korean, English speaker/scene confirmed --------------
# The cell-block guard conversation. MHamlin script lines 3300-3335 give the
# speaker for every line; all of these are Snake, who speaks plain throughout
# the record (the guard's own lines in master are already plain).
JOHNNY = {
    'lonely': ('꽤 외롭겠군.', 'Snake -> guard, "You must be pretty lonely."'),
    'kidname': ('아이 이름이 뭐지?', 'Snake -> guard, "What\'s your kid\'s name?"'),
    'ring': ('조니... 어감이 좋군.', 'Snake -> guard, "Johnny...nice ring to it." (master already uses 조니)'),
    'clan': ('온 집안이 조니로군.', 'Snake -> guard, "A whole clan of Johnnies."'),
    # capacity here is 20 bytes, so the agreement has to be short
    'hearya': ('그래, 알 것 같다.', 'Snake -> guard, "Yeah, I hear ya." - empathetic agreement, 18/20 bytes'),
    'rough': ('힘들겠군.', 'Snake -> guard, "Must be rough."'),
    'letout': ('날 여기서 내보내 줄 순 없나?', 'Snake -> guard, "Don\'t suppose you could let me out of here?"'),
}
NO_SOURCE = {
    ('demo', '178', '35'): JOHNNY['lonely'],
    ('demo', '183', '35'): JOHNNY['lonely'],
    ('demo', '179', '3'): JOHNNY['kidname'],
    ('demo', '184', '3'): JOHNNY['kidname'],
    ('demo', '179', '13'): JOHNNY['ring'],
    ('demo', '184', '13'): JOHNNY['ring'],
    ('demo', '180', '8'): JOHNNY['clan'],
    ('demo', '185', '8'): JOHNNY['clan'],
    ('demo', '180', '23'): JOHNNY['hearya'],
    ('demo', '185', '23'): JOHNNY['hearya'],
    ('demo', '180', '33'): JOHNNY['rough'],
    ('demo', '185', '33'): JOHNNY['rough'],
    ('demo', '181', '35'): JOHNNY['letout'],
    ('demo', '186', '14'): JOHNNY['letout'],
    ('demo', '41', '10'): (
        '팔은 아직 아픈가?',
        'MHamlin script line 1670: "Boss: That arm still hurt?" between "Snake: Boss?" '
        'and "Snake: What are you doing here?" - speaker and slot confirmed. The Boss '
        'speaks plain to Snake throughout this record.'),
    ('demo', '116', '0'): (
        '어떻게?',
        'RECOVERED, not authored: the script reference p13 seq2534 스네이크 "어떻게?" directly after '
        'EVA\'s "그로 변장하면 될 거예요" (= r115 e36). MHamlin script confirms '
        '"Snake: How do I do that?" in the same slot.'),
    ('demo', '296', '0'): (
        '이번엔 잡았다.',
        'MHamlin script line 3899: "Snake: Gotcha this time." while sculpting the C3 '
        'butterfly and catching it. Speaker and scene confirmed.'),
}

# --- 5. incidental proper-noun error found while verifying r159 -------------
EXTRA = {
    ('demo', '159', '29'): (
        '소코로프!',
        'English is "Sokolov!" but master held "소령 ." (= Major). the script reference p14 seq2901 '
        '스네이크 "소코로프!" sits exactly here, between 2900 소코로프 "됐어. 난." and '
        '2902. Proper-noun error, recovered from the transcript.'),
}


def enc_bytes(text):
    """Mirror encode_translation(): 2 bytes per non-ASCII, 1 per ASCII, +1 NUL."""
    return sum(1 if ord(ch) < 0x80 else 2 for ch in text) + 1


def main():
    cap = json.load(io.open(CAPJSON, encoding='utf-8'))
    capacity = {}
    for r in cap['records']:
        for e in r['entries']:
            capacity[e['offset']] = e['capacity_bytes']

    proposals = ctx.read_csv(PROPOSALS)
    fixes = [p for p in proposals if p['verdict'] == 'FIX']

    changes = {}
    origin = {}
    reason = {}
    for p in fixes:
        k = (p['media'], p['record'], p['entry'])
        changes[k] = p['korean_new']
        origin[k] = 'REGISTER_FIX'
        reason[k] = p['reason']
    for table, tag in ((OVERFLOW, 'OVERFLOW_SHORTENED'),
                       (HUMAN_RESOLVED, 'HUMAN_RESOLVED'),
                       (NO_SOURCE, 'NO_SOURCE_TRANSLATED'),
                       (EXTRA, 'PROPER_NOUN_FIX')):
        for k, (text, why) in table.items():
            changes[k] = text
            origin[k] = tag
            reason[k] = why

    master = {}
    for media, path in ctx.MASTER.items():
        for r in ctx.read_csv(path):
            master[(media, r['record'], r['entry'])] = r

    # ---- pre-flight: every string must fit its own entry --------------------
    report = []
    over = []
    for k, text in sorted(changes.items(), key=lambda x: (x[0][0], int(x[0][1]), int(x[0][2]))):
        row = master.get(k)
        if row is None:
            raise SystemExit('no master row for %s' % (k,))
        off = int(row['offset'])
        capb = capacity.get(off)
        need = enc_bytes(text)
        fits = capb is None or need <= capb
        report.append({
            'media': k[0], 'record': k[1], 'entry': k[2], 'offset': off,
            'origin': origin[k],
            'english': (row['preview'] or '').replace('<END>', '').replace('|', ' ').strip(),
            'korean_before': row['korean'], 'korean_after': text,
            'needed_bytes': need, 'capacity_bytes': capb if capb is not None else '',
            'fits': 'YES' if fits else 'NO', 'reason': reason[k],
        })
        if not fits:
            over.append((k, text, need, capb))

    if over:
        print('PRE-FLIGHT FAILED - these would exceed capacity:')
        for k, t, n, c in over:
            print('  %s r%s e%s  need %d cap %d  %r' % (k[0], k[1], k[2], n, c, t))
        raise SystemExit(1)

    # ---- duplicate-pair integrity ------------------------------------------
    for a, b in ((('demo', '192', '15'), ('demo', '193', '15')),
                 (('demo', '100', '30'), ('demo', '106', '34')),
                 (('demo', '179', '3'), ('demo', '184', '3')),
                 (('demo', '179', '13'), ('demo', '184', '13')),
                 (('demo', '180', '8'), ('demo', '185', '8')),
                 (('demo', '180', '23'), ('demo', '185', '23')),
                 (('demo', '180', '33'), ('demo', '185', '33')),
                 (('demo', '181', '35'), ('demo', '186', '14')),
                 (('demo', '178', '35'), ('demo', '183', '35'))):
        if changes.get(a) != changes.get(b):
            raise SystemExit('duplicate pair mismatch: %s vs %s' % (a, b))

    # ---- write --------------------------------------------------------------
    total = 0
    for media, path in ctx.MASTER.items():
        wanted = {k: v for k, v in changes.items() if k[0] == media}
        if not wanted:
            print('%-6s no changes' % media)
            continue
        backup = '%s.%s' % (path, STAMP)
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        with io.open(path, encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            cols = reader.fieldnames
        n = 0
        for r in rows:
            k = (media, r['record'], r['entry'])
            if k in wanted:
                r['korean'] = wanted[k]
                r['accept'] = 'yes'
                n += 1
        if n != len(wanted):
            raise SystemExit('%s: expected %d, matched %d' % (media, len(wanted), n))
        with io.open(path, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
            w.writeheader()
            w.writerows(rows)
        total += n
        print('%-6s applied %d rows (backup %s)' % (media, n, os.path.basename(backup)))

    dest = os.path.join(EVID, 'media-finalize-applied.csv')
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
        w.writeheader()
        w.writerows(report)

    print()
    print('total applied %d' % total)
    print('by origin     %s' % dict(collections.Counter(r['origin'] for r in report)))
    print('pre-flight    all %d strings fit their entry capacity' % len(report))


if __name__ == '__main__':
    main()
