# MGS3 Korean script extraction and comparison

The 20 Shinsnote pages (`/219` through `/238`) are saved under
`analysis/shinsnote_mgs3`. The extraction keeps source page and paragraph order
but does not include images.

Current extraction statistics:

- 20 HTML pages
- 4,071 normalized segments
- 3,033 segments recognized as `speaker: dialogue`
- 195,681 candidate string resources exported from `codec.dat`

Generated files:

- `analysis/shinsnote_mgs3_script.json`: structured source data
- `analysis/shinsnote_mgs3_script.csv`: spreadsheet-friendly source data
- `analysis/mgs3d_game_candidates.json`: GCX/resource candidates
- `analysis/mgs3d_script_comparison.csv`: loose side-by-side suggestions
- `analysis/gamefaqs_mgs3_english.json`: extracted English dialogue
- `analysis/gamefaqs_mgs3_english.csv`: spreadsheet-friendly English dialogue
- `analysis/mgs3_korean_english_alignment.csv`: Korean/English suggestions
- `analysis/mgs3_trilingual_game_comparison.csv`: Korean/English/GCX combined view
- `analysis/movie_strings.csv`: 481 filtered `movie.dat` subtitle candidates
- `analysis/demo_strings.csv`: 1,446 filtered `demo.dat` subtitle candidates
- `analysis/movie_korean_comparison.csv`: movie DAT/Japanese/English/Korean view
- `analysis/demo_korean_comparison.csv`: demo DAT/Japanese/English/Korean view
- `analysis/movie_records.json` / `.csv`: 558 structurally parsed movie entries
- `analysis/demo_records.json` / `.csv`: 2,091 structurally parsed demo entries
- `analysis/movie_korean_comparison_exact.csv`: patchable movie comparison rows
- `analysis/demo_korean_comparison_exact.csv`: patchable demo comparison rows
- `analysis/mgs3_korean_english_alignment_dp.csv`: global one-to-one alignment
- `analysis/movie_korean_comparison_review.csv`: record-context movie review
- `analysis/demo_korean_comparison_review.csv`: record-context demo review
- `analysis/movie_korean_auto_approved.csv`: 47 conservative accepted rows
- `analysis/demo_korean_auto_approved.csv`: 94 conservative accepted rows

The user-supplied GameFAQs text produced 2,164 speaker-labelled English
dialogues. The Korean source currently produces 3,031 speaker-labelled
dialogues. All 3,031 Korean rows receive an English suggestion; different scope
and ordering mean suggestions may repeat and still require review. The combined
CSV is the primary review file.

`movie.dat` and `demo.dat` use aligned, null-terminated MGS token streams with
page-3 custom glyph tokens (`90xx`). A strict token grammar and encoded-text
ratio filter reduced binary false positives to 481 and 1,446 candidates. The
DAT-oriented comparison tables include exact byte offsets and lossless raw text.
Currently 281 movie rows and 916 demo rows receive Korean suggestions. Nothing
is accepted automatically.

The later structural parser supersedes the filtered scan for patching. It found
93 records and 558 entries in `movie.dat`, and 260 records and 2,091 entries in
`demo.dat`. Every exact entry has a record index and byte offset. Exact
comparison generated Korean suggestions for 340 movie entries and 1,326 demo
entries. The earlier filtered tables remain useful as a dialogue-heavy view,
but the `_exact.csv` files are the authoritative build inputs.

## Confirmed movie/demo record structure

Records are type 4 and aligned to 0x10 bytes. Their confirmed fields are:

- `+0x04`: complete aligned record size
- `+0x10`: subtitle/font boundary relative to `record + 0x14`
- `+0x20`: first subtitle entry
- subtitle entry header: upper 16 bits type 7, lower 16 bits declared size
- ordinary entry: header, null-terminated token text, padding, 12-byte timing data
- final entry: declares the same extra 12 bytes but omits them on disk
- font boundary: little-endian font byte size followed by raw 16x16 2-bpp glyphs
- each embedded glyph occupies exactly 64 bytes; this block is not compressed

