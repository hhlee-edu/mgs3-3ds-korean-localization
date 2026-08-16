"""Fit a Korean translation into a resource's original control-code/icon schema.

3DS control-tutorial resources embed button icons as two-byte tokens
(``80 23  A0 7B  A3 1E  80 <digit>  C0 7D  80 23`` renders as ``( # { n } #)``).
A replacement string has to reproduce those bytes *and* interleave its ``<0A>``
line breaks the same way the English does, or the control-code gate rejects it.

Rather than hand-placing line breaks, read the English token stream as a schema --
TEXT / ``<0A>`` / ICON / ``<00>`` in order -- and pour the Korean text into it. The
icons are copied from the source in order, so their bytes and digits are preserved by
construction and the emitted token list equals the original's.

Usage as a library::

    from mgs3d_codec_icon_schema_fit import pour
    korean, err = pour('Aim 버튼({})을 눌러라.', render_bytes(source_resource))

The template marks each icon position with ``{}``; it must contain exactly as many
``{}`` as the source has icons, and mention the buttons in the same order.
"""
import re

ICON_RE = re.compile(r'<80>#<A0>\{<A3><1E><80>(\d)<C0>\}<80>#')
TOKEN_RE = re.compile(r'<80>#<A0>\{<A3><1E><80>\d<C0>\}<80>#|<0A>|<00>')


def schema(raw):
    """render_bytes() output -> ordered list of ('ICON',digit) / ('NL',) / ('END',)."""
    out = []
    for m in TOKEN_RE.finditer(raw):
        s = m.group(0)
        if s == '<0A>':
            out.append(('NL',))
        elif s == '<00>':
            out.append(('END',))
        else:
            out.append(('ICON', ICON_RE.match(s).group(1)))
    return out


def split_words(text, n):
    """Split text into n chunks at word boundaries, as evenly as possible."""
    if n <= 1:
        return [text]
    words = text.split(' ')
    if len(words) < n:
        return [text] + [''] * (n - 1)
    target = len(text) / n
    chunks, cur = [], ''
    for w in words:
        if cur and len(chunks) < n - 1 and len(cur) + 1 + len(w) > target:
            chunks.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    chunks.append(cur)
    while len(chunks) < n:
        chunks.append('')
    return chunks[:n]


def pour(template, raw):
    """-> (korean_with_tokens, '') or (None, reason)."""
    sch = schema(raw)
    parts = template.replace('<0A>', ' ').split('{}')
    icons = [d for t, *d in sch if t == 'ICON']
    if len(parts) - 1 != len(icons):
        return None, 'placeholder count %d != source icons %d' % (len(parts) - 1, len(icons))
    out, pi = [], 0
    pending = parts[0]
    for step in sch:
        if step[0] == 'ICON':
            out.append(pending.strip())
            out.append('<80>#<A0>{<A3><1E><80>%s<C0>}<80>#' % step[1])
            pi += 1
            pending = parts[pi]
        elif step[0] == 'NL':
            a, b = split_words(pending.strip(), 2) if pending.strip() else ('', '')
            out.append(a)
            out.append('<0A>')
            pending = b
        else:
            out.append(pending.strip())
            out.append('<00>')
            pending = ''
    return ''.join(out), ''
