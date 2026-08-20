# Static-font diagnostic — is resident.hpk the common cause of #1 and #2?

Date: 2026-08-20. Status: **hypothesis REFUTED on hardware. Production restored.** Nothing committed,
nothing pushed, no translation data touched.

## Question

Hardware QA reproduced two defects that may share one cause:

- **#1 PROFILE 04/04 (Major Zero).** The Korean radio subtitle at the bottom
  renders correctly, but the **PERSONAL DATA block at the top loses or corrupts
  most of its English letters, digits and symbols.** The earlier 200 px
  row-width theory does not explain this: a width problem would clip Korean too,
  and it would not selectively destroy Latin/numeric/symbol glyphs.
- **#2 Codec contact UI.** Major Tom's name does not appear; selecting The Boss
  shows EVA.

## Why the static font is the suspect

`resident.hpk` in `stage/r_sna01` and `stage/r_sna02` carries the static
dialogue font as HPK member `453c386e` (zlib, 7,479 packed / 21,128 unpacked).
Its payload is an 8,712-byte metric/offset table at `0x0000..0x2207` followed by
**194 glyph slots of 64 bytes each** (16x16, 2 bpp) at `0x2208..0x5207`.

The Korean build overwrites glyph bitmaps in place:

| | value |
|---|---|
| glyph slots total | 194 |
| slots overwritten with Hangul | **191** |
| slots left alone | 3 — `165`, `192`, `193` |
| metric/offset table (`0x0000..0x2207`) | **byte-identical to clean** |
| member packed size | identical, so no HPK index shift |
| `resident.hpk` file size | identical (1,528,898 / 1,144,621) |

Token mapping (`tools/mgs3d_hpk_static_korean.py`): slots `0..80` are tokens
`8101..8151`, slots `81..164` are `8201..8254`, slots `166..191` are
`8302..831B`. Slot `165` (`8301`) is runtime-cleared, which is why it is one of
the three untouched slots.

In clean, those 191 slots hold the static font's **Latin, numeric, punctuation
and symbol glyphs**. So any UI element that draws through the static font path
now paints Hangul bitmaps through an unchanged mapping — the text is looked up
correctly and drawn wrong. That is exactly the shape of defect #1: symbols and
Latin destroyed, Korean untouched, no layout shift.

Defect #2 is a weaker fit. Glyph substitution explains a *garbled* or *blank*
name (Major Tom), but it does not obviously explain a *different correct name*
(The Boss showing EVA), which looks like a selection/index fault rather than a
raster fault. The test below discriminates: if B normalises but C does not, #2
is two separate faults and only its first half is font-related.

## The diagnostic build

`tools/mgs3d_diag_static_font_swap.py apply` restores **only** that member, so
the diagnostic differs from production in two files and nothing else.

Verified before applying — production vs clean, whole file, byte by byte:

| stage | total differing bytes | inside font member | outside font member |
|---|---|---|---|
| r_sna01 | 7,453 | 7,453 | **0** |
| r_sna02 | 7,453 | 7,453 | **0** |

Because the diff is fully contained, restoring the member is identical to
restoring the whole archive, and the diagnostic file equals clean exactly.

| file | production (Korean font) | diagnostic (clean font) |
|---|---|---|
| `stage/r_sna01/resident.hpk` | `4a03cecbb5c38921e47da5d9177f40bc82a6729219731e636a83989809edf38e` | `719bfa972d26efdd24146245995e8aff3a988fc8fedfb6b9057ab66938db5249` |
| `stage/r_sna02/resident.hpk` | `b08b3125394629ec…` (see manifest) | `2fa31647c40f9b9b5d9998f21c7998bcd0f59a0b58b353ee99eed2825d6e64b6` |

Whole-tree check across all 924 staged files, before vs after `apply`:
**2 changed, 0 added, 0 removed**, both `resident.hpk`, both same size.
`codec.dat`, `movie.dat`, `demo.dat`, every `scenerio.gcx`, `ui/*.la2`,
`slot.dat`, `vox.dat` and `exefs/code.bin` are untouched.

Pre-repack gate (`wiki/Build-System.md`): `mgs3d_hpk_chain_check.py` on
`stage/v000a_0/cache.hpk` exits 0 with `OK: no padded-slot drift`. Its SHA-256
is `e02312fc2a52a954090900f0307e67f2bdaee7236bd8d6a7e622cc9e180a28dc`; the
hash recorded in the wiki (`d46373e1…`) is the v0.67-era pin and is stale, but
the archive is **not** the known-defective `49447057…`, and this file is
unchanged from the production build that already booted on hardware. RomFS also
passes R7 hygiene — no `.bak`, log, json, csv or md files anywhere in the tree.

## Baseline for comparison

The production CCI used for the hardware QA that found #1 and #2:

