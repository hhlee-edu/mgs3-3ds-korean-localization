# M1 / M2: splitting translated text from the appended glyph page

Date: 2026-08-20. Status: **M2 tested and cleared. M1 staged, awaiting CCI.**
Nothing adopted into production, master untouched, no commit/push/CCI.

## Why the per-file culprit hypothesis is on hold

`stage/r_sna01/scenerio.gcx` and `stage/r_sna02/scenerio.gcx` are **byte-identical**
in clean (`b7aaf10dc6e0aef5`) and in production (`c325c95d8c9c1914`). Round
"optimized 16" applied `r_sna02` and SAVE was **ok**; round "optimized 9" applied
`r_sna01` and SAVE was **ng**. Identical files cannot behave differently, so the
bisection separated **which stage is resident**, not which file is defective.
The save confirms it: `room r_sna01`, `stage v001a`.

## Are M1/M2 valid with clean code.bin? Yes

Every round in which any regression reproduced ran with `exefs/code.bin`,
`exheader.bin`, `resident.hpk` x2, `cache.hpk`, `codec.dat`, `movie.dat` and
`demo.dat` all **clean** -- only production `scenerio.gcx` was applied. So the
regressions happen with **no glyph hook present**: the appended Korean page is
never decoded. M2's discriminating power therefore comes from the file being
larger (the documented "load size = RomFS file size" path), not from the page
being read.

## The two variants

| variant | size | SHA-256 |
|---|---:|---|
| clean v1.0 | 489,441 | `da6945edb6e22d920b761da16263b41c7e1d435e4e884913bce7718f158c4d60` |
| production | 772,068 | `87c088c6d4705c7e0211e189a12de2462191d2b9ad510e09afc98e4e028a39ff` |
| **M1** translation only | **489,441** | `3646289b8725633a92cd307f4b657577f896145da4990f9bfc161ade619fc6e1` |
| **M2** append only | **772,068** | `ffe35821661e35c1d53cec7052be970daa1844f927114f55772fd4ff4b3d1439` |

M1 = production's original region with the append stripped (size exactly clean's).
M2 = clean's original region byte-for-byte plus production's append at the same
offset (zero translated bytes). They are exact complements: together they hold
every production byte and share none. M1 parses as a well-formed GCX
(1 record, 7,202 resources); M2 fails the record walk at `0x777f0`, which is
clean's EOF -- identical to production, i.e. purely the append.

Append geometry for v001a: clean EOF `0x777E1`, first non-zero appended byte
`0xAC8E9`. The cave's `+0x56000` constant matches **0 of 169** stages, and 90 of
169 have clean content already past it -- and with clean `code.bin` that code
does not exist at all.

## M2 result: cleared

Hardware, clean v1.0 + M2 on `v001a` only: **Boss, Major Tom and SAVE all
normal.** So neither the 282,627-byte size increase nor the appended glyph page
causes these regressions. **The appended page and file growth are exonerated.**

## M1 staged now

924 files, 0 added, 0 removed, exactly one differing from clean v1.0:

```
romfs/stage/v001a/scenerio.gcx   clean 489,441 -> staged 489,441 (delta 0)   3646289b8725633a
```

`code.bin`, `exheader.bin`, `codec.dat`, `movie.dat`, `demo.dat`, both
`resident.hpk`, `cache.hpk`, `r_sna01/scenerio.gcx` and `title/scenerio.gcx` all
verified CLEAN. `cache.hpk` chain: `OK: no padded-slot drift`.

Check on hardware, with the save in `v001a`: **Boss -> EVA**, **Major Tom name**,
**SAVE label**. The Korean text itself will render as garbage (clean
`resident.hpk`, no glyph hook) -- that is expected and is not what is being
judged.

## Pre-analysis for the follow-up, if M1 reproduces

Measured on the 992 resources the translation pass changed in `v001a`:

| | |
|---|---|
| identical byte length | **992 / 992** |
| resource count, record size, every `table_word` | unchanged |
| clean text class | 875 prose, **117 ALL-CAPS short labels** |
| `<0A>` count changed | 95 resources |

The short UI labels **were** translated, and because Korean is shorter the
builder pads each resource back to its original length with NUL bytes:

```
[213]  clean  'KNIFE<00>'                        6 B
       M1     '<85><07><00><00><00><00>'         6 B   <- 3 extra terminators
[215]  clean  'CIG SPRAY<00>'                   10 B
       M1     '<81><06><81>Q<81>#<81><06><00><00>'    10 B
```

Across the whole record:

| | clean | M1 | delta |
|---|---:|---:|---:|
| `<00>` bytes | 9,424 | **26,693** | **+17,269** |
| `<0A>` bytes | 11,321 | 11,389 | +68 |

913 of the 992 changed resources gained extra `<00>`, up to +121 in one
resource. `<00>` is the string terminator. Any consumer that walks this block
**sequentially by terminator** rather than through the offset table would read
17,269 additional empty strings and land N slots off -- which is the shape of
"The Boss shows EVA", "Major Tom has no name", "SAVE has no label".

This is a hypothesis, not a finding: it stands or falls on the M1 result. If M1
comes back clean, the padding is exonerated with everything else and the cause is
elsewhere in the original region.

## Tooling

```
python tools/mgs3d_diag_m1m2_swap.py build
python tools/mgs3d_diag_m1m2_swap.py apply m1|m2|clean|production
python tools/mgs3d_diag_m1m2_swap.py status
```
