# HANDOFF — MGS3D Korean Glyph Integration

## v0.68 (2026-08-14) — QA pass, ETC1 history-card fix, glyph impact cleared

Full write-up: [`docs/v0.68-release-notes.md`](docs/v0.68-release-notes.md).

- **History card corruption is SOLVED.** BCLIM format 10 is **ETC1**, not the
  4-bit luminance image `mgs3d_history_texture.py` assumed — it wrote raw
  nibbles into a block-compressed slot. Format enum derived by measuring
  sibling BCLIMs (`black.bclim` was the control), storage rules confirmed by
  decoding the pristine English card back to its real sentence. New tools:
  `tools/mgs3d_bclim.py` (codec) and `tools/mgs3d_history_texture_v2.py`
  (rebuild, reusing the fixed padded-slot HPK rule). Verified end to end on a
  rebuilt archive; **not yet on hardware.**
- **Translation QA**: new `tools/mgs3d_translation_qa.py`. The handoff merge
  introduced **no regressions** (josa/pronoun/glyphcase regressions in merged
  rows: 0; control codes: 0 drift; new donor-rule violations: 0). Fixed 81 josa
  errors, 3 register clashes, 87 `당신` MT-residue rows. Remaining `당신` (41)
  are all in documented skip classes. movie/demo `당신` intentionally left —
  it is natural cutscene address, not MT residue.
- **Glyph impact cleared.** Applying the current text needed 10 syllables the
  1,120-slot page does not contain (9 introduced by direct-v2 work, 1
  pre-existing). Reworded those 10 lines instead of extending the page, so the
  existing verified glyph page covers everything: **0 missing, 29 slots free.**
  Total Korean text also shrank 3,735 characters.
- Still open and unchanged: `glyphcase` inconsistency (40 rows, needs a
  convention decision), 538 pre-existing donor-source rows carrying Korean from
  v1, and the pristine-HPK tail walk question.

## NEW — history-card glyph corruption on hardware (2026-08-14, analysis only)

**Hardware test of the packer-fixed build: crash is gone, but the opening
history card's Korean glyphs are all illegible/corrupted. Demo and other
Korean text display normally. `codec.dat` is excluded (still mid-translation,
unrelated to rendering). Not fixed — documentation and analysis only, by
instruction.**

Full analysis, evidence images and extracted BCLIM members:
[`docs/evidence/2026-08-14-history-texture-corruption/README.md`](docs/evidence/2026-08-14-history-texture-corruption/README.md).

This is a **second, independent defect** from the HPK cursor-drift crash below
— it is about pixel-data correctness inside one texture, not archive-chain
integrity, and the crash fix is unaffected and now hardware-confirmed working.
Summary:

- The user's hardware build used
  `builds/current/mgs3d-v065-hpk-cursor-fix/romfs/stage/v000a_0/cache.hpk`,
  confirmed sha256 `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`
  — the corrected archive from the RESOLVED section below. **No Data Abort.**
  That is the first hardware confirmation the cursor-drift fix works.
- `tools/mgs3d_history_texture.py`'s pixel-layout model
  (`encode_l4_bclim`/`decode_a4_bclim`: 8x8 Morton tiling, stride = declared
  width 400, 4 bits/pixel) is demonstrably wrong for this asset. Proof:
  decoding the **pristine, untouched, hardware-correct** English texture
  through this exact code produces illegible noise, under every layout
  variant tried (stride 400, stride 512, linear, linear+vflip,
  tiled+byteswap — five hypotheses, all failed).
- The payload is 16,384 bytes for a 64-row, 4bpp image, which implies 512
  texels/row, not the 400 the tool assumes — but stride 512 alone doesn't fix
  the decode either, so the defect is not simply "the width constant is
  wrong."
- The tool's own decode of its own encode looks legible — that is a false
  positive: encode and decode share the same wrong formula, so they agree
  with each other while both disagreeing with the real hardware layout.
  `wiki/History/version-0.65.md` already flagged this exact path as
  hardware-unvalidated before this session; this test is the first time it was
  actually checked, and it failed.
- The Morton/Z-order primitive itself is not the suspect — an identical
  formula is validated working elsewhere (`tools/mgs3d_gcx_font_tool.py:34-39`,
  a different 2bpp/16x16 glyph asset). The bug is specific to this L4/A4
  400x64 asset's stride/format assumptions.

**Next step (not performed):** get a hardware/emulator texture-dump ground
truth for the pristine English member (not a LayeredFS substitute image) to
read the real layout directly instead of guessing further, then re-derive
`encode_l4_bclim` from that. Full detail in the linked evidence doc.

## RESOLVED — hardware Data Abort / HPK cursor drift (2026-08-14)

**Root cause found and reproduced. Hardware-confirmed fixed (see the section
above): the corrected archive produced no Data Abort.**

