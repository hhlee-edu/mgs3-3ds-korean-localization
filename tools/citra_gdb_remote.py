#!/usr/bin/env python3
"""Small GDB-remote client for Citra's built-in debugger stub.

This intentionally implements only the packets useful for read-only discovery and
software breakpoint control.  It has no dependency on a system GDB installation.
"""

from __future__ import annotations

import argparse
import socket
import sys


def checksum(payload: bytes) -> bytes:
    return f"{sum(payload) & 0xff:02x}".encode("ascii")


class GdbRemote:
    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        # Citra's stub expects the client's initial ACK before command packets.
        self.sock.sendall(b"+")
        self.initial_stop = None

    def close(self) -> None:
        self.sock.close()

    def _read_byte(self) -> bytes:
        value = self.sock.recv(1)
        if not value:
            raise ConnectionError("Citra closed the GDB connection")
        return value

    def _receive_packet(self, first: bytes | None = None) -> str:
        if first is None:
            first = self._read_byte()
        while first in (b"+", b"-"):
            first = self._read_byte()
        if first != b"$":
            raise RuntimeError(f"unexpected GDB response: {first!r}")
        body = bytearray()
        while True:
            value = self._read_byte()
            if value == b"#":
                break
            if value == b"}":
                body.append(self._read_byte()[0] ^ 0x20)
            else:
                body.extend(value)
        received = self.sock.recv(2)
        if received.lower() != checksum(bytes(body)):
            self.sock.sendall(b"-")
            raise RuntimeError("bad response checksum")
        self.sock.sendall(b"+")
        return body.decode("ascii", errors="replace")

    def command(self, command: str) -> str:
        payload = command.encode("ascii")
        self.sock.sendall(b"$" + payload + b"#" + checksum(payload))
        first = self._read_byte()
        if first == b"-":
            raise RuntimeError("Citra rejected the packet checksum")
        if first == b"+":
            first = self._read_byte()
        return self._receive_packet(first)

    def continue_and_wait(self) -> str:
        """Resume the guest and wait indefinitely for its next stop reply."""
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(None)
        try:
            return self.command("c")
        finally:
            self.sock.settimeout(old_timeout)


def parse_range(value: str) -> tuple[int, int]:
    try:
        address, length = value.split(":", 1)
        return int(address, 0), int(length, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ADDRESS:LENGTH") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=24689)
    parser.add_argument("--status", action="store_true", help="query stop status")
    parser.add_argument("--registers", action="store_true", help="dump raw registers")
    parser.add_argument("--read", type=parse_range, metavar="ADDRESS:LENGTH")
    parser.add_argument("--packet", help="send one raw GDB packet")
    parser.add_argument(
        "--continue-run",
        action="store_true",
        help="continue the guest and keep this connection until it stops",
    )
    args = parser.parse_args()

    if not any((args.status, args.registers, args.read, args.packet, args.continue_run)):
        args.status = True

    try:
        remote = GdbRemote(args.host, args.port)
    except OSError as exc:
        print(f"cannot connect to Citra GDB stub at {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 2
    try:
        if remote.initial_stop is not None:
            print(f"initial stop: {remote.initial_stop}", flush=True)
        if args.status:
            print(f"status: {remote.command('?')}")
        if args.registers:
            print(f"registers: {remote.command('g')}")
        if args.read:
            address, length = args.read
            reply = remote.command(f"m{address:x},{length:x}")
            if reply.startswith("E"):
                print(f"read error: {reply}", file=sys.stderr)
                return 1
            print(bytes.fromhex(reply).hex(" "))
        if args.packet:
            print(remote.command(args.packet))
        if args.continue_run:
            print("guest running; waiting for stop", flush=True)
            print(f"stopped: {remote.continue_and_wait()}")
    finally:
        remote.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
