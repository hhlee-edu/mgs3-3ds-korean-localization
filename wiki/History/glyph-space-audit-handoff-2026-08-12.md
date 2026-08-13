# Glyph/space audit handoff — 2026-08-12

## 1. 목적과 현재 상태

번역 작업과 분리하여 movie/demo/codec의 실제 글리프 슬롯 및 바이트
용량을 분석하는 read-only 단계까지 완료했다. 현재 산출물은 패치가 아니라
**검증 가능한 비용/부족량 보고서**다.

- 번역 생성·수정: 하지 않음
- DAT/GCX/HPK/ROM 수정: 하지 않음
- record 재배치/offset 변경: 하지 않음
- 기존 빌더 변경: 하지 않음
- 현재 결과: `analysis/glyph_space_audit/current/`
- 상세 근거: `docs/glyph-space-audit-2026-08-12.md`

## 2. 확정된 바이너리 근거

### Resident/static/common

- `r_sna01/resident.hpk` SHA-256:
  `99d17ebb7d336f84f76ec545e6cdfe59fd976992e151ac61498cdcdf18e21cce`
- `r_sna02/resident.hpk` SHA-256:
  `fbd6baa91624a1f79a6f01e3d5a6bfe607e519bf1d66b38d1ae1ef1101a16836`
- 두 live 파일은 각 allocation report의 출력 해시와 일치한다.
- 두 allocation report의 191자 character map도 동일하다.
- 따라서 `common_glyphs.csv`의 문자/token/physical slot은 빈도 추정이
  아니라 검증된 resident allocation이다.

### Local glyph

- 글리프 한 슬롯은 64B, 16x16, 2bpp다.
- movie/demo: record별 `0x90` local page. subtitle token owner가 없는
  슬롯만 그 record 안에서 재사용할 수 있다.
- codec: GCX별 `0x8C` local page. resource token owner가 없는 슬롯만 그
  GCX 안에서 재사용할 수 있다.
- record/GCX 사이에서 슬롯을 공유하거나 옮길 근거는 없다.

## 3. 현재 수치

| 구분 | scope | local slots | dead slots | 재사용 가능 바이트 |
|---|---:|---:|---:|---:|
| movie | 108 records | 476 | 0 | 0 |
| demo | 333 records | 980 | 0 | 0 |
| codec | 2,326 GCX | 14,370 | 1,545 | 98,880 |

GCX53은 24슬롯 중 5슬롯(5, 6, 7, 8, 14)이 owner가 없어 320B를
GCX53 내부에서 재사용할 수 있다. 이것은 GCX53 성장·이동 허가가 아니다.

Demo scene padding 부족:

| scene | pad budget | growth | shortage |
|---:|---:|---:|---:|
| 36 | 117 | 896 | 779 |
| 113 | 198 | 640 | 442 |
| 13 | 150 | 512 | 362 |
| 49 | 5 | 192 | 187 |
| 10 | 534 | 640 | 106 |
| 61 | 86 | 192 | 106 |
| 76 | 710 | 768 | 58 |

Codec preserve-size 부족은 376 GCX다. 최대 부족은 GCX261 2,268B,
GCX270 2,130B, GCX444 1,619B, GCX355 1,095B, GCX652 1,047B다.

## 4. 리포트 해석 규칙

- `common_glyphs`: 검증된 resident 문자, 추가 local 비용 0.
- `new_glyphs`: 해당 scope의 base/resident map에 없는 한글.
- `glyph_add_bytes`: local slot 재사용 전 `new_glyph_count * 64`.
- `glyph_reclaim_bytes`: 실제 zero-owner local slot 용량.
- `donor_reclaim_bytes`: 이번 분석에서는 0. byte donor 이전을 하지 않았다.
- `string_reclaim_bytes`: 인코딩 결과가 줄어든 양. fixed-offset 행 사이에
  자동 이전되는 공간으로 간주하면 안 된다.
- `final_headroom`/`overflow_bytes`: 실제 encoder 및 해당 빌더의 용량식을
  사용한다.
- `overflow_glyphs.csv`: 부족 scope의 글리프, 사용 row, 영어, 한국어,
  기계적 64B 제거 가능량. 번역/축약 제안은 포함하지 않는다.

## 5. 재현 절차

전체 명령은 `docs/glyph-space-audit-2026-08-12.md`의 Reproduction 절을
그대로 실행한다. 성공 시 마지막 출력은 다음이어야 한다.

```json
{"scopes":2767,"glyph_detail_rows":3302,"overflow_scopes":405,"live_local_slot_scopes":2767,"live_dead_slots":1545,"live_reusable_bytes":98880}
```

빠른 코드 검증:

```powershell
python -m py_compile tools/mgs3d_glyph_space_audit.py tests/test_glyph_space_audit.py
python -m unittest tests.test_glyph_space_audit tests.test_codec_size_neutral_select
python -m unittest tests.test_gcx_font_safety.TranslationChangeTests `
  tests.test_gcx_font_safety.CapacityOwnershipTests `
  tests.test_gcx_font_safety.GlyphSlotOwnershipTests `
  tests.test_gcx_font_safety.CliTests
```

## 6. 다음 작업의 정확한 시작점

분석 이후의 첫 구현 후보는 fixed-offset movie/demo rebuild 경로에 검증된
resident `static_map`을 명시적으로 전달하는 연결 작업이다. growing builder는
static allocation을 받지만 `rebuild_record_fixed_reclaim()`은 아직 받지 않는다.

진행 순서:

1. fixed-reclaim 함수의 token map 입력/우선순위를 단위 테스트로 고정한다.
2. 원본 record 크기·subtitle offset·record offset 불변 테스트를 추가한다.
3. 극소수 복제본에만 출력해 byte diff와 재파싱 결과를 검토한다.
4. 사용자 확인 전 ROM/실기 빌드나 전체 patch로 확대하지 않는다.

## 7. 금지 및 주의사항

- 분석 결과만 보고 자동 번역하거나 한국어를 축약하지 않는다.
- `98,880B`를 전역 공간으로 합산해 쓰지 않는다. 전부 각 GCX에 고정된다.
- blank 문자열의 바이트를 다른 fixed-offset 행의 donor로 계산하지 않는다.
- GCX53 record 재배치나 offset 변경을 시도하지 않는다.
- generated CSV를 번역 CSV에 merge하지 않는다.
- pristine 입력과 live 입력을 혼동하지 않는다. pristine은 before/capacity,
  live는 현재 dead-slot inventory에만 사용한다.
- 기존 worktree에는 이 작업과 무관한 미완성 변경이 있으므로 후속 커밋도
  path를 명시해 stage해야 한다.

## 8. 산출물 목록

- `tools/mgs3d_glyph_space_audit.py`
- `tests/test_glyph_space_audit.py`
- `docs/glyph-space-audit-2026-08-12.md`
- `docs/glyph-space-audit-handoff-2026-08-12.md`
- `analysis/glyph_space_audit/current/audit.json`
- `analysis/glyph_space_audit/current/common_glyphs.csv`
- `analysis/glyph_space_audit/current/movie_records.csv`
- `analysis/glyph_space_audit/current/demo_records.csv`
- `analysis/glyph_space_audit/current/demo_scenes.csv`
- `analysis/glyph_space_audit/current/codec_gcx.csv`
- `analysis/glyph_space_audit/current/live_local_slots.csv`
- `analysis/glyph_space_audit/current/glyph_cost_details.csv`
- `analysis/glyph_space_audit/current/overflow_glyphs.csv`
- `analysis/glyph_space_audit/current/overflows.csv`
