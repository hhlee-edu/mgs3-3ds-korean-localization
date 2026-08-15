# 감/달 control-code collision — reassigned to the global page (2026-08-15)

Data-only fix. No `code.bin` patch, no CCI, no token-mapping scheme change.

## The defect

The layout engine tests decoded tokens against control constants. At
`0x00183D68` (mirrored at `0x00184544`):

```
sub    r1, r0, #0x8000
subs   r1, r1, #0x308      ; r0 == 0x8308 ?
subne  r1, r0, #0x8300
subsne r1, r1, #9          ; r0 == 0x8309 ?
beq    0x183d90            ; -> special handler, not drawn
```

`0x8308` and `0x8309` were the static allocation's slots for **감** and **달**,
so both characters were consumed as control codes instead of being drawn.

Scale: the currently accepted codec text contains **감 ×141 and 달 ×146**. Until
now the whole 929-character global page rendered blank, which masked this; once
the base re-anchoring lands (`korean-base-obj-snapshot-2026-08-15.md`) this
would have been the next visible defect.

## The fix

Move both characters out of the static allocation so they are supplied by the
global page instead. Global-page tokens are normalised to the `0x8101` sentinel
by `korean_layout_classify` before those tests run, so they no longer collide.

Note this makes the `korean_layout_classify` patch load-bearing for the first
time — it was a proven no-op for every previously assigned character
(`global-page-render-path-audit-2026-08-15.md` §3).

| character | before | after |
|---|---|---|
| 달 | `0x8309` (static) | `0x87A5` (global, slot 929) |
| 감 | `0x8308` (static) | `0x87A6` (global, slot 930) |

The static allocation report itself is **not** edited: it maps character →
explicit token, so the two characters are simply skipped by the consuming
tools and the other 189 keep their exact tokens. The static HPK font still
carries glyphs at the two vacated slots; they are now unreferenced and
harmless, so `cache.hpk` does not need rebuilding.

Implemented as one shared constant, `CONTROL_CODE_COLLIDING` in
`tools/mgs3d_korean_global_page_build.py`, consumed by
`tools/mgs3d_global_page_build_input.py`.

Also relaxed: the `--extend-map` guard used to abort when a previously
allocated character had dropped out of the corpus. Append-only means a slot is
never reclaimed (dropping one would renumber every later token), and the code
below the guard already retained them, so it now reports instead of aborting.
Three characters are retained on that basis: 쪘 쭈 챈.

## Verification

| check | result |
|---|---|
| page size | 65,280 B, unchanged — `scenerio.gcx` sizes and `K` are unaffected |
| slots 0..928 | **byte-identical** to the previous page (append-only intact) |
| slots changed | exactly 929 and 930, previously zero, now 29 non-zero bytes each |
| glyph render | slot 929 = ㄷ+ㅏ / ㄹ (달), slot 930 = ㄱ+ㅏ / ㅁ (감) |
| token map | first 929 rows identical; 2 appended |
| character map | **exactly 2 assignments changed**, total still 1,120 |
| coverage checks | all PASS except the pre-existing `all_authoring_text_encodes` |
| encoded size | both old and new tokens are 2 bytes — **zero capacity impact** |

Hashes after the rebuild:

| file | sha256 |
|---|---|
| `korean_page_full.bin` | `5cd669563973b622d488d8d4261f2c0a489362b83e999a2bba0580075ed4e862` |
| `korean_token_map_full.csv` | `44608830e00c539ef2c9236a7f891b7c85e646ece5aa6a51c56708dca5430849` |

Previous page/map/manifest archived to
`glyph/pages/global_korean_page_v2/archive-pre-gam-dal-20260815/`.

## Not done yet

The data layer is fixed; the fix is not in a build until:

1. all 169 staged `stage/*/scenerio.gcx` are re-appended with the new page
   (`tools/mgs3d_clean_glyph_v1.py --page glyph/pages/global_korean_page_v2/korean_page_full.bin`)
   — only the trailing 128 bytes of each file change, sizes unchanged;
2. `codec/movie/demo.dat` are rebuilt so the text encodes 감/달 as the new
   tokens.

## Separate finding, not fixed

The encoding preflight fails on **39 of 8,478 accepted codec units**: a literal
`<` in 28 rows (the documented BROKEN_TOKEN class — must be written `<3C>`),
zero-width space `U+200B` in 9, `×` in 1, `·` in 1. Those rows cannot encode and
will fall back to English. The 11 non-`<` ones are typographic noise and are a
mechanical cleanup, not translation work.
