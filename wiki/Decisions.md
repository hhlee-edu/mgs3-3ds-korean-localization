# Decisions

Project decisions, distinct from plain discoveries (discoveries live in
[Current State](Current-State.md)). Each gets an ID so nobody has to
re-derive "why did we do it this way" from session logs again.

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
| DEC-011 | Rename all builds to meaningful names + a manifest before the next repack | `Romforge\output\` is one repack away from writing `Repack_______.cci` — the golden's own documented filename — over an unverified build | ACTIVE, urgent |
| DEC-012 | The `analysis/1 korean_localization_bundle_2026-08-12/` bundle (decomposed 2026-08-13 into `translation/00_source`, `10_master`, `30_shortened`, `40_build_input`; its README preserved at `translation/BUNDLE-README-2026-08-12.md`) is the consolidated translation ground truth; its README's MASTER/SHORTENED split is authoritative | user confirmation, 2026-08-13 | ACTIVE |
| DEC-013 | Wiki documentation reorganization done before the physical `analysis/` data reorganization | 2026-08-13 project cleanup was judged "too vast" to do both in one pass; docs (git-tracked, reversible) came first, the 140 GB data move followed same-day once the wiki existed to describe it | SUPERSEDED by DEC-015 (both phases now done) |
| DEC-014 | PS2 Korean ISO deletion is acceptable | all five extracted PS2 containers survive in `originals/ps2/`; movie/demo subtitles are hardsubbed so the ISO carried no unique extractable value beyond them | ACTIVE |
| DEC-015 | Execute the full physical reorganization (`originals/`, `vendor/`, `translation/`, `glyph/`, `experiments/`, `builds/`, `archive/`, `logs/`) as same-volume moves, driven by the 2026-08-13 inventory, never touching `UNKNOWN`/`IN_PROGRESS`-status files | explicit user instruction ("재배치로 마무리하자"); dry-run first caught a would-be catastrophic collision (169 stage files sharing one basename) and a hash-propagation bug (0-byte files falsely inheriting `ORIGINAL` status) before either could cause damage | ACTIVE — 4,709 moves executed, 0 failures, byte-exact size reconciliation (140.56→140.58 GB, delta fully explained by this session's own new files) |

| DEC-016 | Adopt the USA clean V2 build as the global Korean page baseline | V0a/V0b/V0c/V1/V2 passed; the renderer probe displayed `호프번`; three distinct stage bases matched 4 KiB exactly | ACTIVE |
| DEC-017 | Stop cross-stage GDB sampling after three distinct PASS results and move to 928-character integration review | further traversal requires unrelated game progress while adding little evidence; user explicitly limited it | ACTIVE |
| DEC-018 | Extend the verified 928-token map append-only for canonical-master changes | frequency re-sorting changed 420 existing assignments; preserving all verified tokens and adding `칸` at `0x87A4` avoids needless remapping | ACTIVE |

Add new decisions here as they're made — DEC-IDs are assigned once, never
reused, and never removed even if a decision is later reversed (mark it
`REJECTED` or `SUPERSEDED`, don't delete the row).
