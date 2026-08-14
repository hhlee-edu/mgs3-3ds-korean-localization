# Byte-capacity recheck against the FINAL natural translation (2026-08-14)

Analysis only. No translation text and no `.dat` file was modified.

## Purpose

The global Korean glyph page (`translation/40_build_input/global_page_v2/`)
removed per-GCX/per-record **glyph-slot** scarcity as a shortening driver
(confirmed in `docs/v0.68-release-notes.md` §3: 1,091 required glyphs, 0
missing, 29 slots free). What that does **not** remove is the separate, real
**byte** capacity of each GCX record (codec) / subtitle entry (movie, demo).
This recheck answers only that question, against the current final masters —
not any historical shortened baseline.

## Calculation basis (verified against the actual build code, not assumed)

- **codec**: `mgs3d_build.py` (`--codec-mode safe-fixed`) invokes
  `mgs3d_gcx_font_tool.py build-korean --reuse-freed-font
  --preserve-record-layout`, which calls
  `GcxRecord.replace_resources(..., preserve_layout=True)`
  (`tools/mgs3d_codec_tool.py:233-300`). Confirmed by reading the call site
  (`tools/mgs3d_gcx_font_tool.py:690-696`): `alias_adjacent`/`alias_all` are
  **not** passed by `mgs3d_build.py`, so they default `False` — no
  string-deduplication happens in the real build, matching this script's
  no-dedup assumption. Budget = `font_data_offset - string_resources_offset`,
  one pooled value shared by every resource in the GCX. Fails with
  `CodecError("replacement strings exceed fixed region by N bytes")` if the
  summed encoded length of all resources (translated + unchanged) exceeds it.
- **movie/demo**: the actual `fixed_capacity()` function in
  `tools/mgs3d_movie_tool.py`, invoked via its real `capacity` CLI subcommand
  (not reimplemented) with `--static-allocation character-map.json`. Budget is
  strictly per-entry: `len(subtitle.original) - 4 - len(subtitle.tail)`.
  Confirmed by code inspection that `rebuild_record_fixed_reclaim` (the
  `--fixed-layout-reclaim` mode) only ever grows the record's *font* table,
  never a subtitle's own *text* slot — so movie/demo REVIEW is structurally
  impossible; every non-PASS entry is MUST_SHORTEN by construction.
- **Reference binaries**: `originals/3ds_pristine/romfs/{movie,demo,codec}.dat`
  turned out to be a **different region build** than the one the master CSVs'
  offset/gcx/resource indices were captured against (movie: 558 vs 3,480
  subtitles; demo: different size entirely; codec: record count coincidentally
  matches but ~40% of resource indices are out of range). The correct
  reference — verified by **100% key overlap** (689/689 movie, 2,228/2,228
  demo offsets; 0/22,362 out-of-range codec resource refs) — is
  `experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/`. Tool:
  `tools/mgs3d_capacity_recheck.py`.

Glyph availability is reported for reference only (`missing_glyphs` /
`GLYPH_MISSING` status) and never used as a FAIL condition, per instruction.

## Results

| file | unit | total | PASS | REVIEW | MUST_SHORTEN |
|---|---|---|---|---|---|
| codec | GCX | 2,037 | 1,971 | 44 | **22** |
| movie | subtitle entry | 689 | 588 | — (n/a, no lever) | **101** |
| demo | subtitle entry | 2,228 | 1,920 | — (n/a, no lever) | **308** |

(codec "total" = GCX groups that contain at least one translated+accepted
resource, out of 2,326 GCX total; movie/demo "total" = all accepted rows in
the natural-full CSVs, matching the confirmed 689/2,228 offset sets.)

**Previously-shortened rows that can now keep the natural-level translation:**

| file | recovers |
|---|---|
| codec (rows over budget under v1, PASS under v2) | **31** |
| movie (excluded from old `movie-safe.csv`, PASS now) | **341** |
| movie (excluded from old `movie-max-safe.csv`, PASS now) | **3** |
| demo (excluded from old `demo-safe.csv`, PASS now) | **1,189** |
| demo (excluded from old `demo-max-safe.csv`, PASS now) | **59** |

This is the headline result: under the old glyph-diversity-driven selection,
1,189+341+31 ≈ **1,500+ lines** were being excluded/shortened for reasons that
no longer apply. Only the MUST_SHORTEN counts below are rows that still need
real text shortening.

## MUST_SHORTEN — the key deliverable

Full per-row/per-GCX tables (budget/used/deficit) are in
`docs/capacity-recheck-2026-08-14-report.md` (mirrors the script's stdout
report) and the raw JSON `docs/capacity-recheck-2026-08-14.json`. Highlights:

- **codec, 22 GCX**, deficits from 355 bytes (GCX 13, a 13.8 KB record) down
  to single-byte overages (e.g. GCX 106, 846, 1379, 2046, 2136, and GCX 779 —
  a 302 KB record over by exactly 1 byte). None of the 22 have any
  same-GCX donor-reclaimable bytes (`donor_reclaimable_bytes: 0` in every
  row) — reclaim cannot help any of these; they need actual text trims.
- **codec, 44 GCX classified REVIEW**: over budget, but same-GCX donor-tagged
  (`is_donor=yes`) untranslated resources have enough bytes to cover the gap
  if reclaimed (e.g. GCX 290: 38-byte deficit, 438 donor-reclaimable bytes).
  Text left untouched pending an actual reclaim decision.
- **movie, 101 entries** MUST_SHORTEN, deficits 1–14 bytes (e.g. record 92 @
  offset 193668: 14-byte overage).
- **demo, 308 entries** MUST_SHORTEN, deficits 2–35 bytes (e.g. record 236 @
  offset 485075504: 35-byte overage).

Compare to the old glyph-diversity-driven scope: codec's 22, plus movie's 101,
plus demo's 308 — **431 lines total actually need shortening**, versus roughly
10x that many previously flagged/excluded under the old glyph-count gate.

## Critical finding, out of scope but build-blocking (see below)

While cross-checking this script's formulas against the literal running build
code (not just reading it), a **separate, pre-existing bug** was found in the
codec CSV→JSON conversion step that the real `mgs3d_build.py --codec-review`
path uses. Full writeup: `docs/codec-review-csv-escaping-bug-2026-08-14.md`.
Summary: it currently corrupts/crashes on 7,369 of 7,372 accepted codec rows.
It does not affect the capacity numbers above (this script counts bytes
directly from the CSV, matching the *correct* target encoding, not the buggy
converter's output) — but it means the codec build cannot actually be run via
`--codec-review` today, independent of any capacity result. Flagging for a
decision, not fixed here.

## Files

- `tools/mgs3d_capacity_recheck.py` — the analysis script (read-only).
- `docs/capacity-recheck-2026-08-14-report.md` — full per-row Markdown tables.
- `docs/capacity-recheck-2026-08-14.json` — full machine-readable results.
