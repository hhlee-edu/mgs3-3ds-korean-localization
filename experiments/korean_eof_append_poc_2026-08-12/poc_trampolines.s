.syntax unified
.arm
.section .text
.align 2

@ EOF-append global-page trampoline. The original stress POC intercepted only
@ 0x8401..0x8440; clean integration exposed that stale bound when 0x8451 and
@ 0x84A4 fell through. The normalized range is now the complete physical page:
@ 0x8401..0x87FF excluding every xx00 hole.
@ The build otherwise retains the runtime-verified page3 renderer isolation:
@   1. the glyph index compacts the skipped xx00 holes, and
@   2. the glyph base is computed at runtime from the resident scenerio.gcx
@      buffer instead of being a fixed text-cave literal:
@         korean_page_base = table[2] + K
@      where table[2] (= *(0x00A46FE0)) is the page-2 font pointer the draw
@      path already uses, and K is a build-time constant chosen so that every
@      stage file has its Korean page at exactly page2_offset + K.  This is
@      stage-independent: v1 used buffer_base + <that stage's file size>,
@      which only resolved correctly while that one stage was resident.
@ The A0xx raw-token branches are dead (that namespace was rejected) but are
@ kept byte-for-byte so this build differs from the known-good one only where
@ intended.

@ 2026-08-15: the anchor moved off the shared font slot table[2].
@ table[2] is a per-screen slot: during a codec conversation the engine points
@ it at the loaded codec.dat GCX record's own page-2 glyph area (measured:
@ table[2]=0x15A278DC == codec.dat file offset 0x78A77C, 8192/8192 bytes), so
@ table[2]+K lands outside the resident scenerio.gcx buffer and the whole
@ global page draws as zeros.  The stage text object keeps its OWN page-2
@ pointer, snapshotted at 0x007801CC into [obj+0x4C], and that object is
@ reachable from the single-writer global 0x008E1618 (writer 0x007801C4).
@ Measured live during a failing codec conversation: obj[0x4C]=0x08982744 !=
@ table[2]=0x15A278DC, and obj[0x4C]+K matched korean_page_full.bin 64/64.
@ K itself is unchanged and still parser-relative (K gate: 169/169 stages).
@ 2026-08-16: multi-candidate validating guard.
@ 15 runtime samples (docs/anchor-runtime-verdict-2026-08-16.md,
@ docs/evidence/anchor-samples-2026-08-16.txt) show that NEITHER anchor is
@ correct on its own, and that they fail in disjoint situations:
@   obj[0x4C]  correct throughout a codec conversation (samples 4-9, where
@              table[2] reads as zeros), but it is a snapshot taken once at
@              scene setup (0x007801CC) and never refreshed, so once the
@              scenerio buffer is reallocated it points at reused memory
@              (samples 12-15: base pinned at 0x089d8744 while the live buffer
@              had moved to 0x08a93374). Non-zero wrong data -- garbled glyphs.
@   table[2]   correct after such a reallocation, but the codec conversation
@              screen repoints it at the codec.dat GCX's own glyph area, so it
@              reads as zeros -- blank glyphs.
@ The parser pointer *(0x00A472BC+0xC) was measured too and is NOT independent:
@ par + 4 == table[2] in all 15 samples, so it fails wherever table[2] does.
@
@ Therefore: try each candidate in turn and only accept one that actually points
@ at the Korean page. The page begins with the 호 glyph, whose bytes +0x0C..+0x0F
@ are 0F FF FF F0; +0x00..+0x0B are all zero and so cannot distinguish a good
@ pointer from a zeroed one, which is why the signature is taken at +0x0C.
@ It is compared as four bytes rather than one word because each byte value is
@ an encodable ARM immediate -- a 32-bit compare would need a third register to
@ hold the constant, and the two call sites only have (r0, ip) and (r2, r3) free.
@
@ No cache: measured, it cannot help. Samples 10 and 11 have the *same* base
@ address 0x089d8744, valid in 10 and invalid in 11 -- the address did not move,
@ the memory under it was overwritten. A cache of the last validated address
@ would hand back that same stale address. It would also need a writable word,
@ and this cave is in .text (RX).
@
@ ---------------------------------------------------------------------------
@ 2026-08-17: NON-DEREFERENCING RANGE GUARD -- fixes a hardware Data Abort.
@
@ The 2026-08-16 guard above validated a candidate by READING it, and its only
@ admission test before that read was "!= 0".  A stale snapshot that holds
@ non-pointer garbage therefore faulted inside the guard itself, so the guard
@ could never reject the very case it existed to handle.
@
@ Luma dump crash_dump_00000003.dmp, real hardware, movie playback + R input
@ (docs/evidence/2026-08-17-v082-renderer-data-abort/):
@     obj[0x4C] = 0x2A68DFA8   -> passes "!= 0"
@     + K       = 0x2A6E3FA8
@     LDRB [base+0x0C] @ 0x0087FA08 (korean_draw_2+0x80) -> translation fault
@     DFSR 0x05, FAR 0x2A6E3FB4, r3 held K (0x00056000), r9 held token 0x8428.
@
@ Fix: every pointer is now range-tested with arithmetic ONLY -- no load -- and
@ is dereferenced solely after it lands inside a window where valid values have
@ actually been observed.  Windows, from the 15-sample evidence file:
@     obj                0x158B5810                                  (linear heap)
@     obj[0x4C]          0x08982744, 0x08A93374                      (app heap)
@     table[2]           0x08954BB4, 0x08A9FC9C, 0x08982744,
@                        0x08A93374, 0x15A11B54
@     valid page bases   0x089D8744, 0x08AE9374                      (app heap)
@ so:
@   KOREAN_OBJ_LO/SPAN   [0x08000000, 0x1C000000)  application heap through
@                        linear heap -- the object itself is linear-heap
@                        allocated, the crash value 0x2A68DFA8 is outside.
@   KOREAN_PAGE_LO/SPAN  [0x08000000, 0x0C000000)  the application heap alone.
@                        EVERY page base ever observed to be correct is in it.
@                        The one linear-heap base ever seen (0x15A67B54, codec
@                        samples 4-9) was measured as ZEROS, i.e. already known
@                        invalid, so excluding it loses nothing and removes a
@                        dereference.
@ NULL folds into each test for free: 0 - LO wraps to a huge unsigned value and
@ fails the unsigned CMP, so no separate "cmp #0" is needed.
@
@ The unvalidated table[2] fallback is GONE.  When neither candidate proves
@ itself the trampoline now draws a blank instead of dereferencing an address it
@ could not vet: the base becomes korean_blank_glyph (128 zero bytes assembled
@ into this cave, therefore in mapped RX .text) and the glyph index is forced to
@ 0, so the retail blitter reads 64 bytes of zeros.  Nothing on any path can now
@ dereference an address that has not passed a range test.
@ Blank rather than garbled is also the strictly better failure mode: the width
@ trampolines still return 0x10, so a rejected glyph occupies its correct
@ advance and the line layout is unchanged.
@
@ korean_width_1/2, korean_pre_draw and korean_layout_classify are unchanged and
@ need no guard: they compute widths and classifications from the engine's own
@ tables and never dereference a glyph-page pointer (verified by disassembling
@ their continuations at 0x001843A4, 0x00184484, 0x0015E5A8 and 0x00183A08).
@ ---------------------------------------------------------------------------
@
@ This changes only where the base comes from. The 0x84-0x87 range checks, the
@ xx00 index compaction and the width/classify logic are untouched, so all 931
@ global glyphs are handled identically -- there is no per-character path here.

