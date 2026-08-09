#!/usr/bin/env python3
"""Targeted Capstone scan of code.bin for a reference to GCX53's absolute
position in codec.dat.

Bounded, targeted scan -- NOT a general disassembler and NOT blind
full-binary reversing. docs/session-handoff-2026-08-08.md already
concluded that blind static analysis of code.bin without symbols isn't
tractable; the recommended next step there was Citra dynamic debugging.
This tool respects that conclusion: every subcommand is scoped to
candidate values derived from GCX51-55's real codec.dat offsets, and the
acceptance rule (see `report`) requires a candidate to connect to 2+ of
those GCX, not a single coincidental number match. If nothing survives
that filter, the answer is "targeted static scan inconclusive" -- the
investigation should move to dynamic debugging, not a deeper static dig.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nintendo_blz import decompress  # noqa: E402
from mgs3d_codec_tool import parse_codec  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "_vendor"))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB  # noqa: E402


class ScanError(ValueError):
    pass


CODE_BIN = Path("C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/exefs/code.bin")
EXHEADER = Path("C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/exheader.bin")
CODEC_DAT = Path("C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/codec.dat")
EXPECTED_SHA256 = "10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7"
OUT_DIR = Path("analysis/ps2_korean/full_build/rebuild_2026-08-08")
MANIFEST_PATH = OUT_DIR / "gcx_ref_scan_manifest.json"
IMAGE_PATH = OUT_DIR / "code_en_decompressed_verified.bin"
GCX_RANGE = range(51, 56)
ASSET_STRINGS = [b"gcx", b"raw", b"nav", b"slot", b"rom:", b"vox.dat", b"movie", b"bgm", b"stage"]


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ScanError(f"read outside file at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        raise ScanError("no manifest found -- run `prepare` first")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_image() -> bytes:
    if not IMAGE_PATH.exists():
        raise ScanError("no verified decompressed image found -- run `prepare` first")
    return IMAGE_PATH.read_bytes()


def file_offset_to_va(manifest: dict, file_offset: int) -> int | None:
    for seg in manifest["segments"].values():
        start = seg["file_start"]
        if start <= file_offset < start + seg["file_span"]:
            return seg["va"] + (file_offset - start)
    return None


def gcx_candidates() -> list[dict]:
    """GCX51-55's real absolute offsets in the live codec.dat, plus scaled
    variants matching the project's known alignment conventions."""
    records = parse_codec(CODEC_DAT.read_bytes())
    out = []
    for index in GCX_RANGE:
        record = records[index]
        offset = record.source_offset
        size = len(record.raw)
        out.append({"gcx": index, "field": "abs_offset", "value": offset})
        out.append({"gcx": index, "field": "abs_end", "value": offset + size})
        out.append({"gcx": index, "field": "offset_div10", "value": offset // 0x10})
        out.append({"gcx": index, "field": "offset_div20", "value": offset // 0x20})
        out.append({"gcx": index, "field": "offset_div800", "value": offset // 0x800})
        out.append({"gcx": index, "field": "size", "value": size})
    return out


def command_prepare(args: argparse.Namespace) -> None:
    compressed = CODE_BIN.read_bytes()
    image = decompress(compressed)
    digest = hashlib.sha256(image).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ScanError(
            f"decompressed code.bin hash mismatch: got {digest}, expected {EXPECTED_SHA256} "
            "-- live code.bin changed since this scan was designed; stop and re-verify "
            "before trusting any candidate this tool produces"
        )
    exheader = EXHEADER.read_bytes()
    text_addr, text_pages, text_size = struct.unpack_from("<III", exheader, 0x10)
    ro_addr, ro_pages, ro_size = struct.unpack_from("<III", exheader, 0x20)
    data_addr, data_pages, data_size = struct.unpack_from("<III", exheader, 0x30)
    text_file_start = 0
    text_file_span = text_pages * 0x1000
    ro_file_start = text_file_span
    ro_file_span = ro_pages * 0x1000
    data_file_start = ro_file_start + ro_file_span
    data_file_span = data_pages * 0x1000
    segments = {
        "text": {"va": text_addr, "size": text_size, "file_start": text_file_start, "file_span": text_file_span},
        "rodata": {"va": ro_addr, "size": ro_size, "file_start": ro_file_start, "file_span": ro_file_span},
        "data": {"va": data_addr, "size": data_size, "file_start": data_file_start, "file_span": data_file_span},
    }
    computed_total = data_file_start + data_file_span
    if computed_total != len(image):
        raise ScanError(
            f"segment page-math ({computed_total}) does not match decompressed image size "
            f"({len(image)}) -- VA map is wrong, fix before trusting any hit"
        )
    manifest = {
        "format": "mgs3d-code-gcx-ref-scan-manifest-v1",
        "code_bin_source": str(CODE_BIN),
        "decompressed_size": len(image),
        "decompressed_sha256": digest,
        "segments": segments,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    IMAGE_PATH.write_bytes(image)
    print(f"decompressed OK, sha256 verified. wrote {IMAGE_PATH.name} and {MANIFEST_PATH.name}")
    for name, seg in segments.items():
        print(f"  {name}: va=0x{seg['va']:x} file=0x{seg['file_start']:x}..0x{seg['file_start']+seg['file_span']:x}")


def command_gcx_candidates(args: argparse.Namespace) -> None:
    candidates = gcx_candidates()
    out_path = OUT_DIR / "gcx_ref_scan_candidates.json"
    out_path.write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    print(f"{len(candidates)} candidate values ({len(GCX_RANGE)} GCX x 6 fields) -> {out_path}")
    for row in candidates:
        if row["field"] == "abs_offset":
            print(f"  GCX{row['gcx']}: 0x{row['value']:x} ({row['value']})")


def command_scan_constants(args: argparse.Namespace) -> None:
    image = load_image()
    candidates = gcx_candidates()
    wanted: dict[int, list[dict]] = defaultdict(list)
    for row in candidates:
        wanted[row["value"]].append(row)
    print(f"indexing {len(image)} bytes (word-aligned)...")
    positions: dict[int, list[int]] = defaultdict(list)
    for off in range(0, len(image) - 3, 4):
        value = struct.unpack_from("<I", image, off)[0]
        if value in wanted:
            positions[value].append(off)
    hits = []
    manifest = load_manifest()
    for value, meta in wanted.items():
        for off in positions.get(value, []):
            va = file_offset_to_va(manifest, off)
            for row in meta:
                hits.append({"file_offset": off, "va": va, "value": value, **row})
    out_path = OUT_DIR / "gcx_ref_scan_constants.json"
    out_path.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    print(f"scan-constants: {len(hits)} hits -> {out_path}")
    for h in hits[:30]:
        print(f"  GCX{h['gcx']} {h['field']}=0x{h['value']:x} @ file 0x{h['file_offset']:x} va={h['va']}")


def _decode_one(md: Cs, chunk: bytes, addr: int):
    for insn in md.disasm(chunk, addr, count=1):
        return insn
    return None


def command_scan_movw_movt(args: argparse.Namespace) -> None:
    image = load_image()
    manifest = load_manifest()
    text_seg = manifest["segments"]["text"]
    text = image[text_seg["file_start"]: text_seg["file_start"] + text_seg["size"]]
    base_va = text_seg["va"]

    candidates = gcx_candidates()
    wanted_values = {row["value"] for row in candidates}
    by_value: dict[int, list[dict]] = defaultdict(list)
    for row in candidates:
        by_value[row["value"]].append(row)

    hits = []
    for mode_name, mode, stride in [("thumb", CS_MODE_THUMB, 2), ("arm", CS_MODE_ARM, 4)]:
        md = Cs(CS_ARCH_ARM, mode)
        md.detail = True
        for off in range(0, len(text) - 8, stride):
            addr = base_va + off
            insn = _decode_one(md, text[off:off + 8], addr)
            if insn is None or insn.mnemonic != "movw":
                continue
            movw_reg = insn.reg_name(insn.operands[0].reg)
            movw_imm = insn.operands[1].imm
            next_off = off + insn.size
            next_insn = _decode_one(md, text[next_off:next_off + 8], base_va + next_off)
            if next_insn is None or next_insn.mnemonic != "movt":
                continue
            if next_insn.reg_name(next_insn.operands[0].reg) != movw_reg:
                continue
            movt_imm = next_insn.operands[1].imm
            combined = (movt_imm << 16) | movw_imm
            if combined in wanted_values:
                for row in by_value[combined]:
                    hits.append({
                        "mode": mode_name, "movw_file_offset": off, "movw_va": addr,
                        "movt_file_offset": next_off, "reg": movw_reg, "value": combined,
                        **row,
                    })
    out_path = OUT_DIR / "gcx_ref_scan_movw_movt.json"
    out_path.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    print(f"scan-movw-movt: {len(hits)} hits -> {out_path}")
    for h in hits[:30]:
        print(f"  [{h['mode']}] GCX{h['gcx']} {h['field']}=0x{h['value']:x} "
              f"movw@0x{h['movw_file_offset']:x} movt@0x{h['movt_file_offset']:x} reg={h['reg']}")


def command_scan_tables(args: argparse.Namespace) -> None:
    image = load_image()
    manifest = load_manifest()
    ro_seg = manifest["segments"]["rodata"]
    rodata = image[ro_seg["file_start"]: ro_seg["file_start"] + ro_seg["size"]]

    records = parse_codec(CODEC_DAT.read_bytes())
    target_offsets = [records[i].source_offset for i in GCX_RANGE]
    target_ends = [records[i].source_offset + len(records[i].raw) for i in GCX_RANGE]

    hits = []
    for label, targets in [("start_offsets", target_offsets), ("end_offsets", target_ends)]:
        n = len(targets)
        for off in range(0, len(rodata) - n * 4, 4):
            words = [struct.unpack_from("<I", rodata, off + i * 4)[0] for i in range(n)]
            if words == targets:
                hits.append({"pattern": label, "direction": "forward", "file_offset": ro_seg["file_start"] + off})
            if words == list(reversed(targets)):
                hits.append({"pattern": label, "direction": "reversed", "file_offset": ro_seg["file_start"] + off})
            # fixed linear transform: words[i] - words[0] == targets[i] - targets[0]
            if words[0] != 0:
                deltas = [w - words[0] for w in words]
                target_deltas = [t - targets[0] for t in targets]
                if deltas == target_deltas:
                    hits.append({
                        "pattern": label, "direction": "linear_offset",
                        "file_offset": ro_seg["file_start"] + off, "base_delta": words[0] - targets[0],
                    })
    out_path = OUT_DIR / "gcx_ref_scan_tables.json"
    out_path.write_text(json.dumps(hits, indent=2), encoding="utf-8")
    print(f"scan-tables: {len(hits)} hits (rodata only, {len(rodata)} bytes) -> {out_path}")
    for h in hits:
        print(f"  {h}")


def command_find_loader(args: argparse.Namespace) -> None:
    image = load_image()
    manifest = load_manifest()
    string_hits = []
    for s in ASSET_STRINGS:
        start = 0
        while True:
            idx = image.find(s, start)
            if idx < 0:
                break
            va = file_offset_to_va(manifest, idx)
            string_hits.append({"string": s.decode(), "file_offset": idx, "va": va})
            start = idx + 1
    out_path = OUT_DIR / "gcx_ref_scan_strings.json"
    out_path.write_text(json.dumps(string_hits, indent=2), encoding="utf-8")
    print(f"find-loader: {len(string_hits)} asset-type string hits -> {out_path}")
    for h in string_hits[:40]:
        print(f"  {h['string']!r} @ file 0x{h['file_offset']:x} va={h['va']}")

    # xref backtrace: for each string hit with a resolved VA, search .text
    # for MOVW/MOVT pairs or literal-pool words constructing that VA.
    text_seg = manifest["segments"]["text"]
    text = image[text_seg["file_start"]: text_seg["file_start"] + text_seg["size"]]
    base_va = text_seg["va"]
    target_vas = {h["va"] for h in string_hits if h["va"] is not None}

    literal_hits = []
    for off in range(0, len(text) - 3, 4):
        value = struct.unpack_from("<I", text, off)[0]
        if value in target_vas:
            literal_hits.append({"kind": "literal_pool", "file_offset": text_seg["file_start"] + off, "va": value})

    xref_out = OUT_DIR / "gcx_ref_scan_loader_xrefs.json"
    xref_out.write_text(json.dumps(literal_hits, indent=2), encoding="utf-8")
    print(f"find-loader xrefs: {len(literal_hits)} literal-pool references to asset-string VAs -> {xref_out}")
    for h in literal_hits[:30]:
        print(f"  {h}")


def _disasm_window(image: bytes, manifest: dict, file_offset: int, mode: int, context: int = 10):
    text_seg = manifest["segments"]["text"]
    md = Cs(CS_ARCH_ARM, mode)
    stride = 2 if mode == CS_MODE_THUMB else 4
    lo = max(text_seg["file_start"], file_offset - context * 4)
    hi = min(text_seg["file_start"] + text_seg["size"], file_offset + context * 4)
    va = text_seg["va"] + (lo - text_seg["file_start"])
    lines = []
    for insn in md.disasm(image[lo:hi], va):
        marker = ">" if insn.address == text_seg["va"] + (file_offset - text_seg["file_start"]) else " "
        lines.append(f"{marker} 0x{insn.address:x}: {insn.mnemonic} {insn.op_str}")
    return lines


def command_report(args: argparse.Namespace) -> None:
    image = load_image()
    manifest = load_manifest()

    def load(name):
        p = OUT_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    constants = load("gcx_ref_scan_constants.json")
    movw_movt = load("gcx_ref_scan_movw_movt.json")
    tables = load("gcx_ref_scan_tables.json")

    # Group all GCX-tagged hits by (file_offset) so we can see which
    # candidate positions touch 2+ distinct GCX from GCX51-55.
    by_position: dict[int, set[int]] = defaultdict(set)
    detail: dict[int, list[dict]] = defaultdict(list)
    for h in constants:
        by_position[h["file_offset"]].add(h["gcx"])
        detail[h["file_offset"]].append({"source": "scan-constants", **h})
    for h in movw_movt:
        by_position[h["movw_file_offset"]].add(h["gcx"])
        detail[h["movw_file_offset"]].append({"source": "scan-movw-movt", **h})

    survivors = []
    for pos, gcx_set in by_position.items():
        if len(gcx_set) >= 2:
            survivors.append((pos, gcx_set))

    report = {
        "format": "mgs3d-code-gcx-ref-scan-report-v1",
        "acceptance_rule": "candidate must connect to 2+ of GCX51-55, not a single value match",
        "table_hits": tables,
        "survivors": [],
        "verdict": None,
    }

    if not survivors and not tables:
        report["verdict"] = "targeted static scan inconclusive"
        print("VERDICT: targeted static scan inconclusive")
        print("No candidate connects to 2+ of GCX51-55, and no table pattern found in .rodata.")
        print("Per plan: do not expand to deeper static analysis. Next step is Citra dynamic")
        print("debugging (watchpoint GCX53's byte range, diff normal vs shift_00c0 execution).")
    else:
        for pos, gcx_set in sorted(survivors, key=lambda kv: -len(kv[1])):
            entry = {
                "file_offset": pos,
                "gcx_connected": sorted(gcx_set),
                "evidence": detail[pos],
            }
            for mode_name, mode in [("thumb", 2), ("arm", 4)]:
                try:
                    window = _disasm_window(image, manifest, pos, mode)
                    if window:
                        entry[f"disasm_{mode_name}"] = window
                except Exception:
                    pass
            report["survivors"].append(entry)
        report["verdict"] = f"{len(survivors)} candidate(s) connect to 2+ of GCX51-55"
        print(f"VERDICT: {report['verdict']}")
        for entry in report["survivors"]:
            print(f"\n== file offset 0x{entry['file_offset']:x}, GCX {entry['gcx_connected']} ==")
            for line in entry.get("disasm_thumb", [])[:20]:
                print("  [thumb]", line)

    out_path = OUT_DIR / "gcx_ref_scan_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nfull report -> {out_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="decompress+verify code.bin, derive VA map")
    p.set_defaults(function=command_prepare)

    p = sub.add_parser("gcx-candidates", help="dump GCX51-55 candidate values")
    p.set_defaults(function=command_gcx_candidates)

    p = sub.add_parser("scan-constants", help="raw 32-bit LE constant search")
    p.set_defaults(function=command_scan_constants)

    p = sub.add_parser("scan-movw-movt", help="Thumb/ARM MOVW+MOVT reconstructed-constant search")
    p.set_defaults(function=command_scan_movw_movt)

    p = sub.add_parser("scan-tables", help="rodata consecutive offset-table search")
    p.set_defaults(function=command_scan_tables)

    p = sub.add_parser("find-loader", help="asset-type string table + literal-pool xref search")
    p.set_defaults(function=command_find_loader)

    p = sub.add_parser("report", help="apply strict acceptance filter, render disasm windows")
    p.set_defaults(function=command_report)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.function(args)
    except (ScanError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
