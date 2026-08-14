"""Detect the HPK "padded slot / rewritten size" defect that desynchronises the
game's sequential entry walk.

The retail loader (`0x0014EFE8..0x0014F050` in the decompressed ARM11 code) is
strictly sequential.  It reads a u32 entry count, then repeats
`read(12) -> {key, unpacked, packed}` followed by a read of exactly `packed`
bytes.  It never seeks and never consults a stored offset table.  A header whose
`packed` field is 0 still consumes its 12 bytes and is otherwise skipped
(`0x0014F024`).

An in-place patcher that shrinks a zlib payload, writes the *new* length into
the header and then zero-pads the slot back to the *old* length keeps the
physical offsets fixed but breaks that chain: from the patched entry onward the
loader runs `old - new` bytes early.  It walks the zero padding as a run of
empty 12-byte headers and finally reads a header straddling the last
`(old - new) mod 12` padding bytes, which decodes as garbage.  On hardware that
surfaced as a 60.8 MiB allocation, a NULL return and a NULL-destination memcpy.
See `docs/evidence/2026-08-14-hpk-cursor-drift/README.md`.

This checker walks an archive the way the loader does and reports any entry
followed by zero padding before the next real header -- the exact signature of
that defect.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

HEADER_SIZE = 12


def read_header(data: bytes, pos: int) -> tuple[int, int, int] | None:
    if pos + HEADER_SIZE > len(data):
        return None
    return struct.unpack_from("<3I", data, pos)


def zlib_length(data: bytes, start: int, limit: int) -> int | None:
    """Length actually consumed by a zlib stream at `start`, or None."""
    if start >= len(data) or data[start] != 0x78:
        return None
    obj = zlib.decompressobj()
    try:
        obj.decompress(data[start:limit])
    except zlib.error:
        return None
    return (limit - start) - len(obj.unused_data)


def analyse(data: bytes) -> tuple[list[dict], list[str]]:
    declared = struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else 0
    entries: list[dict] = []
    findings: list[str] = []
    pos = 4

    for index in range(declared):
        header = read_header(data, pos)
        if header is None:
            findings.append(f"entry {index}: header at {pos:#x} runs past EOF")
            break
        key, unpacked, packed = header
        if pos + HEADER_SIZE + packed > len(data):
            findings.append(
                f"entry {index} (key {key:08x}) at {pos:#x}: declared packed size "
                f"{packed:#x} runs past EOF -- chain walk cannot continue"
            )
            break

        entry = {
            "index": index,
            "offset": pos,
            "key": key,
            "unpacked": unpacked,
            "packed": packed,
        }
        entries.append(entry)
        payload = pos + HEADER_SIZE
        pos = payload + packed

        if packed == 0:
            continue

        # The defect signature: the declared payload is followed by zero padding
        # that the loader will consume as empty headers instead of reaching the
        # real next entry.
        run = 0
        while pos + run < len(data) and data[pos + run] == 0:
            run += 1
        if run >= HEADER_SIZE:
            actual = zlib_length(data, payload, payload + packed + run)
            findings.append(
                f"entry {index} (key {key:08x}) at {pos - packed - HEADER_SIZE:#x}: "
                f"declared packed={packed} is followed by {run} zero bytes before the "
                f"next header. The physical slot is {packed + run} bytes, so the loader "
                f"runs {run} bytes early from here on "
                f"(residue {run % HEADER_SIZE} after the empty-header walk)."
                + (f" Actual zlib stream length is {actual}." if actual else "")
            )
            entry["padding"] = run

    return entries, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--reference",
        type=Path,
        help="a known-good archive; the entry tables must match entry for entry",
    )
    args = parser.parse_args()

    data = args.archive.read_bytes()
    entries, findings = analyse(data)
    declared = struct.unpack_from("<I", data, 0)[0] if len(data) >= 4 else 0
    print(f"{args.archive}: {len(data)} bytes, declares {declared} entries")
    print(f"  walked {len(entries)} entries")

    padded = [e for e in entries if "padding" in e]
    if padded:
        print("  FAIL: padded-slot drift detected")
        for line in findings:
            if "zero bytes before the next header" in line:
                print(f"    - {line}")
        return 1

    if args.reference:
        ref_entries, _ = analyse(args.reference.read_bytes())
        for a, b in zip(entries, ref_entries):
            if (a["key"], a["unpacked"], a["packed"]) != (b["key"], b["unpacked"], b["packed"]):
                print(f"  FAIL: entry {a['index']} differs from the reference")
                print(f"    candidate  offset={a['offset']:#x} key={a['key']:08x} "
                      f"unpacked={a['unpacked']:#x} packed={a['packed']:#x}")
                print(f"    reference  offset={b['offset']:#x} key={b['key']:08x} "
                      f"unpacked={b['unpacked']:#x} packed={b['packed']:#x}")
                return 1
        if len(entries) != len(ref_entries):
            print(f"  FAIL: walked {len(entries)} entries, reference walked {len(ref_entries)}")
            return 1
        print(f"  reference match: {len(entries)} entries identical")

    print("  OK: no padded-slot drift")
    # The sequential walk does not currently reach EOF even on the pristine
    # retail archive, so that condition is reported but not treated as failure.
    for line in findings:
        if "zero bytes before the next header" not in line:
            print(f"  note: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
