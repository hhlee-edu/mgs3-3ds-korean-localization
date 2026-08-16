# Global-page render path audit (2026-08-15)

Full static audit of every unpatched hook site in the retail text pipeline,
run to answer "are there more sites like `korean_layout_classify`?"

**Headline: yes there were many candidate sites, but none of them is the bug —
and the `korean_layout_classify` fix staged earlier today is a provable no-op.
The real symptom is much larger than reported: the entire 929-character global
glyph page fails, while the 191 static characters work.**

All addresses are VAs in the decompressed pristine `code.bin`
(`experiments/2026-08-13-clean-glyph-baseline/clean-tree/exefs/code.bin`,
decompressed sha256 `10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7`).

## 1. The retail text encoding, as actually implemented

Derived by disassembly, not assumed:

| step | code | meaning |
|---|---|---|
| decode | `cmp rX,#0x80` / `ldrhhs` / `rev16hs` | byte `< 0x80` → token `0x8000\|byte`; byte `>= 0x80` → big-endian 2-byte token |
| attributes | `bic rX,rY,#0x6000` | bits 13-14 are **style/attribute flags**, stripped before comparison |
| wide test | `cmp rX,#0x8100` + `movge …,#0x10` | any token `>= 0x8100` is a wide (16 px) glyph |
| glyph page | `ip = (tok-0x8400)/1024`, `base = *(0x00A46FD8 + ip*4)` | font-page pointer table at **`0x00A46FD8`** |
| glyph index | `raw = tok - 0x8401`, `idx = raw - (raw>>8)` | `xx00` holes compacted out |

Two consequences that were not previously written down:

- **`bic #0x6000` is a no-op for every assigned Korean token.** The whole
  assigned space is `0x8101-0x87A4`; bits 13 and 14 are clear throughout it.
  The mask only matters for the legacy `0xA0xx` namespace (`0xA05C → 0x805C`),
  which is dead.
- **The retail engine already supports `0x84xx-0x87xx` natively** as font page
  0. The Korean patch does not add the range — it redirects the *glyph base*
  from `table[0]` to `table[2] + 0x56000`.

## 2. Unpatched hook sites — surveyed, all cleared

### 2.1 `bic Rd, Rn, #0x6000` — 35 sites, 6 patched, 29 unpatched

Full list produced by an exact-encoding scan. Clusters: `0x0013D2F4-0x0013D524`
(10, attribute/format decoder), `0x0015E0E8-0x0015E420` (6, draw/measure),
`0x00183AC0-0x00184080` (6, layout/width), plus 7 scattered.

**All 29 are harmless**, by the no-op argument above. This is the same reason
`korean_pre_draw` was left unpatched, and it generalises to every one of them.

### 2.2 Width sites `cmp rX, #0x8100` — 3 unpatched

`0x0015E478`, `0x001842F4`, `0x00184714`. All use `>= 0x8100 → width 16`, which
every Korean token already satisfies. Harmless.

Corollary: the `korean_width_1` / `korean_width_2` trampolines are **redundant** —
the retail code they replaced already returned width 16 for `0x84xx-0x87xx`.
They are harmless, just not load-bearing.

### 2.3 Runtime token rewriter at `0x0024FB78` — checked, harmless

This site walks a loaded string buffer and rewrites tokens in place
(`subeq r1, r1, #0x400`, then `strb`/`strb` back into the buffer). It would be
catastrophic if it applied to our range. It does not: the guard is
`cmp r6, ip, asr #10` with `r6` pinned to **2** at `0x0024FB38`, so only page 2
(`0x8C00-0x8FFF`) is rewritten. Our tokens are page 0.

### 2.4 Control-code collisions — **one real defect found**

The layout engine tests decoded tokens against control constants. Intersecting
every such constant with the 1,120 assigned tokens:

| token | char | tested at |
|---|---|---|
| `0x8308` | **감** | `0x00183D68`, `0x00184544` |
| `0x8309` | **달** | `0x00183D70`, `0x0018454C`, `0x0018459C` |

`감` and `달` are consumed as control codes by the layout/line-wrap engine
(`beq 0x183d90` → the special-handling path) instead of being drawn. This is a
**genuine, live, unrelated defect**. It is not fixed by anything staged, and it
is not fixed by the `korean_layout_classify` patch either — those tokens are
`0x83xx`, outside that patch's `0x84-0x87` check.

Cheapest fix: reassign `감` and `달` to two of the free slots in the global page
(29 slots free per v0.68 notes) and rebuild. No code patch needed.

Unassigned control constants in range, harmless today but **do not allocate**:
`0x8100`, `0x81B0`, `0x825C`, `0x8301`, `0x831E`.