`tools/mgs3d_movie_tool.py` scans all record groups while preserving the opaque
bytes between them. A no-change `movie.dat` rebuild is byte-identical with
SHA-256 `f5c8771f58ec3d2c30a825c3fb622db1fec513a6772aaaa8ef95c097499a06f6`.

## Review workflow

For codec/radio candidates, first enrich the conservative anchor table with
neighboring resources from the same GCX and generate a dedicated offline page:

```powershell
python tools/mgs3d_script_compare.py codec-context `
  analysis/mgs3d_game_candidates.json `
  analysis/review/codec/codec_korean_anchor_review_v3.csv `
  analysis/review/codec/codec_korean_context_review_v3.csv --radius 4

python tools/mgs3d_review_html.py `
  analysis/html/codec/codec_korean_context_review_v3.html `
  --codec analysis/review/codec/codec_korean_context_review_v3.csv
```

Each candidate shows four preceding and following candidate resources in its
GCX, marks the proposed target with `>`, records the English conversation key,
and shows how many GCX copies share the same raw resource. This context is
required for review because a Latin anchor such as `CIA JACK` can occur in an
unrelated radio line. Context assists human verification; it is not automatic
proof of a mapping.

For a focused conversation, export every resource in one GCX range rather than
only anchor-matched candidates. A translation JSON and capacity plan can be
overlaid to mark known targets and the additional resources that must be
translated to free font slots:

```powershell
python tools/mgs3d_script_compare.py export-codec-range `
  partition0/romfs/codec.dat analysis/review/codec/codec_gcx243_major_tom_review.csv `
  --gcx 243 --start 300 --end 440 `
  --translation analysis/codec_fps_corrected_mapping.json `
  --capacity-plan analysis/capacity_plan_gcx243_300_440_minimal.json
```

The generated Major Tom table contains 141 sequential string resources. The
two corrected FPS targets are marked mandatory and the current capacity plan
marks 28 resources total. The remaining selected resources need verified
Korean mappings before a production-safe codec can be built.

### Batch conversation mapping

When the matching game range and whole-script range are known, map the complete
conversation in one command instead of matching individual lines:

```powershell
python tools/mgs3d_script_compare.py batch-map-codec `
  partition0/romfs/codec.dat `
  analysis/mgs3_korean_english_alignment_dp.csv `
  analysis/codec_conversation_batch_review.csv `
  --gcx 243 --start 300 --end 440 `
  --english-start FIRST_SEQUENCE --english-end LAST_SEQUENCE

python tools/mgs3d_review_html.py `
  analysis/html/codec/codec_conversation_batch_review.html `
  --codec analysis/codec_conversation_batch_review.csv
```

The command treats both ranges as ordered conversation blocks. It assigns game
resources monotonically using cumulative text length, divides a Korean paragraph
across consecutive resources at word boundaries, and records the raw game token
SHA-256 for provenance. Shared Latin/number anchors raise a row from `sequence`
to `anchor`; conflicting anchors are reported in `contradictions`. All rows are
exported unapproved because ordered splitting is a review suggestion, not proof
of semantic equivalence. Verify the block's start, end, speakers, and order in
the HTML reviewer before approving its rows together.

GCX adjacency does not establish a conversation. The retired fixed-radius
experiment incorrectly expanded anchors into `No:...|radio_picture...` metadata
and unrelated resources. Its artifacts are quarantined under
`analysis/rejected/fixed_radius_batch_v1` and must not be approved or built.

The active bulk review keeps Korean only on the anchor target and displays
neighbors as context:

```powershell
python tools/mgs3d_script_compare.py align-codec-anchors `
  analysis/mgs3d_game_candidates.json analysis/gamefaqs_mgs3_english.json `
  analysis/mgs3_korean_english_alignment_dp.csv `
  analysis/review/codec/codec_korean_anchor_review_v3.csv

