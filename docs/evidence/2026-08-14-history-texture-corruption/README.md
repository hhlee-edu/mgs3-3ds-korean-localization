# History-card glyph corruption — SOLVED (2026-08-14)

> **Resolved later the same day.** The root cause is that **BCLIM format 10 is
> ETC1**, a block-compressed format — not the 4-bit luminance image
> `mgs3d_history_texture.py` assumed. It wrote raw nibbles into a slot the GPU
> decodes as compressed blocks, so the card rendered as noise.
>
> Proof: decoding the pristine English member with a correct ETC1 reader
> reproduces the real in-game sentence exactly —
> *"After the end of World War II, / the world was split into two -- East and
> West. / This marked the beginning of the era called the Cold War."*
> (`SOLVED-english-etc1-decode.png`).
>
> Fix implemented and verified: `tools/mgs3d_bclim.py` (codec) and
> `tools/mgs3d_history_texture_v2.py` (rebuild). A Korean card built with them
> reads back legibly out of the rebuilt archive
> (`SOLVED-korean-etc1-readback.png`), the HPK entry header stays untouched
> (18856/3884), and `mgs3d_hpk_chain_check.py` reports no drift.
>
> The investigation notes below are kept as the record of how it was narrowed
> down; the "what is NOT yet known" section is now answered.

## How the format was identified

Every earlier hypothesis assumed a *pixel* layout and tried to find the right
stride/tiling. The breakthrough came from **not guessing**: the same DARC
carries other BCLIMs, so their payload sizes against power-of-two-padded
dimensions give the format enum directly.

| fmt | example | declared | payload | padded | bpp | meaning |
|---|---|---|---|---|---|---|
| 2 | `demo_op_0_s_alp_ovl` | 16x18 | 512 | 16x32 | 8.0 | LA44 |
| 10 | `cold_war_text_eng_alp_ovl` | 400x64 | 16384 | 512x64 | 4.0 | **ETC1** |
| 12 | `black.bclim` | 8x8 | 32 | 8x8 | 4.0 | L4 |
| 13 | `radar_base_alp_ovl` | 64x48 | 2048 | 64x64 | 4.0 | A4 |

That is exactly the standard BCLIM/BFLIM enum (…10=ETC1, 11=ETC1A4, 12=L4,
13=A4). `black.bclim` was the decisive control: a solid 8x8 tile whose 32-byte
payload pins fmt 12 at 4 bpp, proving the enum is the standard one and that
fmt 10 is therefore *not* L4/A4.

**Storage rules** (confirmed against ground truth):

* dimensions padded to the next power of two (400x64 → 512x64);
* ETC1 4x4 blocks grouped into 8x8-texel tiles (2x2 blocks); tiles in raster
  order, the four blocks inside a tile in Morton order;
* **each 8-byte ETC1 block is stored byte-reversed** — the last missing piece.
  Without the reversal the text sits in the right place but decodes as colour
  noise, which is what made the earlier attempts look so close yet unreadable.

## Original analysis (2026-08-14, before the fix)

## Hardware test result

The user built and tested a CCI using the packer-fixed `cache.hpk`
(`d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`, staged at
`builds/current/mgs3d-v065-hpk-cursor-fix/romfs/stage/v000a_0/cache.hpk`, hash
confirmed to match). Result:

- **The Data Abort is gone.** This is the first hardware confirmation that the
  [HPK cursor-drift fix](../2026-08-14-hpk-cursor-drift/README.md) works.
- **The opening history card's glyphs are all corrupted/illegible.**
- Everything else tested — demo text, etc. — displays normally.
- `codec.dat` is excluded from this test; its translation pass is still in
  progress ([[direct-v2 quality pass]]) and unrelated to rendering.

This is a **second, independent defect**, unrelated to the cursor-drift crash.
The crash fix addressed archive-chain integrity (where each entry's header
sits). This defect is about pixel data correctness inside one specific
texture. Not fixed here — analysis only, per instruction.

## Why this is isolated to the history card and nothing else

The history card is rendered through a standalone path,
`tools/mgs3d_history_texture.py`, that PIL-renders text to a bitmap and
hand-packs it into the BCLIM's native L4/A4 pixel format
(`render_native` + `encode_l4_bclim`). Every other piece of Korean text in the
game (demo, etc.) goes through the unrelated "resident glyph page + decoder
patch" system ([[Global Korean glyph track]]), which was independently
runtime-verified in the 2026-08-13 clean-glyph-baseline work. That the two
fail independently is expected: they share no code.

## Root cause (established) — the packer's pixel-layout model is wrong for this asset

### It was already an open question, not a settled fact

`wiki/History/version-0.65.md`, written before this session: *"400x64 L4,
padded in its original fixed-size member. Citra custom-texture testing
confirmed the identified card; **hardware validation of the native BCLIM
rebuild is pending**."* The "custom-texture testing" was a LayeredFS PNG
substitution (an override image shown instead of the real texture) — it never
exercised `encode_l4_bclim`. **This hardware test is the first time the actual
packed output was ever checked against anything.** It failed.