## 3. The `korean_layout_classify` fix is a no-op

Traced every use of the value the trampoline returns in `r0`.

The patched trampoline returns `0x8101` for `0x84xx-0x87xx`; unpatched it
returned `bic(token, 0x6000)` — which, per §1, is the token unchanged. Every
downstream consumer of that `r0` is an equality test:

| site | constant |
|---|---|
| `0x00183A18` | `0x805C` |
| `0x00183A80` | `0x8023` |
| `0x00183D68` | `0x8308` |
| `0x00183D70` | `0x8309` |
| `0x00183D7C` | `0x807D` |
| `0x00183D84` | `0x802C` |
| `0x00183D9C` | `0x807D` |

`r0` is dead after `0x00183D8C` (overwritten at `0x00183A88` / `0x00183DB4` /
`0x00183ED4` on every reachable path). Every constant is below `0x8400`, so
both `0x8101` and any token in `0x8401-0x87FF` fail all of them and take the
identical path to `0x00183ED4`.

**The patch therefore changes behaviour for exactly zero assigned characters.**
It is harmless and correct in principle (it makes the classifier consistent with
its four siblings), but it does not fix the reported bug. The staged
`code.bin` / `exheader.bin` need not be reverted, but a CCI built to test it
would test nothing.

The evidence that originally motivated it does not survive either: the
`missing_glyphs` CSV column was used as a diagnostic shortcut ("7/7 samples
matched"), but **865 of the 1,120 assigned characters carry that flag**, so a
7/7 match is what chance predicts.

## 4. What the symptom actually is

`missing_glyphs` turns out to mean, approximately, "not in the static
allocation" — i.e. **needs the global page**. Checked against the actual
reported line (codec GCX 28 / resource 29):

```
외로워 하지마 . RADIO로<0A>자네를 백업할 지원팀은 있으니까 .<0A><00>
missing_glyphs = 백업외워팀
```

| char | token | page | reported |
|---|---|---|---|
| 외 워 백 업 팀 | `0x8490 0x841D 0x8505 0x84D4 0x865B` | **global** | blank |
| 로 하 지 자 네 를 할 원 은 있 으 니 까 | `0x81xx` / `0x82xx` | static | fine |

Of the nine characters in the original report, eight are global-page and one
(`마`, `0x8138`) is static — and the stale flag is known to include a few static
characters spuriously (verified: 5,784 of 6,666 flagged rows disagree with the
current map), so `마` is most likely a reporting artifact, not an observation.

So the symptom is **not "nine specific characters"**. It is:

> **The entire 929-character global glyph page renders blank in the codec
> screen. The 191 static characters render correctly.**

This also fits the previously-recorded fact that demo/movie Korean "displays
normally" — the `ABC 호프번 XYZ` runtime probe that validated global-page
rendering was a **movie.dat** probe (`V2-display-probe-movie.dat`), and `호` is
`0x8401`, a global-page token. Global-page rendering is proven to work there.

## 5. Most probable root cause — `table[2]` is a shared, reassigned slot

The trampolines resolve the Korean glyph base as:

```
korean_page_base = *(0x00A46FE0) + 0x56000      ; = font page table[2] + K
```

Ruled out first (so the remaining suspect is narrow):

- glyph bitmaps: all reported characters have non-blank 64-byte glyphs in the
  staged page (checked directly, 100-122 set bits each);
- page residency: **all 169** staged `stage/*/scenerio.gcx` end with a
  byte-identical copy of `korean_page_full.bin`;
- token encoding, character map, token map: previously verified.

What is *not* safe is the assumption that `table[2]` always points at the
resident `scenerio.gcx` page 2. The setter is `0x0010A894`
(`table[r0] = r1`, plus `table[4] = r1 + 0xFF00` when `r0 == 2`). It has **nine
callers, seven of which pass index 2**:

| caller | source of the pointer |
|---|---|
| `0x001042AC` | `0x0010830C()` |
| `0x007801F4` | `0x0010830C()`, after `0x00108290(0x008E161C)` |
| `0x00780220` | `0x0010830C()`, after `0x0022F7DC(0x009545E4)` |
| `0x0079D9E8` | `[obj+0x4C]` after storing mode id `0xD` |
| `0x0079D9FC` | `0x0010830C()` |
| `0x007A4200` | `[obj+0x4C]` after storing mode id `0xC` |
| `0x007A4214` | `0x0010830C()` |

(`0x00623330` passes 3; `0x0024FBC8` passes 1.)

`table[2]` is therefore a **per-screen font slot that at least seven code paths
reassign**, several of them clearly mode-specific. The Korean base formula is
only valid while the last writer happened to leave it pointing at the resident
scenerio buffer. Note also that the retail draw path guards this slot
(`cmp r0,#0` / `ldreq r0,[sp,#0x44]` at `0x0015E670`) while **the trampoline has
no such check** — a stale or null `table[2]` silently yields `0x56000` +
garbage.

This mechanism predicts exactly the observed split: static characters read the
default font via `table[1]` (`[sp,#0x44]`, set at `0x0015E550`) and keep
working, while every global-page character reads `table[2] + K` and goes blank.

### 5.1 CONFIRMED at runtime (2026-08-15, Azahar + GDB)

Measured live against `MGS SNAKE EATER 3D_Repack.cci` (2026-08-15 00:15 build,
current staging) via `tools/citra_gdb_mi_controller.py`.

| slot | at boot / title | **during a codec conversation** |
|---|---|---|
| `table[0]` `0xA46FD8` | `0x08688578` | `0x08688578` (unchanged) |
| `table[1]` `0xA46FDC` | `0x087A973C` | `0x087A973C` (unchanged) |
| **`table[2]` `0xA46FE0`** | `0x08954BB4` | **`0x15A278DC`** |
| `table[3]` `0xA46FE4` | `0x00000000` | `0x00000000` |
| `table[4]` `0xA46FE8` | `0x08964AB4` | `0x15A377DC` |

Two things are confirmed by this single sample:

1. **`table[4] == table[2] + 0xFF00` in both states**, which is the signature
   the setter at `0x0010A894` writes only on `r0 == 2`. So `table[2]` really is
   maintained through `set_font_page(2, …)`, exactly as §5 predicted.
2. **`table[2]` is the only slot that moved** — and it moved to an entirely
   different memory region (`0x089…` → `0x15A…`, i.e. out of the application
   heap and into the linear-heap range).

Reading the derived Korean base during the codec screen:

```
table2 = 0x15A278DC
korean_page_base = table2 + 0x56000 = 0x15A7D8DC

0x15A7D8DC:  00000000 00000000 00000000 00000000   <- page start
0x15A7E11C:  00000000 00000000 00000000 00000000   <- 임 (0x8422, idx 33) glyph slot
```

**All zeros.** The real glyph for `임` in the staged page is

```
00000000 c0000000 c000b901 c0404707
c0800109 c0c0000c c0800109 c0404707     (38 of 64 bytes non-zero)
```

So the renderer is not failing to draw — it is faithfully drawing a 64-byte
run of zeros, because `table[2] + 0x56000` no longer lands on the resident
Korean page. That is the complete mechanical explanation of the reported
"characters render blank" symptom, observed at the moment of failure.

Corroborating natural experiment from the same session: the codec save prompt
the SAVE-confirmation UI string (quoted text removed) contains exactly one global-page character —
`임` (`0x8422`) — and every other character is static (`게 811B`, `을 8105`,
`저 8213`, `장 8136`, `하 8109`, `시 8123`, `겠 8216`, `습 8127`, `니 810C`,
`까 820D`). The user reports **only `임` is invisible**: ten static controls
visible, one global-page character blank, same line, same frame.

### 5.2 Control sample — in-game, global-page Korean rendering correctly

Second GDB session, same CCI. Breakpoints armed at connect time (before the
initial `-exec-continue`; `-break-insert` is rejected with
`^error,msg="Selected thread is running."` once the guest is running) on all
four global-only trampoline paths: `korean_draw_1` `0x0087F910`, `korean_draw_2`
`0x0087F98C`, `korean_width_1` `0x0087F9F8`, `korean_width_2` `0x0087FA48`.

The build was verified live first: memory at `0x0087F8C4` is byte-identical to
the staged `code.bin` trampoline, and the patch sites hold branches into it
(`0x0015E600` = `0xEA1C84AF`, `0x0015EC58` = `0xEA1C8338`).

Hit on `korean_width_1` (`PC 0x0087F9F8`, `LR 0x087D7FAC`):

| item | value |
|---|---|
| token | `0x8421` `'코'` |
| index | 32 |
| `table[0]` | `0x08688578` |
| `table[1]` | `0x087A973C` |
| `table[2]` | `0x08852520` |
| `table[3]` | `0x087FA5AC` (non-zero here; zero at boot and in codec) |
| `table[4]` | `0x08862420` = `table[2] + 0xFF00` ✓ |
| base | `table[2] + 0x56000` = `0x088A8520` |
| glyph address | base + 32×64 = `0x088A8D20` |
| 64 bytes there | **byte-identical to the staged page** |

The page start also matches: memory at `0x088A8520` equals `page[0:64]`
(`호`, index 0) exactly.

**So `table[2] + 0x56000` is the correct formula — it resolves to the real
resident Korean page whenever `table[2]` has not been reassigned.** The defect
is solely the shared slot, not the offset.

## 6. Can the base be derived from `table[0]` instead? — No

`table[0]` is the natural candidate: the retail engine already maps tokens
`0x8400-0x87FF` to it (`table[(tok-0x8400)/1024]`), and it is written exactly
once, by the font loader at `0x00643554`. Measured across all three samples it
never moved:

| context | `table[0]` | `table[2]` | base = `t2+0x56000` | base − `table[0]` |
|---|---|---|---|---|
| boot / title | `0x08688578` | `0x08954BB4` | `0x089AABB4` | `0x0032263C` |
| codec (broken) | `0x08688578` | `0x15A278DC` | `0x15A7D8DC` | `0x0D3F5364` |
| in-game (working) | `0x08688578` | `0x08852520` | `0x088A8520` | `0x0021FFA8` |

`table[0]` is constant; the distance to the Korean page is not. **A
`table[0] + FIXED_OFFSET` formula is impossible**, and this is structural, not
bad luck:

- `table[0] = fontbuf + [fontbuf+4] + 0x3080` — inside the **font archive**
  buffer, allocated once at boot (`0x00643554`), which is why it never changes.
- The Korean page lives inside the **`scenerio.gcx` stage buffer** at
  `scenerio_buf + page2_offset + 0x56000`. Both terms vary: `scenerio_buf` is a
  fresh heap allocation on every stage load, and `page2_offset` is
  stage-specific — measured across the 169 staged stages it ranges from
  **49,872 to 369,396** (147 distinct `scenerio.gcx` sizes, 369,364-byte
  spread).

Two independent allocations whose separation is heap-layout luck. No constant
can bridge them.

### 6.1 What the measurement does establish

- The **offset** `0x56000` is right; only the **pointer** is unreliable.
- `table[2]` is the only slot that moves; `table[0]`/`table[1]` were identical
  in every sample, and `table[4] == table[2] + 0xFF00` held in all three,
  confirming every observed change went through `set_font_page(2, …)`.
- A font page is **`0xFF00` = 65,280 bytes** — `table[0]`'s region spans
  `+0x3080 … +0x12F80` (exactly `0xFF00`), and the setter's `table[4] = X +
  0xFF00` uses the same stride. **The Korean page is exactly 65,280 bytes**,
  i.e. exactly one font page. That is the one place where a genuinely fixed
  formula could exist, and it is worth recording for the fix decision.

## 7. Conclusion on the base formula

Ranked, with the evidence each rests on:

1. **`table[0] + FIXED_OFFSET` — ruled out.** Measured impossible (§6).
2. **Keep `table[2] + 0x56000`, but stop trusting `table[2]` blindly.** The
   offset is proven correct (§5.2). The trampoline currently has no guard at
   all, while the retail path it replaced does (`cmp r0,#0` /
   `ldreq r0,[sp,#0x44]` at `0x0015E670`). A guard that *validates* rather than
   merely null-checks — verify a signature word at `table[2] + 0x56000` against
   the known page content, and fall back to a private cached copy of the last
   value that passed — would survive the slot being reassigned. Needs a private
   word in the code cave and re-priming on every stage load; the validation
   happens to be cheap because the page's content is known at build time.
