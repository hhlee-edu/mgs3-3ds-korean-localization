# Version 0.67 checkpoint

Version 0.67 records the 2026-08-14 HPK cursor-drift fix, hardware result, build
lineage cleanup, and canonical translation/staging paths. It is a development
checkpoint, not a finished translation release.

## Confirmed

- `tools/mgs3d_history_texture.py` preserves the HPK entry's declared packed
  slot size and pads the shorter zlib stream, preventing sequential-loader
  cursor drift.
- Corrected `cache.hpk` SHA-256:
  `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`.
- `tools/mgs3d_hpk_chain_check.py` reports `OK: no padded-slot drift` for the
  corrected archive.
- Hardware testing confirmed that the corrected archive no longer produces
  the Data Abort.
- The canonical RomForge staging root is
  `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0`.

## Known open defect

The opening history card's Korean glyphs are corrupted on hardware. This is
independent of the resolved HPK crash: the ad hoc BCLIM encoder's pixel-layout
model does not decode the pristine English member correctly and therefore is
not a valid encoder for this asset. See
`docs/evidence/2026-08-14-history-texture-corruption/README.md`.

## Translation state

- Codec `direct-v1` is the last completed baseline.
- Codec `direct-v2` is an unfinished quality-correction working file and is not
  silently promoted into staging.
- `translation/10_master/` is the translation authority.
- `translation/40_build_input/global_page_v2/` contains derived 3DS build
  inputs, not editable translation masters.
- Exact production paths and promotion rules are recorded in
  `wiki/Translation.md`.

## Build hygiene

The misleading seven-underscore CCI was extracted and identified as the
controlled `ABC 호프번 XYZ` probe, not the historical golden build. It was
removed from the canonical output root and archived without deletion.

Before any new CCI build, verify the staged `cache.hpk` with both the chain
checker and SHA-256. After packing, extract the CCI and verify the internal
`stage/v000a_0/cache.hpk` hash before hardware testing.
