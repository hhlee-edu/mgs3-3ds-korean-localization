# Session handoff — 2026-08-08

Canonical summary is `docs/WIKI.md` (updated alongside this doc). This file
is the narrative record of what happened this session, in order.

## 1. movie/demo 3-way matching rebuild (WIKI 4.9)

`tools/mgs3d_script_compare.py`'s `align-dat` + `merge-dat-korean` pipeline
(built 07-31/08-01 for codec, also usable for movie/demo) was already the
"3-way match" the plan called for — it just needed re-running against the
*current* record parser instead of stale 558/2091-entry offsets. Re-ran it:

- Re-verified via `mgs3d_movie_tool.py inspect` on live files: movie is
  108 records/3,480 entries (matches prior docs); demo is actually
  **333 records/11,296 entries**, not 2,091 as WIKI previously said — that
  was a stale/wrong note, not file corruption (confirmed by parsing both
  live and the golden baseline, identical structure). English-card counts
  (movie 689, demo 2,250) were already correct.
- Match result: movie 27→**235**/689 cards got a Korean candidate, demo
  372→**935**/2,250 — because `align-dat` anchors on shared
  names/numbers + same-record context, not literal string equality.
- Outputs: `analysis/ps2_korean/full_build/_scratch/3way/`.

## 2. Shinsnote color classification (WIKI 4.10)

User provided a finer scrape (`신스노트 대사집/shinsnote_mgs3_full.json`,
20 pages, ~9,700 span-level segments) that preserves the original blog's
box background color — gray = cutscene ("movie_demo"), green = radio
("codec"). Wrote `tools/mgs3d_shinsnote_classify.py` to reconstruct
paragraph-level dialogue (reusing `mgs3d_script_compare.extract_page`'s
heading/blockquote logic) and tag each line by nearest reference color
(Euclidean distance — an early version's per-channel tolerance was too
loose and let white/green both register as gray; fixed by tightening to
10 and picking the closer reference). Validated: still exactly 3,031
dialogue lines. Breakdown: movie_demo 933, codec 406, unknown 1,692.

Cross-checked against §1's match results: **~9% of both movie and demo's
matched candidates were actually codec-colored (radio) lines matched into
movie/demo cards by mistake** (movie 22/235, demo 88/935) — anchor
matching false positives, invisible without this color signal.

**Fix applied and re-run**: rebuilt the GameFAQs↔Shinsnote bilingual
alignment restricted to non-codec-colored lines only
(`analysis/shinsnote_mgs3_movie_demo_only.json` → `align-bilingual` →
`merge-dat-korean` again), producing v2 results:
- movie 236/689, demo 949/2,250 matched — same or better coverage
- color-mismatch dropped from 110 rows to 2 harmless edge cases (same
  short phrase appearing in both a codec- and movie_demo-colored box on
  different pages)

Outputs: `movie_korean_comparison_v2.csv` /
`demo_korean_comparison_v2.csv` in the same `_scratch/3way/` folder.

**Review pages** (offline HTML, `mgs3d_review_html.py`):
- `analysis/html/movie_demo/needs_review_v2.html` — 2,403 rows
  (movie 524 + demo 1,879) excluding the 536 color-confirmed rows,
  covering everything from color-flagged mismatches to blank/no-candidate
  cards. **This is the primary open task** — human review, not yet done
  beyond the exploratory work in this session.
- Reference corpus for filling blanks: `analysis/shinsnote_mgs3_classified.csv`.

## 3. codec.dat donor-reclaim rebuild — deployed to live

Re-ran the established pipeline (`docs/WIKI.md` §2.1) against the current
live `codec.dat` (base) and current master CSV (7,339 candidates, all
clean). Selected 2,035/7,339 (fewer than the 8/5 build's 2,149 because the
live file has already spent much of its donor budget — expected, not a
regression). **Caveat**: this was a plain 2-flag rerun; per
[[project-mgs3d-donor-reclaim-build]] memory, that's known to under-count
vs. the true production flags (`--donor-report`/`--alias-savings-report`,
never located). Verified via direct resource-level byte diff against the
pre-build backup that all changes were either the intended
translation/donor targets or benign padding-length adjustments — **no
existing translation was lost**, this is a pure net addition
(533 GCX touched, 8,070 new Hangul glyphs). Backed up first
(`C:\Users\hhlee\Desktop\Romforge\backups\codec_2026-08-08_pre-rebuild.dat`,
SHA-256 `E55644C7...`). New live SHA-256: `19FF34D1...`.

Not yet runtime-verified on hardware/Citra.

## 4. `--grow-records` investigation — the session's main open thread

User asked to determine, with real evidence (not speculation), what needs
fixing to make record growth safe, since it previously caused a real
hardware freeze (`docs/ps2-port-handoff-2026-08-03.md` §5.2: demo.dat
+164,496 bytes across 457 rows → first video doesn't play, hangs).

### 4.1 Ruled out
- **Alignment**: checked every record's start offset against
  0x10/0x20/0x80/0x200/0x800/0x1000. Only 0x10 is universal; everything
  else matches random-chance distribution. No hidden alignment
  requirement beyond what the tool already assumes.
- **Internal absolute-offset table inside the DAT itself**: discovered
  the previously-opaque `gap_before` regions between records (safely
  round-tripped byte-for-byte but never parsed) actually contain
  structured sub-blocks with their own `kind`/`size` headers (e.g.
  `kind=2, size=848` immediately before demo record 1, containing
  float-like data — likely camera/timing metadata, still undeciphered).
  Scanned all of demo.dat's gaps + prefix + suffix (~770MB) for any
  4-byte-aligned value matching one of the 333 known record offsets:
  only 16 scattered hits across ~192M positions — consistent with random
  chance, not a real table. This hypothesis is not supported by evidence.
- **code.bin filename strings**: searched the 5.26MB ExeFS `code.bin` for
  literal `"movie.dat"`/`"demo.dat"` — zero hits (expected; resources are
  presumably referenced by index/hash, not path string).
- Tasks #7 (RomFS file scan for offset references) and #8 (code.bin
  constant search) were started but not completed — file listing done,
  no scan run yet.

