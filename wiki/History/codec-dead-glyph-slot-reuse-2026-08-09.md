# codec.dat dead-glyph-slot reuse (2026-08-09)

Implements and verifies: before growing a GCX's font region (appending new
glyphs, which changes that GCX's byte size), first sweep for custom-glyph
slots that already exist in that GCX's own font table but that zero
currently-live text references, and reuse those in place instead.
`overwrite_font_slots()` (pre-existing) is the safe primitive — a pure
byte-for-byte in-place replace with zero size/offset change. This doc covers
what was built, what was measured, and one important negative result found
during verification.

Not in scope, not touched: `tools/mgs3d_hpk_static_korean.py`'s 191-slot HPK
static-font system (fully separate container/token pages — see
`docs/session-handoff-2026-08-09.md` for the same-day 64B/191-slot forensic
verification this work builds on: 64 bytes = 16x16 2bpp, a real measured
original-format property; 191 slots = a real renderer-confirmed hard limit
for the *HPK* static font, unrelated to codec.dat's per-GCX system).

## Ground-truth file, corrected

Two wrong-file traps were hit and corrected during this work:

1. The repo's own `partition0/romfs/codec.dat` (gitignored, 37MB — wrong
   size entirely) is stale, per the known trap in
   `feedback_mgs3d_build_division_of_labor.md`. **The correct current
   production file is
   `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\codec.dat`**
   (SHA-256 `19ff34d1380e1afd3d19dfbd0c9c3df091fbfb5743e09189b5dc943a85bf6267`,
   the documented 2026-08-08 rebuild).
2. `C:\Users\hhlee\Desktop\Romforge\output\backup_original_dat\codec.dat`
   (37,141,696 bytes) was earlier (previous session) mistaken for the
   pristine **English** original and used to claim GCX 1412 held 986
   legible Japanese-kanji custom glyphs. That file is actually the
   **Japanese-SKU** codec.dat (confirmed: wrong size entirely — the real
   English SKU is 67,204,976 bytes). The genuinely pristine English
   original is
   `C:\Users\hhlee\Desktop\Romforge\output\unpacked_en_original_smoke_backup\partition0\romfs\codec.dat`
   (SHA-256 `dd6ea4b80f194951bcbb0f584abb6b5f96d043e8c3ab78c4ec0c4236982374ea`,
   67,204,976 bytes, dated 2026-08-02). **In that file, GCX 1412 has ZERO
   custom-glyph slots.** The 19 slots GCX 1412 shows in the live build today
   are entirely new Hangul additions from this project's own past work, not
   Japanese-donor leftovers. See `tools/mgs3d_gcx_japanese_donor_audit.py`'s
   output against all three files for the side-by-side proof. **Do not cite
   "GCX 1412 = 986-glyph Japanese donor pool" again — it was a wrong-file
   artifact.**

## What was built

- **`glyph_slot_owners()` / `dead_font_slots()`**
  (`tools/mgs3d_gcx_font_tool.py`, moved from
  `mgs3d_codec_size_neutral_select.py` and fixed in the move): the
  canonical, per-resource, boundary-respecting scan of which of a GCX's own
  `0x8C`-page glyph slots are referenced by currently-live text.
  **Real bug fixed in the move**: the original `glyph_slot_owners` had no
  case for `0x1F` (the Western accent-character escape, `0x1F <suffix>`,
  confirmed real via `decode_mgs_preview()` in `mgs3d_codec_tool.py`) — it
  fell into the generic single-byte-advance branch, which could misalign
  the cursor and hide a real token reference whenever the escape's argument
  byte was `>= 0x80`. Fixed by consuming `0x1F <suffix>` as its own 2-byte
  unit before the general `>= 0x80` token check. Verified against the live
  codec.dat: **zero behavioral difference from the old scanner today**
  (1,545/1,545 dead slots identical either way) — the bug wasn't biting yet,
  but was a live risk for any future translation preserving an original
  `<1F><nn>` byte pair adjacent to a new Hangul character.
  `dead_font_slots(record, set())` = every slot with zero live references
  right now, independent of any translation batch.

- **`tools/mgs3d_gcx_dead_slot_inventory.py`** (new): scans every GCX in a
  codec.dat and reports `total_slots, referenced_slots, dead_slots,
  reusable_bytes, new_korean_needed, remaining_shortage` as both CSV and
  JSON (`mgs3d-codec-dead-glyph-inventory-v1`). `--translation` is optional
  (populates the needed/shortage columns) and accepted as a runtime
  argument since this project has no single stable "canonical latest
  translation.json" — `analysis/` is entirely gitignored and regenerated
  per session.

