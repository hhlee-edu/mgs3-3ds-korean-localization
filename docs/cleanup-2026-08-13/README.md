# MGS3D project inventory and reorganization plan — Phase 1 + 2

> **EXECUTED 2026-08-13, later the same day.** This document originally
> described a survey-only plan ("nothing moved"). The user reviewed it and
> authorized the physical move; it has since been carried out — 4,709 move
> operations, 0 failures, byte-exact size reconciliation confirming zero data
> loss. See `move_log.csv` (added below) for the authoritative old→new path
> map, and [`wiki/Decisions.md`](../../wiki/Decisions.md) DEC-015 for the
> summary. **Everything below this banner is preserved as the original
> pre-move audit** — paths mentioned in prose are the *old* locations; use
> `move_log.csv` to resolve any of them to where they live now. Current,
> living documentation is [`wiki/Home.md`](../../wiki/Home.md), not this file.

| Deliverable | Contents |
|---|---|
| `inventory.csv` / `inventory.json` | all 30,903 files with hash, class, destination, confidence (pre-move snapshot) |
| `move_log.csv` | **the executed move plan** — old path → new path, per-row status, for every file that moved |
| `duplicates.md` | SHA-256-verified duplicate groups |
| `unknown-list.md` | the 748 files that still could not be classified confidently (never moved) |
| `translation-auto-resolution-log.md` | how 251→114 ambiguous translation files were auto-sorted, and why |
| `id_keyed_decisions.json` / `content_decisions.json` | raw per-file measurements behind that auto-sort |
| `tools-classification.md` | 132 tools as ACTIVE / EXPERIMENTAL / UNKNOWN |
| `experiment-runs.md` | 29 candidate `experiments/<run>/` groups |
| `wiki-structure-proposal.md` | page set, document mapping, the durable rules |
| `Current-State-DRAFT.md` | reconciled Confirmed / Invalidated / Unverified (superseded by `wiki/Current-State.md`) |

---

## 1. Scale

| | |
|---|---|
| files | **30,903** |
| bytes | **140.6 GB** |
| git-tracked | 288 (source + docs only; all data is gitignored) |
| files containing Hangul | **899** |
| byte-identical duplicate groups | 2,990 → **29.3 GB redundant** |

Distribution — `analysis/` is 93 % of the tree:

| area | files | size |
|---|---|---|
| ORIGINALS | 21,556 | 12.05 GB |
| EXPERIMENTS | 7,635 | 72.73 GB |
| ARCHIVE | 661 | 33.66 GB |
| TRANSLATION | 307 | 0.52 GB |
| TOOLS | 239 | 0.01 GB |
| VENDOR | 233 | 0.95 GB |
| LOGS | 138 | 0.01 GB |
| WIKI | 50 | 0.00 GB |
| BUILDS | 34 | 20.62 GB |
| GLYPH | 28 | 0.00 GB |
| UNKNOWN | 22 | 0.00 GB |

By status (after the §3.1 auto-resolution pass): ORIGINAL 21,634 ·
EXPERIMENT 3,935 · GENERATED 3,518 · **UNKNOWN 748** (was 947) · ARCHIVE 727 ·
CURRENT 276 · MASTER 28 · SHORTENED 18 · OBSOLETE 12 · BUILD_INPUT 7.

The 21,556 "ORIGINALS" count is dominated by `analysis/script_ref/stages/`
(20,620 small PS2 stage-extract files, 1.81 GB).

---

## 2. Findings that need your decision

### 2.1 The golden CCI binary is gone, but it is reproducible

`docs/WIKI.md` names one boot-verified reference build, "never to be
overwritten":

```text
MGS SNAKE EATER 3D_Repack_______.cci   (7 underscores)
3,248,410,624 bytes
SHA-256 3BD843008721C8018054B041FD6DBDBA617C5DE99751D62E192F4082EE7E6504
```