Full evidence, decoded dump, disassembly and reproduction:
[`docs/evidence/2026-08-14-hpk-cursor-drift/README.md`](docs/evidence/2026-08-14-hpk-cursor-drift/README.md).
The hardware dump is committed at
`docs/evidence/2026-08-14-hpk-cursor-drift/hardware-crash-v2.dmp`
(sha256 `2840ad54c2239aa556775a2e6743db4c762b4ea3ac11f2689f69ac68ee9d0115`).

### Root cause

`tools/mgs3d_history_texture.py:105-107` rewrites the HPK header's `packed`
field to the **new, smaller** compressed length while zero-padding the physical
slot back to the **old** length:

```python
struct.pack_into("<II", hpk, offset + 4, len(patched_darc), len(packed))
hpk[start:start + old_packed_size] = packed.ljust(old_packed_size, b"\0")
```

The retail loader is strictly sequential — `pos += 12 + packed`, no seeks, no
offset table — so keeping offsets fixed *physically* does not keep them fixed
*logically*. From the patched entry onward the loader runs `old - new` bytes
early, walks the zero padding as empty 12-byte headers, and finally reads a
header straddling the last `(old - new) mod 12` padding bytes.

For v0.65 the affected entry is **entry 31, key `309d745f`** — the Cold War
history texture, the one entry that patch touches. `old_packed_size = 3884`,
`new_packed_size = 3146`, so the slot carries **738 bytes of zero padding**.

A header whose `packed` field is 0 still consumes its 12 bytes and is otherwise
skipped (`0x0014F024` → `0x0014F0BC`), so the loader eats the padding as empty
12-byte headers:

```
738 = 12 × 61 + 6
```

61 empty headers, then 6 bytes left over. The loader therefore reads entry 32's
header **6 bytes early**, from `0x494951` instead of `0x494957`, and decodes
`packed = 0x03A00EB1` (60.8 MiB). That allocation fails and returns NULL, the
NULL is not checked, and a memcpy writes to address 0 → Data Abort.

Reproduction is exact: re-running the patch on the clean archive yields sha256
`4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`, the
recorded v0.65 HPK hash, and reproduces the identical bad header offset and
`0x03A00EB1` value. No font size in the usable range yields zero padding, so
**every** archive this tool has produced is affected.

### Corrected crash facts

| | recorded 2026-08-13 | actual (dump) |
|---|---|---|
| PC | `0x00183A4C` | **`0x0018344C`** (`stmia r0!, {r3,r12}`, `r0=0`) |
| LR | `0x00165168` | **`0x00165160`** (return of `bl memcpy` at `0x0016515C`) |

`DFSR=0x805` (write, section translation fault), `FAR=0`, `r6=r8=0x03A00EB1`.
The 96-byte code dump matches the V2 build byte-for-byte at `0x001833F0`.

### Retired hypotheses — withdrawn as causes of this crash, do not resume

All five are ruled out for **this** Data Abort. None of them is re-opened by
anything in this section.

1. **`scenerio.gcx` +399 KB causing RAM exhaustion.** Not the cause. The
   oversized allocation is `0x03A00EB1` (60.8 MiB), read directly out of a
   misparsed HPK header; it has no relation to the 399 KB appended to
   `scenerio.gcx`.
2. **The Korean glyph page itself.** Not the cause. The appended page at
   `0x622DC` matches `korean_page_full.bin` and is never touched on the faulting
   path.
3. **V2 trampoline / text pointer.** Not the cause. The branch word at
   `0x00183A04` → `0x0087FA80` is intact. The 2026-08-13 "invalid text pointer
   in the trampoline path" assessment rested on the misread PC `0x00183A4C` and
   is withdrawn.
4. **Alignment.** Not the cause. HPK entries are tightly packed at arbitrary
   (often odd) offsets by design; entry 31's header sits at `0x493A1F` and the
   chain is byte-exact. No alignment rule is violated.
5. **HPK loader header/cursor arithmetic error.** Not the cause. The loader is
   correct: `0x0014F00C` always requests 12, `0x00165110` advances
   `[stream+0x0C]` by exactly the bytes copied, and all four read paths in
   `0x00164774` consume exactly `packed`. The only sub-request advance is the
   EOF path (`0x001651A4`), which did not apply. **The cursor never lost 6
   bytes — the archive handed the loader a size that disagreed with its own
   physical layout.**

Two further notes:

- The requested dynamic Azahar/GDB cursor observation is **complete/unnecessary**
  — the hardware dump already contained the value it was meant to capture
  (`[stream+0x0C] = 0x1495D` → absolute `0x49495D`). Do not restart that session.
- The `0x001648DC` missing NULL check is **not** the fix. Recorded as a
  diagnostic-only candidate: adding it would convert the crash into silent
  asset loss and hide the real defect. Do not apply it as a solution.

