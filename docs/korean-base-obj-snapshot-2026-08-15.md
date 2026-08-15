# Korean glyph base: table[2] → stage-object page-2 snapshot (2026-08-15)

A/B build. **The only functional change is where `korean_draw_1/2` get the Korean
page base from.** Nothing else was touched: no token mapping, no `scenerio.gcx`,
no `codec.dat`, no glyph data, no slot reassignment, and the four provably
inert patches (`width_1/2`, `pre_draw`, `layout_classify`) were left in place on
purpose so this build isolates one variable.

Background: [`global-page-render-path-audit-2026-08-15.md`](global-page-render-path-audit-2026-08-15.md),
[`evidence/2026-08-15-fontpage0-probe/`](evidence/2026-08-15-fontpage0-probe/README.md).

## 1. Why the anchor moved

`table[2]` (`*(0x00A46FE0)`) is a per-screen font slot. Measured live during a
failing codec conversation:

| context | `table[2]` | `table[2]+0x56000` |
|---|---|---|
| in-game / codec **menu** | `0x08982744` | Korean page, 4096/4096 bytes |
| codec **conversation** | `0x15A278DC` | all zeros |

That codec-conversation buffer was identified exactly: its bytes are
**codec.dat file offset `0x78A77C`, 8192/8192 byte-identical**, and it is the
glyph area of GCX 355 (`record_base + block_start + font_data_offset + 4`,
delta 0). None of the 169 `stage/*/scenerio.gcx` files contains that data. So
the codec does not *relocate* the stage page — it points `table[2]` at a
different asset entirely, and no pointer refresh or cache could have fixed it.

The stage text object keeps **its own** page-2 pointer, snapshotted at
`0x007801CC` into `[obj+0x4C]`, and the object is reachable from a
**single-writer global**: `0x008E1618`, written only at `0x007801C4`
(28 readers, 0 other writers, verified by literal-pool scan of the whole image).

Measured during the same failing conversation:

```
obj       = *(0x008E1618) = 0x158B5810
obj+0x00  (mode id)       = 0x00000002
obj+0x34  (gcx base)      = 0x15A090E0   (first word 0x4EE76D54 = the GCX seed)
obj+0x4C  (page2 snapshot)= 0x08982744   != table[2] = 0x15A278DC
obj[0x4C] + 0x56000       = 0x089D8744   == korean_page_full.bin[0:64], 64/64
```

## 2. The change

`experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s`, `KOREAN_BASE`
macro only (backup: `poc_trampolines.s.bak-pre-objsnapshot-20260815`):

```asm
    ldr  \reg, korean_desc_literal      @ 0x008E1618  (was 0x00A46FE0)
    ldr  \reg, [\reg]                   @ obj
    cmp  \reg, #0
    ldrne \reg, [\reg, #0x4C]           @ engine-owned page-2 snapshot
    ldreq \reg, korean_table2_literal   @ 0x00A46FE0  — NULL fallback
    ldreq \reg, [\reg]                  @ table[2]    (previous behaviour)
    ldr  \scratch, korean_delta_literal @ K = 0x56000, unchanged
    add  \reg, \reg, \scratch
```

`K` is untouched and still parser-relative (K gate: 169/169 stages). No cache,
no new state variable — `[obj+0x4C]` is the engine's own field, rewritten by the
engine on every entry to `0x007801B8`.

If the global is still NULL (early boot, before `0x007801B8` has ever run) the
old `table[2]` path is taken, so this build cannot be worse than the previous one.

## 3. Build and static verification — all PASS

Built with the existing `tools/mgs3d_clean_glyph_v2.py` (full V2 rebuild, needed
because the two grown functions shift every later symbol, so all six branch
words must be recomputed — `tools/mgs3d_layout_classify_fix.py` deliberately
refuses this case). Input tree was a temporary V1-state copy
(clean-tree + the 169 staged `scenerio.gcx`) so the tool's V1 guard applies as
designed; the produced `code.bin`/`exheader.bin` were then staged manually.

