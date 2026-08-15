#!/usr/bin/env python3
"""Drive an execution-breakpoint trace of set_font_page (0x0010A894).

Read-only observation of the font page table's write path.  Requires the
controller daemon started with --trace-glyph-setter, which arms the breakpoint
before the guest's first instruction.

At every hit it records r0 (page index), r1 (new pointer), lr (caller), pc, the
seven-entry font page table, and a wider window around the table so the table's
real extent and any additional/null slots become visible.  It then issues the
documented `skip-setter-equivalent` workaround (reproduces the helper's two
observable writes and returns to lr, avoiding the devkitARM resume bug) and
continues.

Conditional breakpoints must never be used here -- they kill this GDB/stub pair.

    python tools/mgs3d_setter_trace.py --log logs/setter-trace.log \
        --out docs/evidence/2026-08-15-fontpage0-probe/setter-hits.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from mgs3d_fontpage0_probe import (  # noqa: E402
    Tail, control, mi, parse_memory, ProbeError, TABLE_VA,
)

SETTER_VA = 0x0010A894
# 56 words centred on the table: table[-16] .. table[+39]
WINDOW_VA = 0x00A46F98
WINDOW_LEN = 0xE0

REG_RE = re.compile(r"r0=0x([0-9a-fA-F]+) r1=0x([0-9a-fA-F]+) "
                    r"pc=0x([0-9a-fA-F]+) lr=0x([0-9a-fA-F]+)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", type=Path, required=True, help="daemon MI log")
    parser.add_argument("--out", type=Path, required=True, help="JSONL hit record")
    parser.add_argument("--minutes", type=float, default=25.0)
    parser.add_argument("--max-hits", type=int, default=4000)
    parser.add_argument("--wait", type=float, default=20.0,
                        help="seconds to wait for each next hit before re-polling")
    parser.add_argument("--start-stopped", action="store_true",
                        help="the guest is already halted on a setter hit; process it "
                             "before waiting for the next *stopped")
    args = parser.parse_args()

    tail = Tail(args.log)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sink = args.out.open("w", encoding="utf-8", buffering=1)

    deadline = time.monotonic() + args.minutes * 60
    hit = 0
    idle = 0
    print(f"[trace] watching {args.log} -> {args.out}", flush=True)

    pending = args.start_stopped
    while time.monotonic() < deadline and hit < args.max_hits:
        if pending:
            pending = False
        elif not tail.wait(b"*stopped", timeout=args.wait):
            idle += 1
            print(f"[trace] idle ({idle}), {hit} hits so far", flush=True)
            continue
        idle = 0
        hit += 1
        start = tail.cursor
        tag = f"hit{hit}"
        try:
            mi(f"-data-read-memory-bytes 0x{WINDOW_VA:08X} {WINDOW_LEN}")
            control(f"registration {tag}")
        except (ProbeError, OSError) as error:
            print(f"[trace] control failed at {tag}: {error}", flush=True)
            break
        if not tail.wait(f'~"GLYPH_REG_END:{tag}'.encode(), timeout=30.0):
            print(f"[trace] no GLYPH_REG_END for {tag}; stopping", flush=True)
            break

        text = tail._from(start).decode("utf-8", errors="replace")
        found = REG_RE.search(text)
        memory = parse_memory(text)
        table_raw = memory.get(TABLE_VA, b"")
        window_raw = memory.get(WINDOW_VA, b"")

        record: dict[str, object] = {"hit": hit}
        if found:
            r0, r1, pc, lr = (int(g, 16) for g in found.groups())
            record.update({
                "r0_page_index": r0,
                "r1_new_pointer": f"0x{r1:08X}",
                "pc": f"0x{pc:08X}",
                "lr_caller": f"0x{lr:08X}",
                "at_setter": pc == SETTER_VA,
            })
        if len(table_raw) == 28:
            record["table"] = [f"0x{v:08X}" for v in struct.unpack("<7I", table_raw)]
        if len(window_raw) == WINDOW_LEN:
            words = struct.unpack(f"<{WINDOW_LEN // 4}I", window_raw)
            record["window_base"] = f"0x{WINDOW_VA:08X}"
            record["window"] = [f"0x{v:08X}" for v in words]
        sink.write(json.dumps(record) + "\n")

        if found:
            print(f"[trace] {tag}: r0={record.get('r0_page_index')} "
                  f"r1={record.get('r1_new_pointer')} lr={record.get('lr_caller')}",
                  flush=True)

        try:
            # skip-setter-equivalent writes table[r0] = r1 from live registers.
            # Outside the setter those registers are unrelated values, so it
            # would scribble at an arbitrary offset from the table -- only ever
            # issue it on a confirmed hit at 0x0010A894.
            if record.get("at_setter"):
                control("skip-setter-equivalent")
            control("continue")
        except (ProbeError, OSError) as error:
            print(f"[trace] resume failed at {tag}: {error}", flush=True)
            break

    sink.close()
    print(f"[trace] done: {hit} hits recorded in {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