### Packer fix — DONE (2026-08-14)

`tools/mgs3d_history_texture.py` now leaves the entry header untouched and pads
the zlib stream back up to the original `packed_size`, matching the pattern in
`tools/mgs3d_hpk_static_korean.py:120-125`. The logical chain and the physical
layout agree again. Two self-checks were added that abort the patch if the
header ever changes or if the padded slot fails to decompress, plus a comment
naming this crash so the size field is not "optimised" back in.

The fix was verified by building a corrected archive from the clean source. That
archive was **not** left staged — build preparation is the user's step. Rebuild
it during build prep with the tool's normal entry point, using the clean
`cache.hpk` as source and `malgun.ttf` size 12:

- expected sha256 `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`
- expected size 6,453,287 bytes (unchanged from the clean archive)
- for reference, the defective build was `49447057…`; anything producing that
  hash again means the fix was lost

Verification performed on that build:

- Header at `0x493A1F` byte-identical to the clean archive
  (`key 309d745f`, unpacked 18856, packed 3884); file size unchanged.
- Every byte outside entry 31's payload slot byte-identical to the clean archive.
- Slot decompresses to 18856 bytes; the DARC keeps all 7 members with an
  identical member table, and exactly one member's bytes differ —
  `timg/cold_war_text_eng_alp_ovl.bclim`, the intended target.
- `tools/mgs3d_hpk_chain_check.py` exits 0, and `--reference` against the clean
  archive reports all 133 walked entries identical.
- The defective `49447057…` archive is **not present anywhere on this machine**;
  nothing on disk needs to be purged.

Residual assumption: the game's inflate ignores the 738 trailing zero bytes in
the slot. This is standard zlib behaviour and is the same assumption
`mgs3d_hpk_static_korean.py` has always relied on, but it has not been
re-confirmed on hardware for this specific entry.

### Second hardware crash (Luma dump 00000002) — same defect, fix was not in the build

A second physical crash was captured after the packer fix landed in the
repository. It is **not a new failure**: the dump differs from the first in 8
bytes total (`fpinst`/`fpinst2` dead FPU state and two stack bytes). Every
meaningful value is identical, including the stream state
(`cursor=0x1495D`, absolute `0x49495D`) and `r6=r8=0x03A00EB1`.

That cursor is only reachable from an archive whose entry 31 declares a short
`packed` size, so the CCI that crashed **still contained the defective
`cache.hpk`**. The fix was never in that build — most likely the previously
staged archive was reused rather than regenerated.

**Trap to avoid:** the corrected archive is the *same size* as the defective one
(6,453,287 bytes). Size cannot tell them apart. Compare SHA-256 or run the gate.

| archive | sha256 |
|---|---|
| defective | `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d` |
| corrected | `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc` |

### Crash-fix hardware validation — DONE

The corrected `cache.hpk` (`d46373e1...`) was built, staged at the canonical
RomForge path, packed into a CCI, and tested on real hardware: **no Data
Abort.** This closes out the cursor-drift crash end to end. What remains open
from that work is only the low-priority pristine-HPK-tail TODO below, which
was already known not to block anything.

### Next task — top priority

**Investigate the history-card glyph corruption** found by that same hardware
test — see the `NEW` section at the top of this file and
[`docs/evidence/2026-08-14-history-texture-corruption/README.md`](docs/evidence/2026-08-14-history-texture-corruption/README.md).
Per instruction this session was documentation/analysis only; the actual fix
has not been attempted. Recommended starting point: get a hardware/emulator
texture-dump ground truth for the pristine English member instead of guessing
more layout variants (five were already tried and failed).

No CCI has been built and no game binary has been modified as part of *this*
history-texture investigation.

### Low-priority TODO — pristine HPK tail is not fully modelled

Recorded, deliberately not investigated:

- The pristine retail `cache.hpk` is **also** not fully walkable to EOF under
  the current sequential HPK model. The walk stops around key `3e6af67a`, whose
  `packed` field reads `0xbf1d1192`.
- So there is a later archive structure that `tools/mgs3d_hpk_chain_check.py`
  does not yet explain.
- It occurs in the **unmodified retail file**, so it is not connected to the
  Korean patch work and not connected to this crash.
- It is a separate problem from the entry 31 (`309d745f`) → entry 32 failure
  documented above.
- It does **not** block the packer fix or the rebuild.
- Do not investigate it now.
- `mgs3d_hpk_chain_check.py` must keep reporting this tail condition as a
  **NOTE, not a FAIL** — otherwise the gate would reject known-good archives.
  Only the padded-slot signature is a FAIL.

### Canonical RomForge staging correction (2026-08-14)

The only canonical RomForge output root is:

`C:\Users\hhlee\Desktop\Romforge\output`

