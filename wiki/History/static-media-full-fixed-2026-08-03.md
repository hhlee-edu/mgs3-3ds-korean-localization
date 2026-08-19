# Full fixed-size movie/demo Korean candidate (2026-08-03)

This candidate reuses one 165-character static `81/82` Hangul page in codec,
movie, and demo text. Characters outside that page remain record-local. The
static page retains every Hangul character needed by the runtime-validated
first radio paragraph and additionally reserves the characters needed by the
six media cards that otherwise exceeded their record budgets.

## Result

| File | Coverage | Size | Fixed-boundary result | SHA-256 |
| --- | ---: | ---: | --- | --- |
| `codec_static_media_fixed.dat` | 17,206 / 21,086 reviewed units | 67,204,976 | 2,326/2,326 GCX offsets, sizes, string/font/procedure offsets unchanged | `16B02FB3665A779DFCA7CFD13C27B9C2E4889415CBEB6F288385CF1D62B875E6` |
| `movie_static_media_fixed.dat` | 51 / 51 | 229,376 | 108/108 top-level record offsets and sizes unchanged | `3E0F0993762DA71D76D0F6C8A0E70CA2CCAF6D9E30BAD65CDE99F54C66DDA872` |
| `demo_static_media_fixed.dat` | 457 / 457 | 772,935,680 | 333/333 top-level record offsets and sizes unchanged | `1BDC787CBEBDC4BFE1E2B4E38071C002FB30D6278BAE8C8B94BDAB52FAE6413F` |
| `resident_r_sna01_static_media.hpk` | 165 static glyphs | 1,528,898 | original HPK size; patched member 7,151/7,479 bytes | `88D24ACD78ED737E5999B6E715F972AB27F813935F89DF075169CACC22E43E09` |
| `resident_r_sna02_static_media.hpk` | 165 static glyphs | 1,144,621 | original HPK size; patched member 7,151/7,479 bytes | `D375B9AE6DE1A5F9B6EA8F620FA9F048665FB657666B546131DBE95E8B24C3DE` |

The previous growing demo experiment was 164,496 bytes too large. This
candidate never moves a top-level media record and never changes total file
size. Movie/demo internal text/font space may be repacked within each fixed
top-level record; that is the size-neutral mechanism already used by the
media builder.

## Important status

The artifacts above pass structural verification and the complete 96-test
suite. They are not yet runtime-tested as one integrated set. Do not overwrite
the golden real-3DS CCI. Test the five files in a disposable unpacked tree,
starting with the two HPKs plus movie, then demo, then the fixed-layout codec.

The media CSVs contain all accepted PS2-official Korean matches. Codec remains
partial because the strict fixed-layout build uses only record-local font slots
freed inside the same GCX; this deliberately trades coverage for the proven
no-boundary-movement invariant.

## Optional 83xx extended candidate

The static-font entry physically contains 192 complete glyph slots. Runtime
inspection previously showed that the renderer clears `8301`, so the extended
candidate leaves physical slot 165 unused and allocates 26 additional glyphs
to `8302..831B`. The established 165-slot path remains available as the safer
fallback until this extension is runtime-tested.

The canonical extended candidate is retained under
`analysis/script_ref/integrated_191_candidate/romfs`; it does not overwrite the
golden CCI.

After all boundary checks passed, the same five hashes were staged to the
external RomForge `output/unpacked/partition0/romfs` tree for packaging. The
pre-stage files are recoverable from `analysis/script_ref/integrated_next` and
the existing `staging_backup_*` directories. No existing CCI was overwritten;
create a newly named test CCI for runtime validation.

