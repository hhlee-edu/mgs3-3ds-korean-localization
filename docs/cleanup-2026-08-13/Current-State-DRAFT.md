# Current State (DRAFT — proposed `wiki/Current-State.md`)

Reconciled 2026-08-13 from `docs/WIKI.md`, `docs/INDEX.md`, `HANDOFF.md` and the
dated docs. **This is a draft for review, not yet the canonical page.** Where two
documents disagreed, the newer *evidence* wins and the older claim is recorded
under Invalidated rather than deleted.

---

## Confirmed

### Resident asset / global Korean glyph track (newest)
- `scenerio.gcx` resident load size **= the RomFS file size itself**. Not external
  metadata, not a container field, not a fixed request argument.
  (`docs/load-size-source-confirmed-2026-08-13.md`)
- **Bytes appended after EOF do become resident.** Verified byte-for-byte live.
- Korean page live comparison: **192/192 bytes match**.
- `K = 0x56000` in the current 169-stage build.
- Korean page VA `= table[2] + 0x56000`, and the trampoline's own formula
  `*(0x00A46FE0) + 0x56000` resolves to that same address.
- `table[2] @ 0x00A46FE0`.
- Descriptor entry layout: `+0x00 tag / +0x04 ptr / +0x08 size`, stride `0x14`.
- Descriptor tag `0x02180720` is a **resource-class tag** for "stage scenerio",
  identical across `title` and `v001a` — not a per-file hash.
- **169 stages**; page2 offsets come from the **parser formula**.
- GCX containers have **no self-size field** (full u32 scan of 4 files, 0 hits).
- `scenerio` / `.gcx` strings are **not** in `code.bin`. Stage paths are built as
  `stage/%s/` (VA `0x0088F270`, builder `0x0012F324`); extension table
  `0x00908368` stride 8, `'gcx'` @ `0x009083E8`.
- `FSFILE_GetSize` IPC stub is unique: `0x008370DC`. Its only wrapper
  `0x008671B4` is reached solely through vtable slot `0x008ADE24`.

### Structure and relocation
- **The governing principle:** a structural unit's own boundary cannot move;
  growth must be funded from *that unit's own* slack — demo/movie from the
  scene's trailing zero padding, codec from donor-reclaimed bytes inside the GCX.
- `demo.dat` is a **130-scene multiplex container**, `kind = (stream<<16)|type`,
  every scene aligned to `0x800`, walked end-to-end with 0 desync and 0
  undecoded bytes. type=2 media payload, type=4 subtitle records, type=16 scene
  boundary, type=240 per-scene trailer.
- GCX53 relocation root cause: three procedure-table offsets past the inner
  `0x1000` boundary (`+0x64/+0x70/+0x7C`, low 24 bits). Descriptor `0x0200457B`
  selects a fixed container start and must **not** be moved with it.
  Generalized as `relocate_gcx_internal_offsets(record, old, new)`.
- `codec.dat` distributed grow is usable **when accompanied by procedure/internal
  low-24 relocation** — 7 spread GCX, +16,720 bytes, 2,312 GCX shifted,
  full 2,326-GCX / 216,705-word verifier pass, Azahar-verified.
- `movie.dat`/`demo.dat` grow relocation verified 2026-08-10, including a
  71-record grow (+225,424 B) and displacement of the real first video.
- `codec.dat` = **2,326 GCX**. 3DS `movie.dat`/`demo.dat` record structure fully
  decoded with lossless round-trip.

### Source material
- PS2 `MOVIE.DAT` is plain MPEG-2 PS; **Korean subtitles are hardsubbed**, so no
  extractable extractable reference movie text exists. the script reference is therefore the
  effective movie/demo Korean source, not merely a diagnostic.
- The "western 5-language" `movie.dat` structure is **this project's own
  reconstruction**, not stock Japanese. The golden build depends on it, so it
  stays.
- 3DS English text is a **work-in-progress placeholder**, not shipped final text
  — reducing English to buy capacity is cheap.
- the script reference author's own colour boxes classify lines: grey = cutscene
  (movie/demo) 933, green = codec 406, no box 1,692.
- `LA2` = Nintendo DARC; `ARC` = Capcom MT Framework.

---

## Invalidated

Each line is a claim that was believed true and is now disproven. The original
document is kept as evidence; only the conclusion is retired.

