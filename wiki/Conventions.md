# Conventions

Durable management rules for this project, established 2026-08-13
([DEC-013](Decisions.md)). These govern how files, translations, tools, builds,
and documentation get handled from now on.

**Status:** the documentation side (this wiki) is built. The physical data
reorganization described in §1 (moving `analysis/` into `originals/`,
`translation/`, `glyph/`, etc.) is the target structure but has **not** been
executed — it was judged too large to do in the same pass as the documentation
cleanup. Until it happens, apply these rules to *where new work goes*, not as a
claim about where files currently sit. Check `docs/cleanup-2026-08-13/inventory.csv`
for a file's actual current location and proposed destination.

## 1. Asset separation (target structure)

Nine areas, never mixed, plus `vendor/` for third-party runtime:

```text
originals/     game files, read-only, never modified
translation/   Korean text, source through build-input
glyph/         font/glyph/token-map assets
tools/         current, canonical scripts
experiments/   POC/experiment runs, one directory each
builds/        reproducible test/release builds
logs/          GDB/the build logs
wiki/          this — the knowledge base (built)
archive/       retired but not deleted
vendor/        third-party runtime (Citra, Qt DLLs) — belongs to none of the above
```

## 2. Rules

**R1 — Asset separation.** See §1. Don't blend originals with generated output,
or master translation with shortened/capacity-driven variants.

**R2 — Originals are read-only.** Nothing under `originals/` (or, today,
`originals/ps2/`, `partition0/`) is ever written. Verify by hash
before trusting one.

**R3 — Translation lineage is one-directional.**
`00_source → 20_matching → 10_master → 30_shortened → 40_build_input`.
A capacity-driven abbreviation **never** overwrites the master. If the global
Korean page removes the glyph limit, restore high-quality text *from* the
master. See [Translation](Translation.md) for the current lineage map.

**R4 — Size is not identity.** Never deduplicate, compare, or verify a build
artifact by file size. This project's pipelines are deliberately
size-preserving: 40 files share one size and hold 22 distinct contents (see
`docs/cleanup-2026-08-13/duplicates.md`). SHA-256 only.

**R5 — One canonical tool per job.** `v2`/`v3`/`final` variants belong in
`archive/obsolete-tools/`, not `tools/`. See
[`docs/cleanup-2026-08-13/tools-classification.md`](../docs/cleanup-2026-08-13/tools-classification.md)
for the current ACTIVE/EXPERIMENTAL/UNKNOWN split.

**R6 — Build naming.** {#r6-build-naming} No `_`, `__`, `______` names — ever.
Every significant build gets a manifest: name, timestamp, baseline hash,
code.bin hash, DAT hashes, patch list, Korean-page version/hash, token-map
version/hash, stage patch count, `K`, output CCI hash. Urgent right now: see
[DEC-011](Decisions.md).

**R7 — RomForge `output/unpacked` is disposable staging, not storage.** No
`.bak`, log, or analysis file ever sits inside the romfs tree — repack bundles
the whole folder. See [Current State](Current-State.md#known-issues) for the
current violation.

**R8 — Facts live in `Current-State.md`; history stays where it happened.**
When a conclusion is overturned, record both: new fact in Confirmed, old fact
in Invalidated. Never edit history to hide a wrong turn — that's what
[History](History/) is for.

**R9 — Every experiment is a directory.** `experiments/YYYY-MM-DD-name/` with
`README.md` (purpose / baseline / change / result / PASS·FAIL·INCONCLUSIVE /
effect on current conclusions), `input/`, `output/`, `scripts/`, `logs/`,
`manifest.json`.

**R10 — Uncertain means untouched.** A file whose role can't be established
stays exactly where it is, marked `UNKNOWN`, until a human resolves it. Active
in-progress work (see [Translation](Translation.md#in-progress-material)) is
its own category, distinct from `UNKNOWN` — don't force a sort on material
that's deliberately still being worked.

**R11 — Reading order for a new session.**
`README.md → wiki/Home.md → wiki/Current-State.md → HANDOFF.md`.

**R12 — `HANDOFF.md` holds only six things:** current goal, what this session
did, where it is stuck, which wiki pages to read, the exact next task, and
cautions. Technical knowledge goes in the wiki, not there.
