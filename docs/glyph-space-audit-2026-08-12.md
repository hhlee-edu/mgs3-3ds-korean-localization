# MGS3D glyph/space audit (2026-08-12)

## Scope and safety

`tools/mgs3d_glyph_space_audit.py` is read-only with respect to game files. It
parses DAT/GCX/HPK-derived allocation metadata and writes only CSV/JSON reports.
It does not translate, abbreviate, render, patch, relocate, or overwrite any
movie/demo/codec record. GCX 53 is reported as pinned and is never rebuilt.

The current report deliberately uses the pristine English movie/demo/codec as
the **before** image. This avoids treating Korean already present in the live
staging files as original capacity. A separate `live_local_slots.csv` scans the
live files solely to inventory their current local-font slots and dead slots.

## Confirmed font systems

1. **Resident/static/common font**
   - Live files:
     `stage/r_sna01/resident.hpk` and `stage/r_sna02/resident.hpk`.
   - Both live SHA-256 values exactly match their archived allocation reports.
   - Both reports contain the same 191-character map.
   - Tokens occupy the renderer-confirmed `0x81`, `0x82`, and `0x83` pages;
     `0x8301` is excluded because the engine clears it at runtime.
   - `common_glyphs.csv` is therefore an actual slot map, not a frequency list.
     A mapped character has zero additional local-font cost.

2. **movie/demo local font**
   - Per-record page `0x90`, maximum 1,020 slots.
   - Each slot is 64 bytes (16x16, 2bpp).
   - Owners are obtained by parsing every subtitle's page-3 tokens.
   - A slot is reclaimable only when no still-live subtitle in that record owns
     it. Slots cannot be moved between records.

3. **codec local font**
   - Per-GCX page `0x8C`, maximum 1,020 slots.
   - Each slot is 64 bytes (16x16, 2bpp).
   - `glyph_slot_owners()` parses each resource to its null terminator and
     handles the `0x1F <suffix>` escape before interpreting two-byte tokens.
   - `dead_font_slots()` is the canonical zero-live-owner test. Reuse changes
     the resource token to `custom_token(slot)` and overwrites exactly that
     slot through `overwrite_font_slots()`; cross-GCX reuse is forbidden.

## Live slot inventory

| medium | scopes | scopes with font | slots | dead | reusable bytes |
|---|---:|---:|---:|---:|---:|
| movie | 108 records | 13 | 476 | 0 | 0 |
| demo | 333 records | 81 | 980 | 0 | 0 |
| codec | 2,326 GCX | 652 | 14,370 | 1,545 | 98,880 |

The codec result reproduces the independently audited 2026-08-09 inventory.
The largest proven pools are GCX 767 (84 dead), 779 (73), 1740 (27), 1729
(26), and 243 (19). These are local to their own GCX and are not a global bank.

GCX 53 currently has 24 local slots: 19 referenced and 5 dead (indices
5,6,7,8,14; 320 bytes). This does **not** authorize moving or growing GCX 53;
only in-place token/slot reuse is a structurally compatible future option.

## Cost model

For every translation scope:

- `common_glyphs` = Hangul present in the verified resident map.
- `new_glyphs` = Hangul not present in the resident/base character map.
- `glyph_add_bytes` = `new_glyph_count * 64` before local-slot reuse.
- `existing_dead_slots` = zero-owner slots already present before the batch.
- `newly_freed_slots` = slots whose complete owner set is replaced.
- `glyph_reclaim_bytes` = proven reusable local slots times 64.
- `donor_reclaim_bytes` is zero in this analysis because no explicit byte donor
  transfer is performed. Blank Western movie/demo strings are not transferable
  headroom in fixed-layout mode: their offsets and capacities remain unchanged.
- `string_reclaim_bytes` reports encoded shrinkage only; it is not silently
  transferred between fixed-offset rows.
- `string_delta_bytes` is calculated from the real encoder output, including
  terminators/control tokens, not Python character length.
- movie `overflow_bytes` means record growth required when its original record
  footprint is held fixed.
- demo shortage is decided only at scene level: total record growth versus the
  zero-padding run immediately before the next confirmed scene marker.
- codec headroom uses the builder's per-GCX preserve-size equation: original
  string region minus appended font bytes minus final encoded resource bytes.

Important implementation boundary: resident tokens are renderer-valid and the
growing movie/demo builder already accepts a static allocation. The safer
`rebuild_record_fixed_reclaim()` entry point does not yet accept a static map.
This audit calculates the requested fixed-offset + resident-reuse policy, but
that combination still needs a separately reviewed builder-plumbing change
before it can be called an executable patch path. No such change is made here.

## Current-data result

Inputs are the v6.4.5 movie/demo apply CSVs, the 2026-08-08 selected codec
translation JSON, and pristine English DAT files.

