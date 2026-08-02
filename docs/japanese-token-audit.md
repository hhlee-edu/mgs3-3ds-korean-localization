# MGS3D Japanese token reconstruction audit

This document records observed facts separately from decoding hypotheses. The
authoritative machine-readable inventories are generated under
`analysis/japanese_reassembly`; that directory is intentionally untracked.

## Reproducible baseline

```powershell
python tools/mgs3d_text_reassembler.py codec partition0/romfs/codec.dat `
  analysis/japanese_reassembly/codec_token_inventory.json
python tools/mgs3d_text_reassembler.py movie partition0/romfs/movie.dat `
  analysis/japanese_reassembly/movie_token_inventory.json
python tools/mgs3d_text_reassembler.py demo partition0/romfs/demo.dat `
  analysis/japanese_reassembly/demo_token_inventory.json
python tools/mgs3d_decoder_compare.py `
  analysis/japanese_reassembly/decoder_comparison_corpus.json `
  analysis/japanese_reassembly/codec_token_inventory.json `
  analysis/japanese_reassembly/movie_token_inventory.json `
  analysis/japanese_reassembly/demo_token_inventory.json
python tools/mgs3d_japanese_export.py codec partition0/romfs/codec.dat `
  analysis/japanese_reassembly/codec_reassembled.jsonl `
  analysis/japanese_reassembly/codec_reassembly_audit.json
```

The inventory retains source hashes, stable GCX/resource or record/entry IDs,
stream hashes, byte offsets, raw context, and legacy previews. Tokenization is
lossless: concatenating each stream's tokens reproduces its original bytes.

| Container | Source SHA-256 | Streams | Tokens | Distinct values |
| --- | --- | ---: | ---: | ---: |
| codec | `932c0a13dd4a0a55213e0a2352b12a11b496a7216706838d0d044930789a344f` | 198,227 | 8,844,383 | 1,293 |
| movie | `f5c8771f58ec3d2c30a825c3fb622db1fec513a6772aaaa8ef95c097499a06f6` | 558 | 9,905 | 221 |
| demo | `3c451c665ea415ce7b260505eee7f1674bf2169949be90caa45f4b58f09dbe39` | 2,091 | 27,548 | 245 |

The union comparison corpus contains 1,331 distinct token values. Its current
fingerprint is
`eeeec7c8ba66d970f28d57151ae19ea5b345492fa06422367e379fa70f90d14b`.

The read-only exporter emits one deterministic JSON Lines row per original
stream. Each row includes stable identity, source-stream hash, complete raw
bytes, the exact token sequence, reconstructed text, structural controls, and
an explicit unresolved list. The current partial-reassembly gates correctly
fail rather than hiding placeholders:

| Container | Exported streams | Unresolved occurrences | Gate |
| --- | ---: | ---: | --- |
| codec | 198,227 | 154,813 | fail |
| movie | 558 | 638 | fail |
| demo | 2,091 | 1,770 | fail |

The committed bitmap-hash map currently contains 914 visually confirmed glyphs.
It yields 109,300 complete codec streams, 232 complete movie streams, and 952
complete demo streams. These counts are progress measurements, not a relaxed
completion criterion: every gate remains failed until its unresolved count is
zero.

Re-running the movie export with unchanged input and mapping produced the same
SHA-256, `b9423a024d129e0095e54f52855b61452573568cb3e61bf383e8d82f3108881b`,
providing an explicit determinism check for that container at this revision.

## Confirmed structural findings

- `00` terminates every parsed text stream.
- Printable single-byte ASCII is preserved directly.
- Bytes at or above `80` form two-byte units in the parsed text regions. A
  dangling lead byte is an explicit error and is never discarded.
- `8C01..8FFF`, excluding `xx00`, map bijectively to page-2 indices 0..1019.
  Codec GCX records contain the referenced 16x16, 2-bpp glyph arrays. Existing
  Hangul runtime tests independently confirmed that changing such a glyph
  changes the rendered character.
- `9001..93FF`, excluding `xx00`, likewise map to page-3 indices 0..1019.
  Movie/demo records contain their referenced 16x16, 2-bpp glyph arrays, and
  fixed-layout Hangul runtime tests confirmed this rendering path.
- Therefore the old `<Gnnn>` and `<Dnnn>` preview labels are provisional and
  misleading: the observed values are glyph indices, not evidence of local or
  global string dictionaries.
- `0A` occurs as a single-byte layout/control token. `807C` is also used as an
  explicit subtitle line boundary by the existing runtime-tested builder.
- Substantial `83xx`, `A0xx`, `A3xx`, and `C0xx..C3xx` populations exist and
  the legacy preview does not decode them.
- `A0..A3` and `C0..C3` are flagged forms of static pages `80..83`: their lead
  byte differs by flag bits `20` or `40`, while the low byte retains the base
  character identity. They are not separate C-string or dictionary pages.
- Pages `81` and `82` follow Unicode Hiragana/Katakana order while omitting the
  obsolete WI/WE characters. Katakana then continues with VU, small KA, and
  small KE. Consequently the legacy arithmetic decoder drifts by two code
  points near the end: `8251` is `ン`, not `ヱ`.
- Cross-checking byte context against the reference bitmap grid confirms four
  page-83 display characters: `8308` is `、`, `8309` is `。`, `8312` is `ー`,
  and `8314` is `…`. The `40`-flagged `C308`/`C309` forms retain the comma and
  full-stop glyph identity. `8314` frequently occurs twice consecutively,
  independently matching the ellipsis bitmap.
- Text reassembly stops at the first `00`. Bytes owned by the same resource
  after that terminator (for example the observed `FON` payload) are retained
  in `trailing_raw_hex`, not misreported as visible text.
- The balanced `8023 A07B ... C07D 8023` form is structural markup. Its hash and
  brace delimiters are emitted as controls rather than visible Japanese text.

## Embedded glyph catalog

All referenced page-2/page-3 slots have been hashed by their exact 64-byte,
16x16, 2-bpp bitmap using `tools/mgs3d_glyph_catalog.py`. Across 155,374 codec
slot identities, 2,643 movie identities, and 5,547 demo identities, only 1,677
unique referenced bitmaps remain. Of those, 992 occur in more than one of the
three containers. Unicode review can therefore operate on bitmap hashes and
propagate a confirmed character without assuming that local slot numbers are
globally stable.

```powershell
python tools/mgs3d_glyph_catalog.py `
  analysis/japanese_reassembly/referenced_glyph_catalog.json `
  --codec partition0/romfs/codec.dat `
  --movie partition0/romfs/movie.dat `
  --demo partition0/romfs/demo.dat `
  --sheet analysis/japanese_reassembly/referenced_glyph_sheet.png
```

