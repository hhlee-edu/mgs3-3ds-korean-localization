#!/usr/bin/env python3
"""Keep a GDB/MI session attached to Citra and accept local control commands."""

from __future__ import annotations

import argparse
import socket
import subprocess
import threading
import time
from pathlib import Path

GDB = r"C:\devkitPro\devkitARM\bin\arm-none-eabi-gdb.exe"
CONTROL_PORT = 24700


def send_control(command: str) -> int:
    with socket.create_connection(("127.0.0.1", CONTROL_PORT), timeout=3) as sock:
        sock.sendall(command.encode("utf-8") + b"\n")
        print(sock.recv(4096).decode("utf-8", errors="replace"), end="")
    return 0


def daemon(log_path: Path) -> int:
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
    parser.add_argument("--command")
    parser.add_argument(
        "--log", type=Path, default=Path("analysis/citra_gdb_mi.log")
    )
    args = parser.parse_args()
    if args.daemon:
        return daemon(args.log)
    if args.command:
        return send_control(args.command)
    parser.error("use --daemon or --command")


if __name__ == "__main__":
    raise SystemExit(main())
