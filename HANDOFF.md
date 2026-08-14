# HANDOFF — MGS3D Korean Glyph Integration

## RESOLVED — hardware Data Abort / HPK cursor drift (2026-08-14)

**Root cause found and reproduced. No further crash investigation is needed;
what remains is a one-line packer fix and a rebuild.**

Full evidence, decoded dump, disassembly and reproduction:
[`docs/evidence/2026-08-14-hpk-cursor-drift/README.md`](docs/evidence/2026-08-14-hpk-cursor-drift/README.md).
The hardware dump is committed at
`docs/evidence/2026-08-14-hpk-cursor-drift/hardware-crash-v2.dmp`
(sha256 `2840ad54c2239aa556775a2e6743db4c762b4ea3ac11f2689f69ac68ee9d0115`).

### Root cause

`tools/mgs3d_history_texture.py:105-107` rewrites the HPK header's `packed`
field to the **new, smaller** compressed length while zero-padding the physical
slot back to the **old** length:

```python
struct.pack_into("<II", hpk, offset + 4, len(patched_darc), len(packed))
hpk[start:start + old_packed_size] = packed.ljust(old_packed_size, b"\0")
```

The retail loader is strictly sequential — `pos += 12 + packed`, no seeks, no
offset table — so keeping offsets fixed *physically* does not keep them fixed
*logically*. From the patched entry onward the loader runs `old - new` bytes
early, walks the zero padding as empty 12-byte headers, and finally reads a
header straddling the last `(old - new) mod 12` padding bytes.

For v0.65: entry 31 = key `309d745f` = the Cold War history texture, the one
entry that patch touches. `old = 3884`, `new = 3146`, padding 738,
`738 mod 12 = 6`. The loader reads entry 32's header from `0x494951` instead of
`0x494957`, decodes `packed = 0x03A00EB1` (60.8 MiB), the allocation fails and
returns NULL, the NULL is not checked, and a memcpy writes to address 0.

Reproduction is exact: re-running the patch on the clean archive yields sha256
`4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`, the
recorded v0.65 HPK hash, and reproduces the identical bad header offset and
`0x03A00EB1` value. No font size in the usable range yields zero padding, so
**every** archive this tool has produced is affected.

### Corrected crash facts

| | recorded 2026-08-13 | actual (dump) |
|---|---|---|
| PC | `0x00183A4C` | **`0x0018344C`** (`stmia r0!, {r3,r12}`, `r0=0`) |
| LR | `0x00165168` | **`0x00165160`** (return of `bl memcpy` at `0x0016515C`) |

`DFSR=0x805` (write, section translation fault), `FAR=0`, `r6=r8=0x03A00EB1`.
The 96-byte code dump matches the V2 build byte-for-byte at `0x001833F0`.

### Retired hypotheses — do not resume these

- The Korean renderer trampoline at `0x00183A04` → `0x0087FA80` is **not**
  implicated. The branch word is intact. The 2026-08-13 "primary suspect:
  invalid text pointer in the trampoline path" conclusion was built on the
  misread PC `0x00183A4C` and is withdrawn.
- `stage/v000a_0/scenerio.gcx` and its appended Korean page at `0x622DC` are
  not implicated in this crash.
- The requested dynamic Azahar/GDB cursor observation is **complete/unnecessary**
  — the hardware dump already contained the value it was meant to capture
  (`[stream+0x0C] = 0x1495D` → absolute `0x49495D`). Do not restart that session.
- The `0x001648DC` missing NULL check is **not** the fix. Recorded as a
  diagnostic-only candidate: adding it would convert the crash into silent
  asset loss and hide the real defect. Do not apply it as a solution.

### Next task

1. Fix `tools/mgs3d_history_texture.py` so the header and the physical slot
   agree. The correct pattern is already in
   `tools/mgs3d_hpk_static_korean.py:120-125`: pad the payload back to the
   original `packed_size` and **leave the header's size field untouched**.
   (zlib ignores trailing bytes, so the padded stream still decompresses.)
2. Rebuild `cache.hpk`, then gate it with
   `python tools/mgs3d_hpk_chain_check.py <cache.hpk>` — exit 0 required.
3. Only then rebuild the CCI and repeat the v0.65 hardware checks below.

No binary was modified and no CCI was built during this investigation.

## direct-v2 Translation Quality Pass (2026-08-14)

