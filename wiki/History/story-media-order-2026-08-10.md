# movie/demo story playback-order extraction (2026-08-10)

## Required output

The target is story control-flow order, not physical DAT order:

```text
order,stage,script_file,script_offset,type(movie/demo),scene_id,
descriptor/resource_id,source_en
```

Repeated calls and conditional paths must remain separate rows. Physical record
order is used only to join a confirmed scene or descriptor to English text.

## Static asset audit

The extracted PS2 tree contains 156 stage directories, 156 `.02` files and 157
`.01` overlays. Every tested `.02` parses as the same GCX container family used
by the codec tooling. The corresponding 3DS RomFS contains 169
`stage/*/scenerio.gcx` files.

The `.01` overlays contain the media runtime, including
`ANewMpegPssMovieStrProg`, `CODEC_REQ_MOVIE_START`, `NewRadioMovie`,
`NewStreamIpuDriver`, and `NewDemoCamera`. This establishes loader ownership but
does not establish story order or a scene argument.

The old `tools-mgs/gcx-decompile.c` table identifies legacy GCL hash `0xA242`
as `demo`. A structured scan found no such hash in decrypted script resources
of either the PS2 `.02` files or the 3DS `scenerio.gcx` files. Apparent raw hits
occur in procedure/native regions and fail instruction-boundary and container
checks. They must not be reported as media calls.

The procedure areas are platform-specific executable/compiled code rather than
the legacy command stream expected by that decompiler. Consequently a simple
hash scan cannot produce a trustworthy call-order table.

## Confirmed opening runtime anchors

The 2026-08-10 controlled runtime test establishes this prefix:

1. demo scene 127, records 287..291: opening flight over Pakistan through
   `Spread your wings and fly! God be with you!`;
2. movie opening sequence: Sokolov explanation;
3. following parachute dialogue and landing transitions;
4. gameplay return and first codec call.

This is evidence for ordering, but it is not yet evidence for the exact stage
script offset or the movie scene/descriptor value. Unknown fields must remain
unknown rather than being inferred from DAT record zero.

`demo_scene_map.json` currently groups records 287..296 as scene 127. English
inspection disproves that boundary: records 292..296 contain unrelated The End
and combat dialogue, while the runtime-observed opening ends in record 291.
Padding-derived scene grouping is therefore provisional and cannot be used as a
story-order authority. `analysis/story_media_order/opening_runtime_anchors.csv`
contains the two confirmed opening-order anchors with unknown static fields
left explicit.

## Extraction method

Static control flow remains the preferred source for stage, branch and duplicate
call sites. Runtime instrumentation will supply the consumer PC and scene or
descriptor argument at each actual invocation. That PC is then mapped back to
the owning `scenerio.gcx` procedure and offset. The media parser joins the
confirmed ID to its English type-1 subtitle stream.

The next instrumentation must log only the movie/demo request boundary. Broad
RomFS-read logging is unsuitable: MGS3D uses a shared binary RomFS handle and the
earlier broad trace was noisy enough to trigger the diagnostic slow-memory/GPU
failure. The call-boundary log needs sequence number, PC/LR, r0-r3, stage name,
media type, and the selected scene/descriptor. Conditional and repeated runtime
occurrences are preserved verbatim.

## Confidence rule

A final row is `confirmed` only if a script call site and runtime-selected ID
agree, or if static decoding independently proves both. DAT physical order alone
is never sufficient. Rows based only on observed playback are retained as
runtime anchors and are not promoted to the requested final CSV.

## Manual alignment partial-order rule (2026-08-11)

The corrected V6 review state contains 59 Korean text overrides. Thirty-two
relations also have an exact normalized match between their bundled 3DS and
PS2 English. These have been promoted to `safe_manual_anchor`; they cover 15
media groups.

The anchors support this limited ordering rule:

1. `movie` and `demo` are separate monotonic streams.
2. Within either stream, increasing group and subtitle offset normally
   correspond to increasing PS2 English sequence.
3. Several 3DS cards may map to one PS2 row, but their internal offset order
   remains monotonic.
