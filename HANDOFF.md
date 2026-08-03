# MGS3 3DS 한글화 인계

## 최우선 목표

현재 목표는 새 번역을 만드는 것이 아니라 **PS2 정식 한글판의 텍스트와
글꼴 자산을 3DS판에 이식하는 것**이다. 영문-한글 피벗 CSV는 매칭 조사와
진단용으로만 사용한다. 이를 PS2 공식 이식 완성본으로 취급하지 않는다.

상세 현황과 재개 절차는
`docs/ps2-port-handoff-2026-08-03.md`를 먼저 읽는다.

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

## 현재 RomForge unpacked

- `demo.dat`: 영문 피벗 size-neutral 323행 진단본,
  `772,935,680`바이트,
  SHA-256 `EC0DC24CAF2F9544F2A69B4340A49923BA0862AE6A86846727C5CA69223C0443`
- `movie.dat`: 영문 피벗 검토 40행 진단본,
  `229,376`바이트,
  SHA-256 `8E6F5FBC26976B60DC56C90C4A869D88EF4990891718F9FE39FD25F3BAC4BCEE`

이 구성은 PS2 이식 목표의 최종 후보가 아니다. 다음 작업은 PS2 공식
movie/demo 대응 자료를 직접 매칭하는 것이다.

## 커밋과 로컬 산출물

- PS2 고정 레이아웃 기반: `7451f1b`
- PS2 TOM 비트맵 복사 도구: `fcdda0e`
- 인계 기록: `40b9d2d`, `14541df`
- 대형 ISO, SQLite DB, vendored Capstone 및 `analysis/` 산출물은 의도적으로
  미추적 상태다.
