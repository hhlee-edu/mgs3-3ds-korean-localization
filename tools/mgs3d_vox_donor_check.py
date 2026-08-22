#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mgs3d_vox_donor_check.py - vox.dat 자막을 도너 4개 언어로 교차 검증한다.

왜 vox는 다른 도구가 필요한가
  `mgs3d_crossvalidate.py`는 shinsnote 정렬에 기댄다. 그런데 shinsnote는 컷신/무전
  대본이지 게임 중 병사 대사집이 아니다. vox 2,691행과의 완전일치 135건을 열어보면
  중앙값 2글자, 129건이 5자 이하 -- `Ah.`->`아.` 같은 우연이다. 정렬이 성립하지 않는다.

그런데 vox는 자기 안에 더 좋은 기준을 갖고 있다
  vox.dat의 큐 하나에는 EN + FR/DE/IT/ES가 *같은 타이밍에* 들어 있다. 즉 모든 줄에
  전문 번역 4개가 완벽히 정렬된 채로 존재한다. 외부 자료가 전혀 필요 없다.

  한국어와 프랑스어를 의미로 비교하려면 LLM이 필요하지만, 도너 4개의 *합의*를
  기준선으로 쓰면 기계적으로 판정할 수 있는 것이 있다. 4개 언어가 모두 갖고 있는
  것을 한국어만 안 갖고 있으면, 그건 번역 취향이 아니라 손실이다.

검출기
  V1 token   숫자/주파수/대문자 호출부호가 EN과 도너 다수에 있는데 KO에 없음
  V2 terse   EN/도너는 문장 N개인데 KO는 그보다 훨씬 적음 = 정보 손실
  V3 lines   줄바꿈 개수가 EN과 다름 = 자막 레이아웃 깨짐
