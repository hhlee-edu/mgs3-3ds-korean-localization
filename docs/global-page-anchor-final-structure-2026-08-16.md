# Global-page anchor — root cause of the demo/movie regression, and the final structure (2026-08-16)

> **CORRECTED 2026-08-16 by runtime measurement — §4's proposed anchor is WRONG.**
> 15 live samples (`docs/evidence/anchor-samples-2026-08-16.txt`) show the parser
> pointer is **not** independent of `table[2]`: `par + 4 == t2` in *every* sample,
> so it zeroes out during a codec conversation exactly as `table[2]` does. The
> §2 diagnosis of *why* each anchor fails is confirmed; the §4 conclusion drawn
> from it is not. **The measured answer is the multi-candidate validating guard,
> which §4 argued against.** See
> [`anchor-runtime-verdict-2026-08-16.md`](anchor-runtime-verdict-2026-08-16.md).
> Everything below is kept as the static-analysis record.

Static analysis only, on the pristine decompressed image
`experiments/arm/code_romforge_decompressed.bin`
(sha256 `10c7d349…`, the same image the 2026-08-15 audit used, base VA `0x00100000`).
Reuses the existing dumps and GDB samples; **nothing was re-measured at runtime and
no binary was rebuilt or staged.**

## 1. The three candidate anchors, and what each really is

| anchor | expression | maintained by |
|---|---|---|
| old (v0.69) | `*(0x00A46FE0) + K` | `set_font_page(2, …)` — **7 call sites**, per screen |
| current (v0.80/v0.81) | `*(0x008E1618)`→`[obj+0x4C]` `+ K` | written **once per scene setup**, at `0x007801CC` |
| **proposed** | `*(0x00A472BC + 0xC) + 4 + K` | the **GCX parser**, on every `scenerio.gcx` load |

`K = 0x56000`, unchanged and still parser-relative (169/169 stages).

## 2. Why the current anchor fixed codec and broke the cutscenes

The whole answer is in one function — `0x007801B8`, the scene-setup routine:

```asm
0x007801B8  push {r4,r5,r6,lr}
0x007801BC  mov  r4, r0            ; the stage text object
0x007801C0  ldr  r0, [pc,#0x78]    ; = 0x008E1618
0x007801C4  str  r4, [r0]          ; global = obj          <- the only writer
0x007801C8  bl   0x0010830C        ; live page-2 pointer
0x007801CC  str  r0, [r4,#0x4C]    ; obj->page2 = SNAPSHOT <- taken once, here
...
0x007801E8  bl   0x0010830C        ; the same value again
0x007801F0  mov  r0, #2
0x007801F4  bl   0x0010A894        ; set_font_page(2, it)
```

At scene setup `[obj+0x4C]` and `table[2]` are set from the *same* source and agree.
They diverge afterwards, in opposite directions:

- **`table[2]` is live but shared.** `set_font_page` (`0x0010A894`) has seven
  callers passing index 2. A codec conversation repoints it at the codec.dat GCX's
  own glyph area — measured `0x15A278DC`, byte-identical to codec.dat offset
  `0x78A77C`. `table[2] + K` then lands on unrelated memory. Blank glyphs.
- **`[obj+0x4C]` is stable but frozen.** It is a *snapshot* stored at
  `0x007801CC` and never refreshed. It stays valid only while the buffer it
  captured is still the resident one. Once the scenerio buffer is reallocated —
  which is exactly what a cutscene transition does — the snapshot is a dangling
  pointer into memory that now holds something else. **Non-zero, wrong data:
  garbled glyphs, not blank ones.**

That difference in failure mode is the tell, and it matches the reports exactly:
v0.69 reported characters rendering **blank**; v0.80/v0.81 report `억`, `추`, `션`
rendering **깨짐 (garbled)**. Same defect class, opposite pointer pathology.

So neither anchor is correct. v0.80 traded a shared-slot bug for a stale-snapshot
bug, which is why codec started working and the opening cutscene regressed.

## 3. The engine already exposes the right pointer

