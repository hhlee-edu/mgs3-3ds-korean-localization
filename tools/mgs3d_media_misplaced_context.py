# -*- coding: utf-8 -*-
"""Build per-record recovery context for movie/demo MISPLACED rows.

READ-ONLY. Never writes to master / *.dat / staging.

For each MISPLACED row it emits:
  * the full master record (English preview + current Korean), in entry order
  * the script reference transcript window that the record's *other* lines anchor to

Scene anchoring uses several neighbouring lines at once, never a single unique
string -- the failure mode documented in
docs/evidence/2026-08-19-media-offset-audit/README.md sections 3 and 6.
"""
import csv, io, os, re, glob, argparse, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHINS = os.path.join(ROOT, 'translation/00_source/script_ref/original_scrape')
VERDICTS = os.path.join(ROOT, 'output/media-register-qa/media-offset-verdicts-reviewed.csv')
MASTER = {'demo': os.path.join(ROOT, 'translation/10_master/current/demo.csv'),
          'movie': os.path.join(ROOT, 'translation/10_master/current/movie.csv')}

NAV = re.compile(r'^메탈기어솔리드3\s*:?\s*스네이크 이터\s*-\s*한글대사')
HDR = re.compile(r'^메탈기어솔리드3매뉴얼-한글대사\(\d+\)$')
URL = re.compile(r'^https?://')
SPK = re.compile(r'^([^:：]{1,14})\s*[:：]\s*(.+)$')
PUNCT = re.compile(r'[\s.,!?~\'"()\[\]<>·…‥\-—:;]+')


def norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    return PUNCT.sub('', s)


def load_script_ref():
    out = []
    files = sorted(glob.glob(os.path.join(SHINS, '*.txt')),
                   key=lambda p: int(re.search(r'\((\d+)\)', p).group(1)))
    for p in files:
        page = int(re.search(r'\((\d+)\)', p).group(1))
        for ln, line in enumerate(io.open(p, encoding='utf-8-sig').read().split('\n')):
            s = line.strip()
            if not s or HDR.match(s) or NAV.match(s) or URL.match(s):
                continue
            m = SPK.match(s)
            spk, body = (m.group(1).strip(), m.group(2).strip()) if m else ('', s)
            out.append({'seq': len(out), 'page': page, 'ln': ln,
                        'speaker': spk, 'text': body, 'norm': norm(body)})
    return out


def read_csv(p):
    with io.open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def bigrams(n):
    return set(n[i:i + 2] for i in range(len(n) - 1)) if len(n) > 1 else {n}


def sim(a, b):
    if not a or not b:
        return 0.0
    if min(len(a), len(b)) >= 10 and (a in b or b in a):
        return 1.0
    A, B = bigrams(a), bigrams(b)
    return len(A & B) / float(len(A | B))


