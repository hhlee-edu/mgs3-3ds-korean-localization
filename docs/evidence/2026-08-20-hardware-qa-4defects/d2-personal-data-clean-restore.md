# D2 diagnostic: PERSONAL DATA restored to clean English

Date: 2026-08-20. Status: **staged, awaiting hardware test.** No commit, no push,
no CCI. `translation/10_master/` is untouched on disk.

## Baselines used

`reference/clean/codec.dat` does not exist in this repo. `wiki/Build-System.md`
names the authority explicitly, and that is what was used:

```
experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat
67,204,976 B   SHA-256 dd6ea4b80f194951bcbb0f584abb6b5f96d043e8c3ab78c4ec0c4236982374ea
```

`master` (the git branch) is **12 commits behind** `release/v0.83`, so the
current branch is the latest mainline and the build was taken from it. Its
production `codec.dat` is `builds/diag-2026-08-20-codec-textidentity/romfs/codec.dat`,
`72936022...`, byte-identical to what was staged.

## What was built

Pipeline is the wiki's 4-step order. Step 1-2 were reused verbatim from v0.96
(`expanded.json`, 227,393 units) so no re-expansion could shift anything, and
the glyph allocation was pinned with
`--existing-allocation builds/diag-2026-08-20-codec-textidentity/romfs/codec.dat.hangul.json`
so no Korean character could be reassigned to a different token.

The 27,132 PERSONAL DATA `(gcx, resource)` pairs were identified in **clean**
(resources containing `PERSONAL DATA` or `CODE NAME`), and their 26,919
translation units were dropped from the document. A dropped unit is not
replaced at all, so its resource keeps clean's bytes **by construction** --
this is a restore by omission, not a re-encode.

```
capacity --check   2256/2256 GCX ready, total_slot_deficit 0
build-korean       2256 records changed, 0 Hangul glyphs added, gcx size delta 0
output             67,204,976 B (= clean)  SHA-256
                   c39870c5cc393228913c3de41d5a4e1038a4f2fb6623ae688a06543446a031d7
```

## The one deviation, and why it is unavoidable

Dropping PERSONAL DATA also removes its bytes from the per-GCX replacement
pool. **137 of 2,289 GCX records then no longer fit**, total deficit 22,760 B --
the Korean dialogue in those records only fits because Korean PERSONAL DATA is
8-40 bytes shorter per resource than the English it replaced, and that saving
was being lent to the dialogue. GCX 44 is the clearest case:

```
pool with PERSONAL DATA    2,048 B
pool without               73 B     <- 14 of its 17 resources are PERSONAL DATA
dialogue still needs       83 B     -> 10 B over, build aborts
```

This is the exact failure `wiki/Build-System.md` documents. `--alias-adjacent-
strings` does not close it (those records have no duplicate strings to alias).
Re-encoding PERSONAL DATA to clean text rather than dropping it gives an
identical deficit, because the demand it removes is the same as the pool it
returns.

So the two instructions -- restore all of PERSONAL DATA, and change nothing
else -- cannot both hold. The build reverts the **minimum** set: for each short
record, non-PERSONAL-DATA units were reverted in descending order of bytes
recovered until the deficit closed.

```
non-PERSONAL-DATA units reverted to clean English : 151
spread over                                        : 137 GCX records
share of the 200,474 kept units                    : 0.075 %
```

`translation/10_master/current/codec.csv` was **not edited** -- the reverts
exist only in this build's translation document.

## Verification

**PERSONAL DATA, all 27,132 resources, clean vs built:**

| check | result |
|---|---|
| byte-identical to clean | **27,132 / 27,132** |
| differing | **0** |
| resources containing any byte > 0x7F | **0** (ASCII-only) |
| `<0A>` count mismatch vs clean | **0** |

**Everything else, 574,374 resources, production vs built:**

| classification | count |
|---|---:|
| identical to production | 572,311 |
| identical to production except trailing NUL padding | 2,063 |
| **real content change** | **0** |

The 2,063 are the same string-region repacking artefact the v0.96 build recorded
(118 at the time); content is unchanged.

**The 151 collateral reverts:** all 151 carry clean English -- 48 byte-exact,
103 identical apart from trailing NUL padding.

**Structure:** 2,326 records in clean, production and D2; every record size
preserved; every resource count preserved; file size 67,204,976 = clean.

**DAT residue, read from the binary:**

| | v0.96 production | D2 |
|---|---:|---:|
| locations checked | 233,456 | 233,456 |
| non-donor English | 0 | 27,028 |
| donor fr/es English | 6,181 | 6,223 |
| ASCII-only translations | 311 | 310 |

`27,028 + 42 donor-reclassified - 1 = 27,069`, matching the 27,070 reverted
units. The English residue is **entirely** the intended revert -- independently
proven at resource level by the two tables above.

**Gate status.** Structural gates all pass: capacity overflow 0
(2256/2256, deficit 0), missing glyph 0 (0 appended), layout preserved (2,326
records, 0 size change), expand skips unchanged from v0.96 (2, both
allowlisted). The two content gates -- `DAT read-back matches master` and `DAT
English residue = 0` -- are **intentionally violated by this diagnostic** and by
exactly the reverted set; `docs/evidence/2026-08-19-codec-residual/` was not
overwritten, so the production gate record still stands.

**Pre-repack:** `mgs3d_hpk_chain_check.py` on `stage/v000a_0/cache.hpk` exits 0,
`OK: no padded-slot drift`. RomFS passes R7 hygiene.

## Staging

Two files differ from the pre-diagnostic production tree, and nothing else:

| file | from | to |
|---|---|---|
| `exefs/code.bin` | `4e693f32...` | `2b115156...` (alias-range 12-byte fix, **kept**) |
| `romfs/codec.dat` | `72936022...` | `c39870c5...` (D2) |

924 files before, 924 after, 0 added, 0 removed.

## Restore

```
copy builds/diag-2026-08-20-pd-clean-restore/production-backup/romfs/codec.dat  -> staging
python tools/mgs3d_diag_alias_range_patch.py revert                   (if also reverting the code fix)
```

## Test

- **A.** PROFILE 04/04 PERSONAL DATA -- now clean English. Does it render?
- **B.** ordinary codec Korean -- must still be normal.
- **C.** button/icon markup.

If A renders correctly, the defect is caused by our DBCS insertion into that
screen and nothing else. If A is *still* broken with 100 % clean English bytes,
the cause is outside codec.dat entirely.
