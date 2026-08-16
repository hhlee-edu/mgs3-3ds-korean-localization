from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from citra_gdb_remote import GdbRemote

HEADER_CALL = 0x0014F018
CURSOR_STORE = 0x0016519C
TARGET_TOTAL = 0x00627827


def fields(stop: str) -> dict[int, int]:
    return {
        int(reg, 16): int.from_bytes(bytes.fromhex(value), "little")
        for reg, value in re.findall(r"([0-9a-fA-F]{2}):([0-9a-fA-F]{8})", stop)
    }


def read(remote: GdbRemote, address: int, size: int) -> bytes:
    reply = remote.command(f"m{address:x},{size:x}")
    if reply.startswith("E"):
        raise RuntimeError(reply)
    return bytes.fromhex(reply)


def write_reg(remote: GdbRemote, number: int, value: int) -> None:
    reply = remote.command(f"P{number:x}={value.to_bytes(4, 'little').hex()}")
    if reply != "OK":
        raise RuntimeError(f"P{number:x}: {reply}")


def absolute(obj: tuple[int, ...]) -> int:
    return obj[4] - obj[6] - obj[2] + obj[3]


remote = GdbRemote("127.0.0.1", 24689, timeout=10)
try:
    print("INITIAL", remote.command("?"), flush=True)
    print("BP1", remote.command(f"Z0,{HEADER_CALL:x},4"), flush=True)
    print("BP2", remote.command(f"Z0,{CURSOR_STORE:x},4"), flush=True)
    target_index = 0
    watching_store = False
    while True:
        stop = remote.continue_and_wait()
        regs = fields(stop)
        if 15 not in regs or 13 not in regs:
            raise RuntimeError(f"bad stop: {stop}")
        pc, sp = regs[15], regs[13]
        if pc == HEADER_CALL:
            obj = struct.unpack("<7I", read(remote, sp + 8, 28))
            if obj[4] == TARGET_TOTAL:
                idx = target_index
                target_index += 1
                if idx == 31:
                    print(f"START PC=0x{pc:08X} ABS=0x{absolute(obj):08X} LOCAL=0x{obj[3]:08X}", flush=True)
                    watching_store = True
                elif idx == 32:
                    print(f"NEXT_HEADER PC=0x{pc:08X} ABS=0x{absolute(obj):08X} LOCAL=0x{obj[3]:08X}", flush=True)
                    print("DETACH", remote.command("D"), flush=True)
                    break
            # Emulate BL 0x165110 at 0x14F018.
            write_reg(remote, 14, HEADER_CALL + 4)
            write_reg(remote, 15, 0x00165110)
        elif pc == CURSOR_STORE:
            if watching_store:
                obj_addr = regs[4]
                value = regs[1]
                reply = remote.command(f"M{obj_addr + 0xC:x},4:{value.to_bytes(4, 'little').hex()}")
                if reply != "OK":
                    raise RuntimeError(f"M: {reply}")
                after = struct.unpack("<I", read(remote, obj_addr + 0xC, 4))[0]
                # Absolute base is unchanged by this local-cursor store.
                obj = struct.unpack("<7I", read(remote, obj_addr, 28))
                print(f"AFTER_STORE PC=0x{pc:08X} ABS=0x{absolute(obj):08X} LOCAL=0x{after:08X}", flush=True)
                watching_store = False
            write_reg(remote, 15, CURSOR_STORE + 4)
        else:
            raise RuntimeError(f"unexpected PC 0x{pc:08X}")
finally:
    remote.close()