.equ KOREAN_OBJ_LO,    0x08000000
.equ KOREAN_OBJ_SPAN,  0x14000000
.equ KOREAN_PAGE_LO,   0x08000000
.equ KOREAN_PAGE_SPAN, 0x04000000

.macro KOREAN_VALIDATE reg, scratch
    ldrb   \scratch, [\reg, #0x0C]
    cmp    \scratch, #0x0F
    ldrbeq \scratch, [\reg, #0x0D]
    cmpeq  \scratch, #0xFF
    ldrbeq \scratch, [\reg, #0x0E]
    cmpeq  \scratch, #0xFF
    ldrbeq \scratch, [\reg, #0x0F]
    cmpeq  \scratch, #0xF0
.endm

@ KOREAN_BASE reg, scratch
@   in : r1 = compacted glyph index (both call sites)
@   out: \reg = a glyph-page base that is either signature-validated or the
@        in-cave blank page, and in the blank case r1 = 0.
@   Clobbers \reg, \scratch and -- only on the blank path -- r1.
@   No instruction dereferences a pointer that has not passed a range test.
.macro KOREAN_BASE reg, scratch
    @ ---- candidate 1: the stage text object's own page-2 snapshot ----
    ldr    \reg, korean_desc_literal
    ldr    \reg, [\reg]                    @ obj; the literal target is .data
    sub    \scratch, \reg, #KOREAN_OBJ_LO  @ obj sanity, no load (NULL folds in)
    cmp    \scratch, #KOREAN_OBJ_SPAN
    bhs    1f
    ldr    \reg, [\reg, #0x4C]             @ safe: obj proved in-window
    ldr    \scratch, korean_delta_literal
    add    \reg, \reg, \scratch
    sub    \scratch, \reg, #KOREAN_PAGE_LO @ base sanity, no load (NULL folds in)
    cmp    \scratch, #KOREAN_PAGE_SPAN
    bhs    1f
    KOREAN_VALIDATE \reg, \scratch         @ safe: base proved in-window
    beq    3f
    @ ---- candidate 2: the shared font page slot, now validated too ----
1:  ldr    \reg, korean_table2_literal
    ldr    \reg, [\reg]                    @ table[2]; the literal target is .data
    ldr    \scratch, korean_delta_literal
    add    \reg, \reg, \scratch
    sub    \scratch, \reg, #KOREAN_PAGE_LO
    cmp    \scratch, #KOREAN_PAGE_SPAN
    bhs    2f
    KOREAN_VALIDATE \reg, \scratch         @ safe: base proved in-window
    beq    3f
    @ ---- neither candidate proved itself: blank, never dereference ----
2:  ldr    \reg, korean_blank_literal
    mov    r1, #0                          @ index 0 -> the 64 bytes read are zero
3:
.endm

.global korean_draw_1
korean_draw_1:
    mov ip, r1, lsr #8
    cmp ip, #0x84
    blo draw_1_raw_check
    cmp ip, #0x87
    bhi draw_1_raw_check
    and ip, r1, #0xFF
    cmp ip, #0
    bne draw_1_normalized
draw_1_raw_check:
    mov ip, r1, lsr #8
    cmp ip, #0xA0
    blo draw_1_fallback
    cmp ip, #0xA3
    bhi draw_1_fallback
    and ip, r1, #0xFF
    cmp ip, #0
    beq draw_1_fallback
    sub r1, r1, #0xA000
    sub r1, r1, #1
    b draw_1_index
draw_1_normalized:
    sub r1, r1, #0x8400
    sub r1, r1, #1
draw_1_index:
    mov ip, r1, lsr #8
    sub r1, r1, ip
    KOREAN_BASE r0, ip
    add lr, r0, r1, lsl #6
    b 0x0015E67C
draw_1_fallback:
    bic r1, r1, #0x6000
    b 0x0015E604

.align 2
.global korean_draw_2
korean_draw_2:
    mov r3, sb, lsr #8
    cmp r3, #0x84
    blo draw_2_raw_check
    cmp r3, #0x87
    bhi draw_2_raw_check
    and r3, sb, #0xFF
    cmp r3, #0
    bne draw_2_normalized
draw_2_raw_check:
    mov r3, sb, lsr #8
    cmp r3, #0xA0
    blo draw_2_fallback
    cmp r3, #0xA3
    bhi draw_2_fallback
    and r3, sb, #0xFF
    cmp r3, #0
    beq draw_2_fallback
    sub r1, sb, #0xA000
    sub r1, r1, #1
    b draw_2_index
draw_2_normalized:
    sub r1, sb, #0x8400
    sub r1, r1, #1
draw_2_index:
    mov r3, r1, lsr #8
    sub r1, r1, r3
    KOREAN_BASE r2, r3
    b 0x0015ECD0
draw_2_fallback:
    bic r1, sb, #0x6000
    b 0x0015EC5C

.align 2
.global korean_width_1
korean_width_1:
    mov ip, r0, lsr #8
    cmp ip, #0x84
    blo width_1_raw_check
    cmp ip, #0x87
    bhi width_1_raw_check
    and ip, r0, #0xFF
    cmp ip, #0
    bne width_1_korean
width_1_raw_check:
    mov ip, r0, lsr #8
    cmp ip, #0xA0
    blo width_1_fallback
    cmp ip, #0xA3
    bhi width_1_fallback
    and ip, r0, #0xFF
    cmp ip, #0
    beq width_1_fallback
width_1_korean:
    mov sl, #0x10
    b 0x001843A4
width_1_fallback:
    bic r0, r0, #0x6000
    b 0x0018439C

.align 2
.global korean_width_2
korean_width_2:
    mov ip, r1, lsr #8
    cmp ip, #0x84
    blo width_2_raw_check
    cmp ip, #0x87
    bhi width_2_raw_check
    and ip, r1, #0xFF
    cmp ip, #0
    bne width_2_korean
width_2_raw_check:
    mov ip, r1, lsr #8
    cmp ip, #0xA0
    blo width_2_fallback
    cmp ip, #0xA3
    bhi width_2_fallback
    and ip, r1, #0xFF
    cmp ip, #0
    beq width_2_fallback
width_2_korean:
    mov ip, #0x10
    b 0x00184484
width_2_fallback:
    bic r1, r1, #0x6000
    b 0x00184460

.align 2
.global korean_pre_draw
korean_pre_draw:
    mov r2, r1, lsr #8
    cmp r2, #0xA0
    blo pre_draw_fallback
    cmp r2, #0xA3
    bhi pre_draw_fallback
    and r2, r1, #0xFF
    cmp r2, #0
    bne 0x0015E5A8
pre_draw_fallback:
    bic r1, r1, #0x6000
    b 0x0015E5A8

.align 2
.global korean_layout_classify
korean_layout_classify:
    @ 2026-08-15 fix: this classifier only recognised the legacy 0xA0..0xA3
    @ static range and fell through to the raw bic-mask for every global-page
    @ token (0x84xx..0x87xx), unlike korean_draw_1/2 and korean_width_1/2
    @ which both already check this range first. Confirmed live via GDB
    @ (unconditional breakpoint hits at the fallback, 0x87FAAC) that this
    @ fallback path is reached during normal play; the missing check is what
    @ makes global-page Hangul render as blank glyphs (docs/v0.69-... glyph
    @ report). Mirrors the same range check already proven correct in the
    @ draw/width trampolines above, reusing the existing 0x8101 "is Korean"
    @ sentinel for the match case exactly as the legacy range does.
    mov r0, r1, lsr #8
    cmp r0, #0x84
    blo layout_raw_check
    cmp r0, #0x87
    bhi layout_raw_check
    and r0, r1, #0xFF
    cmp r0, #0
    bne layout_normalized
layout_raw_check:
    mov r0, r1, lsr #8
    cmp r0, #0xA0
    blo layout_fallback
    cmp r0, #0xA3
    bhi layout_fallback
    and r0, r1, #0xFF
    cmp r0, #0
    beq layout_fallback
layout_normalized:
    mov r0, #0x8100
    add r0, r0, #1
    b 0x00183A08
layout_fallback:
    bic r0, r1, #0x6000
    b 0x00183A08

.align 2
korean_desc_literal:
    .word 0x008E1618
korean_table2_literal:
    .word 0x00A46FE0
korean_delta_literal:
    .word 0x00056000
korean_blank_literal:
    .word korean_blank_glyph

@ 128 zero bytes, assembled into the cave so they live in mapped RX .text.
@ Used as the glyph base when no candidate can be vetted; with the index forced
@ to 0 the retail blitter reads a 64-byte all-zero glyph, i.e. draws nothing.
@ 128 rather than 64 so any over-read by the blitter still lands on zeros.
.align 2
korean_blank_glyph:
    .space 128, 0