4. The two streams must be merged by PS2 sequence or runtime evidence, not by
   comparing physical offsets or group numbers.
5. Demo group 127 is a known wraparound exception: it is physically near the
   end of `demo.dat`, while runtime evidence fixes it at the story opening
   before movie group 0.

All 32 safe anchors are monotonic within their groups. Expanding the audit to
156 relations with exactly matching complete English bundles covers 37 groups.
Only one within-group inversion remains: movie group 0 places PS2 sequence 40
after the long sequence-43 bundle. That relation is already `suspect` and is
not an order anchor. The only large inversion in the complete demo physical
stream is the known group-127 opening wraparound.

### Anchor-sandwich constraint

An unanchored group between two safe anchors of the same media type is limited
to the open PS2-sequence interval between them:

```text
previous safe-anchor sequence
    < unanchored group candidate sequence
    < next safe-anchor sequence
```

This is an `order_bounded` inference, not runtime confirmation. It may reject
out-of-range text matches, but cannot prove branch selection, repeated
playback, or optional radio calls.

Current demo bounds are:

| 3DS group range | PS2 story-sequence bound |
| --- | --- |
| 127 | opening, sequence 1 onward; explicit wraparound exception |
| 2 | anchors 58..68 |
| 3..11 | after 68 and before 255 |
| 12 | anchor 255 |
| 13 | anchors 284..298 |
| 14..17 | after 298 and before 347 |
| 18 | anchor 347 |
| 19..21 | after 347 and before 420 |
| 22 | anchors 420..421 |
| 23 | after 421 and before 474 |
| 24 | anchors 474..485 |
| 25 | anchors 504..507 |
| 26..35 | after 507 and before 652 |
| 36 | anchors 652..654 |
| 37..59 | after 654 and before 859 |
| 60..61 | anchors 859..871 |
| 62..74 | after 871 and before 1104 |
| 75 | anchor 1104 |
| 76..92 | after 1104 and before 1250 |
| 93 | anchor 1250 |

Current movie bounds are:

| 3DS group range | PS2 story-sequence bound |
| --- | --- |
| 0 | approximately 17..45; sequence-40 suspect relation excluded |
| 1 | after 45 and before 365 |
| 2 | anchors 365..375 |
| 3 | after 375 and before 662 |
| 4 | anchor 662 |

The current cross-stream partial order is therefore:

```text
demo 127 opening
  -> movie 0 Virtuous Mission briefing
  -> demo 2
  -> demo 3..13
  -> demo 18
  -> movie 2
  -> demo 22..36
  -> movie 4
  -> later demo groups
```

Derived rows use separate confidence labels:

- `runtime_confirmed`: observed runtime precedence;
- `anchor_confirmed`: corrected Korean plus exact bundled English;
- `order_bounded`: constrained between two same-stream anchors;
- `text_matched`: text match that also satisfies its order bound;
- `branch_unresolved`: chronological range known, branch/repetition unknown.

These rules clarify story placement and constrain future matching, but do not
replace static or runtime control-flow evidence.

### V6.4.1 corrected 3DS Korean application (2026-08-11)

The V6.4.1 translation-fixed review tool and its correction exports were
adopted as the current workspace baseline. They use dataset key
`130a1b2b44c7dddb` and review state timestamp
`2026-08-11T09:55:49.604Z`.

- 186 row-ID-based 3DS Korean corrections were applied;
- all 186 JSON corrections equal the CSV values and embedded HTML row values;
- no correction ID is missing and no corrected value differs;
- the embedded review state preserves 313 relations: 306 matches and 7 holds;
- the standalone review JSON is byte-semantically identical to the state
  embedded in the canonical HTML.

Canonical artifacts are under `analysis/story_media_order/html/`:

- `mgs3_manual_nm_alignment_review_v6.html`;
- `mgs3_manual_nm_alignment_review_v6_4_1_translation_fixed.html`;
- `mgs3d_manual_alignment_review_v6.json`;
- `mgs3d_3ds_korean_corrections_v1.csv`;
- `mgs3d_3ds_korean_corrections_v1.json`.