python tools/mgs3d_script_compare.py codec-context `
  analysis/mgs3d_game_candidates.json analysis/review/codec/codec_korean_anchor_review_v3.csv `
  analysis/review/codec/codec_korean_context_review_v3.csv --radius 4

python tools/mgs3d_review_html.py analysis/html/codec/codec_korean_context_review_v3.html `
  --codec analysis/review/codec/codec_korean_context_review_v3.csv
```

After reviewing exact anchor targets, copy an approval only to byte-identical
resources with the identical English sequence and Korean fragment:

```powershell
python tools/mgs3d_script_compare.py propagate-codec-approvals `
  analysis/review/codec/codec_korean_context_review_v3_reviewed.csv `
  analysis/review/codec/codec_korean_context_review_v3_approved.csv
```

Finally convert accepted rows with provenance validation. The converter rejects
changed raw-resource hashes, unresolved contradictions, and duplicate targets:

```powershell
python tools/mgs3d_script_compare.py make-translation `
  analysis/review/codec/codec_korean_context_review_v3_approved.csv `
  analysis/codec_korean_context_translation_v3.json `
  --codec partition0/romfs/codec.dat

python tools/mgs3d_gcx_font_tool.py capacity `
  partition0/romfs/codec.dat analysis/codec_korean_context_translation_v3.json `
  --json analysis/codec_korean_context_capacity_v3.json --check
```

The easiest review surface is the self-contained offline page:

```powershell
python tools/mgs3d_review_html.py analysis/html/mgs3d_translation_review.html `
  --movie analysis/movie_korean_auto_approved.csv `
  --demo analysis/demo_korean_auto_approved.csv `
  --codec analysis/codec_korean_anchor_review.csv
```

Open `analysis/html/mgs3d_translation_review.html` in a browser. It contains all
2,948 current review rows and needs no server or network connection. Use the
table, confidence, state, and text filters; edit Korean text directly; tick
`승인`; then press `현재 표 CSV 저장`. The downloaded UTF-8 BOM CSV preserves
the original column set and is accepted directly by the DAT builders. A
downloaded codec table first goes through `make-translation` as shown below.

Open `mgs3d_script_comparison.csv` in a spreadsheet. Relevant columns are:

- `korean`: extracted Korean dialogue
- `gcx`, `resource`: proposed game destination
- `game_preview`: decoded game-side preview
- `confidence`: heuristic confidence, not proof
- `accept`: set to `y` only when the pair should be used

Leave incorrect or unwanted rows blank. Convert only accepted rows:

```powershell
python tools/mgs3d_script_compare.py make-translation `
  analysis/mgs3d_script_comparison.csv analysis/accepted_translation.json
```

Then build Korean `codec.dat`:

```powershell
python tools/mgs3d_gcx_font_tool.py build-korean `
  partition0/romfs/codec.dat analysis/accepted_translation.json `
  C:\Windows\Fonts\malgun.ttf dist/codec.dat `
  --reuse-freed-font --preserve-record-layout
```

Run `mgs3d_gcx_font_tool.py capacity` first. A codec translation is safe only
when every changed GCX has at least as many freed original glyph slots as unique
Hangul syllables. Runtime testing confirmed that relocating later GCX records
causes game `PANIC` errors even when the rebuilt container reparses cleanly.

For cutscene DAT files, review `movie_korean_comparison_exact.csv` or
`demo_korean_comparison_exact.csv`, and put `yes` in `accept` only for confirmed
rows. Build to a separate output path:

```powershell
python tools/mgs3d_movie_tool.py build-korean `
  partition0/romfs/movie.dat analysis/movie_korean_comparison_exact.csv `
  C:\Windows\Fonts\malgun.ttf dist/movie.dat

python tools/mgs3d_movie_tool.py build-korean `
  partition0/romfs/demo.dat analysis/demo_korean_comparison_exact.csv `
  C:\Windows\Fonts\malgun.ttf dist/demo.dat
```

