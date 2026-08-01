# LA2 / ARC format notes

This document describes the two unrelated archive formats represented by
`.la2` and `.arc` in this workspace. Numeric fields are hexadecimal unless
stated otherwise. The conclusions were checked against 245 LA2 files and 130
ARC files present on 2026-07-31.

## Executive summary

| Extension | Actual format | Compression | Names |
|---|---|---|---|
| `.la2` | Nintendo DARC, version `01000000` | No container compression | Separate UTF-16 string table |
| `.arc` | Capcom MT Framework ARC, version `0010` | Per-file zlib | Inline 64-byte ASCII path |

An extension is only a hint. A parser should identify these formats using the
four-byte magic (`darc` or `ARC\0`).

## LA2 (DARC)

All 245 tested LA2 files have the `darc` magic, little-endian BOM, a 1C-byte
header, and version `01000000`. Offsets stored in file entries are absolute
offsets from the start of the archive.

### Header (1C bytes)

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 00 | 4 | char[4] | `darc` |
| 04 | 2 | u16 | BOM: bytes `FF FE` mean little endian |
| 06 | 2 | u16 | header size, observed `001C` |
| 08 | 4 | u32 | version, observed `01000000` |
| 0C | 4 | u32 | total archive size |
| 10 | 4 | u32 | entry-table offset, observed `001C` |
| 14 | 4 | u32 | table region size: entries plus name strings |
| 18 | 4 | u32 | first data-region offset |

The table region can be followed by alignment padding, so
`table_offset + table_size` may be smaller than `data_offset`.

### Entry table (12 bytes per entry)

The first entry is the root directory. Its third word is therefore also the
total number of entries, including directories and root.

| Relative offset | Size | Meaning |
|---:|---:|---|
| 00 | 4 | bit 24 = directory; low 24 bits = byte offset into name table |
| 04 | 4 | file: absolute data offset; directory: parent entry index |
| 08 | 4 | file: byte size; directory: first entry index after its subtree |

Directory nesting is encoded by table order and the subtree-end index. File
entries do not independently store their parent index.

The tested LA2 files commonly contain a literal `.` directory immediately
below the unnamed DARC root. The extractor normalizes that marker to the output
root.

### String table

The string table begins immediately after all entries:

```text
name_table = table_offset + entry_count * 0x0C
```

Names are NUL-terminated UTF-16 strings in BOM byte order. The low 24 bits of
entry word 0 are byte offsets relative to `name_table`, not character indexes.

### Compression and alignment

DARC itself does not compress its members: `offset,size` selects the member
bytes directly. Tested payload offsets are commonly 80-byte aligned, although
alignment should not be assumed by an extractor. Padding between the table and
data, and between payloads, is not part of a member.

## ARC (MT Framework)

The 130 tested ARC files use little-endian version `0010`. All 1,710 tested
members successfully decompressed as zlib streams and matched their declared
uncompressed sizes. The parser nevertheless supports stored members because
the structure permits them.

### Header (0C bytes)

| Offset | Size | Type | Meaning |
|---:|---:|---|---|
| 00 | 4 | char[4] | `ARC\0` |
| 04 | 2 | u16 | version, observed `0010` |
| 06 | 2 | u16 | entry count |
| 08 | 4 | u32 | reserved, observed zero |

### Entry table (50 bytes per entry)

The table begins at 0C; entry `i` begins at `0C + i * 50`.

| Relative offset | Size | Type | Meaning |
|---:|---:|---|---|
| 00 | 40 | char[64] | NUL-terminated ASCII path, normally using `\` separators |
| 40 | 4 | u32 | resource/type hash; algorithm/name mapping not yet established |
| 44 | 4 | u32 | stored (compressed) byte size |
| 48 | 4 | u32 | low 29 bits: uncompressed size; high 3 bits: flags |
| 4C | 4 | u32 | absolute payload offset |

Observed high-bit flag values are `20000000` and `40000000`. Their semantic
meaning has not been established, so they are preserved in the manifest and
must not be discarded when repacking. The type hash likewise appears to stand
in for a resource extension/type; the extractor records it but does not invent
an extension.

### Strings and compression

ARC has no separate string table. Each entry owns a fixed 40-byte inline ASCII
path field. Payloads begin at their absolute offsets and occupy `stored_size`
bytes. A zlib member normally starts with `78 01`, `78 5E`, `78 9C`, or `78 DA`.
After decompression its length must equal `packed_size & 1FFFFFFF`.

## Extractor

`tools/extract_archives.py` detects either format by magic, validates bounds and
paths, recreates DARC directories, decompresses ARC members, and can emit a
JSON manifest containing offsets, sizes, hashes, and flags.

```powershell
python tools/extract_archives.py partition0/romfs/ui/font.la2 --list
python tools/extract_archives.py partition0/romfs/ui/font.la2 -o out/font --manifest
python tools/extract_archives.py game.arc -o out/arc --manifest
```

The extractor rejects absolute paths and `..` components to prevent archive
path traversal. It does not repack archives.

## Confidence and open questions

High confidence: header sizes, entry boundaries, DARC hierarchy/name-table
location, absolute payload offsets, ARC zlib compression, and all size fields.

Still unresolved: the ARC type-hash algorithm/mapping, the meaning of the ARC
high flag bits, and whether other game builds use non-zlib ARC members. These
unknown fields do not prevent lossless extraction.
