# MGS3D English-to-Korean pivot handoff — 2026-08-02

## Current direction

The Japanese glyph-reconstruction path was abandoned for production.  The active
plan uses the Western/English release, matches its decoded English strings to the
Korean transcript, and replaces those strings with Korean while **never changing
the size of codec.dat, movie.dat, demo.dat, or any contained record**.

The Japanese unpack remains only as a backup/reference at:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked_metagear_jpn`

Do not reuse Japanese resources in the English production build unless the user
explicitly changes direction.

## Authoritative source and RomForge state

English unpack/repack root:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs`

Original English DAT backup:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked_en_original_smoke_backup\partition0\romfs`

Original English hashes and sizes:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| codec.dat | 67,204,976 | `DD6EA4B80F194951BCBB0F584ABB6B5F96D043E8C3AB78C4EC0C4236982374EA` |
| movie.dat | 229,376 | `745FEF1E55AF881E8594C8B25D2B8487F8AAC54418573E943D86AC95F44A72B6` |
| demo.dat | 772,935,680 | `E216F28FB8792CE911E96EEE3FC14760184388713358EB21CA4D32A168285468` |

Current RomForge staging state:

- `codec.dat` is the **four-location one-character runtime smoke**, hash
  `D8E33316DB4308FDC62DD653BB71E71FF30B505A9B0032A3B07B02E1D9FE2CD8`.
- `movie.dat` and `demo.dat` are the untouched English originals.
- The large candidates described below are **not staged**.

## Proven runtime result

The first growing-record smoke froze because all three DAT files grew.  They were
restored from backup.  File/record size growth is prohibited from now on.

A size-neutral codec smoke changed all four copies of `Do you copy?` at GCX
15/17/51/53 resource 14 to one Korean glyph, `한`.  The user repacked and confirmed
that `한` rendered in game.  This proves:

- the Western renderer accepts the embedded custom-glyph token;
- Malgun Gothic rendered 16x16 2bpp glyphs work;
- shrinking strings to fund embedded glyph bytes works at runtime;
- fixed file and GCX sizes avoid the earlier freeze.

Smoke input/output:

- `analysis/en_codec_fixed_size_smoke_translation.json`
- `analysis/en_codec_fixed_size_smoke.dat`
- `--preserve-file-size` in `tools/mgs3d_gcx_font_tool.py`

## English-first dialogue review

Combined offline reviewer:

[`analysis/html/EN/index.html`](../analysis/html/EN/index.html)

It combines codec/movie/demo, groups duplicate physical locations by English
sequence, and supports:

- Enter: confirm and advance
- Ctrl+Enter: mark corrected and advance
- U/S: unresolved/unsupported and advance
- left/right: previous/next pending
- current-card highlighting, large decision buttons, notes, CSV download

Review artifacts:

- `analysis/html/EN/confirmed_dialogue_all.csv`: user-supplied/exported result;
  21,590 physical rows, 840 groups, all marked confirmed.
- Comparison against the original matcher showed 705 groups were actually edited,
  while 135 were unchanged.
- `analysis/html/EN/confirmed_dialogue_second_pass.csv`: provenance-restored copy;
  705 corrected, 130 confirmed, five groups reset to pending.
- `analysis/html/EN/second_pass.html`: focused second-pass reviewer.

The five pending groups are EN-78, EN-102, EN-181, EN-333, EN-464:

- EN-78: large semantic difference
- EN-102: `take care of myself` meaning
- EN-181: `드게` likely typo for `듣게`
- EN-333: first-clause semantic drift
- EN-464: likely next-sentence boundary spill

No newer second-pass browser export existed at handoff time.  Check
`analysis/html/EN` and Downloads before proceeding.

## Matcher and build-input conversion

Matcher outputs:

- `analysis/en_codec_korean_matches.csv`
- `analysis/en_movie_korean_matches.csv`
- `analysis/en_demo_korean_matches.csv`

The combined accepted review currently converts to:

- codec: 21,070 physical targets
- movie: 51 targets
- demo: 457 targets
- duplicate target conflicts: zero

Converter:

`tools/mgs3d_english_review_to_build.py`

Generated inputs:

- `analysis/english_bulk_candidate/codec_translation.json`
- `analysis/english_bulk_candidate/movie_translation.csv`
- `analysis/english_bulk_candidate/demo_translation.csv`

It normalizes smart punctuation to renderer-safe ASCII and proportionally
preserves source line counts.

## Size-neutral codec bulk candidate

`tools/mgs3d_codec_size_neutral_select.py` computes per-GCX string savings versus
64-byte unique Hangul glyph cost.  Embedded glyphs alone fit only one translation,
because Western GCXs have no existing Korean slots.

The selector now has a conservative `--reclaim-non-english` mode.  It clears
confidently classified Spanish/French/German/Italian noncandidate strings inside
the same GCX and uses that space for Korean glyphs.  `--protect-review` prevents
every matcher-identified English target, including pending rows, from becoming a
donor.

Protected selection result:

- 20,109 / 21,070 translations selected
- 123,805 non-English donor resources
- 399 / 544 candidate GCXs contain selected translations
- built DAT changes 486 GCXs and embeds 21,669 glyph instances
- output size remains exactly 67,204,976 bytes
- all 2,326 GCXs and 601,657 resources reparse successfully

Candidate (not staged, not runtime-tested):

`analysis/english_bulk_candidate/codec_fixed_size_reclaim_protected.dat`

SHA-256:

`5B7AEC7B950662E9C95C534E17E90400268A2EED1FB8ABA77679B8B7A4329106`

Selection/report inputs:

- `analysis/english_bulk_candidate/codec_selected_reclaim_protected.json`
- `analysis/english_bulk_candidate/codec_selection_reclaim_protected_report.json`

Important: the donor count is large.  Structural verification passed, but the
language classifier/donor policy needs an audit and a small runtime batch before
staging the full codec candidate.  Do not present this as production-ready yet.

Reproduction:

```powershell
$romfs = 'C:\Users\hhlee\Desktop\Romforge\output\unpacked_en_original_smoke_backup\partition0\romfs'
python tools/mgs3d_codec_size_neutral_select.py `
  (Join-Path $romfs 'codec.dat') `
  analysis/english_bulk_candidate/codec_translation.json `
  analysis/english_bulk_candidate/codec_selected_reclaim_protected.json `
  --report analysis/english_bulk_candidate/codec_selection_reclaim_protected_report.json `
  --reclaim-non-english `
  --protect-review analysis/html/EN/confirmed_dialogue_second_pass.csv
