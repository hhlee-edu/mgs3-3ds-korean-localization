#!/usr/bin/env python3
"""Verify a built MGS3D Citra mod and the untouched source inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mgs3d_codec_tool import parse_codec  # noqa: E402
from mgs3d_movie_tool import parse_records  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_output_paths(outputs: object, require_complete: bool) -> set[str]:
    expected = {"romfs/codec.dat", "romfs/movie.dat", "romfs/demo.dat"}
    if not isinstance(outputs, list) or not outputs:
        raise SystemExit("manifest outputs must be a nonempty array")
    if any(not isinstance(item, dict) or "path" not in item for item in outputs):
        raise SystemExit("every manifest output must be an object with a path")
    declared_list = [str(item["path"]) for item in outputs]
    declared = set(declared_list)
    if len(declared) != len(declared_list):
        raise SystemExit("manifest contains duplicate output paths")
    unexpected = declared - expected
    if unexpected:
        raise SystemExit(f"manifest contains unsupported outputs: {sorted(unexpected)}")
    if require_complete and declared != expected:
        raise SystemExit(f"complete build is missing: {sorted(expected - declared)}")
    return declared


def validate_capacity_provenance(
    report: object, codec_item: dict[str, object], source_hash: str
) -> int:
    if not isinstance(report, dict) or report.get("format") != "mgs3d-codec-capacity-v1":
        raise SystemExit("unsupported codec capacity report")
    if (
        report.get("source_codec_sha256") != source_hash
        or codec_item.get("source_codec_sha256") != source_hash
    ):
        raise SystemExit("codec capacity report source hash mismatch")
    if report.get("translation_sha256") != codec_item.get("translation_sha256"):
        raise SystemExit("codec capacity report translation hash mismatch")
    records = report.get("records")
    if not isinstance(records, list):
        raise SystemExit("codec capacity report records must be an array")
    deficits = [item for item in records if int(item.get("slot_deficit", -1))]
    if deficits:
        raise SystemExit(f"safe-fixed capacity report has {len(deficits)} deficits")
    summary = report.get("summary", {})
    if (
        not isinstance(summary, dict)
        or int(summary.get("failing_records", -1)) != 0
        or int(summary.get("total_slot_deficit", -1)) != 0
        or int(summary.get("gcx_records", -1)) != len(records)
    ):
        raise SystemExit("codec capacity report summary mismatch")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mod", type=Path, help="title-ID directory containing build-manifest.json")
    parser.add_argument("--partition", type=Path, default=Path("partition0"))
    parser.add_argument("--baseline", type=Path, default=Path("docs/unpacked-baseline.json"))
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="require codec.dat, movie.dat, and demo.dat for a release candidate",
    )
    args = parser.parse_args()
    manifest = json.loads((args.mod / "build-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "mgs3d-citra-korean-build-v1":
        raise SystemExit(f"unsupported build manifest: {manifest.get('format')!r}")
    if manifest.get("title_id") != args.mod.name:
        raise SystemExit(
            f"manifest title ID {manifest.get('title_id')!r} does not match {args.mod.name!r}"
        )
    outputs = manifest.get("outputs")
    declared = validate_output_paths(outputs, args.require_complete)
    if args.require_complete and manifest.get("codec_mode") != "safe-fixed":
        raise SystemExit(
            f"complete release requires codec_mode='safe-fixed', got "
            f"{manifest.get('codec_mode')!r}"
        )
    for item in manifest["outputs"]:
        path = args.mod / str(item["path"])
        actual_size, actual_hash = path.stat().st_size, sha256(path)
        if actual_size != int(item["size"]) or actual_hash != item["sha256"]:
            raise SystemExit(f"manifest mismatch: {path}")
        print(f"OK hash {item['path']} {actual_size} {actual_hash}")
        allocation_name = item.get("allocation_report")
        allocation_hash = item.get("allocation_report_sha256")
        if allocation_name is not None or allocation_hash is not None:
            if not isinstance(allocation_name, str) or not isinstance(allocation_hash, str):
                raise SystemExit(f"incomplete allocation report metadata: {item['path']}")
            allocation_path = args.mod / allocation_name
            if not allocation_path.is_file() or sha256(allocation_path) != allocation_hash:
                raise SystemExit(f"allocation report mismatch: {allocation_path}")
            print(f"OK allocation report {allocation_name}")

    if "romfs/codec.dat" in declared:
        codec = parse_codec((args.mod / "romfs/codec.dat").read_bytes())
        resources = sum(len(record.resources()) for record in codec)
        if (len(codec), resources) != (2326, 198227):
            raise SystemExit(f"codec structure mismatch: {len(codec)} records, {resources} resources")
        print("OK codec structure 2326 records / 198227 resources")
        codec_item = next(item for item in outputs if item["path"] == "romfs/codec.dat")
        if str(manifest.get("codec_mode", "")).endswith("fixed"):
            source_codec = parse_codec((args.partition / "romfs/codec.dat").read_bytes())
            mismatches = [
                index
                for index, (source, built) in enumerate(zip(source_codec, codec))
                if (
                    source.source_offset != built.source_offset
                    or len(source.raw) != len(built.raw)
                    or source.string_resources_offset != built.string_resources_offset
                    or source.font_data_offset != built.font_data_offset
                    or source.proc_offset != built.proc_offset
                )
            ]
            if mismatches:
                raise SystemExit(
                    f"fixed-layout codec mismatch in {len(mismatches)} GCX records: "
                    f"{mismatches[:10]}"
                )
            print("OK codec fixed layout 2326/2326 records")
            del source_codec
        if manifest.get("codec_mode") == "safe-fixed":
            report_name = codec_item.get("capacity_report")
            report_hash = codec_item.get("capacity_report_sha256")
            if not isinstance(report_name, str) or not isinstance(report_hash, str):
                raise SystemExit("safe-fixed codec is missing its capacity report metadata")
            report_path = args.mod / report_name
            if not report_path.is_file() or sha256(report_path) != report_hash:
                raise SystemExit(f"capacity report mismatch: {report_path}")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            source_hash = sha256(args.partition / "romfs/codec.dat")
            capacity_records = validate_capacity_provenance(
                report, codec_item, source_hash
            )
            print(f"OK codec capacity report {capacity_records} records")
        del codec

    for name, expected in (("movie", (93, 558)), ("demo", (260, 2091))):
        if f"romfs/{name}.dat" not in declared:
            continue
        _, records, _ = parse_records((args.mod / f"romfs/{name}.dat").read_bytes())
        count = sum(len(record.subtitles) for record in records)
        if (len(records), count) != expected:
            raise SystemExit(f"{name} structure mismatch: {len(records)} records, {count} subtitles")
        print(f"OK {name} structure {len(records)} records / {count} subtitles")
        del records

    audit = Path(__file__).resolve().parent / "audit_unpacked.py"
    result = subprocess.run([sys.executable, str(audit), "verify", str(args.partition), str(args.baseline)])
    if result.returncode:
        return result.returncode
    print("ALL BUILD CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
