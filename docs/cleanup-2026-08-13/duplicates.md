# Byte-identical duplicate report — 2026-08-13

Generated read-only. **No file was moved or deleted.**

- duplicate content groups: **2990**
- redundant bytes (all copies but one): **29.27 GB**

## Why size alone must never be used to deduplicate here

Size-neutral builds are *designed* to preserve byte length. In this tree
**40 files share size 772,935,680 but hold 22 distinct contents.**
Deduplicating by size would have destroyed 18 unique builds.
Every group below is confirmed by SHA-256.

## Groups larger than 100 MB per copy

### 772.9 MB x 6 copies — redundant 3.86 GB
`sha256:de580f77e97f243c7b88c2ed…`

- `analysis/1 korean_localization_bundle_2026-08-12/game_dat/demo_live_safe_base.dat`
- `analysis/global_korean_glyph_poc_2026-08-12/romforge_isolated_full/partition0/romfs/demo.dat`
- `analysis/scene_fixed_natural_2026-08-12/demo_live_safe_base.dat`
- `analysis/story_media_order/romforge_apply_v1/backup_before_v645_careful_restage/demo.dat`
- `analysis/story_media_order/romforge_apply_v1/v645_full_html/demo.dat`
- `analysis/story_media_order/romforge_apply_v1/v645_full_rebuild/demo.dat`

### 772.9 MB x 6 copies — redundant 3.86 GB
`sha256:ec0dc24caf2f9544f2a69b43…`

- `analysis/_archive_2026-08-07/english_bulk_candidate/demo_fixed_size_reclaim.dat`
- `analysis/_archive_2026-08-07/english_bulk_final/demo_a.dat`
- `analysis/_archive_2026-08-07/english_bulk_final/demo_b.dat`
- `analysis/ps2_korean/_archive_2026-08-07/integrated_next/demo.dat`
- `analysis/ps2_korean/_archive_2026-08-07/staging_backup_broken_tom_movie_demo/demo.dat`
- `analysis/ps2_korean/_archive_2026-08-07/staging_demo_only/demo.dat`

### 773.0 MB x 5 copies — redundant 3.09 GB
`sha256:44fa6fbba5dabfb4730e8272…`

- `analysis/_archive_2026-08-07/korean_first_draft/000400000007A000/romfs/demo.dat`
- `analysis/_archive_2026-08-07/runtime_bisect/demo_fixed_max_safe_64.dat`
- `analysis/_archive_2026-08-07/runtime_bisect/demo_fixed_max_safe_64_mapping_corrected.dat`
- `analysis/ps2_korean/_archive_2026-08-07/staging_media_minimal/demo.dat`
- `analysis/ps2_korean/_archive_2026-08-07/staging_movie_full_test/demo.dat`

### 772.9 MB x 4 copies — redundant 2.32 GB
`sha256:e216f28fb8792ce911e96eee…`

- `analysis/ps2_korean/_archive_2026-08-07/staging_backup_before_tom_movie_demo/demo.dat`
- `analysis/ps2_korean/_archive_2026-08-07/staging_movie_only/demo.dat`
- `analysis/ps2_korean/_archive_2026-08-07/staging_tom_codec_original_media/demo.dat`
- `analysis/ps2_korean/golden_real3ds_2026-08-02/demo_original_size.dat`

### 772.9 MB x 3 copies — redundant 1.55 GB
`sha256:d3437249681d963bf4efd618…`

- `analysis/global_korean_glyph_poc_2026-08-12/romforge_isolated_full/partition0/romfs/demo.dat.bak-before-autofit106-2026-08-07`
- `analysis/ps2_korean/_archive_2026-08-07/demo_static_media_191_fixed.dat`
- `analysis/ps2_korean/_archive_2026-08-07/integrated_191_candidate/romfs/demo.dat`

### 772.9 MB x 3 copies — redundant 1.55 GB
`sha256:43a8a3e881f2337b8499a09f…`

- `analysis/romforge_ready_hybrid_2026-08-12/romfs/demo.dat`
- `analysis/romforge_ready_hybrid_livebase_2026-08-12/romfs/demo.dat`
- `analysis/shared_glyph_optimized_build_2026-08-12/demo_hybrid.dat`

### 773.6 MB x 2 copies — redundant 0.77 GB
`sha256:b768d62c35e0bb543c9856a8…`

- `analysis/ps2_korean/full_build/rebuild_2026-08-08/demo_full_grow.dat`
- `analysis/ps2_korean/full_build/rebuild_2026-08-08/demo_natural_grow_all.dat`

### 773.2 MB x 2 copies — redundant 0.77 GB
`sha256:c7610e933965da1a70530989…`

- `analysis/runtime_test_natural_grow_2026-08-12/romfs/demo.dat`
- `analysis/structure_expansion_2026-08-12/demo_natural_grow.dat`

### 773.1 MB x 2 copies — redundant 0.77 GB
`sha256:bbbf4ccdd26a39ffe1f0f56b…`

- `analysis/shared_glyph_optimized_build_2026-08-12/demo.dat`
- `analysis/shared_glyph_optimized_build_2026-08-12/demo_dead_reuse.dat`

### 773.0 MB x 2 copies — redundant 0.77 GB
`sha256:ad18a9ee0ace7f9d964f57a7…`

- `Citra/load/mods/000400000007A000/romfs/demo.dat`
- `dist/citra_korean_auto/000400000007A000/romfs/demo.dat`

### 772.9 MB x 2 copies — redundant 0.77 GB
`sha256:800159a0517f759bd6eb3825…`

- `analysis/story_media_order/romforge_apply_v1/backup_before_v644_stage/demo.dat`
- `analysis/story_media_order/romforge_apply_v1/demo_127_first_row.dat`

### 772.9 MB x 2 copies — redundant 0.77 GB
`sha256:3ac4cdc2af5fd6a23dc7292b…`

- `analysis/en_demo_smoke.dat`
- `analysis/story_media_order/romforge_apply_v1/demo_single_row.dat`

### 772.9 MB x 2 copies — redundant 0.77 GB
`sha256:1bdc787cbebdc4bfe1e2b4e3…`

- `analysis/ps2_korean/_archive_2026-08-07/demo_static_media_fixed.dat`
- `analysis/ps2_korean/_archive_2026-08-07/fallback165_patch/partition0/romfs/demo.dat`

### 772.9 MB x 2 copies — redundant 0.77 GB
`sha256:84f2efb06bc5a00b1eb4ec31…`

- `analysis/story_media_order/romforge_apply_v1/backup_before_v645_full_stage/demo.dat`
- `analysis/story_media_order/romforge_apply_v1/v644_gold_remapped/demo.dat`

### 772.9 MB x 2 copies — redundant 0.77 GB
`sha256:5d82314f4a7a6def83622572…`

- `analysis/story_media_order/romforge_apply_v1/v645_full_html/demo_v645_full_reclaim_grown.dat`
- `analysis/story_media_order/romforge_apply_v1/v645_full_rebuild/demo_grown.dat`

### 120.1 MB x 2 copies — redundant 0.12 GB
`sha256:c5a1b9579bb3596dc9f3b4bd…`

- `analysis/global_korean_glyph_poc_2026-08-12/romforge_isolated_full/partition0/romfs/sound/adx/bgm_streamfiles.awb`
- `partition0/romfs/sound/adx/bgm_streamfiles.awb`

## Remaining groups

2974 further duplicate groups exist under 100 MB per copy; see `inventory.csv` column `dup_copies` (>1 means duplicated).
