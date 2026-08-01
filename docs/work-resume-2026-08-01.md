# MGS3D Korean patch work resume — 2026-08-01

> **Paused checkpoint:** work was explicitly stopped by the user after the
> documentation phase. No comparison-audit implementation was started after
> this checkpoint, no build process is running, and no further DAT/CCI staging
> should be assumed. Resume from "Exact continuation order" below.

This is the short, authoritative resume document for today's work. Read it
before changing or staging any DAT file. Detailed history remains in
`docs/session-handoff-2026-08-01.md`.

## Today's objective

1. Increase video subtitles in small fixed-layout steps. If a step passes in
   game, promote it to the canonical personal build.
2. Replace low-confidence subtitle matching with an evidence-based comparison
   and review tool, especially for `codec.dat` radio conversations.

## Exact active state

### Runtime-validated baseline

- The 64-row fixed-layout `demo.dat` passed startup and continued video
  playback without a crash or stop. The user also confirmed that Korean
  subtitles appeared correctly at many points throughout the tested span.
- Its successful CCI is preserved as:
  `C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack_43row_pass.cci`.
- The canonical local build now contains the validated 64-row demo.

### Current RomForge state

RomForge currently contains the runtime-passed 64-row fixed-layout build:

- source CSV: `analysis/demo_fixed_max_safe_64.csv`;
- DAT: `analysis/runtime_bisect/demo_fixed_max_safe_64.dat`;
- size: 773,007,360 bytes;
- SHA-256: `44fa6fbba5dabfb4730e8272c1884ccec29c3f283f3a0a8660363646d8f15985`;
- staged path:
  `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\demo.dat`;
- local and staged hashes were rechecked and match;
- all 260 records structurally reparse.

The user reported that the 64-row build continued without a crash or stop and
displayed Korean subtitles correctly at many points during playback. It was
promoted with the unified builder to
`analysis/korean_first_draft/000400000007A000/romfs/demo.dat`. The verifier
passed the 925-file source inventory, movie/demo hashes and allocation reports,
93/558 movie structure, and 260/2,091 demo structure. The canonical DAT, local
probe, and RomForge staged DAT all have SHA-256
`44fa6fbba5dabfb4730e8272c1884ccec29c3f283f3a0a8660363646d8f15985`.

### Prepared but not approved

`extend-safe` found 14 more structurally safe candidate rows while retaining all
64 probe rows. A 78-row DAT was built only to prove fixed-layout feasibility:

- focused review: `analysis/html/demo/demo_next_14_review.html` and
  `analysis/review/demo/demo_next_14_review.csv`;
- combined table: `analysis/review/demo/demo_fixed_candidate_78_review.csv`;
- capacity: 15/15 changed records and 78/78 rows safe;
- feasibility DAT:
  `analysis/runtime_bisect/demo_fixed_candidate_78_unreviewed.dat`.

Do not stage or promote the 78-row DAT. The new 14 rows come from lower-confidence
alignment suggestions. Structural safety does not prove translation alignment.

## Current test state

`python -m unittest discover -s tests -q` passes 46 tests. The movie tool now
supports:

- `capacity --safe-csv`: retain only fully safe record groups;
- `capacity --max-safe-csv`: find a largest safe accepted-row subset per record;
- `extend-safe`: preserve a validated base and find the largest safe extension;
- `--extension-review`: emit only newly proposed rows for human review.

## Why matching confidence is the main problem

The Korean source, English transcript, and game resources do not share a
one-to-one segmentation:

- Korean and English pages contain radio, cutscene, narration, and guide prose;
- one transcript paragraph may span many game resources;
- the same codec plaintext is duplicated in many GCX records;
- Latin anchors such as `CIA JACK` recur and previously caused a proven wrong
  mapping;
- resource sequence varies between related GCX records;
- a plausible English/Korean pair is not proof that a specific game resource is
  its destination.

No tool should label a row approved from text similarity alone.

## Required comparison-tool design

The reliable tool must separate **candidate generation**, **evidence**, and
**approval**.

### 1. Stable identities and provenance

Every review row needs immutable source identifiers:

- game: DAT/GCX, record/resource or entry, byte offset, raw token hash;
- English: source file, sequence, line number, speaker;
- Korean: source page, sequence, speaker, original full text;
- algorithm version and input hashes.

Downloaded/edited review CSVs must retain these fields. A later build must reject
a row if its raw game hash no longer matches the source.

### 2. Evidence shown, not hidden in one confidence label

Each candidate should expose independent evidence:

- speaker agreement;
- shared anchors and whether each anchor is unique;
- local sequence consistency with already confirmed neighbors;
- same-record/GCX preceding and following resources;
- segmentation ratio and proposed paragraph split;
- duplicate raw-resource count and all duplicate destinations;
- contradictions such as repeated anchors, large length mismatch, crossing
  alignments, or disagreement with confirmed neighbors.

