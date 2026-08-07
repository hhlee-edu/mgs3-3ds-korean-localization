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

## 4.4 Follow-up while user stepped away: full-scale builds + codec capacity

**movie.dat, full `--grow-records` build (all 236 v2-matched candidates,
229 after removing 7 rows with characters the tool's font-mapper doesn't
support — stray jamo/curly quotes, same known bug as before)**: 229/229
selected, file grows 229,376 → 454,800 bytes (+98.3%). Not yet tested —
this is the first build that grows *many* records simultaneously (unlike
today's single-record experiments), the closest thing yet to the original
failure's structural shape. `rebuild_2026-08-08/movie_full_grow.dat`.

**demo.dat, full `--grow-records` build (949 v2-matched candidates, 913
after the same character filtering)**: 913/913 selected, 259/333 records
changed size, file grows 772,935,680 → 773,594,896 bytes (+0.085%,
659,216 bytes total — actually *larger* in absolute bytes than the
original failing test's +164,496, but spread differently). **This is the
most direct available replication of the original failure's pattern**
(many records, real content, simultaneous growth) — testing this is the
top priority for next session. `rebuild_2026-08-08/demo_full_grow.dat`.

**codec.dat capacity analysis (not deployed, not safety-validated)**:
tried `mgs3d_gcx_font_tool.py build-korean` with all 7,339 candidates in
growth mode (`--preserve-total-file-size`, then unrestricted):
- **Hard ceiling found, independent of growth**: GCX 243 needs 567
  appended glyphs but only 434 slots remain; GCX 443 needs 576 but only
  444 remain. This is a fixed per-GCX custom-glyph address-space limit
  (not a byte-budget problem like movie/demo) — growth cannot fix it,
  full stop. These are the same two GCX noted in `session-handoff-2026-08-05.md`
  as the largest all-donor-fit cases (443: 538/538, 243: 332/332) — they're
  already near their ceiling from prior successful work.
- Excluding those two, **unrestricted growth fits essentially all
  remaining 6,469 candidates** (1,675 GCX touched, 71,180 new glyphs —
  8.8x today's live 8,070) but requires codec.dat to grow by
  **4,381,344 bytes (+6.52%)**, 67,204,976 → 71,586,320.
  `rebuild_2026-08-08/codec_full_grow_unrestricted.dat`.
- **This directly conflicts with the project's absolute rule** ("codec.dat/
  movie.dat/demo.dat original file size never changes") and, critically,
  **codec.dat's grow-safety has not been tested at all** — every
  experiment in §4.2 validated movie.dat/demo.dat's record format
  specifically; codec.dat is a structurally different GCX/MT-Framework
  container that could have entirely different (or no) external-reference
  fragility. **Do not deploy or attempt to pack this without the same
  kind of staged, hardware-verified validation movie/demo went through.**

## 4.5 Decisive result: demo.dat tolerates exactly ONE grown record, never two

Deployed `demo_full_grow.dat` (§4.4, 913 candidates/259 records) live and
had the user test it: **first video failed to show — reproduced the
original historical failure exactly.** This is the first time any
experiment this session reproduced that symptom.

Binary-searched the record *count* (not size) from there, rebuilding with
progressively fewer simultaneously-touched records each time, real user
test after each deploy:

| Records touched simultaneously | Result |
|---|---|
| 259 | fail (first video doesn't show) |
| 130 | fail |
| 66 | fail |
| 34 | fail |
| 18 | fail |
| 6 | fail |
| 2 (adjacent: 287, 288) | fail |
| 2 (far apart: 50, 287) | fail — rules out adjacency as the cause |
| 1 (any single record, any size up to 164,496B — §4.2) | **always OK** |

**Conclusion: the count of simultaneously-modified records is the entire
story.** Exactly one modified record, of essentially any size, works
every time. Two or more, regardless of which records or how far apart,
fails every time — and it fails at the very first video even when neither
modified record is record 287 itself is the sole determinant (the
50+287 test modified a record nowhere near what's shown first, and it
still broke the first video) — meaning **whatever breaks is evaluated
globally/early** (e.g. at file-open time), not "when a specific broken
record is reached." This is consistent with the earlier finding that
`gap_before` regions contain undeciphered `kind=2` structured data
(possibly a global table built once, at mastering time, that tolerates
exactly one known deviation but no more — speculative, not confirmed).

**Practical implication — this makes `--grow-records` nearly useless at
scale**: only one line, anywhere in the whole file, can ever be added
via growth. Bulk translation needs to stay on the existing safe route
(`--size-neutral-reclaim` / donor-language reclaim within each record's
own original size), same as codec. Growth is now understood well enough
to be *usable* (e.g. one specific high-value line that has zero donor
headroom could be grown safely) but not a general capacity strategy.

Live demo.dat was restored to its pre-experiment state
(SHA-256 `D3437249...`) after this test. Not yet tested: whether movie.dat
has the exact same "1 record only" ceiling (the full 229-record movie
build was deployed together with demo's failing build, so it's unknown
whether movie.dat *alone* would have failed the same way — worth an
isolated test).

## 4.6 codec.dat growth: also multi-GCX-fragile, unlike movie.dat

With demo.dat's "exactly one, never two" record ceiling established
(§4.5), tested codec.dat the same careful way — small first:
- **GCX 1044 alone** (8 units, +4,768 bytes, 76 new glyphs): built,
  deployed, user tested by making codec calls near the target content —
  **radio calls worked normally, no crash.** Single-GCX growth is safe,
  consistent with movie.dat's behavior.
- **22 GCX simultaneously** (backpack-related content across GCX
  21/22/61-68/217-220/269/314/452-454/457/642/1248/1356 — chosen because
  the user can reach and test that scene directly; excludes GCX 243/443
  which are separately blocked by the glyph-slot ceiling, §4.4; 80 units,
  +56,480 bytes, 899 new glyphs): built, deployed, user tested — **the
  game crashed with an error on the very first radio call** (harder
  failure than demo.dat's silent hang).

**codec.dat behaves like demo.dat, not movie.dat**: single-target growth
is safe, but growing multiple GCX at once breaks something. Not yet
bisected on GCX *count* the way demo.dat was (§4.5's exact threshold
search) — that's the natural next step if this is worth pursuing further,
though testing is harder for codec than movie.dat since there's no
easy "just watch the story play through" verification path (codec calls
are player-triggered and hard to target a specific GCX in-game).

Live codec.dat was restored to the safe donor-reclaim build
(SHA-256 `19FF34D1...`) after this test.

## 4.7 Decisive isolation: it's not about record content at all

Designed a test to separate "does a *subtitle record* changing break it"
from "does *any* absolute-position discontinuity break it, regardless of
cause": rebuilt demo.dat touching **zero subtitle/font content in any
record** — just appended 2,000 zero bytes into two records' `gap_before`
(the previously-opaque inter-record padding, before records 50 and 287),
leaving every record's own header/text/font byte-for-byte identical to
the original. This still shifts every record from 50 onward by 2,000
bytes and everything from 287 onward by another 2,000.

**Result: first video still fails to show, identically to every other
2+-point test.** This conclusively rules out anything about the *modified
record's own content* (translation text, glyph count, encoding) as the
cause — no record content changed at all here. **The failure is purely a
function of how many points in the file have shifted from their original
absolute position, full stop.** This is about as strong as evidence gets
for a pre-built, mastering-time-fixed index/offset table somewhere
(the `kind=2` gap blocks remain the leading candidate, though still
undeciphered) that tolerates exactly one known deviation but not two —
whatever mechanism allows the "exactly one" case to still work (a
resync/fallback path, most likely) apparently can't handle a second one.

Live demo.dat restored again after this test (SHA-256 `D3437249...`).

**Where this leaves things**: the `kind=2` block semantics are now the
clear next target — not to satisfy curiosity, but because this test
proves decoding them (or finding the code that reads them) is *the* path
to understanding why exactly two breaks it, which is the prerequisite for
ever fixing it. Content-side experiments (what translation, how much
text, which record) are no longer useful — this is purely a structural/
indexing question now.

## 4.8 CORRECTION — the real rule, structure fully decoded

§4.5/§4.7's "exactly one modified record, never two" conclusion was
**wrong** — a coincidental correlation, not the actual mechanism. User
explicitly redirected: "don't guess at kind=2's *meaning*, find the
*structure* first." Re-walked demo.dat as a raw chunk stream from offset
0 (not 0x30 — demo.dat's real prefix is only 0x20, differs from
movie.dat) using each block's own `(kind, size)` header to seek forward,
with zero fixed assumptions:

**demo.dat is a multiplexed container of 130 independent scenes**, not a
flat list of subtitle records with mystery padding:
- `kind` decomposes as `(stream<<16 | type)`. `type=2` blocks are
  interleaved multi-stream payload (5 streams, 0-4 — almost certainly
  video/audio packets) — 1,036,745 of the ~1,036,865 total blocks parsed
  cleanly, zero desyncs, zero unexplained bytes end to end.
- `type=16` blocks are scene-boundary tags; the one with `f3=2` marks a
  scene start. **130 scenes total, every single one aligned to a 0x800
  (2KB) boundary**, each followed by zero-padding up to that boundary
  (129,984 bytes total across 129 boundaries, avg ~1KB, max 2,016) before
  the next scene's tag.
- `type=4` blocks are the subtitle/font records this whole session has
  been calling "records" — they're just one ingredient inside a scene,
  interleaved with that scene's `type=2` media packets.
- `type=240` blocks are per-scene trailers (one `f2` value each, meaning
  still unknown — byte length or duration, not yet needed for this fix).

**The actual rule, confirmed by direct test**: playback only cares that
a scene's own **start offset** (the `type=16,f3=2` tag position) stays
byte-identical to the original. Growing a `type=4` record *inside* a
scene never moves that scene's own start (it only pushes bytes forward,
inside the scene and in every later scene) — so a single record's growth
is always safe by construction, no matter the size, which is exactly why
every 1-record test this session passed. Every N≥2 "record count" test
that failed did so because it always happened to touch a record in an
*earlier* scene than the one actually played (record 287 lives in scene
#127; every failing multi-record combination — 50+287, the 259/130/.../2
count bisections, even the "gap-only, no record touched" test that
padded before record 50 — included a change somewhere in scene #26 or
earlier, which cascades forward and shifts scene #127's start). The
"exactly one, never two" pattern was pure coincidence of which records
this session happened to pick, not a real ceiling.

**Fix, verified by direct hardware/Citra test**: fund each scene's growth
from *that same scene's own* trailing zero-padding instead of letting it
push into the next scene. Grew record 50 (scene 26) and record 287
(scene 127) by 1,600 bytes each simultaneously, trimming 1,600 bytes off
each scene's own padding run so every one of the 130 scene-start offsets
stayed byte-for-byte identical to the original (verified before
deploying: `demo_scene_aligned_two.dat`, total file size unchanged,
scene-start list diffed against the original — zero mismatches).
**User confirmed: plays correctly, no hang, no corruption.**

**This reopens bulk demo.dat translation via growth** — as long as each
scene's own growth stays within that scene's own padding budget (min 16,
max 2,016, avg ~1,008 bytes per boundary; ~130KB total across the file),
multiple scenes can be translated simultaneously. Next steps: build a
per-scene budget-aware selector (start from
`build_scene_aligned.py`/`demo_scene_budget.csv`, already computes the
padding table) that, like `--size-neutral-reclaim`, greedily fits as many
translated candidates as possible into each scene's own padding, and
re-run the full 913-candidate demo build through it instead of naive
`--grow-records`. Not yet built — next session's top priority, now that
the actual constraint is fully understood instead of guessed at.

**movie.dat likely has the identical scene structure** (the earlier
`type=240`/`type=16` skeleton walk on movie.dat found the same block
kinds, just far fewer of them, consistent with movie.dat's tiny size) —
its apparent total freedom in every experiment this session is probably
because its whole content fits inside very few scenes and every test
happened to stay within one, not because it's structurally exempt from
the same rule. Worth confirming directly next session rather than
assuming.

**codec.dat's GCX-count fragility (§4.6) is very likely the same
phenomenon** — a completely different container format, but "some
boundary must stay fixed, growth must be funded from same-unit local
slack" is exactly the lesson here too, and codec's already-established
safe recipe (`--reuse-freed-font`/donor-reclaim, funding growth from that
same GCX's own donor savings) is structurally the same fix pattern,
independently arrived at for a different format. No need to re-derive it
for codec; the multi-GCX crash (§4.6) most likely means the *unrestricted
growth* mode doesn't respect a GCX-level boundary the way donor-reclaim
naturally does — not a new mystery, just don't use unrestricted growth
across multiple GCX, same conclusion as before.

## 4.9 Confirmed: codec's multi-GCX crash was purely the wrong build mode

Verified §4.8's hypothesis directly. Took the same 22-GCX "backpack"
candidate set that crashed the game (§4.6, built with codec's
*unrestricted* growth mode, no boundary protection) and rebuilt it
through the actual established safe pipeline instead
(`mgs3d_codec_size_neutral_select.py --reclaim-non-english
--reclaim-language-blocks --protect-review ...` → `donor_audit.py` →
`build-korean --preserve-file-size --reuse-freed-font`, i.e. WIKI §2.1,
the same recipe used for this morning's live deploy).

Only 13/80 candidates survive real donor-budget selection (most of those
22 GCX simply don't have enough local donor savings — same wall as ever),
touching 10 GCX. **The resulting file's SHA-256 is byte-identical to the
current live codec.dat** — these 13 backpack-related lines were already
part of this morning's live donor-reclaim deploy (§3). So the "does
multi-GCX growth work if done safely" question has already been answered
affirmatively by production for months of this project's history; there
was never a new codec mystery, only a bad test (unrestricted mode, never
used for anything real).

**Unified conclusion across all three files**: every structural container
in this game (movie.dat/demo.dat "records" inside scenes, codec.dat
resources inside GCX) shares one rule — **a container's own boundary
must never move; growth is only safe when funded from that same
container's own local slack** (trailing zero padding for demo.dat scenes,
donor-reclaimed bytes for codec GCX, and — per the movie.dat single-record
tests, which never triggered this because movie.dat's whole file
apparently fits in very few scenes — presumably the same for movie.dat's
scenes too, unconfirmed). codec.dat already had the correct safe pipeline
in continuous production use; demo.dat's equivalent (a per-scene
budget-aware selector, `mgs3d_demo_scene_compact.py` + `--grow-records`)
was built and hardware-verified this session (§4.8); movie.dat's own
scene structure has not yet been directly confirmed.

Bottom line for "how much of the backlog can actually be reflected":
today's safe live number is 2,035/7,339 (§3). If growth is ever validated
safe for codec.dat, the ceiling rises to ~6,469/7,339 (88%) minus whatever
the two glyph-slot-maxed GCX need handled separately (they need a
different fix entirely, e.g. genuinely shortening those specific GCX's
vocabulary, not more space).

## 4.10 LLM-assisted translation for movie/demo cards with no Shinsnote match

§2's review backlog (2,403 rows) includes a large chunk of movie/demo
cards that have **no Shinsnote candidate at all** (blank, not just
color-mismatched) — those can never be filled by better matching, only
by an actual new translation. Built a small pipeline to draft candidates
for exactly those rows using a local LLM, reusing this session's other
new infrastructure (the §4.8 scene/capacity model) so the drafts come in
pre-sized to fit:

- `tools/mgs3d_scene_match_html.py` — `build_container()`/`load_script()`
  (built for an offline HTML matching-review tool) expose each card's
  scene, per-card byte capacity, and whether it already has embedded
  glyphs.
- `tools/mgs3d_llm_translate.py` — walks every movie/demo card via the
  above, skips anything that already has a Shinsnote match or existing
  glyphs, and for the rest builds a prompt (speaker, PS2 GameFAQs
  reference line, 3DS placeholder English, ±2 neighboring lines for tone,
  and the card's actual remaining char budget) for a local Ollama model.
  `--prepare-only` writes the batch (context included, no `.dat` access
  needed downstream) to JSON instead of calling Ollama directly.
- `tools/mgs3d_llm_translate_worker.py` — standalone stdlib-only worker
  that reads that batch JSON and calls a remote Ollama API per row,
  writing a CSV as it goes (`--resume` skips rows already done) — meant
  to run unattended on a machine other than this dev PC.
- Backend: Ollama on the Mac mini, `qwen3:8b`, reachable at
  `http://192.168.1.206:11434` over LAN (confirmed reachable and the
  model present via `/api/tags`).

**Batches prepared** (`analysis/ps2_korean/full_build/rebuild_2026-08-08/`):
`movie_llm_batch.json` (319 rows), `demo_llm_batch.json` (1,048 rows).

**Test run**: ran `mgs3d_llm_translate.py` directly against the movie
batch to sanity-check output quality/format before committing to the
full run — got 53/319 rows into `movie_llm_full.csv` (translations look
reasonable, e.g. "Don't get cocky. This isn't a training op." →
"자만하지 마. 이건 훈련 작전이 아니야."). Stopped there when this PC's
session ended unexpectedly (~01:13) before the run finished.

**Handoff to NAS, unattended overnight**: since the dev PC needs to be
off overnight, handed the remaining work (266 movie rows via `--resume`
+ all 1,048 demo rows, ~1,314 total) to `mgs3d_llm_translate_worker.py`
running standalone on the NAS, hitting the same Ollama endpoint. Command
and file list given to the user directly (not recorded in git); NAS run
is user-driven, not something this session executed or can verify from
here — check `movie_llm_full.csv`/`demo_llm_full.csv` timestamps/row
counts next session to see how far it got.

**Important — these are unreviewed drafts, not accepted translations.**
Same status as every other candidate in the §2 backlog: needs human
review for tone/accuracy before being selected into any build, and still
has to pass the normal byte/glyph capacity check (the `char_budget` sent
to the model is a target, not a hard guarantee the model respected it).
Next session: pull the two output CSVs back from the NAS, spot-check
quality, and fold accepted rows into the same review/selection pipeline
as §2's matched candidates.

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
- **Top of next session**: check on the §4.10 overnight LLM translation
  run on the NAS — pull `movie_llm_full.csv`/`demo_llm_full.csv` back,
  see how many of the ~1,367 rows actually completed, spot-check a
  sample for quality before trusting the rest.
- Build the §4.8 per-scene budget-aware selector for demo.dat
  (`--size-neutral-reclaim`-style greedy fit against each scene's own
  padding budget) and re-run the full 913-candidate demo build through
  it — this was the top structural priority before the LLM side-quest
  came up, still open.