The correction CSV/JSON, rather than the old shifted Korean bundles in merge
relations, is authoritative for these 186 3DS rows.

### RomForge application (2026-08-11)

The 186 corrected rows were mapped from review offsets to the current live DAT
offsets by stable `(media, record, entry)` identity. This was necessary because
all 47 movie offsets and 118 of 139 demo offsets differed from the review
offsets after earlier record growth/reflow.

The current live RomForge files were used as build bases so existing Korean
content was retained. A grow-record rebuild changed only the selected type-1
subtitle entries. Byte comparison verified that all 3,433 unselected movie
entries and all 11,157 unselected demo entries were preserved.

Before replacement, both live files were copied to:

```text
C:\Users\hhlee\Desktop\Romforge\output\backup_before_story_translation_v1_20260811_1930
```

The verified outputs were then installed under:

```text
C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs
```

Hashes, sizes, counts, and recovery paths are recorded in
`analysis/story_media_order/romforge_apply_v1/apply-manifest.json`.

### Pristine-base release rehearsal (2026-08-11)

A separate rebuild was tested against untouched English RomFS files, without
using the already-modified live RomForge DATs. Required source identities are:

| file | size | SHA-256 |
| --- | ---: | --- |
| `movie.dat` | 229,376 | `745fef1e55af881e8594c8b25d2b8487f8aac54418573e943d86ac95f44a72b6` |
| `demo.dat` | 772,935,680 | `e216f28fb8792ce911e96eee3fc14760184388713358eb21ca4d32a168285468` |

All 186 corrections resolved against the pristine `(record, entry)` structure,
and all available source English checks matched. The outputs reparsed with 108
movie records/3,480 entries and 333 demo records/11,296 entries. No unselected
subtitle entry changed.

Release packaging is prepared as a rebuild patch: correction CSV/JSON, strict
source/output hashes, and instructions, without distributing proprietary DAT
files. The package staging is `dist/story_translation_patch_v1/package/` and
the tested output metadata is in `dist/story_translation_patch_v1/release-manifest.json`.
Runtime playback is deliberately still marked untested pending explicit user
approval for that separate validation step. `codec.dat` is excluded.

#### Runtime rejection and clean rollback

The grow-built correction artifact failed at the first Pakistan-overflight
video: the video did not begin and the game stalled. Static reparse and
unchanged-entry checks were therefore insufficient to qualify this build.
Both live RomForge files were rolled back to the pristine English baseline:

- `movie.dat`: `745fef1e55af881e8594c8b25d2b8487f8aac54418573e943d86ac95f44a72b6`;
- `demo.dat`: `e216f28fb8792ce911e96eee3fc14760184388713358eb21ca4d32a168285468`.

The failed artifact is retained only for diagnosis and is marked
`rejected_do_not_release`. Future work starts from these pristine DATs and must
not promote a structurally valid build without a separately approved runtime
test.

## Runtime boundary investigation

Targeted RomFS reads established the real opening media blocks without using
DAT order as story order:

- demo scene 127 read: demo file offset `0x26103700`, covering record 287 at
  `0x26108C30`; completion PC/LR `0x00837018/0x00836524`;
- following movie read: a `0x10000` aligned block beginning `0x1120` before the
  confirmed movie base; the same common asynchronous FS completion chain was
  used.

The completion stack is an archive worker chain (`0x001520B8 -> 0x00132EA4 ->
0x0014FF00 -> 0x0011A834`) and is not the story command caller. It is useful for
proving which data was read, but must not be reported as the movie/demo request
PC.

Targeted inspection of the decompressed 3DS command registration tables found
that commands use the project's 24-bit string hash, not the legacy 16-bit
constant:

- `strcode24("demo") = 0x33A20F`, registered handler `0x00409DB0`;
- `strcode24("movie") = 0x09658C`, registered handler `0x0079F6B4`;
- checks: `strcode24("if") = 0x0D86` and `strcode24("eval") = 0x34648C`
  match entries in the same table.

