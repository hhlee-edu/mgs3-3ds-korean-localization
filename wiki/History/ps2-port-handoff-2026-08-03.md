# PS2 정식 한글판 → MGS3D 이식 작업 인계 (2026-08-03)

## 1. 프로젝트 목표

이 프로젝트의 현재 목표는 영문판을 새로 번역하는 것이 아니다. PS2 정식
한글판에 들어 있는 공식 한국어 문장, 토큰 배치, 글꼴 비트맵을 가능한 한
그대로 3DS판 `Metal Gear Solid: Snake Eater 3D`에 이식하는 것이다.

우선순위는 다음과 같다.

1. PS2 공식 한글 문장을 직접 사용한다.
2. 3DS 원본 파일 크기와 모든 내부 레코드 경계를 보존한다.
3. PS2 글리프를 3DS 16×16 2-bpp 형식으로 변환하거나 검증된 3DS 정적
   한글 페이지에 매핑한다.
4. 영문 피벗 결과는 PS2↔3DS 대응 위치를 찾는 보조 자료로만 사용한다.
5. 런타임 검증은 한 번에 한 계층(codec, movie, demo, TOM)만 바꿔 수행한다.

## 2. 혼동하면 안 되는 두 파이프라인

### 2.1 PS2 공식 이식 파이프라인 — 최종 목표

주요 도구:

- `tools/mgs3_ps2_korean_port.py`
- `tools/mgs3_ps2_korean_token_map.py`
- `tools/mgs3_ps2_korean_token_mine.py`
- `tools/mgs3_ps2_korean_paragraph_mine.py`
- `tools/mgs3_ps2_static_first_radio.py`
- `tools/mgs3d_hpk_static_korean.py`
- `tools/mgs3_ps2_tom_bitmap_port.py`

PS2 `CODEC.DAT`의 24×24, 2-bpp, 144바이트 로컬 글리프를 3DS의
16×16, 2-bpp, 64바이트 글리프로 변환한다. 3DS procedure/resource shell과
PS2 공식 텍스트/글꼴을 결합하는 방식과 PS2 레코드 전체를 가져오는 방식이
구현되어 있다.

codec용 공용 정적 글꼴은 다음 HPK에서 런타임 확인됐다.

- `stage/r_sna01/resident.hpk`
- `stage/r_sna02/resident.hpk`
- HPK entry key: `453C386E`
- 정적 페이지: `81xx`, `82xx`, `83xx`
- 사용 가능한 `81/82` 정적 슬롯: 165개

첫 PS2 공식 라디오 문단은 codec 크기와 HPK 크기를 유지한 채 실기/런타임
검증을 통과했다. bulk 후보는 자주 쓰는 165개 글자를 정적 페이지에 두고
나머지만 record-local 글리프로 처리한다.

### 2.2 영문 피벗 파이프라인 — 진단용

주요 입력:

- `analysis/english_bulk_candidate/demo_translation.csv`
- `analysis/english_bulk_candidate/movie_translation.csv`

이 경로는 3DS 영문 자막과 검토된 한국어를 연결하고 맑은 고딕 글리프를
각 movie/demo 레코드의 로컬 page-3 글꼴에 새로 삽입한다. PS2 공식 글꼴과
토큰을 직접 사용하지 않는다.

현재 size-neutral 결과:

- demo: 입력 457행, 선택 323행, 제외 134행
- movie: 입력 51행, 선택 40행, 제외 11행

이 숫자를 “PS2 전체 이식률”로 보고하면 안 된다. 이는 예전 영문 피벗
후보가 현재 donor 정책과 로컬 글꼴 공간 안에 들어가는 비율일 뿐이다.

## 3. codec에서 해결된 것과 movie/demo에 남은 것

codec과 movie/demo는 글꼴 저장 및 참조 방식이 다르다.

### codec

- GCX별 로컬 글꼴과 HPK 공용 정적 글꼴을 함께 사용할 수 있다.
- PS2 공식 텍스트/글꼴 변환 도구가 존재한다.
- 정적 `81/82` 165슬롯을 corpus 빈도순으로 배치하는 bulk 후보가 있다.
- 첫 공식 라디오 문단은 레코드와 파일 크기를 보존한 상태로 검증됐다.

### movie/demo

- `movie.dat`과 `demo.dat`은 별도 자막 레코드 형식이다.
- 각 레코드에 type-1 영문과 type 2–5 타 언어 donor, 로컬 page-3 글꼴이
  들어 있다.
- 현재 `mgs3d_movie_tool.py`는 한글을 레코드 로컬 글꼴에 삽입한다.
- codec용 HPK 정적 `81/82` 페이지를 movie/demo 렌더러가 그대로 참조한다는
  런타임 증거는 아직 없다.
