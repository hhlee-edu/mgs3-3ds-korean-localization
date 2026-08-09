# MGS3 3DS 한글화 인계

## 최우선 목표

현재 목표는 새 번역을 만드는 것이 아니라 **PS2 정식 한글판의 텍스트와
글꼴 자산을 3DS판에 이식하는 것**이다. 영문-한글 피벗 CSV는 매칭 조사와
진단용으로만 사용한다. 이를 PS2 공식 이식 완성본으로 취급하지 않는다.

**상세 현황과 재개 절차는 `docs/WIKI.md`를 먼저 읽는다.** 날짜별
handoff 문서들과 내용이 어긋나면 `WIKI.md`가 우선한다 (2026-08-07부터
캐노니컬 참조문서로 지정, 역사 기록은 `WIKI.md` 8절 색인 참고).

**다음 세션은 여기부터 시작한다: `docs/session-handoff-2026-08-09.md`**
(가장 최근 세션, 08-08 밤부터 08-09 새벽까지). 이 세션에서 나온 것:
demo.dat 오프닝(파키스탄 상공) 5줄 실배포, GCX53 정적 스캔 inconclusive
결론, **GDB 동적 디버깅 성공 레시피 확정**(`feedback_citra_azahar_gdb_debugging.md`
필독 — 포트 프로브가 세션을 죽인다는 게 핵심 교훈), Azahar 소스
instrumentation 준비 완료(빌드는 보류), NAS LLM 번역 작업 진행 중
(다음 세션 최우선: 결과 회수+검수).

2026-08-07 진행: codec GCX 배치1(163개) 완전 클리어, PS2 원본
`MOVIE.DAT`/`DEMO.DAT`를 처음 추출해 하드섭 비디오임을 확인, 진짜 일본어
3DS 원본으로 재확인한 결과 지금 작업 기준인 "서구 다국어 movie.dat 구조"가
이 프로젝트 자체 재구성물임을 발견, movie.dat 첫 실빌드에서 "..." 과다
노출 회귀 발견·수정, demo.dat 배포 직전 라이브의 기존 558글리프 작업을
덮어쓸 뻔한 것을 발견해 중단, CCI 크기 이상(movie.dat 크기와 정확히 일치)
발견, 저장소 대청소(~37GB 아카이빙). 상세는 `docs/session-handoff-2026-08-07.md`,
요약은 `docs/WIKI.md` 2~4절.

**다음 세션 시작 시 반드시 읽을 것:** movie/demo 빌드 전 항상 확인해야 할
안전 체크리스트가 `docs/WIKI.md` 최상단 박스와 4.6절에 있다 — 베이스
파일 vs 라이브 파일 글리프 비교, 기존 로컬 글리프(`\x90`) offset 보존,
"..." 리터럴 금지.

2026-08-05 진행: `PS2대응없음`(PS2 대응 없는 위치) 수기 번역 720행을
마스터 리뷰 CSV에 병합했다. 이어서 도너(fr/es) 삭제 + 용량 재확보
방식으로 2,147개 번역을 실제 RomForge `codec.dat`에 반영했다(구조
검증 통과, 실기/Citra 검증은 아직). 상세는
`docs/session-handoff-2026-08-05.md` 참고 — **CCI 패킹 전 반드시
"중요 경고" 섹션을 읽을 것.**

## 절대 조건

- `codec.dat`, `movie.dat`, `demo.dat`, HPK의 원본 파일 크기를 유지한다.
- 내부 레코드 경계와 이후 레코드 오프셋을 이동하지 않는다.
- 크기가 달라진 산출물은 구조 파싱에 성공해도 패킹하거나 테스트하지 않는다.
- 실기 구동 성공본
  `C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack_______.cci`
  를 덮어쓰지 않는다.
- TOM은 movie/demo 원인 분리가 끝날 때까지 제외한다.

## 확인된 상태

- PS2 codec/HPK 정적 글꼴 이식 경로는 구현되어 있고 첫 공식 라디오 문단은
  런타임 검증을 통과했다.
- bulk codec/HPK 고정 크기 후보가 준비되어 있다.
- movie/demo는 별도 레코드 및 로컬 page-3 글꼴 형식이다. codec용 정적
  글꼴 해결책이 아직 이 경로에 연결되지 않았다.
- 영문 피벗 고정 크기 진단 후보는 demo 457행 중 323행, movie 51행 중
  40행을 선택한다. 이것은 PS2 공식 이식 결과가 아니다.
- demo 457행을 `--grow-records`로 강제 적용한 파일은 첫 영상이 나오지 않고
  정지했다. 실패 원인은 파일/레코드 확장으로 판단하며 재사용하지 않는다.

## 현재 RomForge unpacked (2026-08-09 갱신, 이전 내용은 stale이었음)

- `demo.dat`: PS2 공식 매칭 기반 오프닝 5줄(파키스탄 상공 포함) 실배포,
  `--fixed-layout-reclaim`로 빌드, 개별 subtitle offset/capacity 전수
  검증 통과, 씬 경계 불변 확인,
  SHA-256 `50026766AA0308C2289D4CA668F4D4975FBCE5626E611431FCCEEECDA38938AF`
  — **아직 실기/Citra 테스트 안 됨.**
- `codec.dat`: 2026-08-08 재빌드분 라이브,
  SHA-256 `19FF34D1380E1AFD3D19DFBD0C9C3DF091FBFB5743E09189B5DC943A85BF6267`
  (`project_mgs3d_donor_reclaim_build.md` 참고)
- `movie.dat`: 이번 세션 미변경 (마지막 알려진 상태는
  `docs/session-handoff-2026-08-08.md` 참고, 실배포된 새 빌드 없음)

`--size-neutral-reclaim`은 실기 크래시 확인 후 폐기됐다 —
`feedback_mgs3d_movie_demo_size_neutral_reclaim_unsafe.md` 참고, 앞으로
movie/demo 빌드는 `--fixed-layout-reclaim`만 사용한다.

## 커밋과 로컬 산출물

- PS2 고정 레이아웃 기반: `7451f1b`
- PS2 TOM 비트맵 복사 도구: `fcdda0e`
- 인계 기록: `40b9d2d`, `14541df`
- 대형 ISO, SQLite DB, vendored Capstone 및 `analysis/` 산출물은 의도적으로
  미추적 상태다.
