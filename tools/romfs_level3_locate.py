#!/usr/bin/env python3
"""Locate a named file's absolute byte offset within a CCI's RomFS partition.

Standalone diagnostic tool: parses NCSD -> NCCH -> IVFC (RomFS) -> Level3
metadata to find where a given file (e.g. codec.dat) sits inside the raw
RomFS partition, as seen by the emulator's FS::File::Read() (offset 0 there
corresponds to the start of the RomFS partition / IVFC magic).

Reference: https://www.3dbrew.org/wiki/NCCH/NCSD, https://www.3dbrew.org/wiki/RomFS
"""
import argparse
import struct
from pathlib import Path

MEDIA_UNIT = 0x200


def read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def read_u64(data: bytes, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


def find_partition0(cci: bytes) -> tuple[int, int]:
    assert cci[0x100:0x104] == b"NCSD", "not an NCSD/CCI image"
    # partition table: 8 entries at 0x120, each {offset:u32, size:u32} in media units
    part_off = read_u32(cci, 0x120) * MEDIA_UNIT
    part_size = read_u32(cci, 0x124) * MEDIA_UNIT
    return part_off, part_size


def find_romfs_partition(cci: bytes, ncch_start: int) -> tuple[int, int]:
    ncch = cci[ncch_start:ncch_start + 0x200]
    assert ncch[0x100:0x104] == b"NCCH", f"no NCCH magic at 0x{ncch_start:X}"
    romfs_off_mu = read_u32(ncch, 0x1B0)
    romfs_size_mu = read_u32(ncch, 0x1B4)
    romfs_abs = ncch_start + romfs_off_mu * MEDIA_UNIT
    romfs_size = romfs_size_mu * MEDIA_UNIT
    return romfs_abs, romfs_size


def parse_ivfc_level3_offset(cci: bytes, romfs_abs: int) -> int:
    ivfc = cci[romfs_abs:romfs_abs + 0x60]
    assert ivfc[0:4] == b"IVFC", f"no IVFC magic at 0x{romfs_abs:X} (found {ivfc[0:4]!r})"
    # Each level entry is 0x18 bytes: Offset(u64) Size(u64) BlockSizeLog2(u32) Reserved(u32).
    # Level1 @ +0x0C, Level2 @ +0x24, Level3 @ +0x3C (empirically confirmed against
    # real header bytes -- the BlockSizeLog2=12 values land exactly at +0x1C/+0x34/+0x4C).
    level3_offset = read_u64(cci, romfs_abs + 0x3C)
    level3_size = read_u64(cci, romfs_abs + 0x44)
    return level3_offset, level3_size


def parse_level3_header(cci: bytes, level3_abs: int) -> dict:
    h = cci[level3_abs:level3_abs + 0x28]
    return {
        "header_len": read_u32(h, 0x00),
        "dir_hash_off": read_u32(h, 0x04),
        "dir_hash_len": read_u32(h, 0x08),
        "dir_meta_off": read_u32(h, 0x0C),
        "dir_meta_len": read_u32(h, 0x10),
        "file_hash_off": read_u32(h, 0x14),
        "file_hash_len": read_u32(h, 0x18),
        "file_meta_off": read_u32(h, 0x1C),
        "file_meta_len": read_u32(h, 0x20),
        "file_data_off": read_u32(h, 0x24),
    }


def scan_file_metadata(cci: bytes, level3_abs: int, hdr: dict, target_name: str):
    """Linear-scan the File Metadata Table for an entry whose name matches
    target_name. Entries are variable-length (0x20-byte fixed part + UTF-16LE
    name, padded to 4 bytes), so we must walk sequentially from the table
    start using each entry's own declared name length -- can't index blindly."""
    base = level3_abs + hdr["file_meta_off"]
    end = base + hdr["file_meta_len"]
    pos = base
    results = []
    while pos + 0x20 <= end:
        parent_dir_off = read_u32(cci, pos + 0x00)
        sibling_off = read_u32(cci, pos + 0x04)
        file_offset = read_u64(cci, pos + 0x08)
        file_size = read_u64(cci, pos + 0x10)
        name_len = read_u32(cci, pos + 0x1C)
        if name_len == 0 or name_len > 0x400:
            # Hit padding/garbage or end of meaningful entries -- stop rather
            # than mis-parse and produce a false match downstream.
            break
        name_bytes = cci[pos + 0x20: pos + 0x20 + name_len]
        try:
            name = name_bytes.decode("utf-16-le")
        except UnicodeDecodeError:
            break
        entry_len = 0x20 + ((name_len + 3) & ~3)
        results.append((name, file_offset, file_size, pos))
        if name.lower() == target_name.lower():
            return name, file_offset, file_size, pos
        pos += entry_len
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cci", type=Path)
    ap.add_argument("filename", help="e.g. codec.dat")
    args = ap.parse_args()

    cci = args.cci.read_bytes()
    part0_off, part0_size = find_partition0(cci)
    print(f"partition0: offset=0x{part0_off:X} size=0x{part0_size:X}")

    romfs_abs, romfs_size = find_romfs_partition(cci, part0_off)
    print(f"romfs partition (relative to file start): offset=0x{romfs_abs:X} size=0x{romfs_size:X}")

    level3_rel_offset, level3_size = parse_ivfc_level3_offset(cci, romfs_abs)
    level3_abs = romfs_abs + level3_rel_offset
    print(f"level3: relative_to_romfs=0x{level3_rel_offset:X} absolute=0x{level3_abs:X} size=0x{level3_size:X}")

    hdr = parse_level3_header(cci, level3_abs)
    print(f"level3 header: {hdr}")

    file_data_abs_in_romfs = level3_rel_offset + hdr["file_data_off"]
    print(f"file_data section start, relative to romfs partition start: 0x{file_data_abs_in_romfs:X}")

    result = scan_file_metadata(cci, level3_abs, hdr, args.filename)
    if result is None:
        print(f"\n'{args.filename}' NOT FOUND in file metadata table")
        return
    name, file_offset, file_size, meta_pos = result
    romfs_relative_offset = file_data_abs_in_romfs + file_offset
    print(f"\nFOUND: {name}")
    print(f"  offset within FileData section: 0x{file_offset:X}")
    print(f"  size: 0x{file_size:X} ({file_size} bytes)")
    print(f"  ABSOLUTE OFFSET relative to RomFS partition start (what File::Read offset= means): 0x{romfs_relative_offset:X}")
    print(f"  (that is: {romfs_relative_offset} decimal)")


if __name__ == "__main__":
    main()
