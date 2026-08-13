# Wiki structure proposal — 2026-08-13

> **EXECUTED 2026-08-13, same day.** `wiki/` now exists with all core and topic
> pages; all 45 dated docs moved to `wiki/History/`; `docs/WIKI.md` and
> `docs/INDEX.md` got superseded banners + fixed internal links; `README.md`
> points at `wiki/Home.md`. The physical `analysis/` data reorganization below
> (§1, §5) is still deferred per [DEC-013](../../wiki/Decisions.md) — this
> proposal's *documentation* half is done, its *data* half is not. Original
> proposal text kept below unchanged for reference.

Proposal only when written. `docs/WIKI.md` and `docs/INDEX.md` already did part
of this job; the plan below **absorbed them** rather than starting over.

---

## 1. Page set

```text
wiki/
├─ Home.md                 entry point; links only, no content of its own
├─ Current-State.md        the technical single source of truth
├─ Decisions.md            numbered decisions with rationale (DEC-NNN)
├─ Conventions.md          the durable management rules (section 3 below)
├─ Build-System.md         RomForge flow, staging, manifests, naming
├─ Translation.md          the SOURCE→MASTER→SHORTENED→BUILD_INPUT lineage
├─ Matching.md             3-way alignment, Shinsnote colour classification
├─ Glyph-System.md         resident page, token map, capacity budgets
├─ GCX-Format.md           codec.dat / scenerio.gcx container + procedure tables
├─ DAT-Formats.md          movie.dat / demo.dat records and the scene container
├─ Runtime-Debugging.md    Azahar/Citra + GDB recipe, known traps
├─ Experiments.md          index of experiments/, links only
└─ History/               dated session records, moved verbatim
   ├─ 2026-08-01-session-handoff.md
   └─ …
```

`Home.md` links to every page above. Cross-links use plain relative Markdown
(`[Current State](Current-State.md)`), which works on GitHub wikis, in-editor,
and on disk.

## 2. Mapping from today's documents

| Today | Proposed | Action |
|---|---|---|
| `docs/WIKI.md` §1 absolute rules | `Conventions.md` + `Current-State.md` | split: rules vs. facts |
| `docs/WIKI.md` §2 codec pipeline | `Translation.md`, `GCX-Format.md` | split by topic |
| `docs/WIKI.md` §3–4 movie/demo | `DAT-Formats.md`, `Matching.md` | split by topic |
| `docs/WIKI.md` §6 abandoned approaches | `Decisions.md` (status `REJECTED`) | becomes decisions |
| `docs/WIKI.md` §7 folder map | `Conventions.md` | rewrite after the move |
| `docs/WIKI.md` §8 history index | `History/` + `Home.md` | keep as index |
| `docs/INDEX.md` current/superseded | `Current-State.md` Confirmed/Invalidated | merge, then retire the file |
| `docs/session-handoff-*.md` | `History/` | move verbatim, add banner |
| `docs/*-2026-08-1*.md` (topic docs) | `History/` + cited from `Current-State.md` | move, keep as evidence |
| `HANDOFF.md` | stays at root, **shrunk** to the 6 fields | rewrite |
| `docs/*.csv`, `*.json` | not wiki content | route via inventory |

**Nothing gets deleted.** A superseded document keeps its file and gains a
one-line banner pointing at the current page:

```markdown
> **SUPERSEDED 2026-08-13.** Conclusion retired; kept as experimental evidence.
> Current: [Current State](../Current-State.md).
```

## 3. Durable management rules (proposed `Conventions.md`)

These are the rules the project follows from now on — the point of the exercise.

**R1 — Asset separation.** Nine areas, never mixed: `originals/`,
`translation/`, `glyph/`, `tools/`, `experiments/`, `builds/`, `logs/`, `wiki/`,
`archive/`. Plus `vendor/` for the emulator/Qt binaries, which belong to none of
the nine.

**R2 — Originals are read-only.** Nothing under `originals/` is ever written.
Verified against `originals/hashes/`.

**R3 — Translation lineage is one-directional.**
`00_source → 20_matching → 10_master → 30_shortened → 40_build_input`.
A capacity-driven abbreviation **never** overwrites `10_master`. If the global
Korean page removes the glyph limit, high-quality text is restored *from*
`10_master`.