3. **Relocate the glyphs into `table[0]`'s font page — structurally correct,
   larger change.** The engine already routes `0x84xx-0x87xx` there natively, a
   font page is exactly the Korean page's size, and `table[0]` never moves. If
   that page is unused in the Western build, this removes the need for the
   draw/width trampolines entirely rather than patching around them. Not
   investigated: whether that region is free, and how to patch the font asset.

Option 2 is the minimal fix; option 3 is the one that removes the class of bug.
Neither has been implemented — no `code.bin`, trampoline, CCI or glyph-slot
change was made in this session.

### 7.1 Option 3 feasibility probe (2026-08-15) — VERDICT: needs one more fact

- The font buffer holds **three consecutive `0xFF00` pages**: `table[0]` at
  `F+0x3080`, `table[5]` at `F+0x12F80`, `table[6]` at `F+0x22E80`
  (`0x00643584`-`0x006435A4`). Minimum buffer size therefore
  `0x3080 + 3*0xFF00 = 0x32D80` = 208,256 bytes.
- **`ui/font.la2` is not it.** It is a `darc` container of 14 `.bcfnt` members,
  largest 66,176 bytes — none can hold `F+0x22E80`. No other `ui/**` file
  ≥200 KB is a raw buffer either (all are `.la2` DARC UI containers).