**Name-collision hazard:** `Romforge\output\` tops out at `Repack______.cci`
(6 underscores), so the *next* repack writes 7 underscores — precisely the
filename the docs describe as the boot-verified golden, which would make a fresh
unverified build look authoritative.

**Searched exhaustively (2026-08-13):** every `.cci` on `C:\Users\hhlee` and all
of `D:` — 11 images total, listed below. None matches the golden hash. The
suggested location `C:\Users\hhlee\Desktop\metagear3d\romforge_jpn\output\unpacked`
holds **no CCI at all**; what is there is the *Japanese* unpacked romfs (the JP SKU
reference used for the EN/JP structural comparison), plus the JP and USA `.3ds`
cart dumps (4 GB each) at `metagear3d\`.

```text
4,028,456,960  Romforge\output\MGS SNAKE EATER 3D_Repack.cci … _Repack__.cci   (3 files)
4,028,522,496  …_Repack___.cci, _Repack____.cci
4,040,323,072  …_Repack_____.cci
4,083,195,904  …_Repack______.cci          <- the build HANDOFF says to test next
3,248,480,256  …\rejected_oversize\…_Repack__OVERSIZE_REJECTED.cci
4,294,967,296  analysis/global_korean_glyph_poc_2026-08-12/MGS3D_A0XX_GANADA_POC_v1_failed.cci
3,248,410,624  analysis/script_ref/_archive_2026-08-07/MGS3D_PS2KO_165_FIXED_FALLBACK_v3.cci
3,248,410,624  analysis/script_ref/_archive_2026-08-07/MGS3D_PS2KO_191_FIXED_TEST_Repack.cci
```

**Conclusion: the golden CCI binary no longer exists — but it is fully
reproducible.** `REPACK_VERSION_INDEX.md` records the golden's input directory as
`script_ref/staging_tom_codec_original_media/`, and all five documented input
hashes verify there **5/5, byte-exact**:

| input | recorded SHA-256 | status |
|---|---|---|
| `codec.dat` | `C32E8C6B…51D1` | ✅ MATCH |
| `movie.dat` | `2B774C99…15F8` | ✅ MATCH |
| `demo.dat` | `E216F28F…5468` | ✅ MATCH |
| `stage/r_sna01/resident.hpk` | `6D751F2A…7B77` | ✅ MATCH |
| `stage/r_sna02/resident.hpk` | `BB72B8FA…9496` | ✅ MATCH |

Path: `analysis/script_ref/_archive_2026-08-07/staging_tom_codec_original_media/`.
Repacking that directory reconstructs the boot-verified golden build. The two
same-size 2026-08-03 archived CCIs are *different* builds from the same day, not
the golden.

**This makes the naming rule (R6) urgent rather than cosmetic:** the golden's
identity currently lives only in a recorded hash plus an archived input folder.
Rename builds before the next repack writes 7 underscores.

### 2.2 Korean reference ISO — RESOLVED, deletion is intentional

`메탈 기어 솔리드 3_한글.iso` (4,565,270,528 B) is not on disk; it sits in
`D:\$RECYCLE.BIN\…\$REV4BU2.iso`. **User confirmed 2026-08-13 that deleting the
image is fine.** No recovery needed; the Recycle Bin was left untouched.

This is safe because **everything extracted from it survives**, all five PS2
containers, read-only where it matters:

```text
analysis/script_ref/MGS/
  CODEC.DAT     41,724,368     <- the source of official Korean codec text
  DEMO.DAT   1,504,960,512  (r--)
  MOVIE.DAT    525,156,352  (r--)
  SLOT.DAT     157,562,880
  STAGE.DAT    874,813,440
