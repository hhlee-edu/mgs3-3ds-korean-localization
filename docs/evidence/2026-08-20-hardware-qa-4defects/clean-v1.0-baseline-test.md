# Clean v1.0 baseline test for defect #2

Date: 2026-08-20. Status: **staged, awaiting CCI + hardware test.** No commit,
no push. The D2 build is preserved and fully restorable.

## Why this test

Defect #2 -- Major Tom's name not shown, The Boss showing EVA -- has no
plausible cause inside our change set:

- The bottom radio contact UI is `romfs/ui/menu/sv/radio.la2`, which contains
  **no contact name text at all**. The names are pre-rendered images:
  `rad_icn_zero`, `rad_icn_medic`, `rad_icn_sigint`, `rad_icn_theboss`,
  `rad_icn_eva`, `rad_icn_save` (plus `rad_icn_damylarge/damynomal`, "damy" =
  dummy). There is no `rad_icn_majortom` in the set.
- `radio.la2`, `ui/test/test_radio.la2`, `slot.dat` and `vox.dat` are all
  **byte-identical to clean**.
- Our whole `exefs/code.bin` delta is 8 runs: six glyph-token hooks plus the
  815-byte cave (DBCS text decode -- the contact icons are images, not text),
  and one 22-byte patch at `0x0010AEF4` that walks an object list setting bit 0
  of each node's `+8` word and following `+0x138` (the Circle Pad Pro enable
  patch). It writes a flag bit; it selects nothing.

So booting the unpatched game settles it in one test, which is far cheaper than
tracing an icon index we have no evidence of touching.

## What is staged

`tools/mgs3d_diag_clean_tree_swap.py apply` replaced the 177 files that differed
between staging and
`experiments/2026-08-13-clean-glyph-baseline/clean-tree` (169 `scenerio.gcx`,
`codec.dat`, `movie.dat`, `demo.dat`, both `resident.hpk`, `cache.hpk`,
`exefs/code.bin`, `exheader.bin`), 907 MB, every write hash-verified.

Full-tree check afterwards:

```
clean files 924   staging files 924   file sets equal: True
files differing from clean v1.0: 0
```

**Staging is byte-identical to clean v1.0 across all 924 files.** That means
this build has no Korean text, no glyph hooks and no CPP patch -- it is the
stock game.

## Before repacking

`C:\Users\hhlee\Desktop\Romforge\output\` currently holds:

| file | what it is |
|---|---|
| `MGS SNAKE EATER 3D_Repack.cci` | **the D2 build**, SHA-256 `89b837d79f59655e7e5f373aecc91ab946287c6ef2d0b2173c63bdbfadba2372` |
| `MGS SNAKE EATER 3D_0_91.cci` | v0.91 |

RomForge writes into that same folder, so **rename the D2 image first** (for
example `mgs3d-d2-personal-data-clean.cci`) or the next repack can take its
name. The D2 image is still needed -- its hardware test has not been run.

## Test -- four items only

- **PROFILE** -- open Major Zero's PROFILE 04/04 and read the PERSONAL DATA
  block. This is the stock English card, so it establishes what "correct" looks
  like and whether the 200 px layout ever breaks on its own.
- **Major Tom** -- is the name shown in the codec contact UI?
- **The Boss** -- does selecting The Boss show EVA?
- **SAVE** -- does the SAVE entry show correctly? It is the sixth entry in the
  same list, so it tells us whether any index shift exists at all.

Reading:

| result | conclusion |
|---|---|
| clean also shows EVA / no Major Tom | stock behaviour -- **drop #2 from the Korean blockers** |
| clean shows The Boss and Major Tom correctly | our regression. The only candidate left in the change set is the CPP flag-walk at `0x0010AEF4`; trace code.bin -> UI icon index -> `slot.dat` |
| SAVE also wrong in clean | the whole list is index-shifted in the stock game -- a save-state or progression condition, not a build defect |

## Restore

```
python tools/mgs3d_diag_clean_tree_swap.py revert
python tools/mgs3d_diag_clean_tree_swap.py status    # expect: 177 files differing again
```

Backup verified complete at **177/177 files, 961 MB**, in
`builds/diag-2026-08-20-clean-tree-swap/staging-backup/`. Revert returns staging to the
D2-final build (`codec.dat 52e6f417...`, `code.bin 2b115156...` with the
alias-range fix).
