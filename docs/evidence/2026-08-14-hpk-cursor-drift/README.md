# HPK cursor drift — hardware crash evidence (2026-08-14)

Primary evidence for the `v000a_0/cache.hpk` Data Abort on physical hardware.
Root cause is resolved: it is a **packer** defect in
`tools/mgs3d_history_texture.py`, not a loader defect and not the Korean
renderer trampoline.

## Files

| file | sha256 | note |
|---|---|---|
| `hardware-crash-v2.dmp` | `2840ad54c2239aa556775a2e6743db4c762b4ea3ac11f2689f69ac68ee9d0115` | Luma3DS exception dump v3.1, from the physical 3DS (Luma `crash_dump_00000001`) |
| `hardware-crash-v2-second.dmp` | `1f29fa4fc7d868b7fa43b5296886c5e2ee9522bb5cf7da400809019d44b0d8a3` | second occurrence (Luma `crash_dump_00000002`), **same defect** |
| `hardware-crash-earlier-unrelated.dmp` | `06e0e7bee9b3047981c2a485e6c6f2e25e6be8fa123b08518d5e17d20fad28f6` | older, different fault (Luma `crash_dump_00000000`); see the note at the end |

The first dump was previously an untracked working-copy file named
`tests/crash_dump_00000001(1).dmp`. These are irreplaceable (physical-device
faults) so they are committed here rather than under the gitignored
`experiments/`. Decode them with `tools/mgs3d_crash_dump.py`.

Note that Luma's file timestamps are meaningless here (the console RTC reads
2001); only the dump numbering gives ordering.

### Second occurrence — identical

`hardware-crash-v2-second.dmp` differs from the first dump in **8 bytes total**:
`fpinst`/`fpinst2` (dead FPU state) and two stack bytes. Every meaningful value
matches exactly — `pc=0x0018344C`, `lr=0x00165160`, `r6=r8=0x03A00EB1`,
`r4=0x00919CC8`, and the same stream state (`valid=0x80000`, `cursor=0x1495D`,
`total=0x627827`, `remaining=0x127827`) giving the same absolute cursor
`0x49495D`.

That cursor value is only reachable from an archive whose entry 31 declares a
short `packed` size, so **the CCI that produced this dump still carried the
defective `cache.hpk`**; the packer fix was not in that build.

Beware that the corrected archive is the **same size** as the defective one
(6,453,287 bytes), so size cannot distinguish them — compare SHA-256 or run
`tools/mgs3d_hpk_chain_check.py`.

## Decoded dump

Header: magic `DEADC0DE`/`DEADCAFE`, version 3.1, processor 11 (ARM11),
exception type 3 (**Data Abort**), total 1204 B = 40 hdr + 92 regs + 96 code +
960 stack + 16 extra. Process `MGS-SE3D`, title ID `0004000000081E00`.

```
r0  00000000   r1  087E6E45   r2  0006B693   r3  015A0000
r4  00919CC8   r5  0006B6A3   r6  03A00EB1   r7  00000000
r8  03A00EB1   r9  00000000   r10 008FB03C   r11 00000000
r12 DA780000   sp  00919C40   lr  00165160   pc  0018344C
cpsr 28000010  dfsr 00000805  ifsr 00001006  far 00000000
fpexc 40000700 fpinst EE4C7AAB fpinst2 EE4C7AAB
```

`DFSR=0x805` → WnR=1 (write), FS=5 (section translation fault); `FAR=0`.

The 96-byte code dump matches `V2-code.decompressed.bin` byte-for-byte at
`0x001833F0`, so the dump window is `PC-0x5C .. PC` and the **last** word is the
faulting instruction:

```
0018344C  E8A01008   stmia r0!, {r3, r12}      ; r0 == 0  -> write to address 0
```

Lineage: `V2-code.decompressed.bin` sha256
`105c8a1575dd3c0a65dc89ac6e81aa7e3eb9710f1c9449a00894cfb32cbc5ffa`, i.e. the
recorded clean-baseline V2 build. `r10 = 0x008FB03C` is the max-window global,
whose value is `0x00080000`.