Do not use `C:\Users\hhlee\Desktop\metagear3d\romforge\output`. That parallel
tree caused the corrected HPK to be staged in one location while a CCI was
packed from another. The repeated hardware crash was a build-lineage failure,
not a new crash mechanism.

Current canonical staging file:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\stage\v000a_0\cache.hpk`

- SHA-256: `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`
- chain checker: exit 0, `OK: no padded-slot drift` (the known pristine-tail
  condition remains a NOTE)

Before the next CCI is created, re-run the chain checker and SHA-256 on that
exact path. After creation, extract the CCI and verify that its internal
`stage/v000a_0/cache.hpk` has the same corrected SHA-256. Do not promote to
v0.67 until the hardware result is reported.

Output cleanup: only `unpacked/` remains directly under the canonical output
root. Other backup/experiment folders were moved without deletion to
`C:\Users\hhlee\Desktop\Romforge\archive\output-20260814`. The
seven-underscore CCI was extracted and identified as the controlled
`ABC 호프번 XYZ` probe, not the golden build, and moved to
`output-20260814\cci-abc-hofbeon-probe`.

The canonical unpacked tree is now the v0.67 hardware candidate staging:

- V2 `code.bin`: `8c542191bdc62dffbd851d730dac14bc4dcf14208e54b4d15dbd409c885da7d0`
- V2 exheader: `2268b757185418b3c2c334048fc6b8bbdfcc9508786e06c126707b12522ce1ab`
- v0.65 `codec.dat`: `86cc8e12504e517fd0916de95e3f7a46b7f00b9c6859c28338d187334493c524`
- v0.65 `movie.dat`: `0f7e4c961ca4d10c19a46a7076ca0155a0531ed8b10f1a54b62d382a957945dd`
- probe-free `v000a_0/scenerio.gcx`:
  `badca5afc7e1a372b43cf1d60366732d229d3623f92ce1d525ddd8a097f0354d`
- corrected `v000a_0/cache.hpk`:
  `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`

## movie/demo autonomous batch cleanup (2026-08-14) — converged, done

User stepped out and asked for autonomous batch processing ("외출할거니 일괄
처리해둬"). Ran the contamination hunt to convergence using three methods
(length-ratio z-score at progressively lower thresholds, duplicate-korean-text
scan, and manual context reads of everything adjacent to a confirmed defect),
verifying every candidate against context before fixing, same precondition-
check-then-apply discipline as before.

- **movie: confirmed fully clean.** Re-scanned down to `|z|≥2.0` (37
  candidates) — 0 additional real defects; all were legitimate EN→KO
  word-order splits or natural short-answer expansion. No more edits needed.
- **demo: 46 more rows fixed this session** (3 from a duplicate-text re-scan,
  24 from a `2.0≤|z|<3.0` sweep, 19 from tracing what that sweep's
  re-verification surfaced) — cumulative **115 demo rows fixed today**
  across all rounds. `|z|≥3.0` still reports 55 candidates, but the top ones
  are all reverified as correct; diminishing returns reached (variance keeps
  shrinking each round, so previously-normal rows keep looking like new
  outliers). Judgment call: stopped here rather than chasing an
  ever-lower threshold.
- Full tables and the explicit stopping-point reasoning:
  `translation/10_master/movie-demo-batch-cleanup-2026-08-14.md`.
- Final hashes: `movie_natural_full.csv`
  `a022c716c9b4c047c3c19505e2ba54e328479a233c63aa45a816bc9ee15b4da9`
  (unchanged this session), `demo_natural_full.csv`
  `d386d0b189234ccea8d9dfb1083c005691307d6b66301916f81c12f769a4326e`.
- **Caveat that still stands**: this method catches "a whole other scene's
  line landed here" contamination, not subtler mistranslation/register issues
  of similar length. Don't read "converged" as "movie/demo translation is
  fully verified" — only that this specific contamination pattern is
  exhausted to the point of steep diminishing returns.

## movie/demo full trace-and-fix (2026-08-14) — done, 70 rows fixed total

Follow-up to the light audit below, per explicit instruction ("수정해줘" →
"하나씩 추적 수정" — fix them, tracing each one individually). All 75
candidates from the light audit (movie 7 + demo 75, movie's first 3 clusters
already fixed there) were traced one at a time against surrounding rows before
touching anything.

- **movie: 5/7 remaining candidates were false positives** (legitimate EN→KO
  word-order reordering split across two subtitle cards, not contamination).
  2 were real and fixed (`1590`, `1600`).
- **demo: 17/75 were false positives**, same reordering pattern or a
  proper-noun the checker's name list didn't recognize. **58 were real
  contamination** (korean holding a different scene's dialogue entirely) —
  fixed, plus 4 more cells in the same off-by-one shift chains that weren't
  individually flagged but were clearly part of the confirmed defect (verified
  the same way movie's rec-92 cluster was: two demo copies of that exact scene,
  rec 275 and rec 305, had the identical shift). 62 demo cells changed total.
- Every change was precondition-checked (script aborts if the file's current
  value doesn't match what was traced) before writing, and structurally
  verified after (0 non-korean-column diffs, row counts unchanged).
- Full before/after tables and confidence caveats:
  `translation/10_master/movie-demo-full-trace-fix-2026-08-14.md`.
- **Round 2 (same session, user said "다음"):** 7 more contaminated cells
  noticed by eye while reading context (not from a systematic rescan) — demo
  idx 2759, 3026, 3031, 5196, 6856, 8847, 8852 — traced and fixed the same way.
  demo final sha256 `d1336a1857c7ebfcb9a34b34a83f709eec0f9082bd93af01d0c2c49c5371a523`.
  These were spotted incidentally, not via a full rescan, so more of the same
  contamination likely remains undiscovered in movie/demo.

## movie/demo full light audit (2026-08-14) — movie fixed, demo scoped out

Full statistical scan (length-ratio z-score + missing-proper-noun heuristics)
across all 2,917 movie+demo rows, per user request ("전체 검수, 비교적 가볍게").
Confirms the cross-scene contamination flagged below is **not isolated** — it's
a real pattern with many instances, concentrated far more heavily in demo.dat.

- **movie: 3 cascading off-by-one shift clusters found and fixed (8 rows)** —
  traced each to its correct row using neighbouring content as ground truth,
  pre-condition-checked before writing, verified 0 non-korean-column diffs.
  4 more length-outliers checked and confirmed benign (natural EN→KO
  expansion, not contamination). 7 additional suspects found via the
  missing-proper-noun heuristic are **not yet traced/fixed** (8 others in that
  list were false positives — Khrushchev already correctly rendered as
  흐루쇼프/후르시쵸프, just missing from the checker's name dictionary).
- **demo: 27 length-outliers + 48 proper-noun-mismatch found, none fixed.**
  Confirms the two clusters found last session (rec 228-229, rec 235-236) are
  part of this same wider pattern, not separate incidents. Scale is
  meaningfully larger than movie's — tracing each would mean redoing what was
  just done for the movie clusters, dozens of times over, which exceeds
  "가볍게". Left for a scoped decision: trace-and-fix row by row like movie, or
  treat as a matching/alignment-algorithm problem to be rerun.

Full detail, tables, and the exact top demo examples:
`translation/10_master/movie-demo-light-audit-2026-08-14.md`.

## movie/demo remaining untranslated text (2026-08-14) — done, one issue flagged

Scanned `translation/10_master/bundle_natural_full/{movie,demo}_natural_full.csv`
(the movie/demo translation authority per `wiki/Translation.md`) for cells with
no Hangul at all. Most hits were correctly-English proper nouns (Snake, Boss,
EVA, Ocelot, C3...); 16 were genuine blank/placeholder defects (`.`/`...`/`!`
with the real content missing). **15 fixed directly in `demo_natural_full.csv`**
(structural diff clean: exactly 15 `korean` cells changed, no other column
touched). 1 (`movie_natural_full.csv` idx 1024) left alone — its content is
already fully present in the previous card (`idx=1019`) due to EN/KO word-order
reordering; filling it would duplicate "일주일 전". Full detail, before/after
table and reasoning: `translation/10_master/movie-demo-untranslated-2026-08-14.md`.

**Bigger issue found, not fixed, out of this task's scope:** several rows have
a `korean` value that belongs to a *different, unrelated scene* than their own
`raw_text` (not blank — wrong content). Example: demo idx 7572/7591/7601/7746/
7756/7766, movie idx 1034/1044. This looks like a 3-way alignment/matching
defect, not a missing-translation gap, and is potentially large in scope
(not yet measured). See the "별도로 발견한, 더 큰 문제" section in the doc above.

## direct-v2 Translation Quality Pass (2026-08-14)

Separate track from the glyph/hardware work below — codec.dat Korean
meaning/register quality pass, ignores byte/glyph capacity entirely (that's a
later stage). **Read `translation/10_master/direct-v2-RESUME.md` first**, not
this section, for exact resume steps; this is just a pointer.

- Batches 1-10 applied, **335/22,362 rows fixed**. Batches 1-7 (217 rows)
  were independently re-verified this session (structural diff clean, 7-entry
  changelog spot-check matched byte-for-byte).
- `direct-v2-worklist.json` (defect list) was stale and has been regenerated;
  its generator script (`worklist_build.py`) was lost from an old scratchpad —
  rewrite and commit it under `tools/` or `translation/10_master/` next time,
  don't leave it in a scratchpad again.
- **D2_missing (737 rows) is split into its own pre-processing track by user
  directive** — badly contaminated with mistagged Spanish/French donor text
  (GCX 443's entire D2_missing bucket, 49 rows, turned out to be 0% English).
  Needs GCX-level EN/FR/ES/DE/IT/unknown classification before any
  `D2_missing_en` translation starts; that classification hasn't begun.
- **Handoff file merged back — done (2026-08-14).** The full handoff CSV
  (`translation/10_master/direct-v2-FULL-HANDOFF.csv`, 1,528 data rows) came
  back with `final_korean` filled for 795 rows. **Important:** per that file's
  own `direct-v2-RESUME.md` trail, it was filled by an AI session running in a
  *different* environment (no access to this repo's v1/v2 CSV), not by an
  external human translator — that session did the fill plus three self-QA
  passes (register recheck, re-reading the 318 "no defect" D6_mix rows that
  had only been ending-checked and finding 14 more real mistranslations there,
  and a josa/particle consistency sweep after English proper nouns). This
  session verified rather than trusted that record: cross-checked specific
  logged fixes against the merged file and re-ran the known-bad-josa-pattern
  search against the 795 merged rows (0 hits; 16 remain elsewhere in the
  22,362-row file, outside this merge's scope).
  Merged into `codec-3ds-INTEGRATED-review-direct-v2.csv`: 507 rows actually
  changed, 288 rows confirmed by the translator as not actually defective
  (concentrated in D6_mix, matching the already-documented over-detection
  issue). D6_mix (487) and D3_abbrev (46) are now **fully resolved**.
  D2_missing's required GCX-level language classification is also done — all
  734 rows were individually read; 693 confirmed non-English (excluded for
  good) and 41 translated. Structural diff clean (row count/columns/keys
  unchanged, 0 non-korean-column diffs). Full tables:
  `translation/10_master/direct-v2-batch11-15-changelog.md`.
- **Remaining**: D4_mt_other (3 rows), broken_english (37, needs context
  restoration, not translation), and 16 stray josa errors found outside this
  merge's scope (locations in the changelog).

## Hardware crash investigation handoff (2026-08-13) — SUPERSEDED

> **Superseded 2026-08-14 by the RESOLVED section at the top of this file.**
> Its `PC=0x00183A4C` / `LR=0x00165168` are misreadings of `0x0018344C` /
> `0x00165160`, and its "primary suspect: Korean trampoline text pointer"
> assessment is withdrawn. The build-lineage hashes below are still correct and
> still useful, with one correction: the noted absence of the v0.65 HPK hash
> from `.tmp/cci-831-verify` is not a stray "build-lineage mismatch" — the
> crashed hardware CCI carried V2 `code.bin` **together with** the v0.65
> `cache.hpk` (`49447057…`), which is precisely the archive that crashes.
> `.tmp/cci-831-verify` is a different extraction that pairs V2 code with the
> clean HPK. Retained below for the hash record only.

Original 2026-08-13 text follows.

Hardware crash dump evidence:

- stage resource string: `stage/v000a_0/cache.hpk`
- stage identifier: `v000a_0`
- `PC=0x00183A4C` *(incorrect; actual `0x0018344C`)*
- `LR=0x00165168` *(incorrect; actual `0x00165160`)*

Read-only investigation result (no fix applied):

- The crashed CCI's ExeFS lineage is now exact. Extracting the `.code` member
  directly from `.tmp/cci-831-verify/exefs.bin` produced 5,264,416 bytes,
  SHA-256 `8c542191bdc62dffbd851d730dac14bc4dcf14208e54b4d15dbd409c885da7d0`.
  It is byte-identical to
  `experiments/2026-08-13-clean-glyph-baseline/V2-code.bin`; its decompressed
  SHA-256 is `105c8a1575dd3c0a65dc89ac6e81aa7e3eb9710f1c9449a00894cfb32cbc5ffa`.
  The CCI exheader is likewise the recorded V2 exheader (SHA-256
  `2268b757185418b3c2c334048fc6b8bbdfcc9508786e06c126707b12522ce1ab`,
  text size `0x77FABC`). All six patch words and the 504-byte trampoline hash
  `7298c10440b09e04aff1a705c1c85c0ce6895ee8ba7db4074ce4c2d1bfe4607d`
  match `V2-build-manifest.json` exactly.
- Do not use the current RomForge staging `code.bin` to interpret this crash.
  It is a later, different build: 5,264,412 bytes, SHA-256
  `de35b86eb0f6e8ef72b87faee567fb4f6aae5560307d57ae282cdf60b45f7308`,
  decompressed SHA-256
  `b2ab3030e0eb4fc3f912187a73ddf90fdf83def4bc696a116de3083a6eb35a8f`.
  Its six branch words target a different 456-byte trampoline layout and its
  exheader text size is `0x77FA8C`.
- The current extracted build at `.tmp/cci-831-verify` has a `v000a_0/cache.hpk`
  that is byte-identical to the clean glyph source: size `6,453,287`, SHA-256
  `145a82e9acba662afb024baadd0a25ec1eabca2c1006be26eb5891670561bbc0`.
  All 147 verified zlib entries have identical key order, offsets,
  packed/unpacked sizes, decompressed hashes, gaps, and effective alignment.
- `data.cnf` is unchanged. Within `v000a_0`, the localization build changed
  `scenerio.gcx`:
  - clean: 68,829 bytes, SHA-256
    `c126d93f3437715d5b834962e9e02d0d067061066202a679e2397310874aa420`
  - current: 467,420 bytes, SHA-256
    `badca5afc7e1a372b43cf1d60366732d229d3623f92ce1d525ddd8a097f0354d`
  - its original 68,829-byte prefix is intact;
  - the 65,280-byte Korean page begins at offset `402,140` (`0x622DC`) and
    matches `glyph/pages/global_korean_page_v2/korean_page_full.bin`;
  - recorded address formula: `49,884 + 0x56000 = 402,140`.
- `PC=0x00183A4C` is `ldrhhs r0, [r4]` in the text/layout decoder. A fault there
  indicates an invalid/unreadable text pointer in `r4`, not an HPK table read.
- The same function was directly modified by the Korean renderer patch at
  `0x00183A04`: the original `bic r1,r1,#0x6000` branches to the Korean token
  classifier trampoline at `0x0087FA80`. The code/scenerio glyph path is thus
  substantially more relevant than `cache.hpk`.