The builder uses the original absolute `offset` column and changes only accepted
entries. It safely reuses page-3 font slots owned exclusively by replaced
subtitles, preserving every entry size, record size, and file offset. A build is
refused when either font slots or existing text bytes are insufficient, and the
finished file is reparsed as a structural postcondition. Never use the source
path as the output path.

To expand a runtime-validated fixed-layout base without dropping any known-good
row, use `extend-safe`. It finds a largest safe addition from a broader Korean
candidate table and can emit a small, additions-only review file:

```powershell
python tools/mgs3d_movie_tool.py extend-safe `
  partition0/romfs/demo.dat analysis/demo_fixed_max_safe_64.csv `
  analysis/demo_korean_comparison_review.csv `
  analysis/review/demo/demo_fixed_candidate_78_review.csv `
  --extension-review analysis/review/demo/demo_next_14_review.csv
```

Capacity safety does not establish translation correctness. Review the added
rows before staging the combined output.

## Unified Citra build

`tools/mgs3d_build.py` reads the NCCH header and automatically uses this dump's
title ID, `000400000007A000`. It can build any reviewed subset into the standard
Citra mod layout and writes SHA-256 values to `build-manifest.json`:

```powershell
python tools/mgs3d_build.py `
  --codec-review analysis/codec_korean_anchor_review_reviewed.csv `
  --codec-mode safe-fixed `
  --movie-csv analysis/movie_korean_comparison_exact.csv `
  --demo-csv analysis/demo_korean_comparison_exact.csv `
  --output-root dist/citra_mod
```

`--codec-review` automatically converts accepted codec rows into
`accepted_codec_translation.json`. Advanced users can instead pass a prepared
JSON document with `--codec-translation`; the two options are mutually
exclusive.

`safe-fixed` is the default and refuses unsafe codec output.
`diagnostic-fixed` is only for runtime identification: it preserves GCX layout
but overwrites live Japanese glyphs. `experimental-relocate` may reparse but is
known to crash in game and must not be used for release builds.

Only pass a table after it has accepted rows. The resulting directory is
`dist/citra_mod/000400000007A000`; copy or link that title-ID directory beneath
Citra's `load/mods` directory. A one-line integration sample is already built
there from `analysis/sample_movie_translation.csv`. It replaces the first movie
entry with `한글 출력 시험입니다.`, expands that record's font from 26 to 35
glyphs, and reparses as 93 records / 558 entries.

The production-oriented conservative build is under
`dist/citra_korean_auto/000400000007A000`. It contains both `movie.dat` and
`demo.dat`; `build-manifest.json` records their sizes and SHA-256 hashes. The
movie build changes 47 entries and the demo build changes 94 entries. These are
not claimed to be a finished translation: automatic approval requires a strong
Korean/English anchor plus either a direct DAT anchor or a same-record context
anchor. Rows without this evidence remain blank for human review.

When an English transcript paragraph spans consecutive entries in one record,
the review generator divides the Korean text at word boundaries in proportion
to the Japanese entry lengths. The `korean_full` column retains the unsplit
source sentence for checking. This avoids repeating a complete Korean paragraph
on every subtitle card.

The DAT builder additionally preserves each entry's explicit `80 7C` line
marker. Korean words are distributed according to the original Japanese line
lengths; very short one-word entries fall back to character splitting. The
current conservative build verifies all such accepted cases: 18/18 movie and
15/15 demo entries retain their line layout after rebuilding and reparsing.

Embedded output can be inspected without launching the game:

```powershell
python tools/mgs3d_movie_tool.py extract-font `
  dist/citra_korean_auto/000400000007A000/romfs/movie.dat `
  0 analysis/movie_auto_record0_font.png
```

## Important scope boundary

The source pages mix radio dialogue, cutscene dialogue, stage directions, and
walkthrough prose. `codec.dat` is only one game-side corpus; cutscene subtitles
may instead belong to `demo.dat`. Consequently the comparison is intentionally
loose and no row is accepted automatically. Sequence, length, numbers, and
Latin names are used only to suggest candidates.
