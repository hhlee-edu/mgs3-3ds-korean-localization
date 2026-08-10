# codec.dat EN/JP SKU structural comparison (2026-08-09)

Read-only, GCX-index-by-GCX-index structural comparison between the English
and Japanese SKU codec.dat files, to test whether the Japanese release's
much larger custom-glyph tables give any evidence about the English build's
GCX53 absolute-position sensitivity
([[project-mgs3d-codec-growth-experiment]]). Neither input file was
modified. Same parser (`mgs3d_codec_tool.parse_codec`,
`mgs3d_gcx_font_tool.font_region`) used for both.

## Inputs, identity confirmed before analysis

| SKU | Path | Size | SHA-256 |
| --- | --- | ---: | --- |
| EN pristine | `...\unpacked_en_original_smoke_backup\partition0\romfs\codec.dat` | 67,204,976 | `dd6ea4b80f194951bcbb0f584abb6b5f96d043e8c3ab78c4ec0c4236982374ea` |
| JP | `...\unpacked_metagear_jpn\partition0\romfs\codec.dat` | 37,141,696 | `0c63a109631285920592bfddc3f01dbc3a929bdb41484f91eedcb6b8e8490296` |

**JP file selection, explicit reasoning (per the instruction not to repeat
the earlier GCX1412 wrong-file mistake):** `unpacked_metagear_jpn` was
chosen over `backup_original_dat\codec.dat` (932c0a13dd..., also
37,141,696 bytes) because `unpacked_metagear_jpn` is the file explicitly
and repeatedly named "the Japanese unpack" in this project's own
contemporary documentation (`docs/session-handoff-2026-08-02-english-pivot.md`
line 12: "The Japanese unpack remains only as a backup/reference at
...unpacked_metagear_jpn"; `docs/ps2-korean-port-2026-08-02.md` line 114
uses it directly as `--reference-codec` in a working, tested pipeline).
`backup_original_dat` differs from it in 27% of raw bytes (10,124,163 /
37,141,696) despite the identical file size — but a direct check found
**zero** GCX with a different font-slot count, record size, or source
offset between the two candidates (all 2,326 GCX match exactly on every
structural field this analysis uses). The 27% raw-byte difference is
therefore confined to string/procedure content, not structure — the choice
of JP candidate does not affect any number in this report.

Both files parse cleanly with the unmodified `parse_codec()`; both report
**2,326 GCX records** (same count, not assumed — checked).

## 1. Whole-file summary

| | EN | JP |
| --- | ---: | ---: |
| File size | 67,204,976 | 37,141,696 |
| GCX record count | 2,326 | 2,326 |
| Resource total count | 601,657 | 198,227 |
| Font-bearing GCX count | 8 | 2,237 |
| Total custom glyph slots | 53 | 155,374 |
| Total custom glyph bytes | 3,392 | 9,943,936 |

EN's pristine original barely uses the per-GCX custom-glyph mechanism at
all (8 GCX, 53 slots total) — consistent with Western text mostly needing
only ASCII plus the small built-in accent table. JP uses it in 96% of all
GCX (2,237/2,326), for a combined 9.5MB of glyph bitmap data.

## 2-3. Full GCX-by-GCX comparison, top-50 rankings

Full comparison: `analysis/ps2_korean/full_build/en_jp_compare/compare.json`
(and `.csv`, header exactly per spec:
`gcx,en_offset,jp_offset,en_record_size,jp_record_size,record_size_delta,en_resource_count,jp_resource_count,en_font_slots,jp_font_slots,font_slot_delta,en_font_bytes,jp_font_bytes,font_bytes_delta,en_string_blob_size,jp_string_blob_size,string_blob_delta,en_font_data_offset,jp_font_data_offset,en_proc_offset,jp_proc_offset,en_script_resource_count,jp_script_resource_count,en_display_resource_count,jp_display_resource_count`).

Top-50 CSVs: `top50_A_jp_font_slots.csv`, `top50_B_font_slot_delta.csv`,
`top50_C_record_size_delta_decomposed.csv`, `D_jp_only_font_full_list.csv`
(2,229 rows — see below), all in the same directory.

**A (top `jp_font_slots`) and B (top `jp_font_slots - en_font_slots`) are
the same 50 GCX**, because every GCX in the top of either ranking has
`en_font_slots = 0`. Top 5: GCX 1412 (986 JP slots), 780 (984), 767/768
(983 each), 769/770/771/772 (983 each).

**GCX where both EN and JP already have glyphs (8 total: 4, 5, 6, 8, 9,
11, 12, 14):** slot count and record size are **identical** in every one
(delta = 0). These are almost certainly non-language, engine-shared GCX,
not evidence of JP having a bigger table for a shared resource — the
entire "JP has more glyphs" signal comes from GCX where EN has zero
custom glyphs at all.

