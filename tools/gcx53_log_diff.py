#!/usr/bin/env python3
"""Parse two instrumented-Azahar codec.dat-read logs (normal vs shift_00c0)
and locate the first point of divergence in the read offset stream.

Reference constants (EN live codec.dat): GCX53 starts at file offset
0x457B0 (284592); shift_00c0 moves it +0xC0 (192) to 0x45870.
"""
import argparse
import re
from dataclasses import dataclass
from pathlib import Path

HEADER_RE = re.compile(r"codec\.dat read\s*$")
OFFSET_RE = re.compile(r"^offset=0x([0-9A-Fa-f]+)\s*$")
SIZE_RE = re.compile(r"^size=0x([0-9A-Fa-f]+)\s*$")
SUBFILE_RE = re.compile(r"^subfile_base=0x([0-9A-Fa-f]+)\s*$")
PC_RE = re.compile(r"^guest_pc=0x([0-9A-Fa-f]+)\s*$")

GCX53_OFFSET = 0x457B0
SHIFT_DELTA = 0xC0
GCX53_REGION_END = 0x48B80  # from project memory's working range


@dataclass
class ReadEvent:
    index: int
    offset: int
    size: int
    subfile_base: int
    guest_pc: int


def parse_log(path: Path) -> list[ReadEvent]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    events: list[ReadEvent] = []
    i = 0
    while i < len(lines):
        if HEADER_RE.search(lines[i]):
            offset = size = subfile_base = pc = None
            j = i + 1
            # tolerate other log lines interleaved between fields (rare, but
            # other subsystems' async log writes could theoretically interleave)
            while j < len(lines) and j < i + 12 and pc is None:
                if (m := OFFSET_RE.match(lines[j])):
                    offset = int(m.group(1), 16)
                elif (m := SIZE_RE.match(lines[j])):
                    size = int(m.group(1), 16)
                elif (m := SUBFILE_RE.match(lines[j])):
                    subfile_base = int(m.group(1), 16)
                elif (m := PC_RE.match(lines[j])):
                    pc = int(m.group(1), 16)
                j += 1
            if offset is not None and size is not None and pc is not None:
                events.append(ReadEvent(len(events), offset, size, subfile_base or 0, pc))
            i = j
        else:
            i += 1
    return events


def report(label: str, events: list[ReadEvent]) -> None:
    pcs = sorted(set(e.guest_pc for e in events))
    print(f"{label}: {len(events)} codec.dat reads, {len(pcs)} distinct guest_pc value(s)")
    for pc in pcs[:10]:
        count = sum(1 for e in events if e.guest_pc == pc)
        print(f"    guest_pc=0x{pc:08X}  (x{count})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("normal_log", type=Path)
    ap.add_argument("shifted_log", type=Path)
    args = ap.parse_args()

    a = parse_log(args.normal_log)
    b = parse_log(args.shifted_log)
    report("Run A (normal)", a)
    report("Run B (shift_00c0)", b)

    if not a or not b:
        print("\nOne or both logs produced zero parsed events -- check the log "
              "actually contains 'codec.dat read' blocks (grep for it directly) "
              "before trusting anything else below.")

    # 1. Index-aligned divergence: same call sequence should request the
    #    same offsets until GCX53's region is touched.
    print("\n-- index-aligned diff --")
    n = min(len(a), len(b))
    first_diff = None
    for i in range(n):
        if a[i].offset != b[i].offset or a[i].size != b[i].size:
            first_diff = i
            break
    if first_diff is None:
        print(f"No index-aligned offset/size divergence found in the overlapping prefix "
              f"({n} reads) -- Run B may have been truncated before reaching GCX53's region "
              "(async log flush on crash), or GCX53 simply isn't touched within the first "
              "codec call.")
    else:
        ea, eb = a[first_diff], b[first_diff]
        delta = eb.offset - ea.offset
        tag = " <-- matches +0xC0 shift" if delta == SHIFT_DELTA else ""
        print(f"First divergence at read index {first_diff}:")
        print(f"  normal : offset=0x{ea.offset:X} size=0x{ea.size:X} guest_pc=0x{ea.guest_pc:08X}")
        print(f"  shifted: offset=0x{eb.offset:X} size=0x{eb.size:X} guest_pc=0x{eb.guest_pc:08X}")
        print(f"  delta = 0x{delta:X} ({delta}){tag}")

    # 2. Direct region match: find reads landing in GCX53's known byte range
    #    in each run independently (works even if the two runs' read *counts*
    #    differ, e.g. Run B crashing mid-stream truncates the sequence).
    print("\n-- direct GCX53-region match --")
    region_len = GCX53_REGION_END - GCX53_OFFSET
    for label, events, base in (
        ("normal", a, GCX53_OFFSET),
        ("shifted", b, GCX53_OFFSET + SHIFT_DELTA),
    ):
        hits = [e for e in events if base <= e.offset < base + region_len]
        print(f"{label}: {len(hits)} read(s) in [0x{base:X}, 0x{base + region_len:X})")
        for e in hits[:5]:
            print(f"    idx={e.index} offset=0x{e.offset:X} size=0x{e.size:X} guest_pc=0x{e.guest_pc:08X}")

    print("\n-- interpretation --")
    print("If guest_pc is the SAME single value across both runs and across nearly all "
          "reads (expected -- this is almost certainly the shared svcSendSyncRequest "
          "trampoline, not resource-specific code), that value is still the correct "
          "GDB breakpoint target for Part 4 -- but plan to break there, then walk up "
          "via $lr/stack to find the actual resource-position-computing caller, rather "
          "than expecting the breakpoint PC itself to be the answer.")


if __name__ == "__main__":
    main()
