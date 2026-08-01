# MGS3D Korean localization handoff — 2026-08-01

> For the concise authoritative state and exact continuation order, read
> `docs/work-resume-2026-08-01.md` first.

## Outcome

The codec dialogue path now renders complete Korean sentences in game without a
Citra fatal error when every GCX record keeps its original layout. The runtime
probe translated two consecutive FPS tutorial resources. `analysis/1.png` and
`analysis/2.png` show the Korean lines; `analysis/3.png` through `5.png` show
normal Japanese dialogue continuing afterward.

Validated Korean lines:

1. `아래 화면 오른쪽 위 아이콘으로 사격 모드를 전환할 수 있다.`
2. `FPS 모드로 전환하면 상하좌우 원하는 방향으로 공격할 수 있다.`

## Confirmed runtime rules

- `codec.dat` contains 2,326 sequential GCX records and 198,227 resources.
- The game depends on stable GCX positions, not merely a structurally valid DAT.
- Growing or shrinking a GCX shifts later records and eventually causes repeated
  game `PANIC` breaks and a Citra fatal-error dialog.
- A safe codec build must preserve, for every GCX:
  - source offset;
  - stored record size;
  - string-resource boundary;
  - font-data boundary;
  - procedure boundary.
- The embedded codec font is 16x16, 2-bpp, 64 bytes per glyph.
- `8Cxx` custom tokens and the generated Malgun Gothic glyphs render Hangul.
- Fixed-layout diagnostic replacement ran through Korean and subsequent Japanese
  dialogue without a crash.

## Tool state

`tools/mgs3d_gcx_font_tool.py` now provides three strategies:

- `--reuse-freed-font --preserve-record-layout`: production-safe. It reuses only
  glyph slots no longer referenced after the selected resources are translated.
  The build stops when capacity is insufficient.
- `--reuse-existing-font --preserve-record-layout`: diagnostic only. It keeps
  the layout stable but can corrupt untranslated Japanese glyphs.
- no fixed-layout flags: experimental relocation. It reparses statically but is
  known to crash at runtime and must not be released.

Capacity check:

```powershell
python tools/mgs3d_gcx_font_tool.py capacity `
  partition0/romfs/codec.dat translation.json `
  --json analysis/codec_capacity.json
```

Safe codec build:

```powershell
python tools/mgs3d_gcx_font_tool.py build-korean `
  partition0/romfs/codec.dat translation.json `
  C:\Windows\Fonts\malgun.ttf output_codec.dat `
  --reuse-freed-font --preserve-record-layout
```

The unified builder defaults to `--codec-mode safe-fixed`. The verifier checks
all 2,326 fixed-layout invariants when the manifest records a fixed codec mode.

## Runtime probe artifacts

- Translation input: `analysis/codec_fps_runtime_probe.json`
- Tested codec: `analysis/codec_fps_fixed_layout.dat`
- Tested SHA-256:
  `e4da23e4dd7219ce051159caa0eb5419b511391ef412e02174f6f10414f8806a`
- Capacity report: `analysis/codec_fps_capacity.json`
- Screenshots: `analysis/1.png` through `analysis/5.png`

The probe patches duplicated resource pairs in GCX 243 through 270. It uses
diagnostic glyph reuse and is evidence for fixed-layout Hangul rendering, not a
production translation.

### 2026-08-01 mapping correction

Follow-up source-context inspection found that every resource number in
`analysis/codec_fps_runtime_probe.json` is 30 positions after the Japanese
source matching the supplied Korean FPS mode-switch text. For example, the
semantic source pair in GCX 243 is 366/367, while the diagnostic probe replaced
396/397 (a different handgun/FPS explanation). The two tools use the same
resource numbering; this is a mapping error, not an indexing convention.

Use `analysis/codec_fps_corrected_mapping.json` for the corrected 40-resource
mapping. Its capacity report is `analysis/codec_fps_corrected_capacity.json`.
All 20 GCX records currently have 32 required Hangul syllables, zero freed
slots, and a deficit of 32, so the corrected two-line mapping is not safe to
build by itself.

GCX 243 capacity planning shows that replacing the contiguous range 326..440
frees 30 slots (deficit 2), while 325..440 frees 33 slots (passes). These
planning files use placeholder text and are not translations. A smaller,
non-contiguous conversation/resource set may be possible after analyzing glyph
reference ownership.

`tools/mgs3d_capacity_plan.py` now performs that ownership analysis with a
greedy union/pruning heuristic. It does not prove mathematical optimality. For
GCX 243 and mandatory resources 366/367 it found:

- 10 resources / 35 slots without a range constraint, but the extra resources
  are unrelated later conversations and therefore not a good translation unit;
- 28 resources / 32 slots when restricted to resources 300..440;
- 32 resources / 32 slots when restricted to resources 325..440.

The 300..440 result is retained as
`analysis/capacity_plan_gcx243_300_440_minimal.json` and is the current best
focused candidate. Every selected placeholder resource still needs a verified
Korean mapping before a production build.

## RomForge state

RomForge input:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0`

