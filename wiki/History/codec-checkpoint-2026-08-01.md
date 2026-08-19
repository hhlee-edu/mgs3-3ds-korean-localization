# Codec localization checkpoint — 2026-08-01 23:40 KST

This document supersedes older codec review counts and GCX243 file names in the
session handoff and work-resume notes.

## Human-approved review data

- `analysis/review/codec/codec_korean_context_review_v3.csv`
  - 298/298 rows contain Korean and `accept=yes`.
  - Five low-capacity rows were shortened and remain approved:
    - GCX 193/5: `복장은 UNIFORM, 얼굴은 FACE.`
    - GCX 199/3: `FACE에서 그림을 고른다.`
    - GCX 446/11: `FACE와 UNIFORM이 뜬다.`
    - GCX 446/12: `복장은 UNIFORM, 얼굴은 FACE.`
    - GCX 449/10: `FACE를 고른다.`
- `analysis/review/codec/codec_gcx243_review.csv`
  - 142/142 rows contain Korean and `accept=yes`.
  - The reviewed range is now GCX243 resources 298..439. Resources 298 and 299
    were added after runtime screenshots exposed that the old 300..439 range
    omitted the first two stamina tutorial lines.
- Matching offline HTML files are under `analysis/html/codec/`.
- Superseded and pre-approval CSV/HTML files are recoverable under
  `analysis/archive/` and must not be used for builds.

## Runtime findings

`analysis/화면 캡처 2026-08-01 233430.png` proved GCX243/resource345 renders a
complete Korean camouflage sentence correctly.

`analysis/화면 캡처 2026-08-01 234014.png` showed mixed Japanese/Hangul before a
normal Korean line in `analysis/화면 캡처 2026-08-01 234018.png`. The cause is
now understood:

1. resource298 and resource299 were outside the first GCX243 review range;
2. many radio records contain semantic copies whose custom-glyph numbers and
   raw bytes differ;
3. diagnostic builds overwrite live Japanese custom-glyph slots, so every
   untranslated line in a changed GCX can display mixed Japanese/Hangul.

Exact raw-byte expansion reached 5,213 resources. A second diagnostic expansion
using a unique visible-Japanese signature reached 9,803 resources in 260 GCX
records, but it is still incomplete and is not a production solution.

## Current diagnostic build

- File: `analysis/runtime_codec_298/romfs/codec_all_visible_duplicates.dat`
- SHA-256: `0c63a109631285920592bfddc3f01dbc3a929bdb41484f91eedcb6b8e8490296`
- Size: 37,141,696 bytes
- Structure: 2,326 GCX records and 198,227 resources; full reparse passed.
- Mode: `--reuse-existing-font --preserve-record-layout` (diagnostic only).
- RomForge staging currently contains this same hash at
  `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\codec.dat`.

Do not promote or distribute this DAT. It intentionally overwrites glyphs still
used by untranslated Japanese. Mixed output is expected and has been observed.

## Honest progress estimate

- Changed physical resources in the latest diagnostic: 9,803 / 198,227 (4.95%).
- The number is inflated by duplicate resources.
- Approved source material currently consists mainly of 142 GCX243 tutorial
  lines plus 298 anchor rows representing only 13 distinct Korean strings and
  five principal English conversation entries.
- Coherent, runtime-clean radio localization is approximately 1–3%; overall
  radio content progress is approximately 3–5%.

The Korean reference corpus is available (`analysis/script_ref_mgs3_script.json`,
4,071 segments over 20 parts) together with the English script (4,767 lines),
but it is not a one-to-one map to the 198,227 game resources.

## Required next approach

### Immediate project priority

For the next phase, translation mapping is the highest priority. Do not spend
the main effort on broader diagnostic repacks, duplicate-count inflation, or
isolated runtime probes. The working loop should be:

1. select one real radio conversation used in early gameplay;
2. identify its complete GCX resource group and every live variant;
3. align each Japanese resource to the English and Korean reference context;
4. review and approve every row in the conversation, including short replies;
5. record uncertain or absent reference lines explicitly instead of guessing;
6. only after the mapping is complete, plan capacity and build one safe-fixed
   runtime test.

Progress should be reported primarily as completed conversation groups and
approved unique source lines, not as the number of propagated duplicate game
resources. A conversation is complete only when no untranslated Japanese line
in the changed GCX can reference a repurposed glyph slot.

Stop expanding isolated lines. Identify the GCX records actually used by an
early radio conversation and translate every live string in each selected GCX
conversation group. Then:

1. verify mappings row by row against Japanese, English, and Korean context;
2. ensure no untranslated string in the changed GCX still references glyphs
   that will be repurposed;
3. run strict `capacity --check` with `--reuse-freed-font` assumptions;
4. build with `--reuse-freed-font --preserve-record-layout` only;
5. runtime-test the complete conversation and untouched following dialogue;
6. promote only after mixed output and crashes are absent.

The broad diagnostic DAT should be replaced by the original codec or a focused
safe-fixed build before judging translation quality.

## Added tooling

- `mgs3-dialogue-tool/mgs3_matcher.py`
  - local Korean JSON import;
  - game-candidate JSON batching;
  - anchor evidence and curated-map application;
  - exact duplicate propagation.
- `tools/expand_codec_exact_duplicates.py`
  - diagnostic expansion to raw-identical and sufficiently long, unique visible
    Japanese signatures.
- `tools/mgs3d_gcx_font_tool.py select-diagnostic`
  - selects GCX groups that fit total existing glyph slots for diagnostic builds.

These diagnostic helpers do not replace the strict production capacity check.
