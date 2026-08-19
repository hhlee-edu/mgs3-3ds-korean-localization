# -*- coding: utf-8 -*-
"""Build the movie/demo misplaced-recovery deliverables.

READ-ONLY with respect to master / *.dat / staging / the reviewed verdict CSV.
Writes only into docs/evidence/2026-08-19-media-misplaced-recovery/.

Usage:
    python tools/mgs3d_media_recovery_build.py <findings.jsonl> <suspects.jsonl>
"""
import csv
import io
import json
import os
import re
import sys
import collections
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location(
    'ctx', os.path.join(HERE, 'mgs3d_media_misplaced_context.py'))
ctx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ctx)

OUT = os.path.join(ROOT, 'docs/evidence/2026-08-19-media-misplaced-recovery')

REC_COLS = ['media', 'record', 'entry', 'english', 'current_korean',
            'previous_english', 'next_english', 'speaker', 'addressee',
            'speaker_confidence', 'scene_context', 'speaker_source',
            'mismatch_reason', 'replacement_korean', 'replacement_source',
            'replacement_confidence', 'action', 'position_check', 'note']

SPK_COLS = ['media', 'record', 'entry', 'english', 'korean', 'speaker',
            'addressee', 'speaker_confidence', 'scene_context', 'speaker_source']


SPEAKER_NAMES = {
    '스네이크': '스네이크 (Snake)',
    '에바': '에바 (EVA)',
    '소령': '소령 (Major Zero)',
    '패러메딕': '패러메딕 (Para-Medic)',
    '시긴토': '시긴토 (Sigint)',
    '더 보스': '더 보스 (The Boss)',
    '볼긴': '볼긴 (Volgin)',
    '오셀롯': '오셀롯 (Ocelot)',
    '소코로프': '소코로프 (Sokolov)',
    '그라닌': '그라닌 (Granin)',
    '타티아나': '타티아나 (Tatyana)',
    '잭': '잭 (Jack)',
    '후르시쵸프': '후르시쵸프 (Khrushchev)',
    '존슨': '존슨 (Johnson)',
    '병사': '병사 (a soldier)',
    '파일럿': '파일럿 (the pilot)',
    '더 페인': '더 페인 (The Pain)',
    '디 엔드': '디 엔드 (The End)',
    '더 퓨리': '더 퓨리 (The Fury)',
    '더 피어': '더 피어 (The Fear)',
    '더 소로우': '더 소로우 (The Sorrow)',
    '미그기 파일럿': '미그기 파일럿 (the MiG pilot)',
    '에바의 목소리': '에바 (EVA, voice-over)',
    '방송': '방송 (announcement)',
    '무전': '무전 (radio)',
    '대통령': '대통령 (the President)',
}


def norm_speaker(name):
    """Normalise a transcript label to the '한글 (English)' form used elsewhere.

    '???' is the transcript's own marker for a character whose identity is
    deliberately withheld at that point, so it is reported as UNKNOWN rather
    than being passed off as an identified speaker.
    """
    n = (name or '').strip().lstrip('(').strip()
    if not n or n == '???':
        return 'UNKNOWN', True
    return SPEAKER_NAMES.get(n, n), False


def clean(s):
    return (s or '').replace('<END>', '').replace('|', ' ').strip()


def seq_of(finding):
    """Pull the shinsnote sequence number out of a replacement_source string."""
    src = finding.get('replacement_source') or ''
    for tok in src.replace('seq', ' ').split():
        if tok.isdigit():
            return int(tok)
    return None


def label_at(corpus, i):
    """Explicit speaker label on this line, or the nearest one it continues."""
    for j in range(i, max(-1, i - 6), -1):
        if corpus[j]['speaker']:
            return corpus[j]['speaker'], j
    return '', None


LOCK_RE = re.compile(r'(e\d+(?:[/-]e?\d+)*)\s*=\s*(\d{2,4})')
OWNER_RE = re.compile(r'(?:record\s+|r)(\d{1,3})\b')


def parse_locks(note, own_record):
    """Read the hand-written 'Record lock: e4=2155, e19/e24=2158' annotations.

    A note may describe more than one record ('...; record 322 continues e2=...'),
    so the note is segmented and each segment is attributed to the record named
    in it, defaulting to the finding's own record. Returns {entry: seq}.
    """
    out = {}
    for seg in re.split(r'[;.]', note or ''):
        owner = own_record
        m = OWNER_RE.search(seg)
        if m:
            owner = m.group(1)
        if owner != own_record:
            continue
        for ents, seq in LOCK_RE.findall(seg):
            for e in re.findall(r'e?(\d+)', ents):
                out[e] = int(seq)
    return out


def write_csv(path, cols, rows):
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\r\n')
        w.writeheader()
        w.writerows(rows)