The DAT replacement directory is:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs`

Original DAT backups are under:

`C:\Users\hhlee\Desktop\Romforge\output\backup_original_dat`

### Current RomForge staging — 2026-08-01

The RomForge input has been prepared for the user to repack. It contains the
restored original codec plus the first-draft Korean movie/demo build:

- `codec.dat`: restored original from `backup_original_dat`; 37,141,696 bytes;
  SHA-256 `932c0a13dd4a0a55213e0a2352b12a11b496a7216706838d0d044930789a344f`;
- `movie.dat`: first draft with 47 accepted Korean subtitles; 268,384 bytes;
  SHA-256 `a68600c55b1b74b54a9b903a88b9be596499401c558f080b0e374292bda9f88d`;
- `demo.dat`: first draft with 94 accepted Korean subtitles; 773,029,744
  bytes; SHA-256
  `ad18a9ee0ace7f9d964f57a73a2a27107a3cef21092e9f2c920b45e7fd83675c`.

All three destination hashes were checked against their intended sources after
copying. The corresponding local build is:

`analysis/korean_first_draft/000400000007A000`

This staging contains 141 preliminary Korean subtitle lines total and no codec
translation. It is ready for the user to repack with RomForge and test in
Citra. Do not reintroduce `analysis/codec_fps_runtime_probe.json` or its
diagnostic codec into this staging directory.

### Runtime isolation update

The first combined movie/demo repack appeared to stop during the opening
historical text. The active Citra log files in this workspace were stale (last
modified in 2024), so they contained no evidence from this run. To isolate the
runtime dependency, RomForge staging was changed to movie-only Korean:

- `codec.dat`: original, SHA-256
  `932c0a13dd4a0a55213e0a2352b12a11b496a7216706838d0d044930789a344f`;
- `movie.dat`: 47-line Korean first draft, SHA-256
  `a68600c55b1b74b54a9b903a88b9be596499401c558f080b0e374292bda9f88d`;
- `demo.dat`: restored original, 773,007,360 bytes, SHA-256
  `3c451c665ea415ce7b260505eee7f1674bf2169949be90caa45f4b58f09dbe39`.

All destination hashes match their intended sources. The user should repack
this state and replay the same opening without skipping. If it no longer stops,
the patched `demo.dat` path is the cause; if it still stops, restore original
`movie.dat` as the next control test.

The movie-only control passed the previous stopping point, confirming that the
runtime problem is in the translated `demo.dat` path. The next RomForge staging
uses the first 47 of the 94 accepted demo rows (accepted rows through record 33)
for a binary-search probe:

- CSV: `analysis/demo_runtime_bisect_a_47.csv`;
- DAT: `analysis/runtime_bisect/demo_a_47.dat`;
- size: 773,018,224 bytes;
- SHA-256: `c57b8ccca34bdb5ba788ccc6253b04562d4dc6e588a4f5fc4f9bb077284cee32`.

This DAT was copied to the RomForge staging `romfs/demo.dat`, and the source and
destination hashes matched. Repack and replay the same opening. A stop means
the bad record is among these first 47 accepted rows; passing the opening means
it is among the remaining 47 rows.

The 47-row probe stopped before the KONAMI logo, so the runtime-breaking change
is within its first 47 accepted rows. RomForge staging was advanced to the first
23 accepted rows (through demo record 8, entry 8):

- CSV: `analysis/demo_runtime_bisect_a_23.csv`;
- DAT: `analysis/runtime_bisect/demo_a_23.dat`;
- size: 773,013,744 bytes;
- SHA-256: `4afe064b80d372bf094bbb5a27d63e3a98e9aec32845c5d692ef24fd24349c27`.

The staged copy has the same hash. If this probe stops, continue bisecting rows
1..23; if it passes, bisect rows 24..47 while keeping rows 1..23 excluded.

The 23-row probe also stopped before the KONAMI logo. The next staged probe
contains only the first 11 accepted rows (through demo record 5, entry 1):

- CSV: `analysis/demo_runtime_bisect_a_11.csv`;
- DAT: `analysis/runtime_bisect/demo_a_11.dat`;
- size: 773,011,824 bytes;
- SHA-256: `a046156d5b249781e831a4505e8220cd824721a2e58178b30e5a2aa8015be197`.

The staged source/destination hashes matched. A stop narrows the bad change to
rows 1..11; a pass narrows it to rows 12..23.

The 11-row probe stopped. Inspection showed rows 1..7 all belong to demo record
2, so row-count bisection had repeatedly included the same first rebuilt record.
The next diagnostic staging changes only the very first accepted row, record 2
entry 0 (`충격은`):

- CSV: `analysis/demo_runtime_probe_first_row.csv`;
- DAT: `analysis/runtime_bisect/demo_first_row.dat`;
- size: 773,007,536 bytes;
- SHA-256: `c2c169e57db2757eccdae339bc79835432fb760a3e77955bf659f70741efffb6`.

The staged source/destination hashes matched. If this single-row probe stops,
record 2 rebuilding itself is runtime-incompatible (not evidence that later
accepted rows are bad). If it passes, test the other entries within record 2.

The single-row record-2 probe stopped before the KONAMI logo. This confirms that
record 2 rebuilding is sufficient to trigger the runtime failure. The next probe
excludes record 2 and changes only the first accepted row in record 4, entry 0:

- CSV: `analysis/demo_runtime_probe_record4_one_row.csv`;
- DAT: `analysis/runtime_bisect/demo_record4_one_row.dat`;
- size: 773,008,192 bytes;
- SHA-256: `5b41b6ad34bbbde523ae6bc69e2d7f1b7316183e68aaba33e0e295ca50897e78`.

The staged source/destination hashes matched. If record 4 also stops, suspect a
general demo record-rebuild incompatibility. If it passes, treat record 2 as a
record-specific incompatibility and exclude it from the next multi-record build.

The record-4 single-row probe also stopped before the KONAMI logo. Therefore the
current append-and-grow demo rebuild is runtime-incompatible in general, despite
passing the static parser. Do not stage any generated `demo.dat` from this
builder. The likely required design is a fixed-layout builder that reuses font
slots owned only by replaced subtitles and keeps every record and file offset
unchanged, analogous to safe-fixed codec handling.

### RomForge test cleanup rule

After the user reports a runtime test failure, delete generated `.cci` files
under `C:\Users\hhlee\Desktop\Romforge\output` before preparing the next probe,
so a stale failed image cannot be reused. A recursive check after the record-2
failure found no `.cci` file currently present.

After the record-4 failure,
`C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack.cci` was
deleted and a recursive check confirmed zero remaining CCI files. RomForge
staging `demo.dat` was restored from `backup_original_dat`; source and staged
SHA-256 both equal
`3c451c665ea415ce7b260505eee7f1674bf2169949be90caa45f4b58f09dbe39`.

### Fixed-layout demo implementation

`tools/mgs3d_movie_tool.py build-korean` now defaults to safe fixed-layout
rebuilding. For each changed record it reuses only page-3 font slots referenced
by replaced subtitles and not by retained subtitles. It refuses font-slot or
text-byte deficits instead of growing an entry, record, or the DAT. Three unit
tests cover token ownership, exact-size rebuilding, and deficit rejection; all
43 repository tests pass.

The first record-2 row was rebuilt again with this implementation:

- DAT: `analysis/runtime_bisect/demo_first_row_fixed.dat`;
- size: 773,007,360 bytes, exactly matching the original;
- all 260 record offsets and sizes match the original;
- only 164 bytes differ, from `0x508E78` through `0x5090A7`;
- SHA-256: `27feffc44fe74126224ed192bee365f4e945cfb683ec896346b4433ce1874178`.

This fixed-layout DAT is currently staged in RomForge and its destination hash
matches. Repack it and check whether the KONAMI logo appears. A successful boot
validates fixed-layout demo patching; a failure means record growth was not the
only incompatibility.

#### Runtime result: fixed-layout probe passed

The user repacked the fixed-layout record-2 one-row probe and reported that the
KONAMI logo appeared. This is the first positive runtime validation of generated
`demo.dat` data and confirms the startup failures were caused by the earlier
append-and-grow layout, not merely by changing demo text or font bytes.

The successful input remains staged with SHA-256
`27feffc44fe74126224ed192bee365f4e945cfb683ec896346b4433ce1874178`.
The successful CCI is retained at
`C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack.cci`;
it is 3,139,076,096 bytes and was last written 2026-08-01 09:36:26 KST. The
failure-cleanup rule applies only after a failed runtime test; do not delete this
successful control image unless preparing a later probe requires replacement.

This result validates startup/initial loading only. It does not yet prove that
the translated subtitle renders correctly when its scene is reached, nor that
every other demo record has sufficient exclusive font slots and text bytes.

#### Runtime result: Hangul subtitle rendering also passed

The user left the successful fixed-layout build running and later observed
Korean text during the Sokolov explanation scene. Therefore the same one-row
probe validates the complete demo patch path, not only startup:

- RomForge repacking accepted the fixed-size DAT;
- the game reached and displayed the affected demo scene;
- the reused page-3 font slot rendered Hangul;
- the replacement token stream was read successfully at runtime;
- retained layout/timing data remained usable through that point.

`demo.dat` safe-fixed rebuilding is now runtime-validated for this record-2
sample. Do not generalize this to all 94 draft rows without capacity checks:
each changed record must still satisfy exclusive font-slot ownership and fixed
text-byte capacity, and automatic Korean/English matching remains preliminary.

### Departure checkpoint: exact active state

#### 43-row fixed-layout multi-record probe prepared

After the one-row runtime success, all 94 preliminary accepted demo rows were
checked as complete record groups with the new `mgs3d_movie_tool.py capacity`
command. Nine of 21 changed records satisfy both exclusive page-3 font-slot
capacity and every entry's fixed text-byte capacity. They contain 43 rows:

- safe record IDs: 2, 8, 11, 25, 30, 59, 107, 121, and 224;
- capacity report: `analysis/demo_fixed_capacity.json`;
- filtered review CSV: `analysis/demo_fixed_safe_43.csv`;
- built DAT: `analysis/runtime_bisect/demo_fixed_safe_43.dat`;
- size: 773,007,360 bytes, exactly matching the original;
- SHA-256: `4c98e2e669107014bf5e93a60846ab20e6ca63439154c2521f34adf457afe9c6`;
- structural postcondition: all 260 records reparse successfully.

This DAT is now staged as RomForge `romfs/demo.dat`; the staged SHA-256 matches.
The previously successful one-row CCI remains present and was not deleted.
The user should now repack a new CCI and test startup plus several changed and
unchanged subtitle scenes. Do not treat the retained older CCI as this new
43-row build.

#### Runtime result: 43-row multi-record probe passed the tested opening

The user repacked the staged 43-row fixed-layout DAT and confirmed that the
previous startup/video stopping symptom is gone. In the tested portion, Korean
subtitles appeared from the CIA/approval-related dialogue through the Virtuous
Mission explanation and playback continued normally. The earlier one-row
version's Virtuous Mission explanation was also reconfirmed separately.

Korean text did not appear in the earlier portion of the video. This is not a
runtime-layout failure by itself: the 43-row probe intentionally contains only
the nine complete records that passed fixed font-slot and text-byte capacity.
Coverage and mapping for the omitted opening rows must be handled separately.
The current runtime evidence validates multiple fixed-layout demo records over
the observed opening span, but does not yet prove every one of the nine changed
records or all later video scenes.

After this runtime result, the validated 43-row DAT was promoted into the local
canonical build at `analysis/korean_first_draft/000400000007A000/romfs/demo.dat`
using the transactional unified builder. The manifest now records its fixed
size and SHA-256, while preserving the existing movie output. The build
verifier passed the 925-file source inventory, both output/report hashes,
93/558 movie structure, and 260/2,091 demo structure. The canonical build and
RomForge staging `demo.dat` hashes are identical. The old append-and-grow
94-row demo is no longer the canonical first-draft output.

#### Next video probe: maximal safe 64-row subset

`mgs3d_movie_tool.py capacity --max-safe-csv` now searches every accepted-row
combination inside each changed record and retains a largest fixed-layout-safe
subset. Applied to the 94 preliminary rows, it keeps all validated 43 rows and
adds 21 rows from records 7, 32, 33, 36, 82, and 86.

- CSV: `analysis/demo_fixed_max_safe_64.csv`;
- DAT: `analysis/runtime_bisect/demo_fixed_max_safe_64.dat`;
- size: 773,007,360 bytes;
- SHA-256: `44fa6fbba5dabfb4730e8272c1884ccec29c3f283f3a0a8660363646d8f15985`;
- structural result: 260 records reparse successfully.

This 64-row DAT is staged in RomForge and its destination hash matches. The
known-good 43-row CCI was preserved as
`MGS SNAKE EATER 3D_Repack_43row_pass.cci`; create a new CCI for this probe.
Do not promote the 64-row DAT to the canonical build until its runtime test
passes.

The next expansion has also been prepared but is deliberately not staged.
`mgs3d_movie_tool.py extend-safe` keeps every row in a validated base CSV as
mandatory and searches for the largest safe addition from a broader candidate
CSV. Starting from the 64-row probe it finds 14 additional candidates, for a
78-row structurally safe set across 15 records. The unreviewed feasibility DAT
reparses as all 260 records, but its new mappings are not yet trusted.

- focused human-review page: `analysis/html/demo/demo_next_14_review.html`;
- focused CSV: `analysis/review/demo/demo_next_14_review.csv`;
- combined candidate CSV: `analysis/review/demo/demo_fixed_candidate_78_review.csv`;
- capacity report: `analysis/demo_fixed_candidate_78_capacity.json`;
- local-only feasibility DAT:
  `analysis/runtime_bisect/demo_fixed_candidate_78_unreviewed.dat`.

Do not copy the 78-row DAT to RomForge merely because it passes capacity. First
finish the 64-row runtime test, then verify the Japanese/English/Korean mapping
of each of the 14 additions in the focused page.

#### Codec context-review tooling

`mgs3d_script_compare.py codec-context` now enriches each conservative codec
anchor candidate with neighboring resources from the same GCX, an English
conversation key, and the number of duplicate raw resources. The generated
v3 files are `analysis/review/codec/codec_korean_context_review_v3.csv` and the self-contained
`analysis/html/codec/codec_korean_context_review_v3.html`. The current page contains 298 rows
with +/-4 candidate-resource context. This is intended to prevent repeats of
the `CIA JACK` false match by making local conversation context visible before
approval; it does not itself approve any mapping.

A second command, `export-codec-range`, now exports every resource in a chosen
GCX interval and overlays known translation and capacity-plan metadata. The
focused Major Tom artifacts are `analysis/review/codec/codec_gcx243_major_tom_review.csv`
and `.html`: 141 sequential string resources for GCX 243 resources 300..440,
with resources 366/367 marked as the corrected mandatory FPS targets and all
28 capacity-plan resources visibly marked. Only those two resources currently
have Korean text; the other 26 selected resources require verified mapping and
translation before safe-fixed production output is possible.

This is the authoritative resume point while the user is away.

#### Runtime result: 64-row fixed-layout probe passed

The user tested the 64-row fixed-layout `demo.dat` and reported normal
continued playback with no crash or stop. Korean subtitles appeared correctly
at many points throughout the tested span. The build was promoted to the
canonical local output and fully verified. The canonical DAT, runtime probe,
and RomForge staged DAT all have SHA-256
`44fa6fbba5dabfb4730e8272c1884ccec29c3f283f3a0a8660363646d8f15985`.

This supersedes the earlier instruction to test and conditionally promote the
64-row probe. The next demo expansion remains the unapproved 14-row extension;
review its mappings before staging the 78-row feasibility DAT.

Objective: finish a reliable personal-use Korean patching tool. There is no
deployment or public release task. The user performs RomForge repacking; Codex
prepares and verifies files under the known RomForge unpacked path.

Current RomForge input directory:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs`