### 4.2 Controlled growth experiments (the actual answer)

Built `tools/../rebuild_2026-08-08/build_grow_experiments.py`: grows a
record by appending N zero bytes strictly after its font block (confirmed
pre-existing zero padding there, never touching real content) and bumping
its declared size field. All built from the live/backup file, verified by
re-parsing before deployment.

**On movie.dat** (108 records, small/fast to iterate), user tested each
build in Citra:
| Experiment | Change | Result |
|---|---|---|
| A | last record (107) +16B | OK |
| B | middle record (54) +16B, cascades +16 to all later records | OK (confirmed by watching, not skipping, through to record 54's scene) |
| C | record 1 -32B / record 2 +32B, **total file size unchanged** | OK |
| scale +32,000B (14%) on record 54 | OK |
| scale +164,496B (72%, same magnitude as the historical demo.dat failure) on record 54 | **OK** |

Conclusion: movie.dat tolerates growth, cascading position shifts, and
even the exact historical failure magnitude, when concentrated in one
record. This ruled out "any growth is unsafe" and "that specific byte
magnitude is unsafe" as general rules.

**On demo.dat**, targeting record 287 (the user confirmed this — not
record 0 — is the *actual* first video shown at boot; it contains the
"Flying over Pakistan..." line, `analysis/gamefaqs_mgs3_english.json`
sequence 0-ish):

- `--size-neutral-reclaim` build with a real one-line Korean translation
  ("파키스탄 상공") at that exact offset: succeeded, displayed correctly,
  no growth (donor-reclaim within the record, same as codec's mechanism).
- `--grow-records` build with the same real translation (+352 bytes,
  record grows, 45 subsequent records shift): **succeeded, displayed
  "파키스탄 상공" correctly on real content, at the exact historical
  crash location.**
- Scale series (pure zero-padding grown on record 287, same method as
  movie.dat's scale tests), binary-searched:

| Delta | Result |
|---|---|
| +352B (real translation, not padding) | OK |
| +2,000B | OK |
| +3,008B | **OK** |
| +4,000B | **broken** — not a hang; video starts, then visible object/graphics corruption, audio keeps playing |
| +8,000B | broken (same symptom) |
| +16,000B | broken (same symptom) |
| +32,000B | broken (same symptom); confirmed skipping past it lets the *next* video and the movie.dat handoff play fine — corruption is localized to the oversized record, not cascading |
| +164,496B (exact historical magnitude, file size now matches the old failed test's 773,100,176 bytes exactly) | broken (same symptom) |

**Current known threshold: between +3,008 and +4,000 bytes for demo
record 287** (original size 2,064B → roughly 5,072-6,064B ceiling before
breaking). Not yet narrowed further — session ended here (user had to
step away).

**Important distinction from the original failure mode**: the *symptom*
here (partial video corruption, audio continues, only the oversized
record's playback is affected) is different from the original historical
failure (nothing plays at all, hangs immediately). This suggests **two
separate limits**, not one:
1. A per-record maximum size ceiling (newly found, ~3-4KB region for
   demo record 287 specifically) — likely a fixed-size streaming/decode
   buffer sized for the format's normal ~2KB record size, overflowing
   when one record balloons to an unusually large size.
2. Whatever caused the *original* complete-hang failure (457 records
   modified simultaneously, average growth only ~360B/record — well
   within the newly-found per-record ceiling). Not yet reproduced by any
   experiment this session, since every test so far grew exactly one
   record. **Not yet tested: growing many records simultaneously by
   modest amounts**, which is what actually failed historically.

### 4.3 Next steps (not started)
- Narrow the demo record-287 threshold further (try +3,500 or similar
  between 3,008 and 4,000).
- Test whether the threshold is specific to record 287 or a general
  per-record ceiling (repeat the scale series on a different demo record).
- **Reproduce the original failure mode directly**: grow many records
  simultaneously by modest per-record amounts (mirroring the historical
  457-row/164,496-byte-total test), now that "one record, any reasonable
  size" is confirmed safe — this isolates whether the real problem is
  specifically about *simultaneous multi-record* changes (an index/table
  that only breaks when many things move at once) as opposed to a
  per-record size cap.
- Resume tasks #7/#8 (RomFS/code.bin scanning) if the multi-record test
  doesn't explain it either.

## 5. Housekeeping for next session
- Live `movie.dat`/`demo.dat` were restored to their pre-experiment
  states before ending this session (SHA-256 `1244B124...` /
  `D3437249...` respectively) — nothing experimental is left live.
  `codec.dat`'s rebuild (§3) *is* live and intentional.
- Backups from today: `C:\Users\hhlee\Desktop\Romforge\backups\
  {codec,movie,demo}_2026-08-08_pre-*.dat`.
- Noticed but not cleaned up: `movie.dat.bak-before-record0-2-3-5-12-28-29-2026-08-07`
  and `demo.dat.bak-before-autofit106-2026-08-07` are still sitting inside
  the live unpacked romfs tree — violates the established romfs-hygiene
  rule (repack bundles the whole folder). Should be moved out before the
  next CCI pack.
- All experiment build scripts and output `.dat` files are under
  `analysis/ps2_korean/full_build/rebuild_2026-08-08/` (gitignored, local
  only).
