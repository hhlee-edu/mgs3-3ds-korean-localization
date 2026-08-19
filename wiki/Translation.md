# Translation

**Goal:** port the reference Korean release's text and font onto the 3DS
release (*Metal Gear Solid: Snake Eater 3D*) — not author a new translation.
The English↔Korean pivot (GameFAQs English + the script reference fan-script Korean,
aligned) is diagnostic matching material, not treated as a finished PS2 port —
**except movie/demo**, where PS2 subtitles are hardsubbed and no extractable
official text exists, making the script reference the *only* practical Korean source for
those two containers ([DEC-009](Decisions.md)).

## The lineage

```
SOURCE  (PS2 CODEC.DAT, the script reference, GameFAQs English)
   │
MATCHING  (PS2 ↔ 3DS alignment, 3-way alignment — see Matching.md)
   │
MASTER  (correct translation, glyph-budget-independent)
   │
SHORTENED  (capacity-forced abbreviation, GCX/scene-budget-fit)
   │
BUILD_INPUT  (what the build pipeline actually consumes)
   │
DAT / GCX  →  CCI
```

**Never overwrite MASTER with a shortened variant.** If the global Korean glyph
track ([Glyph System](Glyph-System.md)) removes the per-GCX glyph-diversity
limit, high-quality text should be restorable *from* MASTER.

## Canonical production paths (fixed 2026-08-14)

Use this section as the authority for all future translation and staging work.
Do not choose a file merely because its name contains `final`, `direct`, or
`build`.

| Stage | Codec | Movie | Demo |
|---|---|---|---|
| Completed translation authority | `translation/10_master/codec-3ds-INTEGRATED-review-direct-v1.csv` | `translation/10_master/bundle_natural_full/movie_natural_full.csv` | `translation/10_master/bundle_natural_full/demo_natural_full.csv` |
| Active Korean quality correction | `translation/10_master/codec-3ds-INTEGRATED-review-direct-v2.csv` | edit the completed authority above | edit the completed authority above |
| 3DS/global-page converted input | `translation/40_build_input/global_page_v2/codec_natural_full_global_page.json` | `translation/40_build_input/global_page_v2/movie_natural_full_global_page.csv` | `translation/40_build_input/global_page_v2/demo_natural_full_global_page.csv` |
| Capacity-checked build input | generated from the chosen codec review CSV by `tools/mgs3d_build.py` | `translation/40_build_input/global_page_v2/movie-max-safe.csv` | `translation/40_build_input/global_page_v2/demo-max-safe.csv` |
| Verified DAT candidate | builder output; never edit the DAT directly | `translation/40_build_input/global_page_v2/movie-global-max-safe.dat` | `translation/40_build_input/global_page_v2/demo-global-max-safe.dat` |
| RomForge staging destination | `.../romfs/codec.dat` | `.../romfs/movie.dat` | `.../romfs/demo.dat` |

Canonical RomForge root:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0`

Rules:

1. Translation corrections are made only in the authority/quality-correction
   files above, never in a staged DAT.
2. `direct-v1` is the last completed codec baseline. `direct-v2` is the active
   quality pass and is not promoted to production until that pass and its
   structural verification are complete.
3. Files under `40_build_input/global_page_v2` are derived 3DS inputs. Do not
   hand-edit them as translation masters; regenerate them after master changes.
4. Copy to RomForge only after a separate build output has been produced and
   verified. There is no automatic master-to-staging synchronization.
5. Record the source CSV/JSON hash and output DAT hash whenever staging is
   updated. A staging hash without its source identity is not reproducible.

The v0.67 hardware candidate currently staged on 2026-08-14 is a checkpoint,
not the newest full translation integration: its `codec.dat` and `movie.dat`
come from the v0.65/direct-v1 lineage. Later `direct-v2` edits are therefore not
present until a deliberate rebuild and staging promotion is performed.

## Current ground truth ([DEC-012](Decisions.md))

The `analysis/1 korean_localization_bundle_2026-08-12/` bundle was the
user-confirmed consolidated final material (2026-08-13). **Its own README
stated the role split** — preserved verbatim at
`translation/BUNDLE-README-2026-08-12.md` — and was used to physically
decompose it the same day:

| Bundle folder (original) | Role | Now at |
|---|---|---|
| `translation_sources/natural_full_pre_compaction/` | **MASTER** — "축약 전 자연번역 authority" | `translation/10_master/bundle_natural_full/` |
| `translation_sources/applied_compact/` | **SHORTENED** — explicitly not a quality baseline | `translation/30_shortened/bundle_applied_compact/` |
| `translation_sources/script_ref_reference/` | SOURCE | `translation/00_source/script_ref/bundle_reference/` |
| `translation_sources/codec_3ds_original/` | SOURCE (pre-translation 3DS English) | `translation/00_source/codec_3ds_english/` |
| `translation_sources/3ds_only_dialogue/` | MASTER subset, no PS2 counterpart | `translation/10_master/3ds_only/` |
| root-level `translation_sources/*.json`/`*.csv` | superseded, old-bundle compatibility only | `translation/90_archive/pre_bundle_compat/` |
| `game_dat/` | applied/comparison DAT | `translation/40_build_input/bundle_game_dat/` |
| `glyph_analysis/` | glyph/overflow/runtime analysis | `glyph/validation/bundle_2026-08-12/` |

## Live production master

`translation/10_master/codec-3ds-INTEGRATED-review.csv` (`korean` column) is the
**live** codec master the build pipeline actually reads — 7,339
`대사집 대응 없음` (no-PS2-counterpart) candidates, of which 2,035/7,339 are currently
selected into the production build (86/2,326 GCX changed, 1,207 resources +
54 padding-only, 8,070 new glyphs). Manual backlog for the unmatched remainder:

- `translation/30_shortened/translator_worklist_4994.csv` — general work queue
- `translation/30_shortened/translator_worklist_skip_6_try.csv` — nonzero budget, worth attempting
- `translation/30_shortened/translator_worklist_skip_17_leave_english.csv` — zero budget, leave as-is
- `translation/10_master/manual_backlog/{1999final,trans1999}.csv` — the
  earlier manual-backlog working files (original folder name carried a typo,
  `INTERGRATED`)

## Shortening

Because most GCX have `free_slots=0`, a natural complete sentence usually
overshoots budget 3–4×. The batch-review shortening workflow (draft → verify →
apply → human review-merge in browser) is documented in the
`feedback-mgs3d-gcx-shortening-workflow` memory — reuse it, don't reinvent it.
**Rejected approach:** algorithmic compression ("first N English words + a
Korean particle") — explicitly rejected by the user; text authoring stays a
human job.

## In-progress material

`analysis/script_ref/codec_selected_static_media*.json`,
`codec_translation_static_media*.json`, `early-priority-selection*/` (~9 files,
3.3–23 MB, still under `analysis/` — **deliberately not physically moved**) —
confirmed 2026-08-13 to be **active in-progress translation work**,
not a classification gap. ID-keyed comparison against the current master shows
most of their Korean content isn't (yet) reconciled with it, but that's expected
for live work-in-progress, not a sign something's wrong. Leave alone; don't
auto-sort further. Full measurement detail:
`docs/cleanup-2026-08-13/translation-auto-resolution-log.md`.

## Full inventory

A complete file-by-file classification (source/master/shortened/matching/
archive/unknown, with SHA-256 and cross-references) is in
`docs/cleanup-2026-08-13/inventory.csv`, built 2026-08-13.