def anchor_window(corpus, korean_lines, pad=12, thr=1.0, minlen=10):
    """Locate the scene: collect every corpus hit for each anchor line, then keep
    the densest cluster. Requires >=2 distinct anchors to report a window."""
    hits = []
    for ko in korean_lines:
        n = norm(ko)
        if len(n) < minlen:
            continue                      # too short to locate anything
        for c in corpus:
            if sim(n, c['norm']) >= thr:
                hits.append((c['seq'], n))
    if not hits:
        return None, 0, 0
    best, best_span = None, None
    for s0, _ in hits:
        near = [(s, n) for s, n in hits if abs(s - s0) <= 60]
        distinct = len(set(n for _, n in near))
        span = (distinct, -(max(s for s, _ in near) - min(s for s, _ in near)))
        if best_span is None or span > best_span:
            best_span, best = span, near
    distinct = len(set(n for _, n in best))
    lo = max(0, min(s for s, _ in best) - pad)
    hi = min(len(corpus), max(s for s, _ in best) + pad + 1)
    return (lo, hi), distinct, len(best)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--media')
    ap.add_argument('--records', help='comma list of record numbers')
    ap.add_argument('--start', type=int, default=0, help='skip first N misplaced records')
    ap.add_argument('--limit', type=int, default=6, help='number of records to print')
    ap.add_argument('--grep', help='search the script reference corpus for this substring instead')
    ap.add_argument('--seq', help='print corpus window LO:HI instead')
    ap.add_argument('--gap', action='store_true', help='per-row in-record interpolation report')
    ap.add_argument('--pin', action='store_true', help='pin each record via its single longest distinctive line')
    ap.add_argument('--nowin', action='store_true', help='master record context only, no the script reference window')
    a = ap.parse_args()

    corpus = load_script_ref()
    if a.seq:
        lo, hi = (int(x) for x in a.seq.split(':'))
        for c in corpus[max(0, lo):hi]:
            print('[%4d p%-2d] %s%s' % (c['seq'], c['page'],
                  (c['speaker'] + ' : ') if c['speaker'] else '', c['text'][:100]))
        return
    if a.grep:
        pats = [x for x in a.grep.split('|') if x]
        for c in corpus:
            if any(x in c['text'] for x in pats):
                print('[%4d p%-2d] %s%s' % (c['seq'], c['page'],
                      (c['speaker'] + ' : ') if c['speaker'] else '', c['text'][:100]))
        return
    verd = read_csv(VERDICTS)
    mis = [r for r in verd if r['verdict'] == 'MISPLACED']
    misk = set((r['media'], r['record'], r['entry']) for r in mis)

    master = {}
    for m, p in MASTER.items():
        for r in read_csv(p):
            master.setdefault((m, r['record']), []).append(r)
    for v in master.values():
        v.sort(key=lambda r: int(r['entry']))

    recs = []
    for r in mis:
        k = (r['media'], r['record'])
        if k not in recs:
            recs.append(k)
    if a.media:
        recs = [k for k in recs if k[0] == a.media]
    if a.records:
        want = set(a.records.split(','))
        recs = [k for k in recs if k[1] in want]
    recs = recs[a.start:a.start + a.limit]

    if a.pin:
        for media, rec in recs:
            ents = master.get((media, rec), [])
            targets = [r for r in mis if r['media'] == media and r['record'] == rec]
            cands = sorted(((len(norm(e['korean'] or '')), e) for e in ents
                            if (media, rec, e['entry']) not in misk),
                           key=lambda x: -x[0])[:3]
            pin, pinscore, pinent = None, 0.0, None
            for L, e in cands:
                if L < 12:
                    continue
                n = norm(e['korean'])
                sc, sq = max((sim(n, c['norm']), c['seq']) for c in corpus)
                if sc > pinscore:
                    pin, pinscore, pinent = sq, sc, e
            print('== %s r%s ==  targets: %s' % (media, rec,
                  ','.join('e' + t['entry'] for t in targets)))
            for t in targets:
                print('   e%-3s EN  %s' % (t['entry'], (t['english'] or '')[:74]))
                print('        KO! %s' % (t['korean'] or '')[:74])
            if pin is None or pinscore < 0.6:
                print('   NO PIN (best score %.2f)' % pinscore)
                for L, e in cands[:2]:
                    print('     cand e%-3s %s' % (e['entry'], (e['korean'] or '')[:70]))
                print()
                continue
            print('   pin e%s score %.2f -> seq %d' % (pinent['entry'], pinscore, pin))
            for c in corpus[max(0, pin - 9):pin + 10]:
                print('     [%4d] %s%s' % (c['seq'],
                      (c['speaker'] + ' : ') if c['speaker'] else '', c['text'][:74]))
            print()
        return

    if a.gap:
        for media, rec in recs:
            ents = master.get((media, rec), [])
            targets = [r for r in mis if r['media'] == media and r['record'] == rec]
            # 1. every plausible corpus position for each clean entry
            cand = {}
            for e in ents:
                if (media, rec, e['entry']) in misk:
                    continue
                n = norm(e['korean'] or '')
                if len(n) < 8:
                    continue
                hits = [(sim(n, c['norm']), c['seq']) for c in corpus]
                hits = [h for h in hits if h[0] >= 0.7]
                if hits:
                    cand[int(e['entry'])] = hits
            # 2. densest cluster across entries = the scene window
            flat = [s for v in cand.values() for _, s in v]
            best = None
            for s0 in flat:
                near = [(k, v) for k, v in cand.items() if any(abs(s - s0) <= 45 for _, s in v)]
                if best is None or len(near) > len(best[1]):
                    best = (s0, near)
            if not best or len(best[1]) < 2:
                for t in targets:
                    print('== %s r%s e%s ==  SCENE UNRESOLVED (%d anchor entries)'
                          % (media, rec, t['entry'], len(cand)))
                    print('   EN  %s' % (t['english'] or '')[:78])
                    print('   KO! %s' % (t['korean'] or '')[:78])
                    print()
                continue
            s0 = best[0]
            loc = {}
            for k, v in best[1]:
                inwin = [(sc, s) for sc, s in v if abs(s - s0) <= 45]
                if inwin:
                    loc[k] = max(inwin)[1]
            for t in targets:
                en = int(t['entry'])
                before = [v for k, v in loc.items() if k < en]
                after = [v for k, v in loc.items() if k > en]
                lo = max(before) if before else (min(loc.values()) - 6 if loc else None)
                hi = min(after) if after else (max(loc.values()) + 6 if loc else None)
                print('== %s r%s e%s ==' % (media, rec, t['entry']))
                print('   EN  %s' % (t['english'] or '')[:78])
                print('   KO! %s' % (t['korean'] or '')[:78])
                if lo is not None and hi is not None and hi - lo <= 14:
                    print('   gap %d..%d' % (lo, hi))
                    for c in corpus[max(0, lo):hi + 1]:
                        print('     [%4d] %s%s' % (c['seq'],
                              (c['speaker'] + ' : ') if c['speaker'] else '', c['text'][:74]))
                else:
                    print('   gap TOO WIDE lo=%s hi=%s' % (lo, hi))
                print()
        return

    for media, rec in recs:
        ents = master.get((media, rec), [])
        targets = [r for r in mis if r['media'] == media and r['record'] == rec]
        print('=' * 78)
        print('%s record %s   (MISPLACED %d / %d entries)'
              % (media, rec, len(targets), len(ents)))
        print('=' * 78)
        print('-- master record context --')
        for e in ents:
            mark = '>>' if (media, rec, e['entry']) in misk else '  '
            print('%s e%-3s %s' % (mark, e['entry'], (e['preview'] or '').replace('<END>', '')[:64]))
            print('%s      KO %s' % (mark, (e['korean'] or '')[:64]))
        print('-- where each misplaced KO actually lives in the script reference --')
        for t in targets:
            n = norm(t['korean'])
            loc = [c for c in corpus if n and len(n) >= 4 and (n == c['norm'] or (len(n) >= 8 and n in c['norm']))]
            tag = ', '.join('%d(%s)' % (c['seq'], c['speaker'] or '-') for c in loc[:4]) or 'not found'
            print('   e%-3s KO %-34s -> %s' % (t['entry'], (t['korean'] or '')[:34], tag))
        if a.nowin:
            print()
            continue
        clean = [e['korean'] for e in ents
                 if (media, rec, e['entry']) not in misk and e['korean']]
        win, distinct, nhits = anchor_window(corpus, clean)
        print('-- the script reference anchor: %d distinct anchor line(s), %d hit(s) --'
              % (distinct, nhits))
        if win and distinct >= 2:
            lo, hi = win
            for c in corpus[lo:hi]:
                print('   [%4d p%-2d] %s%s' % (c['seq'], c['page'],
                                               (c['speaker'] + ' : ') if c['speaker'] else '', c['text'][:76]))
        else:
            print('   (no reliable window - fewer than 2 distinct anchors)')
        print()


if __name__ == '__main__':
    main()
