# Documentation index

> **SUPERSEDED 2026-08-13.** This index's job — tracking current vs. superseded
> conclusions — is now done by [`wiki/Current-State.md`](../wiki/Current-State.md)'s
> Confirmed/Invalidated tables, which also cover the newer global-Korean-glyph
> and load-size documents this index never reached. Start at
> [`wiki/Home.md`](../wiki/Home.md). Kept for history; links below updated to
> match the docs' new location in `wiki/History/`.

This index is the authority for document status. Historical files are retained
as experimental evidence; a struck-through entry means that its conclusion was
superseded, not that the underlying observation was deleted.

## Current conclusions (2026-08-12)

- [Glyph/space audit](../wiki/History/glyph-space-audit-2026-08-12.md) — current read-only
  resident/local glyph allocation and movie/demo/codec capacity analysis.
- [Glyph/space audit handoff](../wiki/History/glyph-space-audit-handoff-2026-08-12.md) — exact
  resume point, confirmed boundaries, reproduction, and next safe step.

- [Codec distributed grow stress](../wiki/History/codec-distributed-grow-stress-2026-08-10.md)
  — current runtime result for general GCX relocation.
- [GCX53 relocation root cause](../wiki/History/gcx53-relocation-fix-2026-08-10.md) — focused
  root-cause record; generalized by the distributed stress result above.
- [Movie/demo grow relocation](../wiki/History/movie-demo-grow-relocation-2026-08-10.md) —
  current runtime result for both media containers.
- [Story media playback order](../wiki/History/story-media-order-2026-08-10.md) — current
  movie/demo call-order extraction work.
- [WIKI](WIKI.md) — chronological project notebook. Prefer the newest dated
  section when two entries conflict.

## Superseded conclusions

- ~~[Session handoff 2026-08-08](../wiki/History/session-handoff-2026-08-08.md): demo growth is
  limited to one record / two grown records are inherently unsafe.~~ Superseded
  by the 2026-08-10 movie/demo relocation tests, including seven independently
  grown demo records and a `+0x70` displacement of the opening scene.
- ~~[Session handoff 2026-08-09](../wiki/History/session-handoff-2026-08-09.md): fixed-layout or
  donor reclaim is the only established safe movie/demo path.~~ Superseded as
  a general restriction by the 2026-08-10 grow validation. It remains useful as
  the record of the earlier size-neutral method.
- ~~[GCX53 relocation root cause](../wiki/History/gcx53-relocation-fix-2026-08-10.md):
  movie/demo grow remains unverified and fixed-size paths are the only safe
  recommendation.~~ Its codec diagnosis remains current; only its deferred
  movie/demo status was superseded later that day.
- ~~[Session handoff 2026-08-01](../wiki/History/session-handoff-2026-08-01.md): append-and-grow
  demo rebuilding is runtime-incompatible in general.~~ The tested historical
  artifact failed, but later controlled relocation proved that record movement
  itself is not a general failure condition.

## Historical versions

- 2026-08-01: [session handoff](../wiki/History/session-handoff-2026-08-01.md),
  [work resume](../wiki/History/work-resume-2026-08-01.md)
- 2026-08-02: [Korean port](../wiki/History/ps2-korean-port-2026-08-02.md),
  [English/Korean pivot smoke](../wiki/History/english-korean-pivot-smoke-2026-08-02.md)
- 2026-08-03: [PS2 port handoff](../wiki/History/ps2-port-handoff-2026-08-03.md),
  [Citra runtime smoke](../wiki/History/citra-runtime-smoke-2026-08-03.md)
- 2026-08-07: [session handoff](../wiki/History/session-handoff-2026-08-07.md)
- 2026-08-08: [session handoff](../wiki/History/session-handoff-2026-08-08.md)
- 2026-08-09: [session handoff](../wiki/History/session-handoff-2026-08-09.md)
- 2026-08-10: current conclusions listed above
- 2026-08-12: [glyph/space audit](../wiki/History/glyph-space-audit-2026-08-12.md),
  [handoff](../wiki/History/glyph-space-audit-handoff-2026-08-12.md)
