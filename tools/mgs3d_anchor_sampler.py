#!/usr/bin/env python3
"""Sample the three Korean glyph-base anchors on a timer, so nobody has to hit a
two-second subtitle by hand.

The `anchor` control command takes one sample and leaves the guest stopped, which
means catching a cutscene subtitle depends on typing fast enough. This instead
drives the already-attached daemon through its raw `mi` passthrough:

    interrupt -> read the three candidate bases -> continue

every `--interval` seconds, forever, so the player just plays. Each sample is
self-identifying: during a cutscene the anchors move, so the interesting samples
stand out without anyone having to mark them.

Anchors (see docs/global-page-anchor-final-structure-2026-08-16.md):

    base_old    = *(0x00A46FE0) + 0x56000                  table[2], pre-v0.80
    base_new    = *(*(0x008E1618)+0x4C) + 0x56000          obj snapshot, current
    base_parser = *(0x00A472BC+0xC) + 4 + 0x56000          GCX parser, proposed

For each it dumps 16 bytes at +0x0C, where the resident page is distinctive
(`0fffff f0 00000000 006ff900 02900680`); the first 12 bytes of the page are
zeros and cannot tell a good pointer from a zeroed one.

Requires the daemon from `citra_gdb_mi_controller.py --daemon` to be attached.
Read the results out of that daemon's own --log file.

    python tools/mgs3d_anchor_sampler.py --interval 4
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

CONTROL_PORT = 24700
STAGE_TEXT_OBJECT = 0x008E1618
OBJ_PAGE2_SNAPSHOT = 0x4C
FONT_TABLE2 = 0x00A46FE0
PARSER_DESC = 0x00A472BC
PARSER_DESC_PAGE2 = 0xC
DELTA = 0x56000

OBJ = f"*(unsigned int*)0x{STAGE_TEXT_OBJECT:08X}"
BASE_NEW = f"(*(unsigned int*)({OBJ}+0x{OBJ_PAGE2_SNAPSHOT:X})+0x{DELTA:X})"
BASE_OLD = f"(*(unsigned int*)0x{FONT_TABLE2:08X}+0x{DELTA:X})"
BASE_PAR = f"(*(unsigned int*)(0x{PARSER_DESC:08X}+0x{PARSER_DESC_PAGE2:X})+4+0x{DELTA:X})"


def send(command: str, timeout: float = 5.0) -> str:
    with socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=timeout) as sock:
        sock.sendall(command.encode("utf-8") + b"\n")
        try:
            return sock.recv(4096).decode("utf-8", errors="replace")
        except socket.timeout:
            return ""


def console(expr: str) -> str:
    """Wrap a gdb console command for the daemon's raw `mi ` passthrough."""
    return 'mi -interpreter-exec console "' + expr.replace('"', '\\"') + '"'


def sample(index: int) -> None:
    send(f'mi -interpreter-exec console "echo SAMPLE_BEGIN:{index}\\n"')
    send("mi -exec-interrupt")
    time.sleep(0.5)                       # let the stop record land
    send(console(f'printf "S{index} obj=0x%08x t2=0x%08x par=0x%08x\\n", '
                 f'{OBJ}, *(unsigned int*)0x{FONT_TABLE2:08X}, '
                 f'*(unsigned int*)(0x{PARSER_DESC:08X}+0x{PARSER_DESC_PAGE2:X})'))
    # One printf per anchor. Combining them loses every value when the stage text
    # object is still NULL (boot/menus), because base_new dereferences it and the
    # whole statement aborts.
    for label, expr in (("new", BASE_NEW), ("old", BASE_OLD), ("par", BASE_PAR)):
        send(console(f'printf "S{index} base_{label}=0x%08x\\n", {expr}'))
        send(console(f'echo S{index} {label}=\\n'))
        send(console(f"x/16bx ({expr}+0x0C)"))
    send(f'mi -interpreter-exec console "echo SAMPLE_END:{index}\\n"')
    send("continue")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--interval", type=float, default=4.0)
    ap.add_argument("--count", type=int, default=0, help="0 = run until stopped")
    args = ap.parse_args()

    try:
        send("mi -gdb-set pagination off")
    except OSError as exc:
        print(f"cannot reach the daemon on {CONTROL_PORT}: {exc}", file=sys.stderr)
        print("is `citra_gdb_mi_controller.py --daemon` still attached?", file=sys.stderr)
        return 1

    index = 0
    while args.count == 0 or index < args.count:
        index += 1
        try:
            sample(index)
        except OSError as exc:
            print(f"sample {index}: daemon unreachable ({exc}) -- stopping", file=sys.stderr)
            return 1
        print(f"sample {index} taken", flush=True)
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
