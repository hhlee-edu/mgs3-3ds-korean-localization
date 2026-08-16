"""Data-driven language ID for codec strings.

Hand-written stopword lists kept leaking short donor lines ("Ouais.", "Exacto.")
into the English work queue, and a per-GCX ratio cannot help because every GCX
carries all five language branches at once -- gcx 15, which holds the English first
radio line, is 74% donor by resource count just like a French-heavy record.

So the lexicons are built from the corpus itself:

  donor vocabulary  <- every string that carries an <1F..> accent escape, which only
                       the French/Spanish/German/Italian branches use, plus every
                       master row already marked is_donor=yes.
  english vocabulary<- every master row marked is_donor=no that has an English side.

A token that occurs in one lexicon and not the other is evidence. Tokens common to
both (names, "Snake", "OK") are ignored. That makes the decision rest on words that
actually separate the languages, which is what the hand lists failed to do.
"""
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, 'tools')
from mgs3d_codec_tool import parse_codec
from mgs3d_english_korean_match import decode_western
from mgs3d_codec_status_catalog import strict_western, direct_language

csv.field_size_limit(10 ** 9)
ACC = re.compile(rb'\x1f[\x20-\x7f]')
WORD = re.compile(r"[A-Za-z][A-Za-z']*")
REF = Path('experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat')


def tokens(s):
    return [w.lower() for w in WORD.findall(s or '') if len(w) > 1]


def build(reference=REF):
    donor, eng = Counter(), Counter()
    recs = parse_codec(reference.read_bytes())
    for rec in recs:
        try:
            rs = rec.resources()
        except Exception:
            continue
        for x in rs:
            t = decode_western(x.data)
            if not t or not strict_western(x.data):
                continue
            if ACC.search(x.data) or direct_language(x.data) in ('fr', 'es'):
                donor.update(tokens(t))
    # The codec master's `english` column cannot seed the English lexicon: donor
    # contamination puts French/Spanish text in it (42 rows were already proven
    # mislabelled), which is exactly how "Ouais." came out neutral. movie.csv and
    # demo.csv are cutscene subtitles with no donor branches at all, so they are
    # clean English. Accepted, non-donor codec rows are added on top for the
    # codec-specific vocabulary.
    for name in ('movie', 'demo'):
        for r in csv.DictReader(io.open('translation/10_master/current/%s.csv' % name,
                                        encoding='utf-8-sig', newline='')):
            eng.update(tokens(r.get('preview') or ''))
    # Accepted codec rows are still contaminated -- "ouais"/"exactement" sit in
    # their english column -- so they are used only to ADD donor vocabulary, never
    # to defend a token as English. Only movie/demo previews defend a token.
    for r in csv.DictReader(io.open('translation/10_master/current/codec.csv',
                                    encoding='utf-8-sig', newline='')):
        if (r.get('is_donor') or '') == 'yes':
            donor.update(tokens(r.get('english') or ''))
    # interjections are language-neutral and must never count as donor evidence
    NEUTRAL = {'mmm', 'mm', 'ah', 'aah', 'oh', 'ooh', 'uh', 'huh', 'hm', 'hmm', 'ha',
               'eh', 'er', 'um', 'hey', 'ok', 'okay'}
    # proper nouns are spelled the same in every branch, so they are never evidence
    NAMES = {'snake', 'sigint', 'eva', 'ocelot', 'sokolov', 'volgin', 'granin', 'raikov',
             'adam', 'zero', 'tom', 'boss', 'groznyj', 'grad', 'shagohod', 'para', 'medic',
             'paramedic', 'krasnogorje', 'tatyana', 'khrushchev', 'johnny', 'fox', 'kgb',
             'gru', 'cia', 'dci', 'philosophers', 'sorrow', 'fear', 'pain', 'end', 'fury',
             'aleksandrovna', 'nikolaevich', 'yevgeny', 'borisovitch', 'jack', 'john',
             'doe', 'major', 'colonel', 'usa', 'ussr', 'uk', 'esp', 'mission', 'start',
             'survival', 'food', 'radio', 'codec', 'c3', 'adamska', 'voyevoda', 'raiden'}
    donor_only = {w for w, n in donor.items() if n >= 3 and eng[w] == 0} - NEUTRAL - NAMES
    eng_only = {w for w, n in eng.items() if n >= 2 and donor[w] == 0}
    return donor_only, eng_only


def classify(text, donor_only, eng_only):
    """-> ('donor'|'english'|'neutral', donor_hits, english_hits)"""
    tk = tokens(text)
    d = sum(1 for w in tk if w in donor_only)
    e = sum(1 for w in tk if w in eng_only)
    if d and not e:
        return 'donor', d, e
    if e and not d:
        return 'english', d, e
    if d or e:
        return ('donor' if d > e else 'english' if e > d else 'neutral'), d, e
    return 'neutral', d, e


if __name__ == '__main__':
    do, eo = build()
    print('donor-only tokens   : %d' % len(do))
    print('english-only tokens : %d' % len(eo))
    print()
    probes = ['Ouais.', 'Exactement.', 'Exacto.', 'Entiendo...', 'Tant mieux.', 'Hein ?',
              'Por supuesto.', 'Vraiment ?', 'Pareces contento.', 'Laisse-moi t\'expliquer.',
              'Snake, algunos soldados enemigos tienen radios.',
              'Good.', 'Nothing.', 'Exactly.', 'Yep.', 'Okay.', 'Precisely.', 'Mmm.', 'Ah...',
              "Do you copy? You're already in enemy territory, and somebody might be listening in.",
              'Snake, are you all right!?', 'I\'ve been better.', 'Sigint.']
    for p in probes:
        v, d, e = classify(p, do, eo)
        print('  %-10s d=%d e=%d  %s' % (v, d, e, p[:62]))
