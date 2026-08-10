# Session handoff — 2026-08-09 (continued from 08-08 night)

Canonical summary is `docs/WIKI.md`. This file is the narrative record of
what happened this session, in order. Continues directly from
`docs/session-handoff-2026-08-08.md`'s "top of next session" items.

## 1. Fixed-layout donor-reclaim for movie/demo, and a real deploy

Built `rebuild_record_fixed_reclaim()` / `build-korean --fixed-layout-reclaim`
in `tools/mgs3d_movie_tool.py`, replacing the unsafe `--size-neutral-reclaim`
(see `feedback_mgs3d_movie_demo_size_neutral_reclaim_unsafe.md`). Every
subtitle keeps its own offset and capacity; donor entries (French/German/
Italian/Spanish) are blanked in place, never shrunk; new glyphs are
appended after the record's font table, growing the record only at its
very end. Found and fixed a real bug during this: records with pre-existing
trailing slack (leftover glyph-capacity padding from an older build) could
get silently shrunk by naive alignment padding — added a shrink guard.

Applied to demo.dat's opening "Flying over Pakistan" sequence (scene #127,
records 287-291): the new mode fits 27/27 candidate lines, but needs
9,232 bytes of appended font data against a real scene budget of only
1,974 bytes (measured via `tools/mgs3d_demo_scene_compact.py budget`).
User picked a narrative-order prefix over a cheapest-marginal-cost greedy
selection (avoids the "Korean line, sudden English line" jarring effect
from the earlier `--size-neutral-reclaim` test) — **5/27 lines fit**: both
flagship lines ("파키스탄 상공, 고도 3만 피트." / "곧 소련 영공에
접근합니다.") plus 3 more from record 288, then English for the rest.

Final build, deployed to RomForge live staging (backed up first):
`analysis/ps2_korean/full_build/rebuild_2026-08-08/demo_opening_fixed5_final.dat`
(SHA-256 `50026766AA0308C2289D4CA668F4D4975FBCE5626E611431FCCEEECDA38938AF`).
Independently verified: 0 subtitle offset/capacity drift across all 333
records, all 130 scene starts byte-identical, file size unchanged, 5 lines
manually decoded and confirmed correct with real glyph reuse ("공" shared
between "상공"/"영공"). **Not yet tested on real hardware/Citra** — that's
still open.

## 2. PT-BR HD Remaster fan patch — dead end, don't revisit

User found a Portuguese fan-translation patch for the MGS3 HD Remaster
(different platform, `N:\Traducao PT-BR-175-1-1-1772746651\`) and asked
whether analyzing it could give capacity-handling hints. Checked: it's a
**different container format** (`.sdt` for codec/movie/demo,
`LCGB`-magic-prefixed `.gcx` files for scenario data — not byte-compatible
with our GCX-per-codec.dat format despite the shared `.gcx` extension), no
original files to diff against (only the patched drop-in replacements
shipped), no documentation or patcher source. Portuguese is also Latin
script, so their capacity problem (if any) was pure text-length, not our
actual bottleneck (Hangul glyph-table capacity). Full file list saved at
`analysis/pt_br_hd_remaster_reference/filelist.txt` (6,625 files) in case
useful later, but not worth pursuing further.

## 3. codec.dat GCX53 pinning — targeted Capstone static scan (inconclusive)

Per `docs/session-handoff-2026-08-08.md` §4.11's finding (GCX53's content
and physical address are externally paired, Case 3 confirmed), built a
bounded, targeted Capstone-based scan of `code.bin` — not blind full-binary
reversing, scoped to candidates connected to GCX51-55's real offsets, with
a strict acceptance rule (2+ GCX connected, not a single coincidental
match). New tool: `tools/mgs3d_code_gcx_ref_scan.py`.

Key groundwork: `code.bin` is BLZ-compressed (confirmed via `exheader.bin`
flag byte), decompressed via the already-existing `tools/nintendo_blz.py`
to a verified SHA-256 `10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7`
(matches `analysis/3ds_code_en_decompressed.bin` — the other 4 cached
decompressed variants in the repo are the JP build, don't use them). VA
map derived from `exheader.bin`'s CodeSetInfo, confirmed exact via page
math (1920+58+92 pages × 0x1000 = 8,478,720 bytes = decompressed size
exactly).

Result: **no candidate survived the strict filter** — raw/÷0x10/÷0x20
constant search, Thumb+ARM MOVW/MOVT reconstructed-immediate search, and
`.rodata` consecutive-offset-table search all came back empty for the
high-entropy GCX51-55 values. Verdict: `targeted static scan inconclusive`,
recorded per the pre-agreed exit condition — did not expand into deeper
static analysis. Full report:
`analysis/ps2_korean/full_build/rebuild_2026-08-08/gcx_ref_scan_report.json`.

## 4. Dynamic debugging saga — the real story of tonight

This took most of the session and is worth reading in full in
`feedback_citra_azahar_gdb_debugging.md` and
`project_mgs3d_codec_growth_experiment.md`'s "2026-08-09" section — this
is just the narrative summary.

**What actually happened, in order:**
1. Tried GDB on the old Citra build (`citra-windows-msvc-20240303-0ff3440_2`,
   March 2024 dev nightly) — every attempt failed identically: connect,
   then `GDBStub::ReadByte: recv failed : 0` within the same millisecond,
   stub shuts down and won't restart without a full app relaunch.
2. Tried the UDP scripting protocol (`scripting/citra.py`, port 45987) as
   a GDB-free alternative — protocol itself verified working (exact
   byte-for-byte match reading `.text`'s known bytes), but 4 separate
   signature scans for `codec.dat`'s buffer (full 4GB space, linear-heap
   region, twice over `0x08000000-0x20000000`) all came back with zero
   hits, even right after a real codec call.
3. Installed **Azahar** (`azahar-emu/azahar`, actively-maintained Citra
   fork, v2125.1.3) specifically to test whether a modern fork fixes GDB.
   Same `recv failed : 0` bug reproduced — proved the bug lives in shared
   `core/gdbstub/gdbstub.cpp`, not the old build specifically.
4. User pushed back correctly: TCP `recv()` returning 0 means the *peer*
   closed the connection — could be pointing at *our own client*, not
   necessarily a server bug. This was the right question.
5. **Root cause found**: this whole session's habit of doing bare
   `socket.create_connection((host,port)); s.close()` "is the port open"
   probes was itself the disconnecting client every single time. Once
   probing stopped, GDB connected and worked immediately — **twice**,
   with real register/stack/disassembly captured via
   `tools/citra_gdb_mi_controller.py --command snapshot`.
6. Found the actual working recipe (pre-set `use_gdbstub=true` in Azahar's
   config before launch, launch as a genuinely fresh process with the CCI
   path independently quoted in PowerShell's `-ArgumentList`, attach
   immediately with zero probing in between) — see the dedicated memory
   file for the exact, reusable procedure.
7. **Hard constraint discovered**: the connection only works once per
   Azahar process lifetime. Neither the Debug-menu checkbox toggle nor
   restarting the game within the same running app re-triggers
   `GDBStub::Init` — confirmed by grepping for a new "Starting GDB
   server" log line after both, found none either time. Only a full
   process close + relaunch works.
8. **Architectural ceiling found**: guest-GDB can only inspect/break on
   the 3DS game's own ARM code — it has no visibility into Azahar's own
   C++ implementation (e.g. `Service::FS::File::Read()`, where the actual
   file-offset/size numbers we want live). This is not a tooling
   limitation, it's fundamental to what the GDB stub exposes. To capture
   an actual `codec.dat offset=/size=/guest_pc=` triple, the C++-level
   instrumentation from §5 below is structurally necessary — no amount of
   guest-GDB cleverness substitutes for it.

**Net result:** GDB dynamic debugging is now a genuinely working tool for
this project (huge unblock — it was believed broken all night), but it
answers a *different* question (guest-code register/memory state at a
chosen guest PC) than the one still open (finding what guest PC/offset
actually reads `codec.dat`, which needs §5's instrumentation to discover
in the first place, and *then* guest-GDB to backtrace from).

## 5. Azahar source instrumentation — prepared, not built (Plan B, paused)

Cloned `azahar-emu/azahar` at tag `2125.1.3` (matching the installed
binary) to `D:/dev/azahar-src`. Added one log line in
`src/core/hle/service/fs/file.cpp`'s `File::Read()`, right after the
existing offset/length parse:

```cpp
if (path.DebugStr().find("codec.dat") != std::string::npos) {
    LOG_ERROR(Service_FS, "codec.dat read\noffset=0x{:X}\nsize=0x{:X}\nguest_pc=0x{:08X}",
              offset, length, Core::GetRunningCore().GetPC());
}
```

This edit is **uncommitted, sitting in the clone**, ready to build. Not
yet built: the full build environment doesn't exist on this machine
(Ninja, ccache, Vulkan SDK, vcpkg-driven dependency compile are all
missing; only CMake and MSVC via VS Build Tools are present) and
realistically costs 1-3 hours to stand up from scratch. Paused per user's
explicit call to prioritize restoring the GDB path first (§4) — which
worked, but doesn't replace the need for this instrumentation (see §4.8's
architectural-ceiling finding). **This is the clear next step whenever
there's a block of uninterrupted time to spend on it.**

## 6. LLM translation job (movie/demo backlog) — still running

The overnight NAS/Mac-mini LLM translation job (`tools/mgs3d_llm_translate_worker.py`
on the NAS, `\\rich\WD_14\Dev\Translate\`) is still running as of this
session's end. Progress checked twice:
- Early check: demo 330/1048, movie 2/319.
- Later check: demo 412/1048 (~39%), movie 83/319 (~26%).

Output files: `demo_llm_full_v2.csv`, `movie_llm_full_v2.csv` in the NAS
folder. **Top of next session**: pull the completed files, spot-check a
quality sample before trusting the rest (per the standing rule — LLM
output needs human review, not blind trust), and check `all_runs.log`/
`overnight.log` for any errors that might have stopped it early.

## 7. 64B glyph / 191-slot forensic re-verification (later same day)

User asked for a from-scratch, no-assumptions re-verification of two
long-used constants: "Hangul glyph = 64 bytes" and "static glyph slots =
191" — specifically whether either is a real original-format constraint or
just something a past patcher invented. Full method: repo-wide constant
search, git history (root commit `2008d60` already contained the mature
toolkit — real reversing predates git tracking, so relied on the earliest
committed docs instead), direct visual decode of real original glyph data,
and cross-checking against `docs/ps2-korean-port-2026-08-02.md`'s existing
ARM-disassembly + live-memory-dump findings.

**Result — both are real, not invented:**
- **64 bytes = [B] derived from original data.** 16×16 pixels × 2bpp is a
  fixed mathematical consequence, independently confirmed by decoding two
  unrelated real glyph tables under the same formula: the pristine
  pre-Korean-patch `resident.hpk`'s static font table (slots 0-80 decoded
  into a clean, legible Western accented-Latin character set — À Á Â Ã Ä
  Å Æ Ç È É... ñ) and codec.dat GCX 1412 from a supposedly-pristine backup
  (986 slots decoded into hundreds of legible Japanese kanji). **Important
  correction, found the next day during §8's work: that GCX 1412 backup
  file is actually the Japanese-SKU codec.dat, not the English one — see
  §8's correction.** The 64-byte/16×16/2bpp finding itself is unaffected
  (it was confirmed independently via the HPK decode too, and again via
  §8's own fresh synthetic-GCX test), only the specific "GCX 1412 has 986
  glyphs" claim is wrong.
- **191 static HPK slots = [A] a real renderer-confirmed hard limit,
  unrelated to codec.dat.** `docs/ps2-korean-port-2026-08-02.md` already
  documented this via actual ARM disassembly (renderer branches at
  `0x0015E60C`/`0x0015EC64`) cross-checked against a live emulator memory
  dump: 192 total addressable slots (81+84+27 across the `0x81/82/83`
  token pages), of which token `0x8301` is confirmed cleared by the game
  engine at runtime, leaving 191 genuinely usable. Not an arbitrary safety
  margin. One small, unresolved, low-stakes discrepancy: a raw buffer-size
  computation suggests slot indices 191-193 (0-indexed) still hold
  real-looking leftover Latin characters past the 191 cutoff — plausibly
  just trailing non-functional bytes past the renderer's real address
  range, not verified either way, not worth pursuing further without a
  real hardware test.
- **Absolute distinction, do not merge these two systems**: the 191-slot
  limit belongs entirely to `tools/mgs3d_hpk_static_korean.py`'s HPK static
  font (`resident.hpk`, tokens `0x81/82/83`). codec.dat/movie.dat/demo.dat's
  own per-GCX/per-record custom glyph tables (tokens `0x8C`/`0x90`) are a
  completely separate system with its own 1,020-slot-per-GCX cap, already
  well understood before this check.

## 8. codec.dat dead-glyph-slot reuse — implemented and verified (later same day)

Following directly from §7's investigation: a live scan (found while
verifying §7) showed 1,545 completely dead custom-glyph slots across 147
GCX in the production codec.dat (leftovers from past donor-reclaim builds
that blanked donor text but never reclaimed the now-orphaned glyph bitmaps).
Implemented and verified the fix — full detail, all numbers, and one
important negative result in
**`docs/codec-dead-glyph-slot-reuse-2026-08-09.md`**. Summary:

- Fixed a real (not-yet-triggered) bug in the glyph-reference scanner
  (`glyph_slot_owners`, moved to `mgs3d_gcx_font_tool.py`): missing
  `0x1F <suffix>` accent-escape handling could have misaligned the scan and
  hidden a real glyph reference.
- New tools: `mgs3d_gcx_dead_slot_inventory.py` (whole-codec CSV+JSON
  report), `mgs3d_gcx_dead_slot_audit.py` (independent cross-check via the
  *other* pre-existing scanner), `mgs3d_gcx_japanese_donor_audit.py`
  (donor-language-block detector, general-purpose).
- New `build-korean --reuse-existing-dead-font` + `--dry-run` flags.
- **Important correction found during this work**: the "GCX 1412 = 986
  Japanese donor glyphs" claim from §7 was a wrong-SKU-file artifact (see
  §8's doc for the exact hashes/sizes). GCX 1412 in the real English
  pristine original has 0 custom-glyph slots.
- **Important negative result found during verification**:
  `--reuse-existing-dead-font` produces **zero additional byte savings**
  for any GCX already present in a translation batch, because the
  pre-existing `--reuse-freed-font` mechanism already discovers
  pre-existing dead slots as a mathematical side effect (proven and
  empirically confirmed). The real, delivered value is the whole-codec
  inventory/audit tools (genuinely new: nothing before could answer "how
  much dead capacity exists right now, independent of any translation
  batch") plus explicit reporting/documentation of a previously
  non-obvious property.
- Verified via binary diff on 3 representative GCX (767, 779, 1412):
  zero file-size change, zero offset drift on any other GCX (whole-file
  `mgs3d_codec_offset_diff.py`), zero internal-layout drift
  (`mgs3d_verify_build.py`'s fixed-layout check, 2,326/2,326 records), new
  Hangul glyphs proven to land exactly in pre-existing dead slots, and a
  full byte-diff proving nothing outside the resource table/string
  blob/reused glyph slots changed. 118/118 tests pass (8 new).
- Not yet done: applying this to a real production build (only
  representative-GCX verification was in scope this session).

## 9. codec.dat EN/JP SKU structural comparison (later same day)

Full GCX-by-GCX structural comparison between the EN pristine and JP SKU
codec.dat files, to test whether JP's much larger Kanji glyph tables give
evidence about EN's GCX53 position-sensitivity problem
([[project-mgs3d-codec-growth-experiment]]). Full detail, all numbers, CSV/
JSON artifacts, and the H1-H5 verdicts in
**`docs/codec-en-jp-structural-compare-2026-08-09.md`**. Headline results:

- JP file used: `unpacked_metagear_jpn\...\codec.dat` (explicitly documented
  as "the Japanese unpack" in 2026-08-02 docs) — not `backup_original_dat`
  (which differs in 27% of raw bytes despite identical size, but is
  structurally identical on every field this analysis uses, so the choice
  didn't matter here; recorded for the record).
- JP uses custom glyphs in 2,237/2,326 GCX (155,374 slots, 9.5MB) vs EN's
  8/2,326 (53 slots) — confirms JP genuinely has vastly larger glyph
  tables (H1 CONFIRMED).
- But the max JP-bigger-than-EN size delta for the *same* GCX, across all
  2,326 records, is only +2,832 bytes — zero GCX exceed +5KB. The "tens of
  KB bigger than EN" framing (H2) is REFUTED; only "several KB" holds.
- GCX53 sits at completely different absolute offsets in EN (284,592) vs
  JP (295,808) throughout a real, working shipped JP game — strong
  circumstantial support (H3/H4 CONFIRMED) that the EN GCX53 problem is a
  SKU-specific compiled reference, not a universal engine limit. Does
  **not** locate the actual reference or supply a patch method (H5
  explicitly REFUTED at the held-to-high-bar standard) — dynamic
  debugging (now working, §4 of 2026-08-09's earlier work) is the
  suggested next step, not this comparison itself.
- New tool: `tools/mgs3d_codec_en_jp_structural_compare.py` (read-only,
  reuses `parse_codec`/`font_region`).

## 10. GCX53 dynamic FS instrumentation — first real codec read captured (2026-08-10)

The Azahar source build described as pending in section 5 was completed
successfully. The original instrumentation produced zero events because its
assumption was wrong: MGS3D does not open `codec.dat` as a named FS file or as
an `OpenSubFile`. It opens the entire RomFS through one binary-path IVFC handle
and performs absolute reads itself (`path=[Binary: 000000000000000000000000]`,
`base=0`, `subfile=false`).

After temporarily logging every `File::Read`, the user entered the first codec
screen. The decisive event was:

```
requested=0x54550 size=0x6000 guest_pc=0x00837018
```

Direct byte comparison against the CCI and live production `codec.dat` proved:

- `codec.dat` RomFS base = `0x10550`.
- The read is exactly `codec.dat[0x44000:0x4A000]` (all 24,576 bytes equal;
  SHA-256 `d8f971848eb0258a57de312036f268f11ed972e051935fe35855b9d9f912067b`).
- GCX53 begins at codec offset `0x457B0`, i.e. `0x17B0` bytes into this read.
- Therefore the first codec screen loads GCX53 inside one coarse 24KB FS read.

Important limitation: `guest_pc=0x00837018` is the guest's common synchronous
FS service-call site and was identical for all captured FS reads. It is not yet
the game-code instruction that parses GCX53. Also, shifting GCX53 by `0xC0`
still leaves it inside the same `0x44000..0x4A000` block, so normal-vs-shifted
FS read-stream comparison cannot expose the parser divergence. The next useful
step is guest GDB after this read completes: break/trace from the FS return site
or watch the in-memory bytes corresponding to read-relative `0x17B0`.

The Azahar instrumentation was then narrowed from unconditional logging to only
reads overlapping the verified codec RomFS range `[0x10550, 0x4027CC0)`.

## 11. GCX53 guest-buffer/GDB handoff experiments (2026-08-10, afternoon checkpoint)

This section supersedes section 10's vague "watch the buffer" next step and
records every important success/failure so the same dead ends are not repeated.

### Confirmed facts

- Added `MappedBuffer::GetAddress()` to the local Azahar source clone
  (`D:/dev/azahar-src`) and logged the guest destination of every codec read.
- Startup's unrelated tail read used buffer `0x090F1000`; the first real codec
  screen read was again exactly codec offset `0x44000`, size `0x6000`, but its
  destination was `0x15A08960`. Therefore GCX53 starts at guest VA
  **`0x15A0A110`** (`buffer + 0x17B0`). Buffer addresses are allocation-specific;
  never reuse the startup buffer as the codec-screen buffer.
- Skipping forward caused later codec chunks to load consecutively at
  `0x15A08960`, `0x15A18960`, `0x15A28960`, etc., independently confirming the
  mapped-buffer logging is real.
- Azahar's GDB read-watchpoint accepted `*0x15A0A110` but never fired. Guest JIT
  memory reads do not trigger this GDB hardware-watchpoint path in this setup.
- GDB connection recipe reconfirmed: in `qt-config.ini`, both
  `use_gdbstub\\default=false` and `use_gdbstub=true` are required. Setting only
  the value while leaving `default=true` silently logs
  `Debugging_UseGdbstub: false`. Launch a fresh Azahar, wait about 3 seconds for
  its stub to listen, then launch `tools/citra_gdb_mi_controller.py --daemon`.
  Never probe port 24689.

### Automatic-break experiments and lessons

1. Calling only `GDBStub::Break()` after the mapped-buffer write logged the
   request but did not stop the JIT.
2. Adding `PrepareReschedule()` still did not deliver the trap because the
   async HLE callback bypasses the normal CPU-run `SendTrap()` path.
3. Direct `GDBStub::SendTrap(kernel.GetCurrentThreadManager().GetCurrentThread(),
   5)` did stop GDB, but selected a zero-context helper thread. Thread list and
   all-register snapshots were successfully captured in
   `analysis/gcx53_dynamic_debug/gdb_direct_trap_20260810.log`.
4. Logging `Core::GetRunningCore().SaveContext()` was stable, but captured the
   unrelated thread running at callback time: PC `0x001665D0`, LR `0x00126E2C`,
   SP `0x00919E50`. Static disassembly proved these are an SVC/synchronization
   loop and event polling (`0x126E28 -> 0x133F6C`), not the codec parser.
5. Attempting to save that context into
   `kernel.GetCurrentThreadManager().GetCurrentThread()->context` crashed Azahar
   because current-thread can be null in this async callback. Do not restore
   this approach. The later Vulkan assertion crash was a separate renderer
   failure before the target codec read, not this null crash.

### Current final build — compiled, connected, target event not yet exercised

The correct original requester is already retained by
`HLERequestContext::ClientThread()`. The current source now, after the target
buffer has been written:

1. gets `const auto client_thread = ctx.ClientThread()`;
2. logs the saved `client_thread->context` registers (r0-r12/SP/LR/PC/CPSR);
3. calls `GDBStub::Break()` and `GDBStub::SendTrap(client_thread.get(), 5)`;
4. requests a reschedule.

This is build log `analysis/gcx53_dynamic_debug/build_output17.log`; it compiled
and bundled successfully. At the pause point it was running as Azahar PID
23368, GDB PID 4956, controller PID 19488, but **the user had not yet entered
the first codec on this exact build**. Those processes are intentionally shut
down during checkpoint cleanup. The next session should relaunch this same
binary, connect GDB using the recipe above, enter first codec once, then inspect:

- Azahar log for `GCX53 CPU context` (must now be the requesting FS thread, not
  `0x001665D0`);
- GDB MI log for the stopped thread and immediately issue register/stack/
  disassembly queries before continuing.

If this exact build crashes, first guard `ctx.ClientThread()` against null and
log that condition; do not fall back to the kernel's current thread. If it
stops with the expected real request context, use its LR/stack to place the next
execute breakpoint after FS reply and trace toward the first code touching
GCX53 at guest buffer `logged_buffer + 0x17B0`.

## 12. GCX53 client-thread capture succeeded (2026-08-10, resumed session)

Relaunched the exact `build_output17.log` client-thread instrumentation build,
attached GDB without probing port 24689, and entered the first codec once. The
target read was captured again at codec offset `0x44000`, size `0x6000`, guest
buffer `0x15A08960`. This time `ctx.ClientThread()` was valid and its saved
context was the real FS requester:

```
r0=0x00000000 r1=0x0006000C r2=0x0000000C r3=0x00000000
r4=0x1FF82E80 r5=0x0929BF80 r6=0x15A08960 r7=0x0929BF80
r8=0x00054550 r9=0x00000000 r10=0x00000000 r11=0x00000001
r12=0x080200C2 sp=0x0929BEF0 lr=0x00836524 pc=0x00837018
cpsr=0x20000010
```

`SendTrap(client_thread, 5)` still caused GDB to initially select an unrelated
helper (Thread 8 at `0x001665D0`), but `-thread-info` exposed the real requester
as GDB Thread 11 at `0x00837018`. Explicitly selecting Thread 11 recovered the
expected `PC/LR` pair and a two-frame GDB stack (`0x00837018 -> 0x00836524`).

Live disassembly proved `0x00837018` is the instruction immediately after
`svc 0x32` in the common synchronous FS IPC function. Its caller at
`0x00836520` calls that IPC function and returns at `0x00836524`. Unwinding the
captured raw stack by the two functions' known prologues found the next saved
return address at `SP+0x34 = 0x008358E0`; disassembly there shows a generic
virtual file-object read call at `0x008358DC` followed by its return at
`0x008358E0`. Thus all three addresses are still generic FS layers, not the
GCX53 parser.

An execute breakpoint at `0x00836524` did not fire under the guest JIT, matching
the earlier read-watchpoint limitation. The experiment nevertheless achieved
its immediate objective: the real client thread and complete request-time
register/stack context are now captured. Raw evidence is
`analysis/gcx53_dynamic_debug/gdb_client_thread_resume_20260810.log` plus the
Azahar log's `GCX53 CPU context` event. The temporary breakpoint was deleted
and execution resumed.

The next useful instrumentation should log more of the saved client stack (or
unwind it in the host while the context is available), rather than relying on
guest-JIT breakpoints. The first confirmed outer return to use is `0x008358E0`;
continue unwinding until leaving the generic file abstraction and reaching the
game-side caller that consumes the buffer.

## 13. GCX53 first-consumer trace and +0xC0 comparison (2026-08-10)

Extended the Azahar diagnostic build in two stages. First, the FS callback
scanned 0x400 bytes above the saved client SP for code addresses. This produced
a real read-call chain:

```
0x0011A830 -> 0x0014FEC8 -> 0x00132E6C -> 0x00152060
             -> virtual FS read -> 0x008358DC -> IPC/SVC
```

The first function updates its streaming buffer/counters from the returned byte
count; this is the game-side streaming loader, but not the later GCX consumer.

Second, disabled Dynarmic's page-table fastmem in a temporary diagnostic build
so guest memory accesses pass through `MemoryRead*` callbacks. Traced the
repeatedly stable first-screen GCX53 guest range beginning at `0x15A0A110`.
Normal-file results:

- `PC 0x00108420`, first read at `0x15A0A110`: in-place PRNG/XOR decryption
  loop (actual loads at `0x00108424/28`; callback PC is the JIT block PC), using
  multiplier `0x7D2B89DD`.
- `PC 0x0015EBD8`, read at `0x15A0AD6C`, followed by `0x0015ED60`: the existing
  custom-glyph renderer family. Disassembly directly reconnects this dynamic
  trace to the already-known token-page dispatch at `0x0015EC64` and the 2bpp
  glyph raster loop.

Then deployed the known-failing `codec_gcx53_shift_00c0.dat` to LayeredFS
(backing up the prior normal file first) and repeated the trace. **Decisive
result:** despite GCX53 moving from guest `0x15A0A110` to expected
`0x15A0A1D0`, the decryptor still first read old address `0x15A0A110`; the
renderer later still read old glyph address `0x15A0AD6C` instead of expected
`0x15A0AE2C`. This is direct runtime proof that the failing relocation leaves
the GCX53-derived runtime pointers pinned to the original layout.

Static follow-up found the sole direct `BL 0x00108320` (decrypt function) at
`0x007801DC`. Immediately before it, `0x007801D8` executes
`ldr r0, [r4, #0x34]`, supplying the resource pointer. Runtime inspection found
global `0x008E1618 -> object 0x158B5810`; object fields included
`+0x34=0x15A09110` and `+0x38=0x15A08960` (the FS block base). Because `+0x34`
is 0x1000 before the documented GCX53 start, it appears to be a containing
encrypted/resource-block base, not simply the GCX53 pointer; do not blindly add
0xC0 to this field without tracing its construction and dependents.

Evidence: `gdb_slowmem_trace_20260810.log` (normal),
`gdb_slowmem_shift00c0_20260810.log` (shifted), and the corresponding Azahar
logs. After the comparison, all diagnostic processes were stopped and the
LayeredFS codec was restored to SHA-256
`19FF34D1380E1AFD3D19DFBD0C9C3DF091FBFB5743E09189B5DC943A85BF6267`.
The Azahar source/bundle remains a deliberately slow no-fastmem diagnostic
build; restore `config.page_table` before ordinary emulator use.

Next: trace writes to the resource object's `+0x34` field (or statically trace
the constructor feeding `0x007801B8`) to identify the original offset source.
The patch target is upstream of `0x007801D8`, not the decrypt or glyph-render
loops themselves.

## 14. Packed descriptor located; single-descriptor patch insufficient (2026-08-10)

Slow-memory write tracing found the complete construction chain for the pinned
GCX53 pointer. The resource object's `+0x34` writer is the STM at `0x002A8F50`.
At that point:

```
r5 = 0x0200457B
r7 = 0x15A08960 (loaded FS block guest base)
r8 = 0x00006000
r11 = 0x0000008A
object+0x34 = 0x15A09110
```

The packed descriptor decodes exactly:

```
low 24 bits: 0x00457B * 0x10 = codec offset 0x457B0 (GCX53)
(r5 >> 7) = 0x8A                         (0x800 block number)
(r5 << 4) & 0x7F0 = 0x7B0               (within-block offset)
high byte 0x02 -> 0x6000                 (read/allocation size)
```

The descriptor itself is written to runtime field `0x088512AC` by
`0x0020D3B4`. That command calls argument decoder `0x0022F35C` repeatedly and
stores four script arguments at fields `+0x3C8..+0x3D4`; GCX53 is the second
argument. Capturing the decoder's live source pointer found the original value
at guest `0x08A99722`, bytes `7B 45 00 02`. A unique plaintext search found the
same bytes at file offset `0x14409` of
`analysis/ps2_korean/stages/select/7f010000_87a1c0.01`. Thus the pin is script
data, not `code.bin`. The corresponding 3DS source is associated with the
select-stage scenario resource, which is stored packed/encrypted; a safe 3DS
repacker/patch location has not yet been produced.

Tested a runtime-only descriptor override `0x0200457B -> 0x02004587` together
with `codec_gcx53_shift_00c0.dat`. The arithmetic worked as intended: codec FS
read moved `0x44000 -> 0x44800`, `r11` moved `0x8A -> 0x8B`, and the containing
resource pointer moved `0x447B0 -> 0x44870` (exactly +0xC0). Nevertheless the
first target radio produced an error and was skipped; other radio calls still
worked. Therefore a single descriptor patch is **insufficient**—one or more of
the command's other three arguments or another select-stage GCX53 reference
must also move. Do not call this a successful fix.

After the failed validation, all diagnostic processes were stopped, the
runtime override was removed from source, and LayeredFS `codec.dat` was restored
to normal hash `19FF34D1380E1AFD3D19DFBD0C9C3DF091FBFB5743E09189B5DC943A85BF6267`.
Source has additional `r0-r4` argument logging prepared but not yet rebuilt.
Next: rebuild once, capture `r1/r3/r4` at the descriptor STM, and identify which
companion argument(s) encode the old GCX53 end/size or related resource.

Follow-up capture showed the four decoded command arguments are
`0x3705, 0x0200457B, 0x4, 0x73`. The final value is the decimal resource number
115 (`0x73`), while only the second argument encodes the codec position; there
is no companion end/size descriptor in this command.

A second controlled `+0xC0` run forced `0x0200457B -> 0x02004587` and widened
the slow-memory trace. The override was applied, but crossing the descriptor's
0x800 file-read boundary changed the live containing-resource pointer from
normal `0x15A09110` to `0x15A089D0` (net `-0x740` in guest VA), even though the
underlying file position moved by `+0xC0`. The decrypt path then read at
`0x15A098AC` and the game crashed. This exposes an important aligned-read/guest
placement effect hidden by file-offset arithmetic. LayeredFS was immediately
restored to the normal SHA-256 above and the forced override was removed again.
The next discriminating test is the existing `+0x10` artifact with descriptor
`0x0200457C`: it stays within the same 0x800 read block and should separate
simple guest-address relocation from the boundary-crossing effect.

That `+0x10` test was completed. The override applied and the containing
resource pointer moved exactly as expected, `0x15A09110 -> 0x15A09120`, without
crossing the 0x800 file-read boundary. Nevertheless execution entered the
decrypt/parser path and then collapsed into unmapped low-address reads
(`0x1804`, `0x16F4`, etc.) followed by a Dynarmic assertion. Therefore the
0x800 boundary/guest-placement discontinuity seen in the `+0xC0` case is real
but is not the root cause: even a correctly relocated descriptor and exact
`+0x10` live pointer remain insufficient. This re-establishes that at least one
additional external reference/derived value exists outside the four arguments
of the located select-stage command. Normal LayeredFS was restored and the
temporary `0x0200457C` override was removed.

Parser-entry memory dumps finally explained why the apparently correct
descriptor relocation fails. With normal data, the outer resource base begins
`4EE76D54 00000000 000000A6 ...`. With the `+0x10` artifact and descriptor
changed to `0x0200457C`, the dump at the new base begins with normal
`base+0x10` (`000000FE 0000014D ...`): the complete dump is the normal dump
shifted left by exactly 16 bytes. Therefore `0x0200457B` selects the containing
resource/container start (which must remain fixed), not the movable inner GCX53
payload despite its low bits numerically matching GCX53's file offset. Moving
the descriptor skips the container header and guarantees parser failure.

The remaining repair target is now much narrower: keep descriptor
`0x0200457B`, and update the decrypted container's internal offset entries that
refer at/after inner offset `0x1000` when GCX53 is shifted. The normal header
already exposes flagged entries such as `0x2000104E`, `0x2000108A`, and
`0x200010B3`; their low offset portions cross the inner GCX53 boundary and are
prime runtime-patch candidates for a `+0x10` experiment. Both parser dumps were
preserved as `azahar_normal_parserdump_20260810.log` and
`azahar_shift0010_parserdump_20260810.log`. LayeredFS and source override were
restored afterward.

The minimal runtime repair was then validated successfully. With the existing
`+0x10` codec artifact, descriptor `0x0200457B` was left unchanged and only
three decrypted container-header words were adjusted immediately before parser
entry:

```
base+0x064: 0x2000104E -> 0x2000105E
base+0x070: 0x2000108A -> 0x2000109A
base+0x07C: 0x200010B3 -> 0x200010C3
```

User validation: first codec entry, portrait, dialogue, voice, closing, and
re-calling the codec were all normal. Azahar remained alive with no low-address
parser errors. This is the first runtime-successful GCX53 relocation and
confirms the exact missing relocation class: three flagged inner offsets in the
containing resource header, not the outer packed descriptor. Evidence is
`analysis/gcx53_dynamic_debug/azahar_shift0010_innerpatch_success_20260810.log`
(SHA-256 `837D4ADC3E58ABBBE39A33133E2427C88792E42EE1620A1C90A7B957B265D3FB`).
After capture, the experimental process was stopped, LayeredFS restored to the
normal codec hash, and the runtime mutation removed from Azahar source.

Next: implement these three adjustments in the codec builder at the serialized
container level (accounting for the in-place PRNG/XOR encoding), generalize the
delta instead of hard-coding `+0x10`, and validate a produced codec without any
Azahar runtime mutation.

That permanent implementation and validation are now complete. The three words
are plaintext GCX53 procedure-table entries at raw record offsets
`0x64/0x70/0x7C`, so no PRNG re-encoding is required. Added
`relocate_gcx53_inner_offsets()` to `mgs3d_codec_tool.py`; it preserves each
word's high-byte flags and adds the signed relocation delta to its low 24-bit
offset, while strictly requiring the known three-field layout. The precise
relocation helper exposes this behind `patch_gcx53_inner_offsets=True`, and the
main Korean font builder now automatically computes GCX53's final start delta
after reflow and applies the same correction whenever the delta is nonzero.
Fixed-layout builds have delta zero and remain byte-unaffected.

The generated file-only `+0x10` artifact was
`analysis/gcx53_dynamic_debug/codec_gcx53_shift_0010_inner_offsets_patched.dat`,
SHA-256 `5605848CF3778B8CD444BC0E4D3565BB1CC86CB787BD894BA3C6371981ED329C`.
Compared with the prior failing `+0x10` artifact it differs at exactly three
bytes (`0x45824`, `0x45830`, `0x4583C`). With an Azahar build containing no
runtime mutation and the original descriptor unchanged, the user confirmed the
first codec and the following codec both work normally (portrait, dialogue,
voice, close/re-call). Evidence:
`analysis/gcx53_dynamic_debug/azahar_filepatch_only_success_20260810.log`,
SHA-256 `17AC137C74A8979FA9317E4EF44D0E7A0AEEE3CE02B2B3B3123662637D1FF431`.
LayeredFS was restored afterward to the normal codec hash.

Tests: new `tests/test_codec_gcx53_relocation.py` plus the existing font-safety
and build-verifier suites, 45 tests total, all pass. The external Azahar clone
still contains diagnostic slow-memory/parser-dump instrumentation in source;
the runtime mutation itself is removed. Restore Dynarmic fastmem before normal
emulator use.

Follow-up generalized the implementation beyond GCX53. The core API is now
`relocate_gcx_internal_offsets(record, old_offset, new_offset)`: it scans the
selected record's complete procedure table, preserves high-byte flags, and
relocates every low-24 target at/after the old boundary by the signed delta.
The GCX53 function is a strict wrapper using `0x1000 -> 0x1000 + delta` and
retaining its three-field layout assertion. A full English codec audit covered
2,326 records / 216,705 procedure words and found every low-24 target within its
own record. The same offsets recur across records, so record context cannot be
inferred from two numbers alone; builders already possess that context. Generic
forward/backward tests raise the relevant combined suite count to 45 passing.

## Housekeeping

### Distributed codec grow runtime validation (2026-08-10 evening)

Before any movie/demo work, a normal translation/font build grew GCX
13/100/500/1000/1501/1990/2200 by 16,720 bytes and shifted 2,312 later records.
GCX53 moved `0x457B0 -> 0x45AE0` (+816); its three low-24 procedure targets were
automatically relocated. The whole-file verifier passed 2,326 records and
216,705 procedure words, including boundaries, relocation completeness, flag
preservation, and overflow checks.

Azahar runtime passed first codec, portrait/dialogue/voice, close/return,
same-codec recall, following sequential radio, and a later event radio call.
LayeredFS was restored to pristine SHA-256
`19FF34D1380E1AFD3D19DFBD0C9C3DF091FBFB5743E09189B5DC943A85BF6267`.
See `docs/codec-distributed-grow-stress-2026-08-10.md`.

- Live `codec.dat`/`movie.dat` in the RomForge romfs tree were **not**
  touched this session (all codec/GCX53 work was read-only analysis
  against the live file, or against LayeredFS mod overrides in
  `C:\Users\hhlee\AppData\Roaming\{Citra,Azahar}\load\mods\000400000007A000\romfs\`,
  never the real romfs tree). `demo.dat` **was** updated (§1) and is live.
  §8's new tools/tests were only run against scratch copies of codec.dat —
  the live RomForge codec.dat was never written to.
- LayeredFS mods folders were set up under both `Citra` and `Azahar`
  AppData with a copy of the live `codec.dat` for GCX53 testing — harmless
  to leave in place, doesn't affect the real romfs tree or any repack.
- 2026-08-10 checkpoint cleanup: the final client-thread build had been
  running as Azahar PID 23368, GDB PID 4956, and controller PID 19488.
  All three were intentionally stopped; no experiment depends on live state.
- `analysis/citra_gdb_*.log` and `analysis/citra_azahar_*.log` (many
  files, this session) are the raw evidence trail for §4's investigation
  — kept for reference, not cleaned up.
- **Top of next session**: (1) continue §12 by extending the host-side client
  stack capture/unwind beyond `0x008358E0` until it reaches the game-side
  consumer; (2) check §6's translation job and review quality,
  (3) if GDB is used again, read `feedback_citra_azahar_gdb_debugging.md`
  first — it has the exact procedure and the one mistake not to repeat, (4)
  decide whether to fold §8's `--reuse-existing-dead-font` into a real
  production codec.dat rebuild now that it's verified on representative
  GCX (144 more GCX besides 767/779/1412 still have unclaimed dead-slot
  budget per the inventory JSON — 147 total have dead slots).
