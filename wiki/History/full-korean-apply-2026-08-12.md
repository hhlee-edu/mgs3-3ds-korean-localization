# Full Korean DAT apply — 2026-08-12 (rollback/correction)

> **Do not use the earlier full movie/demo outputs.** The first Pakistan demo
> stalled because `--grow-records-reclaim` changed record and scene layout.
> Both live media DATs were rolled back. Only the merged codec build remains
> deployed.

## Applied corpus

- Translation source exists for movie 689 / 689 and demo 2,228 / 2,228 rows,
  but it is **not yet safe to deploy** under fixed layout.
- The exact safe-source rebase leaves 114 movie and 325 demo rows after first
  terminology compaction. Build candidates fit every subtitle: 69 movie / 184
  demo rows use mechanical punctuation/spacing reduction, while 48 movie / 147
  demo rows use a visibly provisional clipped ending and remain user-review
  items.
- `codec.dat`: official Korean plus 3DS-only merge, 7,305 / 7,305 Hangul units
  verified and deployed.

All three outputs were parsed again after rebuilding. Media verification compares
every translated subtitle's encoded bytes. Codec verification decodes the common
and per-GCX glyph tokens and compares the complete Hangul sequence.

## Shared glyph benefit

The benefit score counts one eliminated 64-byte local glyph slot for each
independent scope containing a character: GCX for codec and record for
movie/demo.

- runtime-verified 191-character map: 20,642 slots / 1,321,088 bytes avoided
- theoretical optimum for the completed corpus: 23,709 slots / 1,517,376 bytes
- theoretical additional saving: 3,067 slots / 196,288 bytes

The theoretical map was not deployed. Changing it requires rebuilding and
runtime-verifying both resident HPKs. The DAT builds use the existing resident
map whose two live HPK hashes match the archived proof.

## Frozen translation source

`analysis/translation_checkpoints/2026-08-12_pre_fixed_budget_compaction/`
contains seven source files plus SHA-256 `manifest.json`. Never edit checkpoint
copies in place. Reduced translations are derived into new CSVs.

Compaction policy: character and proper names use English spelling; reusable
English UI/mission terms are preferred; Korean particles and natural sentence
structure remain Korean. Anything still over its exact fixed capacity is put
in `*_fixed_budget_user_review_v1.csv` and is not silently truncated.

## Mandatory grow safety gate

Before a media build can be copied to Romforge, run
`tools/mgs3d_grow_safety_gate.py`. A candidate fails if file size, record size,
record/subtitle offsets, subtitle capacities/types, or (for demo) any scene
start differs from the original. Then run full content verification and a
Pakistan-scene runtime smoke test. A failure at any stage blocks deployment.

The gate self-test passes the original and rejects the known unsafe demo; see
`analysis/grow_safety/`.

The prepared full candidates are in
`analysis/fixed_budget_build_2026-08-12/`. They translate 689/689 movie and
2,228/2,228 demo rows, but deliberately remain undeployed because the gate
rejects their appended local-font growth:

- movie: +96,080 bytes
- demo: +297,024 bytes, with demo scene-start drift

The next plan item is therefore glyph-space funding: improve/rebuild the shared
resident glyph allocation (or prove an equivalent safe local-slot reuse), then
rebuild these same audited CSVs and rerun the mandatory gate.

## Optimized shared-glyph candidate

The exact fixed-budget corpus was reranked across 2,113 codec GCX/media record
scopes. The optimized 191-character allocation saves 656,000 bytes more local
glyph space than the verified baseline in aggregate. Both resident HPKs rebuild
inside their original compressed and file-size budgets (618 bytes compressed
padding each). Synchronized codec/movie/demo candidates are under
`analysis/shared_glyph_optimized_build_2026-08-12/` and content verification
passes 7,305/7,305 codec Hangul units, 689/689 movie rows, and 2,228/2,228 demo
rows.

This still leaves unfunded media growth of 54,128 bytes for movie and 207,040
bytes for demo. Demo scene compaction fails in 58 scenes, so these files remain
undeployed. Hybrid English-word review lists identify non-shared Korean words
whose replacement can eliminate remaining record-local glyphs; ordinary words
require contextual translation review before substitution.

## Grow-safe hybrid build staged in Romforge

A second-pass hybrid candidate replaces Korean word stems containing any
non-shared Hangul with position-aligned source-English words while retaining
shared-glyph Korean words/particles where possible. This is deliberately a
first-pass review build: automatic alignment is often unnatural and must not be
described as final-quality translation.

- movie: 689/689, appended local font bytes 0, live 245,520-byte base preserved
- demo: 2,228/2,228, appended local font bytes 0, all 130 scene starts preserved
- codec: 7,305/7,305 Hangul units, synchronized to the optimized resident map
- grow safety gate: movie pass, demo pass
- package: `analysis/romforge_ready_hybrid_livebase_2026-08-12/`
- rollback backup:
  `C:/Users/hhlee/Desktop/Romforge/output/backup_before_hybrid_grow_safe_20260812/`

The five-file atomic set was staged in the live Romforge unpacked tree and all
five SHA-256 hashes match the package manifest. Runtime Pakistan-scene smoke
testing remains mandatory before this candidate is promoted. Naturalization
review sources are `movie_live_hybrid_review.csv` and `demo_hybrid_review_v1.csv`.

## Current deployment

- workspace outputs: `analysis/full_korean_apply_2026-08-12/`
- theoretical ranking: `analysis/glyph_space_audit/current/shared_allocation_optimized_full_dialogue.json`
- deployed ROMFS: `C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/`
- previous live DAT backup: `C:/Users/hhlee/Desktop/Romforge/output/backup_before_full_korean_20260812/`

Current live SHA-256 after rollback plus codec merge:

- movie: `8be42adce95fe31445c852e63c84d0c246c637472991565dc417796d307c8bd6`
- demo: `de580f77e97f243c7b88c2ed2d11d3e730ae828bad854dfee449b325dbac9dbd`
- codec: `e72487f9b0a0dbab761b7c098c21fea9d6794774eca3fecfe661a92346bd823`

Movie/demo full Korean application is therefore not complete yet. Do not build
a release ROM from the unsafe workspace artifacts.
