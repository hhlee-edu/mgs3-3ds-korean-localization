# MGS3D Korean augmentation structure study — 0.11

## Scope and safety

This is read-only structure research. The 0.10 scene-fixed demo passed its
opening playback but crashed on the first codec afterward and was rolled back.
No `code.bin` or HPK was patched during this research.

## Current no-code ceiling

- Full demo dialogue: 2,228 rows.
- The scene-padding selection reached 1,268 rows but is runtime-rejected.
- Immutable string overflow excludes 362 rows; scene glyph budget removes 598
  more.
- Dead local-slot reuse is already mathematically included by the builders and
  yields no hidden second pool.
- 64 bytes per glyph and the 191 resident slots are genuine renderer/data
  constraints, not conservative tool limits.
- New hard rule: demo file size, every record start/size, every subtitle
  position/capacity, and all scene starts must remain unchanged. Scene-local
  record growth is not safe at bulk scale even when scene starts are restored.

## A. Scene-shared glyph table

The natural demo corpus needs 4,945 record-local nonresident glyph slots. If
every record in one physical scene could reference one shared scene font, this
falls to 3,872 slots: 1,073 duplicated slots / 68,672 bytes removed. Opening
scene 127 alone saves 43 slots / 2,752 bytes.

Verdict: useful but insufficient alone. The existing `0x9001..0x93FF` page is
record-local; sharing it requires changing the per-record font pointer setup or
rewriting tokens to a new page backed by scene-owned memory.

## B. New global dynamic glyph page — primary candidate

Both confirmed text-rendering paths perform the same generic lookup for token
pages at or above `0x84`:

1. clear token flag bits;
2. derive a page number in 0x400-token units;
3. load a page pointer from global table `0x00A46FD8`;
4. index a fixed 64-byte glyph with `index << 6`.

The relevant instruction sequences are at `0x0015E63C..0x0015E678` and
`0x0015EC94..0x0015ECD8`. Both literal pools resolve to the same pointer table.
Function `0x0010A894` writes a supplied pointer into that table by page index;
for index 2 it also installs a derived pointer at table index 4.

This means augmentation need not replace the 191-slot `81/82/83` resident
page. A new token page can potentially point at one separately allocated Korean
font table. The corpus contains 733 unique Hangul syllables, needing 46,912
bitmap bytes once, versus 316,480 bytes when duplicated record-locally.

Open proof items before patching:

- inventory which dynamic page-table indices are live (`84/88/8C/90/94/98`);
- identify the lifetime and setter call for demo/movie page 3 (`90xx`);
- select an unused page without colliding with flagged token forms;
- allocate/load a 46,912-byte table with lifetime covering media playback;
- add an encoder for that page and make a one-glyph runtime probe.

Verdict: highest-value and lowest renderer-change option. It reuses the
existing 64-byte renderer rather than changing drawing mathematics.

## C. Jamo-composition renderer

The 733 used syllables decompose into 19 initials, 21 vowels, and 21 used final
consonants: 61 component bitmaps / 3,904 bytes. Capacity is excellent, but the
current renderer draws exactly one 16x16 bitmap per two-byte token. Composition
requires a new token grammar plus two or three positioned/combined bitmap
draws, including shape variants for vowel/final context.

Verdict: best theoretical compression, highest code and visual-quality risk.
Keep as fallback after the global-page probe.

## D. External subtitle string table

All natural demo strings encode to 59,815 bytes. Immutable inline slots are
short by only 3,343 bytes in aggregate, so an external table would eliminate
the 362 string-overflow exclusions. It does not solve glyph duplication by
itself. No recursive string-reference token has been proven in the current text
grammar, so this requires a loader/decoder hook or pointer-side table.

Verdict: pair with the global glyph page after the glyph probe works.

## E. Demo resolver/scene-address patch

`sddemotable.txt` maps 142 names onto IDs 0..125, while demo.dat has 130
anonymous physical scene tags; opening ID 0 maps to physical scene 127. The
scene tag carries no resource ID. The descriptor helpers at `0x004449CC` and
consumer path at `0x004BC2DC` are confirmed structural anchors, but the
ID-to-physical permutation resolver is still not located.

Verdict: high risk and unnecessary if global glyph/string storage keeps every
scene start unchanged. Continue only if the global-page route fails.

## 0.11 implementation order

1. Dynamic font-page index inventory from real movie/demo tokens and loader
   setter behavior.
2. Prove an unused page-table index and produce a no-op pointer-table probe.
3. Build a single-glyph global-page test while preserving DAT/scene layout.
4. If runtime succeeds, generate the 733-syllable global table and rebuild all
   fitting inline strings without local glyph growth.
5. Add an external string-table probe for the remaining 362 rows.
6. Retain scene-shared and Jamo composition as fallback designs.

Generated evidence:

- `analysis/augmentation_0_11/structure_hooks.json`
- `analysis/augmentation_0_11/capacity.json`
