# Glyph System

Two separate glyph mechanisms exist in this project. Don't conflate them.

## 1. Per-GCX custom glyphs (`codec.dat`) — production system

See [GCX Format](GCX-Format.md). Each `codec.dat` GCX record carries its own
custom-glyph font; a new unique Hangul glyph costs 64 bytes against that
record's donor-reclaimed budget. This is the mechanism the live production
build uses today.

## 2. 191-slot shared static font (HPK) — separate, unrelated

A fully separate container/token-page system (`tools/mgs3d_hpk_static_korean.py`),
confirmed as a real renderer enforced hard limit of 191 slots — unrelated to
codec.dat's per-GCX system. Do not confuse the two 64-byte-glyph mechanisms;
they're independently implemented and independently limited.

## 3. Global Korean glyph track (2026-08-12+) — parallel, newest

**Goal:** stop growing/moving codec.dat/movie.dat/demo.dat/HPK entirely.
Instead, intercept a spare renderer token range (`8401..87FF`), point it at a
new **resident glyph bitmap page**, and patch `code.bin`'s draw/width/parser
logic to recognize it. Nothing in the DAT/HPK containers is resized or moved.

### Where the font actually lives

The font resource is `stage/<name>/scenerio.gcx` — **per-stage**, one file per
of the (now known to be) **169 stages**, each loaded whole and contiguous. Not
a shared global asset. Chain: `0x007801DC` passes an already-loaded buffer
(`context+0x34`) to parser `0x00108320`, which writes section pointers into
descriptor `0x00A472BC`; `0x0010830C` returns `*(0x00A472BC+0xC)+4`; `0x0010A894`
registers `table[2]` (`table[4]` auto-derives as `table[2]+0xFF00`).

### Why the obvious extensions don't work

- **A 3rd `0xFF00` bank appended to the existing 2-bank font section**: dead —
  across all 169 stage files there are ~168 distinct page2 hashes (each stage
  packs only the glyphs it needs) and in several files `page2 + 0x1FE00` already
  runs past EOF.
- **Reusing "page 1" as spare capacity**: dead — GDB-confirmed it's always
  initialized non-NULL from boot; it's live allocation, not spare.
- **A separate new RomFS asset + loader**: tried, rejected. The candidate load
  API (`0x0061D438`) queues an **async** resource request — it is not a
  synchronous filename→buffer read, do not call it directly with a filename,
  and do not reuse the fixed scratch address `0x00A7B000` (that combination
  crashed on save-codec).

### Current design: Option B, EOF append per stage file

Append the Korean glyph page after each stage's `scenerio.gcx` EOF, computed
from the runtime buffer base plus a fixed offset `K`. Chosen over Option A
(extending the existing page table), which risked adjacent BSS corruption and
an unproven 8th table slot.

**Confirmed 2026-08-13 (see [Current State](Current-State.md)): this works.**
Load size is the RomFS file size itself; EOF-appended bytes are resident;
`K = 0x56000`; live 192/192-byte Korean-page match confirmed. This retracts an
earlier same-week conclusion ("EOF append refuted") that turned out to be a
wrong address constant (`K=0x35000`), not a real limitation — see
[Current State § Invalidated](Current-State.md#invalidated) and
`wiki/History/` for the full retraction trail.

### Patch points (code.bin), minimum confirmed set

Not a one-instruction patch — 2 draw lookups (`0x0015E600`, `0x0015EC58`) + 2
width lookups (`0x00184398`, `0x0018445C`) must branch on the Korean token
range *before* the existing `& ~0x6000` mask, plus a parser/wrapping/control-
token cluster needing its own regression coverage
(`docs/global-korean-glyph-runtime-verification.md` in
[History](History/) lists it).

### Capacity

The frozen 2026-08-12 corpus had 1,119 unique Hangul syllables: 191 shared
static + 928 global, leaving 92 slots. The reorganized canonical master adds
`칸` (U+CE78), so the current build-input set is **191 + 929 = 1,120**, leaving
91 slots. The append-only v2 map preserves every verified 928 assignment and
adds `칸` at `0x87A4`; see `glyph/pages/global_korean_page_v2/` and
`translation/40_build_input/global_page_v2/`.

### Immediate next step

Boot the existing `MGS SNAKE EATER 3D_Repack______.cci` (6 underscores,
statically confirmed as the 169-stage patched build) and check visually
whether `0x8401..0x8403` render as Hangul. **Do not rebuild anything first** —
data residency and pointer arithmetic are already confirmed; only the renderer
trampoline is untested.

### Known-good minimal POC (reproduce before touching anything else)

```powershell
cd D:\dev\3dsmetal
python tools\stage_known_good_ganada_poc.py
```
Hash-verifies and stages `code.bin`/`exheader.bin`/`movie.dat` under
`output/known_good_ganada_poc/partition0/`. Do not use
`MGS SNAKE EATER 3D_Repack___.cci` (3 underscores) — recorded as a failed
loader-POC build.

### Paused

UI-namespace instrumentation/reverse engineering — paused by explicit user
request. Don't resume without being asked.

Full chronological session-by-session narrative (font resource identification,
the 3-bank rejection, the async-loader rejection, the refutation and its
retraction): `wiki/History/`, particularly the font-resource and
global-korean-glyph dated docs.