**R4 — Size is not identity.** Never deduplicate, compare, or verify a build
artifact by file size. This project's pipelines are deliberately size-preserving:
40 files here share one size and hold 22 distinct contents. SHA-256 only.

**R5 — One canonical tool per job.** `v2`/`v3`/`final` variants are allowed to
exist only in `archive/obsolete-tools/`. `tools/` holds the canonical one.

**R6 — Meaningful build names + a manifest.** No `_`, `__`, `______` names. Every
significant build carries a manifest (name, timestamp, baseline hash, code.bin
hash, DAT hashes, patch list, Korean-page version/hash, token-map version/hash,
stage patch count, `K`, output CCI hash) sufficient to reproduce it.

**R7 — RomForge `output/unpacked` is disposable staging, not storage.** No
`.bak`, log, or analysis file ever sits inside the romfs tree — repack bundles
the whole folder.

**R8 — Facts live in `Current-State.md`; history stays where it happened.** When
a conclusion is overturned, record both: new fact in Confirmed, old fact in
Invalidated. Never edit history to hide a wrong turn.

**R9 — Every experiment is a directory.** `experiments/YYYY-MM-DD-name/` with
`README.md` (purpose / baseline / change / result / PASS·FAIL·INCONCLUSIVE /
effect on current conclusions), `input/`, `output/`, `scripts/`, `logs/`,
`manifest.json`.

**R10 — Uncertain means untouched.** A file whose role cannot be established
stays exactly where it is, marked `UNKNOWN`, until a human resolves it.

**R11 — Reading order for a new session.**
`README.md → wiki/Home.md → wiki/Current-State.md → HANDOFF.md`.

**R12 — `HANDOFF.md` holds only six things:** current goal, what this session
did, where it is stuck, which wiki pages to read, the exact next task, and
cautions. Technical knowledge goes to the wiki, not here.

## 4. `Decisions.md` seed

Extracted from existing documents; IDs assigned now so they can be cited.

| ID | Decision | Rationale | Status |
|---|---|---|---|
| DEC-001 | Drop signature-based page2 discovery for the parser formula | signature scan missed 78 of 169 stages | ACTIVE |
| DEC-002 | Korean page delivered by EOF append | resident 192/192 B live-verified | ACTIVE |
| DEC-003 | Port the PS2 official Korean text; do not author a new translation | project goal | ACTIVE |
| DEC-004 | Never spend effort on FR/ES/DE/IT donor text | only EN/KO matter; donor text is capacity, not content | ACTIVE |
| DEC-005 | Abandon the Japanese source-reassembly pipeline | superseded by the English→Korean pivot | REJECTED |
| DEC-006 | Fund all growth from the structural unit's own slack | scene/GCX boundaries cannot move | ACTIVE |
| DEC-007 | Use `--fixed-layout-reclaim`, not `--size-neutral-reclaim`, for movie/demo | verified zero offset drift | ACTIVE |
| DEC-008 | Quarantine fixed-radius batch matching | GCX adjacency does not imply conversation | REJECTED |
| DEC-009 | Shinsnote is the movie/demo Korean source of record | PS2 movie subtitles are hardsubbed | ACTIVE |
| DEC-010 | Text authoring is the human translator's job, not bulk AI | user instruction | ACTIVE |

## 5. Deliberate deviations from the requested layout

- **`vendor/` added.** `Citra/`, `plugins/`, `scripting/`, `citra*.exe`,
  `Qt6*.dll`, `qt.conf`, `license.txt` (~0.95 GB, 233 files) are third-party
  runtime, not project assets. Forcing them into `tools/` would violate R1.
- **`originals/ps2/` and `originals/ps2_stages/` added.** The requested tree has
  `originals/{romfs,exefs,hashes}` only, which covers the 3DS side. The PS2 ISO
  extract (3.1 GB) and PS2 stage extract (1.8 GB, 20,620 files) are also
  originals and need their own homes.
- **`translation/00_source/shinsnote/`** rather than a top-level Shinsnote
  folder, so the immutable-source rule (R2/R3) covers it.
- **`experiments/` keeps run names that already carry dates** (e.g.
  `global_korean_glyph_poc_2026-08-12`) rather than being renamed to
  `YYYY-MM-DD-name`. Renaming would break the reproduction commands recorded in
  the docs; see the risk note in `README.md`.
