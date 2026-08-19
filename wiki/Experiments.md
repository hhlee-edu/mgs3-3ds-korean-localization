# Experiments

Detailed run-by-run README/manifest content stays in each experiment directory
under `analysis/` ([Conventions](Conventions.md) R9) — this page is an index,
not a duplicate.

Full grouping (29 candidate `experiments/<run>/` directories, by size):
[`docs/cleanup-2026-08-13/experiment-runs.md`](../docs/cleanup-2026-08-13/experiment-runs.md).

## Largest / most relevant current runs

| Run | What it is | Status |
|---|---|---|
| `experiments/script_ref/full_build/rebuild_2026-08-08/` (24.8 GB) | Movie/demo scene-budget rebuild candidates from the 2026-08-08 grow investigation | see [DAT Formats](DAT-Formats.md) |
| `experiments/global_korean_glyph_poc_2026-08-12/` (12.3 GB) | Global Korean glyph track POCs — includes the successful 3-glyph renderer isolation and the rejected separate-asset-loader attempt | see [Glyph System](Glyph-System.md) |
| `experiments/story_media_order/` (11.7 GB) | Movie/demo playback-order extraction and relocation apply attempts | see [DAT Formats](DAT-Formats.md) |
| `experiments/scene_fixed_natural_2026-08-12/` (3.9 GB) | Scene-boundary-safe demo builds | see [DAT Formats](DAT-Formats.md) |
| `experiments/shared_glyph_optimized_build_2026-08-12/` (3.2 GB) | Shared-glyph capacity optimization attempts | see [Glyph System](Glyph-System.md) |
| `experiments/movie_relocation_20260810/` | Movie/demo relocation validation (the scene-container discovery) | CONFIRMED — see [Current State](Current-State.md) |
| `experiments/japanese_reassembly/` | Japanese source-reassembly pipeline | **REJECTED**, [DEC-005](Decisions.md) |
| `archive/old-data/rejected/fixed_radius_batch_v1/` | Fixed-radius batch dialogue matching | **REJECTED**, [DEC-008](Decisions.md) |

## Naming note

Most runs already carry their own date in the directory name
(`*_2026-08-12`, `*_20260810`) rather than the proposed `YYYY-MM-DD-name/`
convention. Renaming them would break reproduction commands recorded in
existing docs ([Conventions](Conventions.md), and
`docs/cleanup-2026-08-13/README.md` §2.4) — left as-is.