| Retired claim | Superseded by |
|---|---|
| "EOF-appended data is not resident" (2026-08-12) | 2026-08-13 live byte-for-byte match |
| "Resident read extent = original file size, so append is capped" (2026-08-13, 1st session) | 2026-08-13 2nd session: size follows the RomFS file size |
| `K = 0x35000` | current build uses `K = 0x56000` |
| stage count = 91 | **169** |
| signature-only page2 discovery | parser formula (signature scan missed 78 of 169) |
| "demo growth is limited to exactly 1 record; 2+ inherently unsafe" | scene-start rule; the failing sets all happened to touch a scene before #127 |
| "a demo record has an absolute size cap around 5–6 KB" | explained by scene-boundary displacement, not a record cap |
| "codec.dat growth is impossible" | distributed grow + low-24 relocation works |
| "movie/demo grow modes are deployment-banned" | 2026-08-10 relocation validation (**note:** `docs/WIKI.md` still asserts the ban in §3.1/§6 while its own appended 2026-08-10 section contradicts it) |
| `--size-neutral-reclaim` for movie/demo | replaced by `--fixed-layout-reclaim` |
| "GCX1412 holds 986 Japanese glyphs" | measured on the JP file by mistake; EN original has 0 glyph slots |
| demo parser "2,091 entries" | **333 records / 11,296 entries** |
| Japanese source reassembly pipeline | abandoned in favour of the English→Korean pivot |
| `weak_foreign_anchor()` | removed; misclassified English as foreign |
| fixed-radius batch dialogue matching | rejected; GCX adjacency does not imply conversation |

---

## Unverified

- **Whether `0x8401..0x8403` actually render as Hangul on device/Citra.** Data
  residency and pointer arithmetic are confirmed; only the renderer trampoline
  remains untested. This is the single next task.
- Whether `movie.dat` uses the same scene container as `demo.dat` (assumed, never
  directly confirmed).
- The leading ~646 KB header/index region of PS2 `DEMO.DAT`.
- Full decode of the `kind=2` block.
- The exact count at which simultaneous codec GCX grow breaks.
- The role of the 1,692 "no colour box" the script reference lines.
- Whether grow is safe for *arbitrary* GCX at *arbitrary* sizes (validated range
  only).

---

## Current Build

**Golden CCI — the binary no longer exists, but the build is reproducible.**

- Recorded golden: `MGS SNAKE EATER 3D_Repack_______.cci` (7 underscores),
  3,248,410,624 bytes, SHA-256 `3BD843…E6504`.
- Confirmed absent: all 11 `.cci` images on `C:\Users\hhlee` and `D:` were
  enumerated and hashed; none matches. Two archived images match the golden
  **size** exactly but not its hash — a size collision, not the golden.
- **Reproducible from `analysis/script_ref/_archive_2026-08-07/staging_tom_codec_original_media/`**,
  which `REPACK_VERSION_INDEX.md` names as the golden's input directory. All five
  recorded input hashes verify there 5/5 byte-exact (`codec.dat` `C32E8C6B…`,
  `movie.dat` `2B774C99…`, `demo.dat` `E216F28F…`, `r_sna01/resident.hpk`
  `6D751F2A…`, `r_sna02/resident.hpk` `BB72B8FA…`). Repacking that folder
  reconstructs the boot-verified build.
- ⚠️ **Name-collision hazard:** `Romforge\output\` tops out at 6 underscores, so
  the next repack writes the golden's documented filename. Rename builds (R6)
  before repacking.

- Build named by `HANDOFF.md` as the one to test next:
  `Romforge\output\MGS SNAKE EATER 3D_Repack______.cci` (6 underscores),
  4,083,195,904 bytes, 2026-08-12 23:54. Statically verified as the 169-stage
  patch build (Korean page signature appears exactly 169 times).

## Current Data

- codec master review CSV: `analysis/script_ref/codec-3ds-INTEGRATED-review.csv`
  (11,076,065 B, sha `a836d562…`) — the live master.
- Manual backlog for 대사집 미매칭 codec lines:
  `analysis/script_ref/codec-3ds-INTERGRATED-review.csv_trans/`
  (`1999final.csv`, `trans1999.csv`). Note the folder name contains the typo
  `INTERGRATED`.
- The `codec-3ds-INTEGRATED-review.csv` copy inside that `_trans/` folder is
  **byte-identical to `…before-1999-merge-2026-08-05.bak`** (sha `75d291c1…`),
  i.e. a superseded pre-merge snapshot, not a second master.

## Known Issues

- `HANDOFF.md` (31 KB) carries stacked, mutually contradicting session layers;
  its 2026-08-12 "do not retry" instruction is explicitly void.
- `docs/WIKI.md` contradicts itself on grow-mode safety (see Invalidated).
- `docs/INDEX.md` stops at 2026-08-12 and omits the newer global-Korean-glyph and
  load-size documents.
- ⚠️ Backup files are sitting **inside** the live RomForge romfs tree
  (`demo.dat.bak-before-autofit106-2026-08-07`, 772,935,680 B, and a movie.dat
  backup). Repack bundles the whole folder.

## Next

1. Boot `Repack______.cci` (6 underscores) and look at `0x8401..0x8403`.
2. Resolve the golden-CCI question above and rename builds to meaningful names
   before the underscore counter reaches 7.

## Do Not Reinvestigate

- Whether appended-EOF bytes are resident — settled, they are.
- Where the load size comes from — the RomFS file size.
- Whether GCX53 can move — it can, with low-24 relocation.
- Whether PS2 movie/demo hold extractable Korean text — they do not, hardsubbed.
- Whether codec growth is possible at all — it is.
- Any French / Spanish / German / Italian donor text as translation material.
