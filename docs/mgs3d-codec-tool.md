# MGS3D codec.dat translation tool

`tools/mgs3d_codec_tool.py` handles the sequential GCX container used by
MGS3D's `codec.dat`. It validates and extracts records, decrypts GCX resources,
dumps an editable JSON representation, applies replacements of different
lengths, updates affected GCX offsets, encrypts the resources again, and
rebuilds the DAT file.

## Confirmed properties

The tested `partition0/romfs/codec.dat` contains 2,326 GCX records and 198,227
resources. Records are aligned to 0x10 bytes. String resources use the GCX stream
cipher implemented by the game and by Jayveer/Gcx.

An unchanged rebuild is byte-identical to the source:

```text
SHA-256 932c0a13dd4a0a55213e0a2352b12a11b496a7216706838d0d044930789a344f
```

A resized GCX can pass a complete structural reparse, but runtime testing proved
that this is not sufficient. MGS3D refers to later codec records by stable
positions: growing or shrinking an earlier record eventually executes data as
code and Citra reports repeated game `PANIC` breaks. Production codec builds
must therefore preserve every GCX start, stored size, string boundary, font
boundary, and procedure boundary.

## Commands

Validate and summarize:

```powershell
python tools/mgs3d_codec_tool.py info partition0/romfs/codec.dat
```

Extract individual GCX files and a catalog:

```powershell
python tools/mgs3d_codec_tool.py extract `
  partition0/romfs/codec.dat analysis/codec_gcx_export
```

Dump all resources marked as strings:

```powershell
python tools/mgs3d_codec_tool.py dump `
  partition0/romfs/codec.dat translation.json --strings-only
```

The complete dump is large. Filters are available for focused work:

```powershell
# GCX 0 and 1 only
python tools/mgs3d_codec_tool.py dump codec.dat radio_test.json `
  --strings-only --gcx 0 --gcx 1

# Resources containing an ASCII identifier
python tools/mgs3d_codec_tool.py dump codec.dat matches.json `
  --strings-only --contains radiotest
```

Apply an edited translation document:

```powershell
python tools/mgs3d_codec_tool.py apply `
  partition0/romfs/codec.dat translation.json codec_patched.dat
```

## Translation JSON

Non-ASCII and control bytes use lossless `<HH>` tokens. Do not delete tokens
whose purpose is unknown.

```json
{
  "format": "mgs3d-codec-translation-v1",
  "character_map": {
    "가": "8120",
    "나": "8121"
  },
  "units": [
    {
      "gcx": 0,
      "resource": 0,
      "kind": "string",
      "original_size": 12,
      "preview": "radiotest1b<END>",
      "text": "radiotest1b<00>"
    }
  ]
}
```

`preview` decodes confirmed ASCII, Hiragana, Katakana, and per-GCX custom-glyph
references for reading only. Keep editing the lossless `text` field. A custom
glyph reference appears as `1F nn` in `text` and `<Gnn>` in `preview`.

`character_map` maps a Unicode translation character to the exact byte sequence
expected by the game. For example, a Korean character assigned to custom glyph
0 maps to `1F00`. The same 16x16 glyph must be installed into that GCX.

Without a character map, editable literal text is restricted to printable
ASCII. This prevents the tool from silently writing an invalid UTF-8 string
into the game's proprietary text encoding.

## Per-GCX custom font tool

The dialogue renderer and GCX structure confirm a second, non-BCFNT font path.
Every populated GCX font section is a 32-bit byte count followed by consecutive
16x16, 2-bpp glyphs of 64 bytes each. `1F nn` selects custom glyph `nn`.

```powershell
# List available custom glyphs
python tools/mgs3d_gcx_font_tool.py list partition0/romfs/codec.dat

# Extract GCX 15 as a sheet and JSON manifest
python tools/mgs3d_gcx_font_tool.py extract `
  partition0/romfs/codec.dat 15 analysis/gcx15.png

# Replace glyph 0 from a 16x16 grayscale PNG
python tools/mgs3d_gcx_font_tool.py patch `
  partition0/romfs/codec.dat 15 0 hangul.png codec_patched.dat
```

The four grayscale levels are quantized back to the game's 2-bpp format.

Build a Korean DAT directly from an edited translation document:

```powershell
python tools/mgs3d_gcx_font_tool.py build-korean `
  partition0/romfs/codec.dat translation.json `
  C:\Windows\Fonts\malgun.ttf codec_korean.dat `
  --reuse-freed-font --preserve-record-layout
```

Check whether a translation set frees enough original glyphs before building:

```powershell
python tools/mgs3d_gcx_font_tool.py capacity `
  partition0/romfs/codec.dat translation.json `
  --json analysis/codec_capacity.json `
  --check