Current staged files, rechecked immediately before this checkpoint:

- `codec.dat`: original, 37,141,696 bytes, SHA-256
  `932c0a13dd4a0a55213e0a2352b12a11b496a7216706838d0d044930789a344f`;
- `movie.dat`: earlier 47-line Korean draft, 268,384 bytes, SHA-256
  `a68600c55b1b74b54a9b903a88b9be596499401c558f080b0e374292bda9f88d`;
- `demo.dat`: new fixed-layout, one-row record-2 diagnostic, 773,007,360
  bytes, SHA-256
  `27feffc44fe74126224ed192bee365f4e945cfb683ec896346b4433ce1874178`.

At the original departure checkpoint no `.cci` existed and the fixed-layout
probe had not yet been repacked. The later runtime-result subsection above
supersedes that state: the probe now passes startup and its successful CCI is
present.

Runtime history and conclusion:

1. The original codec plus translated movie plus translated 94-row demo stopped
   during startup/opening playback.
2. Restoring only `demo.dat` to original made the game proceed. This isolated
   the failure to generated demo data; Japanese opening text in that control was
   expected and was not a translation-coverage finding.
3. Append-and-grow demo probes with 47, 23, and 11 accepted rows all stopped
   before the KONAMI logo.
4. A probe changing only record 2 entry 0 also stopped.
5. A different probe changing only record 4 entry 0 also stopped. Therefore the
   failure was not one bad Korean sentence or one special record: growing a demo
   record/file was sufficient to create a runtime-incompatible DAT even though
   the static parser accepted it.