**C (top `record_size_delta`, JP larger)** — full population, not just the
top 50: max is **+2,832 bytes at GCX 1715**; only 137/2,326 GCX exceed
+1KB; **zero** GCX exceed +5KB or +10KB. Median delta across the whole
file is +160 bytes; the mean is a heavily negative -12,925 bytes, because
a small number of GCX are dramatically *smaller* in JP (EN's per-GCX
multi-language, string blob dwarfs JP's single-language one for
dialogue-heavy resources — the extreme case is GCX 1412 itself, at
-332,384 bytes).

Decomposition for the top 15 of ranking C (exact, not estimated — every
term is a real measured field, not an approximation):

| gcx | size_delta | glyph_bytes_delta | string_blob_delta | remainder | glyph_share |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1715 | 2,832 | 5,696 | -2,132 | -732 | 201% |
| 656 | 2,736 | 6,720 | -3,000 | -984 | 246% |
| 1368 | 2,736 | 8,832 | -4,564 | -1,532 | 323% |
| 531 | 2,672 | 5,760 | -2,364 | -724 | 216% |
| 25 | 2,528 | 5,952 | -2,704 | -720 | 235% |

(full top 50 in `top50_C_record_size_delta_decomposed.csv`.) **In every
one of the top 15, the glyph-byte increase alone exceeds 100% of the total
size increase** — the string/resource blob actually *shrinks* in JP
relative to EN (JP doesn't carry FR/DE/IT/ES variants), partially
offsetting the new glyph cost. The net result is still growth because the
glyph cost is larger than the string savings, but this is a real
re-balancing between two large opposing terms, not simply "the same
content plus glyphs bolted on." The `remainder` column (header/resource
table/procedure/alignment) is small and consistently negative (a few
hundred bytes), not a source of the size change.

**D (JP has a font table, EN does not): 2,229 GCX** — the large majority of
JP's 2,237 font-bearing GCX. Full list in `D_jp_only_font_full_list.csv`.

**E (EN has a font table, JP does not): 0 GCX.** Every GCX with EN custom
glyphs also has JP custom glyphs (consistent with EN's 8 font-bearing GCX
all being a subset of JP's 2,237, per the "8 identical GCX" finding above).

## 4. GCX 51-55 detailed comparison

| | GCX51 | GCX52 | GCX53 | GCX54 | GCX55 |
| --- | ---: | ---: | ---: | ---: | ---: |
| en_offset | 265,760 | 274,112 | 284,592 | 297,856 | 347,872 |
| jp_offset | 275,616 | 283,952 | 295,808 | 309,776 | 350,384 |
| offset match? | **no** | **no** | **no** | **no** | **no** |
| en_record_size | 8,352 | 10,480 | 13,264 | 50,016 | 10,368 |
| jp_record_size | 8,336 | 11,856 | 13,968 | 40,608 | 11,760 |
| record_size_delta | -16 | +1,376 | +704 | **-9,408** | +1,392 |
| en_font_slots | 0 | 0 | 0 | 0 | 0 |
| jp_font_slots | 44 | 91 | 111 | 352 | 84 |
| en_string_blob | 4,496 | 6,380 | 8,172 | 34,052 | 6,388 |
| jp_string_blob | 2,668 | 3,152 | 3,636 | 11,100 | 3,372 |
| en_font_data_offset | 4,812 | 6,708 | 8,656 | 36,172 | 6,656 |
| jp_font_data_offset | 2,820 | 3,304 | 3,836 | 11,800 | 3,508 |
| en_proc_offset | 4,816 | 6,712 | 8,660 | 36,176 | 6,660 |
| jp_proc_offset | 5,640 | 9,132 | 10,944 | 34,332 | 8,888 |
| en_resources | 74 | 77 | 116 | 525 | 62 |
| jp_resources | 33 | 33 | 45 | 170 | 29 |

**No absolute offset matches between EN and JP for any of GCX51-55** — not
even approximately; the gap itself isn't constant (+9,856 / +9,840 /
+11,216 / +11,920 / +2,512), because EN and JP diverge in total content
from the very start of the file (every earlier GCX already differs in
size between the two SKUs). This is expected given how different the two
files are overall, and is recorded here as the literal, checked fact per
the instruction, not interpreted further than that.