- **The buffer is fetched by resource id `0x6E383C45`** —
  `0x00245A44 ldr r0,=0x6E383C45` → `bl 0x00147F4C` (lookup) → on non-null,
  `bl 0x00643554` (the font loader). That id is **not** an entry key in
  `stage/v000a_0/cache.hpk`, so it resolves through some other archive/table.
- **`0x00147F4C` is not a file loader.** It is a lookup in a runtime resource
  registry at `0x00A55480`: 16 buckets indexed by `(id & ~0x80000000) >> 3`
  bits [6:3], each a BST compared on `[node+8]`, returning `[node+0xC]` (the
  already-loaded buffer). So `0x6E383C45` is a **runtime id/name-hash**, not a
  path — and it is not stored as a literal 4-byte key in
  `stage/init`, `stage/title`, `stage/v000a_0` `cache.hpk` or
  `ui/resident/resident_a.la2` (all probed, 0 hits). Identifying the file needs
  the *registration* site (whoever inserts into `0x00A55480`) or the name-hash
  function — not attempted, out of the requested scope.
- **Registry internals traced (2026-08-15, still not enough).** The registry
  base `0x00A55480` has 11 code references; the node allocator/inserter is
  `0x0014E464` (free-list at `[base+4]`, 0x508-byte blocks of 16 nodes), with a
  single caller `0x00128AB4`. At `0x00128A8C`, `strd r6, r7, [r4,#8]` fixes the
  node layout: **`r6` = id, `r7` = buffer**. Both arrive as runtime values —
  the id is a **name hash, and it is not CRC32**: tested all 916 romfs files
  across 11 name forms (path/basename/stem, case variants, `rom:/`, `data/`,
  UTF-8 and UTF-16LE) against `0x6E383C45` with and without bit 31 — zero
  matches. Resolving it needs the hash function itself, or walking callers up
  from `0x00128AB4` to the archive-registration loop.