- `LR=0x00165168` lies in a buffer-copy loop following a call to the memcpy-like
  routine at `0x001833FC`; it does not identify an HPK loader. Do not treat the
  live LR as a reliable caller without stack unwind evidence.
- The documented v0.65 Cold War HPK hash
  `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`
  is not present in `.tmp/cci-831-verify`. Reproducing that patch changes only
  HPK key `309d745f`, keeps every entry offset fixed, and produces the recorded
  hash. This is a build-lineage mismatch, not evidence of current HPK damage.

Current assessment *(withdrawn 2026-08-14 — see the RESOLVED section)*:

1. ~~Primary suspect: invalid text pointer or pointer-advance/classification
   interaction in the `0x00183A04` Korean trampoline path.~~ Wrong; the
   trampoline is intact and uninvolved.
2. ~~Closely related changed resource: `stage/v000a_0/scenerio.gcx`.~~ Not
   involved in this crash.
3. ~~Low-priority suspect: current `cache.hpk`.~~ This was in fact the cause —
   but the v0.65 patched archive, not the clean one that was compared.
4. ~~Root cause is not proven because the full register set, fault address, and
   stack unwind were unavailable.~~ They were available all along, inside the
   crash dump; it had simply not been decoded.

Next read-only checks *(all closed 2026-08-14)*:

1. Closed: the full register set, `FAR=0`, `DFSR=0x805` and the 960-byte stack
   were decoded from the dump. `r4` is the stream object on the stack, not a
   text pointer.
2. Closed: the crashed CCI is the recorded V2 code and exheader.
3. Closed: the live LR is `0x00165160`, the return of the `bl memcpy` at
   `0x0016515C`; no unwind was needed.
4. Closed: neither `code.bin` nor `scenerio.gcx` is implicated, so no isolation
   build is required.

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
  — **DEFECTIVE, do not ship.** This is the archive that causes the hardware
  Data Abort (738 bytes of zero padding in entry 31). Must be rebuilt after the
  packer fix; see the RESOLVED section at the top.

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

- `tools/mgs3d_history_texture.py` — **contains the padded-slot defect**
- `tools/mgs3d_hpk_chain_check.py` — gate that detects it
- `tools/mgs3d_hpk_inventory.py`
- `tools/mgs3d_v065_media_fix.py`
- `tools/mgs3d_restore_gcx.py`
- [Version 0.65 checkpoint](wiki/History/version-0.65.md)

## Current Goal

Continue canonical translation integration using the append-only 929-character
global map plus the exact 191-character shared-static allocation.

## V2 HPK Cursor Drift Investigation (2026-08-14) — CLOSED