`0x0010830C` — the getter both stores above go through — is four instructions:

```asm
0x0010830C  ldr r0, [pc,#8]     ; = 0x00A472BC
0x00108310  ldr r0, [r0,#0xC]
0x00108314  add r0, r0, #4
0x00108318  bx  lr
```

`0x00A472BC + 0xC` is written at `0x00108488`, inside the **GCX parser** — the
function whose loop at `0x00108420`-`0x0010845C` is the scenerio seed cipher
(`mul` by the seed constant, `+0xCF9`, `eor` per byte). It computes
`[desc+0xC] = ip + u16(ip) + 8` straight from the freshly parsed buffer, alongside
`[desc+8]`. This is the same parser formula the project already relies on to place
the page (`page2_offset`, 169/169 stages).

Three properties follow, and they are exactly the ones both current anchors lack:

1. **Live** — recomputed by the parser on every `scenerio.gcx` load, so it can
   never go stale the way a snapshot does.
2. **Unshared** — only three literal-pool references to `0x00A472BC` exist in the
   whole image (`0x10831C`, `0x1084A0`, `0x171FC4`); the codec's
   `set_font_page(2, …)` does not touch it. It cannot be stolen.
3. **Mode-independent** — it is a property of the loaded stage, not of the screen,
   so codec, demo, movie and menus all resolve identically.

## 4. Final structure — one common anchor for all 931 glyphs

Inline the getter (do **not** `bl` it — the trampolines are entered by `b`, so `lr`
still holds the patched caller's return address and must survive):

```asm
.macro KOREAN_BASE reg, scratch
    ldr   \reg, korean_parser_desc_literal   @ 0x00A472BC
    ldr   \reg, [\reg, #0xC]                 @ live parsed scenerio page-2
    cmp   \reg, #0
    ldreq \reg, korean_table2_literal        @ not loaded yet -> old behaviour
    ldreq \reg, [\reg]
    addne \reg, \reg, #4                     @ the getter's own +4
    ldr   \scratch, korean_delta_literal     @ K = 0x56000
    add   \reg, \reg, \scratch
.endm
```

Eight instructions, same as the current macro — **no size change**, so no symbol
moves and the six branch words stay as they are.

Properties, against the brief:

- **Covers all 931 global glyphs** (`0x8401-0x87FF`) uniformly. It changes only
  where the base comes from; the range checks, index compaction and width logic
  are untouched.
- **No per-character patching.** Nothing in it mentions `억`/`추`/`션` or
  `외`/`워`/`백`/`업`/`팀`; those were only ever symptoms of the base.
- **Fixed glyphs are unaffected** — they render through `table[1]`/`[sp,#0x44]`
  and never enter this macro.
- **Cannot be worse than the current build.** The null branch keeps the old
  `table[2]` path for the pre-first-load window, which is the same guarantee v0.80
  made.

### Why not a validating guard plus cache fallback

That was the audit's option 2 and it remains a correct *fallback* design, but it is
strictly worse here: it needs a private word in the code cave, re-priming on every
stage load, a signature compare on a per-glyph hot path, and it only ever
*recovers* from a bad pointer. Reading the parser's own live pointer removes the
failure instead of detecting it. If a future report shows even this pointer going
stale, the guard can be layered on top of it — the two are not exclusive.

## 5. What this does and does not settle

Settled statically, with the addresses above: why codec works and the cutscene
does not, and what the common anchor must be.

**Not settled:** that the proposed anchor resolves correctly *at runtime* in the
opening cutscene. That still needs the one GDB sample described in
[`gdb-anchor-sample-recipe-2026-08-16.md`](gdb-anchor-sample-recipe-2026-08-16.md),
which now has a third value worth reading alongside the other two:

```
*(0x00A472BC + 0xC) + 4 + 0x56000
```

If that matches `korean_page_full.bin[0:64]` in **both** the opening-cutscene and
the in-game sample while `[obj+0x4C]+K` matches only in-game, this analysis is
confirmed and the patch is the whole fix.

No `code.bin` was rebuilt and nothing was staged.
