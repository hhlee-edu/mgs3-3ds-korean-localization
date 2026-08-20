# D2 final: PROFILE clean English, dialogue Korean restored

Date: 2026-08-20. Status: **staged, awaiting hardware test.** No commit, no push,
no CCI. `translation/10_master/` untouched on disk. The alias-range 12-byte code
fix is kept.

## Correction to the previous report

The earlier figure of **137 GCX / 22,760 B / 151 units was wrong**. It measured
demand as the *padded slot size* of each production resource instead of the
actual string length. The corrected model reproduces the builder exactly
(it predicts GCX 44 at 10 B over, which is what `build-korean` reports):

| | wrong (padded) | correct (unpadded) |
|---|---:|---:|
| GCX records short | 137 | **31** |
| bytes short | 22,760 | **290** |
| units that must hold at source | 151 | **40** |

**111 of the 151 dialogue lines are Korean again** in this build, verified
individually.

## Where the 290 bytes were looked for

Every route was checked and is empty:

| route | result |
|---|---|
| free PD-only glyphs (drop `--existing-allocation`) | no change -- the short records carry **0** Hangul glyphs |
| dead glyph slots (`mgs3d_gcx_dead_slot_inventory.py`) | only 8 of 2,326 GCX have a font table at all; **0 dead slots, 0 reusable bytes** |
| `--reuse-existing-dead-font` | no change |
| `--alias-adjacent-strings` | no change |
| `--alias-all-strings` + dedup of every final string in the record | closes **3 of 31** records |
| re-encode PD as clean text instead of dropping it | provably net zero -- the pool it returns equals the demand it adds |
| record-level slack | **zero**. GCX 44's string region is `[0x58, 0x858)` = 2,048 B and the 17 resources fill it exactly; the font region is 4 B |

The only remaining levers are growing the record -- which `wiki/Build-System.md`
forbids for shipping builds because later records move -- or shortening the
Korean. So this build holds 40 lines at their source text, and the shortening
worklist below removes even that.

## The build

Steps 1-2 reused verbatim from v0.96 (`expanded.json`, 227,393 units); glyph
allocation pinned with `--existing-allocation` so no character could be
reassigned to a different token.

```
units       227,393 -> 200,434   (26,919 PERSONAL DATA + 40 held at source)
capacity    2258/2258 GCX ready, total_slot_deficit 0
build       2258 records changed, 0 Hangul glyphs added, gcx size delta 0
output      67,204,976 B (= clean)
            SHA-256 52e6f4176fce68e020c54251df7fc4537d70b589e46dcd43fe37d5d1bc81b2b5
```

## Verification

**PERSONAL DATA, 27,132 resources, clean vs built**

| check | result |
|---|---|
| byte-identical to clean | **27,132 / 27,132** |
| differing | **0** |
| any byte > 0x7F | **0** (ASCII-only) |
| `<0A>` count mismatch | **0** |

**Everything else**

| classification | count |
|---|---:|
| identical to production | 572,316 |
| identical except trailing NUL padding | 2,169 |
| held at source (= clean) | 40 |
| **unintended change** | **0** |
| **unintended fallback to clean** | **0** |

**Dialogue recovered:** all **111** lines that the earlier build had reverted
now carry their production Korean again.

**Structure:** 2,326 records, every record size preserved, every resource count
preserved, file size 67,204,976 = clean.

**Gates:** capacity overflow 0 (2258/2258, deficit 0); missing glyph 0; layout
preserved; expand skips unchanged from v0.96 (2, both allowlisted);
`mgs3d_hpk_chain_check.py` exits 0 with `OK: no padded-slot drift`; RomFS passes
R7 hygiene. DAT residue reports 26,954 non-donor English locations -- the
intended PERSONAL DATA revert plus the 40 held lines, confirmed at resource
level by the tables above. The production gate record in
`docs/evidence/2026-08-19-codec-residual/` was not overwritten.

## Staging

| file | from | to |
|---|---|---|
| `exefs/code.bin` | `4e693f32...` | `2b115156...` (alias-range fix, kept) |
| `romfs/codec.dat` | `72936022...` | `52e6f417...` (D2 final) |

924 files before and after, 0 added, 0 removed, nothing else touched.
Restore: `builds/diag-2026-08-20-pd-clean-restore/production-backup/romfs/codec.dat`.

## Getting the last 40 lines to Korean

`d2-shortening-worklist.csv` in this folder: 40 rows with `gcx`, `resource`,
`record_deficit_bytes` (the record's real target), `clean_bytes`,
`korean_bytes`, `must_save_bytes`, the English source and the current Korean.
31 records, **290 B** of record-level deficit; the 40 listed lines return 367 B
between them, so there is slack in how the saving is distributed within a
record.

Most lines need 1-15 B (1-8 Hangul characters); the outlier is GCX 290 res 3 at
57 B. Per `feedback_mgs3d_translation_shortening_approach`, the byte deficits
are computed here but the text authoring goes to the human translator, not an
AI bulk pass. Once those land, rebuild with the 40 back in and the build has
**zero** reverts.

## Defect #2 (Major Tom / The Boss -> EVA)

Kept separate from this experiment. Our entire change set to `exefs/code.bin` is
8 runs: 6 glyph-token hooks plus the 815-byte cave (DBCS text decode) and one
22-byte patch at `0x0010AEF4`. That last one is now disassembled too:

```
clean :  cmp r0,#0 / beq / mov r0,#0 / bl 0x12bd8c / nop / nop
patched: ldr r0,[r6] / ldr r1,[r0,#8] / orr r1,r1,#1 / str r1,[r0,#8]
         ldr r0,[r0,#0x138] / b 0x10aedc
```

It walks an object list, sets bit 0 of each node's `+8` flags word and follows
`+0x138` to the next -- the Circle Pad Pro enable patch. It writes a flag bit;
it does not touch names or icon indices. Combined with `radio.la2`,
`test_radio.la2`, `slot.dat` and `vox.dat` all being byte-identical to clean,
nothing in our change set plausibly selects a contact icon.

`tools/mgs3d_diag_clean_tree_swap.py` is ready to settle it:

```
python tools/mgs3d_diag_clean_tree_swap.py plan     # done: 177 files, 907 MB
python tools/mgs3d_diag_clean_tree_swap.py apply    # staging -> clean v1.0
   ... repack, boot, select The Boss ...
python tools/mgs3d_diag_clean_tree_swap.py revert   # back to this build
```

`experiments/2026-08-13-clean-glyph-baseline/clean-tree` is a complete 924-file
partition0 tree, the same file set as staging, so the swap is exact; only the
177 differing files are touched and every write is hash-verified.

- **clean also shows EVA** -> stock behaviour, drop #2 from the Korean blockers.
- **clean shows The Boss** -> our regression; the CPP flag-walk at `0x0010AEF4`
  is then the only candidate left in the change set, and the trace goes
  code.bin -> UI icon index -> `slot.dat`.

Run the D2 test first -- staging is set up for it now.
