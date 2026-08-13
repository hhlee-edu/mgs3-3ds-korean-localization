# DAT Formats (`movie.dat`, `demo.dat`)

3DS `movie.dat`/`demo.dat` record structure is fully decoded, lossless
round-trip verified (`mgs3d_movie_tool.py`).

## Record layout

- Records are type-4, `0x10`-aligned.
- `+0x04`: aligned total record size.
- `+0x10`: subtitle/font boundary (offset relative to record `+0x14`).
- `+0x20`: first subtitle entry.
- Subtitle entry header: upper 16 bits = type 7, lower 16 bits = declared size.
- Normal entry: header + null-terminated token text + padding + 12-byte timing.
- Font boundary: LE font byte size + raw 16×16 2bpp glyphs, 64 bytes/glyph, no
  compression.
- **Each record's local font is fully independent** — no sharing with codec's
  191-character shared static font. Glyphs cannot be reused across records.

Current live parser scope: **movie.dat 108 records / 3,480 subtitle entries,
demo.dat 333 records / 11,296 entries** (an older parser reported
93 records/558 entries and 2,091 demo entries — both superseded, see
[Current State](Current-State.md#invalidated)).

## The scene container (demo.dat, 2026-08-08 discovery)

`demo.dat` is a **130-scene multiplex container**, walked end-to-end with 0
desync and 0 undecoded bytes from offset 0 (prefix is `0x20`, not `0x30`):

- `kind = (stream << 16) | type`.
- `type=2`: 5-stream-interleaved media payload (video/audio).
- `type=4`: the subtitle records described above.
- `type=16`: scene-boundary tag (`f3=2` marks a scene start).
- `type=240`: per-scene trailer.
- All 130 scenes align to `0x800` (2 KB); each scene is followed by zero
  padding to the next scene (avg ~1 KB, max 2,016 B, 129,984 B total).

**The governing rule:** playback only checks that a scene's *start offset*
matches the original. Growing a `type=4` record *inside* a scene never moves
that scene's own start (growth always displaces things *after* it), so it's
always safe regardless of size. Growing across a scene boundary displaces the
next scene's start and can break the earliest-affected scene's boot.

**Why this was hard to find:** early tests bisecting "how many records can grow
at once" produced an apparently strict rule ("exactly 1 record is safe, 2+
always fails") that turned out to be coincidence — every failing combination
happened to include a record from a scene *before* the real first-video scene
(#127), so the cumulative growth ahead of it pushed scene #127's start. A
gap-only padding test (no content changes at all, just 2,000 B of padding
before scenes #26 and #127) reproduced the same failure, proving the trigger is
purely positional, not content-related.

**Safe multi-scene growth, verified on hardware:** fund each scene's growth from
that scene's *own* trailing padding, so no scene's start offset moves at all.
Records 50 (scene #26) and 287 (scene #127) each grown 1,600 B simultaneously,
funded from their own scene padding → normal playback confirmed.

`movie.dat` is presumed to use the same scene structure (record-growth tests
there have so far always stayed within one scene) but this has **not** been
directly confirmed — see [Current State](Current-State.md#unverified).

## Relocation validation (2026-08-10)

- `movie.dat`: record 0 grown `+0x10` (shifting records 1–107) → Sokolov
  briefing, parachute dialogue, landing, gameplay return, first codec all
  normal. Full 71-record grow (+225,424 B) also normal.
- `demo.dat`: record 286 grown `+0x10` (displacing the real first-video record
  287) → full Pakistan opening + movie handoff normal. Distant-pair and
  7-record-global grows also normal.
- Pure tail-padding relocation in these tests needed **no** GCX53-style low-24
  correction — don't generalize that to every rebuild/scene without checking.

## Known-unsafe / retired approaches

- `--grow-records` as a blanket unlimited-growth mode: retired as a deployment
  path, not because growth is impossible, but because the *scene-boundary*
  discipline above is required — see [Decisions](Decisions.md) DEC-007.
- `--size-neutral-reclaim` for movie/demo: replaced by `--fixed-layout-reclaim`
  (verified zero offset drift, 27/27 opening lines fit).

## Tools

| Tool | Role |
|---|---|
| `mgs3d_movie_tool.py` | inspect / capacity / extend-safe / build-korean, one-stop movie+demo equivalent of the codec pipeline |
| `mgs3d_demo_scene_compact.py` | scene-padding-budget-aware selection (the safe multi-scene growth tool) |
| `mgs3d_movie_sequence_match.py` | aligns EN/KO dialogue pairs to (record, entry) |
| `mgs3d_movie_record_review_html.py` | offline full-record editor, codec's capacity-review-html equivalent |
| `mgs3d_movie_precise_relocate.py` | GCX53-class low-24 relocation for movie/demo |