- 따라서 codec에서 해결된 공용 글리프 방식은 movie/demo에 자동 적용되지
  않는다.

다음 핵심 개발 과제는 PS2 공식 movie/demo 문장을 3DS 레코드에 직접
대응시키고, 해당 렌더러에서 사용할 수 있는 기존 글꼴 슬롯/토큰을 확인해
고정 크기로 재조립하는 것이다.

## 4. 절대 보존 조건

모든 production 후보에 다음 검사를 적용한다.

- 출력 DAT 크기 == 입력 DAT 크기
- 레코드 개수 동일
- 각 레코드 시작 오프셋 동일
- 각 레코드 크기 동일
- 모든 레코드 재파싱 성공
- 두 번 빌드한 SHA-256 동일
- CCI 패킹 전 입력 파일들의 해시 기록

`mgs3d_build.py`는 movie/demo 출력 manifest에 원본 SHA-256과 크기를 기록한다.
`mgs3d_verify_build.py`는 이를 다시 확인하고, 빌드에 사용한 동일 판본 원본과
비교해 파일 크기, 레코드 개수, 각 레코드 시작 오프셋과 크기가 모두 같은
경우에만 통과시킨다. 판본마다 레코드 수가 다르므로 하드코딩된 개수 대신
manifest가 가리키는 실제 원본을 기준으로 한다. 레코드 내부 텍스트/로컬
글꼴 영역은 고정된 레코드 크기 안에서 재배분할 수 있다.

`--grow-records`는 진단 외에는 사용하지 않는다. 전체 파일의 최종 크기를
패딩으로 맞추더라도 중간 레코드 경계가 이동하면 실패다.

## 5. 2026-08-03 런타임 결과

### 5.1 실기 성공 골든 CCI

경로:

`C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack_______.cci`

- 크기: `3,248,410,624`바이트
- SHA-256: `3BD843008721C8018054B041FD6DBDBA617C5DE99751D62E192F4082EE7E6504`
- 사용자 확인: 실제 3DS에서 부팅 성공
- Citra에서 일부 movie 한글 문장 출력 확인:
  - “그렇다.”
  - “손을 떼고 …”
  - “두려워했다고?”

이 CCI는 덮어쓰지 않는다. 내부 구성에 대한 추측보다 CCI 자체의 해시와
실기 성공 사실을 골든 기준으로 삼는다.

### 5.2 실패: demo 457행 강제 확장

명령 개념:

`mgs3d_movie_tool.py build-korean ... --grow-records`

결과:

- 457/457행 선택
- `demo.dat`: `773,100,176`바이트
- SHA-256: `954792FE70C0E2E3FC856B846E20805649813B0E7892CAD581B33DD76B217310`
- 원본 기준 `772,935,680`바이트보다 `164,496`바이트 증가
- 런타임: 첫 영상이 나오지 않고 정지

판정: 구조 파서는 통과했지만 레코드 확장과 후속 오프셋 이동 때문에 런타임
실패했다. 이 파일을 다시 스테이징하거나 패킹하지 않는다.

### 5.3 현재 복구된 RomForge unpacked

현재 `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs`:

- `demo.dat`
  - 영문 피벗 size-neutral 진단본
  - 457행 중 323행 선택
  - `772,935,680`바이트
  - SHA-256 `EC0DC24CAF2F9544F2A69B4340A49923BA0862AE6A86846727C5CA69223C0443`
- `movie.dat`
  - 영문 피벗 검토 후보 51행 중 40행 선택
  - `229,376`바이트
  - SHA-256 `8E6F5FBC26976B60DC56C90C4A869D88EF4990891718F9FE39FD25F3BAC4BCEE`
- `codec.dat`
  - SHA-256 `D94BFA91B720FEDD6D2827566A7AA31DF4DCE98917BC206FF2E19FE6BD0E32F1`
- `stage/r_sna01/resident.hpk`
  - SHA-256 `6D751F2A037FFC468B7501E7F52E77A50AB2275B8F6CE60419E5A5CC945A7B77`
- `stage/r_sna02/resident.hpk`
  - SHA-256 `BB72B8FAB297499859578E48758B54608C79A3CA8C9AEEEEAACE912C44249496`

현재 unpacked의 demo/movie는 PS2 직접 이식 완성본이 아니라 비교/진단본이다.

## 6. Citra 주의사항

Citra는 작업 폴더의 `Citra/config/qt-config.ini`가 아니라 실제로 다음 설정을
사용했다.

`C:\Users\hhlee\AppData\Roaming\Citra\config\qt-config.ini`

