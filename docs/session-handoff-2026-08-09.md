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

## Housekeeping

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
- Azahar is left running in the background (with GDB attached, currently
  free-running) — fine to close whenever, no live experiment depends on
  keeping it open.
- `analysis/citra_gdb_*.log` and `analysis/citra_azahar_*.log` (many
  files, this session) are the raw evidence trail for §4's investigation
  — kept for reference, not cleaned up.
- **Top of next session**: (1) check §6's translation job and review
  quality, (2) decide whether to invest in §5's build environment, (3) if
  GDB is used again, read `feedback_citra_azahar_gdb_debugging.md` first
  — it has the exact procedure and the one mistake not to repeat, (4)
  decide whether to fold §8's `--reuse-existing-dead-font` into a real
  production codec.dat rebuild now that it's verified on representative
  GCX (144 more GCX besides 767/779/1412 still have unclaimed dead-slot
  budget per the inventory JSON — 147 total have dead slots).