| File | Coverage | Size | Boundary result | SHA-256 |
| --- | ---: | ---: | --- | --- |
| `codec.dat` | 17,445 / 21,086 | 67,204,976 | every GCX/string/font/procedure boundary unchanged | `FBBA2D97D5BE68F84876890C56E2758DF930CA39FE317C7E50D5173CDACB1310` |
| `movie.dat` | 51 / 51 | 229,376 | 108/108 top-level records unchanged | `8232FCB3A01868187E803801F73CAF3F2A5F33E18BEC56A6EC7CC0E81D2BFC30` |
| `demo.dat` | 457 / 457 | 772,935,680 | 333/333 top-level records unchanged | `D3437249681D963BF4EFD618F2F843262DA65D98F00E32AD203313E5E08FC3E5` |
| `r_sna01/resident.hpk` | 191 glyphs | 1,528,898 | patched member 6,974/7,479 bytes | `0BB61B40EFAAE1228489907E65BF4A04F5C0A35093F134AC1AB2932A6CDA16F4` |
| `r_sna02/resident.hpk` | 191 glyphs | 1,144,621 | patched member 6,974/7,479 bytes | `CAEB3379ED5DD08EDFEE496E1FCA5E6AF01E864C66C3D8D63EEE57132FF592FD` |

## Packaged 191-glyph test CCI

RomForge's extracted managed `RepackService` was called directly against the
staged unpacked tree. It created a new file and did not overwrite either of the
existing RomForge CCIs or the golden real-3DS image.

- Path: `analysis/script_ref/MGS3D_PS2KO_191_FIXED_TEST_Repack.cci`
- Size: 3,248,410,624 bytes
- SHA-256: `792153E09BA07C0EB0A3B916923732FA0E34567DC859DE4E1925EB9AA4F15661`
- Header: `NCSD`
- Partition 0: offset 16,384, length 3,227,979,776
- Partition 1: offset 3,227,996,160, length 2,473,984
- Partition 7: offset 3,230,470,144, length 17,940,480
- Final partition end: 3,248,410,624, exactly equal to the CCI file size

The repository test suite passes 99/99 after packaging. Structural checks are
complete; the `8302..831B` static-page extension still requires an actual 3DS
runtime test. If it fails, use the retained 165-glyph integrated candidate as
the fallback.

### Post-package RomFS verification

The encrypted CCI was reopened with RomForge's own `CciSource` and
`RomFsUnpacker`. Each target file was read directly from partition 0 and
streamed through SHA-256 without extracting or trusting the staging folder.
All five embedded sizes and hashes exactly match the 191-glyph source table
above:

| Embedded path | Size | SHA-256 result |
| --- | ---: | --- |
| `/codec.dat` | 67,204,976 | exact match |
| `/demo.dat` | 772,935,680 | exact match |
| `/movie.dat` | 229,376 | exact match |
| `/stage/r_sna01/resident.hpk` | 1,528,898 | exact match |
| `/stage/r_sna02/resident.hpk` | 1,144,621 | exact match |

This proves that repacking did not alter, omit, truncate, or substitute any of
the five patched files. It does not prove renderer behavior on hardware.

### Hardware runtime gate

Test only the newly named CCI, keeping the golden CCI untouched. The minimum
acceptance sequence is:

1. Boot through title screen and load a save without an error or black screen.
2. Open the first radio exchange and verify the previously runtime-safe base
   glyphs, line wrapping, speaker changes, and button/control markup.
3. Exercise several later codec calls to check record-local glyphs and confirm
   that untranslated fallback lines remain readable.
4. Play at least one translated movie subtitle and one translated demo scene;
   confirm timing, line breaks, and transition to the following record.
5. Reach scenes that use the two additional extended-allocation requirements
   (demo source offsets `447093852` and `575939116`). Any blank, wrong, or
   cleared glyph there rejects the 191-glyph candidate and selects the retained
   165-glyph fallback.
6. Reboot once after saving. A successful warm session alone is insufficient
   because font/static initialization may differ on a cold launch.

## Packaged 165-glyph fallback CCI

For an unambiguous hardware A/B test, the retained 165-glyph files were
applied to the verified 191-glyph CCI with RomForge's direct repacker. The
result is a separate image; no existing or golden CCI was overwritten.

