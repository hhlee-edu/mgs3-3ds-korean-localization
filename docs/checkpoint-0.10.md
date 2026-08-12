# Checkpoint 0.10 — 2026-08-12

This checkpoint records the current MGS3D Korean-patch tooling and analysis
state. Generated game-data artifacts and copyrighted ROM/ISO/DAT/HPK files are
not committed.

## Runtime state

- Romforge is on the last known-safe codec/resident/movie/demo set after the
  rejected full natural-grow demo stalled at the first Pakistan scene.
- A new scene-fixed demo candidate applies 1,268 natural Korean rows while
  preserving file size, all 130 scene starts, and every record-internal
  subtitle offset/capacity. Static grow and content gates pass; runtime smoke
  testing is pending.
- Full natural translations remain preserved in hashed workspace checkpoints.

## Version policy

Use `0.10` for this checkpoint. If the next iteration has no major structural
change, advance to `0.11`. Reserve a larger version step for a material format,
loader, or runtime strategy change.
