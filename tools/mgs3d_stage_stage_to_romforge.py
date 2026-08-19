# -*- coding: utf-8 -*-
"""Apply the verified stage translation into the RomForge staging tree.

Why this is a splice and not a copy
-----------------------------------
The staged `stage/*/scenerio.gcx` are NOT the clean-tree files. Measured
2026-08-19 over all 169: each staged file is the clean-tree file byte-for-byte
followed by an appended region (66 KB - 417 KB) that carries the resident
Korean glyph page. The page starts exactly 65,275 bytes before EOF in every
file. Copying the build output over the staged file would delete it, and
changing the file's length would move it.

So this writes  verified-record-bytes + the staged file's own appended tail,
and refuses unless

  * the staged file begins with the clean file byte-for-byte,
  * the verified file has exactly the clean file's length,
  * the resulting file has exactly the staged file's length.

The appended tails are copied to a backup directory OUTSIDE the romfs tree
first (R7: nothing extra may live inside the tree, repack bundles the folder).
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / 'experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/stage'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--staging', type=Path, required=True, help='.../partition0/romfs/stage')
    ap.add_argument('--verified', type=Path, required=True, help='build output .../romfs/stage')
    ap.add_argument('--backup', type=Path, required=True, help='tail backup dir, outside romfs')
    ap.add_argument('--apply', action='store_true', help='write; otherwise dry-run')
    a = ap.parse_args()

    names = sorted(d.name for d in CLEAN.iterdir() if (d / 'scenerio.gcx').is_file())
    plan, errors = [], []
    for n in names:
        cb = (CLEAN / n / 'scenerio.gcx').read_bytes()
        sp = a.staging / n / 'scenerio.gcx'
        vp = a.verified / n / 'scenerio.gcx'
        if not sp.is_file():
            errors.append(f'{n}: missing in staging'); continue
        if not vp.is_file():
            errors.append(f'{n}: missing in verified build'); continue
        sb = sp.read_bytes(); vb = vp.read_bytes()
        if sb[:len(cb)] != cb:
            errors.append(f'{n}: staged file does not begin with the clean file'); continue
        if len(vb) != len(cb):
            errors.append(f'{n}: verified length {len(vb)} != clean {len(cb)}'); continue
        tail = sb[len(cb):]
        new = vb + tail
        if len(new) != len(sb):
            errors.append(f'{n}: result length {len(new)} != staged {len(sb)}'); continue
        plan.append((n, sp, tail, new, sb))

    changed = [p for p in plan if p[3] != p[4]]
    print('stage files            : %d' % len(names))
    print('splice plan built      : %d' % len(plan))
    print('files that will change : %d' % len(changed))
    print('errors                 : %d' % len(errors))
    for e in errors[:10]:
        print('   ' + e)
    if errors:
        return 1
    if not a.apply:
        print('dry-run: nothing written')
        return 0

    a.backup.mkdir(parents=True, exist_ok=True)
    for n, sp, tail, new, old in plan:
        (a.backup / ('%s.tail' % n)).write_bytes(tail)
    print('appended tails backed up to %s' % a.backup)

    for n, sp, tail, new, old in plan:
        sp.write_bytes(new)

    # verify what actually landed on disk
    bad = 0
    for n, sp, tail, new, old in plan:
        got = sp.read_bytes()
        if got != new or got[len(got) - len(tail):] != tail:
            bad += 1
            print('   VERIFY FAIL %s' % n)
    print('written and re-read    : %d files, mismatches %d' % (len(plan), bad))
    print('total staged bytes     : %d' % sum(len(p[3]) for p in plan))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
