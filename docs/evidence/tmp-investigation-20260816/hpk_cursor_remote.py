from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from citra_gdb_remote import GdbRemote


BREAKPOINT = 0x0014F02C


def read_memory(remote: GdbRemote, address: int, size: int) -> bytes:
    reply = remote.command(f"m{address:x},{size:x}")
    if reply.startswith("E"):
        raise RuntimeError(f"memory read failed at 0x{address:08X}: {reply}")
    return bytes.fromhex(reply)


def registers(remote: GdbRemote) -> list[int]:
    raw = bytes.fromhex(remote.command("g"))
    return list(struct.unpack_from("<17I", raw))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--total", type=lambda value: int(value, 0), required=True)
    args = parser.parse_args()

    remote = GdbRemote("127.0.0.1", 24689, timeout=10.0)
    try:
        print(f"LABEL={args.label}")
        print(f"INITIAL={remote.command('?')}")
        print(f"BREAK={remote.command(f'Z1,{BREAKPOINT:x},4')}")
        found = 0
        target_index = 0
        previous_packed = None
        while found < 2:
            stop = remote.continue_and_wait()
            print(f"RAW_STOP={stop}")
            fields = {
                int(reg, 16): int.from_bytes(bytes.fromhex(value), "little")
                for reg, value in re.findall(r"([0-9a-fA-F]{2}):([0-9a-fA-F]{8})", stop)
            }
            sp, pc = fields[13], fields[15]
            if pc != BREAKPOINT:
                raise RuntimeError(f"unexpected stop PC 0x{pc:08X}")
            obj = struct.unpack("<7I", read_memory(remote, sp + 8, 28))
            valid, local, total, remaining = obj[2], obj[3], obj[4], obj[6]
            this_index = target_index if total == args.total else None
            if total == args.total:
                target_index += 1
            if this_index in (31, 32):
                absolute = total - remaining - valid + local
                header = read_memory(remote, sp + 0x15C, 12)
                words = struct.unpack("<3I", header)
                print(
                    f"ENTRY={this_index} ABS=0x{absolute:08X} LOCAL=0x{local:08X} "
                    f"VALID=0x{valid:08X} TOTAL=0x{total:08X} "
                    f"REMAINING=0x{remaining:08X}"
                )
                print(
                    f"HEADER12={header.hex()} WORDS="
                    f"0x{words[0]:08X},0x{words[1]:08X},0x{words[2]:08X}"
                )
                print(
                    "PREVIOUS_PACKED="
                    + ("N/A" if previous_packed is None else f"0x{previous_packed:08X}")
                )
                found += 1
            if total == args.total:
                header = read_memory(remote, sp + 0x15C, 12)
                previous_packed = struct.unpack_from("<I", header, 8)[0]
            # Azahar leaves the translated BKPT cached across a remote single-step.
            # Emulate the replaced ARM instruction at 0x14F02C: ldr r2, [sp,#0x164].
            packed = struct.unpack("<I", read_memory(remote, sp + 0x164, 4))[0]
            remote.command(f'z1,{BREAKPOINT:x},4')
            remote.command(f'P2={packed.to_bytes(4, "little").hex()}')
            remote.command(f'Pf={(BREAKPOINT + 4).to_bytes(4, "little").hex()}')
            if found < 2:
                remote.command(f'Z1,{BREAKPOINT:x},4')
        print(f"DETACH={remote.command('D')}")
    finally:
        remote.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
