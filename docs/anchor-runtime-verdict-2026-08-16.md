# Glyph-base anchor — runtime verdict (2026-08-16)

15 live samples taken through the attached GDB daemon while playing the v0.81 CCI
(`MGS SNAKE EATER 3D_Repack___.cci`). Raw log:
`docs/evidence/anchor-run2-2026-08-16.log`; table:
`docs/evidence/anchor-samples-2026-08-16.txt`; parser: `tools/mgs3d_anchor_parse.py`.

Each sample interrupts the guest, resolves all three candidate bases at the same
instant, dumps 16 bytes at `base+0x0C` for each, and resumes. `OK` means those
bytes equal the resident page's own (`0f ff ff f0 00 00 00 00 00 6f f9 00 02 90 06 80`).

## The measurement

| # | obj | t2 | par | new | old | par |
|---:|---|---|---|---|---|---|
| 3 | 158b5810 | 08982744 | 08982740 | OK | OK | OK |
| 4-9 | 158b5810 | 15a11b54 | 15a11b50 | **OK** | **ZEROS** | **ZEROS** |
| 10 | 158b5810 | 08982744 | 08982740 | OK | OK | OK |
| 11 | 158b5810 | 08982744 | 08982740 | **WRONG** | **WRONG** | **WRONG** |
| 12-15 | 158b5810 | 08a93374 | 08a93370 | **WRONG** | **OK** | **OK** |

Totals: `new` 8 OK / 5 WRONG · `old` 6 OK / 6 ZEROS / 1 WRONG · `par` identical to `old`.

## What it settles

**1. `par + 4 == t2` in every single sample.** The GCX parser descriptor
`*(0x00A472BC+0xC)` is not an independent pointer — it moves in lockstep with
`table[2]`. The static analysis inferred independence from the fact that the codec's
`set_font_page(2,…)` does not write it; that inference was wrong, and samples 4-9
show it zeroing exactly where `table[2]` does. **The proposed parser anchor would
not have fixed the codec case at all.** Recorded so it is not proposed again.

**2. Both failure modes are now observed directly, and they are disjoint.**

- Samples 4-9 (`t2` in the linear-heap range `0x15A…` — the codec-conversation
  state): `table[2]`/parser resolve to **zeros**, `obj[0x4C]` is correct. This is
  the v0.69 blank-glyph bug, and it is why v0.80's snapshot anchor fixed codec.
- Samples 12-15: the live buffer moved to `0x08a93374` and `obj[0x4C]` stayed
  pinned at `0x089d8744`, which by then held unrelated non-zero data. **This is the
  stale-snapshot failure, confirmed** — and non-zero wrong data is precisely the
  "garbled, not blank" symptom reported for `억`/`추`/`션`.

So the §2 mechanism in the superseded document was right: `table[2]` is live but
stealable, `obj[0x4C]` is stable but frozen. Neither is correct alone, and there is
no third pointer to switch to.

**3. Sample 11 has all three wrong at once** — a transition frame where the old
buffer was already reused and the new pointers had not yet been published. No
single-candidate scheme survives it.

## The structure this forces

A **multi-candidate validating guard with a cached last-good pointer** — the option
the static write-up argued against on cost grounds, now the only one the data
supports:

```
for candidate in (obj[0x4C], table[2]):          # both, in either order
    base = candidate + K
    if base != 0 and signature_ok(base):         # compare a word against the known page
        cached = base
        return base
return cached                                    # covers the sample-11 transition
```

Coverage against the measurement: samples 3, 10 (both valid) → either; 4-9 → the
`obj[0x4C]` candidate; 12-15 → the `table[2]` candidate; 11 → the cache. **All 15
samples resolve.** No per-character logic anywhere, so it covers all 931 glyphs in
codec, demo and movie alike.

Implementation notes for the trampoline:

- Needs one private word in the code cave for `cached`, and one scratch register
  beyond the current two — `KOREAN_BASE` currently takes `reg, scratch`.
- The signature compare should use a word at `base+0x0C` (`0xf0ffff0f` little-endian),
  **not** `base+0`: the page's first 12 bytes are zeros and cannot distinguish a
  good pointer from a zeroed one. That is exactly why the sampler dumps at `+0x0C`.
- The macro grows, so every later symbol moves and all six branch words must be
  recomputed — the full `mgs3d_clean_glyph_v2.py` rebuild path, not the
  single-function patcher.
- Cost is a hot-path load+compare per glyph; check the cached pointer first so the
  common case is one compare.

## Status

Measured, not implemented. No `code.bin` was rebuilt and nothing was staged.
