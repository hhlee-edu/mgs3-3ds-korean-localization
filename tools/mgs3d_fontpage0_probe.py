#!/usr/bin/env python3
"""Read-only runtime probe of font page table[0] (Option 3 feasibility).

Answers one question and only that question: is the 0xFF00-byte font page that
`*(0x00A46FD8)` points at actually carrying glyph data at runtime, or is it a
free 65,280-byte hole the Korean page could take over?

Nothing here writes guest memory, game data, or build artifacts.  It talks to
the already-running `citra_gdb_mi_controller.py` daemon on its *control* port
(24700) -- never to the gdbstub port (24689), which a bare connect would kill.

Typical use, with the daemon attached and the game past the title screen:

    python tools/mgs3d_fontpage0_probe.py --dump --label title \
        --log logs/gdb-fontpage0-2026-08-15.log

Re-run with a different --label from another screen for a second sample.
Add --registry to also resolve resource id 0x6E383C45 out of the runtime
registry at 0x00A55480 (buffer pointer only; no filename tracing).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import socket
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 24700          # citra_gdb_mi_controller.py control port, NOT 24689

TABLE_VA = 0x00A46FD8         # font page pointer table
EXPECTED_TABLE0 = 0x08688578  # measured 2026-08-15, constant in all 3 samples
PAGE_BYTES = 0xFF00           # one font page
GLYPH_BYTES = 64
SLOTS = PAGE_BYTES // GLYPH_BYTES        # 1020
TABLE0_HEADER_BACK = 0x3080   # table[0] = fontbuf + [fontbuf+4] + 0x3080

REGISTRY_VA = 0x00A55480
FONT_RESOURCE_ID = 0x6E383C45

KOREAN_PAGE = ROOT / "glyph/pages/global_korean_page_v2/korean_page_full.bin"
TOKEN_MAP = ROOT / "experiments/global_korean_page_build_2026-08-12/korean_token_map_full.csv"
DEFAULT_OUT = ROOT / "docs/evidence/2026-08-15-fontpage0-probe"
DEFAULT_LOG = ROOT / "logs/citra_gdb_mi.log"

# Characters whose slots are named in the audit; rendered explicitly in the report.
INTEREST_TOKENS = (0x8401, 0x8421, 0x8422, 0x841D, 0x8490, 0x84D4, 0x8505, 0x865B)

PTR_LO, PTR_HI = 0x08000000, 0x20000000
SHADES = " .+#"


class ProbeError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# token <-> slot index (page 0, xx00 holes compacted out)
# --------------------------------------------------------------------------

def index_to_token(index: int) -> int:
    group, offset = divmod(index, 255)
    return 0x8400 + group * 0x100 + offset + 1


def token_to_index(token: int) -> int:
    raw = token - 0x8401
    return raw - (raw >> 8)


# --------------------------------------------------------------------------
# control-socket / MI-log plumbing
# --------------------------------------------------------------------------

def control(command: str, timeout: float = 5.0) -> str:
    with socket.create_connection((CONTROL_HOST, CONTROL_PORT), timeout=timeout) as sock:
        sock.sendall(command.encode("utf-8") + b"\n")
        try:
            return sock.recv(4096).decode("utf-8", errors="replace")
        except socket.timeout:
            return ""


def mi(raw: str) -> None:
    reply = control(f"mi {raw}")
    if reply.strip() and reply.strip() != "ok":
        raise ProbeError(f"controller rejected {raw!r}: {reply.strip()}")


class Tail:
    """Byte-oriented tail of the daemon's MI log.

    The log is CRLF; read_text() collapses \\r\\n and desynchronises any byte
    offset, so this reads and slices bytes only (2026-08-15 gotcha).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.exists():
            raise ProbeError(f"MI log not found: {path}\n"
                             "Start the daemon with --log pointing at this path.")
        self.capture_start = path.stat().st_size
        self.cursor = self.capture_start

    def _from(self, offset: int) -> bytes:
        with self.path.open("rb") as handle:
            handle.seek(offset)
            return handle.read()

    def wait(self, needle: bytes, timeout: float = 60.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            blob = self._from(self.cursor)
            found = blob.find(needle)
            if found >= 0:
                self.cursor += found + len(needle)
                return True
            time.sleep(0.05)
        return False

    def captured(self) -> str:
        return self._from(self.capture_start).decode("utf-8", errors="replace")


_MARK = 0


def sync(tail: Tail, timeout: float = 120.0) -> None:
    """Round-trip marker: returns once GDB has processed every prior command.

    Matches on the console-stream form (~"TAG) so the daemon's own '>>> ' echo
    of the outgoing command cannot satisfy the wait early.
    """
    global _MARK
    _MARK += 1
    tag = f"FP0SYNC{_MARK}"
    mi(f'-interpreter-exec console "echo {tag}\\n"')
    if not tail.wait(f'~"{tag}'.encode(), timeout=timeout):
        raise ProbeError(f"GDB did not acknowledge marker {tag} within {timeout:.0f}s")


_MEM_RE = re.compile(r'begin="0x([0-9A-Fa-f]+)"[^\n]*?contents="([0-9A-Fa-f]*)"')


def parse_memory(text: str) -> dict[int, bytes]:
    out: dict[int, bytes] = {}
    for addr, payload in _MEM_RE.findall(text):
        try:
            out[int(addr, 16)] = bytes.fromhex(payload)
        except ValueError:
            continue
    return out


def read_block(tail: Tail, addr: int, length: int, chunk: int) -> bytes:
    for offset in range(0, length, chunk):
        size = min(chunk, length - offset)
        mi(f"-data-read-memory-bytes 0x{addr + offset:08X} {size}")
    sync(tail)
    memory = parse_memory(tail.captured())
    parts: list[bytes] = []
    missing: list[str] = []
    for offset in range(0, length, chunk):
        size = min(chunk, length - offset)
        got = memory.get(addr + offset)
        if got is None or len(got) != size:
            missing.append(f"0x{addr + offset:08X}+{size}")
            parts.append(b"\x00" * size)
        else:
            parts.append(got)
    if missing:
        raise ProbeError(f"{len(missing)} unreadable chunk(s), first {missing[0]}; "
                         "target is probably running (memory reads need a stopped guest)")
    return b"".join(parts)


def ensure_stopped(tail: Tail) -> bool:
    control("interrupt")
    return tail.wait(b"*stopped", timeout=8.0)


def pick_chunk(tail: Tail, addr: int, requested: int | None) -> int:
    """Choose a read size, validating a large read against 64-byte ground truth.

    The stub is documented reliable only up to 64 bytes per request.  It does
    NOT always fail loudly above that -- a 1024-byte request can return a
    full-length but WRONG payload, which reads as plausible binary data and
    silently poisons a whole page dump (observed 2026-08-15).  So a large chunk
    is accepted only if it reproduces the same bytes as sixteen 64-byte reads.
    """
    if requested:
        return requested
    big = 1024
    mi(f"-data-read-memory-bytes 0x{addr:08X} {big}")
    # deliberately skip offset 0: parse_memory keys on the begin address, so a
    # 64-byte read at `addr` would overwrite the bulk record under the same key
    for offset in range(64, big, 64):
        mi(f"-data-read-memory-bytes 0x{addr + offset:08X} 64")
    sync(tail)
    memory = parse_memory(tail.captured())
    bulk = memory.get(addr)
    if bulk is None or len(bulk) != big:
        print("[probe] bulk read rejected (short/failed); using 64-byte chunks")
        return 64
    truth = b"".join(memory.get(addr + off, b"") for off in range(64, big, 64))
    if len(truth) != big - 64 or bulk[64:] != truth:
        print("[probe] bulk read DISAGREES with 64-byte reads; using 64-byte chunks")
        return 64
    print("[probe] bulk read verified against 64-byte reads")
    return big


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

def render_slot(data: bytes) -> list[str]:
    rows = []
    for y in range(16):
        line = []
        for x in range(16):
            index = y * 16 + x
            value = (data[index >> 2] >> (6 - (index & 3) * 2)) & 3
            line.append(SHADES[value])
        rows.append("".join(line))
    return rows


def load_token_map() -> dict[int, str]:
    if not TOKEN_MAP.exists():
        return {}
    mapping: dict[int, str] = {}
    with TOKEN_MAP.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            mapping[int(row["index"])] = row["character"]
    return mapping


def census(page: bytes) -> list[dict[str, int]]:
    slots = []
    for index in range(SLOTS):
        raw = page[index * GLYPH_BYTES:(index + 1) * GLYPH_BYTES]
        slots.append({
            "index": index,
            "token": index_to_token(index),
            "nonzero_bytes": sum(1 for byte in raw if byte),
            "set_bits": sum(bin(byte).count("1") for byte in raw),
        })
    return slots


def runs(slots: list[dict[str, int]]) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    start = None
    for slot in slots + [{"index": SLOTS, "nonzero_bytes": 0}]:
        if slot["nonzero_bytes"]:
            if start is None:
                start = slot["index"]
        elif start is not None:
            end = slot["index"] - 1
            result.append({
                "first_index": start, "last_index": end, "count": end - start + 1,
                "first_token": index_to_token(start), "last_token": index_to_token(end),
            })
            start = None
    return result


def analyse(label: str, pointers: list[int], pages: dict[str, bytes],
            extras: dict[str, object], out_dir: Path) -> dict[str, object]:
    page0 = pages["table0"]
    slots = census(page0)
    live = [s for s in slots if s["nonzero_bytes"]]
    korean = KOREAN_PAGE.read_bytes() if KOREAN_PAGE.exists() else b""
    charmap = load_token_map()

    report: dict[str, object] = {
        "label": label,
        "table": {f"table[{i}]": f"0x{p:08X}" for i, p in enumerate(pointers)},
        "table0": f"0x{pointers[0]:08X}",
        "table0_matches_2026_08_15_measurement": pointers[0] == EXPECTED_TABLE0,
        "font_pages_contiguous": {
            "table5_is_table0_plus_0xFF00": len(pointers) > 5 and pointers[5] == pointers[0] + PAGE_BYTES,
            "table6_is_table0_plus_0x1FE00": len(pointers) > 6 and pointers[6] == pointers[0] + 2 * PAGE_BYTES,
        },
        "page_bytes": PAGE_BYTES,
        "slots_total": SLOTS,
        "slots_nonzero": len(live),
        "slots_zero": SLOTS - len(live),
        "nonzero_runs": runs(slots),
        "distinct_slot_values": len({page0[i * GLYPH_BYTES:(i + 1) * GLYPH_BYTES] for i in range(SLOTS)}),
        "page_all_zero": not any(page0),
        "equals_staged_korean_page": bool(korean) and page0 == korean,
        "control_pages": {},
    }
    for name in ("table5", "table6"):
        if name in pages:
            other = pages[name]
            other_live = sum(1 for i in range(len(other) // GLYPH_BYTES)
                             if any(other[i * GLYPH_BYTES:(i + 1) * GLYPH_BYTES]))
            report["control_pages"][name] = {
                "bytes_sampled": len(other),
                "slots_sampled": len(other) // GLYPH_BYTES,
                "slots_nonzero": other_live,
                "equals_table0": other[:len(page0)] == page0[:len(other)],
            }
    report.update(extras)

    lines = [
        f"# font page table[0] probe - label={label}",
        "",
        f"table[0] = 0x{pointers[0]:08X}"
        + ("  (matches the 2026-08-15 measurement)" if pointers[0] == EXPECTED_TABLE0
           else "  (DIFFERENT from the 2026-08-15 measurement 0x08688578)"),
        "  " + "  ".join(f"table[{i}]=0x{p:08X}" for i, p in enumerate(pointers)),
        "",
        f"page span            0x{pointers[0]:08X} .. 0x{pointers[0] + PAGE_BYTES:08X}  "
        f"({PAGE_BYTES} bytes, {SLOTS} slots of {GLYPH_BYTES}B)",
        f"slots with data      {len(live)} / {SLOTS}",
        f"slots all-zero       {SLOTS - len(live)} / {SLOTS}",
        f"distinct slot values {report['distinct_slot_values']}",
        "",
    ]
    if report["nonzero_runs"]:
        lines.append("contiguous non-zero runs (index -> token):")
        for run in report["nonzero_runs"][:40]:
            lines.append(f"  {run['first_index']:4d}-{run['last_index']:4d}  "
                         f"0x{run['first_token']:04X}-0x{run['last_token']:04X}  "
                         f"({run['count']} slots)")
        if len(report["nonzero_runs"]) > 40:
            lines.append(f"  ... {len(report['nonzero_runs']) - 40} more runs")
        lines.append("")

    lines.append("named tokens from the audit:")
    for token in INTEREST_TOKENS:
        index = token_to_index(token)
        slot = slots[index]
        char = charmap.get(index, "?")
        lines.append(f"  0x{token:04X} idx {index:4d}  korean-page char {char}  "
                     f"nonzero_bytes={slot['nonzero_bytes']:2d} set_bits={slot['set_bits']:3d}")
    lines.append("")

    samples = [s["index"] for s in live[:6]] + [token_to_index(t) for t in INTEREST_TOKENS[:2]]
    for index in dict.fromkeys(samples):
        raw = page0[index * GLYPH_BYTES:(index + 1) * GLYPH_BYTES]
        lines.append(f"slot {index} (token 0x{index_to_token(index):04X}, "
                     f"korean-page char {charmap.get(index, '?')}):")
        lines += ["    " + row for row in render_slot(raw)]
        lines.append("")

    for name, info in report["control_pages"].items():
        lines.append(f"control {name}: {info['slots_nonzero']}/{info['slots_sampled']} "
                     f"sampled slots carry data")
    if report["control_pages"]:
        lines.append("")

    if report["page_all_zero"]:
        verdict = ("VERDICT (this sample): table[0]'s page is entirely zero. No glyph data "
                   "would be lost by taking it over.")
    elif len(live) < 16:
        verdict = (f"VERDICT (this sample): only {len(live)} of {SLOTS} slots carry data. "
                   "Taking the page over would destroy exactly those; see the runs above.")
    else:
        verdict = (f"VERDICT (this sample): {len(live)} of {SLOTS} slots carry data -- the page "
                   "is in use. Wholesale replacement would lose those glyphs.")
    lines += [verdict, "",
              "CAVEAT: one sample from one screen. The font buffer is loaded once at boot "
              "(0x00643554) and table[0] never moved across the three 2026-08-15 samples, so a "
              "post-title sample should be representative -- but re-run with a second --label "
              "from a different screen before treating it as settled.",
              "CAVEAT: rendering assumes the Korean page's verified 16x16 2bpp MSB-first "
              "linear-row-major layout. If the retail font page uses a different layout the "
              "zero/non-zero census still holds; only the ASCII art would be wrong."]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"fontpage0-{label}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    text = "\n".join(lines)
    (out_dir / f"fontpage0-{label}.txt").write_text(text, encoding="utf-8")
    print(text)
    return report


# --------------------------------------------------------------------------
# optional: resource registry walk (buffer pointer only, no filename tracing)
# --------------------------------------------------------------------------

def plausible(pointer: int) -> bool:
    return PTR_LO <= pointer < PTR_HI and pointer % 4 == 0


def walk_registry(tail: Tail, chunk: int, table0: int) -> dict[str, object]:
    header = read_block(tail, REGISTRY_VA, 0x80, min(chunk, 0x80))
    words = list(struct.unpack("<32I", header))
    frontier = [w for w in words if plausible(w)]
    seen: set[int] = set()
    nodes: dict[int, tuple[int, int, int, int]] = {}
    depth = 0
    while frontier and depth < 64 and len(nodes) < 4096:
        frontier = [p for p in dict.fromkeys(frontier) if p not in seen]
        if not frontier:
            break
        for pointer in frontier:
            mi(f"-data-read-memory-bytes 0x{pointer:08X} 16")
        sync(tail)
        memory = parse_memory(tail.captured())
        nxt: list[int] = []
        for pointer in frontier:
            seen.add(pointer)
            raw = memory.get(pointer)
            if raw is None or len(raw) != 16:
                continue
            left, right, ident, buffer = struct.unpack("<4I", raw)
            nodes[pointer] = (left, right, ident, buffer)
            nxt += [p for p in (left, right) if plausible(p)]
        frontier = nxt
        depth += 1

    hits = [{"node": f"0x{node:08X}", "id": f"0x{fields[2]:08X}", "buffer": f"0x{fields[3]:08X}"}
            for node, fields in nodes.items()
            if fields[2] == FONT_RESOURCE_ID
            or (fields[2] & 0x7FFFFFFF) == (FONT_RESOURCE_ID & 0x7FFFFFFF)]

    result: dict[str, object] = {
        "registry_header": [f"0x{w:08X}" for w in words],
        "nodes_walked": len(nodes),
        "levels": depth,
        "font_id_hits": hits,
    }
    if hits:
        buffer = int(hits[0]["buffer"], 16)
        head = read_block(tail, buffer, 16, min(chunk, 16))
        skew = struct.unpack("<I", head[4:8])[0]
        result["font_buffer"] = f"0x{buffer:08X}"
        result["font_buffer_header"] = head.hex()
        result["derived_table0"] = f"0x{buffer + skew + TABLE0_HEADER_BACK:08X}"
        result["derivation_matches_table0"] = buffer + skew + TABLE0_HEADER_BACK == table0
    return result


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", action="store_true", help="capture and analyse (needs the daemon)")
    parser.add_argument("--analyze", metavar="LABEL", help="re-analyse an already captured label")
    parser.add_argument("--label", default="sample", help="sample name, e.g. title / codec / ingame")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="daemon MI log path")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--chunk", type=int, help="bytes per memory read (default: probe 1024, fall back to 64)")
    parser.add_argument("--registry", action="store_true",
                        help="also resolve resource id 0x6E383C45 in the registry at 0x00A55480")
    parser.add_argument("--no-control-pages", action="store_true",
                        help="skip the table[5]/table[6] control dumps")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.label):
        parser.error("--label must be [A-Za-z0-9_.-]+")

    if args.analyze:
        out = args.out
        pages = {name: (out / f"fontpage0-{args.analyze}-{name}.bin").read_bytes()
                 for name in ("table0", "table5", "table6")
                 if (out / f"fontpage0-{args.analyze}-{name}.bin").exists()}
        if "table0" not in pages:
            parser.error(f"no captured table0 page for label {args.analyze} in {out}")
        meta = json.loads((out / f"fontpage0-{args.analyze}.json").read_text(encoding="utf-8"))
        pointers = [int(meta["table"][f"table[{i}]"], 16) for i in range(len(meta["table"]))]
        analyse(args.analyze, pointers, pages, {}, out)
        return 0

    if not args.dump:
        parser.error("use --dump or --analyze LABEL")

    tail = Tail(args.log)
    print(f"[probe] control port {CONTROL_PORT}, log {args.log}")
    if not ensure_stopped(tail):
        print("[probe] no *stopped seen after interrupt; continuing anyway "
              "(the guest may already have been halted)")

    table_raw = read_block(tail, TABLE_VA, 28, 28)
    pointers = list(struct.unpack("<7I", table_raw))
    print("[probe] " + "  ".join(f"table[{i}]=0x{p:08X}" for i, p in enumerate(pointers)))
    table0 = pointers[0]
    if table0 == 0:
        raise ProbeError("table[0] is NULL -- the font archive has not loaded yet. "
                         "Let the game reach the title screen and re-run.")
    if table0 != EXPECTED_TABLE0:
        print(f"[probe] NOTE: table[0] is 0x{table0:08X}, not the recorded 0x{EXPECTED_TABLE0:08X}")

    chunk = pick_chunk(tail, table0, args.chunk)
    print(f"[probe] chunk size {chunk} bytes ({-(-PAGE_BYTES // chunk)} reads per page)")

    pages = {"table0": read_block(tail, table0, PAGE_BYTES, chunk)}
    print(f"[probe] table[0] page captured ({len(pages['table0'])} bytes)")

    if not args.no_control_pages:
        for name, base in (("table5", table0 + PAGE_BYTES), ("table6", table0 + 2 * PAGE_BYTES)):
            length = PAGE_BYTES if chunk >= 512 else 64 * GLYPH_BYTES
            pages[name] = read_block(tail, base, length, chunk)
            print(f"[probe] {name} control captured ({len(pages[name])} bytes)")

    extras: dict[str, object] = {
        "font_header_before_table0": read_block(
            tail, table0 - TABLE0_HEADER_BACK, 64, min(chunk, 64)).hex(),
    }
    if args.registry:
        print("[probe] walking the resource registry at 0x00A55480 ...")
        extras["registry"] = walk_registry(tail, chunk, table0)

    control("continue")
    print("[probe] guest resumed")

    args.out.mkdir(parents=True, exist_ok=True)
    for name, blob in pages.items():
        (args.out / f"fontpage0-{args.label}-{name}.bin").write_bytes(blob)
    analyse(args.label, pointers, pages, extras, args.out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
