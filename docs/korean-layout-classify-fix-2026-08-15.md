# `korean_layout_classify` renderer fix (2026-08-15)

Root-caused and fixed the "characters render as blank/missing on hardware"
bug reported live during v0.69 hardware testing (9+ characters across 7+
codec lines: 듣/얼/마/임/백/업/외/워/팀, e.g. "외로워 하지마" showing as
"[blank] 하지마"). This was **not** a translation or capacity bug — every
character was already correctly present in the character-map, the resident
glyph page's bitmap data, and the built codec.dat's byte encoding. It was a
gap in the renderer patch itself.

## Root cause

`tools/mgs3d_clean_glyph_v2.py` assembles six trampoline functions from
`experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s` into a code
cave at `0x0087F8C4`, branched into from six patch sites in `code.bin`. Four
of them (`korean_draw_1/2`, `korean_width_1/2`) correctly check the
global-page token range `0x84xx-0x87xx` before falling back to the legacy
`0xA0xx-0xA3xx` static range. **`korean_layout_classify`** (call site
`0x00183A04`, entry `0x0087FA80`) never got that check — it only recognised
`0xA0xx-0xA3xx` and fell straight through to `bic r0,r1,#0x6000` for every
global-page Hangul token, returning the raw masked token instead of the
`0x8101` "this is Korean" sentinel the caller expects. Whatever downstream
layout/line-wrap decision consumes that sentinel treats an unrecognised
global-page character as not-Korean, which is what produces the blank glyph
(draw and width both still know how to *render* it correctly — this
function just never told the caller it needed to).

`korean_pre_draw` (call site `0x0015E5A4`, entry `0x0087FA58`) has the
identical structural gap, but its own fallback (`bic r1,r1,#0x6000`) turns
out to be a no-op for the entire `0x84xx-0x87xx` range (those bits are
never set there), so the token passes through this specific function
unmodified either way. **Left unpatched** — no evidence it's part of the
observed bug, and the user's instruction scoped this fix to
`korean_layout_classify` only ("이 최소 패치만"). Worth a second look if any
future report doesn't fit the pattern below.

## How it was found

1. Every hardware-reported broken character traced back to a row already
   flagged `blocker=static_glyph` / non-empty `missing_glyphs` in
   `codec.csv` — 434 accepted rows, 334 distinct characters, all stale
   metadata from before the global glyph page existed.
2. Ruled out data-layer causes by direct inspection: character-map.json
   token assignment (correct, unique), `korean_token_map_full.csv` agreement
   (exact match), `korean_page_full.bin` bitmap content (non-blank, normal),
   the actual staged `codec.dat`'s encoded bytes for GCX 28/29 (byte-exact
   correct 2-byte global-page tokens), and all 19 early-game stage
   `scenerio.gcx` files (byte-exact current resident page appended).
3. Disassembled the live, staged `exefs/code.bin` (Capstone, no symbols)
   around the documented patch points and found each one is a `b` to an
   injected trampoline in the `0x0087F8xx-0x0087FBxx` cave. Traced all six
   trampolines; `korean_layout_classify`'s was the only one missing the
   `0x84-0x87` range check, matching the shape of the fix the user's own
   (separate, symbol-aware) static trace had already converged on
   independently, down to the literal `0x8101` return value.
4. Confirmed with `experiments/2026-08-13-clean-glyph-baseline/V2-build-manifest.json`
   and `tools/mgs3d_clean_glyph_v2.py` (the tool that originally generated
   this trampoline) that the function really is named `korean_layout_classify`
   at exactly `0x00183A04` — independent confirmation from the source of
   truth, not just inference from disassembly.
5. Live GDB (Azahar, `--gdbport=24689`): unconditional breakpoints at the
   trampoline's match/fallback exits confirmed the fallback path
   (`0x0087FAAC` at the time, pre-fix) is genuinely reached during normal
   play (hit with `r1=0x8044`, an ASCII `'D'`, high byte `0x80` — outside
   both ranges, a legitimate non-bug case). Conditional breakpoints
   (`r1 in [0x8400,0x8800)`) reliably crashed the GDB client itself
   (`devkitARM gdb 14.1`, `finish_step_over` internal assertion, reproduced
   twice) before a Korean-range sample could be captured live — see the GDB
   recipe memory for this new gotcha. The static evidence from steps 1-4 is
   deterministic (there is no code path in the unpatched function that
   could handle `0x84-0x87` correctly), so the fix proceeded without that
   specific live sample.

## The fix

`experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s`:
`korean_layout_classify` now checks `0x84 <= high_byte <= 0x87` with a
nonzero low byte first (identical shape to the other four functions),
returning the same `0x8101` sentinel on match; falls through to the
unchanged legacy `0xA0-0xA3` check and `bic` fallback otherwise. Original
backed up to `poc_trampolines.s.bak-pre-layout-classify-fix`.

New tool: **`tools/mgs3d_layout_classify_fix.py`** — re-assembles the fixed
source with the same devkitARM toolchain `mgs3d_clean_glyph_v2.py` uses,
then (unlike that script, which starts from a zero cave) patches an
*already-V2* `code.bin` in place:

- refuses to run unless the input `code.bin` hashes to the exact known V2
  build (`8c542191...`) — won't silently patch an unknown base;
- verifies `korean_layout_classify`'s start address didn't move
  (`0x0087FA80` unchanged, since it's the last function before the literal
  pool and none of the five preceding functions changed size);
- disassembles and compares the five untouched functions instruction-by-
  instruction, allowing exactly one expected difference: the two
  `ldr rX,[pc,#N]` literal-pool loads inside `korean_draw_1`/`korean_draw_2`
  legitimately re-encode their offset (the shared literal pool moved 32
  bytes) but must resolve to the identical two constants — verified,
  not assumed;
- extends `exheader.bin`'s declared `.text` size by exactly the trampoline's
  growth (504 → 536 bytes) since the classifier now reaches further into
  the already-reserved zero-padded cave (no file grows; the boundary the
  loader maps as executable just moves);
- recompresses via `3dstool` (`--compress-type blz`) and verifies the
  round-trip decompresses back to the exact patched image before writing
  anything.

Result: **all 6 branch-instruction patch sites are byte-identical** to the
current V2 build (`korean_layout_classify`'s own entry point didn't move,
so nothing needed re-pointing) — this is a pure body-only, single-function
patch.

## Staged

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\`:

| file | new sha256 |
|---|---|
| `exefs/code.bin` | `7652602c4f173fdc045565577ecdd1195f529db16d5cc4c20eee2a27af7114fb` |
| `exheader.bin` | `65134e0f02331342a064468b4fcf2367c90196bfd4a8de2c10e508e257f3d62f` |

Previous (V2, pre-fix) files archived, not deleted, to
`C:\Users\hhlee\Desktop\Romforge\archive\pre-layout-classify-fix-20260815\`.
Nothing else in the RomForge tree touched this round. **No CCI built.**

## Still open

- No live GDB sample of a real `0x84-0x87` token hitting the (now-fixed)
  classifier — the static/structural proof is solid, but hardware
  confirmation on the *next* CCI build is the real test.
- `korean_pre_draw`'s identical structural gap, analysed as a likely no-op
  — flag if a future hardware report doesn't fit the "already in
  `missing_glyphs`" pattern this fix addresses.
- GDB stability: conditional breakpoints crash `devkitARM gdb 14.1` against
  this Citra/Azahar stub every time (2/2). Unconditional breakpoints work
  fine. Recorded in the GDB debugging memory — use unconditional
  breakpoints plus manual register filtering next time, not `-break-condition`.