6. The old append-and-grow algorithm must not be restored or used for testing.

Implementation now under test:

- `tools/mgs3d_movie_tool.py build-korean` uses `rebuild_record_fixed`.
- Page-3 tokens are decoded back to their 0..1019 font-slot indices.
- A slot is reusable only when it is referenced by a replaced subtitle and by
  no retained subtitle in the same record.
- Unique non-ASCII characters in the Korean replacement are assigned only to
  those safely freed slots.
- The translated encoded text must fit in the original entry text region.
- Existing entry headers, timing tails, entry sizes, record sizes, global file
  size, all later offsets, and unrelated bytes remain fixed.
- The builder stops with `fixed-layout font deficit` or
  `fixed-layout text deficit` rather than emitting an unsafe enlarged DAT.
- Tests are in `tests/test_movie_fixed_layout.py`; the complete suite currently
  reports 43 passing tests.

Exact next user test:

1. The initial fixed-layout repack/startup test is complete and passed: the
   KONAMI logo appeared.
2. Next calculate capacity for all 94 preliminary rows and build only the rows
   whose complete records satisfy both exclusive-font-slot and fixed-text-byte
   constraints.
3. The one-row probe has already displayed Hangul successfully. Test the next
   safe multi-record subset through the opening and across several changed and
   unchanged subtitles to catch record-specific issues.