def main():
    findings_path, suspects_path = sys.argv[1], sys.argv[2]
    os.makedirs(OUT, exist_ok=True)

    corpus = ctx.load_shinsnote()
    verd = ctx.read_csv(ctx.VERDICTS)
    misk = set((r['media'], r['record'], r['entry'])
               for r in verd if r['verdict'] == 'MISPLACED')

    master = {}
    for media, path in ctx.MASTER.items():
        for r in ctx.read_csv(path):
            master.setdefault((media, r['record']), []).append(r)
    for v in master.values():
        v.sort(key=lambda r: int(r['entry']))

    found = [json.loads(l) for l in io.open(findings_path, encoding='utf-8') if l.strip()]
    bykey = dict(((f['media'], f['record'], f['entry']), f) for f in found)

    # ---- 1. recovery sheet -------------------------------------------------
    rows = []
    for r in verd:
        if r['verdict'] != 'MISPLACED':
            continue
        f = bykey[(r['media'], r['record'], r['entry'])]
        ents = master.get((r['media'], r['record']), [])
        idx = next((i for i, e in enumerate(ents) if e['entry'] == r['entry']), None)
        prev = clean(ents[idx - 1]['preview']) if idx not in (None, 0) else ''
        nxt = clean(ents[idx + 1]['preview']) if idx is not None and idx + 1 < len(ents) else ''
        rows.append({
            'media': r['media'], 'record': r['record'], 'entry': r['entry'],
            'english': clean(r['english']), 'current_korean': r['korean'],
            'previous_english': prev, 'next_english': nxt,
            'speaker': f['speaker'], 'addressee': f['addressee'],
            'speaker_confidence': f['speaker_confidence'],
            'scene_context': f['scene_context'],
            'speaker_source': f['speaker_source'],
            'mismatch_reason': f['mismatch_reason'],
            'replacement_korean': f['replacement_korean'],
            'replacement_source': f['replacement_source'],
            'replacement_confidence': f['replacement_confidence'],
            'action': f['action'], 'position_check': f['position_check'],
            'note': f['note'],
        })
    rows.sort(key=lambda r: (r['media'], int(r['record']), int(r['entry'])))
    write_csv(os.path.join(OUT, 'media-misplaced-recovery.csv'), REC_COLS, rows)

    # ---- 2. speaker/context sheet -----------------------------------------
    spk = []
    for r in rows:
        row = dict((c, r.get(c, '')) for c in SPK_COLS)
        row['korean'] = r['current_korean']
        spk.append(row)

    # KEEP rows come from the hand-verified record locks written into the
    # findings notes while each scene was read. Every pair is validated three
    # ways before it is emitted:
    #   1. the entry must actually exist in master for that record
    #   2. the sequence must be inside the record's confirmed scene window
    #   3. entries in ascending order must map to non-decreasing sequences
    # Anything that fails is dropped rather than guessed at.
    scene = {}
    for f in found:
        s = seq_of(f)
        if s is not None:
            scene.setdefault((f['media'], f['record']), []).append(s)

    locks = {}
    for f in found:
        key = (f['media'], f['record'])
        for ent, seq in parse_locks(f.get('note'), f['record']).items():
            locks.setdefault(key, {}).setdefault(ent, seq)

    extra, dropped = 0, collections.Counter()
    for (media, rec), table in locks.items():
        ents = master.get((media, rec), [])
        valid_entries = set(e['entry'] for e in ents)
        anchors = scene.get((media, rec))
        lo = min(anchors) - 40 if anchors else None
        hi = max(anchors) + 40 if anchors else None

        pairs = []
        for ent, seq in table.items():
            if ent not in valid_entries:
                dropped['entry not in master'] += 1
                continue
            if not (0 <= seq < len(corpus)):
                dropped['sequence out of range'] += 1
                continue
            if lo is not None and not (lo <= seq <= hi):
                dropped['outside confirmed window'] += 1
                continue
            pairs.append((int(ent), ent, seq))
        pairs.sort()
        prev = -1
        kept = []
        for _, ent, seq in pairs:
            if seq < prev:
                dropped['non-monotonic'] += 1
                continue
            prev = seq
            kept.append((ent, seq))

        byent = dict((e['entry'], e) for e in ents)
        for ent, seq in kept:
            if (media, rec, ent) in misk:
                continue                      # already emitted above
            lab, li = label_at(corpus, seq)
            if not lab:
                dropped['no speaker label'] += 1
                continue
            name, hidden = norm_speaker(lab)
            spk.append({
                'media': media, 'record': rec, 'entry': ent,
                'english': clean(byent[ent]['preview']),
                'korean': byent[ent]['korean'],
                'speaker': name, 'addressee': '',
                'speaker_confidence': 'LOW' if hidden else ('HIGH' if li == seq else 'MEDIUM'),
                'scene_context': 'shinsnote seq%d, from the record lock verified while reading this scene' % seq,
                'speaker_source': 'shinsnote seq%d; explicit label on seq%d%s'
                                  % (seq, li, '' if li == seq else ' (continuation of the same speaker)'),
            })
            extra += 1
    if dropped:
        print('lock pairs dropped  %s' % dict(dropped))

    spk.sort(key=lambda r: (r['media'], int(r['record']), int(r['entry'])))
    write_csv(os.path.join(OUT, 'media-speaker-context.csv'), SPK_COLS, spk)

    # ---- 3. extra suspects (outside the 98) --------------------------------
    sus = [json.loads(l) for l in io.open(suspects_path, encoding='utf-8') if l.strip()]
    write_csv(os.path.join(OUT, 'media-extra-suspects.csv'), list(sus[0].keys()), sus)

    print('recovery rows       %d' % len(rows))
    print('speaker rows        %d  (misplaced %d + keep %d)' % (len(spk), len(rows), extra))
    print('extra suspects      %d' % len(sus))
    print('action              %s' % dict(collections.Counter(r['action'] for r in rows)))
    print('replacement_conf    %s' % dict(collections.Counter(r['replacement_confidence'] or '-' for r in rows)))
    print('speaker_conf (98)   %s' % dict(collections.Counter(r['speaker_confidence'] for r in rows)))
    print('speaker_conf (all)  %s' % dict(collections.Counter(r['speaker_confidence'] for r in spk)))
    print('position_check      %s' % dict(collections.Counter(r['position_check'] for r in rows)))


if __name__ == '__main__':
    main()
