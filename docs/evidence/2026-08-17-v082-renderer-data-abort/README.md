# Hardware Data Abort in the v0.82 renderer guard (2026-08-17)

**Analysis only. No patch, no CCI, no staging change was made.**

Luma3DS dump `crash_dump_00000003.dmp` (sha256 `a899458f…`), captured on real
hardware during **movie playback with an R-button input**. Copied here as
`hardware-crash-00000003.dmp` because `logs/` is gitignored; full decode in
`parsed-dump.txt`, produced by the new `tools/parse_luma_crash_dump.py`.

## Verdict

The crash is **inside the v0.82 renderer trampoline**, in the multi-candidate
validating guard introduced by this build. It is the *"dereferences the candidate
before validating it"* failure mode.

```
PC   = 0x0087FA08   = korean_draw_2 + 0x80   (code cave 0x0087F8C4 .. 0x0087FB70)
insn = E5D2300C     = LDRB r3, [r2, #0x0C]   <- KOREAN_VALIDATE signature read
FAR  = 0x2A6E3FB4   = r2 + 0x0C              (unmapped)
DFSR = 0x00000005   = translation fault, section, read
CPSR = 0x28000010   = User mode, ARM state
```

## Chain of proof

1. **Format.** Luma3DS ARM11 exception dump, `totalSize` 0x564 == file length,
   23-word register block, `additionalData` process name `MGS-SE3D`, type 3 =
   data abort.
2. **The 96-byte code dump is unique to v0.82.** Searching the whole decompressed
   image of each renderer generation for the exact 96-byte window:

   | build | staged `code.bin` sha256 | window found |
   |---|---|---|
   | v0.82 validating guard | `1de8f4d9…` | **yes, at VA 0x0087F9AC** |
   | v0.81 obj-snapshot | `ea2bb144…` | no |
   | pre-obj-snapshot (`table[2]` only) | `8c542191…` | no |

3. **Two independent literal-pool resolutions confirm the address mapping**
   (they are not assumed — they are computed from the dumped instructions):
   - `0x0087F9E4: E59F2178` → `ldr r2,[pc,#0x178]` → `0x0087FB64` = documented
     literal pool base = `korean_desc_literal` (`0x008E1618`).
   - `0x0087FA00: E59F3164` → `ldr r3,[pc,#0x164]` → `0x0087FB6C` =
     `korean_delta_literal`, and the dump has **`r3 = 0x00056000`** — K itself.
4. **Register state matches the source line-for-line.**
   `KOREAN_BASE r2, r3` is exactly `korean_draw_2`'s register pair, and
   `sb`(r9)`= 0x8428` is a global-page token; the macro's index arithmetic
   (`sub r1,r9,#0x8400; sub r1,r1,#1; mov r3,r1,lsr#8; sub r1,r1,r3`) yields
   `0x27`, and the dump has **`r1 = 0x00000027`**. Token `0x8428` = **병**.
5. **All 6 patch branches are on target** in the staged image, so this is not a
   mis-aimed branch:
   `draw_1`→`0x0087F8C4`, `draw_2`→`0x0087F988`, `width_1`→`0x0087FA48`,
   `width_2`→`0x0087FA98`, `pre_draw`→`0x0087FAE8`,
   `layout_classify`→`0x0087FB10`. The crash PC lies inside `draw_2`'s extent.

## Mechanism

```asm
ldr  r2, korean_desc_literal   @ 0x008E1618
ldr  r2, [r2]                  @ obj          -- succeeded, so obj is mapped
cmp  r2, #0
beq  1f
ldr  r2, [r2, #0x4C]           @ obj[0x4C]    -- succeeded, returned 0x2A68DFA8
cmp  r2, #0                    @ only a NULL test
beq  1f
ldr  r3, korean_delta_literal  @ 0x00056000
add  r2, r2, r3                @ 0x2A6E3FA8
ldrb r3, [r2, #0x0C]           @ <== DATA ABORT: unmapped
```