The demo handler calls the generic argument decoder at `0x0022F35C`; the first
decoded value is available at `0x00409DD0`. The movie handler has the analogous
point at `0x0079F6C0`. A runtime hit at `0x00409DD0` produced `r0=0x10000000`,
but it occurred around six seconds into startup, before scene 127 was read.
It is therefore an initialization command and is not a scene-127 ID.

The attempted GDB breakpoint and instruction-substitution probes are rejected
as evidence. Both perturbations reproducibly reached an unrelated invalid GPU
address (`0x2888E4E4` at guest PC `0x00161470`) and Vulkan assertion at roughly
50 seconds. Repeating those probes would only ask the user to replay a known
unstable diagnostic. Azahar was restored to upstream Dynarmic/FS code and GDB
was disabled after the tests.

The next safe approach must observe the argument decoder without pausing or
substituting a guest instruction—for example, a host-side Dynarmic IR callout
that preserves the translated ARM instruction exactly, validated first against
an uninstrumented runtime hash/trace. Until then, neither `r0=0x10000000` nor
the registered `movie` handler is promoted to a story scene mapping.

### Non-invasive tick-marker probe

A replacement probe was compiled in the external Azahar worktree. Dynarmic's
existing per-instruction tick callback marks translated blocks containing
`0x00409DD0` or `0x0079F6C0`. At the normal block-end tick callback it removes
the marker before updating emulated time and logs PC/LR plus r0-r12. It neither
replaces a guest instruction nor pauses execution, writes guest memory, or
changes the effective tick count. Runtime output is not evidence until this
build completes the opening path without the prior diagnostic crash.

The runtime validation failed: with the ROM path correctly passed, Azahar
terminated about 5.7 seconds after boot, before a usable media event was
recorded. The tick-marker patch was removed and the stable bundle rebuilt.
This probe is rejected as evidence and must not be retried.

Static disassembly supplies a safer next boundary. The `movie` handler calls
the common argument reader at `0x0022F35C`, stores its return value at offset
`+4` of the global request object, and writes request type `5` at offset `+0`.
The `demo` handler preserves the same reader's first return value in `fp` and
passes it unchanged to `0x004449CC` and as argument r3 to `0x004BC2DC`.
Both therefore consume the tagged value decoded by `0x00171C7C`; they do not
accept a plain DAT record offset directly. The decoder dispatches on the high
nibble of the script byte and handles 1-, 2-, 3-, and 4-byte immediates plus
string/reference forms. Reconstructing this decoder for `scenerio.gcx` is now
the preferred route to a static call-site scanner.

### First static 3DS call extraction

`tools/mgs3d_story_media_calls.py` implements the constant subset of the
tagged argument decoder and scans only the procedure region of each parsed
`scenerio.gcx`. The 3DS `demo` hash occurs in a consistent little-endian
24-bit command frame with marker `0x06` or `0x64`; the two marker families
account for 150 and 67 calls respectively. The scan produces 217 `demo`
candidates across 71 stages, including repeated calls, and zero `movie`
command frames. The first argument forms are 150 24-bit immediates and 67
compact constants.

The zero `movie` result is meaningful but not yet proof of playback semantics:
the observed Sokolov movie may be selected by the `demo` request machinery or
by a downstream scene transition. The candidate rows therefore retain
`static_structural_candidate` confidence, leave `scene_id` empty, and expose
the decoded first value as `record_id/descriptor`. Physical DAT order is not
used. Output is
`analysis/story_media_order/static_media_call_candidates.csv`.

The scanner and its tests compile successfully. Direct decoder assertions
cover the observed 24-bit immediate, compact constants, unresolved dynamic
forms, and both command markers. The local Python environment does not contain
pytest, so the focused assertions were executed directly rather than reporting
a pytest suite result.

### Descriptor ownership