> **Closed the same day. See the RESOLVED section at the top of this file.**
> Every confirmed observation below held up, including the six-byte drift and
> the `0x00494951` header offset. The open question — where the cursor lost six
> bytes — is answered: it did not. The header read always consumes 12, and
> `0x00165110` has no under-advance path outside EOF. The six bytes are the
> residue (`738 mod 12`) of zero padding written into entry 31's slot by
> `tools/mgs3d_history_texture.py`, which the loader consumed as 61 empty
> headers. The three requested dynamic observations are moot; the dump already
> held the cursor value. Retained below for the static-analysis record.

Scope is the initial V2 crash build only. Its `code.bin` SHA-256 is
`8C542191BDC62DFFBD851D730DAC14BC4DCF14208E54B4D15DBD409C885DA7D0`
(504-byte trampoline; six V2-manifest patches). Do not substitute the current
RomForge `DE35B86E...7308` build.

Confirmed from the hardware dump:

- The physical 3DS produced the `PC=0x0018344C` Data Abort (`FAR=0`). This is
  not an Azahar crash or emulator result.
- That hardware Data Abort ultimately parsed the next HPK header from absolute offset
  `0x00494951`; the 12 bytes there decode the third word as `0x03A00EB1`.
- The valid next header starts at `0x00494957`, exactly six bytes later, and is
  `f642b10e a0030000 5a010000`.