## Stream object (`r4 = sp+0x88 = 0x00919CC8`)

```
[r4+0x00] 008A78A4   vtable        ([vtable+8] = 0x00165110, the read method)
[r4+0x04] 087D24E0   window buffer base
[r4+0x08] 00080000   valid bytes in window
[r4+0x0C] 0001495D   cursor within window
[r4+0x10] 00627827   total stream size  == cache.hpk size (6,453,287)
[r4+0x18] 00127827   bytes still unread from file
[r4+0x1C] ...        file object
```

Bytes consumed from file = `0x627827 - 0x127827 = 0x500000` = 10 × `0x80000`, so
the window covers `[0x480000, 0x500000)` and the absolute cursor is
`0x480000 + 0x1495D = 0x49495D`.

This is confirmed by data, not only arithmetic: the memcpy had already loaded
two words from the source, and `r3 = 0x015A0000` / `r12 = 0xDA780000` are exactly
the words at file offsets `0x49495D` and `0x494961`.

## Loader model (static, exact)

`0x0014EFE8..0x0014F050` — HPK entry loop:

```
read(4)  -> entry count (148)
loop i:
    read(12) -> {key, unpacked, packed}      ; 0x0014F00C: mov r2,#0xC
    if packed == 0: skip
    0x00164774(stream, packed, key, mode, unpacked)
```

`0x00165110` — windowed read(stream, dst, size):

* copies from the window, advancing `[r4+0x0C]` by exactly the bytes copied;
* refills via `0x0014FEC8` when the window is drained, capping at `[0x008FB03C]`
  = `0x80000` and resetting the cursor to 0;
* the **only** path that advances by less than requested is EOF
  (`[r4+0x18] <= 0` at `0x001651A4` returns the short count), and the caller at
  `0x0014F018` ignores the return value.

`0x00164774` — entry processor: every branch reads exactly `packed` bytes
(`0x001647C8`, `0x00164850`, `0x001648F4`, `0x00164968`).

**Therefore the loader advances by exactly `12 + packed` per entry.** There is no
"12 becomes 6" condition anywhere in the header-read path. At entry 31 the file
was nowhere near EOF (`0x1A7827` bytes remained) and the header at `0x493A1F`
sits mid-window, so neither the EOF path nor a window-boundary straddle applies.

## Root cause — `tools/mgs3d_history_texture.py:105-107`

```python
struct.pack_into("<II", hpk, offset + 4, len(patched_darc), len(packed))
start = offset + 12
hpk[start:start + old_packed_size] = packed.ljust(old_packed_size, b"\0")
```

The header's `packed` field is rewritten to the **new, smaller** compressed
length, while the physical slot is zero-padded back to the **old** length "to
keep every entry offset fixed". The offsets are fixed only physically; the
loader is strictly sequential, so from that entry onward it runs
`old_packed_size - new_packed_size` bytes **early** for the rest of the archive.

Reproduction (exact): running `patch_hpk` on the clean
`cache.hpk` (`145a82e9acba662afb024baadd0a25ec1eabca2c1006be26eb5891670561bbc0`)
with `malgun.ttf` size 12 yields sha256
`4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d` — the
recorded v0.65 HPK hash — with `hpk_entry_offset = 4799007 = 0x493A1F`
(entry 31, key `309d745f`), `old_packed_size = 3884`, `new_packed_size = 3146`,
i.e. 738 bytes of zero padding.

