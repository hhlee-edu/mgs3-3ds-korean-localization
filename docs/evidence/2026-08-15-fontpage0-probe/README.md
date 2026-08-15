# font page `table[0]` probe — Option 3 feasibility (2026-08-15)

Scope: decide whether the `0xFF00`-byte font page at `*(0x00A46FD8)` (`table[0]`,
measured `0x08688578`) is actually carrying glyph data, i.e. whether the Korean
page — which is exactly `0xFF00` bytes — could take it over.

Nothing in this folder modifies game data, `code.bin`, or any build. Analysis and
measurement only.

Background and the fix options this feeds: [`../../global-page-render-path-audit-2026-08-15.md`](../../global-page-render-path-audit-2026-08-15.md) §7.1.

## 1. Static result — pristine dialogue never uses page 0

`tools/mgs3d_glyph_page_analyze.py --dump-pages` over the **clean-tree** retail
Western data (`experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/`),
reference image `code_en_decompressed_verified.bin`:

| page | tokens | movie | demo | codec |
|---|---|---|---|---|
| **0** | **`0x8401-0x87FF`** | **0** | **0** | **0** |
| 1 | `0x8801-0x8BFF` | 0 | 0 | 0 |
| 2 | `0x8C01-0x8FFF` | 0 | 0 | **68** |
| 3 | `0x9001-0x93FF` | 0 | 0 | 0 |
| 4 | `0x9401-0x97FF` | 0 | 0 | 0 |
| 5 | `0x9801-0x9BFF` | 0 | 0 | 0 |
| 6 | `0x9C01-0x9FFF` | 0 | 0 | 0 |

Counts are after the renderer's own `& ~0x6000` flag normalization, so the legacy
`0xA4xx-0xA7xx` aliases are included in the page-0 row.

Full table: [`pristine-page-token-use.csv`](pristine-page-token-use.csv).

- **The retail Western dialogue data never references page 0.** That is the range
  the Korean patch reuses, and it is unused by the original text.
- Page 2 *is* used by retail codec content (68 tokens) — consistent with the
  audit's finding that `table[2]` is a live, reassigned shared slot.
- **Limit of this evidence:** these three DATs hold dialogue/subtitles only. UI and
  menu text lives elsewhere (`ui/*.la2`, HPK archives) and was not scanned, and a
  font page can be populated by its asset regardless of whether any text uses it.
  Whether the page's *memory* is blank is a runtime question — §2.

## 2. Runtime probe — `tools/mgs3d_fontpage0_probe.py`

Read-only. Talks only to the `citra_gdb_mi_controller.py` control port (24700),
never to the gdbstub port (24689) — a bare connect there consumes the stub's one
and only session.

What it captures, per sample:

1. `table[0..6]` from `0x00A46FD8` (runtime values; it never assumes `0x08688578`,
   and flags a mismatch), plus the contiguity checks
   `table[5] == table[0]+0xFF00` and `table[6] == table[0]+0x1FE00`.
2. The full `0xFF00` page at `table[0]`, chunked. It probes a 1024-byte
   `-data-read-memory-bytes` once and falls back to 64-byte chunks if the stub
   refuses (the documented reliable size).
3. A zero/non-zero + set-bit census of all **1020** 64-byte slots, with contiguous
   runs reported as `index → token` in `0x84xx-0x87xx`.
4. `table[5]` / `table[6]` as controls, so "page 0 is empty" can be contrasted
   against populated sibling pages rather than trusted alone.
5. 16×16 2bpp ASCII renders of the non-zero slots and of the tokens named in the
   audit (`0x8401 호`, `0x8422 임`, `0x865B 팀`, …), to tell real glyph data from
   incidental non-zero bytes.
6. `--registry`: BFS over the runtime resource registry at `0x00A55480`
   (node layout `[+0]`/`[+4]` children, `[+8]` id, `[+0xC]` buffer) for id
   `0x6E383C45`, then checks `buffer + [buffer+4] + 0x3080 == table[0]`.
   **Buffer pointer only — no filename / backing-asset tracing.**

Offline self-check performed before any attach: token↔index round-trip 1020/1020,
census of the staged Korean page yields 929 live slots in 1 contiguous run, and
the renderer reproduces `임` correctly.

### Running it

Requires Azahar launched with `--gdbport=24689` and the controller daemon
attached (see the recipe in the GDB memory note; `graphics_api=1` / OpenGL avoids
the Vulkan assertion that ends long sessions).

