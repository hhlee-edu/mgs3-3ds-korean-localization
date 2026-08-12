# Shared glyph patch preparation — 2026-08-12

## Completed preparation

- `rebuild_record_fixed_reclaim()` now accepts the verified resident
  `static_map`. Shared `81/82/83` glyphs are encoded first and are not rendered
  or charged as record-local page-3 glyphs.
- `movie_tool.py capacity` accepts the same `--static-allocation`, so its report
  and the fixed-reclaim builder use identical glyph ownership assumptions.
- `mgs3d_review_translation.py` deterministically extracts the 1,187 currently
  empty rows owned by active v10 matches. It preserves existing Korean and
  overrides, and resolves the two duplicate active-left IDs with the same
  last-relation-wins rule as the review UI.
- `mgs3d_shared_glyph_prepare.py` combines the current codec, movie, and demo
  corpora while preserving every verified baseline character-to-token mapping.
  It never assigns runtime-cleared token `8301`.

The prepared allocation is
`analysis/glyph_space_audit/current/shared_allocation_candidate_191.json`.
It contains the exact runtime-verified 191-character map. The full read-only
audit is under `analysis/glyph_space_audit/prepared_191_current/`.

## Current verified audit

- scopes: 2,767
- overflow scopes: 405
- live dead local slots: 1,545
- live reusable bytes: 98,880
- both resident hashes match their proof reports
- both resident character maps match the prepared candidate

No HPK, DAT, GCX, ROM, or review JSON was patched during this preparation.
`mgs3d_review_v10.json` still has zero translation overrides.

## Deferred translation integration

Translation text for the 1,187 active matched rows is intentionally deferred.
After a reviewed translation CSV exists, apply it with
`mgs3d_review_translation.py apply`, feed its audit CSV back to
`mgs3d_shared_glyph_prepare.py --review-csv`, and rerun the glyph-space audit.
Natural translations remain authoritative; capacity overflow is reported and
must not trigger automatic shortening.
