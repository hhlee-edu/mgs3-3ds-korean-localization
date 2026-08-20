# #1 traceback: PROFILE / PERSONAL DATA vs the ordinary codec dialogue path

Date: 2026-08-20. Status: **analysis only. Nothing changed, nothing committed.**
The alias-range diagnostic is still staged in `exefs/code.bin`; RomFS is untouched.

## Hardware results so far

| experiment | A (PROFILE) | B (dialogue Korean) | C (markup) |
|---|---|---|---|
| clean static font | no change | no change | no change |
| alias range `0xA4..0xA7` | **no change** | **normal** | - |

So B proves the Korean glyph path works end to end. A fails anyway. The defect
is specific to the PROFILE card, not to Korean rendering.

## Hypotheses now excluded, with the evidence

- **Alias range `0xA0..0xA3`.** Refuted on hardware for #1. It is still a real
  bug against 33,798 original markup tokens and the 12-byte fix is worth keeping
  on its own merits, but it is not this defect.
- **The 12 unhooked alias folds.** `code.bin` has 35 `bic rX, rY, #0x6000`
  instructions. Ten of them (function `0x0013CB6C`) are **bitfield packing, not
  text** -- they clear a 2-bit field and immediately `orr` it back to
  `#0x2000/#0x4000/#0x6000/#0xe000` alongside `<<7`, `<<11`, `<<17`, `<<24`
  field writes. After filtering, **18 are real glyph-token folds and only 6 are
  hooked**:

  | function | token folds | hooked |
  |---|---:|---:|
  | `0x0015E080` | 5 | 0 |
  | `0x0015E3C4` | 3 | 2 |
  | `0x0015EBD8` | 1 | 1 |
  | `0x00183884` | 8 | 3 |
  | `0x0024FA90` | 1 | 0 |

  Worth recording -- two functions got partial coverage -- but **it does not
  explain #1**: `bic #0x6000` is a **no-op on `0x84xx..0x87xx`** (neither bit 13
  nor bit 14 is set in that range), and every unhooked site I disassembled is an
  equality test against a specific control code (`0x831E` at `0x00183F28`,
  `0x8028`/`0x8030` at `0x00183C7C`, a literal-table compare at `0x00183AC0`) or
  a token search loop. A Korean token passes through them unchanged, which is
  the correct behaviour.
- **The token-rewriting site `0x0024FB78`.** The only fold that writes back into
  the string buffer (`strb`/`strb`). It computes `(token - 0x8400) >> 10` and
  compares against `r6`, which is **hardcoded to 2** at `0x0024FB38`, so it only
  remaps `[0x8C00, 0x8FFF]` (the original's 68 `8Cxx` tokens) down by `0x400`.
  Our `0x8401..0x87FF` is bank 0 and never matches. Excluded.
- **Row width.** Clean PERSONAL DATA never exceeds **200 px** -- max, p99 and the
  budget are all exactly 200. Staged exceeds it in **1,575 of 217,056 lines
  (0.73 %)**, max 216 px, and its median line is actually *narrower* than clean
  (120 px vs 144 px). A real defect, far too small to be "mass corruption".

## The structural difference between the two paths

Same measurement, clean-derived resource indices applied to both builds:

| per line | clean PROFILE | staged PROFILE | staged dialogue |
|---|---:|---:|---:|
| lines | 217,056 | 217,056 | 991,043 |
| ASCII only | **100.0 %** | 0.8 % | 72.8 % |
| mixes ASCII + DBCS | 0.0 % | **66.7 %** | 10.0 % |
| uses static font `81-83` | 0.0 % | **92.8 %** | 25.5 % |
| uses global page `84-87` | 0.0 % | 59.5 % | 20.2 % |
| **uses both font systems on one line** | 0.0 % | **53.1 %** | 19.6 % |

Two things fall out:

1. **The original PROFILE card is 100 % single-byte ASCII, zero DBCS tokens.**
   Its layout path was never exercised with a wide glyph in the shipped game.
   Dialogue, by contrast, was already 1.5 % mixed in clean.
2. **Staged PROFILE leans on the static font far harder than dialogue does** --
   92.8 % of its lines versus 25.5 % -- and puts both font systems on the same
   line in 53.1 % of lines versus 19.6 %.

## Why the static-font experiment did not settle anything

The static dialogue font is HPK member `453c386e`. A full scan of the clean tree
finds it in **exactly 2 files out of 181 stages**:

```
stage/r_sna01/resident.hpk
stage/r_sna02/resident.hpk
```

The diagnostic CCI swapped those two archives and nothing else, so it can only
change what is drawn **while the player is inside r_sna01 or r_sna02**. If the
failing PROFILE was opened from any of the other 179 stages, "no change" is not
evidence that the font is innocent -- the swapped asset was never loaded.

That matters because staged PERSONAL DATA is **92.8 % dependent on tokens
`81xx/82xx/83xx`, which are exactly the slots that live in that stage-scoped
archive**, while the dialogue that renders correctly leans much more on the
global page.

**Leading hypothesis:** the PROFILE card resolves most of its glyphs through a
stage-resident font that is absent in most stages, in a screen whose original
content never used that font at all. Two observations are missing before this
can be called: which stage the failing PROFILE was opened from, and whether the
**Korean** inside the card renders (every report so far only covers the
English/digits/symbols).

## Minimal diagnostic candidates -- proposals only, nothing applied

Ranked. The first three change no code at all.

- **D0 - free, do first.** Record (a) which stage/scene the broken PROFILE was
  opened from, and (b) whether the Korean text inside the PERSONAL DATA card
  renders. If the failing screen was outside `r_sna01`/`r_sna02`, re-run the
  existing static-font diagnostic CCI *inside* one of those two stages. No build
  needed for (a) and (b).
- **D1 - data only, strongest discriminator.** Re-encode the 27,132 PERSONAL
  DATA resources to use **only** global-page tokens `0x84..0x87`, dropping
  `81/82/83` entirely. Touches nothing else. If the card clears, the
  stage-scoped static font is the cause.
- **D2 - data only, cleanest yes/no.** Revert the 27,132 PERSONAL DATA resources
  to clean English (back to 100 % ASCII) and leave every other translation in
  place. If the card renders perfectly, the defect is triggered solely by our
  DBCS insertion into that screen.
- **D3 - data only, cheapest.** Revert just the 1,575 over-200 px locations (two
  distinct rows: `선호 영화:...` at 208 px x883, `선호 마스코트:...` at 216 px
  x692). Isolates the width/clip sub-defect from everything else.
- **D4 - code, low priority.** Hook the remaining 12 glyph-token folds. Ranked
  last because `bic #0x6000` is a no-op on `0x84..0x87` and the sites are
  control-code compares, so the expected effect is nil -- but it is the only
  remaining code-side lever if D0-D3 all come back clean.
