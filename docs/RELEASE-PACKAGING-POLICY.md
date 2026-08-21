# 릴리즈/배포 방침 (2026-08-19 확정)

이 문서가 **배포 관련 결정의 기준**이다. 다른 문서와 충돌하면 이 문서가 이긴다.
결정 주체는 사용자이며, 여기 적힌 내용은 사용자가 확정한 방침을 옮긴 것이다.

관련 결정 ID: [`wiki/Decisions.md`](../wiki/Decisions.md) **DEC-019 ~ DEC-022**.

> **승인 규칙 (별개이지만 항상 같이 적용).** 이후 **모든 버전은 사용자 승인 없이
> 올리지 않는다.** 빌드·스테이징·문서화까지는 진행하되, 배포·commit/push는 승인 후에만.

## 0. 현재 검증 상태

| 항목 | 상태 |
|---|---|
| CPP 기본 활성화 빌드 (`code.bin` 24바이트 변경) | **Azahar에서 성공 확인** — 오른쪽 스틱 및 CPP 동작 정상 (2026-08-19) |
| 해당 `code.bin` | `4e693f32b1b20d99…` (이전 `b9514ec5…`, 백업 `Romforge\archive\pre-cpp-20260819\`) |
| 같이 검증된 한글화 데이터 | `codec.dat b29807f8825ea7ae…` (v0.90 말투 교정본) |
| 패치 상세 | [`v0.9-cpp-test-staging-2026-08-19.md`](v0.9-cpp-test-staging-2026-08-19.md) |
| **실기 CPP 경로** | **2026-08-21 확인** — 실기에서는 게임 옵션의 확장 슬라이드 패드를 켜면 C스틱이 동작한다. 즉 **CPP 코드 패치는 에뮬 전용 우회책**이고, 실기 빌드에는 넣을 필요가 없다 |

즉 **에뮬용 산출물의 기술적 실현 가능성은 검증이 끝났다.** 남은 것은 언제·어떤
형식으로 포장하느냐다.

## 1. 개발 중 — 트리는 하나만 유지한다

- 개발 중에는 **실기용/에뮬용 staging을 분리하지 않는다.**
- **현재 최신 staging 하나**를 계속 개발·검수 기준으로 사용한다.
  (`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0`)
- 실기판/에뮬판 **두 트리를 따로 관리하지 않는다.**
- 개발 과정에서 두 버전을 각각 수정해 **서로 다른 번역/renderer 버전이 생기는 것을
  금지한다.** 이 금지가 이 방침의 핵심이며, 분기는 오직 최종 단계에서만 일어난다.

**개발 staging의 기본 상태는 CPP-on이다 (2026-08-19 확정).** 개발·실기 검수 편의를
위해 개발 트리에는 CPP default-on 패치를 적용해 둔다. 검수는 이 하나의 트리에서 한다.

> CPP 패치를 다시 적용할 때는 **반드시 `--output`으로 workdir를 staging 밖으로 뺄 것.**
> `mgs3d_cpp_default_patch.py`는 `code.blz.bin` / `code.decompressed.bin`을 workdir에
> 남기는데, workdir 기본값이 `--code`의 부모라 staging exefs를 그대로 지정하면
> 중간 산출물이 스테이징에 쌓인다. 스테이징 exefs에는 `banner/code/icon/logo`만 있어야 한다.

## 2. 최종 릴리즈 — 공통 기반에서 두 산출물

```
clean original
      │
      ▼
확정 한글화 공통판  (동일한 번역 데이터 · renderer · code)
      ├────────────────────────────► CPP-off 호환판   (CPP 강제 활성화 없음)
      └── + mgs3d_cpp_default_patch.py ──► CPP-on 판 (New 3DS 계열 + 에뮬레이터)
                (마지막 단계에서만 적용)
```

- **공통 기반**은 동일한 최종 한글화 데이터/renderer/code다.
- **CPP-off 호환판**은 CPP 강제 활성화가 없는 기본판이다. CPP 미장착 구형 3DS를 위한
  호환 산출물이다.
- **CPP-on 판**은 최종 공통판에 `tools/mgs3d_cpp_default_patch.py`의 CPP 기본 활성화
  변경을 **마지막 단계에서** 적용한 별도 산출물이며, New 3DS 계열과 에뮬레이터를
  대상으로 한다.
- **사용자용 범용 CPP 패처는 제공하지 않는다.** 두 산출물 모두 완성된 배포 패치 형태다.
- 최종적으로 사용자가 고를 수 있도록 **실기용 패치와 에뮬용 패치를 각각 완성된
  배포 패치 형태로** 제공한다.

## 3. CPP 변경의 위치 — 독립적인 옵션 레이어

- CPP 변경은 현재 확인된 **`code.bin` 24바이트 변경**이다
  (`0x0010AEF4`의 6워드, 상세는 [`v0.9-cpp-test-staging-2026-08-19.md`](v0.9-cpp-test-staging-2026-08-19.md) §2).
- **한글 번역 데이터와 독립적인 옵션 레이어로 취급한다.** 번역 작업이 이 변경에
  영향을 주거나 받지 않는다.
- 적용 도구는 스테이징된 `code.bin`을 입력으로 받아 재실행해도 안전하므로
  (idempotent), 최종 산출물이 CCI든 .3ds든 **마지막 단계에 한 번 적용**하면 된다.
- 실기용에 이 변경을 넣지 않는 이유: preset 3은 ZL/ZR과 오른쪽 스틱을 전제하므로
  **CPP 미장착 구형 3DS에서는 조작이 망가진다**
  ([`cstick-default-scheme-feasibility-2026-08-19.md`](cstick-default-scheme-feasibility-2026-08-19.md) §5).

## 4. 배포물에 만들지 않는 것

- 사용자에게 **별도의 범용 패처 프로그램은 제공하지 않는다.**
- 사용자가 **체크박스로 옵션을 조합하는 패처 형태는 현재 배포 계획에 없다.**
- **CPP만 따로 적용하는 사용자용 도구/세이브 패처는 기본 배포물로 만들지 않는다.**
  (`tools/mgs3d_save_tool.py`의 `enable-cpp`/`disable-cpp`는 **내부 개발·검증용**으로
  남는다. 배포 대상이 아니다.)
- 남의 세이브 파일 동봉(RT37 세트)도 배포 계획에서 빠진다 — 에뮬용 산출물이
  그 필요 자체를 없앴다.

## 5. 릴리즈 생성 원칙

1. 최종적으로 **하나의 clean baseline에서 출발한다.**
2. **같은 확정 한글화 빌드**로부터 실기판과 에뮬판을 생성한다.
3. **에뮬판만** 마지막 단계에서 CPP default patch를 적용한다.
4. 두 버전의 차이가 **CPP 관련 변경 외에는 없음을 SHA/diff로 검증한다.**
5. 개발 과정에서 두 버전을 별도로 수정하는 것을 **금지한다**(§1).

### 4번 검증의 구체적 형태

릴리즈 직전에 두 산출물을 놓고 다음을 전부 통과해야 한다.

| 검사 | 기대값 |
|---|---|
| `romfs/` 전 파일 SHA-256 | **완전 일치** (codec/movie/demo/그 외 전부) |
| `exheader.bin` SHA-256 | **일치** (CPP 패치는 크기를 바꾸지 않는다) |
| `code.bin` BLZ 해제 후 diff | **`0x0010AEF4..0x0010AF0B` 구간 외 차이 0** |
| 그 구간의 실기판 6워드 | 원본 시퀀스 (`E3500000 0A000004 E3A00000 EB0083A1 E320F000 E320F000`) |
| 그 구간의 에뮬판 6워드 | 패치 시퀀스 (`E5960000 E5901008 E3811001 E5801008 E5900138 EAFFFFF3`) |
| 글리프 패치 6곳 · 트램폴린 `0x0087F8C4..0x008838C3` | 두 판 **동일** |

`mgs3d_cpp_default_patch.py --verify-only`가 임의의 `code.bin`이 어느 쪽인지
(`unpatched` / `already patched` / `UNKNOWN`) 판정해 준다.

## 6. 아직 확정하지 않은 것

- **최종 패치 형식은 미확정.** xdelta / BPS / LayeredFS / RomFS 등 실제 배포 형식은
  **최종 빌드가 확정된 뒤** 결정한다.
- 지금 우선하는 것은 **clean original → 최종 공통 한글판을 재현할 수 있는 현재 빌드
  파이프라인의 보존**이다. 파이프라인을 깨는 변경은 배포 형식 논의보다 우선해서 막는다.

## 관련 문서

- [`v0.9-cpp-test-staging-2026-08-19.md`](v0.9-cpp-test-staging-2026-08-19.md) — 현재 스테이징 내용, 패치 상세, 롤백
- [`cstick-default-scheme-feasibility-2026-08-19.md`](cstick-default-scheme-feasibility-2026-08-19.md) — 코드 근거, 구형 3DS 제약
- [`citra-extrapad-applet-freeze-2026-08-17.md`](citra-extrapad-applet-freeze-2026-08-17.md) — 애초에 이 옵션 레이어가 필요한 이유
- [`cstick-save-patcher-2026-08-18.md`](cstick-save-patcher-2026-08-18.md) — 세이브 기반 대안 (내부용으로 격하)
- [`cstick-save-distribution-2026-08-17.md`](cstick-save-distribution-2026-08-17.md) — RT37 세이브 동봉안 (배포 계획에서 제외)
