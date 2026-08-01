# MGS3D Korean localization toolkit

This workspace contains reverse-engineered tools for translating the Japanese
Nintendo 3DS release of Metal Gear Solid 3D. Original game files, extracted
scripts, generated patches, and emulator state are intentionally excluded by
`.gitignore`.

## Supported files

- `codec.dat`: encrypted sequential GCX records, resources, and per-record fonts
- `movie.dat`: type-4 subtitle records and page-3 embedded fonts
- `demo.dat`: the same subtitle/font records embedded among large video payloads
- LA2/DARC and ARC/zlib archives through `tools/extract_archives.py`

All builders write to a separate output. The audited `partition0` source is
never modified.

## Typical workflow

1. Install dependencies with `python -m pip install -r requirements.txt` and
   run `python tools/mgs3d_doctor.py`.
2. Put an unpacked game under `partition0`.
3. Create or verify its integrity inventory with `tools/audit_unpacked.py`.
4. Extract Korean/English reference scripts with
   `tools/mgs3d_script_compare.py`.
5. Inspect `movie.dat` and `demo.dat` with `tools/mgs3d_movie_tool.py`.
6. Generate the offline review page with `tools/mgs3d_review_html.py`.
7. Approve/edit rows in the browser and download each reviewed CSV.
8. Build the Citra mod with `tools/mgs3d_build.py`.

Example final build:

```powershell
python tools/mgs3d_build.py `
  --codec-review analysis/codec_reviewed.csv `
  --codec-mode safe-fixed `
  --movie-csv analysis/movie_reviewed.csv `
  --demo-csv analysis/demo_reviewed.csv `
  --output-root dist/citra_mod
```

The builder reads the NCCH title ID, creates the corresponding Citra
`load/mods/<title-id>/romfs` layout, emits SHA-256 values, and structurally
reparses every changed container. `safe-fixed` is the default codec mode. It
first runs a strict capacity preflight, writes `codec-capacity.json`, preserves
every original GCX position, and refuses the build before generating
`codec.dat` if translated resources do not free enough existing glyph slots.

Verify a complete build and the untouched source in one command:

```powershell
python tools/mgs3d_verify_build.py `
  dist/citra_mod/000400000007A000 --require-complete
```

This checks all three manifest hashes, 2,326/198,227 codec structure counts,
93/558 movie counts, 260/2,091 demo counts, and the 925-file source inventory.
Without `--require-complete`, the verifier checks only the outputs declared in
the manifest, which supports incremental codec/movie/demo development builds.
For `safe-fixed` codec outputs it also verifies the capacity-report hash and
requires every recorded slot deficit to be zero. The report is cryptographically
linked to the exact source codec and translation JSON; the verifier checks its
source and translation hashes against the build manifest.

Incremental builds preserve metadata from the previous manifest only when an
existing output still has the exact recorded size and SHA-256. This keeps the
codec mode and capacity-report proof attached to an unchanged codec while
discarding stale metadata for externally replaced files. `--require-complete`
accepts only a `safe-fixed` codec; diagnostic, experimental, unknown, and legacy
unrecorded codec modes cannot be release candidates.

The unified builder writes DAT files, Hangul allocation reports, capacity
reports, and the manifest to sibling `.tmp` paths first. A failed child build
removes those temporary artifacts and leaves the last committed local build
untouched. Successful allocation reports are committed beside their DAT files,
hashed in the manifest, and checked by the verifier.

When one invocation builds multiple DAT files, none of them is committed until
every requested codec/movie/demo child builder has succeeded. For example, a
successful staged movie followed by a failed demo build leaves neither a new
movie nor a new manifest behind. The manifest is always committed last and acts
as the local transaction marker.

Each title-ID build directory also uses `.mgs3d-build.lock`, containing the
builder process ID, to prevent two local builds from sharing the same temporary
paths or racing the manifest. Normal success and handled failure both remove the
lock. If the Python process or computer is forcibly terminated, first confirm
that no build is running and then remove the stale lock manually.

Detailed format and translation notes are in:

- `docs/la2-arc-format.md`
- `docs/mgs3d-codec-tool.md`
- `docs/mgs3d-script-comparison.md`
- `docs/unpacked-integrity.md`

## Current verification

The current private working data verifies:

- 2,326 GCX records and 198,227 codec resources after rebuilding
- 93 movie records / 558 subtitle entries
- 260 demo records / 2,091 subtitle entries
- byte-identical no-change `movie.dat` rebuilding
- raw 16x16, 2-bpp, 64-byte embedded glyphs in movie/demo records
- successful 773 MB streaming `demo.dat` rebuild
- Hangul glyph extraction and visual inspection for codec and movie output
- successful in-game rendering of 16x16 Hangul glyphs in codec dialogue
- confirmed runtime requirement that all codec GCX positions and sizes remain fixed
- complete two-resource Korean FPS tutorial probe followed by stable Japanese dialogue

Runtime validation was performed with a user-supplied, legally obtained game
image. Game content is not distributed with this toolkit. Full codec translation
still requires manually verified resource alignment and enough translated text
per GCX to reclaim font slots safely.