The first 21 hash-addressed Unicode mappings are committed in
`tools/data/mgs3d_japanese_glyphs.json`. They were visually verified from GCX
243's enlarged original bitmaps and reconstruct resources 366/367 with zero
unresolved tokens:

```text
下画面右下のアイコンで、射撃モードの
切り替えが可能になる。

FPSモードに切り換えれば、上下左右、
任意の方向へ攻撃を行うことが出来るぞ。
```

Because mappings are keyed by bitmap SHA-256 rather than local slot, the same
confirmations also resolve matching glyphs in movie and demo records.

No sequential UTF-8, UTF-16LE, or UTF-32LE Hiragana/Katakana Unicode table was
found in `partition0/exefs/code.bin`. This does not prove that no character
mapping exists there; it rules out only those direct table representations.
`ui/font.la2` contains fourteen BCFNT UI fonts, not the embedded codec/subtitle
glyph arrays.

## Existing decoder comparison

`codec`, `movie`, `demo`, and `script_compare` are not four independent text
decoders. They all call `tools/mgs3d_codec_tool.py:decode_mgs_preview`, so their
outputs agree for all 1,331 corpus values by shared implementation rather than
independent confirmation.

The matcher consumes that preview and removes every angle-bracketed segment
with `CONTROL_CODE_RE`. This changes 1,062 of the 1,331 token-value cases and
loses unresolved/glyph information. Its disposition is therefore
`unsupported-as-decoder`; it remains usable only as a downstream matching tool
after authoritative Japanese reconstruction.

An independent MGS radio investigation reports the same broad design: a fixed
kana lookup followed by call-specific bitmap Kanji rather than Shift-JIS text.
It also describes the practical need for a per-call bitmap dictionary. This is
supporting cross-version evidence, not proof for an individual MGS3D token;
MGS3D conclusions above additionally rely on the local byte layout and runtime
glyph-replacement tests. See [MGS Undubbed's font investigation](https://blog.mgs-undubbed.io/posts/ai-musings/).

## Open completion-gate items

- Classify `80xx`, including every control value and its arguments.
- Classify and map base punctuation/control page `83xx` and determine the exact
  rendering/layout semantics of the `20` and `40` flag variants.
- Map every observed embedded page-2/page-3 glyph bitmap to Japanese Unicode,
  preserving per-record identity where the same index has different glyphs.
- Determine whether any actual recursive string-reference encoding occurs;
  current D/G labels are not evidence that it does.
- Produce reconstructed output for every stream and drive unresolved,
  unclassified, invalid, and unexplained counts to zero.
