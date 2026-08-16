import re
from pathlib import Path

EXPECT = bytes.fromhex('0ffffff000000000006ff90002900680')
lines = Path('logs/anchor-run2-2026-08-16.log').read_text(encoding='utf-8', errors='replace').splitlines()

# Only gdb console-output records, in order. Association is positional: a dump
# belongs to the most recent base_X= that preceded it. Keying by address is wrong
# because the same address holds different data at different times.
events = []
for line in lines:
    if not line.startswith('~"'):
        continue
    s = line[2:]
    if s.endswith('"'):
        s = s[:-1]
    events.append(s)

samples = []
cur = None
key = None
for s in events:
    if 'SAMPLE_BEGIN' in s:
        cur = {'ptr': None, 'base': {}, 'by': {}}
        samples.append(cur)
        key = None
        continue
    if cur is None:
        continue
    m = re.search(r'obj=0x([0-9a-f]+) t2=0x([0-9a-f]+) par=0x([0-9a-f]+)', s)
    if m:
        cur['ptr'] = (m.group(1), m.group(2), m.group(3))
        continue
    m = re.search(r'base_(new|old|par)=0x([0-9a-f]+)', s)
    if m:
        key = m.group(1)
        cur['base'][key] = int(m.group(2), 16)
        continue
    m = re.match(r'^(0x[0-9a-fA-F]+):(.*)$', s)
    if m and key:
        vals = [int(v, 16) for v in re.findall(r'0x([0-9a-fA-F]{2})(?![0-9a-fA-F])', m.group(2))]
        if vals:
            cur['by'].setdefault(key, []).extend(vals)


def verdict(sample, k):
    b = bytes(sample['by'].get(k, [])[:16])
    if not b:
        return '-', None
    if b == EXPECT:
        return 'OK', b
    if set(b) == {0}:
        return 'ZEROS', b
    return 'WRONG', b


print('%-3s %-9s %-9s %-9s | %-6s %-6s %-6s | %-9s %-9s %-9s'
      % ('#', 'obj', 't2', 'par', 'new', 'old', 'par', 'b_new', 'b_old', 'b_par'))
print('-' * 92)
n = 0
for s in samples:
    if not s['ptr']:
        continue
    n += 1
    o, t, p = s['ptr']
    v = {k: verdict(s, k)[0] for k in ('new', 'old', 'par')}
    b = s['base']
    print('%-3d %-9s %-9s %-9s | %-6s %-6s %-6s | %-9s %-9s %-9s'
          % (n, o, t, p, v['new'], v['old'], v['par'],
             '%08x' % b['new'] if 'new' in b else '?',
             '%08x' % b['old'] if 'old' in b else '?',
             '%08x' % b['par'] if 'par' in b else '?'))

tot = {}
for k in ('new', 'old', 'par'):
    c = {}
    for s in samples:
        if not s['ptr']:
            continue
        c[verdict(s, k)[0]] = c.get(verdict(s, k)[0], 0) + 1
    tot[k] = c
print()
print('verdict totals:', tot)

for s in samples:
    if not s['ptr']:
        continue
    vn, bn = verdict(s, 'new')
    if vn in ('WRONG', 'ZEROS'):
        vo, bo = verdict(s, 'old')
        vp, bp = verdict(s, 'par')
        print()
        print('=== first sample where the CURRENT anchor fails ===')
        print('  obj=0x%s t2=0x%s par=0x%s' % s['ptr'])
        for k, vv, bb in (('new', vn, bn), ('old', vo, bo), ('par', vp, bp)):
            print('  base_%-4s= 0x%08x -> %s  %s'
                  % (k, s['base'].get(k, 0), bb.hex(' ') if bb else '-', vv))
        print('  expected                %s' % EXPECT.hex(' '))
        break
