# Renderer range guard — Data Abort fix, staged (2026-08-17)

Fixes the hardware Data Abort root-caused in
[`evidence/2026-08-17-v082-renderer-data-abort/`](evidence/2026-08-17-v082-renderer-data-abort/README.md).
**Staged, no CCI built** — RomForge is GUI-only, that repack is yours.

## The defect being fixed

v0.82's validating guard admitted a candidate pointer on `!= 0` alone and then
*read* it to check the page signature. A stale snapshot holding non-pointer
garbage therefore faulted inside the guard, so the guard could never reject the
one case it existed to handle:

```
obj[0x4C] = 0x2A68DFA8   -> passes "!= 0"
+ K       = 0x2A6E3FA8
LDRB [base+0x0C] @ 0x0087FA08   -> translation fault, FAR 0x2A6E3FB4
```

## What changed

`experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s`
(backup `…s.bak-pre-range-guard-20260817`). Only `KOREAN_BASE` changed — the
`0x84–0x87` range checks, the `xx00` index compaction and all width/classify
logic are untouched, so all 931 global glyphs still take one common path.

Every pointer is now range-tested with **arithmetic only, no load**, and is
dereferenced solely after it lands in a window where valid values have actually
been observed. NULL folds into each test for free (`0 - LO` wraps above the
span), so no separate `cmp #0` is needed.

```asm
    ldr    reg, korean_desc_literal
    ldr    reg, [reg]                    @ obj; literal target is .data
    sub    scratch, reg, #0x08000000     @ obj sanity  -- no load
    cmp    scratch, #0x14000000
    bhs    1f
    ldr    reg, [reg, #0x4C]             @ safe: obj proved in-window
    ldr    scratch, korean_delta_literal
    add    reg, reg, scratch
    sub    scratch, reg, #0x08000000     @ base sanity -- no load
    cmp    scratch, #0x04000000
    bhs    1f
    KOREAN_VALIDATE reg, scratch         @ safe: base proved in-window
    beq    3f
1:  ldr    reg, korean_table2_literal    @ candidate 2, now validated the same way
    ldr    reg, [reg]
    ldr    scratch, korean_delta_literal
    add    reg, reg, scratch
    sub    scratch, reg, #0x08000000
    cmp    scratch, #0x04000000
    bhs    2f
    KOREAN_VALIDATE reg, scratch
    beq    3f
2:  ldr    reg, korean_blank_literal     @ neither proved itself -> blank
    mov    r1, #0
3:
```

### Where the windows come from

From the 15 runtime samples in `evidence/anchor-samples-2026-08-16.txt`:

| value | observed |
|---|---|
| `obj` | `0x158B5810` (linear heap) |
| `obj[0x4C]` | `0x08982744`, `0x08A93374` |
| `table[2]` | `0x08954BB4`, `0x08A9FC9C`, `0x08982744`, `0x08A93374`, `0x15A11B54` |
| **page bases measured correct** | `0x089D8744`, `0x08AE9374` — application heap only |

- **Object window `[0x08000000, 0x1C000000)`** — the object itself is
  linear-heap allocated, so the window has to reach that far. The crash value
  `0x2A68DFA8` is outside it.
- **Page window `[0x08000000, 0x0C000000)`** — every base ever measured
  *correct* is in the application heap. The one linear-heap base ever seen
  (`0x15A67B54`, codec samples 4–9) was measured as ZEROS, i.e. already known
  invalid, so excluding it loses nothing and removes a dereference.

### Removed and added

- **Unvalidated `table[2]` fallback: gone.** It is now range-checked and
  signature-checked like candidate 1.
- **No cache**, as instructed — samples 10 and 11 share the address
  `0x089D8744`, valid then invalid, so a cached address hands back a stale one.
- **New blank path.** `korean_blank_glyph` is 128 zero bytes assembled into the
  cave, so it lives in mapped RX `.text`. With the index forced to 0 the retail
  blitter reads a 64-byte all-zero glyph. The width trampolines still return
  `0x10`, so a rejected glyph keeps its correct advance and line layout is
  unchanged — blank, not shifted.

### Why width/classify need no guard

`korean_width_1/2`, `korean_pre_draw` and `korean_layout_classify` never
dereference a glyph-page pointer — verified by disassembling their
continuations at `0x001843A4`, `0x00184484`, `0x0015E5A8`, `0x00183A08`. They
compute widths and classifications from the engine's own tables. The
"never dereference an unvetted pointer" policy holds there trivially; changing
them would only perturb layout.

## Build

`mgs3d_clean_glyph_v2.py` full rebuild (the macro grew, so every later symbol
moves). Input tree `.tmp/v1-state-20260817/partition0` = `clean-tree` + the 169
staged `scenerio.gcx`, all 169 verified to differ from clean before building.
Tool status **PASS**, `v1_pages_preserved: true`, changed files exactly
`exefs/code.bin` + `exheader.bin`.

Trampoline 684 → **944 B**. Symbol moves:

| symbol | v0.82 | now |
|---|---|---|
| `korean_draw_1` | `0x0087F8C4` | `0x0087F8C4` (fixed, first) |
| `korean_draw_2` | `0x0087F988` | `0x0087F9C8` |
| `korean_width_1` | `0x0087FA48` | `0x0087FAC8` |
| `korean_width_2` | `0x0087FA98` | `0x0087FB18` |
| `korean_pre_draw` | `0x0087FAE8` | `0x0087FB68` |
| `korean_layout_classify` | `0x0087FB10` | `0x0087FB90` |
| literal pool | `0x0087FB64` | `0x0087FBE4` |
| `korean_blank_glyph` | — | `0x0087FBF4` (128 B) |

