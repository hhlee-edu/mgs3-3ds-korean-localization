# -*- coding: utf-8 -*-
"""Translate and apply the codec TRANSLATE 46.

Approved 2026-08-19. Writes only translation/10_master/current/codec.csv, after
a pre-flight that every string passes. No DAT, no staging, no commit here.

Byte model, matching raw_text in master exactly:
    stored korean = TEXT<0A><00>
    bytes = 2 per non-ASCII + 1 per ASCII + 1 (<0A>) + 1 (<00>)
so a row's TEXT budget is capacity_bytes - 2.

Register follows the settled project rules: Snake plain, Zero (Major) 하게체,
Para-Medic / EVA polite, Sigint casual, The Boss plain. Character names keep the
Latin spelling codec already ships (Snake, EVA), unlike movie/demo.
The 30 contaminated drafts were NOT consulted.
"""
import csv
import io
import json
import os
import shutil
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(ROOT, 'docs/evidence/2026-08-19-codec-residual')
PREP = os.path.join(EVID, 'codec-translate-prep.csv')
MASTER = os.path.join(ROOT, 'translation/10_master/current/codec.csv')
CHARMAP = os.path.join(ROOT, 'translation/40_build_input/global_page_v2/character-map.json')
STAMP = 'bak-pre-codec-final-20260819'

# (gcx, resource) -> (korean text without control codes, origin)
T = {
    ('910', '30'): ('OK?', 'NEW'),
    ('2022', '24'): ('UMA?', 'NEW'),
    ('2155', '11'): ('그러지.', 'NEW'),
    ('510', '28'): ('시긴토!', 'NEW'),
    ('573', '10'): ('시긴토.', 'NEW'),
    ('2022', '22'): ('시긴토?', 'NEW'),
    ('510', '40'): ('시긴토!', 'NEW'),
    ('647', '17'): ('뭐가 왜?', 'NEW'),
    ('2201', '16'): ('그래서?', 'NEW'),
    ('243', '825'): ('...그래...', 'NEW'),
    ('242', '0'): ('응답 없음', 'RECOVERED'),
    ('443', '716'): ('뭐, 그렇지.', 'NEW'),
    ('2210', '52'): ('걱정하지 마.', 'NEW'),
    ('238', '20'): ('훈련이 아냐?', 'NEW'),
    ('1721', '28'): ('그래, 미안.', 'NEW'),
    ('1598', '10'): ('오셀롯이에요.', 'NEW'),
    ('511', '20'): ('괜찮아, Snake?', 'NEW'),
    ('28', '90'): ('패러... 메딕?', 'NEW'),
    ('2149', '10'): ('저장할까요?', 'RECOVERED_SHORTENED'),
    ('656', '19'): ('그럴 거예요.', 'NEW'),
    ('1301', '25'): ('그럭저럭이다.', 'NEW'),
    ('2160', '10'): ('살아서 돌아와요.', 'RECOVERED_SHORTENED'),
    ('2148', '10'): ('저장 준비됐나요?', 'RECOVERED_SHORTENED'),
    ('1379', '16'): ('신경 쓰지 마...', 'NEW'),
    ('359', '10'): ('아, 나비도요.', 'NEW'),
    ('1301', '24'): ('Snake, 괜찮나?', 'NEW'),
    ('681', '30'): ('응? 왜 그래, 시긴토?', 'NEW'),
    ('1753', '40'): ('그건 못 봤군.', 'NEW'),
    ('1129', '14'): ('Snake, 괜찮나!?', 'NEW'),
    ('745', '21'): ('알아. 좀비라고 하지.', 'NEW'),
    ('243', '824'): ('...Snake, 괜찮나?', 'NEW'),
    ('1037', '52'): ('...정말 그게 다일까?', 'NEW'),
    ('1659', '15'): ('라이코프는 원래 그래요.', 'NEW'),
    ('1723', '10'): ('Snake! 대답해! Snake! SNAKE!!', 'RECOVERED_SHORTENED'),
    ('1267', '34'): ('Snake! 왜 EVA를 공격하나!?', 'NEW'),
    ('243', '743'): ('버리기 아깝다고 하더군.', 'NEW'),
    ('440', '33'): ('헛소문이라고 들었다.', 'NEW'),
    ('2022', '25'): ('미확인 신비 동물이요.', 'NEW'),
    ('745', '26'): ('좀비를 모르신다고요?', 'NEW'),
    ('1727', '840'): ('EVA, 오셀롯에 대해 묻고 싶다...', 'NEW'),
    ('1037', '56'): ('그렇군... 나도 그 생각을 하고 있었다.', 'NEW'),
    ('1757', '20'): ('알아요. Snake, 그로즈니그라드가 어딘지 알아요?', 'NEW'),
    ('1037', '50'): ('패러메딕, Snake가 대체 왜 저러나?', 'NEW'),
    ('1037', '60'): ('!! 어... 어쨌든 무사해서 다행이다.', 'NEW'),
    ('274', '13'): ('뭐, 좀 화려한 건 인정한다...', 'NEW'),
    ('1897', '10'): ('Snake, EVA가 심하게 다쳤어요! 빨리 부상을 치료해주세요!!', 'RECOVERED'),
}