```
C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack.cci
3,303,145,472 bytes
SHA-256 803e72359d60ad2eeaaf8a5c456cbda720cc2e56726ee96f07df35c1255b837f
```

Confirmed by `tools/mgs3d_diag_cci_verify.py`: its embedded `r_sna01` /
`r_sna02` archives hash to the production font at image offsets `0x08FB7AB30`
and `0x08FD6A2C0`.

## Diagnostic CCI - built and verified

```
C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack_.cci
3,303,145,472 bytes
SHA-256 a8c41db9737aa3b74b2a5ed4ea4edbbf087c67fdef112ee42b2988ab4f58fb2b
```

`tools/mgs3d_diag_cci_verify.py` -> `diagnostic CCI confirmed`. The embedded
archives hash to the clean font at image offsets `0x08FB7AB30` (r_sna01) and
`0x08FD6A2C0` (r_sna02) -- **the same offsets as the production image**, so the
RomFS layout did not move.

Full byte-diff of the two 3.3 GB images, production vs diagnostic:

| region | differing bytes | what it is |
|---|---|---|
| `r_sna01` archive | 7,453 | the font member |
| `r_sna02` archive | 7,453 | the font member |
| 6 runs elsewhere | 320 | **10 x 32-byte SHA-256, nothing else** |
| everything else | **0** | |

The 320 bytes are the NCCH/IVFC integrity chain recomputing over the changed
RomFS, and they are required to change:

| offset | role |
|---|---|
| `0x0000041E0` | partition0 NCCH header, RomFS superblock hash |
| `0x0005424C0` | RomFS `+0x4C0`, inside the 0x800 hash region (IVFC master hash) |
| `0x0C2260DA0`, `0x0C2260E20` | IVFC level-1 hashes (1 x 32 B each) |
| `0x0C345B940`, `0x0C345FA60` | IVFC level-2 hashes (3 x 32 B each) |

Two further guarantees fall out of the same diff:

- The **exefs superblock hash at `0x41C0` is unchanged** -- `code.bin` and the
  whole exefs are byte-identical between the two images. No code change is
  riding along with this diagnostic.
- **partition1 (`0x0C3AA8000`) and partition7 (`0x0C3D04000`) are
  byte-identical** -- no diff run falls inside either.

So the two images differ by exactly one variable: the 191 static-font glyph
bitmaps. The production baseline `MGS SNAKE EATER 3D_Repack.cci`
(`803e7235...`) was not overwritten and is still on disk for comparison.

## Test

Boot the diagnostic CCI and record three observations:

- **A.** PROFILE 04/04 PERSONAL DATA renders English/digits/symbols correctly.
- **B.** Major Tom's name appears in the codec contact UI.
- **C.** Selecting The Boss no longer shows EVA.

Prediction: **A normalises.** B is likely. C is the discriminator — if C stays
broken while A and B recover, #2 is not one defect but two, and the EVA
misdisplay lives outside the font.

All three normalising confirms the static font as the common cause of #1 and #2.
Until then, no production fix is applied.

## Restore

The diagnostic is currently live in staging. After the test:

```
python tools/mgs3d_diag_static_font_swap.py revert
python tools/mgs3d_diag_static_font_swap.py status     # expect: Korean font
```

Production copies are held at `builds/diag-2026-08-20-static-font/production-backup/`
and are hash-verified against staging on both directions of the swap.


---

# RESULT: refuted, and where the trail goes next

## Hardware verdict

A, B and C were **all unchanged** with the clean static font in place. The font
is exonerated for both defects. Production staging was restored the same day:
`revert` ran clean and all **924 staged files are byte-identical** to the
pre-diagnostic snapshot, so nothing from this experiment survives in the tree.

## #2 is not ours, and is not #1

The bottom radio contact UI is `romfs/ui/menu/sv/radio.la2`
(`romfs/ui/test/test_radio.la2` is the test variant). It carries **no contact
name text at all**. The names are pre-rendered images:

```
rad_icn_zero.bclim   rad_icn_medic.bclim   rad_icn_sigint.bclim
rad_icn_theboss.bclim  rad_icn_eva.bclim   rad_icn_save.bclim
rad_icn_damylarge.bclim  rad_icn_damynomal.bclim   <- "damy" = dummy
```

There is **no `rad_icn_majortom`** in the set — only `rad_icn_zero`. Selecting a
contact therefore picks an *image index*, and "no name shown" / "the wrong name
shown" are both image-index outcomes, not text or glyph outcomes.

`slot.dat` additionally embeds two copies of a contact table whose UTF-16LE
placeholder panes read `MAJOR TOM / PARAMEDIC / SIGINT / THE BOSS / EVA`.

| file | clean vs staging |
|---|---|
| `ui/menu/sv/radio.la2` | identical, `a2fa694d7379ab20…` |
| `ui/test/test_radio.la2` | identical, `4e488020fcf30043…` |
| `slot.dat` | identical |