GDB 스텁이 켜져 있으면 게임이 부팅 직후 멈춘 것처럼 보인다.

- `use_gdbstub\default=false`
- `use_gdbstub=false`
- 포트 `24689` listener가 없는지 확인

2026-08-03에 실제 AppData 설정의 GDB를 껐고 정상 CPU 진행을 확인했다.

## 7. 다음 작업 순서

1. 골든 CCI와 PS2 원본 ISO를 보존하고 해시를 다시 확인한다.
2. PS2 쪽 movie/demo 공식 한글 데이터가 어느 컨테이너/레코드에 있는지
   추출 목록을 만든다.
3. 3DS movie/demo의 type-1 영문 엔트리와 PS2 공식 한글을 장면·순서·문장
   기준으로 대응시킨다. 영문 피벗 매칭 자료는 위치 힌트로만 사용한다.
4. movie/demo 렌더러가 codec HPK 정적 `81/82` 글꼴을 참조할 수 있는지
   GDB로 확인한다.
5. 참조 가능하면 PS2 corpus 빈도 기반 정적 토큰 매핑을 공유한다.
6. 참조 불가능하면 각 레코드의 기존 로컬 글꼴 슬롯과 donor 공간만 사용해
   PS2 글리프를 변환·배치한다.
7. 제외되는 공식 문장은 레코드별 부족 바이트와 부족 글리프를 보고하고,
   원문 의미를 유지하는 축약안을 별도로 만든다.
8. 크기·레코드 경계 검증을 통과한 후보만 새 CCI 이름으로 패킹한다.
9. movie/demo/TOM을 동시에 변경하지 말고 한 계층씩 런타임 검증한다.

## 8. 보존 자료

- PS2 ISO: `메탈 기어 솔리드 3_한글.iso` (미추적, 삭제 금지)
- PS2 추출: `analysis/ps2_korean/MGS/`
- codec 상세 조사: `docs/ps2-korean-port-2026-08-02.md`
- 골든 기록: `analysis/ps2_korean/golden_real3ds_2026-08-02/`
- 실패/복구 기록: `analysis/ps2_korean/FULL_DEMO_MOVIE40_TEST.md`
- TOM 도구: `tools/mgs3_ps2_tom_bitmap_port.py`

로컬 SQLite DB, vendored Capstone, ISO 및 `analysis/`의 대형 산출물은 Git에
넣지 않는다. 코드와 문서만 커밋한다.

## 9. PS2 STAGE 공식 한국어 추출 진전 (2026-08-03)

`STAGE.DAT`의 156개 스테이지를 모두 추출했다. 기존 Python 추출기는 영상
스테이지의 plain PSQ 그룹(`7F000010`, `7F000005`, `7F000004`)을 zlib
그룹으로 오인했으며, `tools/mgs3_ps2_stage_extract.py`에 해당 그룹 처리와
`--list`, `--all`을 추가했다.

각 스테이지의 `7f000002_180720.02`는 MGS3 GCX이며 기존 `GcxRecord`로
156/156개가 모두 파싱된다. 여기에는 PS2 공식 한국어 토큰과 24×24 로컬
글꼴이 들어 있다. 전체 텍스트 후보는 90,216개지만 공용 시스템 문장이
여러 스테이지에 반복된다. 바이트 동일 중복을 제거하는 기준으로 한
스테이지에만 존재하는 후보는 1,548개다.

재현 명령:

```powershell
python tools/mgs3_ps2_stage_extract.py `
  analysis/ps2_korean/MGS/STAGE.DAT `
  analysis/ps2_korean/stages --all

python tools/mgs3_ps2_stage_text_catalog.py `
  analysis/ps2_korean/stages `
  analysis/ps2_korean/korean_token_map_paragraph_span24.json `
  analysis/ps2_korean/stage_text_unique.csv --stage-specific-only
```

카탈로그는 stage, GCX resource index, 원시 토큰, 현재 해독문, 로컬 글리프
참조 수를 보존한다. `81/82/83` 공용 토큰은 확인된 매핑만 유니코드로
해독하고, 미확인 공용 토큰은 `<Sxxxx>`, 레코드 로컬 글리프는 `<Lnnn>`로
남겨 추측 번역이 공식 원문에 섞이지 않게 한다.

다음 작업은 `stage_text_unique.csv`의 장면 순서를 3DS `demo.dat` type-1
영문 카드 순서와 연결하고, PS2 로컬 글리프 비트맵을 Unicode로 확정해
공식 한국어 build CSV를 생성하는 것이다. 플랫폼별 조작법 차이는 사용자가
별도로 처리하므로 이 자동 이식 단계에서는 별도 교정하지 않는다.
