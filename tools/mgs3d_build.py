#!/usr/bin/env python3
"""Build verified MGS3D Korean files into a Citra mod directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def title_id(header: Path) -> str:
    data = header.read_bytes()
    if len(data) < 0x110 or data[0x100:0x104] != b"NCCH":
        raise BuildError(f"not an NCCH header: {header}")
    return f"{int.from_bytes(data[0x108:0x110], 'little'):016X}"


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise BuildError(f"builder failed with exit code {completed.returncode}: {' '.join(command)}")


def preserved_output_metadata(
    relative: str,
    size: int,
    digest: str,
    previous_outputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    previous = previous_outputs.get(relative)
    if (
        previous
        and int(previous.get("size", -1)) == size
        and previous.get("sha256") == digest
    ):
        return dict(previous)
    return {"path": relative, "size": size, "sha256": digest}


def select_codec_mode(
    codec_built: bool, requested_mode: str, codec_present: bool, previous_mode: object
) -> str | None:
    if codec_built:
        return requested_mode
    if codec_present:
        return previous_mode if isinstance(previous_mode, str) else "unknown"
    return None


def temporary_path(target: Path) -> Path:
    return target.with_name(target.name + ".tmp")


def discard_temporary(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def allocation_report_path(target: Path) -> Path:
    return target.with_suffix(target.suffix + ".hangul.json")


def acquire_build_lock(build_root: Path) -> Path:
    build_root.mkdir(parents=True, exist_ok=True)
    lock = build_root / ".mgs3d-build.lock"
    try:
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()}\n")
    except FileExistsError as exc:
        raise BuildError(
            f"another build is active or a stale lock remains: {lock}"
        ) from exc
    return lock


def release_build_lock(lock: Path | None) -> None:
    if lock is not None:
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", type=Path, default=Path("partition0"))
    parser.add_argument("--output-root", type=Path, default=Path("dist/citra_mod"))
    parser.add_argument("--font", type=Path, default=Path(r"C:\Windows\Fonts\malgun.ttf"))
    parser.add_argument("--font-size", type=int, default=15)
    parser.add_argument("--codec-translation", type=Path)
    parser.add_argument("--codec-review", type=Path, help="review CSV with accepted codec rows")
    parser.add_argument(
        "--codec-mode",
        choices=("safe-fixed", "diagnostic-fixed", "experimental-relocate"),
        default="safe-fixed",
        help="codec layout strategy; safe-fixed refuses collateral glyph damage",
    )
    parser.add_argument("--movie-csv", type=Path)
    parser.add_argument("--demo-csv", type=Path)
    args = parser.parse_args()
    build_lock: Path | None = None
    temporary_artifacts: list[Path] = []
    staged_outputs: list[tuple[Path, Path]] = []
    try:
        if args.codec_translation and args.codec_review:
            raise BuildError("use only one of --codec-translation and --codec-review")
        if not any((args.codec_translation, args.codec_review, args.movie_csv, args.demo_csv)):
            raise BuildError("select at least one translation input")
        tid = title_id(args.partition / "header.bin")
        build_root = args.output_root / tid
        build_lock = acquire_build_lock(build_root)
        manifest_path = build_root / "build-manifest.json"
        previous_manifest: dict[str, object] = {}
        if manifest_path.is_file():
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                loaded.get("format") == "mgs3d-citra-korean-build-v1"
                and loaded.get("title_id") == tid
            ):
                previous_manifest = loaded
        previous_outputs = {
            str(item["path"]): item
            for item in previous_manifest.get("outputs", [])
            if isinstance(item, dict) and "path" in item
        }
        romfs = build_root / "romfs"
        romfs.mkdir(parents=True, exist_ok=True)
        python = sys.executable
        tools = Path(__file__).resolve().parent
        outputs: list[dict[str, object]] = []

        codec_translation = args.codec_translation
        if args.codec_review:
            codec_translation = args.output_root / tid / "accepted_codec_translation.json"
            run([python, str(tools / "mgs3d_script_compare.py"), "make-translation",
                 str(args.codec_review), str(codec_translation), "--codec",
                 str(args.partition / "romfs/codec.dat")])

        if codec_translation:
            target = romfs / "codec.dat"
            capacity_report: Path | None = None
            capacity_temporary: Path | None = None
            capacity_command: list[str] | None = None
            target_temporary = temporary_path(target)
            allocation_report = allocation_report_path(target)
            allocation_temporary = allocation_report_path(target_temporary)
            temporary_artifacts.extend([target_temporary, allocation_temporary])
            if args.codec_mode == "safe-fixed":
                capacity_report = build_root / "codec-capacity.json"
                capacity_temporary = temporary_path(capacity_report)
                temporary_artifacts.append(capacity_temporary)
                discard_temporary(capacity_temporary)
                capacity_command = [
                    python,
                    str(tools / "mgs3d_gcx_font_tool.py"),
                    "capacity",
                    str(args.partition / "romfs/codec.dat"),
                    str(codec_translation),
                    "--json",
                    str(capacity_temporary),
                    "--check",
                ]
            command = [python, str(tools / "mgs3d_gcx_font_tool.py"), "build-korean",
                       str(args.partition / "romfs/codec.dat"), str(codec_translation),
                       str(args.font), str(target_temporary), "--font-size", str(args.font_size)]
            if args.codec_mode == "safe-fixed":
                command.extend(["--reuse-freed-font", "--preserve-record-layout"])
            elif args.codec_mode == "diagnostic-fixed":
                command.extend(["--reuse-existing-font", "--preserve-record-layout"])
            discard_temporary(target_temporary, allocation_temporary)
            try:
                if capacity_command:
                    run(capacity_command)
                run(command)
                if not allocation_temporary.is_file():
                    raise BuildError(
                        f"codec builder did not create allocation report: {allocation_temporary}"
                    )
                staged_outputs.extend([
                    (target_temporary, target),
                    (allocation_temporary, allocation_report),
                ])
                if capacity_report and capacity_temporary:
                    staged_outputs.append((capacity_temporary, capacity_report))
            except (OSError, BuildError):
                discard_temporary(target_temporary, allocation_temporary)
                if capacity_temporary:
                    discard_temporary(capacity_temporary)
                raise
            codec_output: dict[str, object] = {
                "path": "romfs/codec.dat",
                "size": target_temporary.stat().st_size,
                "sha256": sha256(target_temporary),
                "allocation_report": f"romfs/{allocation_report.name}",
                "allocation_report_sha256": sha256(allocation_temporary),
            }
            if capacity_report:
                codec_output["capacity_report"] = capacity_report.name
                codec_output["capacity_report_sha256"] = sha256(capacity_temporary)
                codec_output["source_codec_sha256"] = sha256(
                    args.partition / "romfs/codec.dat"
                )
                codec_output["translation_sha256"] = sha256(codec_translation)
            outputs.append(codec_output)
        for name, translation in (("movie", args.movie_csv), ("demo", args.demo_csv)):
            if not translation:
                continue
            target = romfs / f"{name}.dat"
            target_temporary = temporary_path(target)
            allocation_report = allocation_report_path(target)
            allocation_temporary = allocation_report_path(target_temporary)
            temporary_artifacts.extend([target_temporary, allocation_temporary])
            discard_temporary(target_temporary, allocation_temporary)
            try:
                run([python, str(tools / "mgs3d_movie_tool.py"), "build-korean",
                     str(args.partition / f"romfs/{name}.dat"), str(translation),
                     str(args.font), str(target_temporary), "--font-size", str(args.font_size)])
                if not allocation_temporary.is_file():
                    raise BuildError(
                        f"{name} builder did not create allocation report: {allocation_temporary}"
                    )
                staged_outputs.extend([
                    (target_temporary, target),
                    (allocation_temporary, allocation_report),
                ])
            except (OSError, BuildError):
                discard_temporary(target_temporary, allocation_temporary)
                raise
            outputs.append({
                "path": f"romfs/{name}.dat",
                "size": target_temporary.stat().st_size,
                "sha256": sha256(target_temporary),
                "allocation_report": f"romfs/{allocation_report.name}",
                "allocation_report_sha256": sha256(allocation_temporary),
            })

        # Include already-built siblings when the command is run incrementally.
        recorded = {str(item["path"]) for item in outputs}
        for name in ("codec.dat", "movie.dat", "demo.dat"):
            target = romfs / name
            relative = f"romfs/{name}"
            if target.exists() and relative not in recorded:
                size, digest = target.stat().st_size, sha256(target)
                outputs.append(
                    preserved_output_metadata(
                        relative, size, digest, previous_outputs
                    )
                )
        outputs.sort(key=lambda item: str(item["path"]))
        codec_present = any(item["path"] == "romfs/codec.dat" for item in outputs)
        effective_codec_mode = select_codec_mode(
            codec_translation is not None,
            args.codec_mode,
            codec_present,
            previous_manifest.get("codec_mode"),
        )
        manifest = {
            "format": "mgs3d-citra-korean-build-v1",
            "title_id": tid,
            "font": str(args.font),
            "font_size": args.font_size,
            "outputs": outputs,
        }
        if effective_codec_mode is not None:
            manifest["codec_mode"] = effective_codec_mode
        manifest_temporary = temporary_path(manifest_path)
        temporary_artifacts.append(manifest_temporary)
        discard_temporary(manifest_temporary)
        manifest_temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for temporary, target in staged_outputs:
            temporary.replace(target)
        manifest_temporary.replace(manifest_path)
        print(f"Citra mod ready at {build_root} ({len(outputs)} files)")
        return 0
    except (OSError, BuildError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        discard_temporary(*temporary_artifacts)
        release_build_lock(build_lock)


if __name__ == "__main__":
    raise SystemExit(main())