- **`tools/mgs3d_gcx_dead_slot_audit.py`** (new): independent safety check,
  following `mgs3d_codec_donor_audit.py`'s methodology — re-derives dead
  slots via the *other* existing scanner (`freed_font_slots`, a cruder
  cross-resource raw-substring join that can only under-report dead slots)
  and requires the inventory's claimed-dead set to be a superset. Also
  states the structural facts backing "cross-GCX independence" and
  "bitmap-only sufficiency, no metrics table" as machine-readable summary
  fields, not just prose.

- **`tools/mgs3d_gcx_japanese_donor_audit.py`** (new): general-purpose
  donor-language-block detector for a single GCX (same shape as the
  existing French/Spanish `language_block_donors()`, scored on token
  composition instead of a word list since Japanese has none). Used to
  investigate and correct the GCX 1412 claim above; kept as a reusable
  tool, not proven to find a large donor block anywhere in the real English
  codec.dat (see Results).

- **`--reuse-existing-dead-font`** (`build-korean` in
  `mgs3d_gcx_font_tool.py`): new opt-in flag, requires
  `--reuse-freed-font`. Priority order for slot selection: (1) slots
  already dead before this run (`dead_font_slots(record, set())`), (2)
  slots freed newly by this run's own resource replacements, (3) append
  (last resort, unchanged mechanism). A hardening assertion
  (`selected_slots[:reused_count] == available_slots[:reused_count]`)
  guards against the class of token/bitmap-placement mismatch already
  latent in the pre-existing `--reuse-existing-font` diagnostic mode (not
  fixed here — out of scope, no current caller hits it — just not
  inherited by the new mode).

- **`--dry-run`** (`build-korean`): validates and reports without writing
  any files. Both modes print, and the `.hangul.json` sidecar's new
  `reuse_summary` block records, `reused_existing_dead`,
  `reused_newly_freed`, `newly_appended`, `final_gcx_size_delta` (per GCX
  and aggregate).

## Important negative result, found during verification — read before citing "byte savings"

`freed_font_slots(record, replaced_resource_ids)` (the pre-existing
`--reuse-freed-font` mechanism) is monotonic in `replaced_resource_ids`:
excluding more resources from the "still referenced" scan can only find
*more* dead slots, never fewer. Since `∅ ⊆ replaced_resource_ids` always,
**`freed_font_slots(record, replaced_resource_ids) ⊇ freed_font_slots(record, ∅)`
for any non-empty replacement set** — meaning the OLD `--reuse-freed-font`
mode *already* discovers every pre-existing dead slot as an (undocumented,
non-obvious) side effect, for any GCX that has at least one unit in the
current translation.json.

Verified empirically, not just proven on paper: building the same
translation against GCX 767/779/1412 with `--reuse-freed-font` alone versus
adding `--reuse-existing-dead-font` produced **byte-identical results**
(28/28 dead-slot reuse, 0 appended, either way) — only the
`reused_existing_dead` vs `reused_newly_freed` attribution in the report
changed, not the total.

**What this means:** the real bottleneck was never "the build algorithm
misses pre-existing dead slots" — that case was already covered. The actual
gap, exactly as diagnosed before implementation, is that **a GCX with dead
slots but zero units in the current translation.json is invisible to
`build-korean` entirely** (skipped before `font_region` is ever called),
which is a discovery/prioritization problem, not a build-time algorithm bug.
Stage 1 (inventory) and Stage 3 (audit) solve exactly that — they are the
tools that answer "how much dead capacity exists across all 2,326 GCX right
now, independent of any specific translation batch" — which is genuinely
new capability. `--reuse-existing-dead-font` itself delivers: (a) an
explicit, tested, machine-checked guarantee of a property that was
previously true only by an easy-to-miss set-theory accident, (b) the
disaggregated reuse-source reporting the spec asked for, and (c)
forward-compatibility if `freed_font_slots`'s scope is ever narrowed later.
It does not reduce append bytes for any GCX already present in a
translation batch, because there was nothing left to reduce there.

## Results (measured against the live production codec.dat)

Whole-file inventory (`analysis/ps2_korean/full_build/dead_slot_reuse/inventory_full.json`):
**14,370 total custom-glyph slots, 1,545 dead, across 147 of 652 GCX with a
font table** (98,880 reusable bytes) — matches the number cited going into
this work exactly, now backed by a checked-in tool rather than an ad-hoc
scan. Top GCX by dead-slot count: 767 (115 total/84 dead), 779 (115/73),
1740 (51/27), 1729 (51/26), 243 (586/19). GCX 1412 has 19 total/13 dead (see
correction above — small, and self-inflicted by this project's own earlier
work, not a Japanese donor block).

Independent audit
(`analysis/ps2_korean/full_build/dead_slot_reuse/audit_full.json`): **all
1,545 dead slots confirmed by both scanners, 0 disagreements, 0 overlap
failures.**

