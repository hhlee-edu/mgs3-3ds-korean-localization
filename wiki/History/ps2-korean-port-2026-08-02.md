# reference-Korean to MGS3D port investigation

## Confirmed format facts

- The Korean reference `MGS/CODEC.DAT` uses the same sequential GCX container family
  parsed by `mgs3d_codec_tool.py`.
- It contains 2,355 GCX records and 203,214 resources.
- Every font section is structurally valid.  The local glyph format is 24x24,
  2 bits per pixel, MSB-first linear order: 144 bytes per glyph.
- There are 2,315 populated font sections, 108,058 physical glyphs, and at
  most 657 glyphs in one GCX.
- Korean strings use the same `8C01..8FFF` page-2 index family observed in
  MGS3D.  The 3DS representation uses 16x16, 2-bpp, 64-byte glyphs.
- A deterministic converter now downsamples the official PS2 bitmaps to the
  existing runtime-tested 3DS linear glyph layout.

Authoritative report:

`analysis/script_ref/codec_font_report.json`

## Record correspondence

Structural sequence comparison against the unpacked 3DS Japanese edition
finds 2,142 exact record pairs.  Equal-length variant blocks bounded by exact
monotonic anchors add 173 positional pairs, for 2,315 mapped 3DS records.
Eleven 3DS records remain unmatched because the surrounding insert/delete
blocks have unequal lengths.  Such records are not guessed.

The Japanese edition is used only as a 3DS GCX structure/procedure reference.
No Japanese dialogue is emitted by the Korean port.

## Runtime probes and dispositions

### English procedure + PS2 strings/font

Disposition: **rejected**.

The large candidate passed structural parsing and page-2 bounds checks, but
the first radio conversation was skipped.  Western GCX records contain English,
Spanish, and French resource branches; replacing those with the shorter PS2
single-language resource sequence does not preserve the procedure's resource
contract.

### Complete PS2 record + converted font

Disposition: **rejected**.

The first-radio probe exited with an error.  PS2 GCX procedure bytecode is
highly similar to the 3DS bytecode but is not directly executable by the 3DS
runtime.

### 3DS single-language procedure shell + PS2 strings/font

Disposition: **rejected**.

The focused probe uses the corresponding 3DS single-language record for its
procedure and resource layout, replaces all visible resources with the PS2
official Korean resources, and installs converted 16x16 glyphs.  Only target
GCX 15 is changed; every other record comes from the prior runtime-stable
candidate.

- rejected probe SHA-256: `BBE782A4E25BD9DD1684BD8E893D918FCF1416DFC532AF8DBA2B9FE7A854FB2F`
- candidate: `analysis/script_ref/codec_ps2_jpshell_gcx16_probe_on_stable.dat`
- rollback: `analysis/script_ref/codec_before_ps2_official_port.dat`

The emulator exited immediately before the first radio conversation.  A
follow-up probe containing the untouched corresponding 3DS Japanese GCX and no
PS2 data also stopped with an emulator error.  Therefore whole GCX/procedure
replacement across the regional executables is not a viable production path.

## Korean token architecture

The official PS2 strings establish that `81xx` and `82xx` are not Japanese in
the Korean executable.  They select a shared, frequency-oriented Korean static
page.  `8Cxx` supplies record-local uncommon syllables.  For the first official
radio paragraph, 89 normalized PS2 symbols align exactly with 89 Korean Unicode
characters; repeated symbols produce no contradictions.  This seeds 34 shared
token mappings and 17 record-local mappings.

Conservative mining against 21,082 confirmed physical codec rows expands the
shared table to 65 mappings with no duplicate Unicode assignments.  The
remaining mappings stay unresolved rather than being guessed.

- seed: `analysis/script_ref/korean_token_map_seed.json`
- mined: `analysis/script_ref/korean_token_map_mined_combined.json`

Capacity measurements after treating the shared page as global:

- 2,218 / 2,355 PS2 GCXs need at most 96 local glyphs;
- 2,219 need at most 100;
- 2,224 need at most 127;
- only the remaining large outlier blocks require splitting, sharing, or
  focused editing.

The production direction is therefore to preserve every English-edition GCX
procedure, resource index, and language branch; decode Korean reference tokens to
Unicode; then encode the result using the already runtime-tested 3DS local
glyph mechanism.  Static-page patching remains an optional further capacity
optimization, not a prerequisite for the 94.2% fitting subset.

## Reproduction

