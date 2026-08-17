#!/usr/bin/env python3
"""Parse a Luma3DS/Rosalina ARM11 exception dump (crash_dump_*.dmp).

Format (little-endian), 40-byte header:
    u32 magic[2]              0xDEADC0DE, 0xDEADCAFE
    u32 versionMinor:16, versionMajor:16
    u32 processor:16, core:16
    u32 type                  0=FIQ 1=undefined instruction 2=prefetch abort 3=data abort
    u32 totalSize
    u32 registerDumpSize      92 for ARM11 userland (23 words)
    u32 codeDumpSize
    u32 stackDumpSize
    u32 additionalDataSize

Register dump (23 words):
    r0..r12, sp, lr, pc, cpsr, dfsr, ifsr, far, fpexc, fpinst, fpinst2

Usage: python parse_luma_crash_dump.py <dump.dmp> [--stack-words N]
"""
import struct
import sys

EXC_TYPES = {0: "FIQ", 1: "undefined instruction", 2: "prefetch abort", 3: "data abort"}

# ARMv6 short-descriptor fault status encodings (DFSR/IFSR status bits [3:0] + bit10)
FSR_NAMES = {
    0x01: "alignment fault",
    0x02: "debug event",
    0x03: "access flag fault, section",
    0x04: "instruction cache maintenance fault",
    0x05: "translation fault, section",
    0x06: "access flag fault, page",
    0x07: "translation fault, page",
    0x08: "synchronous external abort, non-translation",
    0x09: "domain fault, section",
    0x0B: "domain fault, page",
    0x0C: "L1 external abort on translation table walk",
    0x0D: "permission fault, section",
    0x0E: "L2 external abort on translation table walk",
    0x0F: "permission fault, page",
    0x16: "asynchronous external abort",
}

CPSR_MODES = {
    0x10: "User", 0x11: "FIQ", 0x12: "IRQ", 0x13: "Supervisor",
    0x17: "Abort", 0x1B: "Undefined", 0x1F: "System",
}

REG_NAMES = ([f"r{i}" for i in range(13)] +
             ["sp", "lr", "pc", "cpsr", "dfsr", "ifsr", "far", "fpexc", "fpinst", "fpinst2"])

# 3DS userland virtual memory regions, for classifying pointers.
REGIONS = [
    (0x00100000, 0x04000000, "process code/data (.text/.rodata/.data/.bss)"),
    (0x08000000, 0x0C000000, "APPLICATION heap (svcControlMemory)"),
    (0x0C000000, 0x0E000000, "SYSTEM heap"),
    (0x0E000000, 0x10000000, "BASE heap"),
    (0x10000000, 0x14000000, "mapped memory / shared memory"),
    (0x14000000, 0x1C000000, "linear heap (N3DS extended)"),
    (0x1E800000, 0x1F000000, "N3DS extra QTM"),
    (0x1F000000, 0x1F600000, "VRAM"),
    (0x1FF00000, 0x1FF80000, "DSP memory"),
    (0x1FF80000, 0x1FF82000, "shared page / config mem"),
    (0x30000000, 0x40000000, "linear heap (new mapping)"),
]


def classify(addr):
    for lo, hi, name in REGIONS:
        if lo <= addr < hi:
            return name
    return "UNMAPPED / not a standard 3DS userland region"