The first `demo` argument is now tied to a real file namespace. The handler
calls `0x004449CC` with type `5`; that function preserves the low 24 bits and
places `5` in the high byte. The generic loader's type table maps index `5`
directly to `demo.dat` (the neighboring entries resolve to `stage.dat`,
`codec.dat`, `bgm.dat`, `movie.dat`, `vox.dat`, and `slot.dat`). Candidate rows
therefore include both the decoded low-24 value and the packed
`0x05xxxxxx` file descriptor.

This does not yet make the low-24 value a byte offset or scene ID. Multiplying
it by the codec-style `0x10` unit does not reproduce demo scene starts, and
interpreting its tagged payload as a GCX resource offset produces unrelated
string interiors. Both shortcuts are rejected. The descriptor must be followed
through the generic demo.dat resource resolver before joining it to scene 127
or any physical record range.

### Demo resource-name mapping

The PS2 `.02` files use the same 24-bit `demo` command frame, not the legacy
16-bit hash. A scan parses all 156 files and finds 139 calls; matching stages
retain identical tagged descriptors across PS2 and 3DS. For example,
`s000a_0` uses `0x003BC006` and `0x003CA006` on both platforms. This establishes
that the low-24 value is a cross-platform story resource identifier rather
than a 3DS physical file offset.

The 3DS RomFS supplies the missing dictionary in
`sound/table/sddemotable.txt`. A named entry is encoded as:

```text
((strcode24(resource_name) & 0xFFFF) << 8) | 0x06
```

Original case is significant. This rule maps 146 of 150 u24 calls. Compact
arguments 0..3 map through the table's numeric IDs. Overall, 213 of 217 static
calls now have a demo-table ID and resource name: 178 are unique exact rows,
35 retain all colliding/aliased names, and four title-stage special values
remain unresolved.

The table's numeric ID is recorded as `demo_table_id`, not `scene_id`.
Those namespaces demonstrably differ: opening resource `v020_010_p010` has
table ID 0, while the provisional padding-derived map called its physical
opening region scene 127. Until the physical demo.dat resolver is proven,
`scene_id` remains empty. This prevents the known-bad scene map from silently
re-entering the result.

## Movie namespace and static placement

The generic loader's filename table maps namespace/type index `3` to
`movie.dat` (neighboring index `5` is `demo.dat`).  The `5` written by the
registered movie handler at `0x0079F6B4` belongs to the separate media request
queue and must not be interpreted as the generic loader namespace.

All 169 3DS `scenerio.gcx` files were scanned with the same structurally
framed command rule used for demo. They contain zero explicit `movie` command
frames. The PS2 `.02` corpus has two such frames, in `s221a_0` and `s223a_0`,
but neither has a matching 3DS frame. Therefore an explicit movie call list
cannot honestly be manufactured from the 3DS command hash.

There is no movie equivalent of `sddemotable.txt` under `sound/table`. The HD
manifest `analysis/pt_br_hd_remaster_reference/filelist.txt` does provide a
separate `us/movie/_bp` namespace containing ten movie resource names. Tests
of the demo descriptor formula, the full 24-bit name hash, and raw resource
names found no structurally valid movie call mapping in the 3DS scenario
procedures. A lone byte hit for the demo-style formula of `m010_020_m010` is
the beginning of another command hash (`06 00 bc 05`), so it is rejected as a
coincidence. `record_id/descriptor`, `packed_file_descriptor`, and
`movie_table_id` consequently remain blank.

`tools/mgs3d_story_movie_map.py` instead performs a narrower, labelled
placement. It inserts a known movie name only when its sequence number lies
uniquely between two already mapped demo resources in the same stage and
procedure. Nine of ten names satisfy that rule. For each of those nine, the
two bounding demo descriptors also occur in the matching PS2 stage, providing
cross-platform confirmation of the anchors—not of a movie descriptor. These
rows use confidence `static_sequence_gap_inference` and are written to
`analysis/story_media_order/static_movie_call_candidates.csv` in columns
compatible with the demo output, with extra evidence-boundary columns.