- **Caller walk exhausted (2026-08-15).** `0x00128AB4` sits in `0x00128898`,
  which is a **generic `register(id, buffer)` entry point with 5 callers**
  (`0x00102CFC`, `0x00103144`, `0x001197EC`, `0x001478F4`, `0x00164614`); those
  fan out to 3 → 16 → 9 callers across unrelated subsystems. No archive-loading
  loop and no file/member identifier appears at any level, and neither `id` nor
  `buffer` is ever a literal — both are parameters threaded down from callers.
  **The id→file binding does not exist statically**; it is produced at runtime
  by a name hash (shown not to be CRC32). Pinning the asset would need the hash
  function, or a live read of the registry — both outside the scoped work.
- **Blocking unknown:** where `0x6E383C45` is stored, and whether `table[0]`'s
  `0xFF00` page holds glyphs the Western build actually uses. Until that is
  answered, Option 3 is neither confirmed nor ruled out.
- **If it turns out replaceable, the payoff is total:** the retail page-0 index
  math (`raw = tok-0x8401; idx = raw - (raw>>8)`, `0x0015E63C`-`0x0015E678`) is
  *already identical* to the trampoline's compaction, and retail width already
  returns 16 for `>= 0x8100`. All six injected patches
  (`korean_draw_1/2`, `korean_width_1/2`, `korean_layout_classify`,
  `korean_pre_draw`) become removable and `code.bin` can return to stock.

## 6. Recommended next steps

1. **Do not build a CCI to test the layout_classify fix** — §3 proves it cannot
   change anything.
2. **Confirm §5 with one GDB sample.** Unconditional breakpoint at the
   `korean_draw_1` trampoline entry (`0x0087F8C4`); read `*(0x00A46FE0)` and the
   computed base once from a **codec** screen and once from a **movie/demo**
   subtitle. If they resolve differently relative to the resident
   `scenerio.gcx`, §5 is confirmed. Requires the user to play to each screen;
   conditional breakpoints must not be used (they crash this GDB/stub pair).
3. **If confirmed**, change the base resolution rather than the range checks —
   e.g. derive the Korean page from the same pointer the retail page-0 path uses
   (`table[0]`, populated once by the font loader at `0x00643554`), or add a
   validity check with a fallback, instead of depending on the shared `table[2]`.
4. **Independently, fix 감/달** (§2.4) by reassigning those two characters to
   free global-page slots. This is a data change, no code patch.

## Reproduction

Scripts used for this audit are ad-hoc scans over the decompressed image
(exact-encoding word scans plus Capstone context dumps). The three findings that
matter are each re-derivable from the addresses tabulated above.
