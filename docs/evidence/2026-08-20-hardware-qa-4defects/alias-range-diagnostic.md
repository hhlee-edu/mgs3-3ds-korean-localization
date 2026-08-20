# #1 diagnostic: narrow the glyph hooks' alias range to 0xA4..0xA7

Date: 2026-08-20. Status: **staged, awaiting hardware test.** Nothing committed,
nothing pushed. **No RomFS file touched** -- `codec.dat`, `movie.dat`,
`demo.dat`, every `scenerio.gcx`, both `resident.hpk` and `cache.hpk` are
byte-identical to production.

## Why

`exefs/code.bin` carries six hooks that replace `bic rX, rY, #0x6000` with a
branch into an 815-byte cave at VA `0x0087F8C4`. That `bic` is the game's alias
fold -- token pages `0xA0`/`0xC0`/`0xE0` are alias copies of base page `0x80`,
and clearing bits 13-14 folds them back. Each hook tests two lead-byte ranges
and otherwise re-runs the original `bic`.

| range | verdict |
|---|---|
| `0x84..0x87` | correct -- `mgs3d_korean_global_page_build.py` declares the Korean namespace as `0x8401..0x87FF` and scans with `[\x84-\x87][\x01-\xff]` |
| `0xA0..0xA3` | **wrong** -- the alias of `0x84..0x87` is `0xA4..0xA7` (`t\|0x2000`). `0xA0..0xA3` is the alias of `0x80..0x83`, the game's own page |

`A0 7B` folds to `80 7B` = `{`, `C0 7D` folds to `80 7D` = `}`, `80 23` = `#`:
the `#{ ... }#` inline markup the game uses for button glyphs. Clean
`codec.dat` holds **33,798** of them (`A0 7B` x16,983, `A3 1E` x16,815) across
13,571 resources in 179 of 2,326 GCX records, 177 of which also carry PERSONAL
DATA. They are byte-identical in staged -- original game text we mis-render.
The hooks capture `{` (page `0xA0`) but not `}` (page `0xC0`), so every one of
those blocks opens and never closes.

## The change

Twelve `cmp` immediates -- six pairs, one byte each, all inside the cave:

| VA | production | diagnostic |
|---|---|---|
| `0x0087F8E8` / `0x0087F8F0` | `cmp ip, #0xa0` / `#0xa3` | `#0xa4` / `#0xa7` |
| `0x0087F9EC` / `0x0087F9F4` | `cmp r3, #0xa0` / `#0xa3` | `#0xa4` / `#0xa7` |
| `0x0087FAEC` / `0x0087FAF4` | `cmp ip, #0xa0` / `#0xa3` | `#0xa4` / `#0xa7` |
| `0x0087FB3C` / `0x0087FB44` | `cmp ip, #0xa0` / `#0xa3` | `#0xa4` / `#0xa7` |
| `0x0087FB6C` / `0x0087FB74` | `cmp r2, #0xa0` / `#0xa3` | `#0xa4` / `#0xa7` |
| `0x0087FBB4` / `0x0087FBBC` | `cmp r0, #0xa0` / `#0xa3` | `#0xa4` / `#0xa7` |

Tool: `tools/mgs3d_diag_alias_range_patch.py` (`build` / `apply` / `revert` /
`status`). Recompression uses the same 3dstool BLZ path as
`mgs3d_cpp_default_patch.py` and is round-trip verified before writing.

## Verification

**Binary scope.** Decompressed image diff production vs diagnostic:
**12 bytes, 0 outside the cave.** Cave disassembly: 203 instructions in both,
**exactly 12 differ**, all of them `cmp` immediates. The ten `0x84`/`0x87`
comparisons are present and unchanged; zero `0xA0`/`0xA3` comparisons remain.
Recompressed size is **identical** to production (5,264,540 B).

| artifact | SHA-256 |
|---|---|
| production `code.bin` (compressed) | `4e693f32b1b20d99705576a209efca4671f80fad71930650c5befe2d46527cb4` |
| production image (decompressed) | `1dee3180ef71c67f39c97eae26c08ed8156d98ec8d32304bfadc2247d4de5983` |
| diagnostic `code.bin` (compressed) | `2b115156b5f2ce831f13cfe14d536e937ab20344d5beea3e2a88960e7db628b5` |
| diagnostic image (decompressed) | `283211e147d54d7316e036d55e7c8a70f879df4756151b6b0e70d32933e53b64` |

**Staging scope.** All 924 staged files hashed before and after: **1 changed
(`exefs/code.bin`), 0 added, 0 removed, 0 RomFS files touched**, size unchanged.
`mgs3d_diag_static_font_swap.py status` still reports the Korean font on both
stages, i.e. the earlier diagnostic did not leak back in.

**Token flow, parsed from `codec.dat` (not a raw byte scan).**

| | clean | staged |
|---|---:|---:|
| Korean `84-87` tokens | 0 | 785,948 |
| alias `A0-A3` (game markup) | 33,798 | 33,798 |
| alias `A4-A7` (real Korean alias) | **0** | **0** |
| captured by production hooks | 33,798 | 819,746 |
| captured by diagnostic hooks | **0** | **785,948** |
| released back to the `bic` fold | 33,798 | 33,798 |

So the 33,798 markup tokens stop entering the Korean path, and Korean handling
is **785,948 -> 785,948: zero regression**.

**Is enabling `A4..A7` a new risk?** No, and not merely because nothing emits it
today. Under production an `A4xx` token is folded by the original `bic` to
`0x84xx` -- our Korean page -- so it already rendered as a Korean glyph. Under
the diagnostic the hook catches it and renders it as a Korean glyph. **The
outcome is the same either way**, so the new arm cannot introduce a regression.
A raw single-byte scan of the other containers was run and is reported as
inconclusive: it is dominated by false positives inside compressed GCX blobs.

**Reversibility.** `revert` restored `4e693f32...` exactly, and a second `apply`
restored `2b115156...` exactly. Round-trip is byte-exact in both directions.

**Pre-repack gate.** `mgs3d_hpk_chain_check.py` on `stage/v000a_0/cache.hpk`
exits 0 with `OK: no padded-slot drift`. RomFS passes R7 hygiene -- no `.bak`,
log, json, csv or md files anywhere in the tree.

## Test

Repack and check three things on hardware:

- **A.** PROFILE 04/04 PERSONAL DATA display
- **B.** ordinary codec Korean output (regression check -- must be unchanged)
- **C.** button/icon markup display

**#2 (Major Tom missing, The Boss showing EVA) is explicitly out of scope for
this experiment.** On current evidence it is a UI image-index problem in
`ui/menu/sv/radio.la2`, whose contact "names" are pre-rendered `.bclim` images
in a file byte-identical to clean. It is tracked separately from this alias bug.

Production is only patched if this diagnostic comes back clean.

## Restore

```
python tools/mgs3d_diag_alias_range_patch.py revert
python tools/mgs3d_diag_alias_range_patch.py status   # expect: production
```