def main():
    path = sys.argv[1]
    stack_words = 512
    if "--stack-words" in sys.argv:
        stack_words = int(sys.argv[sys.argv.index("--stack-words") + 1])

    with open(path, "rb") as fh:
        blob = fh.read()

    hdr = struct.unpack_from("<10I", blob, 0)
    magic0, magic1, ver, proc, typ, total, reg_sz, code_sz, stack_sz, extra_sz = hdr
    if (magic0, magic1) != (0xDEADC0DE, 0xDEADCAFE):
        sys.exit(f"not a Luma3DS exception dump: magic {magic0:#x} {magic1:#x}")

    print(f"file            : {path}")
    print(f"format version  : {ver & 0xFFFF}.{ver >> 16}")
    print(f"processor       : ARM{proc & 0xFFFF}  core {proc >> 16}")
    print(f"exception type  : {typ} ({EXC_TYPES.get(typ, '?')})")
    print(f"total size      : {total} (file {len(blob)})")
    print(f"sections        : regs={reg_sz} code={code_sz} stack={stack_sz} extra={extra_sz}")
    print()

    off = 40
    regs = list(struct.unpack_from(f"<{reg_sz // 4}I", blob, off))
    off += reg_sz
    code = blob[off:off + code_sz]
    off += code_sz
    stack = blob[off:off + stack_sz]
    off += stack_sz
    extra = blob[off:off + extra_sz]

    print("== registers ==")
    for i, v in enumerate(regs):
        name = REG_NAMES[i] if i < len(REG_NAMES) else f"w{i}"
        note = ""
        if name in ("sp", "lr", "pc", "far") or name.startswith("r"):
            note = "  <- " + classify(v & ~1)
        print(f"  {name:<8} = 0x{v:08x}{note}")
    print()

    cpsr = regs[16]
    mode = CPSR_MODES.get(cpsr & 0x1F, f"?{cpsr & 0x1F:#x}")
    thumb = bool(cpsr & 0x20)
    flags = "".join(c if cpsr & (1 << b) else "-" for c, b in
                    (("N", 31), ("Z", 30), ("C", 29), ("V", 28), ("Q", 27)))
    print(f"cpsr 0x{cpsr:08x}: mode={mode} state={'Thumb' if thumb else 'ARM'} flags={flags} "
          f"IRQ={'off' if cpsr & 0x80 else 'on'} FIQ={'off' if cpsr & 0x40 else 'on'}")

    dfsr, ifsr, far = regs[17], regs[18], regs[19]
    def fsr_decode(v):
        status = (v & 0xF) | ((v >> 6) & 0x10)
        return f"0x{v:08x} status=0x{status:02x} ({FSR_NAMES.get(status, 'unknown')}) " \
               f"domain={(v >> 4) & 0xF} {'write' if v & (1 << 11) else 'read'}"
    print(f"dfsr : {fsr_decode(dfsr)}")
    print(f"ifsr : {fsr_decode(ifsr)}")
    print(f"far  : 0x{far:08x}  <- {classify(far)}")
    print(f"lr   : 0x{regs[14]:08x} ({'Thumb' if regs[14] & 1 else 'ARM'} target 0x{regs[14] & ~1:08x})")
    print()

    # Which register + offset produced FAR?
    print("== FAR correlation (which register is the faulting base?) ==")
    for i, v in enumerate(regs[:16]):
        d = far - v
        if -0x2000 <= d <= 0x2000:
            print(f"  far = {REG_NAMES[i]} + {d:#x}   ({REG_NAMES[i]} = 0x{v:08x})")
    print()

    instr_size = 2 if thumb else 4
    pc = regs[15]
    code_start = pc - (code_sz - instr_size)
    print(f"== code dump ({code_sz} bytes, assumed [0x{code_start:08x} .. 0x{pc:08x}] ending AT pc) ==")
    for i in range(0, len(code), instr_size):
        addr = code_start + i
        word = int.from_bytes(code[i:i + instr_size], "little")
        marker = "  <== PC (faulting instruction)" if addr == pc else ""
        print(f"  0x{addr:08x}: {word:0{instr_size * 2}x}{marker}")
    print()

    print(f"== stack dump ({stack_sz} bytes from sp=0x{regs[13]:08x}) ==")
    print("   showing words that look like code/heap pointers, plus a raw window")
    sp = regs[13]
    words = struct.unpack_from(f"<{len(stack) // 4}I", stack, 0)
    print("   -- candidate return addresses / pointers --")
    for i, w in enumerate(words):
        region = classify(w & ~1)
        if "UNMAPPED" in region:
            continue
        if w < 0x1000:
            continue
        print(f"   [sp+0x{i * 4:04x}] 0x{sp + i * 4:08x} = 0x{w:08x}  {region}"
              f"{' (Thumb)' if w & 1 else ''}")
    print()
    print("   -- raw stack --")
    for i in range(0, min(len(words), stack_words), 4):
        row = " ".join(f"{w:08x}" for w in words[i:i + 4])
        print(f"   0x{sp + i * 4:08x}: {row}")
    print()

    if extra:
        print(f"== additional data ({extra_sz} bytes) ==")
        tag = extra[:8].rstrip(b"\x00").decode("latin1", "replace")
        print(f"  ascii tag : {tag!r}")
        print(f"  raw       : {extra.hex()}")
        if extra_sz == 16:
            pid, = struct.unpack_from("<I", extra, 8)
            print(f"  (Luma layout: process name {extra[:8].rstrip(chr(0).encode()).decode('latin1')!r}, "
                  f"pid/tid-lo 0x{pid:08x}, tail 0x{struct.unpack_from('<I', extra, 12)[0]:08x})")


if __name__ == "__main__":
    main()
