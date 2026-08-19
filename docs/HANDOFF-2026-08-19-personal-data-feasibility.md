# PERSONAL DATA layout feasibility handoff

상태: READ-ONLY / DRY-RUN 분석 완료. master, staged codec.dat, production codec.dat은 수정하지 않았다.

## 결론

clean English의 PERSONAL DATA control stream `<0A>` × 9 + `<00>`를 복원하는 구조 자체는 확인되었다. 현재 한국어가 비어 있지 않은 47 canonical 행은 44행 `PASS`, 3행 `SHORTEN`이며 `HARD`는 0행이다. 나머지 77행은 current_korean이 공란이어서 자동 보존/필드 대응을 확정할 수 없는 `HUMAN`이다.

따라서 판정은 **B에 가장 가까움**이다. 비공란 47행 기준으로는 3 canonical 행만 소폭 축약 검토가 필요하다. 공란 77행까지 포함한 124행 전체를 “현재 한글 유지”만으로 자동 확정할 수는 없다.

## 수치

- canonical 행: 124
- unique location: 27,132
- dry-run expand: 47 unit → 25,401 unit, master row expansion 45
- 복원 control sequence: 전 location 25,401개가 `<0A>` × 9 + `<00>`
- PASS: 44
- SHORTEN: 3
- HARD: 0
- HUMAN: 77
- byte 계산상 예상 failing location: 1,780
- byte 계산상 예상 failing record: 2
- canonical 최악 deficit: 11 bytes
- canonical deficit 합계: 18 bytes
- 신규 glyph 필요: 없음

SHORTEN 대상은 다음과 같다.

| GCX/resource | location 수 | 현재 bytes | 복원 후 bytes | 최저 slot | deficit |
|---|---:|---:|---:|---:|---:|
| 28/21 | 680 | 142 | 150 | 139 | 11 |
| 445/7 | 420 | 136 | 144 | 138 | 6 |
| 28/18 | 680 | 132 | 140 | 139 | 1 |

## glyph gate

전체 기존 expanded translation에 separator-only scratch를 병합한 뒤 clean English codec.dat를 authority로 사용해 기존 capacity checker를 실행했다.

- GCX records: 2,288
- ready records: 2,288
- failing records: 0
- total glyph slot deficit: 0
- new glyph: 없음

이 glyph gate 결과와 byte-slot 결과는 서로 다른 검사다. glyph pool은 통과하지만, 위 3개 canonical 위치는 fixed byte budget에서 separator 9개 복원분만큼 여유가 부족하다.

## 산출물

- `docs/evidence/2026-08-19-personal-data-feasibility/personal-data-layout-feasibility.csv`
- `docs/evidence/2026-08-19-personal-data-feasibility/personal-data-layout-feasibility-summary.json`
- `docs/evidence/2026-08-19-personal-data-feasibility/personal-data-expand-report.json`
- `docs/evidence/2026-08-19-personal-data-feasibility/personal-data-full-capacity-report.json`
- `docs/evidence/2026-08-19-personal-data-feasibility/personal-data-clean-authority-capacity-report.json`
- `tools/mgs3d_personal_data_feasibility.py`
- `tools/mgs3d_personal_data_capacity_dryrun.py`

scratch JSON은 분석용이며 production 산출물이 아니다. 실제 수정은 승인 후에도 canonical 124행 단위로만 진행해야 한다.

## 다음 승인 후 작업

1. SHORTEN 3행의 기존 프로젝트 용어 정책을 확인한다.
2. HUMAN 77행은 공란 대응 정책을 별도로 결정한다.
3. 그 후에만 master canonical 수정안을 만들고 expand → byte capacity → build 순서로 검증한다.

이번 단계에서는 번역문, master, staging, build, CCI, CPP, commit/push를 변경하지 않았다.