```

Safe mode reuses only glyph slots that are no longer referenced after all
actually changed resources in that GCX are replaced. Merely listing an
unchanged resource in a translation/template does not free its glyphs. Safe
mode stops instead of producing a
file when the unique Hangul count exceeds the freed-slot count. This normally
means that a complete radio conversation or larger GCX group must be translated
together; replacing one isolated line rarely frees enough slots.

`--check` gives automation a nonzero exit status when any changed GCX has a
slot deficit. The unified builder runs this strict preflight automatically in
`safe-fixed` mode and writes `codec-capacity.json` beside the build manifest
before creating `codec.dat`.

The capacity report records SHA-256 values for both the source `codec.dat` and
the exact translation JSON, plus aggregate counts for listed/changed resources,
ready/failing GCX records, and total slot deficit. Safe-fixed build verification
requires those hashes to match the manifest and the current source partition;
a stale or substituted capacity report cannot validate another build.

Plan a compact candidate resource set and emit an editable template:

```powershell
python tools/mgs3d_gcx_font_tool.py plan-capacity `
  partition0/romfs/codec.dat 243 32 366 367 `
  --min-resource 300 --max-resource 440 `
  --json analysis/gcx243-plan.json `
  --template analysis/gcx243-template.json
```

The planner analyzes which resources own every custom glyph, keeps the listed
mandatory resources, and uses a deterministic greedy/pruning heuristic. Its
result is compact but does not claim mathematical optimality. The template
contains lossless original `text` plus a human-readable `preview`; verify the
mapping and edit every selected line that will contribute freed slots.

All codec translation consumers share the same schema validator. It rejects
missing or mistyped `gcx`, `resource`, and `text` fields; negative indices;
invalid `kind` values; malformed or empty character-map entries; and duplicate
`(gcx, resource)` units. Duplicate targets are errors even when their text is
identical, so build order can never silently decide which entry wins.

Validate a translation without reading any game files:

```powershell
python tools/mgs3d_codec_tool.py validate-translation `
  translation.json --json analysis/translation-validation.json
```

This also parses every lossless `<HH>` token stream, checks that all other
characters are encodable (Hangul is reserved for later per-GCX allocation), and
reports unit count, GCX count, character-map entries, unique Hangul count, and
the provisional rendered byte count.

`--reuse-existing-font --preserve-record-layout` is diagnostic only. It keeps
the game stable but deliberately overwrites live Japanese glyphs, causing mixed
Japanese/Hangul text elsewhere. Runtime probes use this mode solely to identify
resources and validate rendering.

## Conservative automatic radio pass

The first codec comparison exported 195,681 candidates because many GCX files
copy common resource tables. Exact plaintext deduplication reduces this to
35,433 unique resources (23,352 occur only once). The anchor review therefore
matches unique plaintext first and then expands the result back to every GCX
copy that must be changed.

The codec anchor review contains 299 targets where at least two Latin/number
anchors identify one English transcript entry. Runtime screenshots proved that
two anchors such as `CIA JACK` can still select an unrelated Japanese resource.
The current rule therefore keeps two-anchor rows for review but auto-accepts
only matches with at least three shared anchors, including one anchor unique in
the English transcript. With the current corpus this changes automatic codec
approval from 21 rows to zero.

```powershell
python tools/mgs3d_script_compare.py make-translation `
  analysis/codec_korean_anchor_review.csv `
  analysis/codec_korean_auto_translation.json

python tools/mgs3d_gcx_font_tool.py build-korean `
  partition0/romfs/codec.dat analysis/codec_korean_auto_translation.json `
  C:\Windows\Fonts\malgun.ttf dist/codec.dat
```

The earlier 21-GCX/504-glyph output is retained only as a static research
artifact. It is not runtime-safe because it relocates following GCX records and
must not be distributed as a production patch.

`make-translation` also reads the original GCX resource's `<0A>` layout. It
wraps Korean at word boundaries into the same number of radio-window lines and
preserves a trailing newline. The current verified example uses three lines:
`잭, 잘 듣게.` / `드디어 CIA 장관으로부터` / `버츄어스 미션의 허가가
났다네.`

For every GCX, safe mode collects the Hangul syllables used in `text`, selects
only freed original slots, renders the replacements, converts Korean characters
to matching `8Cxx` tokens, pads the encrypted string region back to its exact
original size, and writes a `codec_korean.dat.hangul.json` allocation report.

## Current boundary

Runtime testing has confirmed 16x16 Hangul rendering and the fixed-record layout
requirement. The remaining production boundary is complete, manually verified
radio-resource alignment in sufficiently large GCX groups to free enough font
slots without damaging untranslated Japanese text.

The fixed-layout FPS runtime probe replaced two consecutive tutorial resources
across their duplicated GCX copies. Citra displayed both Korean sentences with
correct wrapping, continued into unmodified Japanese dialogue, and produced no
game `PANIC` or fatal-error dialog. Screenshots are retained privately as
`analysis/1.png` through `analysis/5.png`.
