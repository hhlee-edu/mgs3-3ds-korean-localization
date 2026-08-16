#!/usr/bin/env python3
"""Keep a GDB/MI session attached to Citra and accept local control commands."""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

GDB = r"C:\devkitPro\devkitARM\bin\arm-none-eabi-gdb.exe"
CONTROL_PORT = 24700
GLYPH_PAGE_TABLE = 0x00A46FD8
PAGE0_HIT_BITMAP = 0x00916000
# v0.80 moved the Korean glyph base off the shared font slot table[2] and onto
# the stage text object's own page-2 snapshot. Both are read by `anchor` so a
# single sample says which formula resolves and which does not.
STAGE_TEXT_OBJECT = 0x008E1618      # single-writer global, written at 0x007801C4
OBJ_PAGE2_SNAPSHOT = 0x4C           # [obj+0x4C], the engine's own page-2 pointer
FONT_TABLE2 = 0x00A46FE0            # the pre-v0.80 anchor
KOREAN_PAGE_DELTA = 0x56000
# The proposed anchor: the GCX parser's own live page-2 pointer, which
# 0x0010830C returns as *(0x00A472BC+0xC)+4. Written by the parser at 0x00108488
# on every scenerio.gcx load, and referenced by only three literals in the whole
# image -- so it is neither snapshot-stale nor stealable by the codec.
PARSER_DESC = 0x00A472BC
PARSER_DESC_PAGE2 = 0xC


def send_control(command: str, timeout: float = 3.0) -> int:
    with socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=timeout) as sock:
        sock.sendall(command.encode("utf-8") + b"\n")
        print(sock.recv(4096).decode("utf-8", errors="replace"), end="")
    return 0