4. On any later failed test, immediately delete every `.cci` below
   `C:\Users\hhlee\Desktop\Romforge\output`, restore the original demo backup,
   and investigate in-place byte semantics beyond size/offset preservation.
   Do not resume row bisection with append-and-grow outputs.

Failure cleanup command must resolve each target and keep it under the exact
RomForge output root before deletion. The known generated filename from the
last failure was
`C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack.cci`.
Original DAT backups remain in
`C:\Users\hhlee\Desktop\Romforge\output\backup_original_dat` and must not be
deleted.

## Matching correction

The earlier codec matcher accepted 21 rows from two shared Latin anchors. Runtime
screenshots proved that `CIA JACK` can map a Korean sentence to an unrelated
Japanese resource. The rule now requires at least three shared anchors and one
anchor unique in the English transcript. Re-running the 195,681 candidates keeps
299 rows for review and auto-accepts zero.

Use `analysis/review/codec/codec_korean_anchor_review_v3.csv`; do not use the old 21-row
automatic translation as production input.

## Next work

1. Build manually verified mappings for complete radio conversations or larger
   GCX groups, starting with the runtime-identified Major Tom tutorial group.
2. Translate enough resources in each GCX to free the required number of glyph
   slots; isolated lines normally have zero or too few safe slots.
3. Run `capacity` and require zero deficit for every changed GCX.
4. Build with `safe-fixed`, run the full verifier, repack with RomForge, and test
   Korean followed by untouched dialogue.
5. Keep movie/demo work separate. The new fixed-layout demo builder passes
   structural verification but is awaiting its first runtime result; do not
   describe it as runtime-safe until the current probe boots successfully.

## Repository handoff

This directory is not currently a Git repository. Generated/private content is
excluded in `.gitignore`, including `partition0`, `analysis`, `Citra`, `dist`,
game images, emulator binaries, and generated font previews. Initialize Git,
review the exact tracked file list, commit, and configure/push to the Gitea
remote only in a later explicit step.
