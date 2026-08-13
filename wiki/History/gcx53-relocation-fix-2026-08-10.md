# GCX53 relocation fix (2026-08-10)

## Outcome

GCX53 can be relocated safely. The packed select-stage descriptor must remain
unchanged; three flagged offsets in GCX53's own procedure table must move by
the same signed delta as the GCX53 record.

For the validated `+0x10` case:

| GCX53 raw field | Original | Relocated |
|---:|---:|---:|
| `+0x64` | `0x2000104E` | `0x2000105E` |
| `+0x70` | `0x2000108A` | `0x2000109A` |
| `+0x7C` | `0x200010B3` | `0x200010C3` |

The high byte is a flag and is preserved. Only the low 24-bit offset is
adjusted.

## Root cause

The first codec command decodes four arguments:

```text
0x3705, 0x0200457B, 0x4, 0x73
```

`0x73` is resource 115. Although the low bits of `0x0200457B` numerically match
GCX53's original file offset (`0x457B0`), runtime dumps proved that this packed
value selects the fixed containing resource, not the movable inner GCX53
payload.

Changing it to `0x0200457C` for a `+0x10` relocation advanced the resource base
by 16 bytes. The parser-entry dump therefore became the normal header with its
first 16 bytes removed. That experiment necessarily crashed and established
that the descriptor must not move.

With the descriptor fixed, the containing resource loaded from the correct
base. Its GCX53 procedure table still contained three offsets at or beyond the
inner `0x1000` boundary. Those stale values pointed into the old layout. Adding
the record delta to those three low-24 values repaired the references.

## Evidence chain

1. Slow-memory tracing found the loader descriptor `0x0200457B` and the
   resource object pointer writer.
2. A descriptor-only `+0xC0` test crashed.
3. A boundary-neutral descriptor-only `+0x10` test also crashed, ruling out the
   0x800-aligned FS read boundary as the root cause.
4. Normal and shifted parser-entry dumps showed that changing the descriptor
   skipped the first 16 bytes of the containing header.
5. A runtime experiment kept the descriptor fixed and patched only the three
   procedure offsets. Portrait, dialogue, voice, close/re-call all worked.
6. A file-only artifact containing the same three byte changes worked without
   any runtime mutation. The first and following codec calls both succeeded.

Key artifacts:

- `analysis/gcx53_dynamic_debug/azahar_normal_parserdump_20260810.log`
- `analysis/gcx53_dynamic_debug/azahar_shift0010_parserdump_20260810.log`
- `analysis/gcx53_dynamic_debug/azahar_shift0010_innerpatch_success_20260810.log`
- `analysis/gcx53_dynamic_debug/azahar_filepatch_only_success_20260810.log`
- `analysis/gcx53_dynamic_debug/codec_gcx53_shift_0010_inner_offsets_patched.dat`

The successful file-only artifact has SHA-256
`5605848CF3778B8CD444BC0E4D3565BB1CC86CB787BD894BA3C6371981ED329C`.

## Implementation

`tools/mgs3d_codec_tool.py` now provides the general primitive
`relocate_gcx_internal_offsets(record, old_offset, new_offset)`. It:

- scans the selected GCX record's complete procedure table;
- selects low-24 targets at or above `old_offset`;
- preserves the high-byte flags;
- applies the signed `new_offset - old_offset` delta;
- supports forward and backward relocation and rejects 24-bit overflow.

This is not GCX53-specific. A full-file audit covered 2,326 GCX records and
216,705 procedure-table words; every low-24 target lies within its own stored
GCX record. The common high-byte flag families are `0x10`, `0x20`, and `0x50`
(plus a small number of `0x01/0x02/0x03` and unflagged entries). GCX53 uses the
same representation.

The record object is required context: the same internal offsets recur in many
GCXs, so two bare numbers cannot uniquely identify a record across the whole
file. Once the parser/builder has selected a record, only `old_offset` and
`new_offset` are needed to relocate every affected table entry automatically.

`relocate_gcx53_inner_offsets(record, delta)` remains as a strict wrapper. It
calls the general fixer with `0x1000 -> 0x1000 + delta` and additionally refuses
the operation unless the known GCX53 fields are exactly `0x64/0x70/0x7C`.

`tools/mgs3d_gcx_font_tool.py` computes GCX53's actual final offset after codec
reflow and applies the correction automatically when the delta is nonzero.
Fixed-layout builds have delta zero and are unchanged.

`tools/mgs3d_codec_precise_relocate.py` exposes the correction explicitly via
`patch_gcx53_inner_offsets=True` so old diagnostic artifacts remain
reproducible by default.

Tests are in `tests/test_codec_gcx53_relocation.py`. They cover generic forward
and backward moves, flag preservation, the strict GCX53 wrapper, and unexpected
layouts. Together with the existing font-safety and build-verifier suites, 45
relevant tests pass.

## movie.dat / demo.dat implications

The lesson is broader than codec parsing: a structurally valid rebuild does not
prove that external or containing-resource offsets remain valid.

Current safe movie/demo paths are not directly exposed:

- default `rebuild_record_fixed()` preserves every subtitle, record, and file
  offset;
- `--size-neutral-reclaim` rebuilds each record to its original size;
- both paths reparse the finished file and retain fixed-layout invariants.

The following paths need the same class of investigation before release use:

- `--grow-records`, which repacks a record and shifts later records;
- `--fixed-layout-reclaim`, which keeps subtitle offsets within a record but
  can grow the record and therefore move later records/scenes;
- any future scheme funded from scene-level trailing padding.

Required investigation for those modes:

1. map the outer scene/container that selects each movie/demo record;
2. capture the runtime record base before and after a minimal `+0x10` move;
3. dump the parser-entry header and find stale inner offsets;
4. verify whether offsets are flagged low-24 values, absolute file positions,
   or scene-relative positions;
5. implement relocation with strict layout assertions;
6. validate at least the modified cutscene and the following cutscene on the
   emulator and, before release, real hardware.

Until that work is complete, the fixed-size movie/demo builders remain the
release path. Reparse success alone is not authorization to use growing modes.