python tools/mgs3d_gcx_font_tool.py build-korean `
  (Join-Path $romfs 'codec.dat') `
  analysis/english_bulk_candidate/codec_selected_reclaim_protected.json `
  C:\Windows\Fonts\malgun.ttf `
  analysis/english_bulk_candidate/codec_fixed_size_reclaim_protected.dat `
  --preserve-file-size
```

## Size-neutral movie result

`tools/mgs3d_movie_tool.py` now has `--size-neutral-reclaim`:

- preserves type-1 English targets;
- clears entry types 2–5 in changed records as donor languages;
- selects a deterministic fitting Korean subset;
- appends record-local page-3 glyphs;
- pads each record back to its exact original size;
- verifies output file size and every record offset/size.

Current movie result:

- 40 / 51 translations selected
- 108 records reparsed
- file size remains exactly 229,376 bytes

Candidate (not staged, not runtime-tested):

`analysis/english_bulk_candidate/movie_fixed_size_reclaim.dat`

SHA-256:

`8E6F5FBC26976B60DC56C90C4A869D88EF4990891718F9FE39FD25F3BAC4BCEE`

Command:

```powershell
python tools/mgs3d_movie_tool.py build-korean `
  (Join-Path $romfs 'movie.dat') `
  analysis/english_bulk_candidate/movie_translation.csv `
  C:\Windows\Fonts\malgun.ttf `
  analysis/english_bulk_candidate/movie_fixed_size_reclaim.dat `
  --size-neutral-reclaim
```

## Demo status

The demo input contains 457 accepted targets.  The old empty-slot capacity path
reported 0 because Western records contain no embedded font slots.  The new
`--size-neutral-reclaim` implementation should handle it like movie, but the
773MB demo build had **not yet been run at handoff time**.

Next command:

```powershell
python tools/mgs3d_movie_tool.py build-korean `
  (Join-Path $romfs 'demo.dat') `
  analysis/english_bulk_candidate/demo_translation.csv `
  C:\Windows\Fonts\malgun.ttf `
  analysis/english_bulk_candidate/demo_fixed_size_reclaim.dat `
  --size-neutral-reclaim
```

Expect high memory use because the current parser loads the roughly 773MB file
and reparses the complete output.

## False lead closed

`romfs/ui/font.la2` is byte-identical between English and Japanese and contains
14 BCFNT UI fonts.  Its CMAPs are ASCII/sparse UI icon maps, not the dialogue
static Japanese pages.  The temporary `tools/mgs3d_la2_font_tool.py` and PNGs in
`analysis/english_bulk_candidate/` were diagnostic only.  Do not use font.la2 as
the production dialogue-font solution without new runtime evidence.