`v020_020_m010` crosses the opening stage boundary and has no unique
same-procedure pair. It is retained as `resource_name_only`, without an
invented stage, procedure, call order, or descriptor. Runtime/outer
stage-control evidence is still required to promote any sequence-gap row to
an actual call site. Physical `movie.dat` record order and old scene-number
maps were not used.

## Integrated story-media order and dialogue join

`tools/mgs3d_story_media_order.py` now combines all 217 demo calls and ten
movie resources into `analysis/story_media_order/story_media_order.csv`.
Repeated calls are retained. Within a procedure the original script offsets
and call order are preserved; inferred movies are inserted only between their
recorded bounding demo calls. Mission stages are ordered `v*` then `s*`, with
stage/procedure order exposed rather than pretending conditional calls form a
single unconditional playthrough.

The first integration pass reports 227 rows: 151 have a same-stage PS2
resource anchor, 168 have an HD filelist resource, and 101 non-collision rows
have both. Thirty-five hash/alias collision rows retain every candidate.
These are resource-identity matches, not dialogue-boundary matches.

Dialogue is deliberately more conservative. Only the runtime-confirmed
Pakistan opening boundary and the immediately following `v020_020_m010`
movie are promoted. The two colliding opening demo names remain separate call
rows but share one explicitly labelled unresolved p010/p011 dialogue boundary.
The verified English/Korean opening text comes from the English transcript and
the reviewed Korean reference dialogue data. This produces three call rows with a
dialogue start and leaves 224 for manual/resource-boundary review. The latter
are written separately to
`analysis/story_media_order/story_media_order_manual_review.csv`; aggregate
counts are in `story_media_order_summary.json`.

This low dialogue-match count is intentional. Existing movie/demo alignment
CSVs attach English and Korean to DAT records, but do not identify a resource
name, and the known physical demo scene map is unreliable. Record number or
DAT order alone is therefore insufficient to copy those translations into a
resource row. The next safe matching pass must establish named SDT/resource
boundaries or use additional runtime boundaries, then use English similarity
to validate the join.

## Story-sequence English/Korean join

The matching direction was changed to use story and transcript sequence before
attempting complete DAT resource boundaries. `tools/mgs3d_movie_sequence_match.py`
first combines consecutive 3DS subtitle cards and matches them to whole PS2/HD
English transcript lines. `tools/mgs3d_story_sequence_join.py` then promotes a
match only when either (a) two or more consecutive cards form one exact
transcript line, or (b) two or more unique English/Korean candidates form a
monotonic sequence run inside the same structural media segment. The upstream
PS2 English/Korean alignment confidence is retained; isolated fuzzy/single-line
candidates are not promoted.

Across 2,939 English type-1 movie/demo subtitle rows, 462 are now automatic
context matches (15.72%): 15 movie and 447 demo. Of these, 174 are multi-card
exact matches with non-empty Korean output and 288 are supported by a
multi-line monotonic context run. The remaining 2,477 rows stay as explicit
gaps. Seventeen opening rows also
carry the runtime-confirmed `v020_010_p010/p011` or `v020_020_m010` resource
anchor; other matched dialogue rows deliberately leave `resource_id` blank
until adjacent resource anchors remove ambiguity.

Outputs are `story_sequence_korean_matches.csv`, `story_sequence_gaps.csv`,
and `story_sequence_summary.json` under `analysis/story_media_order/`. This is
a candidate mapping layer only. It does not modify the translation CSVs or
replace any Qwen text.

## Sequence-first monotonic DP pass

`tools/mgs3d_story_sequence_dp.py` reverses the earlier lookup direction. It
starts from each media segment having at least two ordered English-sequence
anchors, constrains that segment to the anchor's PS2 transcript window, and
then computes a monotonic dynamic-programming alignment. Transitions support
up to six 3DS cards against up to three PS2 transcript lines, plus explicit
card/script gaps. Backward sequence movement is impossible in the DP graph.
String similarity contributes to the score but cannot select text outside the
anchored story window. Single 1:1 promotion still requires 0.84 similarity;
N:M context requires 0.72 and a multi-item transition.

The previous 2,477 gaps break down as follows:

