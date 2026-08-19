# MGS3D Korean Localization — Wiki

reference Korean release ported onto the 3DS release of *Metal Gear Solid:
Snake Eater 3D*. This wiki is the canonical knowledge base — new session
reading order: `README.md` → **this page** → [Current State](Current-State.md)
→ `HANDOFF.md` ([Conventions](Conventions.md) R11).

## Start here

- **[Current State](Current-State.md)** — the technical single source of
  truth: Confirmed / Invalidated / Unverified, current build, known issues,
  next steps. Read this before trusting any other document's conclusions.
- **[Decisions](Decisions.md)** — numbered project decisions and why they were
  made.
- **[Conventions](Conventions.md)** — the durable management rules (asset
  separation, translation lineage, build naming, …) established 2026-08-13.

## By topic

- **[Translation](Translation.md)** — source→master→shortened→build-input
  lineage, the current ground-truth bundle, the live production master CSV.
- **[Matching](Matching.md)** — the 3-way PS2/the script reference/3DS alignment
  pipeline, the script reference colour-box classification, review states.
- **[Glyph System](Glyph-System.md)** — the per-GCX custom-glyph mechanism,
  the 191-slot HPK static font, and the newer resident global-Korean-page
  track.
- **[GCX Format](GCX-Format.md)** — `codec.dat` structure, donor-reclaim
  growth mechanism, GCX53 relocation.
- **[DAT Formats](DAT-Formats.md)** — `movie.dat`/`demo.dat` record structure
  and the 130-scene multiplex container.
- **[Build System](Build-System.md)** — RomForge pipeline, the golden build,
  build naming.
- **[Runtime Debugging](Runtime-Debugging.md)** — the Citra/Azahar + GDB
  attach recipe.
- **[Experiments](Experiments.md)** — index of `analysis/` experiment runs.

## History

[`wiki/History/`](History/) holds the dated session records verbatim — the raw
evidence behind every claim in Current-State. Superseded conclusions are never
deleted, only marked as superseded (R8). Start with `docs/INDEX.md`'s former
role, now folded into Current-State's Invalidated table.

## Full file inventory

A complete 2026-08-13 classification of every file in the project (30,903
files, hashed and role-tagged) lives in
[`docs/cleanup-2026-08-13/`](../docs/cleanup-2026-08-13/README.md). The
physical data reorganization it proposes is deferred ([DEC-013](Decisions.md));
this wiki is the documentation half of that cleanup, done first.
