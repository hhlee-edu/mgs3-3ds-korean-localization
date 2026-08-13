# Korean global page 8400 audit and build

## Current verdict

The renderer-isolation build was visually confirmed to display `ABC 가나다 XYZ`
by intercepting `8401..8403`.  Resident text storage, 64-byte glyph addressing,
2bpp rendering, and the fixed 16px advance therefore work.

`8401..87FF` has zero structured occurrences, including `20/40/60` flag aliases,
in the current movie, demo, and codec authorities.  It is **not yet finalized as
globally unused**: conservative scanning finds candidate byte pairs throughout
UI LA2 and resident HPK binaries.  Those pairs may be compressed/graphic data,
but they require format-aware analysis or runtime UI traversal before the range
can safely be claimed.  Existing global page data is not overwritten.

## Generated page

`tools/mgs3d_korean_global_page_build.py` deterministically reproduces the
translation inventory and subtracts the verified 191-character allocation.

```text
all Hangul              1119
existing fixed          191
new global candidates   928
page capacity           1020
free                    92
page bytes              65280 (0xFF00)
```

The tool fails if more than 1,020 new characters are required.  It emits a
full-size zero-padded page for both the 64-character stress set and all 928
characters.  It does not patch game files.

## Outputs

All outputs are under `analysis/global_korean_page_build_2026-08-12/`:

- `namespace_audit.csv/json`
- `whole_romfs_raw_candidates.csv`
- `korean_page_stress_64.bin` and its token map
- `korean_page_full.bin` and its token map
- `build_stress_64.json`, `build_full.json`

## Remaining runtime gates

1. With the already successful three-token interception build, traverse title,
   options, save/load, inventory, cure, camouflage, map, radio list, HUD,
   game-over, and result screens.  Any changed/missing UI glyph rejects page 0.
2. Before a 64-character runtime build, provide a durable 0xFF00 storage/loader.
   The proven text cave has only 1,420 bytes left; placing 4,096 bytes there
   would overlap rodata.  Expanding into it is forbidden.
3. Only after both gates pass may `8401..87FF` be marked safe and movie/demo/
   codec stress strings be generated.  No existing DAT record or GCX53 is moved.

## Reproduction

```powershell
python tools/mgs3d_korean_global_page_build.py --audit --scan-assets
python tools/mgs3d_korean_global_page_build.py --stress 64 --build-full
```