- 246 (9.93%) are confirmed split/merge cases;
- 2 (0.08%) are modified English expression matches;
- 1,117 (45.09%) remain additions/deletions or insufficient text matches
  inside a valid anchored window;
- 1,112 (44.89%) belong to segments without two reliable ordered anchors and
  are retained as anchor/order-risk review rows.

The DP pass adds 248 high-confidence rows to the earlier 462, for 710/2,939
(24.16%). Added relations are 36 1:1, 190 PS2 1-to-3DS-N, zero PS2-N-to-3DS-1,
and 22 N:M rows. Gaps fall from 2,477 to 2,229. Outputs are
`story_sequence_dp_matches.csv`, `story_sequence_dp_review.csv`, and
`story_sequence_dp_summary.json`. These remain mapping evidence only; no
translation/Qwen source file is modified.

## Confirmed-match anchor expansion

The next pass keeps the DP graph, similarity function, and promotion thresholds
unchanged. Instead, it feeds all 710 previously confirmed mappings back into
their structural movie/demo segment as sequence anchors. This adds 442 unique
`(segment, DAT offset, English sequence)` anchor points. The count of populated
media segments with at least two locally monotonic anchors rises from 50 to 57
(7 newly eligible segments). No anchor is inferred from DAT physical order,
`scene_id`, a hash collision, or English fuzzy similarity alone.

With the same monotonic DP, 25 more rows are promoted: 6 one-to-one and 19
PS2-one-to-3DS-many relations. The confirmed total becomes 735/2,939 (25.01%),
and gaps fall from 2,229 to 2,204. Anchor/order-unresolved rows fall from 1,112
to 985, a reduction of 127. The expanded outputs are
`story_sequence_dp_expanded_matches.csv`,
`story_sequence_dp_expanded_review.csv`, and
`story_sequence_dp_expanded_summary.json` under
`analysis/story_media_order/`.

After anchor expansion, 1,219 rows remain unmatched inside anchored windows.
The unchanged DP diagnostics divide them into 73 transitions proposed by the
monotonic path but below the existing automatic threshold, 1,122 explicit card
gaps chosen by the DP, and 24 rows whose Korean N:M partition was empty. These
are review categories, not newly accepted translations. The Qwen/application
CSVs remain untouched.

## Post-release TODO: shared Hangul glyph allocation

Finish the movie/demo patch with the existing record-local glyph path first.
After the patch is complete, investigate a shared/global Hangul glyph page to
remove duplicate 64-byte glyph bitmaps across records. The existing
`build-korean --static-allocation` support can emit references to a stable
allocation, but it must not be used in a release until the corresponding
shared font data is installed at runtime and its loading/addressing behavior is
confirmed. Revisit this primarily for low-padding demo scenes such as 13 and
36; it is a later capacity optimization, not a blocker for the current
translation-review workflow.

### Capacity-edit ledger and final reminder

- Treat every capacity-oriented movie/demo translation change supplied from
  this point onward as an incremental override. Accumulate it on top of all
  earlier scene edits; never regenerate a build from only the newest change
  CSV and thereby discard previous shortening work.
- The current capacity-edit series starts with the shortened baseline
  translations for all scenes that exceeded their local budget. The explicit
  `mgs3d_scene13_36_v643_changes.csv` file is one revision in that cumulative
  series, not a standalone complete translation set.
- Build inputs must be produced by merging the canonical reviewed translation
  set with every later capacity-edit CSV in chronological order. For duplicate
  IDs, the newest `new_korean` value wins. Keep the source CSVs as an audit
  trail.
- A successful boundary-preserving RomForge build is not the end of the text
  work. After the shared/global Hangul glyph patch is implemented, recalculate
  every scene budget and make one final translation pass, restoring natural
  Korean where capacity-driven abbreviations or mixed English/Korean wording
  are no longer necessary.
- **Required handoff reminder:** when the final movie/demo build succeeds,
  explicitly tell the user that the shared-glyph patch and the post-patch
  translation readjustment remain on the TODO list.