- Path: `analysis/script_ref/MGS3D_PS2KO_165_FIXED_FALLBACK_v3.cci`
- Size: 3,248,410,624 bytes, exactly equal to the 191-glyph CCI
- SHA-256: `951B5986BBF362DB9B395D7933AECE119D7A9B17FFD7A7C9B2F9619C1087A1BC`
- Embedded `/codec.dat`: `16B02FB3665A779DFCA7CFD13C27B9C2E4889415CBEB6F288385CF1D62B875E6`
- Embedded `/demo.dat`: `1BDC787CBEBDC4BFE1E2B4E38071C002FB30D6278BAE8C8B94BDAB52FAE6413F`
- Embedded `/movie.dat`: `3E0F0993762DA71D76D0F6C8A0E70CA2CCAF6D9E30BAD65CDE99F54C66DDA872`
- Embedded sna01 HPK: `88D24ACD78ED737E5999B6E715F972AB27F813935F89DF075169CACC22E43E09`
- Embedded sna02 HPK: `D375B9AE6DE1A5F9B6EA8F620FA9F048665FB657666B546131DBE95E8B24C3DE`

The encrypted fallback CCI was reopened and all five embedded hashes were
verified directly. Two earlier files named without `_v3` were rejected because
their patch roots were wrong and they were byte-identical to the 191-glyph CCI;
those duplicate images were deleted. Only `_v3` is the valid fallback.

Run the 165-glyph image first, then the 191-glyph image against the same save:

- If both fail at the same point, investigate the shared codec/media/static
  integration rather than the page-83 extension.
- If 165 works and 191 fails, reject `8302..831B` and keep the 165-glyph build.
- If both work, accept 191 because it provides the higher codec coverage
  (17,445 instead of 17,206 reviewed units) while preserving all fixed sizes.

## Static-allocation local-search audit

A one-for-one local-search pass found a nominal `17,446`-row allocation, but
the extra total came from adding five duplicate copies of one line while
removing four existing “Tom Major” lines. It was rejected because aggregate
count alone must not shrink already translated coverage. The optimizer now
defaults to monotonic improvement: a swap is legal only if every previously
feasible codec row remains feasible. No legal improving swap exists for the
current required 99 characters and 191-slot limit, so the verified 17,445-row
allocation remains canonical. The rejected experimental CCI is not a test
artifact and was deleted.

The remaining selector gap was also audited exactly. All 544 codec GCXs have
zero usable record-local glyph slots in the untouched English source. Under
that condition, the maximum for each GCX is an exact cardinality knapsack:
discard rows needing a non-static Hangul glyph, then take the largest string
savings until the fixed byte budget is exhausted. The summed exact upper bound
is 17,445 and the selector chooses exactly 17,445 (gap zero) in all 544/544
records. Of the 3,641 unselected rows, 3,609 require glyphs outside the static
191-character page and 32 are excluded by fixed per-GCX string capacity. The
audit is retained in
`analysis/script_ref/codec_selection_static_media_191_exact_audit_report.json`.

## Static HPK scope audit

The full staged RomFS contains 158 HPK archives. A binary scan for the valid
zlib-backed static-font entry key `453C386E` found exactly two entries:

- `stage/r_sna01/resident.hpk`
- `stage/r_sna02/resident.hpk`

No stage `cache.hpk` contains another copy, so there is no omitted archive that
needs the same fixed-size font patch. Of 169 scenario GCXs, 163 reference
`r_sna01`; 52 of those also reference `r_sna02`. This demonstrates that the two
patched resident archives are shared broadly across the game rather than being
limited to two isolated stages. The packaged CCI hash audit already proves both
patched paths are present with the expected bytes.

The reproducible report is
`analysis/script_ref/hpk_static_scope_audit.json`; rerun it with
`tools/mgs3d_hpk_static_audit.py ROMFS --expect-entry-count 2`. The complete
repository suite passes 103/103 after adding this audit.
