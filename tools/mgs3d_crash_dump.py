"""Decode a Luma3DS ARM11 exception dump and resolve it against a code image.

Luma writes these to `<sd>/luma/dumps/arm11/crash_dump_NNNNNNNN.dmp`.  Layout:

    u32 magic[2]      0xDEADC0DE, 0xDEADCAFE
    u16 versionMajor, u16 versionMinor
    u32 processor     9 or 11
    u32 exceptionType 0 FIQ, 1 undefined instruction, 2 prefetch abort,
                      3 data abort, 4 debug/other
    u32 totalSize
    u32 registerDumpSize, codeDumpSize, stackDumpSize, additionalDataSize
    ... register dump, code dump, stack dump, additional data (name + title id)

For ARM11 the register dump is 23 words: r0-r12, sp, lr, pc, cpsr, then
dfsr, ifsr, far, then fpexc, fpinst, fpinst2.  The code dump ends *at* pc, so
its last word is the faulting instruction.

With `--code <decompressed .code>` the faulting instruction is located in the
image (confirming build lineage) and the stack is scanned for text pointers.
The MGS3D ARM11 text segment is mapped flat at 0x00100000.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

MAGIC = (0xDEADC0DE, 0xDEADCAFE)
HEADER_WORDS = 10
REG_NAMES = [
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11",
    "r12", "sp", "lr", "pc", "cpsr", "dfsr", "ifsr", "far", "fpexc", "fpinst",
    "fpinst2",
]
EXCEPTION_TYPES = {
    0: "FIQ",
    1: "undefined instruction",
    2: "prefetch abort",
    3: "data abort",
    4: "debug/other",
}
DFSR_FAULTS = {
    0x1: "alignment",
    0x4: "instruction cache maintenance",
    0x5: "translation (section)",
    0x7: "translation (page)",
    0x9: "domain (section)",
    0xB: "domain (page)",
    0xD: "permission (section)",
    0xF: "permission (page)",
}
TEXT_BASE = 0x00100000


def parse(data: bytes) -> dict:
    head = struct.unpack_from("<%dI" % HEADER_WORDS, data, 0)
    if (head[0], head[1]) != MAGIC:
        raise ValueError("not a Luma exception dump")
    version = (head[2] & 0xFFFF, head[2] >> 16)
    processor, etype, total = head[3], head[4], head[5]
    reg_size, code_size, stack_size, extra_size = head[6:10]
    off = HEADER_WORDS * 4
    regs = struct.unpack_from("<%dI" % (reg_size // 4), data, off)
    off += reg_size
    code = data[off:off + code_size]
    off += code_size
    stack = data[off:off + stack_size]
    off += stack_size
    extra = data[off:off + extra_size]
    return {
        "version": version, "processor": processor, "type": etype,
        "total": total, "regs": regs, "code": code, "stack": stack,
        "extra": extra,
    }


def describe_dfsr(dfsr: int) -> str:
    status = (dfsr & 0xF) | ((dfsr >> 6) & 0x10)
    kind = DFSR_FAULTS.get(status & 0xF, "unknown")
    access = "write" if dfsr & (1 << 11) else "read"
    return f"{access}, {kind} fault (status {status:#x})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump", type=Path)
    ap.add_argument("--code", type=Path, help="decompressed .code image to resolve against")
    ap.add_argument("--base", type=lambda s: int(s, 0), default=TEXT_BASE)
    ap.add_argument("--stack", action="store_true", help="dump all stack words")
    args = ap.parse_args()

    info = parse(args.dump.read_bytes())
    regs = info["regs"]
    print(f"{args.dump}")
    print("  Luma dump v%d.%d, processor %d, exception %d (%s)" % (
        info["version"][0], info["version"][1], info["processor"], info["type"],
        EXCEPTION_TYPES.get(info["type"], "?")))
    if len(info["extra"]) >= 16:
        name = info["extra"][:8].split(b"\0")[0].decode("ascii", "replace")
        title = struct.unpack_from("<Q", info["extra"], 8)[0]
        print(f"  process {name}, title {title:016X}")

    print("\n  registers")
    for i in range(0, min(len(regs), len(REG_NAMES))):
        print("    %-8s %08X" % (REG_NAMES[i], regs[i]))
    if len(regs) > 17:
        print("\n  %s" % describe_dfsr(regs[17]))

    pc, sp = regs[15], regs[13]
    code = info["code"]
    start = pc - (len(code) - 4)
    print("\n  code dump %08X..%08X (last word is the faulting instruction)" % (start, pc))
    if args.code:
        image = args.code.read_bytes()
        off = start - args.base
        match = 0 <= off <= len(image) - len(code) and image[off:off + len(code)] == code
        print("    image match at %08X: %s" % (start, "YES" if match else "NO"))
    for i in range(0, len(code), 4):
        word = struct.unpack_from("<I", code, i)[0]
        addr = start + i
        print("    %08X  %08X%s" % (addr, word, "   <== PC" if addr == pc else ""))

    stack = info["stack"]
    print("\n  stack from sp=%08X (%d bytes); words that look like text pointers" % (sp, len(stack)))
    for i in range(0, len(stack) - 3, 4):
        word = struct.unpack_from("<I", stack, i)[0]
        if args.stack or (TEXT_BASE <= word < 0x00900000 and word % 4 == 0):
            print("    sp+%03X (%08X) = %08X" % (i, sp + i, word))
    return 0


if __name__ == "__main__":
    sys.exit(main())