### Proof the layout model is wrong: decoding the pristine, correct asset produces noise

`tools/mgs3d_history_texture.py` decodes/encodes with a shared assumption:
8x8-tile Z-order (Morton) addressing, tile stride equal to the declared
display width (400), 4 bits per pixel. Feeding the **pristine, untouched,
known-hardware-correct** English member
(`stage/v000a_0/cache.hpk` entry 31, key `309d745f`, before any Korean patch)
through that exact decode logic does not produce legible English text — it
produces regular horizontal noise bands:

| input | result |
|---|---|
| pristine English, stride 400 (the tool's actual assumption) | `pristine-english-decoded-stride400.png` — illegible |
| pristine English, stride 512 | `pristine-english-decoded-stride512.png` — illegible |
| pristine English, no tiling (linear) | `pristine-english-decoded-linear.png` — illegible |

Two more variants were tried and also failed (not saved, reproducible from
`tools/mgs3d_history_texture.py`'s `morton`/tiling code with the modifications
noted below): linear with vertical flip, and tiled-with-byte-swap. **None of
the five layout hypotheses tested reconstruct the real English text.** The
correct layout has not been found.

### The byte count itself contradicts the tool's width assumption

The BCLIM member is 16,424 bytes; the last 40 are the CLIM/imag footer, so the
pixel payload is exactly 16,384 bytes. At 4 bits per pixel (2 pixels/byte)
and height 64, that payload holds `16384 * 2 / 64 = 512` texels per row — not
400. The tool hard-codes width (400) as the tile stride in both
`encode_l4_bclim`'s `tile = (y // 8) * (width // 8) + x // 8` and the
matching line in `decode_a4_bclim`; the true stride is provably not 400. But
forcing stride 512 into the same tiling formula *also* fails to produce
legible text (see table above), so the discrepancy is not simply "use 512
instead of 400" — something else about the layout (bit depth, tile size, tile
iteration order, or the format-10 assumption itself) is also wrong, and this
investigation did not isolate it.

### The self-consistent "success" was a false positive

Decoding the **patched Korean** member back through the same tool's own
`decode_a4_bclim` *does* produce legible Korean text
(`staged-korean-decoded-selfconsistent-stride400.png`). This is not evidence
the encoding is correct — `encode_l4_bclim` and `decode_a4_bclim` share the
same (wrong) layout formula, so decoding with the same wrong formula that
wrote the data trivially reconstructs it. This is exactly the kind of
self-consistency check that hid the bug until real hardware exposed it.

### The swizzle primitive itself is not the suspect

`tools/mgs3d_gcx_font_tool.py:34-39` implements the identical bit-interleaved
Morton/Z-order function for a *different*, previously-working asset (16x16,
2bpp custom dialogue glyphs) and it is validated correct there. So the general
Z-order convention this codebase uses is right; the bug is specific to this
L4/A4, 400x64 BCLIM asset's width/stride/format assumptions in
`mgs3d_history_texture.py`, not to the Morton math as a concept.

## Answers to the questions this file used to leave open

- **Correct pixel layout** — ETC1, padded 512x64, 2x2-block tiles in Morton
  order, blocks byte-reversed. Implemented in `tools/mgs3d_bclim.py`.
- **Does `fmt == 10` mean L4?** No. It is ETC1. The assumption came from a
  generic enum reading and was never checked against this engine; the
  sibling-BCLIM size table above settles it.
- **Do other assets share the defect?** No other BCLIM in this project goes
  through the ad-hoc encoder — the history card was the only caller of
  `encode_l4_bclim`. Other Korean text reaches the screen through the resident
  glyph page, which is a different mechanism entirely.

## Remaining caveat

The ETC1 encoder in `mgs3d_bclim.py` is lossy (ETC1 always is). A
decode → encode → decode round-trip of the *original* English card moves about
12% of pixels, mostly by small amounts on antialiased glyph edges. That
number is not a defect measure for our use: we never re-encode the original,
we encode freshly rendered Korean text, and the read-back
(`SOLVED-korean-etc1-readback.png`) is clean and legible. Hardware
confirmation of the rebuilt card is still pending.

## Evidence files

| file | note |
|---|---|
| `pristine-english-member.bclim` | untouched member, entry 31, from the clean archive (`145a82e9...`) |
| `staged-korean-member-d46373e1.bclim` | patched member from the archive that was just hardware-tested (`d46373e1...`) |
| `pristine-english-decoded-stride400.png` | tool's actual assumption, applied to known-good data → illegible |
| `pristine-english-decoded-stride512.png` | byte-count-implied stride, applied to known-good data → still illegible |
| `pristine-english-decoded-linear.png` | no-tiling hypothesis → illegible |
| `staged-korean-decoded-selfconsistent-stride400.png` | the false-positive self-consistency check |
