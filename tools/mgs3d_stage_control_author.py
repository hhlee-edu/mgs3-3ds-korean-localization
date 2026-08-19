# -*- coding: utf-8 -*-
"""Round-trip-safe authoring for stage rows that carry control tokens.

READ-ONLY. Writes nothing except its own report.

Why this exists
---------------
The scan's `english` column is a *display* rendering: the button-icon control
bytes are flattened into literal ASCII like `# {   3 0 } #`. Feeding that back
through parse_rendered() produces plain ASCII, not the original control bytes,
so it does NOT round-trip. Measured 2026-08-19: 0 of 142 TUTORIAL_CONTROL rows
re-encode from the `english` column.

Authoring therefore has to start from the resource's real bytes. This module
decomposes them into

    ('C', bytes)  control token   (1F xx, A0 7B, C0 7D)
    ('G', bytes)  2-byte glyph    (existing high-byte text)
    ('T', str)    plain ASCII run

and re-emits them as a parse_rendered() source string where every non-ASCII
byte is an explicit <hh> escape. Only 'T' runs are translatable; the control
and glyph bytes are reproduced verbatim, so the final gate's token-stream check
cannot be broken by an authoring mistake.
"""
import csv
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from mgs3d_codec_tool import parse_rendered  # noqa: E402

ANALYSIS = os.path.join(ROOT, 'docs/evidence/2026-08-19-stage-pretranslation-analysis')
WORK = os.path.join(ANALYSIS, 'stage-translation-working.csv')
CHARMAP = os.path.join(ROOT, 'translation/40_build_input/global_page_v2/character-map.json')

CONTROL_PAIRS = (b'\xa0{', b'\xc0}')


def decompose(raw):
    """raw resource bytes -> segment list. The trailing NUL is kept separate."""
    segs, buf, i = [], bytearray(), 0
    while i < len(raw):
        b = raw[i]
        if b == 0:
            break
        if b == 0x1F and i + 1 < len(raw):
            if buf:
                segs.append(('T', bytes(buf).decode('latin1'))); buf = bytearray()
            segs.append(('C', raw[i:i + 2])); i += 2; continue
        if raw[i:i + 2] in CONTROL_PAIRS:
            if buf:
                segs.append(('T', bytes(buf).decode('latin1'))); buf = bytearray()
            segs.append(('C', raw[i:i + 2])); i += 2; continue
        if b >= 0x80 and i + 1 < len(raw):
            if buf:
                segs.append(('T', bytes(buf).decode('latin1'))); buf = bytearray()
            segs.append(('G', raw[i:i + 2])); i += 2; continue
        buf.append(b); i += 1
    if buf:
        segs.append(('T', bytes(buf).decode('latin1')))
    return segs, raw[i:]          # tail = terminator and anything after it


def esc_bytes(b):
    return ''.join('<%02X>' % x for x in b)


def esc_text(s):
    """ASCII run -> parse_rendered source. '<' and '>' must be escaped."""
    out = []
    for ch in s:
        if ch in '<>':
            out.append('<%02X>' % ord(ch))
        elif 0x20 <= ord(ch) <= 0x7E:
            out.append(ch)
        else:
            out.append('<%02X>' % ord(ch))
        # Hangul is passed through untouched; the character map encodes it.
    return ''.join(out)


def compose(segs, tail, glossary=None):
    """Segments -> parse_rendered source string, applying the run glossary."""
    glossary = glossary or {}
    out = []
    for kind, val in segs:
        if kind in ('C', 'G'):
            out.append(esc_bytes(val))
        else:
            ko = glossary.get(val)
            out.append(esc_text(val) if ko is None else ko)
    return ''.join(out) + esc_bytes(tail)


def main():
    csv.field_size_limit(10 ** 9)
    cmap = {k: bytes.fromhex(v) for k, v in
            json.load(io.open(CHARMAP, encoding='utf-8-sig'))['characters'].items()}
    rows = list(csv.DictReader(io.open(WORK, encoding='utf-8-sig', newline='')))
    target = [r for r in rows if r['category'] == 'TUTORIAL_CONTROL']

    ident_ok = ident_bad = 0
    runs = {}
    for r in target:
        raw = bytes.fromhex(r['raw_hex'])
        segs, tail = decompose(raw)
        src = compose(segs, tail)
        try:
            enc = parse_rendered(src, cmap)
        except Exception as exc:
            ident_bad += 1
            print('  ENCODE FAIL %s: %s' % (r['id'], exc))
            continue
        if enc == raw:
            ident_ok += 1
        else:
            ident_bad += 1
            if ident_bad <= 3:
                print('  IDENTITY DIFF id=%s' % r['id'])
                print('    raw %r' % raw[:48])
                print('    enc %r' % enc[:48])
        for kind, val in segs:
            if kind == 'T' and any(c.isalpha() for c in val):
                runs[val] = runs.get(val, 0) + 1

    print('identity round-trip: %d / %d  (fail %d)' % (ident_ok, len(target), ident_bad))
    print('distinct translatable runs: %d' % len(runs))
    dest = os.path.join(ANALYSIS, 'stage-control-runs.csv')
    with io.open(dest, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh, lineterminator='\r\n')
        w.writerow(['english_run', 'occurrences', 'ascii_bytes', 'korean'])
        for s, n in sorted(runs.items(), key=lambda kv: -kv[1]):
            w.writerow([s, n, len(s), ''])
    print('run sheet -> %s' % os.path.relpath(dest, ROOT))
    return 0 if ident_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