GCX 1412 Japanese-donor-block check (`tools/mgs3d_gcx_japanese_donor_audit.py`):
0 slots in the true English pristine original; in the live build, 0 slots
attributable to any detected Japanese-dominant resource block (there isn't
one). Run against the actual Japanese-SKU file purely for contrast: even
there, only 4/986 slots are owned *exclusively* by the detected block
(the word/token-composition heuristic used is intentionally conservative
and not tuned further, since that file is out of scope for this English
project regardless).

## Verification (representative GCX 767, 779, 1412)

All against the live production `codec.dat` above. Test translation: 2
short lines in GCX 767 (9 unique Hangul), 2 in GCX 779 (16 unique), 1 in
GCX 1412 (3 unique) — sized to fit within each GCX's measured dead-slot
budget. Built with
`build-korean --preserve-file-size --reuse-freed-font --reuse-existing-dead-font`.

1. **`mgs3d_codec_offset_diff.py`** (whole file, all 2,326 GCX):
   `overall_pass: true` — file size unchanged (67,204,976 bytes both sides),
   record count unchanged, only GCX 767/779/1412 differ at all, zero
   offset/size mismatches anywhere.
2. **`mgs3d_verify_build.py`** (`codec_mode: "fixed"` manifest): `OK codec
   structure 2326 records / 601657 resources`, `OK codec fixed layout
   2326/2326 records` — `source_offset, len(raw), string_resources_offset,
   font_data_offset, proc_offset` identical for every record. (The tool's
   final whole-partition `audit_unpacked.py` step then fails against the
   synthetic single-file test partition used here, as expected — that check
   requires a complete RomForge unpacked tree and is unrelated to codec.dat;
   the codec-specific checks above are what this task verifies and they
   pass cleanly.)
3. **New-glyph-lands-in-a-pre-existing-dead-slot proof**: every allocated
   `(character, token)` in the `.hangul.json` sidecar for all 3 GCX resolves
   to a slot index `< old_count` that Stage 1's inventory had already
   flagged dead *before* the build (28/28 characters, 3/3 GCX).
4. **Byte-diff proof**: for each of the 3 GCX, every byte that differs
   between the before/after record falls inside the resource table (offsets
   shift when a resource's length changes), the encrypted string blob, or
   one of the specifically-reused 64-byte glyph slots — nowhere else. The
   font-section length header, the procedure/bytecode tail, and every
   *other* (non-reused) glyph slot are byte-identical.
5. **Old-vs-new dry-run comparison**: see the negative result above — on
   these 3 GCX (each already having translation units), old and new
   approaches are byte-identical (28/28 reused, 0 appended, both ways).
   Re-running the existing, already-fully-built 21,542-unit production
   translation (`rebuild_2026-08-08/selected_translation.json`) against the
   same source shows the same thing at scale: 8,070/8,070 already reused
   via the old mechanism, 0 appended either way — consistent with the
   negative result, not a new data point.

All artifacts (`inventory_full.json/csv`, `audit_full.json`, test
translation, built `.dat`/`.hangul.json`, offset-diff/verify-build output)
are under `analysis/ps2_korean/full_build/dead_slot_reuse/` and the session
scratch directory; nothing was written to the live RomForge staging file —
all builds in this task ran against a scratch copy.

## Tests

`tests/test_gcx_font_safety.py`: `GlyphSlotOwnershipTests` (accent-escape
handling, null-terminator stop, out-of-range token ignored, dead-slot
detection on a real hand-built synthetic GCX) and `DeadSlotReuseBuildTests`
(full bytes-in/bytes-out `build-korean --reuse-existing-dead-font` run:
output size unchanged, `font_data_offset`/`proc_offset` unchanged, the
specific pre-existing dead slot's bitmap changes and nothing else does).
`tests/test_codec_size_neutral_select.py`: one test confirming
`glyph_slot_owners` still works correctly (including the `0x1F` fix) from
its new home. 118/118 tests pass (110 pre-existing + 8 new), including a
new synthetic-GCX byte fixture (`build_synthetic_gcx()`) that didn't exist
in the repo before this work.

## Not done / explicitly out of scope

- Full production codec.dat rebuild with the new flag — this task builds
  and verifies the tooling against representative GCX only, per the
  original instruction not to auto-apply without proof first.
- Fixing the pre-existing `--reuse-existing-font` (diagnostic-only) mode's
  latent token/bitmap-placement mismatch bug — unrelated diagnostic path,
  no current caller hits it.
- Resolving the 194-vs-192-slot discrepancy noted in the prior session's
  64B/191-slot forensic doc — unrelated to codec.dat, HPK-only.
