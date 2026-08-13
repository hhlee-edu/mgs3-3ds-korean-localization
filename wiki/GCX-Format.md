# GCX Format (`codec.dat`)

`codec.dat` = **2,326 GCX records**, lossless round-trip confirmed. Each GCX is
a self-contained resource with its own procedure table and (optionally) a local
custom-glyph font.

## Structure

- Each GCX record has a **procedure table** of offset words. Most are
  self-relative; some (see GCX53 below) reference other locations inside the
  same record and must be relocated together if the record moves.
- Custom glyphs are **64 bytes each** (16×16, 2bpp) — a measured, original-format
  property, not a project convention.
- GCX containers have **no self-size field anywhere** — confirmed by a full u32
  scan of 4 files. Size is implied by position in the parse, not stored.

## Growth mechanism (donor reclaim)

The core mechanism this project's translation pipeline runs on: a new **unique**
Korean glyph appearing in a GCX record costs **64 bytes**, charged against that
record's own `donor_savings` (space freed by deleting that record's FR/ES donor-
language text). If `free_slots` exist, that many are free. Most GCX have
`free_slots=0`, so **unique glyph diversity per GCX**, not sentence length, is
the real capacity bottleneck.

Pipeline:
```
codec-3ds-INTEGRATED-review.csv (master, korean column)
  → mgs3d_codec_ps2none_translation_build.py   (CSV → translation JSON)
  → mgs3d_codec_size_neutral_select.py --reclaim-non-english --reclaim-language-blocks
  → mgs3d_codec_donor_audit.py                (safety gate, mandatory)
  → mgs3d_gcx_font_tool.py build-korean --preserve-file-size --reuse-freed-font
  → mgs3d_codec_offset_diff.py                (structural re-verification)
```

## Dead-glyph-slot reuse (2026-08-09)

A live scan found **1,545 dead glyph slots across 147 GCX** — leftovers from
earlier FR/ES donor reclaims that blanked the text but not the glyph bitmap.
`mgs3d_gcx_dead_slot_inventory.py` / `mgs3d_gcx_dead_slot_audit.py` and
`build-korean --reuse-existing-dead-font` implement and verify reuse. Measured
result: `--reuse-freed-font` already finds these dead slots as a side effect for
GCX inside a translation batch, so the new flag doesn't save extra bytes there —
its real value is inventory/audit visibility into codec-wide dead capacity
outside any specific batch. **Not yet applied to the production build.**

⚠️ **Correction on record:** GCX 1412 was previously believed to hold 986
Japanese glyphs. That was measured on the wrong file (the Japanese-SKU
`codec.dat`, 37,141,696 B, mistaken for the English original). The genuine
English original has **zero** custom-glyph slots in GCX 1412. See
`wiki/History/codec-dead-glyph-slot-reuse-2026-08-09.md` for the full
wrong-file trap and the corrected hashes.

## GCX53 — pinned record, solved

GCX53 looked immovable but isn't. Root cause: three procedure-table offsets past
the inner `0x1000` boundary (`+0x64/+0x70/+0x7C`, **low 24 bits** of each word)
reference the record's own container start. Descriptor `0x0200457B` selects that
fixed container start and must never move with a relocation. Fix: when a GCX
moves by `delta`, patch those three low-24 targets by `delta`, preserving the
upper flag byte. Generalized as
`relocate_gcx_internal_offsets(record, old_offset, new_offset)` — audited across
all 2,326 GCX / 216,705 procedure words with zero out-of-range targets.

EN/JP structural comparison (2026-08-09) supports this: GCX53's absolute offset
differs completely between the EN and JP SKUs, and JP boots fine — so
"GCX position can't change" is not an engine-wide constraint, it's specific to
whatever references GCX53's old position, most likely inside `code.bin`.

## Distributed grow (2026-08-10, current safe path for growth)

Growing multiple separated GCX (tested: 13, 100, 500, 1000, 1501, 1990, 2200) at
once, combined with the low-24 relocation above, works — verified in Azahar
across first codec, portrait/dialogue/voice, exit/return, re-call, and
subsequent event codecs. This does **not** mean arbitrary GCX at arbitrary sizes
are safe (see [Current State](Current-State.md#unverified)) — only the tested
range is confirmed.

## Tools

| Tool | Role |
|---|---|
| `mgs3d_codec_tool.py` | round-trip inspect/rebuild |
| `mgs3d_gcx_font_tool.py` | production Korean build, `safe-fixed` default mode |
| `mgs3d_codec_size_neutral_select.py` | donor-reclaim capacity selection |
| `mgs3d_codec_donor_audit.py` | mandatory safety gate |
| `mgs3d_gcx_dead_slot_inventory.py` / `_audit.py` | dead-slot visibility |
| `mgs3d_codec_precise_relocate.py` / `mgs3d_codec_grow_verify.py` | GCX53-class relocation + full-table verification |
| `mgs3d_gcx_workbench.py` | batch shortening review workbench (see [Matching](Matching.md)) |

## Safety rule

Use `safe-fixed` codec mode by default. A resized GCX may reparse correctly but
crash in game because later records move. Diagnostic/relocation modes are
research-only.