```

Since PS2 movie/demo subtitles are hardsubbed (no extractable text) and
`CODEC.DAT` is preserved intact, the ISO carries no unique remaining value.

One correction to record, because it would mislead a future session: **`git
checkout` cannot restore that ISO.** Git holds a blob under the same path
(`ade3c8db…`) which is a valid ISO9660 image (`CD001` at `0x8001`) but only
**270,303,232 bytes** — a different, smaller image. `docs/WIKI.md` also describes
the ISO as "git 미추적" (untracked), which is wrong; it is tracked. Update
`wiki/Conventions.md` so nobody trusts git as the ISO's backup.

Other project files also sit in the Recycle Bin. Most are harmless (superseded
`gcx_batch_*.html` copies whose live equivalents match byte-for-byte), but two
have **no live counterpart**:

| file | size | assessment |
|---|---|---|
| `codec_compact_reviewed_batch02.json` | 218,113 | only `batch01` exists live |
| `codec_compact_reviewed_batch03.json` | 383,922 | only `batch01` exists live |

These are browser-review outputs from the workbench flow. `docs/WIKI.md` §2.3
notes batches 2–3 "had mechanical compression applied, then reverted", and that
you explicitly rejected algorithmic compression — so deleting them was most
likely deliberate and correct. Flagging them only so the decision is conscious
rather than accidental.

### 2.3 Size must never be used as identity here

40 files share size `772,935,680` and hold **22 distinct contents**. The
pipelines are deliberately size-preserving, so a size-based dedup would have
destroyed 18 unique builds. Every duplicate claim in `duplicates.md` is
SHA-256-verified. This is now rule **R4**.

### 2.4 Moving files will break recorded reproduction commands

`analysis/README.md` states plainly:

> Capacity reports, mappings, and historical extraction artifacts remain in the
> analysis root so recorded build and verification commands keep their paths.

Many docs cite exact `analysis/...` paths. A large move invalidates them. Options,
for your call:

1. **Move and rewrite** the path references in the docs at the same time (most
   work, cleanest result).
2. **Move and leave a path-map** (`archive/PATH-MAP-2026-08-13.csv`, old → new)
   so old commands remain traceable.
3. **Leave `analysis/` in place** and build the new tree only for
   originals/translation/glyph/wiki/builds.

My recommendation is (2): it preserves reproducibility at a fraction of the cost
of (1), and the inventory already contains both columns needed to generate the map.

### 2.5 The three orientation documents disagree with each other

- `docs/WIKI.md` contradicts **itself** on grow-mode safety: §3.1 and §6 say grow
  modes are deployment-banned, while its own appended 2026-08-10 section
  concludes codec grow is usable.
- `HANDOFF.md` stacks sessions newest-first; its 2026-08-12 "do not retry"
  instruction is explicitly voided by the 2026-08-13 section above it.
- `docs/INDEX.md` stops at 2026-08-12 and omits the newer global-Korean-glyph and
  load-size documents.

`Current-State-DRAFT.md` resolves these into Confirmed / Invalidated / Unverified.
Please check the Invalidated table — that is where I made judgement calls.

### 2.6 Backups are inside the live romfs tree

Already flagged in `HANDOFF.md`, still true, and it is a build-correctness bug
rather than untidiness — repack bundles the whole folder:

- `Romforge\output\unpacked\partition0\romfs\demo.dat.bak-before-autofit106-2026-08-07` (772,935,680 B)
- `…\romfs\movie.dat.bak-before-record0-2-3-5-12-28-29-2026-08-07` (229,376 B)

Outside this repository, so I did not move them.

---

## 3. Translation assets (Phase 3)

286 files classified as translation assets (307 minus 21 that §3.1 pass 5
correctly reclassified out — glyph-allocation diagnostics and build smoke
tests, not translation text); 899 files overall contain Hangul (the remainder
sit inside experiment runs and are flagged `CONTAINS KOREAN - protect` in the
inventory).

**Established with confidence:**

| Role | File |
|---|---|
| MASTER | `analysis/script_ref/codec-3ds-INTEGRATED-review.csv` — 11,076,065 B, sha `a836d562…` |
| MASTER (manual backlog) | `…/codec-3ds-INTERGRATED-review.csv_trans/1999final.csv`, `trans1999.csv` |
| ARCHIVE | 4 dated `codec-3ds-INTEGRATED-review.csv.*bak` snapshots |
| SOURCE | `analysis/script_ref_mgs3/page_*.html`, `대사집 대사집/script_ref_mgs3_full.json` |
| SOURCE | `analysis/gamefaqs_mgs3_english.*` (PS2 English pivot anchor) |
| BUILD_INPUT | `analysis/script_ref/full_build/translator_worklist_*.csv` |

**Resolved by hashing:** the `codec-3ds-INTEGRATED-review.csv` sitting inside the
`_trans/` folder is byte-identical to `…before-1999-merge-2026-08-05.bak`
(sha `75d291c1…`). It is a superseded pre-merge snapshot, **not** a second
master. Only one live master exists.

### 3.1 Second pass: 251 → 114, anchored on the bundle you pointed to

You confirmed `analysis/1 korean_localization_bundle_2026-08-12/` as the
consolidated final material. **Its own `README.md` already states the answer**
— it explicitly separates `natural_full_pre_compaction/` ("축약 전 자연번역
authority") from `applied_compact/` ("용량 제한 적용·축약본… 기준본으로 사용하지
않는다"). That gave a ground truth to propagate outward from, in five
increasingly-automated passes — each logged, nothing moved:

| Pass | Method | Resolved |
|---|---|---|
| 1 | Bundle's own README roles, applied to its 56 files | 55 |
| 2 | Exact SHA-256 match to an already-resolved file, anywhere in the tree | 103 |
| 3 | (gcx,resource) / (record,entry) **ID-keyed** comparison against the bundle's master corpus — robust to text-formatting drift, unlike a raw english-string join | 25 |
| 4 | Confirmed-unmerged matching artifact (see below) | 39 |
| 5 | `*.dat.hangul.json` / `*smoke*` reclassified out of TRANSLATION (glyph-allocation diagnostics, not text) + 2 direct doc-citation resolutions | 23 |
| | **Total** | **137 / 251 (55 %)** |

Pass 3's ID-keyed check produced a finding worth keeping: most of the Korean
content in `full_build/_scratch/3way/*_comparison_*.csv` **does not exist in the
current master by ID at all** — not a handful of edge cases, but the bulk of it
(e.g. `demo_korean_comparison_3way.csv`: 5 exact / 882 matched keys / 889 Korean
rows). That is not an open MASTER-vs-SHORTENED question — it is confirmation
that these are **still-pending 3-way matching output that was never merged**,
exactly what `docs/WIKI.md` §4.9 describes them as. That specific role — pending
matching candidate, not master, not shortened — is what pass 4 recorded, safely,
because there is no master-quality text at risk in calling a match "not yet
merged."

Two resolutions in pass 5 rest on direct quotes rather than inference:
- `analysis/review/codec/codec_korean_context_review_v3.csv` — `analysis/README.md`
  literally says "completed 298/298 approved review."
- The `movie_korean_comparison_exact*.csv` / `demo_korean_comparison_exact*.csv`
  family — `docs/WIKI.md` §4.3 names these exact files as keyed to the
  pre-2026-08-08 parser, incompatible with the current one. mtimes (2026-08-01/02)
  confirm.

**Deliberately not resolved — still needs your eyes (114 files, mostly under
`analysis/script_ref/`):**

The biggest unresolved cluster by size is the `codec_selected_static_media*.json`
/ `codec_translation_static_media*.json` / `early-priority-selection*/` family
(~9 files, 3.3–23 MB each). ID-keyed comparison shows most of their Korean
content isn't explained by the current master, but unlike the 3way cluster I
can't tell *why* — a genuinely wider resource universe than the master covers,
an abandoned "static media" approach from the 2026-08-03 TOM-patch era, or
something else. Also unresolved: `stage_text_catalog.csv` (27 MB, OCR'd PS2
stage text — may not be dialogue at all), `local_glyph_ocr/ocr.json` (raw OCR
output), and roughly 90 small (<0.7 MB) diagnostic/capacity files. Full list:
`unknown-list.md`.

**Note on filenames:** 57 paths contain Hangul, and several use CP949-era encoding
(`대사집 대사집/`, `화면 캡처 …png`). Any move must preserve the exact bytes; a
careless rename will mangle them.

---

## 4. Tools (Phase 4 — classification only)

132 tools (excluding `tools/_vendor/`, a vendored capstone).

| | count |
|---|---|
| ACTIVE (referenced by docs/code/tests) | 82 |
| EXPERIMENTAL (untracked; global-Korean-glyph track) | 9 |
| UNKNOWN (no inbound reference) | 41 |

The 41 UNKNOWN are **not** proposed for archiving. Absence of a reference is weak
evidence for a hand-run CLI tool: my first scan called `mgs3d_gcx_workbench.py`
unreferenced, when `docs/WIKI.md` §2.3 documents it as the active review
workbench. Only one true version-collision family exists
(`mgs3d_korean_eof_append_poc.py` vs `_poc_v2.py`), so R5 costs almost nothing
to adopt.

29 experiment runs are grouped in `experiment-runs.md`; the largest are
`script_ref/full_build` (26.6 GB), `story_media_order/romforge_apply_v1`
(11.6 GB) and `global_korean_glyph_poc_2026-08-12` (12.3 GB across two subdirs).

---

## 5. What I propose to do next — awaiting your approval

Nothing below has been started.

| Step | Effect | Risk |
|---|---|---|
| A | Create `wiki/` and write `Home`, `Current-State`, `Decisions`, `Conventions` from the drafts | none — new files only |
| B | Shrink `HANDOFF.md` to the six fields, moving detail into wiki pages | low — content preserved |
| C | Move `docs/session-handoff-*.md` etc. into `wiki/History/` with superseded banners | low |
| D | Create `originals/` and hash-verify against `originals/hashes/` | none — copy/verify first |
| E | Build `translation/` **only** for the roles proven in §3 | low — UNKNOWN stays put |
| F | Group experiment runs under `experiments/`, add README + manifest per run | medium — path references (§2.4) |
| G | Rename builds to meaningful names + manifests (R6) | medium — do before the next repack |
| H | Reclaim the 29.3 GB of hash-verified duplicates | **destructive — separate approval** |

Suggested order: A → B → C (documentation, zero risk) before any file movement,
so the wiki exists to describe the move while it happens.

**Resolved 2026-08-13 (no longer blocking):**

- PS2 ISO (§2.2) — deletion confirmed intentional; extracts preserved.
- Golden CCI (§2.1) — binary is gone but reproducible from
  `staging_tom_codec_original_media/`, 5/5 input hashes verified. Step G (build
  renaming) should therefore happen **before the next repack**.

**Open questions for you:**

1. Path-reference strategy (§2.4) — my recommendation is the path-map.
2. The 114 remaining unresolved translation files (§3.1) — the biggest chunk is
   the `codec_selected_static_media*` / `early-priority-selection*` cluster
   (~9 files). Worth walking together, or leave indefinitely?
3. Step H (duplicate reclamation) — hold entirely for now, or proceed for the
   `_archive_2026-08-07` subtree only?