**That reproduction produces the observed hardware fault exactly**, because a
header whose `packed` field is 0 still consumes its 12 bytes and is otherwise
skipped (`0x0014F024` → `0x0014F0BC`, which reads nothing further when the
caller's spare argument is 0). The loader therefore walks the padding as
`738 // 12 = 61` empty headers and reads the next real header straddling the
remaining `738 mod 12 = 6` padding bytes — landing on `0x494951` with
`packed = 0x03A00EB1`. **The drift that matters is the padding length modulo
12, not its absolute size.**

A font-size sweep over the usable range (any size whose output does not exceed
3884 bytes) produces padding from 1192 down to 7 bytes and never 0 — **no
parameter choice makes this tool emit a correct archive.**

## Failure chain

1. Entry 31 (`309d745f`) header declares `packed = 3146`; its physical slot is
   3884 bytes, the trailing 738 being zero padding written by the tool.
2. The loader consumes the padding as 61 empty headers, then reads entry 32's
   header from `0x494951` instead of `0x494957` — 6 bytes early.
3. Those 12 bytes decode as `key = 0x00000000`, `unpacked = 0x42F60000`,
   `packed = 0x03A00EB1`.
4. `0x001648B0` allocates `unpacked` (1.12 GiB) → NULL.
5. `0x001648D8` allocates `packed` (60.8 MiB) → NULL; `0x001648DC mov r5, r0`
   stores it with no check.
6. `0x001648F4` calls read(stream, NULL, 0x03A00EB1); `0x0016515C` calls memcpy
   with dst = 0 and len = `0x80000 - 0x1495D = 0x6B6A3` (the window remainder).
7. `0x0018344C stmia r0!, {r3, r12}` writes to address 0 → Data Abort.

Every register in the dump is accounted for by this chain.

## Correct pattern for comparison

`tools/mgs3d_hpk_static_korean.py:120-125` performs the same in-place entry
replacement but **never rewrites the header size field** — it only pads the
payload back to the original `packed_size`. That archive stays chained
correctly. This is the pattern `mgs3d_history_texture.py` must adopt.

## Retired hypotheses

* `PC = 0x00183A4C` / `LR = 0x00165168` (recorded 2026-08-13) are misreadings of
  `0x0018344C` / `0x00165160`. `0x00183A4C` is a real instruction
  (`ldrhcs r0,[r4]`) in the patched text decoder, which is why the reading looked
  self-consistent, but it is not where this crash occurred.
* The Korean renderer trampoline at `0x00183A04` → `0x0087FA80` is **not**
  implicated. The branch itself is intact (verified: `EA1BF01D` targets
  `0x0087FA80`).
* `stage/v000a_0/scenerio.gcx` and its appended Korean page at `0x622DC` are not
  implicated in this crash.
* The requested dynamic Azahar/GDB observation of the cursor is unnecessary; the
  hardware dump already contains the value it was meant to capture.

## Reverification

```
python tools/mgs3d_hpk_chain_check.py <path to cache.hpk>
```

Exit status is non-zero when an entry's declared `packed` size is followed by
zero padding before the next header — the exact defect above. Verified results:

| archive | result |
|---|---|
| `originals/3ds_pristine/.../cache.hpk` | OK |
| clean `145a82e9…` | OK |
| v0.65 repro `49447057…` | FAIL — entry 31, 738 zero bytes, residue 6 |

## Earlier, unrelated dump

`hardware-crash-earlier-unrelated.dmp` (Luma `crash_dump_00000000`) is a
different fault and is kept only so it is not mistaken for this one:
`PC=0x00115098`, `LR=0x00106F5C`, `FAR=0x00030000`, DFSR `0x5` — a **read**
translation fault, not a write, at a non-zero address, in an unrelated function.
It predates both HPK dumps and is not explained by the drift above. Not
investigated.

## Open, unrelated to this crash

The sequential walk does not reach EOF on **any** of these archives, including
the pristine retail one (it stops at key `3e6af67a`, whose `packed` field reads
`0xbf1d1192`). So the loader model above is incomplete for the archive tail —
some later entry class is walked differently. This does not affect the result:
the crash occurs at entry 31→32, far inside the region where the model is
verified sane, and the model reproduces the fault exactly. The checker therefore
reports the tail as a note rather than a failure. Resolving the tail is a
separate, lower-priority question.