def daemon(log_path: Path, trace_glyph_setter: bool = False, watch_addr: str | None = None,
           break_addrs: list[str] | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("w", encoding="utf-8", buffering=1)
    proc = subprocess.Popen(
        [GDB, "--quiet", "--interpreter=mi2"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdin is not None and proc.stdout is not None

    stopped = threading.Event()

    def reader() -> None:
        for line in proc.stdout:
            log.write(line)
            if line.startswith("*stopped"):
                stopped.set()

    threading.Thread(target=reader, daemon=True).start()

    def issue(line: str) -> None:
        log.write(f">>> {line}\n")
        proc.stdin.write(line + "\n")
        proc.stdin.flush()

    issue("-gdb-set pagination off")
    issue("-gdb-set mi-async on")
    issue("-gdb-set target-async on")
    issue("-target-select remote 127.0.0.1:24689")
    time.sleep(1.0)
    if trace_glyph_setter:
        issue("-break-insert *0x0010A894")
    for addr in break_addrs or []:
        # Execution breakpoints must be armed before the initial continue:
        # the boot-time targets fire within the first seconds of guest run.
        issue(f"-break-insert *{addr}")
    if watch_addr:
        # MI's raw -break-watch rejected a C-cast expression here ("Garbage
        # following <expression>", devkitARM gdb 14.1, 2026-08-12). Route
        # through the console command instead, which uses the full CLI
        # expression parser; it still emits a normal *stopped record on hit.
        issue(f'-interpreter-exec console "watch *(unsigned int*){watch_addr}"')
    issue("-exec-continue")

    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", CONTROL_PORT))
        server.listen()
        log.write(f"controller listening on {CONTROL_PORT}\n")
        while proc.poll() is None:
            conn, _ = server.accept()
            with conn:
                command = conn.makefile(encoding="utf-8").readline().strip()
                if command == "interrupt":
                    issue("-exec-interrupt")
                elif command == "snapshot":
                    stopped.clear()
                    issue("-exec-interrupt")
                    if not stopped.wait(timeout=5.0):
                        conn.sendall(b"timed out waiting for guest stop\n")
                        continue
                    issue("-data-list-register-values x")
                    issue('-interpreter-exec console "info registers"')
                    issue('-interpreter-exec console "x/32wx $sp"')
                    issue('-interpreter-exec console "x/24i $pc-32"')
                    issue("-stack-list-frames")
                elif command.startswith("glyph "):
                    # Keep a machine-readable state marker adjacent to the MI
                    # memory response.  The guest must be stopped for memory
                    # reads; interrupting is read-only and does not patch it.
                    state = command[6:].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", state):
                        conn.sendall(b"invalid state label\n")
                        continue
                    stopped.clear()
                    issue(f'-interpreter-exec console "echo GLYPH_DUMP_BEGIN:{state}\\n"')
                    issue("-exec-interrupt")
                    if not stopped.wait(timeout=5.0):
                        conn.sendall(b"timed out waiting for guest stop\n")
                        continue
                    issue(f"-data-read-memory-bytes 0x{GLYPH_PAGE_TABLE:08X} 28")
                    issue(f'-interpreter-exec console "x/7wx 0x{GLYPH_PAGE_TABLE:08X}"')
                    issue(f'-interpreter-exec console "echo GLYPH_DUMP_END:{state}\\n"')
                elif command.startswith("korean-page "):
                    state = command[12:].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", state):
                        conn.sendall(b"invalid state label\n")
                        continue
                    stopped.clear()
                    issue(f'-interpreter-exec console "echo KOREAN_PAGE_BEGIN:{state}\\n"')
                    issue("-exec-interrupt")
                    if not stopped.wait(timeout=5.0):
                        conn.sendall(b"timed out waiting for guest stop\n")
                        continue
                    issue("-data-read-memory-bytes 0x00A46FE0 4")
                    issue('-interpreter-exec console "printf \\"table2=0x%08x korean=0x%08x\\\\n\\", *(unsigned int*)0x00A46FE0, *(unsigned int*)0x00A46FE0 + 0x56000"')
                    # Azahar's GDB stub is reliable at 64 bytes per request;
                    # capture a full 4 KiB as 64 adjacent chunks.
                    for offset in range(0, 4096, 64):
                        issue('-interpreter-exec console '
                              f'"x/64bx (*(unsigned int*)0x00A46FE0+0x56000+0x{offset:X})"')
                    issue(f'-interpreter-exec console "echo KOREAN_PAGE_END:{state}\\n"')
                elif command.startswith("anchor "):
                    # The v0.81 measurement: resolve BOTH glyph-base formulas at
                    # the same instant and dump the first 64 bytes each lands on.
                    # A correct base starts with the 호 glyph, i.e.
                    # korean_page_full.bin[0:64]. All zeros means the old blank
                    # symptom; anything else non-matching means the garbled one.
                    # Read-only, and no breakpoints -- conditional breakpoints
                    # crash this GDB/stub pair, so this deliberately avoids them.
                    state = command[7:].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", state):
                        conn.sendall(b"invalid state label\n")
                        continue
                    stopped.clear()
                    issue(f'-interpreter-exec console "echo ANCHOR_BEGIN:{state}\\n"')
                    issue("-exec-interrupt")
                    if not stopped.wait(timeout=5.0):
                        conn.sendall(b"timed out waiting for guest stop\n")
                        continue
                    issue('-interpreter-exec console '
                          f'"printf \\"obj=0x%08x\\\\n\\", *(unsigned int*)0x{STAGE_TEXT_OBJECT:08X}"')
                    issue('-interpreter-exec console '
                          f'"printf \\"objpage2=0x%08x\\\\n\\", '
                          f'*(unsigned int*)(*(unsigned int*)0x{STAGE_TEXT_OBJECT:08X}+0x{OBJ_PAGE2_SNAPSHOT:X})"')
                    issue('-interpreter-exec console '
                          f'"printf \\"table2=0x%08x\\\\n\\", *(unsigned int*)0x{FONT_TABLE2:08X}"')
                    issue('-interpreter-exec console '
                          f'"printf \\"parserpage2=0x%08x\\\\n\\", '
                          f'*(unsigned int*)(0x{PARSER_DESC:08X}+0x{PARSER_DESC_PAGE2:X})"')
                    issue('-interpreter-exec console '
                          f'"printf \\"base_new=0x%08x base_old=0x%08x base_parser=0x%08x\\\\n\\", '
                          f'*(unsigned int*)(*(unsigned int*)0x{STAGE_TEXT_OBJECT:08X}+0x{OBJ_PAGE2_SNAPSHOT:X})+0x{KOREAN_PAGE_DELTA:X}, '
                          f'*(unsigned int*)0x{FONT_TABLE2:08X}+0x{KOREAN_PAGE_DELTA:X}, '
                          f'*(unsigned int*)(0x{PARSER_DESC:08X}+0x{PARSER_DESC_PAGE2:X})+4+0x{KOREAN_PAGE_DELTA:X}"')
                    issue(f'-interpreter-exec console "echo ANCHOR_PARSER_PAGE\\n"')
                    issue('-interpreter-exec console '
                          f'"x/64bx (*(unsigned int*)(0x{PARSER_DESC:08X}+0x{PARSER_DESC_PAGE2:X})'
                          f'+4+0x{KOREAN_PAGE_DELTA:X})"')
                    issue('-interpreter-exec console '
                          f'"x/64bx (*(unsigned int*)(*(unsigned int*)0x{STAGE_TEXT_OBJECT:08X}'
                          f'+0x{OBJ_PAGE2_SNAPSHOT:X})+0x{KOREAN_PAGE_DELTA:X})"')
                    issue('-interpreter-exec console '
                          f'"x/64bx (*(unsigned int*)0x{FONT_TABLE2:08X}+0x{KOREAN_PAGE_DELTA:X})"')
                    # 추 is global index 93, 션 is 223 -- the two reported glyphs
                    for label, index in (("chu", 93), ("syeon", 223)):
                        issue(f'-interpreter-exec console "echo ANCHOR_GLYPH_{label}\\n"')
                        issue('-interpreter-exec console '
                              f'"x/64bx (*(unsigned int*)(*(unsigned int*)0x{STAGE_TEXT_OBJECT:08X}'
                              f'+0x{OBJ_PAGE2_SNAPSHOT:X})+0x{KOREAN_PAGE_DELTA:X}+{index * 64})"')
                    issue(f'-interpreter-exec console "echo ANCHOR_END:{state}\\n"')
                elif command.startswith("registration "):
                    state = command[13:].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", state):
                        conn.sendall(b"invalid state label\n")
                        continue
                    issue(f'-interpreter-exec console "echo GLYPH_REG_BEGIN:{state}\\n"')
                    issue('-interpreter-exec console "printf \\"r0=0x%08x r1=0x%08x pc=0x%08x lr=0x%08x\\\\n\\", $r0, $r1, $pc, $lr"')
                    issue(f"-data-read-memory-bytes 0x{GLYPH_PAGE_TABLE:08X} 28")
                    issue(f'-interpreter-exec console "echo GLYPH_REG_END:{state}\\n"')
                elif command.startswith("page0-hits "):
                    state = command[11:].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", state):
                        conn.sendall(b"invalid state label\n")
                        continue
                    stopped.clear()
                    issue(f'-interpreter-exec console "echo PAGE0_HITS_BEGIN:{state}\\n"')
                    issue("-exec-interrupt")
                    if not stopped.wait(timeout=5.0):
                        conn.sendall(b"timed out waiting for guest stop\n")
                        continue
                    issue(f"-data-read-memory-bytes 0x{PAGE0_HIT_BITMAP:08X} 1020")
                    issue(f'-interpreter-exec console "echo PAGE0_HITS_END:{state}\\n"')
                elif command == "skip-setter-equivalent":
                    # Diagnostic-only workaround for a devkitARM GDB bug when
                    # resuming from this software breakpoint.  Reproduce the
                    # six-instruction helper's exact observable writes, then
                    # return to LR while leaving the breakpoint installed.
                    issue('-interpreter-exec console "set {unsigned int}(0x00A46FD8 + $r0 * 4) = $r1"')
                    issue('-interpreter-exec console "set {unsigned int}0x00A46FE8 = ($r0 == 2 ? $r1 + 0xFF00 : *(unsigned int*)0x00A46FE8)"')
                    issue('-interpreter-exec console "set $pc = $lr"')
                elif command == "watch-wait":
                    # One-shot wait for a hardware watchpoint hit (set via
                    # --watch at daemon start). Discards any stale stop event
                    # left over from the initial gdbstub halt-on-connect.
                    stopped.clear()
                    if not stopped.wait(timeout=180.0):
                        conn.sendall(b"timed out waiting for watchpoint hit\n")
                        continue
                    issue('-interpreter-exec console "echo WATCH_HIT_BEGIN\\n"')
                    issue('-interpreter-exec console "printf \\"pc=0x%08x lr=0x%08x r0=0x%08x r1=0x%08x r2=0x%08x r3=0x%08x sp=0x%08x\\\\n\\", $pc, $lr, $r0, $r1, $r2, $r3, $sp"')
                    issue('-interpreter-exec console "info registers"')
                    issue('-interpreter-exec console "x/32wx $sp"')
                    issue('-interpreter-exec console "x/24i $pc-32"')
                    issue("-stack-list-frames")
                    issue('-interpreter-exec console "echo WATCH_HIT_END\\n"')
                elif command == "font-context":
                    # Dump the state needed to identify the font resource at
                    # the 0x007801DC breakpoint: r4 is the context object and
                    # [r4,#0x34] is the already-loaded resource buffer.
                    issue('-interpreter-exec console "echo FONT_CTX_BEGIN\\n"')
                    issue("-data-list-register-values x")
                    issue('-interpreter-exec console "printf \\"r4=0x%08x lr=0x%08x pc=0x%08x\\\\n\\", $r4, $lr, $pc"')
                    issue('-interpreter-exec console "x/32wx $r4"')
                    issue('-interpreter-exec console "printf \\"buffer=0x%08x\\\\n\\", *(unsigned int*)($r4+0x34)"')
                    issue('-interpreter-exec console "x/64wx *(unsigned int*)($r4+0x34)"')
                    issue('-interpreter-exec console "x/16wx *(unsigned int*)($r4+0x4c)"')
                    issue("-stack-list-frames")
                    issue('-interpreter-exec console "echo FONT_CTX_END\\n"')
                elif command == "continue":
                    issue("-exec-continue")
                elif command.startswith("mi "):
                    issue(command[3:])
                elif command == "quit":
                    issue("-gdb-exit")
                else:
                    conn.sendall(b"unknown command\n")
                    continue
                conn.sendall(b"ok\n")
    log.close()
    return proc.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--trace-glyph-setter", action="store_true")
    parser.add_argument("--watch", help="hex address for a write watchpoint set before the initial continue")
    parser.add_argument("--break-at", action="append", dest="break_addrs",
                        help="hex address for an execution breakpoint set before the initial continue (repeatable)")
    parser.add_argument("--command")
    parser.add_argument("--command-timeout", type=float, default=3.0)
    parser.add_argument(
        "--log", type=Path, default=Path("logs/citra_gdb_mi.log")
    )
    args = parser.parse_args()
    if args.daemon:
        return daemon(args.log, args.trace_glyph_setter, args.watch, args.break_addrs)
    if args.command:
        return send_control(args.command, args.command_timeout)
    parser.error("use --daemon or --command")


if __name__ == "__main__":
    raise SystemExit(main())