Separate track from the glyph/hardware work below — codec.dat Korean
meaning/register quality pass, ignores byte/glyph capacity entirely (that's a
later stage). **Read `translation/10_master/direct-v2-RESUME.md` first**, not
this section, for exact resume steps; this is just a pointer.

- Batches 1-10 applied, **335/22,362 rows fixed**. Batches 1-7 (217 rows)
  were independently re-verified this session (structural diff clean, 7-entry
  changelog spot-check matched byte-for-byte).
- `direct-v2-worklist.json` (defect list) was stale and has been regenerated;
  its generator script (`worklist_build.py`) was lost from an old scratchpad —
  rewrite and commit it under `tools/` or `translation/10_master/` next time,
  don't leave it in a scratchpad again.
- **D2_missing (737 rows) is split into its own pre-processing track by user
  directive** — badly contaminated with mistagged Spanish/French donor text
  (GCX 443's entire D2_missing bucket, 49 rows, turned out to be 0% English).
  Needs GCX-level EN/FR/ES/DE/IT/unknown classification before any
  `D2_missing_en` translation starts; that classification hasn't begun.
- **Batch order**: keep mining D4_mt (235 left, 108 still have a "당신/귀하"
  literal — fast, mechanical next batch) → then D6_mix (581, only
  formal-vs-informal clashes are real defects) / D3_abbrev (47) → D2 language
  cleanup + `D2_missing_en` translation last.

## Hardware crash investigation handoff (2026-08-13) — SUPERSEDED

> **Superseded 2026-08-14 by the RESOLVED section at the top of this file.**
> Its `PC=0x00183A4C` / `LR=0x00165168` are misreadings of `0x0018344C` /
> `0x00165160`, and its "primary suspect: Korean trampoline text pointer"
> assessment is withdrawn. The build-lineage hashes below are still correct and
> still useful, with one correction: the noted absence of the v0.65 HPK hash
> from `.tmp/cci-831-verify` is not a stray "build-lineage mismatch" — the
> crashed hardware CCI carried V2 `code.bin` **together with** the v0.65
> `cache.hpk` (`49447057…`), which is precisely the archive that crashes.
> `.tmp/cci-831-verify` is a different extraction that pairs V2 code with the
> clean HPK. Retained below for the hash record only.

Original 2026-08-13 text follows.

Hardware crash dump evidence:

- stage resource string: `stage/v000a_0/cache.hpk`
- stage identifier: `v000a_0`
- `PC=0x00183A4C` *(incorrect; actual `0x0018344C`)*
- `LR=0x00165168` *(incorrect; actual `0x00165160`)*

Read-only investigation result (no fix applied):

- The crashed CCI's ExeFS lineage is now exact. Extracting the `.code` member
  directly from `.tmp/cci-831-verify/exefs.bin` produced 5,264,416 bytes,
  SHA-256 `8c542191bdc62dffbd851d730dac14bc4dcf14208e54b4d15dbd409c885da7d0`.
  It is byte-identical to
  `experiments/2026-08-13-clean-glyph-baseline/V2-code.bin`; its decompressed
  SHA-256 is `105c8a1575dd3c0a65dc89ac6e81aa7e3eb9710f1c9449a00894cfb32cbc5ffa`.
  The CCI exheader is likewise the recorded V2 exheader (SHA-256
  `2268b757185418b3c2c334048fc6b8bbdfcc9508786e06c126707b12522ce1ab`,
  text size `0x77FABC`). All six patch words and the 504-byte trampoline hash
  `7298c10440b09e04aff1a705c1c85c0ce6895ee8ba7db4074ce4c2d1bfe4607d`
  match `V2-build-manifest.json` exactly.
- Do not use the current RomForge staging `code.bin` to interpret this crash.
  It is a later, different build: 5,264,412 bytes, SHA-256
  `de35b86eb0f6e8ef72b87faee567fb4f6aae5560307d57ae282cdf60b45f7308`,
  decompressed SHA-256
  `b2ab3030e0eb4fc3f912187a73ddf90fdf83def4bc696a116de3083a6eb35a8f`.
  Its six branch words target a different 456-byte trampoline layout and its
  exheader text size is `0x77FA8C`.
- The current extracted build at `.tmp/cci-831-verify` has a `v000a_0/cache.hpk`
  that is byte-identical to the clean glyph source: size `6,453,287`, SHA-256
  `145a82e9acba662afb024baadd0a25ec1eabca2c1006be26eb5891670561bbc0`.
  All 147 verified zlib entries have identical key order, offsets,
  packed/unpacked sizes, decompressed hashes, gaps, and effective alignment.
- `data.cnf` is unchanged. Within `v000a_0`, the localization build changed
  `scenerio.gcx`:
  - clean: 68,829 bytes, SHA-256
    `c126d93f3437715d5b834962e9e02d0d067061066202a679e2397310874aa420`
  - current: 467,420 bytes, SHA-256
    `badca5afc7e1a372b43cf1d60366732d229d3623f92ce1d525ddd8a097f0354d`
  - its original 68,829-byte prefix is intact;
  - the 65,280-byte Korean page begins at offset `402,140` (`0x622DC`) and
    matches `glyph/pages/global_korean_page_v2/korean_page_full.bin`;
  - recorded address formula: `49,884 + 0x56000 = 402,140`.
- `PC=0x00183A4C` is `ldrhhs r0, [r4]` in the text/layout decoder. A fault there
  indicates an invalid/unreadable text pointer in `r4`, not an HPK table read.
- The same function was directly modified by the Korean renderer patch at
  `0x00183A04`: the original `bic r1,r1,#0x6000` branches to the Korean token
  classifier trampoline at `0x0087FA80`. The code/scenerio glyph path is thus
  substantially more relevant than `cache.hpk`.
- `LR=0x00165168` lies in a buffer-copy loop following a call to the memcpy-like
  routine at `0x001833FC`; it does not identify an HPK loader. Do not treat the
  live LR as a reliable caller without stack unwind evidence.
- The documented v0.65 Cold War HPK hash
  `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`
  is not present in `.tmp/cci-831-verify`. Reproducing that patch changes only
  HPK key `309d745f`, keeps every entry offset fixed, and produces the recorded
  hash. This is a build-lineage mismatch, not evidence of current HPK damage.

Current assessment *(withdrawn 2026-08-14 — see the RESOLVED section)*:

1. ~~Primary suspect: invalid text pointer or pointer-advance/classification
   interaction in the `0x00183A04` Korean trampoline path.~~ Wrong; the
   trampoline is intact and uninvolved.
2. ~~Closely related changed resource: `stage/v000a_0/scenerio.gcx`.~~ Not
   involved in this crash.
3. ~~Low-priority suspect: current `cache.hpk`.~~ This was in fact the cause —
   but the v0.65 patched archive, not the clean one that was compared.
4. ~~Root cause is not proven because the full register set, fault address, and
   stack unwind were unavailable.~~ They were available all along, inside the
   crash dump; it had simply not been decoded.

Next read-only checks *(all closed 2026-08-14)*:

1. Closed: the full register set, `FAR=0`, `DFSR=0x805` and the 960-byte stack
   were decoded from the dump. `r4` is the stream object on the stack, not a
   text pointer.
2. Closed: the crashed CCI is the recorded V2 code and exheader.
3. Closed: the live LR is `0x00165160`, the return of the `bl memcpy` at
   `0x0016515C`; no unwind was needed.
4. Closed: neither `code.bin` nor `scenerio.gcx` is implicated, so no isolation
   build is required.

## Version 0.65 Handoff (2026-08-13)

Version 0.65 is committed and pushed as `fee6d82`, tagged `v0.65`. The local
RomForge `output/unpacked` staging tree is ready to repack for hardware testing;
the CCI itself has intentionally not been built yet.

Changes already present in RomForge staging:

- The opening Cold War history card is patched natively in
  `stage/v000a_0/cache.hpk`, not in `demo.dat`. Its resource chain is HPK key
  `309d745f` -> DARC -> `timg/cold_war_text_eng_alp_ovl.bclim` (400x64 L4).
  A Citra custom-texture probe confirmed the correct screen. The native BCLIM
  still needs hardware validation.
- The first briefing's duplicated Jack subtitle slots now read
  `버추(가상)미션?`; both remain inside their original 20-byte capacities.
  Existing normalization already corrected three `버츄어스 미션` occurrences
  to `버추어스 미션`.
- Corrupted GCX 13 was confirmed to be the 264-entry internal encyclopedia
  index, not dialogue. The entire same-offset/same-size record was restored
  byte-for-byte from the pristine Western codec (`0x1C50`, 24,864 bytes).

Prepared staging hashes:

- `codec.dat`: `86cc8e12504e517fd0916de95e3f7a46b7f00b9c6859c28338d187334493c524`
- `movie.dat`: `0f7e4c961ca4d10c19a46a7076ca0155a0531ed8b10f1a54b62d382a957945dd`
- `stage/v000a_0/cache.hpk`: `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`
  — **DEFECTIVE, do not ship.** This is the archive that causes the hardware
  Data Abort (738 bytes of zero padding in entry 31). Must be rebuilt after the
  packer fix; see the RESOLVED section at the top.

Validation completed: `codec.dat` parses as 2,326 GCX records / 601,657
resources; `movie.dat` round-trips byte-identically; the patched HPK zlib entry
decompresses and inventories correctly; all 140 unit tests pass (two Windows
temporary-directory ACL failures were rerun successfully with permission).

Next session:

1. Repack the already-prepared RomForge staging tree as the v0.65 CCI.
2. Test on hardware with no Citra custom-texture dependency.
3. Verify the opening history card first, then the first briefing wording.
4. Smoke-test the codec encyclopedia/radio-picture area affected by GCX 13.

Reproduction tools and detailed record:

- `tools/mgs3d_history_texture.py` — **contains the padded-slot defect**
- `tools/mgs3d_hpk_chain_check.py` — gate that detects it
- `tools/mgs3d_hpk_inventory.py`
- `tools/mgs3d_v065_media_fix.py`
- `tools/mgs3d_restore_gcx.py`
- [Version 0.65 checkpoint](wiki/History/version-0.65.md)

## Current Goal

Continue canonical translation integration using the append-only 929-character
global map plus the exact 191-character shared-static allocation.

## V2 HPK Cursor Drift Investigation (2026-08-14) — CLOSED

> **Closed the same day. See the RESOLVED section at the top of this file.**
> Every confirmed observation below held up, including the six-byte drift and
> the `0x00494951` header offset. The open question — where the cursor lost six
> bytes — is answered: it did not. The header read always consumes 12, and
> `0x00165110` has no under-advance path outside EOF. The six bytes are the
> residue (`738 mod 12`) of zero padding written into entry 31's slot by
> `tools/mgs3d_history_texture.py`, which the loader consumed as 61 empty
> headers. The three requested dynamic observations are moot; the dump already
> held the cursor value. Retained below for the static-analysis record.

Scope is the initial V2 crash build only. Its `code.bin` SHA-256 is
`8C542191BDC62DFFBD851D730DAC14BC4DCF14208E54B4D15DBD409C885DA7D0`
(504-byte trampoline; six V2-manifest patches). Do not substitute the current
RomForge `DE35B86E...7308` build.

Confirmed from the hardware dump:

- The physical 3DS produced the `PC=0x0018344C` Data Abort (`FAR=0`). This is
  not an Azahar crash or emulator result.
- That hardware Data Abort ultimately parsed the next HPK header from absolute offset
  `0x00494951`; the 12 bytes there decode the third word as `0x03A00EB1`.
- The valid next header starts at `0x00494957`, exactly six bytes later, and is
  `f642b10e a0030000 5a010000`.
- The resulting `0x03A00EB1` allocation request is downstream evidence of the
  misaligned header, not the current root-cause target.
- Previous entry 31 is key `309d745f`, header offset `0x00493A1F`, unpacked
  size `0x49A8`, and packed size `0x0F2C`. Its zlib stream consumes all 3884
  packed bytes; do not re-investigate zlib consumption.

Static initial-V2 loader path:

- `0x0014F018 -> 0x00165110` reads the complete 12-byte HPK header.
- `0x0014F02C` loads `packed_size`; `0x00164780` retains it in `r6`.
- `0x001648F4` requests exactly `r6` bytes from the stream.
- `0x00165198 add r1,r1,r6` / `0x0016519C str r1,[r4,#0xC]` is the local
  cursor update. The expected calculation is
  `0x00493A1F + 0x0C + 0x0F2C = 0x00494957`.
- No explicit `-6` cursor/seek arithmetic was found in the restricted static
  path. Crucially, the value written at `0x0016519C` has **not** been observed
  dynamically; `0x00494957` there remains a static inference.

Only next diagnostic requested:

Observe these three values dynamically in the initial V2 crash CCI while entry
31 is processed, and stop:

1. Immediately before entry 31: stream absolute cursor at `0x0014F018`;
   expected `0x00493A1F`.
2. Immediately after `0x0016519C`: stream absolute cursor; expected
   `0x00494957`.
3. Immediately before entry 32 header read at `0x0014F018`: expected
   `0x00494957`.

The first appearance of `0x00494951` is the only desired result. Do not expand
static analysis, patch the 60.8 MiB request, shrink the `0x80000` buffer, remove
cache resources, modify binaries, or build another CCI.

Dynamic attempt status:

- A fresh Azahar/GDB session accepted both breakpoints, but the target
  `v000a_0` entry path was not reached within the short observation window, so
  none of the three values was captured.
- Azahar was used only for an attempted dynamic observation; it did not produce
  the original Data Abort or the `0x03A00EB1` value.
- Earlier Azahar debugging attempts showed a debugger breakpoint-cache/assertion
  problem. This assertion is separate from the physical-device crash. Do not
  spend time repeatedly repairing that environment. The last attempt was
  stopped cleanly and Azahar configuration was restored byte-for-byte (backup
  SHA-256 `55593EF2FF4DEF10FE91A10B71BF5EFA10A3E9B0AC9BECF0E582B5E3085AEBD7`).

## Work Completed This Session

- USA clean baseline V0a/V0b/V0c PASS.
- K Gate PASS: all 169 stages use parser-relative `K = 0x56000`.
- Glyph layout: MSB-first, linear row-major, no vertical flip.
- V1 data-only and V2 trampoline PASS.
- Controlled renderer probe displayed `ABC 호프번 XYZ`.
- Three distinct resident bases matched Korean page data 4096/4096 bytes.
- Full 928-glyph page/map deterministic validation PASS.
- Probe-free clean integration CCI produced and manifested.
- Canonical master exposed one additional syllable (`칸`); append-only v2 now
  preserves 928/928 old assignments and adds it at `0x87A4`.
- Combined 1,120-character coverage and encoding preflight PASS.
- Size-preserving media candidates built and content-verified. Whole-record
  safe: movie 247/247, demo 732/732. Maximum row-level safe: movie 585/585,
  demo 1,871/1,871. They are partial subsets, not full master builds.

## Current Blocker

Full natural movie/demo text still exceeds fixed string capacity in many
records. A deliberate relocation/shortening decision is required; do not
silently treat the partial safe DATs as complete.

## Read These Wiki Pages

1. [Current State](wiki/Current-State.md)
2. [Glyph System](wiki/Glyph-System.md)
3. [Translation](wiki/Translation.md)
4. [Build System](wiki/Build-System.md)
5. [Decisions](wiki/Decisions.md)

## Next First Task

**Blocked until the packer fix lands.** The prepared RomForge staging tree
carries a `cache.hpk` produced by the defective
`tools/mgs3d_history_texture.py`, so repacking it as-is reproduces the hardware
Data Abort. Order of work:

1. Fix `tools/mgs3d_history_texture.py` (see the RESOLVED section at the top).
2. Rebuild `cache.hpk` and gate it with `tools/mgs3d_hpk_chain_check.py`.
3. Then repack the staging tree and perform the four v0.65 hardware checks
   listed above.

Do not rebuild the old `demo.dat` history-subtitle probe; it targeted the first
spoken demo line and was the wrong resource.

## Cautions

- Do not overwrite `translation/10_master/` with encoded or shortened data.
- Do not include the controlled `ABC 호프번 XYZ` movie probe in clean builds.
- Do not resume exhaustive GDB traversal, save manipulation, cheats or
  equipment preparation.
- Do not generalize the three-stage runtime sample to all 169 stages.

## Key Artifacts

- `docs/evidence/2026-08-14-hpk-cursor-drift/` (tracked: hardware dump + full
  crash analysis; note `experiments/` is gitignored, so irreplaceable primary
  evidence belongs here instead)
- `experiments/2026-08-13-clean-glyph-baseline/clean-build-manifest.json`
- `experiments/2026-08-13-clean-glyph-baseline/runtime-verification.txt`
- `experiments/2026-08-13-clean-glyph-baseline/full-page-rebuild-audit/full-928-validation.json`
- `experiments/global_korean_page_build_2026-08-12/korean_token_map_full.csv`
- `translation/40_build_input/global_page_v2/`
- `glyph/validation/global_page_v2/` (15 labelled review sheets)
- `experiments/2026-08-13-clean-glyph-baseline/media-candidate-manifest.json`
