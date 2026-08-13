# HANDOFF — MGS3D Korean Glyph Integration

## Version 0.65 Handoff (2026-08-13)

Version 0.65 is committed and pushed as `fee6d82`, tagged `v0.65`. The local
RomForge `output/unpacked` staging tree is ready to repack for hardware testing;
the CCI itself has intentionally not been built yet.

Changes already present in RomForge staging:

- The opening Cold War history card is patched natively in
  `stage/v000a_0/cache.hpk`, not in `demo.dat`. Its resource chain is HPK key
  `309d745f` -> DARC -> `timg/cold_war_text_eng_alp_ovl.bclim` (400x64 L4).
  A Citra custom-texture probe confirmed the correct screen. The native BCLIM
  still needs hardware validation.
- The first briefing's duplicated Jack subtitle slots now read
  `버추(가상)미션?`; both remain inside their original 20-byte capacities.
  Existing normalization already corrected three `버츄어스 미션` occurrences
  to `버추어스 미션`.
- Corrupted GCX 13 was confirmed to be the 264-entry internal encyclopedia
  index, not dialogue. The entire same-offset/same-size record was restored
  byte-for-byte from the pristine Western codec (`0x1C50`, 24,864 bytes).

Prepared staging hashes:

- `codec.dat`: `86cc8e12504e517fd0916de95e3f7a46b7f00b9c6859c28338d187334493c524`
- `movie.dat`: `0f7e4c961ca4d10c19a46a7076ca0155a0531ed8b10f1a54b62d382a957945dd`
- `stage/v000a_0/cache.hpk`: `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`

Validation completed: `codec.dat` parses as 2,326 GCX records / 601,657
resources; `movie.dat` round-trips byte-identically; the patched HPK zlib entry
decompresses and inventories correctly; all 140 unit tests pass (two Windows
temporary-directory ACL failures were rerun successfully with permission).

Next session:

1. Repack the already-prepared RomForge staging tree as the v0.65 CCI.
2. Test on hardware with no Citra custom-texture dependency.
3. Verify the opening history card first, then the first briefing wording.
4. Smoke-test the codec encyclopedia/radio-picture area affected by GCX 13.

Reproduction tools and detailed record:

- `tools/mgs3d_history_texture.py`
- `tools/mgs3d_hpk_inventory.py`
- `tools/mgs3d_v065_media_fix.py`
- `tools/mgs3d_restore_gcx.py`
- [Version 0.65 checkpoint](wiki/History/version-0.65.md)

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

Repack the prepared RomForge staging tree and perform the four v0.65 hardware
checks listed above. Do not rebuild the old `demo.dat` history-subtitle probe;
it targeted the first spoken demo line and was the wrong resource.

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
