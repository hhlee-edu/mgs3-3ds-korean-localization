# MGS3D Korean localization tools

Reverse-engineered tools and documentation for localizing the Japanese Nintendo
3DS release of *Metal Gear Solid 3D: Snake Eater*.

This repository contains only source code and format documentation. Original
game files, extracted scripts, generated patches, emulator binaries/state, and
reference-site downloads are excluded by `.gitignore`.

## Current capabilities

- extract, inspect, edit, and rebuild `codec.dat` GCX resources;
- render and allocate the embedded 16x16, 2-bpp codec glyphs;
- preserve all 2,326 GCX positions for runtime-safe codec builds;
- inspect and rebuild `movie.dat` and `demo.dat` subtitle/font records;
- compare Korean and English reference scripts with game-side resources;
- generate an offline translation review page;
- build and verify a Citra-compatible mod directory;
- inspect LA2/DARC and ARC/zlib archives.

Runtime testing has confirmed complete Korean codec sentences followed by
stable Japanese dialogue when every GCX record keeps its original layout.

## Start here

- **[Wiki home](wiki/Home.md)** — the canonical knowledge base. Read
  [Current State](wiki/Current-State.md) next, then `HANDOFF.md`.
- [Toolkit workflow](MGS3D_KOREAN_TOOLKIT.md)

Dated session records and topic docs formerly linked here directly now live in
[`wiki/History/`](wiki/History/); `docs/WIKI.md` and `docs/INDEX.md` remain as
superseded-but-preserved originals, each bannered to point at the current wiki.

## Install and diagnose

Python 3.10 or newer is required. Install the two runtime dependencies and run
the readiness check:

```powershell
python -m pip install -r requirements.txt
python tools/mgs3d_doctor.py
```

Use `--source-only` when checking a source checkout that does not contain local
game files or the configured Korean font.

## Safety rule for codec builds

Use the unified builder's default `safe-fixed` codec mode. A resized GCX may
reparse correctly but is known to crash in game because later records move.
Diagnostic and relocation modes are research-only and must not be released.

```powershell
python tools/mgs3d_build.py --help
python tools/mgs3d_verify_build.py --help
python tools/mgs3d_codec_tool.py validate-translation translation.json
python tools/mgs3d_doctor.py --source-only
```

Use `mgs3d_verify_build.py <title-id-directory>` for an incremental build, or
add `--require-complete` when validating a release candidate containing all
three DAT outputs. Safe-fixed codec verification includes the recorded capacity
report and rejects any nonzero glyph deficit. Complete release verification
also rejects diagnostic, experimental, unknown, and legacy unrecorded codec
modes.

Run the source-only safety regression tests (no game files required):

```powershell
python -m unittest discover -s tests -v
```

These tests cover unchanged-resource detection, custom-glyph ownership,
capacity-plan range/mandatory constraints, impossible targets, strict capacity
CLI behavior, and codec translation schema validation.

No copyrighted game data is included or required in version control.

## Version 0.67 status

Version 0.67 is a development checkpoint, not a finished translation release.
The HPK padded-slot cursor-drift crash is fixed and the fix is confirmed on
hardware. The native opening-history Korean texture remains visibly corrupted
because its BCLIM pixel layout is not yet modelled correctly. Codec direct-v2
quality correction is still in progress, and movie/demo subtitles retain known
omissions and review items. Translation drafts, game data, DAT/CCI outputs, and
other large generated artifacts remain outside the public repository.
