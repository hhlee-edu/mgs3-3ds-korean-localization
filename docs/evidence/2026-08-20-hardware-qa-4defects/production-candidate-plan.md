# Production candidate: what is adopted, what was only a diagnostic

Date: 2026-08-20. **Plan only. Nothing built, nothing staged, no commit, no push,
no CCI.** The staging tree currently holds a diagnostic configuration and will be
rebuilt from the recipe below when the go-ahead comes.

## Scope decision

PERSONAL DATA is **not** translated. Hardware confirmed PROFILE renders correctly
when those 27,132 resources carry clean English, so the card stays English by
choice rather than being chased further.

## Adopted fixes

| # | change | artifact | evidence |
|---|---|---|---|
| 1 | `codec.dat`: PERSONAL DATA restored to clean English, every other translation kept | `builds/diag-2026-08-20-pd-clean-restore/romfs/codec-final.dat` `52e6f417…` | hardware: with the stage side clean, this codec.dat cures PROFILE; the production one (`72936022…`) reproduces it |
| 2 | stage builder padding policy: keep the clean terminator run, fill slack with `0x20` instead of NUL | `tools/mgs3d_stage_apply.py` (patched) + `builds/diag-2026-08-20-stage-repad` (169 files) | hardware: v001a P1 cured The Boss->EVA and the missing Major Tom name; the same build with NUL padding reproduced both |
| 3 | `r_sna01` resource 479 `'SAVE\0'` never translated | `tools/mgs3d_stage_apply.py` `PERMANENT_EXCLUSIONS` | hardware: restoring that one resource, and nothing else, brings the SAVE label back |
| 4 | `code.bin` alias range `0xA0..0xA3` -> `0xA4..0xA7` (12 bytes) | `builds/diag-2026-08-20-alias-range/exefs/code.bin` `2b115156…` | not a cause of any of the four defects, but a real bug against 33,798 original markup tokens; kept on its own merit |
| 5 | everything else production, unchanged | `builds/diag-2026-08-20-clean-tree-swap/staging-backup` | `exheader.bin`, `movie.dat`, `demo.dat`, both `resident.hpk`, `cache.hpk` |

## Diagnostics -- not adopted, kept only as evidence

`diag-2026-08-20-m1m2-v001a` (M1/M2), `diag-2026-08-20-p1-v001a` (P1), `diag-2026-08-20-variants` (r_sna01 /
v007a_0 M1-M2-P1), `diag-2026-08-20-p2` (P2), `diag-2026-08-20-resource-bisect` (R1-R8),
`diag-2026-08-20-pd-page4`, and the clean-tree swap. None of these belong in a build.
`diag-2026-08-20-pd-clean-restore` is the exception: its `codec-final.dat` **is** adopted.

## How to rebuild the candidate

```
1. reset all 924 files to experiments/2026-08-13-clean-glyph-baseline/clean-tree
2. exefs/code.bin      <- builds/diag-2026-08-20-alias-range/exefs/code.bin        2b115156
   exheader.bin        <- builds/diag-2026-08-20-clean-tree-swap/staging-backup          2bca5dcb
   romfs/movie.dat     <- same backup                                         c48d8cc8
   romfs/demo.dat      <- same backup                                         c44bb512
   r_sna01/resident.hpk, r_sna02/resident.hpk, v000a_0/cache.hpk <- same backup
3. romfs/codec.dat     <- builds/diag-2026-08-20-pd-clean-restore/romfs/codec-final.dat  52e6f417
4. stage/*/scenerio.gcx (169) <- builds/diag-2026-08-20-stage-repad
5. regenerate r_sna01/scenerio.gcx with PERMANENT_EXCLUSIONS applied so that
   resource 479 is clean ASCII, then repad it with the same policy
```

Step 5 is the only piece not yet built. The staged R7 file proved the content is
right, but it was produced by restoring one resource by hand and it carries no
appended glyph page. The shipping file needs the exclusion applied in the builder
and the append kept.

## Verification before the candidate is called good

- 924 files, 0 added, 0 removed; exactly 177 differ from clean
- `codec.dat`: 27,132 PERSONAL DATA resources byte-identical to clean and
  ASCII-only; every other resource identical to v0.96 production
- 169 `scenerio.gcx`: trailing-NUL totals back at clean's level (the repad
  verifier already reports 830,544 vs clean 916,412 vs old production 2,475,910,
  max run 9 vs 122)
- `r_sna01` resource 479 == clean `'SAVE\0'`
- `mgs3d_hpk_chain_check.py` on `cache.hpk`: `OK: no padded-slot drift`
- R7 hygiene: no `.bak`/log/json/csv/md inside the RomFS tree

## Open items

**titlearea -- unresolved.** Title screen save-slot area name, culprit
`stage/title/scenerio.gcx`, never analysed. It has not been re-tested since the
repad fix landed, so it may already be fixed; the last full-repad round reported
only SAVE and PROFILE.

**PROFILE has a second independent cause.** The 169 production stage files
reproduce PROFILE on their own, with every non-stage file clean. That was
measured before the repad fix, so it is unknown whether repad also closed it.
The candidate build has never been tested as a whole, so this is the one real
risk in it.

**40 dialogue lines held at source.** Adopting the D2 `codec.dat` means 40
non-PERSONAL-DATA units across 31 GCX records stay English because their record's
byte pool was subsidised by the Korean PERSONAL DATA that is now gone.
`d2-shortening-worklist.csv` in this folder lists them with the exact per-line
deficit (31 records, 290 B). Recovering them is translator work, not a build fix.

## First test of the candidate

Build it, repack once, and check all six in one pass: The Boss, Major Tom, the
SAVE label, the title save-slot area name, PROFILE 04/04, and ordinary codec
Korean. That single run either closes the whole set or leaves exactly the two
open items above to chase.
