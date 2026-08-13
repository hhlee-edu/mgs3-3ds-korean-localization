# MGS3D PS2KO Citra 런타임 스모크 테스트 (2026-08-03)

## 대상

- Citra Nightly 2104 (`HEAD-0ff3440`)
- 격리 portable 환경: `analysis/citra_smoke_runtime/`
- 주력 CCI: `analysis/ps2_korean/MGS3D_PS2KO_191_FIXED_TEST_Repack.cci`
- 대조 CCI: `analysis/ps2_korean/MGS3D_PS2KO_165_FIXED_FALLBACK_v3.cci`

기존 AppData 설정과 세이브는 사용하거나 변경하지 않았다. 실행 환경에는 별도의
`user/` 디렉터리를 두었다.

## OpenGL 결과

191 빌드와 165 빌드는 모두 약 6초 후 같은 방식으로 종료되었다. 두 로그는 시간값을
제외하면 게임 초기화 경로가 사실상 같았고, 두 실행 모두 Windows Application Error에
다음 충돌이 기록되었다.

- faulting module: `nvoglv64.dll`
- exception: `0xc0000005`
- fault offset: `0x0000000001568dbd`

따라서 이 종료는 191 정적 글리프 구성이나 DAT 크기 차이로 생긴 빌드별 실패가 아니라,
이 PC의 NVIDIA OpenGL 드라이버 경로에서 재현되는 Citra 충돌이다.

보존 로그:

- `analysis/citra_smoke_runtime/citra_log_191.txt`
- `analysis/citra_smoke_runtime/stderr_191.log`
- `analysis/citra_smoke_runtime/stderr_165.log`

## Vulkan 결과

격리 설정의 `[Renderer] graphics_api`를 `2`(Vulkan)로 바꿔 191 빌드를 실행했다.

- Citra가 Program ID `0004000000081E00`을 읽었다.
- Vulkan 장치와 파이프라인 초기화가 완료되었다.
- DSP 펌웨어 로드와 애플리케이션 DSP 초기화가 완료되었다.
- OpenGL 실행에서 발생한 `nvoglv64.dll` 충돌은 재현되지 않았다.
- 프로세스는 30초 제한까지 계속 살아 있었고 테스트가 종료시킨 것이다.
- Citra 로그에 `<Critical>` 항목은 없었다.

보존 로그:

- `analysis/citra_smoke_runtime/stderr_191_vulkan.log`

이 결과는 CCI 복호화/로딩과 게임 초기 실행이 성공하고, 수정된 고정 크기 이미지가 즉시
거부되거나 초기 로드 중 종료되지 않는다는 증거다. 다만 화면을 직접 확인하지 않았고
코덱·데모·무비의 모든 수정 레코드를 실제 재생한 것은 아니므로, 전체 이식의 최종 런타임
검증으로 간주하지 않는다.

## 남은 런타임 게이트

1. 실기 또는 화면을 확인할 수 있는 Vulkan Citra에서 타이틀 화면 진입을 확인한다.
2. 신규 세이브로 게임을 시작해 `codec.dat`, `demo.dat`, `movie.dat`의 대표 수정 구간을
   각각 재생한다.
3. 한글 글리프 모양, 줄바꿈, 누락 문자와 진행 정지를 확인한다.
4. 가능하면 191 빌드를 우선 사용하고, 글리프 페이지 문제일 때만 165 fallback과 비교한다.

구조 검증(전체 CCI 크기, 내장 파일 해시/크기, GCX 및 movie/demo 레코드 경계)은 별도의
빌드 verifier 결과가 권위 있는 증거다. Citra 스모크 테스트는 그 구조 검증을 대체하지 않는다.

## 실기 결과 추가

사용자가 `MGS3D_PS2KO_191_FIXED_TEST_Repack.cci`를 실기에서 실행했다. 오류 없이 진행됐고,
표시된 한글 부분은 모두 정상 렌더링됐다. 초반에는 영어로 남은 문장이 상당수 확인됐다.
따라서 191 슬롯 확장 자체와 현재 한글 글리프 렌더링은 통과로 취급하며, 다음 단계는
`codec-untranslated-review.csv`에서 초반 미선택 공식 한글 후보를 우선하는 작업이다.