def body_bytes(text):
    return sum(1 if ord(c) < 0x80 else 2 for c in text)


def accepted(row):
    return (row.get('accept') or '').strip().lower() in ('y', 'yes', '1', 'ok', 'o', 'true')


def main():
    csv.field_size_limit(10 ** 9)
    prep = {(r['gcx'], r['resource']): r
            for r in csv.DictReader(io.open(PREP, encoding='utf-8-sig', newline=''))}
    charmap = set(json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].keys())

    missing_key = [k for k in prep if k not in T]
    extra_key = [k for k in T if k not in prep]
    if missing_key or extra_key:
        raise SystemExit('translation table does not cover the prep set exactly: '
                         'missing %s extra %s' % (missing_key, extra_key))

    report, fails = [], []
    for key, (text, origin) in T.items():
        p = prep[key]
        cap = int(p['capacity_bytes'])
        need = body_bytes(text) + 2                 # <0A> + <00>
        miss = sorted({c for c in text if ord(c) > 0x7f and c not in charmap})
        bad_ctrl = '<' in text or '>' in text        # no raw control codes in the body
        ok = need <= cap and not miss and not bad_ctrl
        report.append({
            'gcx': key[0], 'resource': key[1], 'origin': origin,
            'english': p['english'], 'korean': text,
            'needed_bytes': need, 'capacity_bytes': cap,
            'headroom': cap - need,
            'missing_glyphs': ''.join(miss),
            'control_ok': 'yes' if not bad_ctrl else 'NO',
            'gate': 'PASS' if ok else 'FAIL',
            'speaker': p['speaker'], 'occurrences': p['occurrences'],
        })
        if not ok:
            fails.append((key, text, need, cap, miss, bad_ctrl))

    report.sort(key=lambda r: (int(r['gcx']), int(r['resource'])))
    with io.open(os.path.join(EVID, 'codec-translate-applied.csv'), 'w',
                 encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(report[0].keys()), lineterminator='\r\n')
        w.writeheader()
        w.writerows(report)

    print('PRE-FLIGHT  %d rows' % len(report))
    print('  capacity PASS %d / FAIL %d' % (len(report) - len(fails), len(fails)))
    print('  missing glyphs %d' % sum(1 for r in report if r['missing_glyphs']))
    print('  control-code issues %d' % sum(1 for r in report if r['control_ok'] != 'yes'))
    if fails:
        for k, t, n, c, m, b in fails:
            print('   FAIL gcx%s res%s need %d cap %d miss=%s ctrl=%s %r'
                  % (k[0], k[1], n, c, m, b, t))
        raise SystemExit(1)

    with io.open(MASTER, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        cols = reader.fieldnames
    backup = '%s.%s' % (MASTER, STAMP)
    if not os.path.exists(backup):
        shutil.copy2(MASTER, backup)

    applied = 0
    for r in rows:
        key = (r['gcx'], r['resource'])
        if key in T:
            r['korean'] = T[key][0] + '<0A><00>'
            r['accept'] = 'yes'
            r['translate'] = 'yes'
            r['status'] = 'codec-final-2026-08-19'
            applied += 1
    if applied != len(T):
        raise SystemExit('expected %d rows, matched %d' % (len(T), applied))

    with io.open(MASTER, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)

    print()
    print('master applied %d rows (backup %s)' % (applied, os.path.basename(backup)))
    print('origins %s' % dict(collections.Counter(v[1] for v in T.values())))
    print('accepted rows now %d' % sum(1 for r in rows if accepted(r)))


if __name__ == '__main__':
    main()
