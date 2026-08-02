# MGS3 3DS Koreanization handoff

## Current state

- Base tooling and fixed-layout Korean port are in commit `7451f1b`.
- PS2 TOM bitmap copier is in commit `fcdda0e` (`tools/mgs3_ps2_tom_bitmap_port.py`).
- Stable fixed-layout codec/HPK set is documented under `analysis/ps2_korean/`.
- A minimal movie/demo isolation set is staged at `analysis/ps2_korean/staging_media_minimal/`:
  stable codec, one movie subtitle line, and the known-safe 64-row demo subset; TOM is intentionally excluded.

## Next test

Repack a CCI from `staging_media_minimal`, run it in Citra, and verify the opening movie and demo subtitles for graphics corruption. If stable, expand movie/demo rows incrementally to identify the collision boundary.

## Known findings

- Opening historical narration is in `demo.dat` records 245–247, not `movie.dat`.
- Pakistan and oxygen/mask lines are later demo records and were omitted from the safe 64-row subset.
- TOM bitmap port currently covers the mapped 141-resource tutorial blocks; remaining English TOM lines may belong to other resources/branches.

## Deliberately uncommitted artifacts

Local SQLite databases, vendored Capstone binaries, and the large source ISO remain untracked and are not part of the repository commits.