Confidence should be derived from explicit evidence and include rejection
reasons. `high`, `medium`, or `context` alone is not sufficient.

### 3. Conversation-level review

Radio translation must be approved as a conversation/resource group, not as
isolated lines. The reviewer should:

- group rows by GCX and English/Korean conversation;
- show resources in exact numeric order;
- allow one source paragraph to be split across consecutive resources;
- lock already verified anchors;
- flag gaps, overlaps, duplicate use of a source row, and order crossings;
- calculate fixed-layout font capacity for the whole proposed GCX group before
  export.

### 4. Conservative gates

Automatic approval is allowed only when all required evidence is present. At a
minimum:

- three shared anchors;
- at least one English-unique anchor;
- compatible speaker where speaker data exists;
- monotonic agreement with verified neighboring anchors;
- no equal-scoring competing English candidate;
- no known contradiction;
- source raw hash and provenance intact.

Rows failing any gate remain review candidates. Human approval must be explicit.

### 5. Build boundary

Approval and fixed-layout capacity are separate gates:

1. verify semantic alignment;
2. approve/edit Korean text;
3. validate provenance and token grammar;
4. plan capacity for the complete GCX/record group;
5. build fixed-layout only;
6. structurally verify;
7. test in game;
8. promote only after runtime success.

## Superseding codec checkpoint

Codec work continued after this resume note was written. Use
`docs/codec-checkpoint-2026-08-01.md` for the authoritative approved counts,
current file names, runtime screenshots, diagnostic hash, progress estimate,
and next workflow. Older codec counts and GCX243 instructions below are
historical only.

## Existing comparison artifacts

### General codec context

- `analysis/review/codec/codec_korean_context_review_v3.csv`
- `analysis/html/codec/codec_korean_context_review_v3.html`

These contain 299 conservative anchor candidates with +/-4 same-GCX candidate
resources, English conversation keys, and duplicate counts. Nothing is
automatically approved.

### Major Tom focused range

- `analysis/review/codec/codec_gcx243_major_tom_review.csv`
- `analysis/html/codec/codec_gcx243_major_tom_review.html`

This contains every string resource in GCX 243 resources 300..440, in order.
The corrected FPS targets are 366/367. The current capacity plan marks 28
resources total; only 366/367 have verified Korean text. The other 26 plan
resources require verified mapping/translation before a production build.

## Exact continuation order

1. Do not stage the 78-row feasibility DAT. Review its 14 additions first.
2. Use the new `batch-map-codec` command to map ordered GCX ranges to ordered
   Korean/English whole-script ranges. It emits raw-resource hashes, explicit
   anchor evidence, contradictions, and unapproved conversation-level rows.
3. Use GCX 243 resources 300..440 as the first conversation-level test case;
   identify its matching English sequence start/end and review the batch output.
4. Confirm and translate a coherent resource group large enough to satisfy the
   28-resource capacity plan, then run strict capacity and safe-fixed build.
5. Runtime-test Korean radio followed by untouched Japanese dialogue.

### Batch mapping implementation update

The fixed-radius `expand-codec-anchors` experiment was rejected. GCX resource
adjacency mixed dialogue with `No:...|radio_picture...` metadata and unrelated
resources, so all v1 whole-codec and GCX 243 batch artifacts were moved to
`analysis/rejected/fixed_radius_batch_v1`. The command now refuses to run.

The active v3 workflow filters metadata before anchor generation and keeps
neighboring resources as context only. Its artifacts are
`analysis/review/codec/codec_korean_anchor_review_v3.csv`,
`analysis/review/codec/codec_korean_context_review_v3.csv`, and
`analysis/html/codec/codec_korean_context_review_v3.html`. It contains 298 exact
anchor candidates, zero metadata rows, and zero automatic approvals.

`propagate-codec-approvals` copies an explicit approval only to identical
English-sequence, raw-hash, and Korean-fragment tuples.
`make-translation --codec` now rejects stale raw hashes and contradictions; the
unified builder automatically supplies the source codec for this validation.
No generated batch row is automatically approved. Human review of paragraph
boundaries remains required before capacity checking or building.

## Commands to resume

```powershell
python -m unittest discover -s tests -q

Get-FileHash -Algorithm SHA256 `
  analysis/runtime_bisect/demo_fixed_max_safe_64.dat, `
  'C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\demo.dat'

python tools/mgs3d_review_html.py `
  analysis/html/codec/codec_korean_context_review_v3.html `
  --codec analysis/review/codec/codec_korean_context_review_v3.csv

python tools/mgs3d_script_compare.py export-codec-range `
  partition0/romfs/codec.dat analysis/review/codec/codec_gcx243_major_tom_review.csv `
  --gcx 243 --start 300 --end 440 `
  --translation analysis/codec_fps_corrected_mapping.json `
  --capacity-plan analysis/capacity_plan_gcx243_300_440_minimal.json
```
