#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mgs3d_crossvalidate.py - 4자료 교차 검증으로 번역 결함 후보를 뽑는다.

사용
  python tools/mgs3d_crossvalidate.py --containers codec,movie,demo,vox       --en-script translation/20_matching/en_script/en_script_mgs3_gamefaqs.json

자료 넷 (전체 색인: translation/00_source/SOURCES.md)
  (1) 3DS 영문 대사      각 컨테이너 CSV의 english/preview 열
  (2) 현재 한국어 번역    같은 CSV의 korean 열
  (3) 영문 대사집(화자)   --en-script. GameFAQs FAQ 34684, 2,164행/화자 37종
  (4) 한국어 대사집       translation/20_matching/script_ref/*.json (shinsnote, 4,070세그)

왜 문자열 비교로는 안 되나
  `demo 9/15`의 한국어 `칭찬하고`는 그 자체로 멀쩡한 한국어다. 영어 `What is it?`와
  비교해도 언어가 달라 유사도가 무의미하다. 결함인 이유는 *위치*가 틀렸다는 것이고,
  그건 순서를 봐야 안다. (2)와 (4)는 둘 다 서사 순서를 가지므로 정렬할 수 있다.

검출기 아홉 - 뒤쪽 넷은 정렬에 의존하지 않는다
  D1 order      정렬 백본(LIS) 위반 + 블록 합의 이탈          [2+4]
  D2 register   화자별 어투 일관성 (화자는 (3)이 확정)        [2+3]
  D3 drift      제자리 유사도 낮고 먼 장면과 강하게 일치       [2+4]
  D4 fragment   영어는 완결문인데 한국어가 연결어미로 끊김     [1+2]
  D5 terse      예산 남는데 영어 대비 과도하게 짧음           [1+2]
  D6 dup        같은 한국어가 *컨테이너를 넘어* 다른 영어에    [1+2]
  D7 pronoun    we/our/us <-> 나/내 인칭·수 불일치            [1+2]
  D8 speechact  앞줄이 질문인데 긍정 답변이 수긍으로 번역      [1+2]
  D9 enpos      영문 대사집 위치와 한국어 위치가 어긋남        [1+2+3+4]

  정렬 기반(D1~D4)만으로는 실플레이 발견 5건 중 1건밖에 못 잡았다. D5~D7을 넣고
  4/5가 됐다. **새 결함 유형은 손질의로 끝내지 말고 검출기로 굳힐 것.**

출력
  {container}-findings.csv   컨테이너별 전체
  worklist.csv               통합·등급순. tier A(우선)/B(검토)/C(참고), sources 열에
                             그 판정을 떠받치는 자료 번호

**출력은 판정이 아니라 후보다.** 사람이 읽고 결정한다. 정본(current/*.csv)은
이 도구가 건드리지 않는다.

함정 (실제로 밟은 것들)
  - record 순서 != 서사 순서. demo 288~291이 HALO 오프닝이다. 전역 LIS만 쓰면
    정상 줄이 대량 오탐된다 -> 블록(record/gcx) 합의로 억제
  - `-니까`는 존댓말이 아닐 수 있다. `확실합니까?`(존댓말) vs `필요하니까.`(연결어미)
    -> 앞 음절 종성이 ㅂ인지로 가른다
  - D6는 컨테이너를 넘어 봐야 한다. `demo 24/14`의 한국어는 `codec 38:15`에서 왔다
  - shinsnote는 vox를 못 덮는다. vox는 tools/mgs3d_vox_donor_check.py 를 쓸 것
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from bisect import bisect_left
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 9)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIN_CODEC = 'translation/20_matching/script_ref/script_ref_mgs3_codec_only.json'
SHIN_MD = 'translation/20_matching/script_ref/script_ref_mgs3_movie_demo_only.json'

# ---------------------------------------------------------------- 정규화

TAG = re.compile(r'<[^>]{0,12}>')
PUNCT = re.compile(r'[\s.,!?~’“”\'"·…:;()\[\]{}<>|/\\-]+')


def strip_tags(s):
    """게임 제어코드(<0A> <00> <END> <G027> ...)와 줄바꿈 표기를 제거."""
    s = TAG.sub(' ', s or '')
    return s.replace('|', ' ').replace('\\n', ' ')


def norm(s):
    """비교용 키: 태그/공백/구두점 제거 + NFC.
    shinsnote가 ' , ' 처럼 구두점 앞을 띄어쓰기 때문에 필수."""
    s = unicodedata.normalize('NFC', strip_tags(s))
    return PUNCT.sub('', s)


def bigrams(s):
    if len(s) > 1:
        return {s[i:i + 2] for i in range(len(s) - 1)}
    return {s} if s else set()


def dice(a, b):
    """bigram Dice 계수 0~1."""
    if not a or not b:
        return 0.0
    return 2.0 * len(a & b) / (len(a) + len(b))


def game_bytes(s):
    """게임 인코딩 기준 바이트: 한글 2, 그 외 1."""
    return sum(2 if '가' <= c <= '힣' else 1 for c in strip_tags(s))


# ---------------------------------------------------------------- 자료 로드

def load_shinsnote(paths):
    segs = []
    for p in paths:
        full = os.path.join(ROOT, p)
        if not os.path.exists(full):
            continue
        d = json.load(open(full, encoding='utf-8'))
        for s in d['segments']:
            if not (s.get('text') or '').strip():
                continue
            segs.append({
                'page': int(s['page']), 'sequence': int(s['sequence']),
                'speaker': s.get('speaker') or '', 'kind': s.get('kind') or '',
                'text': s['text'], 'key': norm(s['text']),
            })
    segs.sort(key=lambda s: (s['page'], s['sequence']))
    for i, s in enumerate(segs):
        s['ord'] = i
        s['bg'] = bigrams(s['key'])
    return segs


def load_en_script(path):
    """(3) 영문 대사집. shinsnote와 같은 스키마를 기대한다.
       {"segments":[{"page":N,"sequence":N,"speaker":str,"text":<영어>}, ...]}
    없으면 None. 있으면 영어<->영어 앵커가 추가되어 정렬 밀도가 크게 오른다."""
    if not path:
        return None
    d = json.load(open(path, encoding='utf-8'))
    segs = d['segments'] if isinstance(d, dict) else d
    out = []
    for s in segs:
        t = (s.get('text') or '').strip()
        if not t:
            continue
        out.append({'page': int(s.get('page', 0)), 'sequence': int(s.get('sequence', 0)),
                    'speaker': s.get('speaker') or '', 'text': t,
                    'key': norm(t.lower())})
    out.sort(key=lambda s: (s['page'], s['sequence']))
    for i, s in enumerate(out):
        s['ord'] = i
    return out


CONTAINERS = {
    'codec': dict(path='translation/10_master/current/codec.csv', en='english', ko='korean',
                  keys=('gcx', 'resource'), shin=[SHIN_CODEC], block='gcx'),
    'demo': dict(path='translation/10_master/current/demo.csv', en='preview', ko='korean',
                 keys=('record', 'entry'), shin=[SHIN_MD], block='record'),
    'movie': dict(path='translation/10_master/current/movie.csv', en='preview', ko='korean',
                  keys=('record', 'entry'), shin=[SHIN_MD], block='record'),
    'vox': dict(path='translation/vox/vox-translation.csv', en='english', ko='korean',
                keys=('id',), shin=[SHIN_CODEC, SHIN_MD], block=None),
}


def load_rows(cfg):
    rows = []
    for r in csv.DictReader(open(os.path.join(ROOT, cfg['path']), encoding='utf-8-sig')):
        ko = (r.get(cfg['ko']) or '').strip()
        if not ko:
            continue
        en = (r.get(cfg['en']) or '').strip()
        try:
            sk = tuple(int(r[k]) for k in cfg['keys'])
        except (ValueError, KeyError):
            sk = tuple(str(r.get(k, '')) for k in cfg['keys'])
        rows.append({
            'raw': r, 'en': en, 'ko': ko, 'sortkey': sk,
            'loc': '/'.join(str(r.get(k, '')) for k in cfg['keys']),
            'kkey': norm(ko), 'ekey': norm(en.lower()),
            'block': str(r.get(cfg['block'], '')) if cfg['block'] else '',
        })
    rows.sort(key=lambda r: r['sortkey'])
    for i, r in enumerate(rows):
        r['ord'] = i
        r['bg'] = bigrams(r['kkey'])
    return rows


# ---------------------------------------------------------------- 앵커 + 정렬

MIN_ANCHOR_CHARS = 6  # `그래` `아` 같은 짧은 감탄사는 앵커로 못 쓴다 (다대다로 붙는다)


def build_anchors(rows, segs, min_chars=MIN_ANCHOR_CHARS):
    """완전일치 + *양방향 유일*인 쌍만 앵커로 채택.
    유일성을 안 걸면 `그래.`가 수십 곳에 붙어 정렬이 무너진다."""
    by_row, by_seg = defaultdict(list), defaultdict(list)
    seg_index = defaultdict(list)
    for s in segs:
        if len(s['key']) >= min_chars:
            seg_index[s['key']].append(s)
    for r in rows:
        if len(r['kkey']) < min_chars:
            continue
        for s in seg_index.get(r['kkey'], ()):
            by_row[r['ord']].append(s['ord'])
            by_seg[s['ord']].append(r['ord'])
    anchors = []
    for ro, sos in by_row.items():
        if len(sos) != 1:
            continue
        if len(by_seg[sos[0]]) != 1:
            continue
        anchors.append((ro, sos[0]))
    anchors.sort()
    return anchors


def lis_backbone(anchors):
    """our_ord 오름차순 앵커들의 shin_ord에 대한 최장증가부분수열.
    LIS에 든 것 = 일관된 정렬 백본. 빠진 것 = 순서 위반 후보."""
    if not anchors:
        return [], []
    tails, tails_idx, prev = [], [], [-1] * len(anchors)
    for i, (_, so) in enumerate(anchors):
        j = bisect_left(tails, so)
        if j == len(tails):
            tails.append(so)
            tails_idx.append(i)
        else:
            tails[j] = so
            tails_idx[j] = i
        prev[i] = tails_idx[j - 1] if j > 0 else -1
    seq, k = [], tails_idx[-1]
    while k != -1:
        seq.append(k)
        k = prev[k]
    seq.reverse()
    keep = set(seq)
    return ([anchors[i] for i in seq],
            [anchors[i] for i in range(len(anchors)) if i not in keep])


def interpolate(backbone, n_rows, n_segs):
    """백본 앵커 사이를 선형 보간해 모든 행에 기대 shinsnote 위치를 준다."""
    if not backbone:
        return None
    exp = [None] * n_rows
    pts = [(0, 0)] + backbone + [(n_rows - 1, n_segs - 1)]
    for (r0, s0), (r1, s1) in zip(pts, pts[1:]):
        if r1 <= r0:
            continue
        for r in range(r0, min(r1 + 1, n_rows)):
            t = (r - r0) / (r1 - r0)
            exp[r] = s0 + t * (s1 - s0)
    fallback_lo, fallback_hi = backbone[0], backbone[-1]
    for i in range(n_rows):
        if exp[i] is None:
            exp[i] = fallback_lo[1] if i < fallback_lo[0] else fallback_hi[1]
    return exp


# ---------------------------------------------------------------- 검출기

def soft_anchors(rows, segs, seg_bg_idx, min_score=0.70):
    """퍼지 매칭 기반 soft anchor.

    완전일치 + 양방향 유일 앵커만 쓰면 블록당 2개가 안 나와 합의가 성립하지 않는다
    (codec 9,057행에 앵커 63개). 우리 번역은 shinsnote를 베낀 게 아니라 독립 번역이라
    완전일치가 드물기 때문이다. Dice 0.7 이상이면 같은 줄로 보고 합의 근거로 쓴다.
    """
    out = {}
    for r in rows:
        if len(r['kkey']) < 8:
            continue
        cand = defaultdict(int)
        for bg in r['bg']:
            for so in seg_bg_idx.get(bg, ()):
                cand[so] += 1
        if not cand:
            continue
        top = sorted(cand.items(), key=lambda kv: -kv[1])[:120]
        best = max(((dice(r['bg'], segs[so]['bg']), so) for so, _ in top), default=(0, -1))
        if best[0] >= min_score:
            out[r['ord']] = (best[1], best[0])
    return out


def block_regions(rows, soft):
    """블록(record/gcx)별로 soft anchor가 모이는 shinsnote 구간을 합의로 산출."""
    by_ord = {r['ord']: r for r in rows}
    per_block = defaultdict(list)
    for ro, (so, sc) in soft.items():
        per_block[by_ord[ro]['block']].append(so)
    region = {}
    for blk, sos in per_block.items():
        if len(sos) < 2:
            continue
        sos.sort()
        med = sos[len(sos) // 2]
        near = [x for x in sos if abs(x - med) <= BLOCK_SPAN]
        if len(near) < 2:
            continue
        region[blk] = (min(near), max(near), len(near), len(sos))
    return region


BLOCK_SPAN = 60   # 한 블록(장면)이 shinsnote에서 차지하는 최대 폭



def build_seg_bigram_index(segs):
    idx = defaultdict(list)
    for s in segs:
        for bg in s['bg']:
            idx[bg].append(s['ord'])
    return idx


def best_matches(row, segs, seg_bg_idx, topn=3, min_len=6):
    """bigram 역색인으로 후보를 좁힌 뒤 Dice로 점수. 전수 비교는 너무 느리다."""
    if len(row['kkey']) < min_len:
        return []
    cand = defaultdict(int)
    for bg in row['bg']:
        for so in seg_bg_idx.get(bg, ()):
            cand[so] += 1
    if not cand:
        return []
    top = sorted(cand.items(), key=lambda kv: -kv[1])[:200]
    scored = [(dice(row['bg'], segs[so]['bg']), so) for so, _ in top]
    scored.sort(reverse=True)
    return scored[:topn]


# 종결어미 -> 화계. 어투 일관성 판정용.
RE_HAECHE = re.compile(r'(어|아|지|네|야|라고|거야|잖아|는데|군|나|니|자|해|돼)[.!?…]*$')
RE_HAPSYO = re.compile(r'(습니다|십니다|입니다|합니다|십시오|세요|어요|예요|이에요|죠)[.!?…]*$')
RE_CONNECTIVE = re.compile(r'(하고|이고|으로|에서|지만|는데|면서|어서|아서|려고|거나|든지|하며)$')
RE_TERMINAL_EN = re.compile(r'[.?!…]\s*$')


def _is_polite_nikka(ch):
    """`-ㅂ니까`(존댓말)와 `-니까`(연결어미)를 가른다.

    `확실합니까?`는 존댓말이고 `필요하니까.`는 반말 연결어미다. 둘 다 `니까`로
    끝나므로 문자열만 보면 구분이 안 된다. 앞 음절의 *종성이 ㅂ*인지로 가른다.
    이 구분을 안 하면 정상 반말이 대량 오탐된다.
    """
    if not ch or not ('가' <= ch <= '힣'):
        return False
    return (ord(ch) - 0xAC00) % 28 == 17          # 종성 ㅂ


def register_of(ko):
    k = strip_tags(ko).strip().rstrip('.!?… ')
    if k.endswith('니까'):
        return 'formal' if _is_polite_nikka(k[-3:-2]) else 'plain'
    k2 = strip_tags(ko).strip()
    if RE_HAPSYO.search(k2):
        return 'formal'
    if RE_HAECHE.search(k2):
        return 'plain'
    return ''


# ---- D7 : 인칭/수 불일치용 어휘 집합
PRON_EN_WE = re.compile(r'\b(we|our|ours|us)\b', re.I)
PRON_EN_I = re.compile(r'\b(i|my|mine|me)\b', re.I)
PRON_KO_WE = re.compile(r'(우리|저희)')
PRON_KO_I = re.compile(r'(내가|내\s|나는|나의|나도|제가|저는)')

# ---- D8 : 응답 유형(발화수반행위) 불일치
#
# "Right." 은 문맥에 따라 *긍정*(맞다)일 수도 *수긍*(알았다)일 수도 있다.
# 앞줄이 물음표로 끝나면 답변이므로 반드시 긍정이어야 하는데, 수긍으로 번역되면
# 화자 역할이 뒤집힌다. movie 44/31 이 그 사례다 -- Snake가 "...증명되나?"라고
# 묻고 Zero가 "Right."로 답하는데 「알았어」로 번역돼 있었다.

EN_AFFIRM = re.compile(r'^(that.?s |thats )?(right|correct|exactly|precisely|affirmative|yes|yeah|yep|true)[.!?…]*$', re.I)
EN_ACK = re.compile(r'^(got it|roger|roger that|understood|copy|copy that|will do|ok|okay|alright|all right)[.!?…]*$', re.I)
KO_AFFIRM = re.compile(r'^(그렇다|맞다|그래|맞아|그렇습니다|맞습니다|그렇지|응|예|네|그러하다)[.!?…]*$')
KO_ACK = re.compile(r'^(알았다|알았어|알겠다|알겠어|알겠습니다|알았습니다|이해했다|알아들었다)[.!?…]*$')


def detect_speechact(container, rows):
    """앞줄이 질문인데 긍정 답변이 수긍으로 번역된 줄(또는 그 반대)."""
    out = []
    for i, r in enumerate(rows):
        en = strip_tags(r['en']).strip()
        ko = strip_tags(r['ko']).strip()
        if not en or not ko or len(en) > 18:
            continue
        prev_en = strip_tags(rows[i - 1]['en']).strip() if i else ''
        prev_is_q = prev_en.endswith('?')
        if EN_AFFIRM.match(en) and KO_ACK.match(ko):
            why = '영어는 긍정(Right/Yes)인데 한국어는 수긍(알았다)'
            score = 0.9 if prev_is_q else 0.45
        elif EN_ACK.match(en) and KO_AFFIRM.match(ko):
            why = '영어는 수긍(Got it/Roger)인데 한국어는 긍정(맞다/그렇다)'
            score = 0.6
        else:
            continue
        if prev_is_q:
            why += '. 앞줄이 질문이라 답변이어야 한다'
        out.append(dict(
            detector='D8-speechact', container=container, loc=r['loc'], score=score,
            english=en[:160], korean=ko[:120], shin_speaker='',
            shin_text=f'앞줄 EN {prev_en[:80]}', shin_pos='', expected_pos='', note=why,
        ))
    return out

def detect_aux(container, rows, budget_of, global_ko=None):
    """정렬과 무관한 검출기 3종.

    D1~D4는 shinsnote 정렬에 기대는데, 정렬이 닿지 않는 결함이 많다.
    (실측: 사용자가 플레이 중 발견한 5건 중 D1~D4가 잡은 것은 1건)
    """
    out = []

    # D6 : 같은 한국어가 서로 다른 영어에 붙음 = 한쪽이 다른 줄에서 새어 온 것.
    #      영어끼리도 닮았으면 정상(`Major,` / `Major!` -> `소령님!`)이므로 제외한다.
    #      *컨테이너를 넘어* 봐야 한다: demo 24/14 의 한국어는 codec 38/15 에서 왔다.
    #      컨테이너별로만 보면 demo 안에 하나뿐이라 원리적으로 못 잡는다.
    index = global_ko if global_ko is not None else {}
    if not index:
        for r in rows:
            if len(r['kkey']) >= 4:
                index.setdefault(r['kkey'], []).append((container, r))
    for r in rows:
        if len(r['kkey']) < 4:
            continue
        group = index.get(r['kkey'], ())
        if len(group) < 2:
            continue
        for oc, other in group:
            if oc == container and other['ord'] == r['ord']:
                continue
            sim = dice(bigrams(r['ekey']), bigrams(other['ekey']))
            if sim >= 0.45:
                continue                   # 영어도 비슷하면 같은 대사다
            out.append(dict(
                detector='D6-dup', container=container, loc=r['loc'],
                score=round(1.0 - sim, 3),
                english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
                shin_speaker='', shin_text=f"같은 한국어가 [{oc} {other['loc']}] "
                                           f"EN {strip_tags(other['en'])[:66]} 에도 붙어 있음",
                shin_pos='', expected_pos='',
                note=f'한국어가 동일한데 영어 유사도 {sim:.2f}. 둘 중 하나는 다른 줄의 번역',
            ))
            break

    # D7 : 인칭/수 불일치. "The Shagohod is ours!" -> "샤고호드는 내 거" 같은 오역.
    for r in rows:
        en, ko = strip_tags(r['en']), strip_tags(r['ko'])
        if len(r['kkey']) < 3:
            continue
        we_en, i_en = bool(PRON_EN_WE.search(en)), bool(PRON_EN_I.search(en))
        we_ko, i_ko = bool(PRON_KO_WE.search(ko)), bool(PRON_KO_I.search(ko))
        if we_en and i_ko and not we_ko:
            why = '영어는 we/our/us 인데 한국어는 나/내'
        elif i_en and we_ko and not i_ko:
            why = '영어는 I/my/me 인데 한국어는 우리'
        else:
            continue
        out.append(dict(
            detector='D7-pronoun', container=container, loc=r['loc'], score=0.75,
            english=en[:160], korean=ko[:120], shin_speaker='', shin_text='',
            shin_pos='', expected_pos='', note=why,
        ))

    # D5 : 과축약. 예산이 넉넉한데 영어 대비 한국어가 지나치게 짧다 = 정보 손실.
    #      예산이 모자라 줄인 것은 결함이 아니므로 사용률이 낮은 것만 본다.
    for r in rows:
        b = budget_of(r)
        if not b or b < 12:
            continue
        used = game_bytes(r['ko'])
        en_len = len(strip_tags(r['en']).strip())
        if en_len < 18:
            continue
        ratio_budget = used / b
        ratio_en = used / en_len
        if ratio_budget <= 0.55 and ratio_en <= 0.55:
            out.append(dict(
                detector='D5-terse', container=container, loc=r['loc'],
                score=round(1.0 - ratio_en, 3),
                english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
                shin_speaker='', shin_text='', shin_pos='', expected_pos='',
                note=f'예산 {used}/{b}B({ratio_budget:.0%})만 쓰고 영어 {en_len}자 대비 '
                     f'{ratio_en:.0%}. 자리가 남는데 줄였다 = 정보 손실 의심',
            ))
    return out



# 검출기 -> 근거 자료. 4자료 중 무엇이 그 판정을 떠받치는지 명시한다.
#   1 = 3DS 영문 대사   2 = 현재 한국어 번역
#   3 = 영문 대사집(화자)  4 = 한국어 대사집(shinsnote)
DETECTOR_SOURCES = {
    'D1-order':     '2+4',
    'D2-register':  '2+3',
    'D3-drift':     '2+4',
    'D4-fragment':  '1+2',
    'D5-terse':     '1+2',
    'D6-dup':       '1+2',
    'D7-pronoun':   '1+2',
    'D8-speechact': '1+2',
    'D9-enpos':     '1+2+3+4',
}

# 신뢰 등급. 근거가 독립적으로 둘 이상이면 높다.
TIERS = [
    ('A', {'D9-enpos', 'D4-fragment'}, 0.0),
    ('A', {'D1-order'}, 0.75),
    ('A', {'D8-speechact'}, 0.85),
    ('B', {'D1-order', 'D2-register', 'D7-pronoun', 'D8-speechact'}, 0.0),
    ('C', set(), 0.0),
]


def tier_of(det, score):
    for name, dets, minsc in TIERS:
        if (not dets or det in dets) and score >= minsc:
            return name
    return 'C'


def attach_en_script(rows, en_script):
    """우리 행 -> 영문 대사집 세그먼트. 영어끼리의 완전일치 + 양방향 유일만 채택.

    자료 (3)이 주는 것은 둘이다.
      1. **화자.** 게임 데이터에는 화자 필드가 아예 없다. shinsnote로 추정하려면
         한국어가 먼저 정렬돼야 하는데 그게 순환이다. 영어는 바로 붙는다.
      2. **서사 위치.** 우리 영어가 대본 어디에 있는지 알면, 그 줄의 한국어가
         엉뚱한 장면에 붙었는지 *한국어 정렬과 독립적으로* 검증할 수 있다.
    """
    if not en_script:
        return {}
    idx, back = {}, {}
    for s in en_script:
        if len(s['key']) >= 8:
            idx.setdefault(s['key'], []).append(s)
    for r in rows:
        if len(r['ekey']) < 8:
            continue
        g = idx.get(r['ekey'])
        if g and len(g) == 1:
            back.setdefault(g[0]['ord'], []).append(r)
    out = {}
    for so, rs in back.items():
        if len(rs) != 1:
            continue                        # 한 대사가 여러 행에 붙으면 화자 확정 불가
        s = en_script[so]
        out[rs[0]['ord']] = s
    return out


def map_en_to_shin(rows, en_map, soft):
    """영문 대사집 색인 -> shinsnote 색인 대응.

    두 자료는 같은 대본의 영어판/한국어판이고 둘 다 서사 순서다. 양쪽 앵커를
    *동시에* 가진 행이 곧 대응쌍이다. 그 쌍들로 LIS를 잡고 사이를 보간한다.
    """
    pairs = sorted((en_map[ro]['ord'], soft[ro][0]) for ro in en_map if ro in soft)
    if len(pairs) < 4:
        return None, pairs
    backbone, _ = lis_backbone(pairs)
    if len(backbone) < 4:
        return None, pairs

    def predict(en_ord):
        lo = None
        for e, s in backbone:
            if e <= en_ord:
                lo = (e, s)
            else:
                if lo is None:
                    return float(s)
                de, ds = e - lo[0], s - lo[1]
                return lo[1] + (ds * (en_ord - lo[0]) / de if de else 0)
        return float(backbone[-1][1])
    return predict, pairs


def detect(container, rows, segs, en_script=None, verbose=True, global_ko=None):
    findings = []
    anchors = build_anchors(rows, segs)
    backbone, violations = lis_backbone(anchors)
    exp = interpolate(backbone, len(rows), len(segs))
    seg_bg_idx = build_seg_bigram_index(segs)

    if verbose:
        dens = f'{len(rows)/max(1,len(backbone)):.1f}' if backbone else 'n/a'
        print(f'[{container}] 행 {len(rows)} | shinsnote 세그 {len(segs)} | '
              f'앵커 {len(anchors)} (백본 {len(backbone)}, 위반 {len(violations)}) | '
              f'백본 1개당 {dens}행', file=sys.stderr)

    by_ord = {r['ord']: r for r in rows}

    # ---- D1 : 오매핑 후보
    #      근거 두 갈래를 합친다.
    #        (a) 전역 LIS 위반 앵커       - 완전일치라 근거가 강함
    #        (b) 블록 합의 구간 밖 soft anchor - 퍼지라 넓게 잡힘
    #      단, 블록이 *통째로* 그 위치를 가리키면 오탐이다 (demo 288 = HALO 오프닝이
    #      record 뒤쪽에 저장됨). 그 경우는 억제한다.
    soft = soft_anchors(rows, segs, seg_bg_idx)
    region = block_regions(rows, soft)
    seen = set()

    def emit(ro, so, why, base):
        if ro in seen:
            return
        r = by_ord[ro]
        blk = r['block']
        reg = region.get(blk)
        if reg:
            lo, hi, nnear, ntot = reg
            if lo - BLOCK_SPAN <= so <= hi + BLOCK_SPAN:
                return                     # 블록이 통째로 여기 있다 -> 정상
            dist = min(abs(so - lo), abs(so - hi))
            conf, ev = base + 0.25, f'블록 앵커 {nnear}/{ntot}개는 seg{lo}~{hi}'
            expected = f'seg{lo}~{hi}'
        else:
            dist = abs(so - exp[ro]) if exp else 0
            conf, ev = base, '블록 내 합의 근거 없음(앵커 부족)'
            expected = f'seg~{int(exp[ro])}' if exp else ''
        seen.add(ro)
        sg = segs[so]
        findings.append(dict(
            detector='D1-order', container=container, loc=r['loc'],
            score=round(min(1.0, conf), 3),
            english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
            shin_speaker=sg['speaker'], shin_text=sg['text'][:120],
            shin_pos=f"p{sg['page']}/{sg['sequence']}", expected_pos=expected,
            note=f'{why}. {ev}인데 이 줄만 seg{so} (거리 {int(dist)})',
        ))

    for ro, so in violations:
        emit(ro, so, '완전일치 앵커가 정렬 백본을 위반', 0.55)
    for ro, (so, sc) in sorted(soft.items()):
        if ro in seen or by_ord[ro]['block'] not in region:
            continue
        emit(ro, so, f'퍼지 일치(Dice {sc:.2f})가 블록 합의 구간 밖', 0.35)

    # ---- D3 : 제자리 유사도는 낮은데 다른 장면 줄과 훨씬 더 닮음
    if exp:
        WINDOW = 40
        for r in rows:
            if len(r['kkey']) < 8:
                continue
            bm = best_matches(r, segs, seg_bg_idx, topn=1)
            if not bm:
                continue
            score, so = bm[0]
            if score < 0.55:
                continue                      # 어디에도 안 닮으면 판단 불가(독립 번역)
            if abs(so - exp[r['ord']]) <= WINDOW:
                continue                      # 제자리에 있다
            s = segs[so]
            # 점수는 유사도가 아니라 *이상치 정도*여야 한다.
            # 유사도를 그대로 쓰면 제대로 번역된 줄이 1.0으로 맨 위에 온다.
            anomaly = score * min(1.0, abs(so - exp[r['ord']]) / 400.0)
            findings.append(dict(
                detector='D3-drift', container=container, loc=r['loc'],
                score=round(anomaly, 3),
                english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
                shin_speaker=s['speaker'], shin_text=s['text'][:120],
                shin_pos=f"p{s['page']}/{s['sequence']}",
                expected_pos=f"seg~{int(exp[r['ord']])}",
                note=f'shinsnote seg{so}(거리 {int(abs(so-exp[r["ord"]]))})와 유사도 '
                     f'{score:.2f}로 강하게 일치. 그 장면 번역이 새어 들어왔는지 확인',
            ))

    # ---- D4 : 조각 (다른 줄 앞부분과 일치 + 영어 대비 과도하게 짧음)
    #      영어가 완결문인데 한국어가 연결어미로 끊기는 경우만 채택 -> 오탐 억제
    ko_index = defaultdict(list)
    for r in rows:
        if len(r['kkey']) >= 4:
            ko_index[r['kkey']].append(r)
    for r in rows:
        k = strip_tags(r['ko']).strip()
        en = strip_tags(r['en']).strip()
        if not k or not en:
            continue
        incomplete = bool(RE_CONNECTIVE.search(k)) and bool(RE_TERMINAL_EN.search(en))
        if not incomplete:
            continue
        src = ''
        for s in segs:
            if s['key'].startswith(r['kkey']) and len(s['key']) > len(r['kkey']) + 2:
                src = f"shinsnote p{s['page']}/{s['sequence']} [{s['speaker']}] {s['text'][:70]}"
                break
        findings.append(dict(
            detector='D4-fragment', container=container, loc=r['loc'], score=0.9,
            english=en[:160], korean=k[:120], shin_speaker='', shin_text=src[:160],
            shin_pos='', expected_pos='',
            note='영어는 완결문인데 한국어가 연결어미로 끊김 = 조각. '
                 + ('출처 후보 찾음' if src else '출처 미상'),
        ))

    # ---- D2 : 화자 어투 일관성 (백본 근처에서 화자가 확정되는 행만)
    if exp and backbone:
        spk_reg = defaultdict(Counter)
        aligned = []
        for r in rows:
            so = int(round(exp[r['ord']]))
            if not (0 <= so < len(segs)):
                continue
            bm = best_matches(r, segs, seg_bg_idx, topn=1)
            if not bm or bm[0][0] < 0.45 or abs(bm[0][1] - so) > 10:
                continue                       # 화자 확정 근거가 약하면 건너뛴다
            s = segs[bm[0][1]]
            reg = register_of(r['ko'])
            if not reg or not s['speaker']:
                continue
            spk_reg[s['speaker']][reg] += 1
            aligned.append((r, s, reg))
        for r, s, reg in aligned:
            c = spk_reg[s['speaker']]
            total = sum(c.values())
            if total < 5:
                continue                       # 표본 부족
            major, n = c.most_common(1)[0]
            if reg != major and n / total >= 0.8:
                findings.append(dict(
                    detector='D2-register', container=container, loc=r['loc'],
                    score=round(n / total, 3),
                    english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
                    shin_speaker=s['speaker'], shin_text=s['text'][:120],
                    shin_pos=f"p{s['page']}/{s['sequence']}", expected_pos='',
                    note=f'{s["speaker"]}의 어투는 {major} {n}/{total}인데 이 줄만 {reg}',
                ))
    def budget_of(r):
        raw = r['raw']
        if raw.get('size'):
            try:
                return int(raw['size']) - 1
            except ValueError:
                return 0
        if raw.get('max_bytes'):
            try:
                return int(raw['max_bytes'])
            except ValueError:
                return 0
        return game_bytes(r['ko'])          # codec: 현재 길이를 예산 대용으로

    findings += detect_aux(container, rows, budget_of, global_ko)
    findings += detect_speechact(container, rows)

    # ---- 자료 (3) 영문 대사집이 있을 때만 도는 검출기
    en_map = attach_en_script(rows, en_script)
    if en_map:
        predict, pairs = map_en_to_shin(rows, en_map, soft)
        if verbose:
            print(f'[{container}] 영문 대사집 매칭 {len(en_map)}행 | '
                  f'영·한 동시 앵커 {len(pairs)}쌍 | 위치 예측 '
                  f'{"가능" if predict else "불가(쌍 부족)"}', file=sys.stderr)

        # ---- D9 : 영어 위치와 한국어 위치가 어긋남
        #      한국어 정렬만 보는 D1과 달리, *영어가 대본 어디에 있는지*를 독립
        #      근거로 쓴다. 두 자료가 서로를 반증하므로 오탐이 적다.
        if predict:
            for ro, s in en_map.items():
                if ro not in soft:
                    continue
                got = soft[ro][0]
                want = predict(s['ord'])
                gap = abs(got - want)
                if gap < 120:
                    continue
                # 흔한 대사는 대본에 여러 번 나온다. 예측 위치의 shinsnote 문장과도
                # 닮았다면 '다른 출현에 붙었을 뿐 번역은 맞다'는 뜻이므로 억제한다.
                wi = int(round(want))
                if 0 <= wi < len(segs) and dice(r0['bg'] if False else by_ord[ro]['bg'],
                                                segs[wi]['bg']) >= 0.5:
                    continue
                r = by_ord[ro]
                sg = segs[got]
                findings.append(dict(
                    detector='D9-enpos', container=container, loc=r['loc'],
                    score=round(min(1.0, gap / 600.0) * 0.5 + 0.5, 3),
                    english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
                    shin_speaker=sg['speaker'], shin_text=sg['text'][:120],
                    shin_pos=f"p{sg['page']}/{sg['sequence']}",
                    expected_pos=f'shin~{int(want)}',
                    note=f'영문 대사집에서 이 줄은 [{s["speaker"]}] 대사이고 대본 '
                         f'{s["ord"]}번째다. 거기에 대응하는 shinsnote 위치는 ~{int(want)}인데 '
                         f'한국어는 {got}에 붙는다 (거리 {int(gap)})',
                ))

        # ---- D2b : 확정 화자 기준 어투 일관성
        #      기존 D2는 shinsnote 앵커로 화자를 추정해 앵커 부족으로 거의 못 돌았다.
        #      영문 대사집은 화자를 직접 준다.
        spk = defaultdict(Counter)
        for ro, s in en_map.items():
            reg = register_of(by_ord[ro]['ko'])
            if reg:
                spk[s['speaker']][reg] += 1
        for ro, s in en_map.items():
            reg = register_of(by_ord[ro]['ko'])
            c = spk[s['speaker']]
            total = sum(c.values())
            if not reg or total < 8:
                continue
            major, n = c.most_common(1)[0]
            if reg != major and n / total >= 0.85:
                r = by_ord[ro]
                findings.append(dict(
                    detector='D2-register', container=container, loc=r['loc'],
                    score=round(n / total, 3),
                    english=strip_tags(r['en'])[:160], korean=strip_tags(r['ko'])[:120],
                    shin_speaker=s['speaker'], shin_text='', shin_pos='', expected_pos='',
                    note=f'{s["speaker"]}의 어투는 {major} {n}/{total}인데 이 줄만 {reg} '
                         f'(화자는 영문 대사집 확정)',
                ))

    return findings, dict(rows=len(rows), segs=len(segs), anchors=len(anchors),
                          backbone=len(backbone), violations=len(violations))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description='4자료 교차 검증으로 번역 결함 후보를 찾는다')
    ap.add_argument('--containers', default='codec,movie,demo',
                    help='쉼표 구분. codec,movie,demo,vox (기본: vox 제외 - shinsnote가 vox를 안 덮는다)')
    ap.add_argument('--en-script', default=None,
                    help='(3) 영문 대사집 JSON. shinsnote와 같은 스키마. 있으면 앵커 밀도가 오른다')
    ap.add_argument('--out-dir', default='translation/10_master/review/crossvalidate')
    ap.add_argument('--min-score', type=float, default=0.0)
    args = ap.parse_args()

    en_script = load_en_script(args.en_script)
    if en_script:
        print(f'[en-script] {len(en_script)} 세그먼트 로드', file=sys.stderr)

    out_dir = os.path.join(ROOT, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    all_findings, summary = [], {}

    names = [c.strip() for c in args.containers.split(',') if c.strip()]

    # D6는 컨테이너를 넘어 봐야 하므로 전 컨테이너를 먼저 읽어 한국어 전역 인덱스를 만든다.
    loaded = {n: load_rows(CONTAINERS[n]) for n in names}
    global_ko = defaultdict(list)
    for n, rs in loaded.items():
        for r in rs:
            if len(r['kkey']) >= 4:
                global_ko[r['kkey']].append((n, r))
    print(f'[global] 한국어 인덱스 {len(global_ko)}개 (컨테이너 {len(loaded)}종)', file=sys.stderr)

    for name in names:
        cfg = CONTAINERS[name]
        rows = loaded[name]
        segs = load_shinsnote(cfg['shin'])
        f, stat = detect(name, rows, segs, en_script, global_ko=global_ko)
        f = [x for x in f if x['score'] >= args.min_score]
        f.sort(key=lambda x: (-x['score'], x['detector']))
        all_findings += f
        summary[name] = dict(stat, findings=len(f))
        p = os.path.join(out_dir, f'{name}-findings.csv')
        cols = ['detector', 'container', 'loc', 'score', 'english', 'korean',
                'shin_speaker', 'shin_text', 'shin_pos', 'expected_pos', 'note']
        with open(p, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(f)
        print(f'  -> {p}  ({len(f)}건)', file=sys.stderr)

    # ---- 통합 워크리스트: 네 컨테이너를 한 파일로, 신뢰 등급순
    for x in all_findings:
        x['sources'] = DETECTOR_SOURCES.get(x['detector'], '')
        x['tier'] = tier_of(x['detector'], float(x.get('score') or 0))
    order = {'A': 0, 'B': 1, 'C': 2}
    all_findings.sort(key=lambda x: (order[x['tier']], -float(x.get('score') or 0),
                                     x['container'], x['detector']))
    wl = os.path.join(out_dir, 'worklist.csv')
    wcols = ['tier', 'sources', 'detector', 'container', 'loc', 'score',
             'english', 'korean', 'shin_speaker', 'shin_text', 'shin_pos',
             'expected_pos', 'note']
    with open(wl, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=wcols, extrasaction='ignore')
        w.writeheader()
        w.writerows(all_findings)
    tc = {}
    for x in all_findings:
        tc[x['tier']] = tc.get(x['tier'], 0) + 1
    summary['worklist'] = dict(total=len(all_findings), by_tier=tc)
    print('', file=sys.stderr)
    print(f'통합 워크리스트 -> {wl}', file=sys.stderr)
    print(f'  A(우선 검토) {tc.get("A",0)} | B(검토) {tc.get("B",0)} | '
          f'C(참고) {tc.get("C",0)}', file=sys.stderr)

    with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    print('\n=== 요약 ===', file=sys.stderr)
    for k, v in summary.items():
        if k == 'worklist':
            continue
        print(f'  {k:6} 행 {v["rows"]:>5}  백본 {v["backbone"]:>4}  '
              f'순서위반 {v["violations"]:>3}  결함후보 {v["findings"]:>4}', file=sys.stderr)
    by_det = {}
    for x in all_findings:
        by_det[x['detector']] = by_det.get(x['detector'], 0) + 1
    for k, v in sorted(by_det.items()):
        print(f'  {k:14} {v}', file=sys.stderr)


if __name__ == '__main__':
    main()
