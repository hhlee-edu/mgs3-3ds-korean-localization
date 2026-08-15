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
@ If the global is still NULL (early boot, before 0x007801B8 has run) the old
@ table[2] path is used, so this can never be worse than the previous build.
.macro KOREAN_BASE reg, scratch
    ldr \reg, korean_desc_literal
    ldr \reg, [\reg]
    cmp \reg, #0
    ldrne \reg, [\reg, #0x4C]
    ldreq \reg, korean_table2_literal
    ldreq \reg, [\reg]
    ldr \scratch, korean_delta_literal
    add \reg, \reg, \scratch
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