```powershell
python tools/mgs3_ps2_codec_report.py `
  analysis/script_ref/MGS/CODEC.DAT `
  analysis/script_ref/codec_font_report.json

python tools/mgs3_script_ref_port.py `
  analysis/script_ref/MGS/CODEC.DAT `
  analysis/script_ref/codec_before_ps2_official_port.dat `
  analysis/script_ref/codec_ps2_jpshell_gcx16_probe_on_stable.dat `
  analysis/script_ref/codec_ps2_jpshell_gcx16_probe_on_stable.json `
  --reference-codec `
  C:\Users\hhlee\Desktop\Romforge\output\unpacked_metagear_jpn\partition0\romfs\codec.dat `
  --ps2-gcx 16 `
  --reference-shell
```

The complete unit-test suite currently passes 83 tests.

## Runtime-validated static Korean page breakthrough

The English runtime's static dialogue font was located by tracing the `81xx`,
`82xx`, and `83xx` renderer branches.  The relevant renderer paths are at
`0x0015E60C` and `0x0015EC64`.  At runtime, the combined static glyph table was
observed at `0x086854F8`.

The table comes from HPK entry key `453C386E` in both:

- `stage/r_sna01/resident.hpk`
- `stage/r_sna02/resident.hpk`

The English entry is a fixed-size zlib member with 21,128 unpacked bytes and a
7,479-byte packed budget.  Its static font begins at entry offset `0x2208`.
The layout is 64 bytes per 16x16 2-bpp glyph: `81xx` starts at slot 0, `82xx`
at slot 81, and `83xx` at slot 165.  The runtime intentionally clears the
first `83xx` glyph; the rest of the extracted HPK font matched the live memory
dump.

`tools/mgs3d_hpk_static_korean.py` now replaces the first 50 `81xx` slots with
14px Malgun Gothic glyphs for the first official PS2 radio paragraph.  The
smallest deterministic zlib result is 7,397 bytes and is padded to the original
7,479-byte member budget, preserving each HPK's exact file size and every later
entry offset.  `tools/mgs3_ps2_static_first_radio.py` maps the Korean Unicode
characters to those static tokens and emits all four English GCX copies
(15/17/51/53).  No record-local glyphs are added.

The first-radio fixed-layout build changes exactly four GCXs and preserves the
67,204,976-byte `codec.dat` size.  Ten later diagnostic strings in each GCX are
cleared only to fund the longer official paragraph inside the unchanged string
region.

Runtime result: **passed**.  The user confirmed that the first radio was not
skipped, all four official Korean sentences appeared, and glyph rendering and
line wrapping were normal.

Validated artifacts:

- `analysis/script_ref/codec_ps2_static_first_radio_4copy.dat`
  (`ACF23134EBA9DBADFC56CA5A7D1857C431D23365DC6D3A5A9586157CEDB4CB5B`)
- `analysis/script_ref/resident_r_sna01_static_korean.hpk`
  (`8BE80AC7372A03797660290A13C75F38014C5E84C648F1E367046397FC68BC65`)
- `analysis/script_ref/resident_r_sna02_static_korean.hpk`
  (`8EAA073DD38CCA65CDE0BD789CCD4945F33AB8007938C1D40D37AED15F36D162`)
- tested CCI: `MGS SNAKE EATER 3D_Repack____.cci`

The three pre-test staged files are backed up under
`analysis/script_ref/staging_backup_*`.  The validated candidates remain staged
in RomForge.  Production expansion should allocate the 165 static `81/82`
slots by corpus frequency, then use record-local `8Cxx` only for uncommon
characters while preserving every GCX and HPK boundary.

## Bulk static-page candidate

Bulk production reserves the 50 runtime-validated first-radio Hangul
characters, then fills the remaining 115 static `81/82` slots by frequency
across the reviewed codec corpus. The corpus contains 537 unique Hangul
characters. Both HPKs use the same 165-character allocation, retain their
original sizes and entry offsets, and compress the patched entry to 6,970 of
the available 7,479 bytes.

The official first-radio paragraph is retained at all 16 physical targets.
The size-neutral selector accepts 20,923 of 21,098 targets (99.17%) and excludes
175. The build changes 523 GCXs, adds 6,429 record-local glyph instances, and
uses at most 115 local glyphs in one GCX. Two builds and their allocation
sidecars are byte-identical; all 83 tests pass.

Staged hashes:

- `codec.dat`: `D94BFA91B720FEDD6D2827566A7AA31DF4DCE98917BC206FF2E19FE6BD0E32F1`
- `r_sna01/resident.hpk`: `6D751F2A037FFC468B7501E7F52E77A50AB2275B8F6CE60419E5A5CC945A7B77`
- `r_sna02/resident.hpk`: `BB72B8FAB297499859578E48758B54608C79A3CA8C9AEEEEAACE912C44249496`

This candidate is staged but not yet repacked or runtime validated. Test these
codec/HPK changes before expanding movie or demo.