```powershell
python tools\mgs3d_fontpage0_probe.py --dump --label title --log logs\gdb-fontpage0-2026-08-15.log
python tools\mgs3d_fontpage0_probe.py --dump --label title-reg --registry --no-control-pages --log logs\gdb-fontpage0-2026-08-15.log
python tools\mgs3d_fontpage0_probe.py --dump --label codec --log logs\gdb-fontpage0-2026-08-15.log
```

`table[0] = 0x00000000` means the font archive has not loaded yet — wait for the
title screen and re-run; the probe interrupts and resumes cleanly, so re-running
is safe. Do **not** reset the game from Azahar's UI and do not attach a second
gdb: either kills the stub for that process.

Outputs land here as `fontpage0-<label>.{json,txt}` plus the raw
`fontpage0-<label>-table{0,5,6}.bin`.

## 3. Runtime result (2026-08-15) — the page is NOT free

Two independent Azahar launches, both sampled at the title screen
(`fontpage0-title-*`, `fontpage0-title2-*`).

```
table[0]=0x08688578  table[1]=0x087A973C  table[2]=0x08954BB4  table[3]=0x00000000
table[4]=0x08964AB4  table[5]=0x08698478  table[6]=0x086A8378
```

- `table[5] == table[0]+0xFF00` and `table[6] == table[0]+0x1FE00` — the three
  consecutive font pages predicted by `0x00643584`-`0x006435A4`, confirmed live.
- `table[0]` reproduced the 2026-08-15 value exactly.
- **1005 of 1020 slots are non-zero**; 946 distinct 64-byte slot values; 11
  contiguous non-zero runs spanning `0x8401-0x87FF` almost end to end.
- **The two captures are byte-identical, 65280/65280, across separate processes.**
  Heap garbage or live per-frame state could not do that: this is deterministic
  content loaded from an asset.
- The 1024-byte bulk reads were validated against 64-byte reads in the second
  run (`bulk read verified`), so the dump is not a stub artefact.

### Is it glyph data?

It does not render as readable characters under the renderer's proven format
(16×16 2bpp linear row-major MSB-first) nor under 1/2/4bpp × row-major /
column-major / y-flipped / 8×8-Morton / 8×8-block × 8×8, 8×16, 12×16, 16×12,
16×16, 24×24 — all searched.

But its *texture* matches glyph data. Scoring horizontal transitions per 16-pixel
row under the renderer's format (coherent bitmaps score low, noise scores high):

| region | transitions/row |
|---|---|
| staged Korean page (ground truth glyphs) | 3.47 |
| `table[0]-0x3080` region (glyphs readable by eye) | 3.35 |
| **`table[0]` page, slots 0-199** | **3.26** |
| **`table[0]` page, slots 400-599** | **3.87** |
| `table[0]` page, slots 800-999 | 9.37 |

Byte-alphabet profile agrees: the first ~0xC000 of the page is 60-72% "2bpp
glyph alphabet" bytes at entropy ≈3 (the Korean page is 88% / 3.08), and the
last ~0x3000 jumps to entropy ≈7.

Independently, the buffer region *immediately before* `table[0]`
(`table[0]-0x3000 … table[0]`, 82-91% glyphy) decodes cleanly into **legible
Hangul syllables** under the exact same format — proof that the surrounding
buffer really is a glyph store and that the decode routine used here is correct.

### Verdict

**`table[0]`'s font page is occupied.** Roughly the first 600-790 of its 1020
slots carry deterministic, glyph-textured asset content; only the tail looks
like non-glyph data. Taking the page over wholesale would overwrite it.

Option 3 as originally framed — "relocate the Korean glyphs into `table[0]`'s
page because it may be free" — is **not supported**: the page is not free. It is
not yet proven that the content is ever *drawn* (§1 shows retail dialogue never
emits a page-0 token), but the burden is now on proving that region dead, and a
929-glyph overwrite of live font-buffer content is not a cheap experiment.

Still open, deliberately not chased further: the exact cell encoding of that
page, and the `--registry` resolution of `0x6E383C45` (the session ended before
it ran; it does not change the verdict).

### Reading the verdict

- 1020/1020 slots zero → the page carries nothing; taking it over loses no glyph.
- Some slots non-zero → the report names their token ranges and renders them, so
  the loss is identified character by character.
- `table[5]`/`table[6]` populated while `table[0]` is empty is the strongest
  positive signal: the read path and font buffer are real, page 0 specifically is
  not.

Caveat to carry forward: a single sample is one screen. The font buffer is loaded
once at boot (`0x00643554`) and `table[0]` did not move across the three
2026-08-15 samples, so a post-title sample should be representative — but take a
second `--label` from a different screen before treating it as settled.
