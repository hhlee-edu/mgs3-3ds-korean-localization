# Natural translation structure expansion — 2026-08-12

The earlier automatic hybrid-naturalization plan is paused. The live Romforge
tree is restored to the pre-crash five-file set.

## 1. Codec crash diagnosis

The rejected codec was 513,600 bytes smaller than the safe codec. Of 2,326
GCXs, 1,509 changed size and 2,312 changed start offset. The first difference
starts at GCX13 (+128 bytes); known address-sensitive GCX53 is consequently
relocated. Full parsing and text verification cannot certify this layout at
runtime. Reports are `codec_crash_vs_safe_grow.json/.csv` and
`codec_crash_vs_safe_offsets.json`.

## 2. Boundary-fixed codec/common-map attempt

Re-encoding the safe codec for the optimized resident map while preserving all
GCX boundaries was attempted with both existing-font reuse and fixed-layout
dead/freed-slot reuse. It fails at GCX72/GCX13 because the affected GCXs have
no free local font slots. Therefore the optimized map cannot be paired safely
with the complete codec using the current format. The verified 191 map, safe
codec, and two verified resident HPKs remain authoritative.

## 3. Movie natural grow

The live 245,520-byte movie base was used. `--grow-records` without donor
reclaim builds all 689 natural Korean rows. Output is 362,864 bytes (+117,344).
All 108 records parse; donor and untouched subtitle bytes are unchanged; full
translation verification passes. Past runtime work accepted a larger
+225,424-byte movie grow through the opening path, but this candidate still
requires its own runtime test.

## 4. Demo resolver/scene constraint

Scenario commands address named demo resources through `sddemotable.txt` IDs,
not raw DAT byte offsets. The physical resolver remains unidentified. Natural
non-donor grow preserves 130 scenes, every donor, and every untouched subtitle,
but shifts 127 physical scene starts by at most 280,240 bytes. Previous focused
runtime probes accepted sequential scene relocation; older scene-local work
also showed that preserving starts by consuming local padding is fully safe.
The complete natural build exceeds local padding in many scenes, so full-game
runtime proof or resolver patching is still required.

The 130 physical scene-start tags are structurally identical and contain no
scene/table ID. `sddemotable.txt` has 142 names aliased onto 126 numeric IDs
(0..125), while opening table ID 0 resolves to physical scene 127. Therefore
there is no simple in-file offset table to rewrite: an external permutation
resolver maps resource IDs to physical scenes. It must be located before a
general scene-address patch can be implemented.

## 5. Natural translation candidate

`analysis/runtime_test_natural_grow_2026-08-12/` contains an atomic test set:

- natural movie: 689/689;
- natural demo: 2,228/2,228;
- unchanged safe codec: 7,305/7,305 Hangul units;
- unchanged runtime-verified resident HPKs and 191-character allocation.

This package is not installed in Romforge. It is a runtime test candidate, not
a release. Test order is Pakistan demo -> following movie -> first codec ->
repeat codec after backpack recovery. Any failure requires complete rollback.

## Romforge staging and resumed naturalization

The natural-grow runtime package was installed in Romforge after backing up the
safe set to
`C:/Users/hhlee/Desktop/Romforge/output/backup_before_natural_grow_test_20260812/`.
All five installed hashes match the package manifest. Codec and both resident
HPKs are the unchanged safe versions; only movie/demo are natural-grow test
files.

### Runtime rejection

The full natural-grow package stalled at the first Pakistan demo. It was
immediately rolled back as an atomic five-file set. The package manifest is
marked `REJECTED: first demo stalled; do not install`. This disproves using
sequential scene relocation for the complete demo build: focused +0x10 probes
do not generalize to 127 shifted scenes / +280KB cumulative displacement.
From this point, a demo candidate must preserve all 130 physical scene starts
exactly. `mgs3d_media_natural_grow_verify.py` now treats any shifted demo scene
as a hard failure rather than a runtime warning.

The paused naturalization plan resumed separately from the live test. Seventy-
six mistranslated/misaligned opening demo rows (records 0..15) were manually
rewritten in `demo_opening_natural_overrides_v2.csv`. The v2 build verifies all
2,228 rows, changes no donor or untouched subtitle, preserves 333 records and
130 scenes, and grows 303,648 bytes. It remains a workspace candidate until
the currently staged v1 runtime test result is known.