Both loads before the fault succeeded, so `obj` was a readable pointer and
`obj[0x4C]` simply **was not a page pointer** — it read back `0x2A68DFA8`, which
is not in any 3DS userland region (valid samples were always `0x08xxxxxx`).
`obj[0x4C]` is the scene-setup snapshot taken at `0x007801CC`; during movie
playback the object it was snapshotted from has been reused, so the field holds
non-pointer data.

**The guard's only admission test is `!= 0`.** It has no range or mapping check,
so it cannot reject an unmapped candidate — the rejection test *is* the fault.
The `table[2]` fallback at label `1:` is therefore unreachable in exactly the
case it exists to handle.

## This did not originate in v0.82 — but v0.82 is what crashed

The dangling candidate arrived with the 2026-08-15 obj-snapshot re-anchor
(v0.81 `ea2bb144…`), whose macro is:

```asm
ldr   reg,[reg]
cmp   reg,#0
ldrne reg,[reg,#0x4C]     @ no NULL check, no validation
ldr   scratch, delta
add   reg, reg, scratch   @ then straight to retail 0x0015ECD0
```

With the same garbage `obj[0x4C]`, v0.81 hands `r2 = 0x2A6E3FA8` to retail code,
which does `add ip, r2, r1, lsl #6` at `0x0015ECD8` and — since `r7 = 0x3A` makes
`tst r7,#1` equal — branches to `0x0015EDC8`, whose **first instruction is
`ldrb r2, [ip]`**. So v0.81 aborts too, at

```
PC  = 0x0015EDC8      FAR = 0x2A6E3FA8 + 0x27*64 = 0x2A6E4968
```

Both addresses are inside the same unmapped 1 MB section, so the two builds have
practically the same exposure. **A v0.81 `code.bin` A/B will most likely still
crash, at a retail PC instead of a cave PC.** The real control is the
pre-obj-snapshot renderer `8c542191…` / exheader `2268b757…`
(`Romforge\archive\pre-objsnapshot-20260815\`), which uses `table[2] + K` only —
a pointer the engine keeps live and mapped, so it degrades to blank glyphs rather
than faulting.

## Context at fault time

- Resident stage is **`v003a`** — the ASCII `76 30 30 33 / 61` ("v003a") sits at
  `sp+0x390`, and `romfs/stage/v003a` exists in the staging tree.
- The stack holds `0x3F800000` (1.0f) and `0x3D800000` (0.0625f = 1/16) pairs and
  coordinates `0xD8`/`0x180` — a text/glyph draw path, consistent with `draw_2`.
- **`lr = 0x087D7599` is not a return address.** It is in the application heap
  with bit 0 set; this game's code lives at `0x001xxxxx–0x00Fxxxxx`. `korean_draw_2`
  never writes LR, so it is caller scratch holding data. No LR-based backtrace is
  available, and LR has no relation to the cave.
- **Register contract is not violated.** `korean_draw_2` writes only r1/r2/r3,
  which is the documented free pair (r2, r3) plus the index register the retail
  code expects. Nothing in the dump indicates caller-saved register damage.

## Not related to codec.dat

`codec.dat` duplicate propagation only changes which strings are present. The
fault is a pointer-provenance defect on the glyph-base path and would reproduce
with any Korean global-page character on screen.

## Second report — Azahar Circle Pad Pro — NO EVIDENCE ON DISK

Nothing on this machine records it:

- `%APPDATA%\Azahar\log\azahar_log.txt` ends 2026-08-16 11:46 (the GDB anchor
  session) with a GDB stub disconnect, **not** a crash. It contains zero `ir:`
  / Circle-Pad-Pro traffic.
- `%LOCALAPPDATA%\CrashDumps\azahar.exe.*.dmp` — 10 host-process dumps, newest
  **2026-08-15 22:16**, all predating the v0.82 build (2026-08-16 11:52).
- No WER report archive/queue entries for azahar or citra.

So it cannot be compared to this PC/LR family yet. Capture needed — see the
handoff notes.
