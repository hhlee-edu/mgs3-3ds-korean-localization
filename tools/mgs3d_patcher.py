#!/usr/bin/env python3
"""MGS3D standalone patcher — inspect and build standalone Korean CCI images.

Reads the user's own game dump and says whether it is an input this patcher
supports.  **Nothing is written, decrypted, or modified**; every file is opened
read-only.

    python tools/mgs3d_patcher.py inspect <base.cci|.3ds>
    python tools/mgs3d_patcher.py inspect <base.cci|.3ds> --update <update.cia>

Identity rules come from `docs/patcher-design.md` §3:

  * the container must be **decrypted** (NCCH NoCrypto flag). Encrypted dumps are
    rejected with a clear message -- no keys ship with this tool
  * version is decided by the **BLZ-decompressed** `.code` SHA-256, never by the
    compressed one (BLZ recompression is not deterministic)
  * `originals/3ds_pristine` is *not* a baseline -- it is a different title
    (37 MB codec.dat vs our 67 MB). Its hashes appear nowhere here

Track selection follows the confirmed UX (design §6.3):

    base only                 -> 1.0 Korean build, no CPP
    base + official 1.1 CIA   -> 1.1 Korean build, with CPP

Exit codes: 0 supported, 2 not supported (build must not run), 1 usage/IO error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nintendo_blz import decompress  # noqa: E402
from mgs3d_delta import apply as apply_delta, sha256_path  # noqa: E402
from mgs3d_cpp_default_patch import (  # noqa: E402
    compress as compress_code,
    detect as detect_cpp,
    patch_image as apply_cpp,
    slot_state as cpp_slot_state,
)

MEDIA_UNIT = 0x200

BASE_TITLE_ID = 0x0004000000081E00
UPDATE_TITLE_ID = 0x0004000E00081E00
BASE_PRODUCT_CODE = "CTR-P-AMGE"
UPDATE_PRODUCT_CODE = "CTR-U-AMGE"

# BLZ-decompressed .code images. Measured, see docs/patcher-design.md §3.2.
CODE_BASELINES = {
    "10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7": ("1.0", 8_478_720),
    "68bdf9c5e2436dcb0b752bc7e74b375fa1bff38201412627eb744d24d1f63962": ("1.1", 8_744_960),
}

REGIONS = {
    "E": "North America",
    "J": "Japan",
    "P": "Europe",
    "K": "Korea",
    "C": "China",
    "T": "Taiwan",
}

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
THREEDSTOOL = ROOT / "experiments/repack_tools/3dstool/3dstool.exe"
PAYLOAD = ROOT / "payload/standalone"
GLYPH10_SHA = "4dbe3791040cbe4fdcbb7a61eb1ebbd5aed7cccf63fc0ae92d5061369fba8945"
GLYPH11_SHA = "db815f8043d75da06f17377e42cdac1369ab33ce0d932ee54b73be83e43416dd"
PATCHED11_SHA = "26ec9cc5d7b6fe757fd62e10a51e6ebf1deceee2061d12802c06cfc30065c28d"
EXHEADER10_SHA = "2bca5dcbae0167221ac09007003be57bbc8ce2e83fa41f6d86f90f9a37c754d7"
EXHEADER11_SHA = "a2d369ddcbf300be10075731c1354f600a5b7f389586abd328d2531e30662a36"
PLAIN10_SHA = "3d758611bc5b4c4a8e5f5129074b3c390fac28d043ac1aeaa855738280a6abf0"
PLAIN11_SHA = "ce8978119aa6f4da89ceefdc39a03aa46d7182cbb26fa113abe76a056f7db2eb"


class InspectError(Exception):
    """Something made the input unreadable as a 3DS container."""


@dataclass
class Ncch:
    offset: int
    program_id: int
    product_code: str
    no_crypto: bool
    fixed_key: bool
    crypto_method: int
    exheader_offset: int
    exheader_size: int
    exefs_offset: int
    exefs_size: int
    romfs_offset: int
    romfs_size: int


@dataclass
class Report:
    base_ok: bool = False
    base_version: str | None = None
    base_title_id: int | None = None
    base_product_code: str | None = None
    base_code_sha: str | None = None
    base_code_size: int | None = None
    update_present: bool = False
    update_ok: bool = False
    update_version: str | None = None
    update_title_id: int | None = None
    update_code_sha: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def supported(self) -> bool:
        return self.base_ok and (not self.update_present or self.update_ok) and not self.reasons

    @property
    def region(self) -> str | None:
        if not self.base_product_code:
            return None
        letter = self.base_product_code[-1]
        return REGIONS.get(letter, f"Unknown ({letter})")

    @property
    def track(self) -> str:
        if not self.supported:
            return "-"
        return "1.1 + CPP" if self.update_present else "1.0 without CPP"


def read_ncch(handle, offset: int) -> Ncch:
    handle.seek(offset)
    head = handle.read(0x200)
    if len(head) < 0x200 or head[0x100:0x104] != b"NCCH":
        raise InspectError(f"no NCCH header at {offset:#x}")
    flags = head[0x188:0x190]
    exefs_off, exefs_size = struct.unpack_from("<II", head, 0x1A0)
    romfs_off, romfs_size = struct.unpack_from("<II", head, 0x1B0)
    return Ncch(
        offset=offset,
        program_id=struct.unpack_from("<Q", head, 0x118)[0],
        product_code=head[0x150:0x160].split(b"\0")[0].decode("latin1"),
        no_crypto=bool(flags[7] & 0x04),
        fixed_key=bool(flags[7] & 0x01),
        crypto_method=flags[3],
        exheader_offset=offset + 0x200,
        exheader_size=struct.unpack_from("<I", head, 0x180)[0],
        exefs_offset=offset + exefs_off * MEDIA_UNIT,
        exefs_size=exefs_size * MEDIA_UNIT,
        romfs_offset=offset + romfs_off * MEDIA_UNIT,
        romfs_size=romfs_size * MEDIA_UNIT,
    )


def ncsd_partition0(handle) -> int:
    handle.seek(0)
    head = handle.read(0x200)
    if len(head) < 0x200 or head[0x100:0x104] != b"NCSD":
        raise InspectError("not an NCSD/CCI image (no 'NCSD' magic at 0x100)")
    offset, size = struct.unpack_from("<II", head, 0x120)
    if not size:
        raise InspectError("CCI has no partition 0")
    return offset * MEDIA_UNIT


def cia_first_content(handle) -> int:
    handle.seek(0)
    head = handle.read(0x20)
    if len(head) < 0x20:
        raise InspectError("file is too small to be a CIA")
    header_size, _type, _version, cert_size, ticket_size, tmd_size, _meta = struct.unpack_from(
        "<IHHIIII", head, 0
    )
    if header_size != 0x2020:
        raise InspectError(f"not a CIA (header size {header_size:#x}, expected 0x2020)")

    def align(value: int, boundary: int = 0x40) -> int:
        return (value + boundary - 1) // boundary * boundary

    offset = align(header_size)
    offset = align(offset + cert_size)
    offset = align(offset + ticket_size)
    return align(offset + tmd_size)


def exheader_code_is_compressed(handle, ncch: Ncch) -> bool:
    handle.seek(ncch.exheader_offset + 0x0D)
    flags = handle.read(1)
    if not flags:
        raise InspectError("exheader is unreadable")
    return bool(flags[0] & 0x01)


def read_exefs_code(handle, ncch: Ncch) -> bytes:
    if not ncch.exefs_size:
        raise InspectError("NCCH has no ExeFS")
    handle.seek(ncch.exefs_offset)
    header = handle.read(0x200)
    if len(header) < 0x200:
        raise InspectError("ExeFS header is truncated")
    for index in range(8):
        entry = header[index * 0x10: (index + 1) * 0x10]
        name = entry[:8].split(b"\0")[0].decode("latin1")
        if name != ".code":
            continue
        offset, size = struct.unpack_from("<II", entry, 8)
        handle.seek(ncch.exefs_offset + 0x200 + offset)
        data = handle.read(size)
        if len(data) != size:
            raise InspectError(".code is truncated")
        return data
    raise InspectError("ExeFS has no '.code' entry")


def code_identity(handle, ncch: Ncch) -> tuple[str, int, str | None]:
    """Return (sha256, size, version) of the decompressed .code."""
    packed = read_exefs_code(handle, ncch)
    data = decompress(packed) if exheader_code_is_compressed(handle, ncch) else packed
    digest = hashlib.sha256(data).hexdigest()
    known = CODE_BASELINES.get(digest)
    return digest, len(data), known[0] if known else None


def check_decrypted(ncch: Ncch, label: str, reasons: list[str]) -> bool:
    if ncch.no_crypto:
        return True
    reasons.append(
        f"{label} is encrypted (NCCH crypto method {ncch.crypto_method:#04x}"
        f"{', fixed key' if ncch.fixed_key else ''}). This patcher ships no keys and "
        "does not decrypt. Supply a decrypted dump."
    )
    return False


def inspect_base(path: Path, report: Report) -> None:
    with open(path, "rb") as handle:
        ncch = read_ncch(handle, ncsd_partition0(handle))
        report.base_title_id = ncch.program_id
        report.base_product_code = ncch.product_code
        if not check_decrypted(ncch, "Base game", report.reasons):
            return
        if ncch.program_id != BASE_TITLE_ID:
            report.reasons.append(
                f"Base title ID is {ncch.program_id:016X}, expected {BASE_TITLE_ID:016X}"
            )
        if ncch.product_code != BASE_PRODUCT_CODE:
            report.reasons.append(
                f"Base product code is {ncch.product_code}, expected {BASE_PRODUCT_CODE}"
            )
        digest, size, version = code_identity(handle, ncch)
        report.base_code_sha, report.base_code_size, report.base_version = digest, size, version
        if version is None:
            report.reasons.append(
                f"Base code is not a supported build: decompressed SHA-256 {digest} "
                f"({size:,} B) matches no known image"
            )
        elif version != "1.0":
            report.reasons.append(
                f"Base code is {version}; the base dump must be the unpatched 1.0 image"
            )
    report.base_ok = not report.reasons


def inspect_update(path: Path, report: Report) -> None:
    report.update_present = True
    with open(path, "rb") as handle:
        suffix = path.suffix.lower()
        offset = cia_first_content(handle) if suffix == ".cia" else 0
        ncch = read_ncch(handle, offset)
        report.update_title_id = ncch.program_id
        if not check_decrypted(ncch, "Update", report.reasons):
            return
        if ncch.program_id != UPDATE_TITLE_ID:
            report.reasons.append(
                f"Update title ID is {ncch.program_id:016X}, expected {UPDATE_TITLE_ID:016X}"
            )
        if ncch.product_code != UPDATE_PRODUCT_CODE:
            report.reasons.append(
                f"Update product code is {ncch.product_code}, expected {UPDATE_PRODUCT_CODE}"
            )
        digest, size, version = code_identity(handle, ncch)
        report.update_code_sha, report.update_version = digest, version
        if version != "1.1":
            report.reasons.append(
                f"Update code is not the official 1.1 image: decompressed SHA-256 {digest} "
                f"({size:,} B)"
            )
    report.update_ok = not report.reasons


def render(report: Report, verbose: bool) -> str:
    lines = [
        f"Base game : {'OK' if report.base_ok else 'FAILED'}",
        f"Region    : {report.region or '-'}",
        f"Title ID  : {report.base_title_id:016X}" if report.base_title_id else "Title ID  : -",
        f"Update    : {report.update_version or 'Unrecognised'}"
        if report.update_present
        else "Update    : Not supplied",
        f"Track     : {report.track}",
        f"Result    : {'Supported' if report.supported else 'Not supported'}",
    ]
    for index, reason in enumerate(report.reasons):
        lines.append(f"{'Reason    : ' if index == 0 else '            '}{reason}")
    if verbose:
        lines.append("")
        lines.append(f"base code sha256   : {report.base_code_sha} ({report.base_code_size:,} B)"
                     if report.base_code_sha else "base code sha256   : -")
        if report.update_present:
            lines.append(f"update code sha256 : {report.update_code_sha}")
    return "\n".join(lines)


def command_inspect(args: argparse.Namespace) -> int:
    report = Report()
    try:
        inspect_base(args.base, report)
        if args.update is not None:
            inspect_update(args.update, report)
    except InspectError as exc:
        report.reasons.append(str(exc))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render(report, args.verbose))
    return 0 if report.supported else 2


def run_tool(*args: str | Path) -> None:
    command = [str(THREEDSTOOL), *(str(x) for x in args)]
    print("tool       : " + " ".join(command[1:4]) + (" ..." if len(command) > 4 else ""))
    # 3dstool looks for ignore_3dstool.txt next to its own exe using the
    # *current working directory*, not the exe's own path.  Without cwd=
    # here it inherits whatever directory the patcher was launched from and
    # fails to open it (harmless -- it only affects file skip lists -- but
    # prints a scary "cannot open" line on every invocation).
    subprocess.run(command, check=True, cwd=THREEDSTOOL.parent)


def unpack_cci(cci: Path, dest: Path, *, romfs_dir: bool = True) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths = {name: dest / name for name in (
        "p0.cxi", "p1.cfa", "p7.cfa", "ncsdheader.bin", "ncchheader.bin",
        "exh.bin", "plain.bin", "exefs.bin", "romfs.bin", "exefsheader.bin")}
    run_tool("-xvt017f", "cci", paths["p0.cxi"], paths["p1.cfa"], paths["p7.cfa"],
             cci, "--header", paths["ncsdheader.bin"])
    run_tool("-xvtf", "cxi", paths["p0.cxi"], "--header", paths["ncchheader.bin"],
             "--exh", paths["exh.bin"], "--plain", paths["plain.bin"],
             "--exefs", paths["exefs.bin"], "--romfs", paths["romfs.bin"])
    exefs = dest / "exefs"
    run_tool("-xvtf", "exefs", paths["exefs.bin"], "--header", paths["exefsheader.bin"],
             "--exefs-dir", exefs)
    if romfs_dir:
        run_tool("-xvtf", "romfs", paths["romfs.bin"], "--romfs-dir", dest / "romfs")
    paths["exefs"] = exefs
    paths["romfs"] = dest / "romfs"
    return paths


def load_payload_manifest() -> dict:
    path = PAYLOAD / "manifest.json"
    if not path.is_file():
        raise RuntimeError(f"standalone payload is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def replace_with_delta(source: Path, delta_name: str, scratch: Path) -> dict:
    scratch.parent.mkdir(parents=True, exist_ok=True)
    meta = apply_delta(source, PAYLOAD / delta_name, scratch)
    source.unlink()
    scratch.replace(source)
    return meta


def verify_romfs_tree(root: Path, manifest: dict, *, target: bool) -> list[str]:
    expected = manifest["romfs"]
    actual = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))[:5]
        extra = sorted(set(actual) - set(expected))[:5]
        raise RuntimeError(f"RomFS file set mismatch: missing={missing}, extra={extra}")
    key = "target_sha256" if target else "source_sha256"
    size_key = "target_size" if target else "source_size"
    bad = []
    for rel, entry in expected.items():
        path = actual[rel]
        if path.stat().st_size != entry[size_key] or sha256_path(path) != entry[key]:
            bad.append(rel)
    if bad:
        raise RuntimeError(f"RomFS verification failed for {len(bad)} files: {bad[:5]}")
    return [f"RomFS {len(actual)}/{len(expected)} byte-identical"]


def patch_code_and_meta(track: str, tree: dict[str, Path], work: Path) -> tuple[str, str]:
    packed = tree["exefs"] / ".code.bin"
    if not packed.is_file():
        packed = tree["exefs"] / "code.bin"
    if not packed.is_file():
        raise RuntimeError("re-unpacked ExeFS has no code.bin/.code.bin")
    raw = work / "code.clean.raw"
    raw.write_bytes(decompress(packed.read_bytes()))
    if sha256_path(raw) != next(k for k, v in CODE_BASELINES.items() if v[0] == "1.0"):
        raise RuntimeError("unpacked code no longer matches clean 1.0")
    if track == "1.0":
        replace_with_delta(raw, "code/1.0-glyph.m3dxd", work / "code.next.raw")
        replace_with_delta(tree["exh.bin"], "meta/1.0-exheader.m3dxd", work / "exh.next")
        expected_code, expected_exh, expected_plain = GLYPH10_SHA, EXHEADER10_SHA, PLAIN10_SHA
    else:
        replace_with_delta(raw, "code/1.0-to-1.1.m3dxd", work / "code.next.raw")
        if sha256_path(raw) != next(k for k, v in CODE_BASELINES.items() if v[0] == "1.1"):
            raise RuntimeError("1.0→1.1 code delta did not reproduce official 1.1")
        replace_with_delta(tree["exh.bin"], "meta/1.0-to-1.1-exheader.m3dxd", work / "exh.next")
        replace_with_delta(tree["plain.bin"], "meta/1.0-to-1.1-plain.m3dxd", work / "plain.next")
        if sha256_path(tree["exh.bin"]) != EXHEADER11_SHA or sha256_path(tree["plain.bin"]) != PLAIN11_SHA:
            raise RuntimeError("official 1.1 exheader/plain reconstruction hash mismatch")
        print("official 1.1: code/exheader/plain SHA-256 verified")
        replace_with_delta(raw, "code/1.1-glyph.m3dxd", work / "code.next.raw")
        version, profile = detect_cpp(raw.read_bytes())
        if version != "1.1" or cpp_slot_state(raw.read_bytes(), profile)[1] != "unpatched":
            raise RuntimeError("1.1 glyph image is not CPP-off before CPP stage")
        patched, changed = apply_cpp(raw.read_bytes(), profile)
        if not changed:
            raise RuntimeError("CPP patch was not applied to 1.1")
        raw.write_bytes(patched)
        expected_code, expected_exh, expected_plain = PATCHED11_SHA, EXHEADER11_SHA, PLAIN11_SHA
    if sha256_path(raw) != expected_code:
        raise RuntimeError(f"{track} final decompressed code hash mismatch")
    version, profile = detect_cpp(raw.read_bytes())
    state = cpp_slot_state(raw.read_bytes(), profile)[1]
    wanted = "unpatched" if track == "1.0" else "already patched"
    if state != wanted:
        raise RuntimeError(f"{track} CPP state is {state}, expected {wanted}")
    if sha256_path(tree["exh.bin"]) != expected_exh or sha256_path(tree["plain.bin"]) != expected_plain:
        raise RuntimeError(f"{track} exheader/plain verification failed")
    packed.write_bytes(compress_code(raw.read_bytes(), work / "compress"))
    if sha256_path(raw) != hashlib.sha256(decompress(packed.read_bytes())).hexdigest():
        raise RuntimeError("compressed code round-trip mismatch")
    return expected_code, state


def command_build(args: argparse.Namespace) -> int:
    progress = getattr(args, "progress", None)

    def stage(percent: int, message: str) -> None:
        print(f"stage      : {percent:3d}% {message}")
        if progress is not None:
            progress(percent, message)

    print("WARNING: remove /luma/titles/0004000000081E00/ (or disable Luma game patching).")
    print("         Leftover LayeredFS/code patches will double-patch this CCI and can crash it.")
    report = Report()
    try:
        stage(2, "원본 CCI 확인")
        inspect_base(args.base, report)
        if not report.supported:
            print(render(report, True))
            return 2
        if not THREEDSTOOL.is_file():
            raise RuntimeError(f"3dstool is missing: {THREEDSTOOL}")
        manifest = load_payload_manifest()
        work = args.workdir.resolve()
        if work.exists() and any(work.iterdir()):
            raise RuntimeError(f"workdir must be new or empty: {work}")
        work.mkdir(parents=True, exist_ok=True)
        stage(8, "원본 CCI 구조 풀기")
        source = unpack_cci(args.base.resolve(), work / "source")
        stage(30, "원본 RomFS 무결성 확인")
        checks = verify_romfs_tree(source["romfs"], manifest, target=False)
        stage(43, "한국어 데이터 패치 적용")
        for rel, entry in manifest["romfs"].items():
            if "delta" in entry:
                path = source["romfs"] / Path(rel)
                replace_with_delta(path, entry["delta"], work / "scratch" / Path(rel))
        stage(54, "패치된 RomFS 무결성 확인")
        checks += verify_romfs_tree(source["romfs"], manifest, target=True)
        stage(62, f"{args.track} 실행 코드 패치 및 검증")
        code_sha, cpp_state = patch_code_and_meta(args.track, source, work)
        new = work / "new"; new.mkdir()
        exefs_bin, romfs_bin, p0 = new / "exefs.bin", new / "romfs.bin", new / "p0.cxi"
        stage(69, "ExeFS 다시 만들기")
        run_tool("-cvtf", "exefs", exefs_bin, "--header", source["exefsheader.bin"],
                 "--exefs-dir", source["exefs"])
        stage(74, "RomFS 다시 만들기 (가장 오래 걸릴 수 있음)")
        run_tool("-cvtf", "romfs", romfs_bin, "--romfs-dir", source["romfs"])
        stage(84, "게임 파티션 다시 만들기")
        run_tool("-cvtf", "cxi", p0, "--header", source["ncchheader.bin"],
                 "--exh", source["exh.bin"], "--plain", source["plain.bin"],
                 "--exefs", exefs_bin, "--romfs", romfs_bin, "--not-encrypt")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        stage(89, "최종 CCI 조립")
        run_tool("-cvt017f", "cci", p0, source["p1.cfa"], source["p7.cfa"], args.out.resolve(),
                 "--header", source["ncsdheader.bin"], "--not-pad")
        stage(94, "완성 CCI 재검증")
        # The patched tree was already checked file-by-file above.  During final
        # verification, compare the RomFS image carried by the output CCI with
        # the exact image we built.  This proves the repack preserved it without
        # extracting and hashing the entire multi-gigabyte tree a second time.
        verify = unpack_cci(args.out.resolve(), work / "verify", romfs_dir=False)
        if sha256_path(verify["romfs.bin"]) != sha256_path(romfs_bin):
            raise RuntimeError("re-unpacked RomFS image verification failed")
        checks.append("RomFS image byte-identical after repack")
        verify_code = verify["exefs"] / ".code.bin"
        if not verify_code.is_file():
            verify_code = verify["exefs"] / "code.bin"
        final_raw = decompress(verify_code.read_bytes())
        if hashlib.sha256(final_raw).hexdigest() != code_sha:
            raise RuntimeError("re-unpacked ExeFS/code verification failed")
        if sha256_path(verify["exh.bin"]) != sha256_path(source["exh.bin"]):
            raise RuntimeError("re-unpacked exheader verification failed")
        if sha256_path(verify["plain.bin"]) != sha256_path(source["plain.bin"]):
            raise RuntimeError("re-unpacked plain verification failed")
        if sha256_path(verify["p1.cfa"]) != sha256_path(source["p1.cfa"]) or sha256_path(verify["p7.cfa"]) != sha256_path(source["p7.cfa"]):
            raise RuntimeError("partition 1/7 changed during repack")
        out_report = Report(); inspect_base(args.out.resolve(), out_report)
        if out_report.base_title_id != BASE_TITLE_ID or out_report.base_product_code != BASE_PRODUCT_CODE:
            raise RuntimeError("output NCSD/NCCH identity verification failed")
        result = {"track": args.track, "output": str(args.out.resolve()), "size": args.out.stat().st_size,
                  "sha256": sha256_path(args.out), "code_sha256": code_sha, "cpp": cpp_state,
                  "exheader_sha256": sha256_path(verify["exh.bin"]), "plain_sha256": sha256_path(verify["plain.bin"]),
                  "verify": checks + ["ExeFS/code PASS", "exheader/plain PASS", "partition1/7 byte-identical", "NCSD/NCCH identity PASS"]}
        (work / "build-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        stage(100, "완료")
        print(json.dumps(result, indent=2))
        return 0
    except (InspectError, OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect", help="identify a dump; writes nothing")
    inspect.add_argument("base", type=Path, help="the user's own base game dump (.cci/.3ds)")
    inspect.add_argument("--update", type=Path, help="official 1.1 update (.cia or decrypted .cxi)")
    inspect.add_argument("-v", "--verbose", action="store_true", help="also print measured hashes")
    inspect.set_defaults(function=command_inspect)
    build = subparsers.add_parser("build", help="build and re-unpack-verify a standalone Korean CCI")
    build.add_argument("base", type=Path, help="clean decrypted USA 1.0 CCI/3DS")
    build.add_argument("--track", choices=("1.0", "1.1"), required=True)
    build.add_argument("--out", type=Path, required=True, help="output CCI path")
    build.add_argument("--workdir", type=Path, required=True, help="new/empty work directory")
    build.set_defaults(function=command_build)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.function(args)


if __name__ == "__main__":
    raise SystemExit(main())