- The resulting `0x03A00EB1` allocation request is downstream evidence of the
  misaligned header, not the current root-cause target.
- Previous entry 31 is key `309d745f`, header offset `0x00493A1F`, unpacked
  size `0x49A8`, and packed size `0x0F2C`. Its zlib stream consumes all 3884
  packed bytes; do not re-investigate zlib consumption.

Static initial-V2 loader path:

- `0x0014F018 -> 0x00165110` reads the complete 12-byte HPK header.
- `0x0014F02C` loads `packed_size`; `0x00164780` retains it in `r6`.
- `0x001648F4` requests exactly `r6` bytes from the stream.
- `0x00165198 add r1,r1,r6` / `0x0016519C str r1,[r4,#0xC]` is the local
  cursor update. The expected calculation is
  `0x00493A1F + 0x0C + 0x0F2C = 0x00494957`.
- No explicit `-6` cursor/seek arithmetic was found in the restricted static
  path. Crucially, the value written at `0x0016519C` has **not** been observed
  dynamically; `0x00494957` there remains a static inference.

Only next diagnostic requested:

Observe these three values dynamically in the initial V2 crash CCI while entry
31 is processed, and stop:

1. Immediately before entry 31: stream absolute cursor at `0x0014F018`;
   expected `0x00493A1F`.
2. Immediately after `0x0016519C`: stream absolute cursor; expected
   `0x00494957`.
3. Immediately before entry 32 header read at `0x0014F018`: expected
   `0x00494957`.

The first appearance of `0x00494951` is the only desired result. Do not expand
static analysis, patch the 60.8 MiB request, shrink the `0x80000` buffer, remove
cache resources, modify binaries, or build another CCI.

Dynamic attempt status:

- A fresh Azahar/GDB session accepted both breakpoints, but the target
  `v000a_0` entry path was not reached within the short observation window, so
  none of the three values was captured.
- Azahar was used only for an attempted dynamic observation; it did not produce
  the original Data Abort or the `0x03A00EB1` value.
- Earlier Azahar debugging attempts showed a debugger breakpoint-cache/assertion
  problem. This assertion is separate from the physical-device crash. Do not
  spend time repeatedly repairing that environment. The last attempt was
  stopped cleanly and Azahar configuration was restored byte-for-byte (backup
  SHA-256 `55593EF2FF4DEF10FE91A10B71BF5EFA10A3E9B0AC9BECF0E582B5E3085AEBD7`).

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

**Superseded — the packer fix landed and was hardware-tested (see the RESOLVED
and Canonical RomForge sections above).** No Data Abort on hardware. Current
top task is the NEW section at the top of this file: the history card renders
but its glyphs are corrupted, which is an unrelated pixel-layout bug in the
same tool. Analysis only has been done so far; the fix has not been attempted.

Do not rebuild the old `demo.dat` history-subtitle probe; it targeted the first
spoken demo line and was the wrong resource.

## Cautions

- Do not overwrite `translation/10_master/` with encoded or shortened data.
- Do not include the controlled `ABC 호프번 XYZ` movie probe in clean builds.
- Do not resume exhaustive GDB traversal, save manipulation, cheats or
  equipment preparation.
- Do not generalize the three-stage runtime sample to all 169 stages.

## Key Artifacts

- `docs/evidence/2026-08-14-hpk-cursor-drift/` (tracked: hardware dumps + full
  crash analysis; note `experiments/` is gitignored, so irreplaceable primary
  evidence belongs here instead)
- `docs/evidence/2026-08-14-history-texture-corruption/` (tracked: extracted
  BCLIM members + decode attempts for the glyph-corruption analysis above)
- `experiments/2026-08-13-clean-glyph-baseline/clean-build-manifest.json`
- `experiments/2026-08-13-clean-glyph-baseline/runtime-verification.txt`
- `experiments/2026-08-13-clean-glyph-baseline/full-page-rebuild-audit/full-928-validation.json`
- `experiments/global_korean_page_build_2026-08-12/korean_token_map_full.csv`
- `translation/40_build_input/global_page_v2/`
- `glyph/validation/global_page_v2/` (15 labelled review sheets)
- `experiments/2026-08-13-clean-glyph-baseline/media-candidate-manifest.json`
