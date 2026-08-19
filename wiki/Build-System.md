# Build System

## ⚠️ codec production build에는 `expand_locations`가 **필수**다

**`tools/mgs3d_build.py`를 그대로 쓰면 codec 빌드가 깨진다.** 이 스크립트에는
duplicate-location 확장 단계가 **없다**. 2026-08-19에 이것 때문에 빌드가 실패했고
원인을 찾는 데 상당한 시간이 들었다.

이유: `translation/10_master/current/codec.csv`는 동일 문자열을 **한 행으로 접고**
나머지 위치를 `locations` 열에 담는다. `make-translation`은 canonical `(gcx, resource)`
**하나만** 내보내므로, 확장하지 않으면 같은 GCX의 나머지 중복 위치가 문서에서 빠진다.

byte 예산은 **GCX 단위 풀**(교체 대상 리소스들의 원본 바이트 합계) 안에서 재배분되므로,
위치가 빠지면 그 바이트도 풀에서 사라져 **멀쩡한 번역이 용량 초과로 실패**한다.

```
GCX 44 실측 (2026-08-19)
  확장 없음 : 교체 3행,  풀    73B → 한국어 83B  = +10B 초과, 빌드 실패
  확장 적용 : 교체 17행, 풀 2,048B → 여유 충분,  빌드 성공
전체       : 8,994행 → 225,307 units (25배)
```

**증상**: `error: GCX <n>: replacement strings exceed fixed region by <n> bytes`
→ 번역이 길어서가 아니라 **확장 단계 누락**을 먼저 의심할 것. donor accept 해제나
행 제외로 대응하면 멀쩡한 번역을 잃는다.

올바른 순서:

```
1. mgs3d_script_compare.py make-translation  <master.csv> <canonical.json> --codec <codec.dat> --character-map <map>
2. mgs3d_codec_expand_locations.py           --translation <canonical.json> --out-doc <expanded.json> --out-report <report.json>
3. mgs3d_gcx_font_tool.py capacity           <codec.dat> <expanded.json> --json <cap.json> --check
4. mgs3d_gcx_font_tool.py build-korean       <codec.dat> <expanded.json> <font> <out.dat> --font-size 15 --reuse-freed-font --preserve-record-layout
```

소스 codec.dat은 항상 clean-tree(`experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat`,
`dd6ea4b8…`)다. staging본을 소스로 쓰면 이중 적용이 된다.

`mgs3d_build.py`는 movie/demo에는 그대로 써도 된다 — 그쪽 CSV는 위치를 접지 않는다.

## RomForge pipeline

- Analysis/translation/verification work: `D:\dev\3dsmetal\analysis` (this repo).
- RomForge unpack + CCI output: `C:\Users\hhlee\Desktop\Romforge\output`.
- **Canonical path reaffirmed 2026-08-14:** use the path above. Do not use
  `C:\Users\hhlee\Desktop\metagear3d\romforge\output`; that was a mistaken
  parallel output tree and produced a build-lineage mix-up.
- The canonical `output` root now keeps only `unpacked/` (current staging).
  Other former output-root folders were moved, not deleted, to
  `C:\Users\hhlee\Desktop\Romforge\archive\output-20260814`.
- The seven-underscore CCI was initially retained as a presumed golden build,
  then extracted and identified as the controlled `ABC 호프번 XYZ` probe
  (`fb8215dd...47fb`), not the recorded golden build. It is archived under
  `output-20260814\cci-abc-hofbeon-probe` and must not be used as a baseline.
- `Romforge\output\unpacked` gets overwritten by later builds — for a past
  version, trust the archived staging directory + hash, not the live unpacked
  tree.