- Movie: 108 records reported; 13 contain 47 translation rows. All 13 require
  record growth under a no-growth record policy. Across touched records the
  resident map avoids 326 record-local character allocations; 150 local
  allocations remain (counts are per-record, as required by the format).
  Three records also contain at least one encoded subtitle that exceeds its
  own immutable text capacity; glyph space cannot fix those rows.
- Demo: 333 records and 130 scenes reported; 83 records contain 201 translation
  rows. Nine records contain at least one immutable subtitle-capacity overflow.
  Independently, seven scenes exceed their own confirmed padding budget:

  | scene | budget | growth | shortage |
  |---:|---:|---:|---:|
  | 36 | 117 | 896 | 779 |
  | 113 | 198 | 640 | 442 |
  | 13 | 150 | 512 | 362 |
  | 49 | 5 | 192 | 187 |
  | 10 | 534 | 640 | 106 |
  | 61 | 86 | 192 | 106 |
  | 76 | 710 | 768 | 58 |

- Codec: all 2,326 GCX are reported; 552 contain selected translation units.
  Per-GCX preserve-size analysis reports 376 shortages. The largest are GCX
  261 (2,268 bytes), 270 (2,130), 444 (1,619), 355 (1,095), and 652 (1,047).
  GCX 53 has no unit in this translation input and is reported unchanged.

`overflow_glyphs.csv` lists each 64-byte local glyph contributing to an
overflow, its line count, row IDs, English source, and Korean text. The tool
does not invent English substitutions. `english_substitution=not_generated`;
`saving_if_removed_from_scope=64` is only a mechanical upper bound if the user
later supplies an approved wording that eliminates that glyph from every row
in the same local scope.

## Reproduction

```powershell
python tools/mgs3d_glyph_space_audit.py `
  --static-allocation analysis/ps2_korean/_archive_2026-08-07/review5-combo-position-files/sna01-allocation-report.json `
  --resident C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/stage/r_sna01/resident.hpk `
  --resident-proof analysis/ps2_korean/_archive_2026-08-07/review5-combo-position-files/sna01-allocation-report.json `
  --resident C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/stage/r_sna02/resident.hpk `
  --resident-proof analysis/ps2_korean/_archive_2026-08-07/review5-combo-position-files/sna02-allocation-report.json `
  --movie C:/Users/hhlee/Desktop/Romforge/output/unpacked_en_original_smoke_backup/partition0/romfs/movie.dat `
  --live-movie C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/movie.dat `
  --movie-translation analysis/story_media_order/romforge_apply_v1/v645_full_rebuild/movie_full_apply.csv `
  --demo C:/Users/hhlee/Desktop/Romforge/output/unpacked_en_original_smoke_backup/partition0/romfs/demo.dat `
  --live-demo C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/demo.dat `
  --demo-translation analysis/story_media_order/romforge_apply_v1/v645_full_rebuild/demo_full_apply.csv `
  --codec C:/Users/hhlee/Desktop/Romforge/output/unpacked_en_original_smoke_backup/partition0/romfs/codec.dat `
  --live-codec C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/codec.dat `
  --codec-translation analysis/ps2_korean/full_build/rebuild_2026-08-08/selected_translation.json `
  --output analysis/glyph_space_audit/current
```

## Outputs

- `common_glyphs.csv`: verified common character/token/physical-slot map.
- `movie_records.csv`, `demo_records.csv`, `demo_scenes.csv`, `codec_gcx.csv`:
  complete scope reports, including untranslated scopes.
- `live_local_slots.csv`: current live local slots and proven dead indices.
- `glyph_cost_details.csv`: every new local glyph and its owning rows.
- `overflow_glyphs.csv`: glyph detail restricted to overflowing scopes.
- `overflows.csv`: record/scene/GCX shortages.
- `audit.json`: input hashes, resident proof, and aggregate counts.

## Tests

- `python -m py_compile tools/mgs3d_glyph_space_audit.py tests/test_glyph_space_audit.py`: PASS.
- Audit unit tests plus codec size-neutral tests: 14/14 PASS.
- GCX translation/capacity/slot-owner/CLI safety tests: 16/16 PASS.
- Relevant movie token/static-page integration tests: 2/2 PASS.
- A full legacy suite attempt exposed two environment/pre-existing issues, not
  audit failures: one sandbox-denied `TemporaryDirectory` in an existing GCX
  build test, and the already-modified growing movie builder reuses slot
  `0x9001` where its old test expects an append at `0x9003`. This audit does
  not modify that builder or relax either assertion.

## Files created or changed by this analysis

- `tools/mgs3d_glyph_space_audit.py`
- `tests/test_glyph_space_audit.py`
- `docs/glyph-space-audit-2026-08-12.md`
- `analysis/glyph_space_audit/current/*` (generated CSV/JSON only)

No DAT, GCX, HPK, translation CSV/JSON, builder, or ROM image was modified.