| check | result |
|---|---|
| assemble (devkitARM, `-march=armv6k`) | OK, trampoline **572 B** (was 536 B) |
| literal pool | `0x008E1618`, `0x00A46FE0`, `0x00056000` all present |
| six branch words | all re-encoded, all target in-cave; `draw_1` unchanged (first function, address fixed) |
| symbol moves | `draw_2` +16 B, `width_1/2`, `pre_draw`, `layout_classify` +32 B — matches 2×16 B of added code |
| changed byte ranges vs the previously staged image | **confined to the 5 moved branch words + the cave**, nothing else |
| decompressed image size | unchanged, 8,478,720 B |
| cave headroom after the trampoline | ≥512 B still zero |
| exheader | 2 bytes differ (text size `0x18`): 7,863,004 → 7,863,040 (+36 = 572−536) |
| BLZ round-trip | verified by the build tool |
| staging tree diff | 978 files, **exactly 2 changed** (`exefs/code.bin`, `exheader.bin`) |
| `mgs3d_hpk_chain_check.py` | exit 0, `OK: no padded-slot drift` (known pristine-tail NOTE) |

**Documentation discrepancy found, not a defect:** `wiki/Build-System.md` still
names `d46373e1…` as the required staged `cache.hpk`. The actual staged archive
is `e02312fc2a52a954090900f0307e67f2bdaee7236bd8d6a7e622cc9e180a28dc`, which is
the documented v0.69 history-card ETC1 rebuild
(`v0.69-pending-corrections-and-history-fix-2026-08-14.md:127`). The wiki line is
stale; the chain-check gate itself passes. Left uncorrected — out of this task's
scope.

**Also stale, in generated output:** `V2-build-manifest.json` still reports
`anchor_va: 0x00A46FE0` / `formula: *(0x00A46FE0) + 0x56000`. Those two strings
are hardcoded constants in `mgs3d_clean_glyph_v2.py` and were not updated,
because touching the build tool was out of scope. **The manifest's formula field
does not describe this build.** This document is the authority.

## 4. Hashes

| file | sha256 |
|---|---|
| staged `exefs/code.bin` (new) | `ea2bb144194cd5509ce5340715e4c003fee7bd65e49bf1c40f381efae4bee20c` |
| staged `exheader.bin` (new) | `39bd66cdc9b90aefdf2ff997c6e71ac120c668de4c97f9f79a92920082f1d87d` |
| decompressed image (new) | `6ca7b6026c23897c0bf20416cd14b3c8f85e346554a01808c5d0c8e5c61a0deb` |
| trampoline blob (572 B) | `db806d3b35f9749696c5630446c8e066d0c1b56777d26de89cf017fd0d9e29ed` |
| previous `code.bin` (archived) | `7652602c4f173fdc045565577ecdd1195f529db16d5cc4c20eee2a27af7114fb` |
| previous `exheader.bin` (archived) | `65134e0f02331342a064468b4fcf2367c90196bfd4a8de2c10e508e257f3d62f` |

Previous staged files archived (moved, not deleted) to
`C:\Users\hhlee\Desktop\Romforge\archive\pre-objsnapshot-20260815\`.
Previous `experiments/2026-08-13-clean-glyph-baseline/V2-*` artifacts archived to
that directory's `archive-pre-objsnapshot-20260815/`.

## 5. CCI — not built here

`RomForge.exe` is GUI-only (no CLI; its config file stores window geometry), and
`wiki/Build-System.md` defines RomForge as the repack pipeline. Building a CCI
through an ad-hoc `3dstool`/`makerom` path instead would create a second,
unvalidated build lineage — the exact failure that caused a corrected `cache.hpk`
to be staged in one tree while the CCI was packed from another. So the repack was
not attempted; staging is complete and gated.

After repacking, extract the CCI and confirm its internal
`exefs/code.bin` is `ea2bb144…` — a staging-only check is not sufficient.
