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
- separate French/Spanish donor branches from English using a language ID built
  from the corpus itself, not hand-written stopword lists
  (`tools/mgs3d_codec_langid.py`);
- preserve 3DS button-icon tokens through a translation by pouring the Korean
  into the source resource's own control-code schema
  (`tools/mgs3d_codec_icon_schema_fit.py`);
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
[`wiki/History/`](wiki/History/). Documents that quoted game dialogue were
removed from the repository and its history; see the policy below.

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

## Version 0.83 status

Version 0.83 is a development checkpoint, not a finished translation release.
**Version numbering stops here** — later codec work continues on this
checkpoint instead of incrementing.

Confirmed on hardware: the HPK padded-slot cursor-drift crash is fixed, the
global Korean glyph page renders, and the codec ships Korean for the early
briefing, survival, CQC, camouflage and Para-Medic conversations.

Known open items:

- the native opening-history Korean texture is still visibly corrupted, because
  its BCLIM pixel layout is not modelled correctly yet;
- 640 codec rows remain for human review, mostly because the speaker cannot be
  proven — Shinsnote only covers 423 of its 4,070 lines with codec targets, and
  that is the binding constraint, not the analysis;
- `movie.dat` and `demo.dat` subtitles retain known omissions and review items.

Translation drafts, game data, DAT/CCI outputs, and other large generated
artifacts remain outside the public repository.

### The extractor was blind to 3DS-only strings

`strict_western()` accepted `0x80 0x7C` and rejected the whole resource on any
other high byte. 3DS button icons are two-byte tokens — `( # { 7 } #)` is
`80 23 A0 7B A3 1E 80 37 C0 7D 80 23` — so **every control-tutorial string that
mentions a button was dropped before it could reach the master**, and no
coverage report could see it: the same predicate built both the numerator and
the denominator, so the two matched by construction and reported zero missing.

Measuring the icon-token grammar over the whole corpus showed it is completely
closed (`0xA0`→`0x7B` and `0xC0`→`0x7D` in 16,981/16,981 cases, `0xA3`→`0x1E` in
16,815/16,815, `0x80` taking twelve distinct second bytes), so only that exact
set was allowed. The parser change loses **no** previously accepted resource and
exposes 13,569 positions across 316 strings.

Coverage is now computed without self-reference: `ACTUAL_CODEC_ENGLISH` comes
from the binary, `MASTER_KNOWN` from the master's own index, and
`MASTER_MISSING` is the **set difference** — never a subtraction of totals.

Method, measurements and the gate list are written up in
[`docs/codec-extraction-method.md`](docs/codec-extraction-method.md).

## Game text is not in this repository

Konami's script — English or Japanese — the PS2 Korean localization, and
third-party transcriptions of it are copyrighted. None of it is committed here,
in any form:

- `translation/` and `docs/decisions/` are gitignored, so master CSVs and the
  hand-adjudicated translation tables stay local;
- evidence files that embed script are excluded by name in `.gitignore`;
- the documentation does not quote dialogue either. Positions are identified by
  `gcx` / `resource` number, never by their text.

What stays in version control is tooling, byte-level format documentation, and
aggregate counts.