- ⚠️ **`Romforge\output\unpacked\...\romfs\` is disposable staging, not
  storage** ([Conventions](Conventions.md) R7). No `.bak`/log/analysis file
  belongs there — repack bundles the whole folder into the CCI. Known live
  violation: `demo.dat.bak-before-autofit106-2026-08-07` (772,935,680 B) and a
  `movie.dat.bak-…` sitting in the current unpacked tree.

## Build naming — the current failure mode

**Never use bare underscore-count names again** (`Repack.cci`, `Repack_.cci`,
… `Repack_______.cci`). This project's own golden reference build carries this
exact naming scheme, and as of 2026-08-13 the live output directory already
has 0 through 6 underscores — **the next repack will write 7, the golden's own
documented filename**, over a completely different, unverified build. See
[Decisions](Decisions.md) DEC-011 — this is urgent, not stylistic.

Going forward ([Conventions](Conventions.md) R6): meaningful names
(`mgs3d-clean-original.cci`, `mgs3d-globalpage-poc01.cci`, …) plus a manifest
recording build name, timestamp, baseline hash, code.bin hash, DAT hashes,
patch list, Korean-page version/hash, token-map version/hash, stage patch
count, `K`, output CCI hash — sufficient to reproduce the build from the
manifest alone.

## The golden build

Recorded reference, boot-verified 2026-08-03 (partial Korean movie output
confirmed in Citra):
```
MGS SNAKE EATER 3D_Repack_______.cci   (7 underscores)
3,248,410,624 bytes
SHA-256 3BD843008721C8018054B041FD6DBDBA617C5DE99751D62E192F4082EE7E6504
```

**As of 2026-08-13 the binary itself no longer exists anywhere on disk** (11
CCIs across the whole machine were hashed; none match). It is fully
reproducible from `archive/old-data/script_ref_archive_2026-08-07/staging_tom_codec_original_media/`
— all five recorded input hashes (`codec.dat`, `movie.dat`, `demo.dat`,
`stage/r_sna01/resident.hpk`, `stage/r_sna02/resident.hpk`) verify there
byte-exact against `analysis/REPACK_VERSION_INDEX.md (kept at its original path -- not part of the move, still describes CCI-to-input mapping)`. See
[Current State](Current-State.md#current-build) for the full evidence.

`analysis/REPACK_VERSION_INDEX.md (kept at its original path -- not part of the move, still describes CCI-to-input mapping)` is the authority for CCI-to-input mapping —
**never assume two similarly-named CCIs share an input set.** Two same-day
(2026-08-03) archived CCIs at the golden's exact byte size turned out to be
two entirely different builds (confirmed by hash), not copies of the golden.

## Safety rule for codec builds

## v0.67 HPK pre-pack gate

The hardware candidate uses this exact staging file:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\stage\v000a_0\cache.hpk`

Immediately before every CCI repack, run:

```powershell
python tools/mgs3d_hpk_chain_check.py "C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\stage\v000a_0\cache.hpk"
Get-FileHash -Algorithm SHA256 "C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\stage\v000a_0\cache.hpk"
```

Required result: exit 0, `OK: no padded-slot drift`, SHA-256
`d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`.
The defective archive is
`4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`.
Both have the same size, so size is not an identity check.

After repacking, extract the new CCI and hash its internal
`romfs/stage/v000a_0/cache.hpk`. A staging-only check is insufficient.

## Safety rule for codec builds

Use the unified builder's default `safe-fixed` mode
([GCX Format](GCX-Format.md)). A resized GCX may reparse correctly but crash in
game because later records move. Diagnostic/relocation modes are research-only
and must not ship.

```powershell
python tools/mgs3d_build.py --help
python tools/mgs3d_verify_build.py --help
python tools/mgs3d_codec_tool.py validate-translation translation.json
python tools/mgs3d_doctor.py --source-only
```

`mgs3d_verify_build.py <title-id-directory>` does an incremental build check;
add `--require-complete` for a release-candidate check with all three DAT
outputs. Complete-release verification rejects diagnostic, experimental,
unknown, and legacy unrecorded codec modes.

## Division of labor

This assistant (Codex) prepares/verifies/stages files; the user performs the
actual RomForge repack and hardware/Citra test. Check in on scope before
starting a long investigation stretch.