GCX53 itself: JP is 704 bytes *larger* than EN (13,968 vs 13,264), funded
by +111 glyph slots (7,104 bytes) partially offset by a -4,536-byte
smaller string blob (45 JP resources vs 116 EN resources — EN carries the
FR/DE/IT/ES variants JP doesn't need). GCX54 is the largest swing here: JP
is 9,408 bytes *smaller* despite +352 glyph slots (22,528 bytes), because
its string blob shrinks by 22,952 bytes (525 EN resources vs 170 JP —
consistent with EN multiplexing roughly 3x as many resources, matching a
multi-language layout).

## 5. Glyph/string delta decomposition

Covered inline in §2-3 (exact, not estimated, for every row — every term
is a directly measured field from the parsed records, so no approximation
was needed anywhere in this analysis).

## 6. Hypothesis verdicts

**H1 — JP has genuinely more GCX with more custom glyphs than EN: CONFIRMED.**
2,229 GCX have JP glyphs where EN has zero. Not a marginal effect — 96% of
all GCX in JP carry a custom-glyph table vs 0.3% in EN. Caveat: the 8 GCX
where EN already has glyphs show *zero* difference from JP (not "JP has
more" in those cases) — the entire H1 signal comes from GCX where EN's
custom-glyph mechanism simply isn't used at all, not from JP outgrowing an
EN table that already exists.

**H2 — JP has GCX several-KB-to-tens-of-KB *bigger than the corresponding
EN GCX*, existing normally: PARTIALLY CONFIRMED, with the "tens of KB"
part specifically REFUTED.** The measured maximum `record_size_delta`
across all 2,326 GCX is **+2,832 bytes** (GCX 1715) — real and several-KB,
but zero GCX reach +5KB, let alone the "tens of KB" (수십 KB) named in the
hypothesis, when measured as JP-minus-EN for the same index. Read literally
("bigger than EN"), only the several-KB half of H2 holds.
Separately, and worth stating precisely rather than folding into the same
verdict: JP does contain individual GCX with tens-of-KB *absolute* custom
glyph payloads functioning normally in a real shipped game (GCX 1412: 986
slots = 63,104 bytes of glyph data, GCX 780: 984 slots = 62,976 bytes) —
these just aren't *bigger than EN's version of the same GCX*, because EN's
version of that specific GCX carries an even larger multi-language dialogue
payload (EN GCX1412 = 588,768 bytes vs JP's 256,384).

**H3 — the game engine itself does not fundamentally prohibit GCX size
growth: CONFIRMED.** Independent of the EN-comparison framing above, JP is
a real, complete, shipped, working game whose entire codec.dat has a
totally different per-GCX size/offset layout from EN throughout (not just
at GCX51-55) — the engine handles arbitrarily different GCX
sizes/positions correctly in normal play, because it does so in an entire
shipped title. This is the strongest and least qualified verdict in this
report.

**H4 — the EN GCX53 shift problem is plausibly a SKU-specific
loader/index/absolute-reference issue rather than a generic
record-size-growth problem: CONFIRMED (strong circumstantial evidence, not
a located mechanism).** GCX53 sits at completely different absolute file
offsets in EN (284,592) and JP (295,808) — an 11,216-byte gap, far larger
than anything a single record-size change could produce — and JP's game
works normally with GCX53 at that different, JP-specific position. This is
consistent with each SKU shipping its own compiled `code.bin` with
offsets/references tuned to *that SKU's own* codec.dat layout at
mastering time, rather than a single, universal, hardcoded
"GCX53 must be at file offset 284,592" constant baked into the engine
itself. This analysis did not touch `code.bin` for either SKU and does not
locate the actual reference mechanism — it only shows the position
*varies safely and correctly by SKU*, which is what a per-SKU-compiled
reference would look like and is hard to explain under a universal,
engine-level fixed-offset model.

**H5 — the JP structure lets us prove a safe, direct patch method to give
EN GCX bigger font tables: REFUTED at the current evidence bar (explicitly
held to a high standard per instruction).** This analysis is a pure
codec.dat structural comparison; it says nothing about *where* or *how*
EN's `code.bin` (or any other file) references GCX53's position, which is
exactly the missing piece needed to actually patch it safely — a prior
session's targeted Capstone disassembly of EN's `code.bin` already
searched for this and came back inconclusive (`gcx_ref_scan_report.json`,
2026-08-08). Knowing that JP tolerates a different layout does not by
itself supply a way to make *EN's* code.bin tolerate one too. This would
require either finding the actual reference (dynamic debugging, now that
a working GDB recipe exists per `feedback_citra_azahar_gdb_debugging.md`)
or a fundamentally different strategy.

## 7. Suggested next experiments (written after the verdicts above, not before)

1. **Dynamic debugging is now the highest-leverage next step for H4/H5**,
   given the working GDB recipe from 2026-08-09: set a breakpoint/watchpoint
   on the memory range GCX53 occupies at runtime and single-step to find
   the actual PC/instruction that computes or reads its address, rather
   than continuing static disassembly (already tried, inconclusive).
2. If a JP 3DS dump/emulator setup is available, repeating the *same* kind
   of GCX53-position-sensitivity experiment
   ([[project-mgs3d-codec-growth-experiment]]) against the **JP** build
   (shift JP's GCX53 by a controlled delta and see if JP breaks the same
   way) would be a strong, direct test of the "per-SKU-compiled reference"
   theory — if JP *also* breaks when its own GCX53 is shifted from its own
   original position, that's much stronger confirmation than the
   circumstantial evidence here. Out of scope for this task (no JP
   emulator/save-state setup was prepared here).
3. Do not use JP's codec.dat, resources, or glyph bitmaps directly in the
   EN production build — this task only establishes that different
   layouts *can* work in principle, not a transfer mechanism, and JP
   resource content is semantically unrelated to EN's (different
   language, different resource counts/order per GCX throughout).