"""
import argparse
import csv
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mgs3d_vox_extract as V  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = 'translation/vox/vox-translation.csv'
MAP = 'translation/vox/vox-map.json'

DONOR_LANGS = (2, 3, 4, 5)
EN_LANGS = (1, 7)

# 언어를 넘어 보존되어야 하는 토큰: 숫자/주파수, 그리고 전부 대문자인 호출부호.
TOK_NUM = re.compile(r'\d+(?:[.,]\d+)*')
TOK_CAPS = re.compile(r'\b[A-Z][A-Z0-9]{2,}\b')
SENT_SPLIT = re.compile(r'[.!?]+')


def decode(raw):
    """레코드 바이트 -> 표시용 문자열. 0x80 0x7C 는 줄바꿈 토큰."""
    return (raw.replace(b'\x80\x7c', b'\n')
               .replace(b'\x1f', b'')
               .decode('latin-1', 'replace'))


def tokens(s):
    return set(TOK_NUM.findall(s)) | set(TOK_CAPS.findall(s))


def sentences(s):
    return [x for x in SENT_SPLIT.split(s) if x.strip()]


def main():
    ap = argparse.ArgumentParser(description='vox 자막을 도너 4개 언어로 교차 검증')
    ap.add_argument('--vox', default=None, help='clean vox.dat (기본: vox-map.json 의 source)')
    ap.add_argument('--out', default='translation/vox/donor-check-findings.csv')
    args = ap.parse_args()

    vox = args.vox or json.load(open(os.path.join(ROOT, MAP), encoding='utf-8'))['source']['path']
    blob = open(vox, 'rb').read()
    cues = V.group_cues(V.parse_records(blob))
    print(f'vox.dat {len(blob):,}B | 큐 {len(cues)}', file=sys.stderr)

    # 번역 CSV: id -> row. id 는 영문 바이트의 sha256 앞 12자리.
    rows = list(csv.DictReader(open(os.path.join(ROOT, CSV), encoding='utf-8-sig')))
    by_id = {r['id']: r for r in rows}
    print(f'번역 CSV {len(rows)}행', file=sys.stderr)

    # 어떤 대문자 토큰을 라틴으로 남기는지는 프로젝트 관행이다.
    # `SNAKE`는 「스네이크」로 음역하고 `GRU`/`KGB`는 그대로 둔다. 코퍼스에서 배운다:
    # 한국어 쪽에 그대로 등장한 적이 있는 토큰만 "보존 대상"으로 본다.
    # "한국어에 한 번이라도 등장했으면 보존 대상"으로 보면 안 된다 -- 소수의 행이
    # `SNAKE`를 라틴으로 남겼다는 이유로 「스네이크」로 음역한 수백 행이 전부 걸린다.
    # 토큰별 *유지율*을 재서 과반이 유지될 때만 보존 대상으로 본다.
    seen, kept_cnt = {}, {}
    for r in rows:
        en_t = set(TOK_CAPS.findall(r.get('english') or ''))
        ko_s = r.get('korean') or ''
        for t in en_t:
            seen[t] = seen.get(t, 0) + 1
            if t in ko_s:
                kept_cnt[t] = kept_cnt.get(t, 0) + 1
    latin_kept = {t for t, n in seen.items() if kept_cnt.get(t, 0) / n >= 0.5}
    print(f'라틴 유지 관행 토큰 {len(latin_kept)}종 '
          f'(후보 {len(seen)}종 중 유지율 50% 이상): {" ".join(sorted(latin_kept)[:12])}',
          file=sys.stderr)

    findings = []
    matched = 0
    for cue in cues:
        en_rec = next((r for r in cue if r['lang'] in EN_LANGS), None)
        if not en_rec:
            continue
        row = by_id.get(V.make_id(en_rec['text']))
        if not row or not (row.get('korean') or '').strip():
            continue
        matched += 1
        en = decode(en_rec['text'])
        ko = (row['korean'] or '').replace('\\n', '\n')
        donors = [decode(r['text']) for r in cue if r['lang'] in DONOR_LANGS]
        if len(donors) < 2:
            continue
        loc = row['id']

        # --- V1 : 언어를 넘어 보존되는 토큰이 한국어에서만 사라짐
        en_tok = {t for t in TOK_NUM.findall(en)}
        en_tok |= {t for t in TOK_CAPS.findall(en) if t in latin_kept}
        if en_tok:
            kept = {t for t in en_tok if sum(1 for d in donors if t in d) >= len(donors) - 1}
            lost = sorted(t for t in kept if t not in ko)
            if lost:
                findings.append(dict(
                    detector='V1-token', loc=loc, score=1.0,
                    english=en.replace('\n', ' / ')[:150], korean=ko.replace('\n', ' / ')[:110],
                    evidence=f"도너 {len(donors)}개 중 다수가 보존: {' '.join(lost)}",
                    note=f'영어와 도너에 있는 {", ".join(lost)} 가 한국어에만 없다. '
                         f'주파수/호출부호/수치는 언어와 무관하게 보존되어야 한다',
                ))

        # --- V2 : 도너 합의보다 문장 수가 크게 적음
        n_en = len(sentences(en))
        n_don = [len(sentences(d)) for d in donors]
        n_ko = len(sentences(ko))
        if n_en >= 2 and n_don:
            consensus = statistics.median(n_don)
            # 한국어는 문장을 쉼표로 합치는 일이 흔하다(`Huh. A bird...` -> `흠, 새네...`).
            # 문장 수만 보면 그런 정상 번역이 전부 걸린다. 실제로 *짧아졌는지*를 같이 본다.
            don_len = statistics.median(len(d) for d in donors)
            ko_load = len(ko) * 2                      # 한글 1자 ~= 라틴 2자 분량
            if consensus >= 2 and n_ko * 2 <= consensus and ko_load < don_len * 0.6:
                findings.append(dict(
                    detector='V2-terse', loc=loc,
                    score=round(1.0 - (n_ko / max(1.0, consensus)), 3),
                    english=en.replace('\n', ' / ')[:150], korean=ko.replace('\n', ' / ')[:110],
                    evidence=f'문장 수 EN {n_en} / 도너 {n_don} / KO {n_ko}',
                    note=f'다섯 언어가 문장 {consensus:g}개인데 한국어만 {n_ko}개. 내용 누락 의심',
                ))

        # --- V3 : 줄바꿈이 사라져 한 줄이 넓어짐 (자막 가로 넘침 위험)
        #
        # 줄이 *늘어나는* 것은 무해하다 - 더 짧게 접힐 뿐이다.
        # 줄이 *줄면* 한 줄이 길어져 화면 밖으로 넘칠 수 있다. 그쪽만 본다.
        en_lines, ko_lines = en.split('\n'), ko.split('\n')
        if len(ko_lines) < len(en_lines):
            en_w = max(len(x) for x in en_lines)
            ko_w = max(len(x) * 2 for x in ko_lines)   # 한글 1자 ~= 라틴 2자 폭
            if ko_w > en_w:
                findings.append(dict(
                    detector='V3-lines', loc=loc,
                    score=round(min(1.0, (ko_w - en_w) / max(1, en_w)), 3),
                    english=en.replace('\n', ' / ')[:150], korean=ko.replace('\n', ' / ')[:110],
                    evidence=f'줄 EN {len(en_lines)} -> KO {len(ko_lines)}, '
                             f'최장 줄 폭 EN {en_w} -> KO {ko_w}',
                    note='줄바꿈이 사라져 한 줄이 영어 최장 줄보다 넓어졌다. 화면 넘침 위험',
                ))

    findings.sort(key=lambda f: (-f['score'], f['detector']))
    out = os.path.join(ROOT, args.out)
    cols = ['detector', 'loc', 'score', 'english', 'korean', 'evidence', 'note']
    with open(out, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(findings)

    from collections import Counter
    print(f'\n대조된 큐 {matched} | 결함 후보 {len(findings)}', file=sys.stderr)
    for k, v in sorted(Counter(f['detector'] for f in findings).items()):
        print(f'  {k:10} {v}', file=sys.stderr)
    print(f'-> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