That subsystem is darc -> `.bclyt` layout -> `.bclim` images + `.bcfnt` fonts.
It shares **nothing** with the codec path every one of our changes lives in
(`codec.dat` DBCS tokens -> `resident.hpk` static font). Our only code edits are
six hooks in the DBCS token decoder plus the CPP patch — none of which the
BCFNT/BCLYT renderer executes.

**Conclusion: #1 and #2 do not share a cause, and #2 cannot be produced by our
change set.** Treat it as stock behaviour until a clean unpatched build says
otherwise.

## What #1 actually changed (measured, 27,132 PERSONAL DATA resources)

| | ASCII letters/digits | ASCII symbols/space | 2-byte tokens |
|---|---:|---:|---:|
| clean | 2,979,173 | 552,837 | **0** |
| staged | 866,518 | 516,644 | **833,468** |

Clean PERSONAL DATA is **100 % single-byte ASCII**. Our build replaced ~2.1 M
ASCII characters with wide tokens, so the PROFILE card is now a **mixed
ASCII + wide-token line** — a case that screen never had to render before.
Staged lead bytes: `81:260,694 82:294,906 83:36,815 84:202,917 85:29,215
86:4,767 87:4,154`. Every `81/82/83` low byte is inside the 194-slot static-font
range, so the token stream itself is self-consistent.

## A separate, confirmed regression: the hooks capture the wrong alias page

`exefs/code.bin` differs from clean by **692 bytes in 8 runs** (decompressed size
unchanged at 8,478,720). Six of them replace `bic rX, rY, #0x6000` with a branch
into an 815-byte cave at VA `0x0087F8C4`:

| site VA | clean instruction | cave entry |
|---|---|---|
| `0x0015E5A4` | `bic r1, r1, #0x6000` | `0x0087FB68` |
| `0x0015E600` | `bic r1, r1, #0x6000` | `0x0087F8C4` |
| `0x0015EC58` | `bic r1, sb, #0x6000` | `0x0087F9C8` |
| `0x00183A04` | `bic r0, r1, #0x6000` | `0x0087FB90` |
| `0x00184398` | `bic r0, r0, #0x6000` | `0x0087FAC8` |
| `0x0018445C` | `bic r1, r1, #0x6000` | `0x0087FB18` |

That `bic` is the game's **alias fold**: token pages `0xA0`, `0xC0` and `0xE0`
are alias copies of base page `0x80`, and clearing bits 13-14 folds them back.
Each hook tests two ranges and otherwise re-executes the original `bic` — the
non-Korean fall-through is byte-faithful. The two ranges are:

- `0x84..0x87` — our Korean page. `mgs3d_korean_global_page_build.py` declares
  the namespace as `0x8401..0x87FF` and scans with `[\x84-\x87][\x01-\xff]`.
  **Correct.**
- `0xA0..0xA3` — **wrong.** The alias of `0x84..0x87` is `0xA4..0xA7`
  (`t|0x2000`, exactly what the same tool's alias audit computes). `0xA0..0xA3`
  is the alias of `0x80..0x83`, the game's own page. This is an **off-by-4**.

What that page actually holds, from clean `codec.dat`:

```
... press the Enter button (   8023  A07B   A31E 8030  C07D  8023   )
                               #     {             }      #
```

`A0 7B` folds to `80 7B` = `{`, `C0 7D` folds to `80 7D` = `}`, `80 23` = `#`.
These are the `#{ … }#` inline markup blocks the game uses for button glyphs.

| | count in clean `codec.dat` |
|---|---:|
| `A0 7B` (the `{`) | 16,983 |
| `A3 1E` | 16,815 |
| **total captured by the hooks** | **33,798** |
| resources affected | 13,571 |
| GCX records affected | 179 of 2,326 — **177 of them also hold PERSONAL DATA** |

These tokens are **byte-identical in staged**: this is original game text we
never touched and now mis-render. Under the hooks they are re-based as
`token - 0xA001` into the Korean glyph page, and the markup dispatch that
follows the patched instruction is skipped entirely. Two of the six hooks also
force glyph width to `0x10`, where clean left `A0 7B` narrow (`0x807B < 0x8100`,
so `movge` never fired).

Worst of it: the hooks capture `{` (page `0xA0`) but **not** `}` (page `0xC0`,
outside both tested ranges). Every one of those markup blocks now opens and
never closes.

## Next step

The cheapest decisive experiment for #1 is on the **code** side, not the assets:
narrow the second range in all six hooks from `0xA0..0xA3` to `0xA4..0xA7` and
retest. It is a 12-byte change (six `cmp` immediate pairs), fully reversible,
and it removes 33,798 mis-routed original tokens without touching one byte of
translation data. Nothing has been applied — this is a proposal.