## Static verification — all PASS

| check | result |
|---|---|
| changed byte regions vs pristine | **0 unexpected** — only the 6 patch words and the cave |
| cave content == assembled trampoline | yes, 944 B |
| padding after the trampoline | 908 B, all zero |
| six branch words | **6/6** land exactly on their symbol, all in-cave |
| literals | `0x008E1618`, `0x00A46FE0`, `0x00056000` correct; blank literal == `korean_blank_glyph`, inside the cave |
| blank glyph zone | 128 B all zero, ends exactly at the new `.text` end |
| exheader | only offsets `0x18`/`0x19`: `.text` 7,862,468 → **7,863,412** (+944, exactly the trampoline) |
| `.text` page limit | `0x0087FC74` ≤ `0x00880000`, **908 B headroom left** |
| fixed-glyph path (`0x81-0x83`) | unchanged — no retail instruction moved |
| staged `code.bin` round-trip | decompresses to the verified image |
| HPK pre-pack gate | exit 0, `OK: no padded-slot drift` |
| `scenerio.gcx` untouched | 169/169 |
| Korean page resident | 169/169 |
| guard signature `0F FF FF F0` at page+0x0C | **169/169** — the signature test can succeed in every stage |

### Guard-before-load proof

Both `KOREAN_BASE` instances were decoded instruction by instruction from the
built binary and matched against the required pattern
(`ldr → sub/cmp/bhs → ldr[+0x4C] → add K → sub/cmp/bhs → ldrb`):

- `korean_draw_1` at `0x0087F920` (reg `r0`, scratch `ip`) — **PASS**
- `korean_draw_2` at `0x0087FA24` (reg `r2`, scratch `r3`) — **PASS**

### Replay of the recorded samples

| sample | new guard picks | dereferences |
|---|---|---|
| 1 (`obj = 0`) | blank | candidate-2 signature only |
| 3, 4, 10 | candidate 1 | obj[0x4C], then its signature |
| 11 (both wrong, same address) | **blank** (was: garbled) | signatures only |
| 12 (snapshot stale) | candidate 2 | signatures only |
| **2026-08-17 crash value** | falls to candidate 2 | **signature read at `0x2A6E3FB4` is skipped** |

The skipped address is byte-for-byte the `FAR` in the hardware dump.

## Staged

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\`

| file | size | sha256 |
|---|---:|---|
| `exefs/code.bin` | 5,264,540 | `b9514ec5da8897db9443925ea0d24379ea86a9dd9f089e5fd5718ece3a820c7d` |
| `exheader.bin` | 2,048 | `2bca5dcbae0167221ac09007003be57bbc8ce2e83fa41f6d86f90f9a37c754d7` |

Previous pair archived to `C:\Users\hhlee\Desktop\Romforge\archive\pre-range-guard-20260817\`
(`code.bin` `1de8f4d9…`, `exheader.bin` `5ea5ddd5…`). Only these two files
changed in the staging tree; `codec.dat` (v0.88 `6bdec076…`), `movie.dat`,
`demo.dat`, `scenerio.gcx` and `cache.hpk` are untouched.

## Test order — Citra is the verification gate

Per the 2026-08-17 instruction this build is reproduced, fixed and regression
tested **on Citra/Azahar**. Hardware installation is *not* required to sign this
off; a real-3DS run is reserved for genuine hardware-side defects and final
release validation.

1. **codec** — the five global-page characters from the v0.69 blank-glyph report,
   in `gcx 28`. Exercises candidate 1 while `table[2]` is stolen.
2. **demo/movie opening** — the three global-page characters reported corrupted
   in demo record 5 (offsets `11537428` / `11537816`). Exercises the
   stale-snapshot case, where candidate 1 must be rejected and candidate 2 used.
3. **movie + repeated R input** — the crash repro. Stage `v003a` is the one the
   dump was taken in. Expected result: **no Data Abort**; if neither candidate
   can be vetted, the affected characters go blank while the rest of the line
   renders and keeps its spacing.
4. Mixed lines — the fixed-range (`0x81-0x83`) characters in
   those same sentences must still render, and boot→title must be clean.

**A blank glyph is now an expected, safe outcome, not a failure.** The failure
condition for this build is a Data Abort or a layout shift.

**Do not touch the Circle Pad / 확장 슬라이드 패드 option during these runs.** It
freezes Citra for an unrelated reason — the emulator cannot create library applet
`0x408 Extrapad`, so the game spins forever waiting for it. See
[`citra-extrapad-applet-freeze-2026-08-17.md`](citra-extrapad-applet-freeze-2026-08-17.md).
That freeze is not a regression of this build and no `code.bin` change can fix it.

Optional faster iteration: Citra can overlay `exefs/code.bin` from
`%APPDATA%\Citra\load\mods\0004000000081E00\`, which avoids a RomForge repack per
attempt. Caveat, unverified: the mods path cannot supply `exheader.bin`, so the
`.text` size bump is not applied there. Citra maps `.text` by `num_max_pages`
(1920 pages → `0x00100000–0x00880000`), which does cover the cave, so it should
behave the same — but the CCI remains the authoritative artifact, and any
surprising result should be re-checked from a repack before being believed.

## Residual risk, stated honestly

A range check is not a mapping oracle. An address inside
`[0x08000000, 0x0C000000)` that happens to be in an unallocated part of the
application heap would still fault. This build removes the entire observed
failure class (wild non-heap garbage) and every unvalidated dereference, but a
guarantee would need `svcQueryMemory`, which is far too expensive per glyph.
If a Data Abort ever recurs, the dump's `FAR` will say immediately whether it
landed inside or outside the window, and the window can be tightened from that.
