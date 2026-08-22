# HANDOFF

> 읽는 순서 (R11): `README.md` → `wiki/Home.md` → `wiki/Current-State.md` → 이 파일.
> 기술 지식은 wiki에, 여기는 여섯 가지만 (R12).

## 1. 현재 목표

v0.93c를 CCI로 리팩해 실기 검증. 번역 검수는 도구가 전수로 훑는 체제로 전환 완료.

## 2. 이번 세션(2026-08-22)이 한 것

- **교차 검증 도구 둘** — `tools/mgs3d_crossvalidate.py`(검출기 D1~D9,
  codec/movie/demo/vox), `tools/mgs3d_vox_donor_check.py`(vox 도너 4언어)
- **적용** — codec 정본 377건(2026-08-17 full-QA 제안) + 교차검증·실플레이 24건
  + vox 자막 줄바꿈 30건
- **스테이징** — 네 컨테이너 전부. 두 트리 924 files, 바이트 총계 불변
- **정리** — 백업 41개를 `10_master/archive/backups/`로, 문서를 `docs/`로
  (translation/ 아래는 gitignore라 저장소에 안 남는다), `release-v0.93c/` 매니페스트
- v0.93c 커밋·푸시 (`8818576`)

## 3. 막혀 있는 곳

없음. 다만 아래 둘은 사람이 정해야 한다.

- **화자별 어투 정책** — Zero/Tom의 존댓말이 전반에 섞여 있어 한 줄씩 못 고친다
- **`29/23`** — "Shagohod is ours!"가 예산 17B라 고유명사를 뺀 「이건 우리 것이다!」로 갔다

## 4. 읽을 wiki 페이지

`Current-State.md`(현황·Known Issues) → `Conventions.md`(R1~R12) →
`Translation.md`(정본 경로) → `Build-System.md`

도구 문서: `docs/crossvalidate.md`, `docs/vox-donor-check.md`
**자료를 찾기 전에 `docs/SOURCES.md`부터 볼 것** — 2026-08-22에 영문 대사집이
`analysis/`에 있는데 못 찾아 외부 수집을 시도한 일이 있다.

## 5. 다음 작업

1. CCI 리팩 + 실기 검증. **리팩 전에 골든 이름 충돌을 피할 것** — `Romforge/output/`이
   밑줄 6개까지 차 있어 다음 repack이 골든의 파일명(7개)을 쓴다 (R6)
2. 워크리스트 A 2건 / B 55건 검토
   (`translation/10_master/review/crossvalidate/worklist.csv`)

## 6. 주의

- **`errors: []`는 "할 일 없음"이 아니다.** 적용 기록만 있고 바이너리에 안 실린
  5건이 있었다
- **byte-fit PASS 기록은 바이너리가 바뀌면 재검증할 것.** 08-17 PASS 3건이 지금 FAIL
- **PERSONAL DATA는 마스터에 한국어가 있지만 바이너리는 영문이 결정 사항.**
  단순 재빌드가 되돌린다 — `40_build_input/2026-08-22/hold-locations.json`으로 제외
- **`5C 6E`를 파일 전체에서 바이트로 세지 말 것.** 한글 토큰 `특`(845C)이 0x5C를
  꼬리 바이트로 쓴다. clean/이전 빌드와 상대 비교할 것
- **크기로 동일성을 판단하지 말 것 (R4).** 항상 SHA-256