## Tests and verification caveat

Earlier in the session, before the latest size-neutral donor changes, the main
suite passed 71 tests and the matcher suite passed five.  The default Python
later reported that `pytest` was not installed, so the newest changes have only
been checked with `py_compile`, actual builders, full structural reparsing, size
checks, offset checks, and the one-character runtime smoke.  Re-establish the
project test interpreter and run the complete suite before production staging.

## Immediate next steps

1. Look for a completed browser export from `second_pass.html`; if present,
   regenerate build inputs from it.  Otherwise finish the five pending groups.
2. Run the demo size-neutral build and verify exact size/record offsets.
3. Add focused unit tests for codec donor padding and movie/demo
   `--size-neutral-reclaim` selection/padding.
4. Audit codec donor classification.  Produce counts and samples per inferred
   language; prove no English target/resource is cleared.
5. Create a deliberately small multi-line runtime batch (codec plus movie, then
   demo separately), not the full candidates.  Back up and stage one DAT class at
   a time.
6. Only after those runtime checks, stage the full fixed-size candidates and
   repack.

Never stage a DAT whose byte size differs from the corresponding original.

## 2026-08-02 final review and bulk-build update

The second-pass review is complete.  The user made exactly one correction:

- EN-181: `드게` -> `듣게`

EN-78, EN-102, EN-333, and EN-464 were explicitly confirmed as written.  The
authoritative review export is now:

`analysis/html/EN/confirmed_dialogue_final.csv`

It contains 840 fully decided groups (706 `corrected`, 134 `confirmed`, zero
pending, blank, unresolved, or unsupported groups) representing 21,590 physical
rows.  `analysis/html/EN/final_review.html` is the corresponding reviewer.

Fresh build inputs generated from that final CSV contain:

- codec: 21,082 physical targets
- movie: 51 targets
- demo: 457 targets

The final fixed-size builds were each run twice from the original English DATs.
Each A/B pair is byte-identical:

- codec: 20,208 / 21,082 selected, 67,204,976 bytes,
  SHA-256 `AD85D951C097F093AA40FCA8F6279623063EEA9891B44C556B4C5F04C552477F`
- movie: 40 / 51 selected, 229,376 bytes,
  SHA-256 `8E6F5FBC26976B60DC56C90C4A869D88EF4990891718F9FE39FD25F3BAC4BCEE`
- demo: 323 / 457 selected, 772,935,680 bytes,
  SHA-256 `EC0DC24CAF2F9544F2A69B4340A49923BA0862AE6A86846727C5CA69223C0443`

Determinism also covers the intermediate selection/allocation metadata, not
only the final DAT bytes.  The A/B metadata hashes match:

- codec selected JSON: `3A13002CFEE6482BACCC4DB9E4B18D7087AEC7AB097EB87F77715B288A17988D`
- codec selection report: `29B9E61ABF8D452A03351F1BB79AE6AD474978A3A08FC18050F5F04F17EBFD9E`
- codec glyph allocation: `D9392B0D489FF99A90F5F0EA10C88C10003CECD24773A06DD354389179D1913D`
- movie glyph allocation: `AA60A2896720175B47C4AF9570139B48B135F7C3EF6C44C68376176089057C6A`
- demo glyph allocation: `4BCDE0255E39F090665A8BF20C355275DBED4F619B412B8DEA40B4244FC766DB`

Canonical generated files are under `analysis/english_bulk_final/`.  The codec
donor audit covers 147,878 Spanish/French donor resources, with zero overlap
against all 21,082 protected English review targets and zero classification
failures.  The complete `unittest` suite passes 76 / 76 tests.

The first small multi-line codec batch did not crash, but the user saw English.
Inspection showed that the installed DAT hash exactly matched the intended
batch; the batch simply selected later lines such as `"스네이크"?`, `왜?`, and
`무슨 뜻이지?`, rather than the opening `Do you copy?` line being observed.
This result does not disprove Korean rendering: the earlier exact-size
`Do you copy?` -> `한` smoke rendered successfully.

The final bulk codec candidate is currently staged at:

`C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/codec.dat`

Its staged hash is the codec hash above and its size is unchanged.  The staged
movie and demo remain byte-identical to the original English files.  Await the
user's repack/runtime result for this codec-only bulk test before staging either
movie or demo.  If codec passes, test movie alone next while preserving the
validated codec, then demo alone last.  Never stage all three untested classes
at once.

## Worktree warning

The worktree was already dirty and contains many user/session files.  Do not
reset or discard unrelated changes.  No commit was requested or created.
