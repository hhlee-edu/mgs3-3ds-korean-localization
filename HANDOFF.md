# HANDOFF — MGS3D Korean Glyph Integration

## Current Goal

Continue canonical translation integration using the append-only 929-character
global map plus the exact 191-character shared-static allocation.

## Work Completed This Session

- USA clean baseline V0a/V0b/V0c PASS.
- K Gate PASS: all 169 stages use parser-relative `K = 0x56000`.
- Glyph layout: MSB-first, linear row-major, no vertical flip.
- V1 data-only and V2 trampoline PASS.
- Controlled renderer probe displayed `ABC 호프번 XYZ`.
- Three distinct resident bases matched Korean page data 4096/4096 bytes.
- Full 928-glyph page/map deterministic validation PASS.
- Probe-free clean integration CCI produced and manifested.
- Canonical master exposed one additional syllable (`칸`); append-only v2 now
  preserves 928/928 old assignments and adds it at `0x87A4`.
- Combined 1,120-character coverage and encoding preflight PASS.
- Size-preserving media candidates built and content-verified. Whole-record
  safe: movie 247/247, demo 732/732. Maximum row-level safe: movie 585/585,
  demo 1,871/1,871. They are partial subsets, not full master builds.

## Current Blocker

Full natural movie/demo text still exceeds fixed string capacity in many
records. A deliberate relocation/shortening decision is required; do not
silently treat the partial safe DATs as complete.

## Read These Wiki Pages

1. [Current State](wiki/Current-State.md)
2. [Glyph System](wiki/Glyph-System.md)
3. [Translation](wiki/Translation.md)
4. [Build System](wiki/Build-System.md)
5. [Decisions](wiki/Decisions.md)

## Next First Task

`mgs3d-globalpage-media-maxsafe01.cci` is REJECTED. Runtime showed `양`
(`0x8451`) and `써` (`0x84A4`) corrupted because the inherited stress
trampoline intercepted only `0x8401..0x8440`. Corrected full-range candidate:
`mgs3d-globalpage-media-maxsafe02.cci`, SHA-256 `727A62F1…57E3`, runtime pending.

## Cautions

- Do not overwrite `translation/10_master/` with encoded or shortened data.
- Do not include the controlled `ABC 호프번 XYZ` movie probe in clean builds.
- Do not resume exhaustive GDB traversal, save manipulation, cheats or
  equipment preparation.
- Do not generalize the three-stage runtime sample to all 169 stages.

## Key Artifacts

- `experiments/2026-08-13-clean-glyph-baseline/clean-build-manifest.json`
- `experiments/2026-08-13-clean-glyph-baseline/runtime-verification.txt`
- `experiments/2026-08-13-clean-glyph-baseline/full-page-rebuild-audit/full-928-validation.json`
- `experiments/global_korean_page_build_2026-08-12/korean_token_map_full.csv`
- `translation/40_build_input/global_page_v2/`
- `glyph/validation/global_page_v2/` (15 labelled review sheets)
- `experiments/2026-08-13-clean-glyph-baseline/media-candidate-manifest.json`
