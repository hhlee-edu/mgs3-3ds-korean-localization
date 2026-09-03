# HANDOFF

> 읽는 순서 (R11): `README.md` → `wiki/Home.md` → `wiki/Current-State.md` → 이 파일.
> 기술 지식은 wiki에, 여기는 여섯 가지만 (R12).

## 1. 현재 목표

**지금 1순위는 standalone 패처 구현이다.** Luma LayeredFS 배포 경로는 **중단**했고
(2026-08-28 사용자 결정), 리팩 CCI 경로가 다시 유일한 배포 경로다. 그 경로를 자동화할
수 있는지는 **R1 에서 실기로 확인됐다 — HARDWARE PASS**(아래).

목표 UX 는 입력 하나로 갈린다.

| 입력 | 산출 | CPP |
|---|---|---|
| **원본 CCI 만** | **1.0 한글판** | **미포함** |
| **원본 CCI + 공식 1.1 Update CIA** | **1.1 한글판** | **포함** |

설계는 [`docs/patcher-design.md`](docs/patcher-design.md).

**구현 1단계 `inspect` 완료 (2026-08-28).** `tools/mgs3d_patcher.py inspect <base> [--update <cia|cxi>]`,
테스트 `tests/test_mgs3d_patcher_inspect.py` **13 PASS**. 읽기 전용이고 아무것도 만들지 않는다.
버전 판별은 **BLZ 해제본 SHA-256** 으로만 한다. 종료 코드 0 지원 / 2 미지원 / 1 IO.

```
Base game : OK
Region    : North America
Title ID  : 0004000000081E00
Update    : Not supplied
Track     : 1.0 without CPP
Result    : Supported
```

**다음 blocker: 복호화된 공식 1.1 update 가 없다.** 보유분
`Desktop/metagear3d/0004000e00081e00 … Update v1.1 ENC.cia` 는 NCCH 가 암호화(crypto_method 0,
NoCrypto 없음)라 exheader/ExeFS 가 암호문이다 — `inspect` 는 이것을 정확히 거부한다.
**1.1 트랙의 정상 경로는 실파일로 아직 검증하지 못했다.** GodMode9 로 설치된 업데이트를
복호화 덤프로 뽑아 주면 닫힌다.

그 다음 순서는 code 단계(해제 → 차분 → 재압축 → 왕복 검증) → 데이터 차분 → 리팩·매니페스트.

번역 쪽은 그대로다: codec/movie/demo가 2026-08-23 검수 후속 조치까지 반영돼 1.0/1.1 양
트리에 스테이징됐고, 정적 검증은 전부 통과했다. 1.1 갈래는 CPP 패치도 얹혀 있다.

### 지금 스테이징된 것 — **v0.94a** (1.0 = `unpacked-v0.93a-staging`, 1.1 = `unpacked`, 양쪽 동일)

| 파일 | SHA-256 (앞 16) |
|---|---|
| codec.dat | `dd103ac2a1a0e94a` (2026-09-01 미번역 338행 종결) — **v0.94a** |
| movie.dat | `4d5cbf8a9865fd63` |
| demo.dat | `0ed26fe41b260ab7` |
| vox.dat | `6788330fe623512f` |

직전 `codec.dat`(`0e510ab6…`)은 `builds/diag-2026-08-27-qa-b006b010/staging-backup/`에,
그 앞(`af7b3769…`)은 `builds/diag-2026-08-26-donor-b004b005/staging-backup/`에,
movie/demo 직전 파일은 `builds/diag-2026-08-24-proper-noun/staging-backup/{v1.0,v1.1}/`에
있다. 되돌리려면 그걸 덮으면 된다.

⚠️ 새 `codec.dat`은 **세 세션째** 실기/아자르에서 표시 확인을 안 했다.

### 배포 정책 — 3분할안은 **보류**, 패처 트랙으로 대체 (2026-08-28)

아래 3분할(LayeredFS) 구조는 **중단됐다.** 정책 문서
[`docs/RELEASE-PACKAGING-POLICY.md`](docs/RELEASE-PACKAGING-POLICY.md) §4·§4.5 와
`wiki/Decisions.md` **DEC-023** 은 아직 그 구조와 「범용 패처는 만들지 않는다」를 담고 있어
**현재 방침과 충돌한다 — 개정이 필요하다**(미실시).

여전히 유효한 것: **1.0 산출물은 CPP-off 여야 한다**(정책 §3). 그런데 현재 1.0 스테이징
이미지는 **CPP-on**(`283211e1…`)이라 **CPP-off 1.0 글리프 이미지가 패처의 선행 산출물**이다.

<details><summary>보류된 3분할 구조 (기록 보존)</summary>

**공통 번역 RomFS + 환경별 1.0/1.1 code 패치**, 세 산출물. 범용 패처는 만들지 않는다.
정본은 [`docs/RELEASE-PACKAGING-POLICY.md`](docs/RELEASE-PACKAGING-POLICY.md) §4,
결정 ID는 `wiki/Decisions.md` **DEC-023** (DEC-022 는 SUPERSEDED).

- 사용자는 **① 공통 RomFS + (② 1.0용 또는 ③ 1.1용 code 패치)** 를 받는다.
  선택 기준은 기종이 아니라 **설치된 `code.bin` 해시**다.
- 경로는 1.0/1.1 공통으로 베이스 TID `/luma/titles/0004000000081E00/`.
  **2026-08-27 실기 확인됨** (아래 T3).
- 1.0 차분은 반드시 **CPP-off 이미지**에서 뽑을 것 — 현재 `unpacked-v0.93a-staging`
  은 CPP-on 이다 (2026-08-27 측정). 1.0 차분은 아직 **미생성**.
- 1.1 CPP 를 배포물에 넣을지는 **미결**. 별도 작업 중.
- 절차서 [`docs/luma-layeredfs-hardware-verification-plan-2026-08-27.md`](docs/luma-layeredfs-hardware-verification-plan-2026-08-27.md) ·
  결과 [`docs/evidence/2026-08-27-luma-layeredfs-hardware/README.md`](docs/evidence/2026-08-27-luma-layeredfs-hardware/README.md)

</details>

#### 실기 검증 현황 — Luma LayeredFS(T3~T10, 중단) + 리팩 파이프라인(R1, 통과)

| 시험 | 구성 | 결과 |
|---|---|---|
| **T3** | `romfs/codec.dat` 만 | ✅ 깨진 글자 — TID 적용 + RomFS overlay 성공 |
| **T4** | + `romfs/stage/…` 169 | 깨짐. T3 과 구별 불가라 아무것도 증명 못 함 |
| **T5 / T5-control** | + `code.bin`(글리프 포트 / 순정 1.1) | ❌ 둘 다 CRASH — `code.bin` 전체 교체 경로 종료 |
| **T6** | `code.ips` | ❌ CRASH. 덤프 판독 결과 **실행 중이던 코드가 1.0** 이었다 |
| **T7** | 공식 1.1 CIA 직접 설치 후 재시험 | ❌ START 즉시 CRASH. **1.1 실행 확인**, 2바이트 글자 그리기 경로에서 사망 |
| **T9 / T10** | 1.1 + `code.ips` (+ 번역 codec / 순정 codec) | ❌ 무전 오픈 시 CRASH / ✅ 정상 |
| **R1** | RomForge GUI 없이 **3dstool 로 리팩** | ✅ **HARDWARE PASS** (2026-08-28) |

**크래시 필요조건은 1.1 glyph code 패치 AND 번역 codec.dat 다.** 순정 codec 텍스트는
`0x80xx` 토큰만 쓰고, 케이브의 한글 분기는 `0x84..0x87`/`0xA4..0xA7` 에서만 열린다.
최소 재현본은 `builds/diag-2026-08-28-codec-minimal-repro/`(무전 한 줄, 케이브 토큰 1개).

**LayeredFS 갈래는 여기서 중단한다.** 남은 H1/H2(스테이지 글리프 페이지 상주 여부)도
그 갈래에서만 의미가 있다.

#### R1 — 3dstool 리팩 파이프라인, **HARDWARE PASS** (2026-08-28)

`Romforge/output/unpacked/partition0`(= v0.94a 소스, 1.1 standalone 트랙)에서
**partition 0 만 3dstool 로 재조립**하고 partition 1/7 은 원본에서 바이트 복사해
CCI 를 만들었다. 정적으로 romfs 916/916 · exefs 바이트 동일 · code 해제본
`26ec9cc5…` 동일 · exheader/plain 동일 · 구조 필드 29/30 일치.

1차 실기는 크래시했지만, **원인은 컨테이너가 아니었다.**

> **SD 의 `/luma/titles/0004000000081E00/` 잔재가 같은 Title ID 로 걸려 이중 패치를
> 일으켰다.** 그 폴더를 치우자 **같은 CCI 가 실기에서 정상 동작**했다.
> `Enable game patching` 이 켜져 있으면 **CCI 로 띄워도** 그 폴더가 적용된다.

따라서 **D1~D4(컨테이너 구조 차이)는 크래시 원인이 아니고 blocker 에서 제외**한다.
D4 정합 후보(`builds/diag-2026-08-28-r1b-d4/`)는 **진단 산출물로만 보존**한다.

증거: [`docs/evidence/2026-08-28-r1-3dstool-repack/README.md`](docs/evidence/2026-08-28-r1-3dstool-repack/README.md) ·
[`docs/evidence/2026-08-28-r1b-d4-fix/README.md`](docs/evidence/2026-08-28-r1b-d4-fix/README.md)

## 2. 세션 기록

> **최신은 15차(2026-08-28)이고 바로 아래에 있다.** 이 절은 시간순이 아니다 —
> **15차(08-28)** → 14차(08-27~28) → 13차(09-01) → 12차(09-01) → 11차(08-31) → 10차(08-30) → 9차(08-29)
> → 8차(08-28) → 7차(08-27) → 6차(08-27) → 5차(08-27) → 1차(08-25) → 2차 → 08-23 → 08-22
> → 어투 정책 → 4차(08-26) → 3차(08-25).

### 15차 (2026-08-28) — LayeredFS 중단, R1 리팩 파이프라인 실기 통과

번역 데이터·`code.bin`·CPP·스테이징 **전부 무변경**. CCI·commit·push 없음.

- **T7~T10 로 크래시 필요조건 확정**: 1.1 glyph code 패치 **AND** 번역 `codec.dat`.
  순정 codec 은 `0x80xx` 토큰뿐이라 케이브 한글 분기가 아예 안 열린다(T10 정상 설명).
  최소 재현본 A/B 제작(`builds/diag-2026-08-28-codec-minimal-repro/`).
- **덤프 3건 판독**: T6=1.0 실행 중 1.1 차분 적용(`.rodata` 로 점프, permission fault),
  T7·R1 1차=1.1 실행 중 2바이트 글자 경로에서 `PC 0x02403FE4` 로 wild jump(동일 서명).
  도구: `tools/mgs3d_crash_identify_build.py`(스택 복귀 주소 `bl`/`blx` 대조로 실행 빌드 판별).
- **사용자 지시로 LayeredFS 배포 경로 중단**, standalone 패처로 목표 전환.
  조사·설계만 `docs/patcher-design.md` 에 정리(구현 없음).
- **R1 실기 통과** — 위 §1 참조. 1차 크래시는 SD 의 Luma 타이틀 폴더 잔재였다.
- 부수 발견: RomForge 가 만든 romfs 는 **sibling chain 에서 23개 파일을 빠뜨린다**
  (name hash table 은 916 전부 온전 → 게임 동작 무영향). romfs 검증은 디렉터리 열거가
  아니라 메타데이터 전수 스캔으로 해야 한다 — `builds/diag-2026-08-28-r1-repack/romfs_tool.py`.
- **패처 `inspect` 구현** — `tools/mgs3d_patcher.py`, 테스트 13 PASS. 실제 리테일 USA
  덤프가 설계 기준값 `10c7d349…` 와 일치함을 확인했고(= clean-tree `code.bin` 이 진짜
  리테일 1.0 임이 확정), 공식 1.1 CIA 는 암호화라 거부된다.
- 덤으로 정리된 것: 오랫동안 「오기」로 적혀 있던 TID **`000400000007A000` 은 실제 일본판**
  이다(`CTR-P-AMGJ`, code `cd05ad71…`). `originals/3ds_pristine` 이 그 일본판이라
  **어떤 기준값으로도 쓰면 안 된다.**

### 14차 (2026-08-27~28) — 배포 정책 3분할 확정 + Luma 실기 검증 T3~T6

번역 데이터는 **한 바이트도 건드리지 않았다.** staging 무변경, CCI·commit·push 없음.

#### 확정한 것 — 배포 구조

**공통 번역 RomFS + 환경별 1.0/1.1 code 패치** 3분할. 범용 패처 없음.
`docs/RELEASE-PACKAGING-POLICY.md` §4 전면 교체(구 §4 → §4.5), §6 교체.
`wiki/Decisions.md` **DEC-023** 신설, DEC-022 SUPERSEDED.
README 에 「배포 구조」 신설 + 「설치」 3단계 재작성.

#### 정정한 것

- **트램폴린 16 KB 표기는 틀렸다.** `0x0087F8C4..0x008838C3`(16,384 B) →
  실측 **예약 816 B**(`0x330`), 기록 폭 815 B, 실변경 647 B. 1.0 `.text` 패딩이
  1,852 B 뿐이라 16 KB 는 물리적으로 불가능. 2곳 정정.
- **`exefs.bin` 은 Luma 게임 패칭 경로에 없다.** 절차서 초판의 추측을 소스 확인으로 삭제.
- **오기 TID `000400000007A000`** → `MGS3D_KOREAN_TOOLKIT.md` 예제에서 제거.
- `docs/evidence/2026-08-21-v1.1-glyph-port/RESULT.md` 에 **정정 배너만** 추가
  (「1.1이 CPP enforcer 재작성」 주장 반증). 본문은 당시 기록이라 그대로 뒀다.

#### Luma 실기 검증 — §1 표 참조

핵심만: **T3 통과**(TID·overlay), **T5/T5-control 둘 다 CRASH**(`code.bin` 전체 교체
경로 문제, 내용 무관), **T6 `code.ips` 준비 완료**.

#### Luma 소스로 확인한 사실 (`LumaTeam/Luma3DS`)

`sysmodules/loader/source/patcher.c` · `loader.c`. 전부 **베이스 program ID** 로
경로 생성, `PATCHGAMES`(= `Enable game patching`) 게이트.

| 경로 | 적용 대상 | 비고 |
|---|---|---|
| `code.bin` | 압축 해제본 | 전체 교체. `fileSize > size` 면 **건너뜀**(크래시 아님) |
| `code.ips` | 압축 해제본 | `PATCH` 헤더, RLE 지원 |
| `code.bps` | 압축 해제본 | — |
| `exheader.bin` | — | 크기 정확히 일치 필요 |
| `romfs` / `locale.txt` | — | — |

적용 순서 **`code.bps` → `code.ips` → `code.bin`**. 버퍼 = `mapped.total_size << 12`
= (1961+65+109)×4096 = **8,744,960 B** — 우리 1.1 이미지와 정확히 일치.
`CodeSetInfo` 크기는 **페이지 수**라 선언 크기 뒤 패딩(케이브 자리)도 매핑된다.

#### 새로 만든 것

- `tools/mgs3d_make_code_ips.py` — `build`/`verify`. 쓴 파일을 **독립 파서로 다시
  적용**해 target 과 바이트 동일하지 않으면 **파일을 남기지 않는다.**
- `builds/diag-2026-08-28-code-ips/code.ips` **882 B** `499096d19debb7cc…`
  7 레코드 / 839 B 커버 / **실변경 671 B**.
  순정 1.1(`68bdf9c5…`) + IPS = `db815f80…` = **2026-08-21 실기 6/6 통과 이미지와
  바이트 동일**(standalone CCI 압축본 `61c34f8a…` 의 해제본).
- 7개 레코드 전부 `.text`(1961p = `0x7A9000`) 안. 최고 접촉 `0x7A8433`.
  **`.rodata`/`.data` 를 안 건드리므로 영역 배치 가정 위험이 구조적으로 없다.**

#### 발견 — 한국어 stage 파일이 순정보다 훨씬 크다

169/169 전부 **+66,360 ~ +417,491 B**. `camera` 는 순정 **77 B** → 한국어 417,568 B.
훅은 글리프 페이지를 `*(font_page_table[2]) + 0x56000`(=352,256 B)에서 찾는다.
LayeredFS 가 **순정 RomFS 메타데이터 크기**로 버퍼를 잡으면 글리프 페이지는 버퍼 밖이다.
대조로 `codec.dat` 은 순정과 크기가 **같다**(T3 이 통과한 이유).
2026-08-13 의 "load size = RomFS 파일 크기" 확인은 **리팩 CCI** 에서 한 것이고,
**LayeredFS 에서 같은지는 확인한 적이 없다.** → H1/H2, T6 이후 판정.

#### SD 카드 준비 폴더 (전부 `builds/`, gitignore 대상)

| 폴더 | 내용 |
|---|---|
| `diag-2026-08-27-luma-t3/sd-root/` | `romfs/codec.dat` |
| `diag-2026-08-27-luma-t5/step1-T4-stage/sd-root/` | `romfs/stage/…` 169 |
| `diag-2026-08-27-luma-t5/step2-T5-code/sd-root/` | `code.bin` (글리프 포트) — **폐기** |
| `diag-2026-08-27-luma-t5-control/sd-root/` | `code.bin` (순정 1.1) — **폐기** |
| **`diag-2026-08-28-luma-t6-ips/sd-root/`** | **`code.ips` — 다음 실기** |

### 14차 (2026-09-03) — **v0.94a1: 3dstool ignore 파일 오류 수정**

- 사용자 리포트: 한글 없는 경로(C 드라이브)로 옮겨도 빌드 시 `IGNORE_3dstool.txt`를
  열지 못했다는 메시지가 뜬다. 단 **1.0/1.1 CCI 생성은 완료로 표시되고 한글도 정상 출력**
  — 기능은 안 깨졌고 메시지만 잘못 떴다.
- 원인: `tools/mgs3d_patcher.py`의 `run_tool()`이 `subprocess.run()`에 `cwd`를 넘기지
  않았다. `3dstool.exe`는 `experiments/repack_tools/3dstool/ignore_3dstool.txt`를
  **실행 파일 자기 경로가 아니라 현재 작업 디렉터리 기준**으로 찾는다 — 패처를 다른
  폴더에서 실행하면 그 디렉터리에 파일이 없으니 open 실패 메시지가 뜬다. 무해하지만
  (파일 스킵 목록 용도) 사용자에게는 에러로 보인다.
- 수정: `run_tool()`에 `cwd=THREEDSTOOL.parent` 추가. 모든 호출부가 절대경로만 넘기므로
  cwd 변경으로 인한 부작용 없음.
- 패처 버전 표시를 **v0.94a1**로 올림 (`tools/mgs3d_patcher_gui.py` TITLE,
  `tools/mgs3d_patcher_gui.spec` 산출물 이름, `README.md` 배지/제목). 스테이징된
  codec/movie/demo/vox 데이터는 이번 변경과 무관 — 위 「지금 스테이징된 것」 표의
  v0.94a 해시 그대로다.
- GUI exe 재빌드는 아직 안 함 — `tools/build_mgs3d_gui_exe.cmd`로 다시 빌드해야 배포용
  실행 파일에 반영된다.

### 13차 (2026-09-01) — **v0.94a 버전업 + 스테이징**

- 사용자가 버전을 **v0.94a** 로 올렸다. 2026-08-21 의 「v0.94/v0.95 없음」 규칙은 여기서 끝난다.
- 스테이징 확인: 1.0 `unpacked-v0.93a-staging` 과 1.1 `unpacked` 가 **네 컨테이너 모두 동일**하다.
  codec.dat `dd103ac2…` / movie.dat `4d5cbf8a…` / demo.dat `0ed26fe4…` / vox.dat `6788330f…`.
  각 978 파일, 3,277,362,819 B (1.1) · 3,277,259,519 B (1.0).
- 릴리스 매니페스트: `builds/release-v0.94a/manifest.json`. v0.93c 이후 **codec.dat 만** 움직였다.
- ⚠️ 스테이징 폴더 이름은 아직 `unpacked-v0.93a-staging` 이다. 사용자 데스크톱이라 임의로
  바꾸지 않았다. 이름을 v0.94a 로 맞추려면 RomForge 경로 설정도 함께 봐야 한다.
- **남은 pool 작업은 사용자 지시로 중단했다.** 조사만 했고 적용한 것은 없다 —
  master·빌드·스테이징 모두 그대로다. 조사에서 확인한 수치는 아래 「중단 시점 pool 현황」 참조.
- **CCI 미생성 · commit 없음 · push 없음.**

#### 중단 시점 pool 현황 (조사만, 미적용)

| pool | 규모 | 조사 결과 |
|---|---:|---|
| 공유 문자열 의미 오류 | 8행 / 1,319 location | `39/23 Yes.`→「왜?」(492곳, **예산 6 B 라 1음절만 가능**), `235/16 Understood.`·`276/13 Got it.`→「알겠나?」(175곳, 확인이 질문으로 뒤집힘), `83/14 Snake!`·`240/38 Snake?`·`443/784 SNAKE!!`→「"스네이크"?」(290곳), `443/595 Really?`→「정말...」(215곳), `241/41 Major!`→「...소령...」(147곳). 고칠 문안은 전부 현재보다 **짧아서** capacity 위험이 없다 |
| MISSION / 임무 | 147행 3,421곳 vs 52행 1,116곳 | 2026-08-31 에 세운 규칙(영어 원문이 대문자로 쓰는 것만 화면 용어)대로면 MISSION 은 드리프트다. mission 은 영어 원문 311회가 전부 소문자이고 codec.dat 에 라벨 리소스도 없다. 바꾸면 **바이트가 줄어든다**(7→4 B) |
| RADIO / MAP / SMOKE | RADIO 22행, MAP 11행, SMOKE 6행 | **뜻이 갈린다.** RADIO 는 무전기(대부분)와 자동차 라디오(`2181/27`), MAP 은 Survival Viewer 메뉴 "MAP"(대부분)과 종이 지도, SMOKE 는 SMOKE GRENADE 아이템과 연기. 행 단위 판정 필요 |
| `<0A>` 바로 뒤 문장부호 | 14행 / 20 location | 전수 목록 확보. `18/14`·`52/28` 「회수하라<0A>. 장소는」 처럼 줄 첫머리에 마침표가 온다 |
| 도너 STRUCTURAL_ONLY 후보 | 45행 / 940 location | 미조사 |
| EVA 비존댓말 잔여 | 37행 | 미조사 |

### 12차 (2026-09-01) — 미번역 338행 전수 분류 + 44행 번역 (`docs/evidence/2026-09-01-untranslated-338/`)

- **338행 전수 분류.** STRUCTURAL 268 / **TRANSLATE 44(전부 번역 완료)** /
  INTENTIONAL_ENGLISH 17 / DONOR 7 / HUMAN 2. **CAPACITY_BLOCKED 0.**
  `review_untranslated` 338 → **294**.
- **`text_kind=identifier` 는 판정 근거가 될 수 없다.** 코퍼스 247행이 그 라벨인데
  **25행은 이미 번역돼 라이브**다(`'...Good.'`→「...좋아.」·`'Finally.'`→「드디어.」·
  `'Four.'`→「넷.」). 길이 휴리스틱이지 구조 표시가 아니다. 분류는 clean tree 원문 ·
  `codec-safe-final.json` · staged codec.dat · hold/override 네 가지에서만 했다.
- **STRUCTURAL 의 대부분은 GCX 13 의 264행**이다. clean 원문이
  `No:N/264 page:N<80>|radio_picture156<80>|rd_ani_<자산키>` 인 코덱 초상 애니메이션 색인이라
  번역하면 자산 조회가 깨진다. 그 밖에 디버그 식별자 3행과 `DUMMY` 1행.
- **영어처럼 보이는 도너 3행을 잡았다** — `443/1344 Ah...` · `443/1723 Snake Eater...` ·
  `1974/25 Ah.` 는 clean tree 에서 앞뒤가 통째로 스페인어 블록이다. `Snake Eater...` 는
  스페인어 분기가 바로 앞줄의 「en persa quiere decir "snake eater"」를 인용한 것이다.
  **문자열만 보고 번역했으면 스페인어 분기에 한국어를 써 넣을 뻔했다.**
  셋 다 `accept` 공백이라 빌드 미사용이고, hold 에는 넣지 않았다(gate 불변식만 흔들고 얻는 안전이 없다).
- **44행은 전부 3언어 짝의 영어 분기**였고 staged 파일에서 주변 줄은 한국어인데 그 줄만
  영어로 나가고 있었다 — 예: GCX 253 늪 대화가 「무엇?」 / `Crocodiles.` / 「악어?」.
- **어투를 추정하지 않았다.** 확정 화자는 화자 정책, UNKNOWN 은 **그 줄이 받는 바로 앞
  번역행의 어투**를 따르고 행마다 근거를 남겼다.
- **9행이 예산에 정확히 딱 맞는다.** 「아무것도.」(11 B) 대신 「아냐.」, 「동의한다.」 대신
  명사형 「동감.」 같은 축약이 있었지만 CAPACITY_BLOCKED 0, 다른 location 희생 0.
- **전용 도구 `mgs3d_codec_apply_translations.py` 를 만들었다.** 기존 `apply_qa_fixes` 는
  「제어 토큰 불변」 가드 때문에 빈 칸→텍스트를 원칙적으로 거부한다. 새 도구는 제어 꼬리를
  **clean 리소스에서 읽어 대조**해 줄바꿈을 넘겨짚지 않고, 예산·글리프·hold·override 를 검사한다.
- gate PASS: dropped 0, failing 0, capacity 2,256-2,256, 글리프 0, layout 0, 크기 불변,
  변경 870 = 예상 870, 의도 밖 0, 역판독 870/870, hold 47,925, override 13, 도너 885,
  충돌 0, coverage PASS. 1.0/1.1 staging 동일. **CCI 미생성·commit 없음·push 없음.**
- ⚠️ 길어진 행 누적은 **476개 그대로**다(이번 44행은 빈 칸을 채운 것이라 영어보다 짧거나 같다).
  실기/Azahar 표시 확인은 **여전히 미완**이다.

### 11차 (2026-08-31) — 용어·표기 pool 종결 (`docs/evidence/2026-08-31-terminology-pool/`)

- **26개 용어 / 221행 통일 + 작은 pool 4개 처리. 6,766 location.**
- **판정 기준을 영어 원문에서 뽑았다.** 영어는 화면에 있는 것만 대문자로 쓴다
  (LIFE 43·CURE 37·FOOD 48 vs 일반명사 `food` 90). 장치 이름은 Title Case 가 100% 일관
  (`Survival Viewer` 88/88·`Circle Pad` 36/36·`Camo Index` 36/36·`Alert Phase` 11/11).
  hornet·cigar·patrol·tunnel·spy 는 대문자가 **0회**다.
- **결정적 발견 — codec.dat 안에 실재하는 버튼 라벨은 `SAVE`·`DO NOT SAVE` 뿐이다**
  (2210·2211/1675·1676, SAUVEGARDER·GUARDAR 과 같은 표). CURE·FOOD·BACKPACK·LIFE·
  STAMINA 는 라벨 리소스가 **0** → 화면에 영어 텍스처로 나오므로 대문자로 두는 관행이 옳다.
  **save 만 우리가 번역**하고 버튼이 「저장」이므로 통화도 「저장」이어야 한다. location 수로는
  SAVE 가 200:35 로 앞섰지만 화면이 다수결을 이긴다.
- **뜻이 다른 것은 통일하지 않았다** — save(구하다/저장)·patrol(순찰/순찰대)·
  cigar(CIGAR/**시가상어**)·hornet(말벌/HORNET STRIPE/발틱 호넷)·food·movie·영화 제목.
  `443/824` "red finned cigar shark" 를 CIGAR 로 바꿀 뻔한 것을 제외 규칙이 막았다.
- **문자열 치환이 왜 위험한지 조사(助詞)가 증명했다.** 「Survival Viewer을」·「말벌으로」·
  「저격총로」·「횃불나」·「THERMAL GOGGLES이군」 다섯 종류가 나왔다. ㄹ 받침은 을/이/은 에서는
  자음, 로/으로 에서는 모음처럼 행동한다. **221행 전부를 눈으로 대조하며 잡았다.**
- **인명은 한글, 지명은 로마자**라는 규칙을 확인하고 Khrushchev→「흐루쇼프」로 맞췄다.
- **작은 pool** — 화자 미확정 4행 중 2행은 문장이 이미 맞아 해소, 2행은 통화 전체 어투 패스가
  필요해 유지. override canonical `2113/28` 은 override 가 막으려는 방향이 아니라 해소했고
  빌드에서 5곳을 직접 열어 override location 만 그대로임을 확인했다. 도너 오라벨 4행
  (`Sin respuesta`→「죄의 응답」 등)은 2026-08-28 의 **정반대 방향** 교정으로 처리했다.
- **손대지 않고 수치만 남긴 것** — MISSION/임무 147:52, RADIO·MAP·SMOKE(각각 뜻이 둘).
- gate PASS: dropped 0, failing 0, capacity 2,256-2,256, 글리프 0, layout 0,
  의도 밖 0, 역판독 6,766/6,766, hold 47,925, override 13, 도너 885, coverage PASS.
  1.0/1.1 staging 반영. **CCI 미생성·commit 없음·push 없음.**
- ⚠️ 길어진 행 누적 **476개**(+60). 최대 +7 B, 전부 SURVIVAL→Survival Viewer 계열.

### 10차 (2026-08-30) — B026-B030 FINAL · **codec 전수 문맥 검수 완료** (`docs/evidence/2026-08-30-qa-b026-b030/`)

- **B026-B030 1,269행 검수. 이로써 8,334 / 8,334 행 = 100%.** `rows_remaining 0`.
  KEEP 894 / REGISTER_ERROR 219 / REFERENCE_IMPROVEMENT 61 / WRONG_MEANING 52 /
  CONTROL_LAYOUT 21 / CONTEXT_DEPENDENT 14 / OVER_COMPRESSED 5 / MEANING_LOSS 3.
  **354행 / 1,140 location 수정** (누적 수정 canonical 1,385행).
- **지배적 계열은 화자 어투가 통째로 뒤섞인 것 (219행).** GCX 1818-1901(튜토리얼 힌트)과
  2173-2207(영화 통화)은 화자 라벨이 대부분 UNKNOWN 이지만 **영어 turn 구조가 화자를 확정한다**
  — 패러메딕이 묻고 스네이크가 답하는 왕복이다. 한국어는 그 안에서 반말·해요체·합쇼체·해라체가
  줄마다, 때로는 **한 줄 안에서** 뒤집혀 있었다(`2175/20` 은 한 문장에 세 가지가 다 있다).
  호칭도 「스네이크님」·「스네이크 씨」·「스네이크야」로 갈렸고, 패러메딕이 스네이크를
  「자네」라고 부르는 행도 있었다.
- **`2080/10`: 뱀에 물렸을 때의 독 경고가 「스네이크에게 물렸을 때」로 읽혔다.**
  일반명사가 주인공 이름으로 끌려간 것으로, B017·B018 의 `the end`→「디 엔드」와
  CHECKPOINT 3 의 The End→「끝이죠?」에 이어 **이 충돌의 세 번째 방향**이다.
  같은 계열로 spider→SPIDER, character→CHARACTER, alien→ALIEN, movie→MOVIE,
  food poisoning→「FOOD 중독」이 나왔다.
- **화면에 영어가 그대로 나오던 두 행** — `2136/12` 는 한국어 칸이 통째로 `Snaaake!`,
  `2210/571` 은 끝에 `SNAKE!!` 가 남아 있었다. hold 도 도너도 아니라 실제로 표시된다.
- **기계 번역 조각 다수** — 앞줄에서 이어지는 절이 「이지만…」·「를 사용하거나…」·「와 맨해튼의…」
  같은 조각으로 남았고, 오타(「편다」·「LIFE가계속」·「프랭클린껜」·「호수가」), 주어 뒤바뀜
  (`2181/26` 깨달은 사람은 아버지인데 「나는」), 뜻 반전(`1771/13` going off→「꺼지는」),
  어휘 오역(inchworm→「지네」, the ship→「배」, volunteers→「자원봉사단」)이 함께 나왔다.
- **capacity 를 실제 safe-select 로 잡았다.** per-location 최소 예산 대조는 보수적으로 36행을
  초과로 잡지만 진짜 제약은 GCX pool 이다. master 사본에 적용해 chain 을 그대로 돌린 dry-run 이
  `dropped 2` 를 냈고 **둘 다 이번에 건드린 행**이었다 — `2136/10` 은 예산 9B 라 롤백,
  `2153/10` 은 축약. **손대지 않은 이웃은 하나도 드롭되지 않았다.** 재실행 후 `dropped 0`.
- **생성기 가드가 `2113/28` 을 거부했다** (override canonical). CHECKPOINT 3 의 `1267/35` 와
  같은 사유로 두 번째다. 글리프 미등록 6건도 예산 점검기가 잡았다.
- **도너 6라운드: 새 누락 없음.** 후보 7행 전부 이미 hold 이거나 `accept` 미설정이다.
  마지막 구멍은 착수 직전에 메운 `1762/39`(hold r5, 47,925곳)였다.
- **검증 도구 두 개 신규** — `mgs3d_codec_fix_budget_check.py`(적용 전 예산·글리프),
  `mgs3d_codec_preservation_verify.py`(clean 대조로 hold/override/도너 절대 검증).
  **delta 검증은 이전 빌드에서 이미 깨져 있던 hold 를 볼 수 없다** — 두 검사는 서로 다른
  실패를 잡는다.
- gate PASS: 변경 1,142 = 수정 1,140 + 도너 clean 복원 2, 역판독 1,140/1,140, 의도 밖 0,
  dropped 0, capacity 2,256-2,256, hold 47,925, override 13, 도너 제외 885, coverage PASS.
  1.0/1.1 staging 반영. **CCI 미생성·commit 없음·push 없음.**
- ⚠️ 길어진 행 누적 **416개**. 실기 확인은 별도 후속 QA 항목.

### 9차 (2026-08-29) — B021-B025 CHECKPOINT 3 (`docs/evidence/2026-08-29-qa-b021-b025/`)

- **B021-B025 1,384행 검수** (누적 7,065/8,334 = **84.8%**). KEEP 1,072 /
  REGISTER_ERROR 224 / REFERENCE_IMPROVEMENT 52 / WRONG_MEANING 16 /
  CONTEXT_DEPENDENT 8 / CONTROL_LAYOUT 6 / OVER_COMPRESSED 5 / MEANING_LOSS 1.
  **290행 / 9,292 location 수정.**
- **EVA 어투가 지배적 계열.** 확정 정책은 EVA 존댓말인데 코퍼스 88행이 아니었고 80행이
  이 구간에 몰려 있었다. 순수 반말 외에 **존댓말 어미에 「나/내/네」를 섞는 형태**와
  **EVA 가 스네이크를 「자네」라고 부르는 형태** 두 가지가 더 있었다. 88 → **44행**.
- **`1534/10`: The End 를 일반명사 「끝이죠?」로 옮긴 행.** B017·B018 의 `the end`→「디 엔드」와
  **정반대 방향의 같은 용어 충돌**이다. 이 계열은 양방향으로 다 일어난다.
- **capacity 를 빌드 전에 잡았다.** 작성한 290행 중 **27행이 location 예산 초과**였다
  (1715/20 은 107B 대 91B). 전부 축약해 27 → 7 → **0** 으로 맞춘 뒤 빌드했고,
  다른 행을 희생시키지 않았다. CHECKPOINT 2 의 드롭 사고를 되풀이하지 않았다.
- **생성기 가드가 세 건을 거부했다** — `1267/35`(override canonical), `1523/20`·`1523/21`
  (검수판 res 번호 오독, 실제는 18·19). 447/13 사고 이후 넣은 batch 범위 가드가 두 번째로 값을 했다.
- gate PASS: 예상 9,292 = 변경 9,292(정확히 일치), 역판독 9,292/9,292, 의도 밖 0,
  dropped 0, capacity 2,256-2,256, hold 47,923, override 13, 도너 482, coverage PASS.
  1.0/1.1 staging 반영. **CCI 미생성·commit 없음·push 없음.**
- ⚠️ 길어진 행 누적 **276개**. 실기 확인은 별도 후속 QA 항목.

### 8차 (2026-08-28) — B021 착수 전 선처리 (`docs/evidence/2026-08-28-enemy-residue/`)

- **`enemy` 잔류 16행 / 1,411 location 전부 수정.** B003·B004·B006 을 해당 16행만 재개봉했다.
  근거: clean codec.dat 전체에 standalone `ENEMY`/`Enemy` 토큰이 **0건**(화면 용어가 아니다),
  코퍼스가 이미 373행 11,091곳에서 「적」을 쓴다, 그리고 **`155/24` 가 `155/16` 과 같은 문장을
  이미 「적을 무력화한 뒤에도」로 옮겨 두었다.** 코퍼스 잔여 소문자 `enemy` **0행**.
  `171/18` 은 `east`·`camera`·`right`·`hide` 까지 영어라 문장 전체를 복원했다(예산 128B 중 70B).
- **expand 가 duplicate 를 안 쓰던 원인을 규명했다.** `mgs3d_codec_expand_locations.py` 가
  **`is_donor == yes` 인 master 행을 통째로 건너뛴다.** `make-translation` 은 그 열을 보지
  않으므로 canonical 만 한국어가 되고 duplicate 는 영어로 남는데 아무 경고도 없다.
  오라벨 행은 381개 중 212개가 미기록 location 을 갖지만 **209개는 진짜 도너**라 안 쓰는 게 맞고,
  영어는 정확히 3행이었다. `745/25`·`1715/47` 만 `is_donor` 를 고쳐 39곳을 전파했다.
  **build pipeline 은 한 줄도 바꾸지 않았다** — 틀린 것은 코드가 아니라 데이터였다.
  `462/20` 은 한국어가 `...CQC.` 로 영어와 바이트 동일이라 이득이 없어 그대로 두었다.
- gate PASS: dropped 0 / failing 0 / capacity 2,256-2,256 / 역판독 1,450-1,450 /
  의도 밖 0 / hold 47,923 / override 13 / 도너 482 / coverage PASS. 1.0/1.1 staging 반영.
  **CCI 미생성·commit 없음·push 없음.**

### 7차 (2026-08-27) — B016-B020 CHECKPOINT 2 (`docs/evidence/2026-08-27-qa-b016-b020/`)

- **B016-B020 1,303행 검수** (누적 5,681/8,334 = **68.2%**). KEEP 995 /
  REGISTER_ERROR 159 / WRONG_MEANING 60 / REFERENCE_IMPROVEMENT 51 /
  CONTEXT_DEPENDENT 22 / CONTROL_LAYOUT 7 / MEANING_LOSS 5 / OVER_COMPRESSED 2 / HUMAN 2.
  **278행 / 11,174 location 수정.**
- **capacity 사고 — 넘친 행이 아니라 옆 행이 사라진다.** `761/10`·`765/10` 의
  「Snake! Snake! SNAKE!!」 수정이 GCX **781** 의 pool 을 넘겨, **건드리지도 않은 `781/12`**
  까지 safe-select 가 드롭했다(첫 빌드 6곳). 두 수정을 되돌리고 `1199/14` 를 54B→45B 로
  줄여 `dropped 0` 회복. → **capacity `--check` 의 「fixed-layout ready」는 드롭한 뒤의
  숫자라 안전 신호가 아니다. 빌드 로그의 `dropped N` 을 봐야 한다.**
- **도너 보호의 두 번째 구멍 (round 4).** 질문을 「이 canonical 이 도너인가」에서
  **「이 location 의 clean 바이트가 FR/ES 인가」**로 바꾸니 두 종류가 나왔다 —
  (a) 영어 고유명사만 든 짧은 스페인어 행(`me pregunto si The Boss piensa igual...` 908/61,
  `es decir a The Boss.` 1368/63, 각 64곳), (b) **부분 hold 누락**(443/3064 은 32곳 중
  6곳만 보호). **161 location** 추가, hold 47,762 → **47,923**.
  새 도구 `tools/mgs3d_codec_donor_location_gap.py`.
- **용어 치환이 동사·게이지를 덮은 사고 (세 번째 계열).** `disguise`→CAMO 2건,
  `stamina`→**LIFE**(1823/12), `task`→MISSION, `cover`→CAMO,
  **`the end`→보스 이름 「디 엔드」 2건**(867/14·995/15, 코퍼스 전수 2건뿐).
- **한글 문장 안 소문자 영어 잔류 전수 조사** — 77행(일반명사 55행 / 2,014곳).
  `enemy` 16행 / 1,411곳이 최대. 코퍼스는 「적」 373행이고 대문자 `ENEMY` 는 0행이라
  화면 용어가 아님이 확정된다. 이번 구간 밖이라 pool 로 남겼다.
- **master locations 를 expand 가 쓰지 않는 공백** — 212행 / 6,190곳 중 도너가 209행,
  **영어는 정확히 3행 / 48곳**(`745/25`·`462/20`·`1715/47`). 파이프라인 소관이라 손대지 않았다.
- gate PASS: 역판독 11,174/11,174, 의도 밖 변경 0, hold 47,923/47,923, override 13/13,
  도너 482/482, dropped 0, capacity 2,256/2,256, coverage PASS. 1.0/1.1 양쪽 staging 반영,
  **CCI 미생성·commit 없음·push 없음**.
- ⚠️ **길어진 행 누적 143개**(28+43+72)의 화면 줄바꿈은 확인하지 못했다. 실기 확인 4세션째 미완.

### 6차 (2026-08-27) — B011-B015 CHECKPOINT 1 (`docs/evidence/2026-08-27-qa-b011-b015/`)

- **B011-B015 1,474행 검수** (누적 4,378/8,334 = **52.5%**, 절반 통과). KEEP 1,307 /
  WRONG_MEANING 106 / REGISTER_ERROR 29 / REFERENCE_IMPROVEMENT 21 /
  CONTEXT_DEPENDENT 10 / MISPLACED 1. **153행 / 1,820 location 수정.**
- **새 구조 오류: 여는 따옴표가 문자열 종결자 `<00>` 뒤로 밀려난 행.** `<00>` 뒤는 게임이
  읽지 않으므로 화면에는 닫는 따옴표만 나온다. 코퍼스 전수 검색 결과 정확히 4건
  (`670/19`, `731/10`, `1153/17`, `1891/10`)이고 뒤 batch 3건까지 함께 닫았다.
- **override canonical 수정 거부 4건** (`443/936`, `654/10`, `662/24`, `677/12`).
  5차의 `243/883` 사고를 게이트가 아니라 **생성기 단계**에서 막도록 가드를 넣었다.
- **`447/13` 오타깃 사고 — 자체 검출·수정 완료.** `## GCX 451` 섹션 아래 행을 447 로 적었는데,
  447/13 은 한국어가 빈 스페인어 도너 행이라 **빈 값 대 빈 값 대조가 조용히 통과**했다.
  빌드는 무영향(accept 미설정이라 expand 가 쓰지 않음)이었지만 master 가 오염되고 원래 대상
  451/13 은 안 고쳐졌다. 게이트의 `expected 1,805 ≠ changed 1,804` 1곳 차이로 잡았다.
  → **「before 가 일치했다」는 올바른 행을 고쳤다는 증거가 아니다.** 생성기에
  live-row 가드(accept≠yes 또는 한국어 공백이면 거부)를 추가했다.
- **「시긴토」는 오류가 아니다** — Sigint 표기가 코퍼스 32행 전부 일관된다. 「시긴트」로
  고칠 뻔했으나 코퍼스 스캔이 막았다. 고유명사 정책 pool 로 넘겼다.
- gate PASS: 역판독 1,820/1,820, 의도 밖 변경 0, hold 47,762/47,762, override 13/13,
  도너 182/182, capacity 2,256/2,256, coverage PASS. 1.0/1.1 양쪽 staging 반영,
  **CCI 미생성·commit 없음·push 없음**.
- ⚠️ **길어진 행 누적 71개**(5차 28 + 6차 43)의 화면 줄바꿈은 확인하지 못했다.

### 5차 (2026-08-27) — B006-B010 + 숨은 도너 3라운드 (`QA-PROGRESS.md`)

- **B006-B010 1,424행 검수** (누적 2,904/8,334 = **34.8%**). KEEP 1,278 /
  WRONG_MEANING 68 / REGISTER_ERROR 33 / REFERENCE_IMPROVEMENT 22 /
  CONTEXT_DEPENDENT 13 / MISPLACED 6 / HUMAN 3 / MEANING_LOSS 1. **127행 수정**
  (배치 안 120 + 배치 밖 구조적 발견 7).
- **용어 치환이 같은 철자의 일반명사를 덮은 사고 12건** — `stamina`→게이지 이름 LIFE 6건,
  `life cycle`·`brought back to life`→LIFE, 읽는 `magazine`→탄창 MAGAZINE,
  `food poisoning`→FOOD, `survival`→SURVIVAL, 동물 `snake`→코드네임 「스네이크」 4건,
  깨진 토큰 `CIGARette`·`trEVAlly`. 깨진 토큰은 코퍼스 전체에 2건뿐이었고 둘 다 닫혔다.
- **다른 통화 조각이 문장 끝에 붙은 오염 3건** (`443/627`에 「달 표면 기지에서 워싱턴으로
  쏟아지는」, `443/746`에 소음기 조작 설명, `2191/11`에 마취탄 설명). 전수 검색 결과
  나머지 9건은 영어도 중간에서 끊기는 정상 분할이었다.
- **숨은 도너 11행 / 171 location 추가 확정** — 08-26 스캔이 `The Boss`·`Sigint`·
  `The End`·`Para-Medic`·`OK` 같은 **영어 고유명사가 든 프랑스어/스페인어 행**을 후보에서
  뺐던 구멍이다. hold 47,630 → **47,762**.
- **게이트가 canonical↔override 충돌을 잡았다** — `243/883` 을 Para-Medic 존댓말로 고쳤더니
  "선언 1,250 중 1,249만 변경"이 떴다. 그 canonical 은 override 대상이었고, override 사유가
  *"canonical 을 존댓말로 바꾸면 Tom 통화 86곳이 깨진다"* 였다. 수정을 되돌렸다.
- 빌드·검증 통과 후 1.0/1.1 스테이징. `codec.dat` `70acf913…`.
  역판독 1,163/1,163, 의도 밖 변경 0, hold 47,762/47,762, 도너 182/182 복원,
  coverage-verify PASS. 증거 `docs/evidence/2026-08-27-qa-b006-b010/`.
> 진행 위치와 현재 수치는 `QA-PROGRESS.md`가 authority다.

### 1차 (2026-08-25) — QA 전략 전환

**이 1차 세션에서는** 번역 0건 수정, 빌드·스테이징·CCI 없음. codec QA 방침이
"위험 후보만"에서 **"영어분기 전수 문맥 검수"**로 바뀌었고, 기반만 만들었다.
(3차·4차에서는 수정·빌드·스테이징을 했다 — §1의 해시를 볼 것.)

- **전수 검수판 `codec-full-context-review.csv` 8,334행** — 영어분기 번역행 8,173 +
  미번역 161. master 번역행 9,058 = 8,173 + 도너 제외 885, **누락 0 / 중복 0**
  (`coverage-verify.json`이 master에서 독립적으로 다시 세서 PASS).
  통화 단위로 읽는 판은 `review-md/batch-001..030.md`(배치당 최대 300행).
- **외부 대사집을 scene → call → turn 으로 재구조화** — 기존 JSON은 2,164 문장 평탄
  리스트였다. 원본 FAQ의 배너/구분선/`-제목 … ===` 구조를 다시 파싱해 71 scene /
  398 call / 4,203 turn. wiki 무선 통신 261 통화를 합쳤다.
- **GCX ↔ call 매퍼** — anchor(30자·6단어 이상, 한 source 안 유일) → block(단조
  turn 순서) → block 안에서만 local alignment. 전역 fuzzy 없음.
  GCX **CONFIRMED 287 / HIGH 86 / REVIEW 137 / UNMAPPED 1,260**, 행 4,310 매핑.
  hold-out 20%: turn 정확 165/173, 화자 172/173. HIGH 이상만 보면 153/154·154/154.
  **REVIEW 라벨은 실제로 63%** — 라벨이 제 일을 한다.
- **`text_kind` 도 못 믿는다** — 미번역 워크리스트 50행 중 48행이 `identifier`로
  라벨돼 있으면서 실제로는 대사(`Agreed.` `Ah.`). 필터를 걷어내 50행 전부 포함.
- **다음 세션 1순위**: 사람이 확정한 화자 16행 중 **5행이 매퍼와 불일치**
  (746/14, 1586/11, 1818/25, 48/35, 60/35). 전부 짧은 공유 문자열 alignment 건이고
  anchor는 하나도 틀리지 않았다.

증거·재생성 절차 `docs/evidence/2026-08-25-codec-full-context/README.md`.
도구 7종은 `tools/mgs3d_codec_{external_structure,clean_raw_cache,gcx_structure,
scene_mapper,scene_mapper_validate,full_review_dataset,review_coverage_verify}.py`.

### 같은 날 2차 — 문맥 보강 + batch-001 검수 (`SESSION-2.md`)

- **override 5건은 매퍼가 맞다.** 원인은 alignment 가 아니라 **행 단위 exact lookup** —
  같은 영어를 가진 *다른* canonical 행의 화자를 가져다 붙였다(745/24→746/14,
  437/33→1586/11). 1818/25 는 아예 근거 없음. 443/887(Zero)도 같은 혐의, 677/12 는
  override 가 맞다. 검수판의 `speaker` 만 정정했고 **override CSV 와 master 는 그대로**.
- **매퍼 guard 2개 채택** — `--gcx-consensus 3`(한 source 안 두 call 에 걸려 버려지던
  앵커를 GCX 투표로 회수) + `--space-insensitive`(`code names`≠`codenames`).
  앵커 2,475→3,077, CONFIRMED GCX 287→313, hold-out CONFIRMED 356/356.
  CONFIRMED/HIGH 에서 새 불일치 0.
- **Shinsnote 는 reference-only 확정.** 구조화(scene 49/call 628/turn 3,031)는 됐지만
  3DS codec 한국어가 Shinsnote 에서 온 게 아니라 앵커가 84개뿐 → 316행(3.8%)만 연결.
  정밀도는 CONFIRMED 61/61·HIGH 70/71 로 높다. 짧은 공유 문장 68건 이탈 0.
- **batch-001 287행 검수 완료** — KEEP 108 / CONTROL_LAYOUT 178 / REFERENCE_IMPROVEMENT 1.
  ⚠ **GCX 13(무선 사진 인덱스 테이블) 177행이 대사처럼 번역돼 현재 빌드에 들어가 있다**
  (`page:`→`페이지:`, 공백→`|`). 엔진이 파싱하는지 확인이 먼저다.
- 검수판은 62열 8,334행, coverage 재검증 PASS. baseline 은 `baseline/` 에 SHA 로 보존.

### 직전 세션(2026-08-23) 요약

- **직전 "무인 정밀 검수" 재검증과 후속 조치 5건** — ledger의 판정 순서 결함으로
  화자와 말투가 정면 충돌하는 7행이 `SOURCE_CONFLICT_RESOLVED`로 통과하고 있었다.
  문맥 조사 중 미검출 2건이 더 나와 총 8행 교정, 화자 배정 1건(1543/14 → EVA) 정정.
  `unresolved`는 **상수 0 하드코딩이었고** 이제 계산값이다. `KEEP_STRUCTURAL` 4,463행
  (49.3%, evidence 공란)은 `UNREVIEWED_NO_DETECTOR`로 바꿔 `resolved`에서 뺐다.
  미번역 워크리스트는 1,040행이 아니라 **51행**(나머지는 도너 오라벨 878 + 구조행 111).
  고유명사를 한국어 대사집 기준 한글로 통일(1,453행/1,642건, 신규 glyph 0).
  빈 한국어+accept=yes 3행이 48곳을 널 바이트로 덮고 있던 것을 clean 복원.
  codec/movie/demo 재빌드·검증·양 트리 스테이징 완료.
  증거 `docs/evidence/2026-08-23-review-followup/`.
- **D precision 무인 정밀 검수** — ⚠️ "9,057행 전부 명시적 판정, 미해결 0"은
  과대 표현이었다. `미해결 0`은 계산값이 아니라 상수였고, 4,463행(49.3%)은 어떤 검출기도
  걸리지 않은 `KEEP_STRUCTURAL`로 라벨만 붙은 것이다. 2026-08-23 후속 조치에서 정정했다.
  실제 표시 시뮬레이션은 여전히 제외. codec 9,057행과
  movie/demo 2,917행 판정. 화자 출처 충돌 43건 해소.
  media 의미·영문 잔존·문장부호 55행 추가 수정. movie 1/1, demo 54/54 회귀검사,
  대상 밖 변화와 레이아웃 변화 0. codec/movie/demo를 RomForge 1.0/1.1에 스테이징.
  증거 `docs/evidence/2026-08-23-d-precision/`.
- **D 전체 말투·문맥 패스 완료 및 스테이징** — codec 번역 9,057행 전수 장부화,
  화자 확정 4,292행. 확정 말투 불일치·혼용과 sense 오역을 조사해 canonical 141행을
  수정했다. production 위치 1,752곳 역판독 일치, 대상 밖 텍스트 변화 0, 레이아웃 변화 0,
  safe-select 탈락 0. 최종 SHA-256 `772c9007…`; RomForge 1.0/1.1 양쪽 스테이징 완료.
  증거 `docs/evidence/2026-08-23-full-translation-audit/`.

- **codec strong 39건 문맥 QA 결과 반영** — 반환된 39행은 KEEP 29 / FIX 6 /
  CONTEXT_DEPENDENT 4 / HUMAN 0. FIX 6건을 canonical 정본에 반영했다. 제출 축약안 중
  예산을 넘긴 S20·S31은 각각 「그러시든가...」·「아직이죠?」로 재축약했다.
  production 파이프라인 재생성 결과 safe-select 탈락 0, fixed-layout 2,257/2,257 PASS,
  실제 전파 75/75 역판독 일치, 대상 외 표시 텍스트 변화 0. 진단 `codec.dat` SHA-256
  `b98a0e83…`. RomForge 1.0/1.1 양쪽에 백업 후 스테이징했고 SHA-256을 재확인했다.
  증거 `docs/evidence/2026-08-23-codec-strong43/`
- **1.1 CPP 패치 이식 완료** — 아자르에서 확장 슬라이드 패드가 안 켜지던 원인은
  단순히 **1.1 빌드에 CPP 패치가 없었던 것**. 1.1 enforcer는 `−0x554` 균일 시프트로
  멀쩡히 살아 있다(`0x0010A96C`, 슬롯 `0x0010A9A0`), 패치 바이트는 1.0과 동일.
  `mgs3d_cpp_default_patch.py`가 이제 1.0/1.1을 앵커로 자동 판별한다.
  `builds/diag-2026-08-23-v1.1-cpp/` 산출·스테이징, 정적 55/55 PASS.
  문서 `docs/cpp-v1.1-port-2026-08-23.md`, 증거 `docs/evidence/2026-08-23-cpp-v1.1/`
- **08-21 오진 정정** — "1.1이 enforcer를 재작성해 1.0 패턴이 0회"는 틀렸다.
  검색 패턴이 `bl`의 **상대 분기 변위를 가로질러서** 못 찾은 것이고, 22 B 중 다른 건
  2 B뿐이다. `v1.1-port-analysis-2026-08-21.md` §4.4에 정정 박스를 달았다
- **`mgs3d_port_v11_glyph.py` 결함 2건 수정** — ① `PROD10`이 `Romforge/output/unpacked`
  하드코딩인데 그 트리가 1.1로 바뀌어 "1.0 도너"로 1.1을 읽고 있었다(`verify`가
  08-21 빌드에서도 크래시). ② CPP 검사가 **1.0 주소**를 1.1 이미지에 대고 봐서 아무것도
  못 잡았다. 경로·주소 수정 + 도너 길이 검사 + `--with-cpp` 추가

### 직전 세션(2026-08-22) 요약

- **교차 검증 도구 둘** — `tools/mgs3d_crossvalidate.py`(검출기 D1~D9,
  codec/movie/demo/vox), `tools/mgs3d_vox_donor_check.py`(vox 도너 4언어)
- **적용** — codec 정본 377건(2026-08-17 full-QA 제안) + 교차검증·실플레이 24건
  + vox 자막 줄바꿈 30건
- **스테이징** — 네 컨테이너 전부. 두 트리 924 files, 바이트 총계 불변
- **정리** — 백업 41개를 `10_master/archive/backups/`로, 문서를 `docs/`로
  (translation/ 아래는 gitignore라 저장소에 안 남는다), `release-v0.93c/` 매니페스트
- v0.93c 커밋·푸시 (`8818576`)
- **QA 3라운드** — Eva/Sokolov 어투 정책 확정, 실기 발견 5건, Sokolov-Shagohod 장면,
  **codec English 열 손상 371행 복구**, demo offset 407행 검수.
  증거: `docs/evidence/2026-08-22-qa-eva-scene/`, `docs/evidence/2026-08-22-qa3-sokolov-english-offset/`

### 화자 어투 정책 (확정)

| 화자 | 정책 | 근거 |
|---|---|---|
| Snake | 반말 | 89/89 일관 |
| Para-Medic | 존댓말 | 한국어 참조 대본 |
| Sigint | 반말 | 〃 |
| Eva | 존댓말 | 참조 대본 에바 587줄 일관 |
| Sokolov | 반말/하게체 | 참조 대본 + 동일 장면 연속 대화 |
| Zero / Tom / Boss | 반말 | 다수 일관 |

미확정: **Volgin, Ocelot, Campbell** (표본 부족)

### 4차 (2026-08-26) — 숨은 도너 2라운드 + B004/B005 (`QA-PROGRESS.md`)

- **숨은 도너 확정과 복원** — clean-tree raw + 분기 블록 구조로 재판정.
  CONFIRMED **62행 / 1,004 location**(빌드에 있던 것 31행), hold 46,732 → **47,630**.
  `<1F>"`(¡) 541행 · `<1F>@`(¿) 1,440행을 전수 확인해 **영어가 하나도 없음**을 근거로
  악센트를 단독 증거로 승격했다. 구조만으로 잡히는 45행(`Yep.` `Great!` 등 영어 포함)은
  **일부러 hold 하지 않았다** — 2026-08-23 이 폐기한 블록 보간과 같은 실패다.
- **도너 복원 부작용 2곳을 영어 축약으로 흡수** — 도너 슬롯이 원문을 되찾자
  847/14·2136/10 이 예산 초과. 도너를 덮지 않고 영어를 줄여 **dropped 0** 복귀.
- **B004·B005 597행 검수** (누적 1,480/8,334 = **17.8%**). KEEP 551 /
  WRONG_MEANING 15 / CONTEXT_DEPENDENT 13 / 그 외 18. **24행 수정.**
  대표: `fatigues`→「피로」, `cover will be blown`→「엄폐물이 날아가게」,
  `like a sore thumb`→「아픈 엄지손가락」, `stamina`→「LIFE」, `Action Button`→「작업 버튼」.
- **새 pool(수정 안 함)** — 용어 표기 불일치 **7종 / 359행 / 8,554 location**
  (Survival Viewer 6종, Action Button 5종…). 화면 UI 표기 확인 후 정책 결정 사안.
- 빌드·검증 통과 후 1.0/1.1 스테이징. `codec.dat` `0e510ab6…`.
  역판독 1,176/1,176, 의도 밖 변경 0, hold 47,630/47,630, 도너 31/31 복원.

### 3차 — override 재감사 + GCX 13 구조 식별자 + B002/B003 검수 (`QA-PROGRESS.md`)

**진행 authority 는 이제 `docs/evidence/2026-08-25-codec-full-context/QA-PROGRESS.md` 다.**
다음 세션은 이 파일 → QA-PROGRESS.md → 대상 batch 파일 순으로만 읽는다.

- **override 16건 전수 재감사** — CORRECT 9 / WRONG_SPEAKER 7 / AMBIGUOUS 0.
  잘못된 3건(443/887·746/14·1818/25)은 어투를 거꾸로 넣고 있어 **삭제**, 라벨만
  틀린 4건(48/35·60/35·1586/11·2113/28)은 화자·근거만 정정. 2113/28 은 Shinsnote
  p5/127-137 이 통화 전체를 담고 있어 Snake 로 확정됐다. override 16 → 13.
- **GCX 13 은 무선 사진 인덱스 테이블이 맞다** — clean raw 가
  `No:8/264 page:8<80>|radio_picture156<80>|rd_ani_gingameaji` 로 `<80>|` 필드
  구분자를 쓴다. ⚠️ SESSION-2 의 "공백→| 114행 훼손"은 **오판이었다** — 그 114행은
  clean 과 바이트 동일하고, 진짜 훼손은 **63행**(`page:`→`페이지:`, 구분자 소실,
  `<0A>` 추가, 자산 키 `bereidesu`→`bereisu`)이다. 177행을 파이프라인에서 제외했고
  같은 형태는 코퍼스 전체에서 GCX 13 뿐이다.
- **B002·B003 596행 검수 완료** (누적 883/8,334 = 10.6%). KEEP 467 /
  CONTROL_LAYOUT 102 / WRONG_MEANING 10 / REGISTER_ERROR 5 / 그 외 12.
- **문장부호 앞 공백 129행 원인 확정** — Shinsnote 스크레이프가 문장부호를 띄어 쓴 것이
  그대로 이식됐다(연결된 105행 전부 원문에는 공백 없음). 공백만 제거해 128행 적용.
- **수정 141행 + 구조 제외 177행 + override 7건**, 빌드·검증 통과 후 1.0/1.1 스테이징.
  `codec.dat` `af7b3769…`. 역판독 1,132/1,132, 의도 밖 변경 0, hold 46,732/46,732 유지.
- **미해결(사람 판단)** — 영어분기 도너 잔여 21행(16행 빌드 포함), `"Yes."→「왜?」`
  492 location, 화자 어투 정책 위반 88행/1,532 location. 전부 QA-PROGRESS.md 에 있다.

## 3. 막혀 있는 곳

없음. 다만 아래 둘은 사람이 정해야 한다.

- **화자별 어투 정책** — Zero/Tom의 존댓말이 전반에 섞여 있어 한 줄씩 못 고친다
- **`29/23`** — "Shagohod is ours!"가 예산 17B라 고유명사를 뺀 「이건 우리 것이다!」로 갔다
- **movie/demo 단독 호명 자막 29건은 라틴 `Snake`로 남았다** — 슬롯이 원문 길이에
  고정돼 8바이트 한글 이름이 물리적으로 안 들어간다. 나머지 본문은 전부 한글로 통일됐고
  codec에는 라틴 인물명이 0건이다. 목록은
  `docs/evidence/2026-08-23-review-followup/proper-noun-reverted-media.csv`

## 4. 읽을 wiki 페이지

`Current-State.md`(현황·Known Issues) → `Conventions.md`(R1~R12) →
`Translation.md`(정본 경로) → `Build-System.md`

도구 문서: `docs/crossvalidate.md`, `docs/vox-donor-check.md`
**자료를 찾기 전에 `docs/SOURCES.md`부터 볼 것** — 2026-08-22에 영문 대사집이
`analysis/`에 있는데 못 찾아 외부 수집을 시도한 일이 있다.

## 5. 다음 작업

**T6 — 다음 세션 1순위 (사람, 실기 5분).**

1. SD 의 `sdmc:/luma/titles/0004000000081E00/code.bin` 을 **삭제한다.**
   남아 있으면 Luma 적용 순서(`bps` → `ips` → `bin`) 때문에 IPS 결과를 덮어써서 또 죽는다.
2. `builds/diag-2026-08-28-luma-t6-ips/sd-root/luma` 를 SD 루트에 복사한다.
3. `romfs/` (codec.dat + stage 169) 는 **그대로 유지한다.**
4. 새 게임 첫 코덱 무전을 확인한다.

| 관측 | 다음 |
|---|---|
| **정상 한글** | ③ 통과 + 글리프 페이지 상주 확인. 배포 구조 확정 가능 |
| 부팅 + 깨진 글자 | 차분 경로는 살았다 → stage 글리프 페이지(H1/H2)만 남는다 |
| 부팅 + 영어 | IPS 미적용. 경로·`Enable game patching` 재확인 |
| 크래시 | `sdmc:/luma/dumps/arm11/*.dmp` 를 받아 `python tools/parse_luma_crash_dump.py <파일>`. PC/LR/FAR 를 evidence §7 대조표와 대조 |

되돌리기: `sdmc:/luma/titles/0004000000081E00/` 폴더 삭제.


**0. codec 전수 문맥 검수 — 완료 (2026-08-30).** B001-B030 8,334 / 8,334 행,
   `rows_remaining 0`. 새 batch 를 열 이유는 없다.
   상세는 `docs/evidence/2026-08-25-codec-full-context/QA-PROGRESS.md` 가 authority.
   남은 후속은 두 가지뿐이다.
   - **(a) 길어진 행 476개의 실기/Azahar 표시 확인.** 자동 검증은 바이트·인코딩·용량만
     증명하고 **줄바꿈 위치와 화면 넘침은 증명하지 못한다.** 다섯 세션째 밀려 있다.
   - **(b) ~~용어 표기 pool~~ — 2026-08-31 종결.** 26개 용어 / 221행 통일.
     남은 것은 MISSION/임무(147:52)와 RADIO·MAP·SMOKE(각각 뜻이 둘)뿐이고, 둘 다
     프로젝트 정책 결정이 필요하다. `docs/evidence/2026-08-31-terminology-pool/README.md`.

**1. 리팩 + 아자르/실기 검증 (사람)** — 여기서부터다.
   - 리팩 전에 골든 이름 충돌을 피할 것. `Romforge/output/`이 밑줄 6개까지 차 있어
     다음 repack이 골든의 파일명(7개)을 쓴다 (R6)
   - 1.1 + CPP는 `Romforge/output/unpacked` (`exefs/code.bin` = `6ad1c99…`).
     되돌리려면 `builds/diag-2026-08-23-v1.1-cpp/pre-patch/code.bin`을 덮는다
   - **볼 것**: 오른쪽 스틱(CPP), 그리고 이번에 축약이 30행 더 들어갔으니
     줄바꿈·화면 넘침. 무인 검수는 실제 표시 시뮬레이션을 여전히 못 한다

**2. 미번역 영어 51행** —
   `docs/evidence/2026-08-23-review-followup/codec-untranslated-english-worklist.csv`.
   2026-08-24 짧은 후속 작업에서 `2029/10 By the way, Para-Medic...`을 Snake 화자 근거로
   `그런데, 패러메딕...`으로 번역했다(중복 3곳 동일 발화). **현재 50행**이다.
   적용 근거·백업·재분류 결과는 `docs/evidence/2026-08-24-untranslated-pass1/`.
   ⚠️ 통짜 번역 금지. `Exactly.` 하나가 234곳에 퍼져 있고 화자가 섞여 있어, 한 가지
   말투를 넣으면 상당수가 어색해진다. per-location override layer(§6)가 필요하다

**3. 미검수 4,463행** — `UNREVIEWED_NO_DETECTOR`. 어떤 검출기도 걸린 적이 없는 행들이라
   새 검출 기준을 만드는 것부터다. 그중 4,383행이 실제 빌드 대상이다.
   `output/speaker-conflict-fix-20260823/codec-precision-ledger.csv`

**4. 워크리스트 A 2건 / B 61건** (C는 1,063건)
   `translation/10_master/review/crossvalidate/worklist.csv`

## 6. production 규칙 — codec per-location override

**codec shared-string 의 speaker/register 예외는 canonical master 를 훼손하지 않고
expand 이후 per-location override layer 에서만 처리한다. Override CSV 는 production
authority 의 일부이며 `reason` 은 필수다.**

```
make-translation → expand-locations → mgs3d_codec_location_override.py
  → hold-locations 제외 → safe-select/capacity → build-korean
```

authority `translation/10_master/current/codec-location-overrides.csv` ·
도구 `tools/mgs3d_codec_location_override.py` · 상세 `wiki/Build-System.md`.
공유 문자열의 화자별 예외에만 쓴다. 일반 번역 수정에는 쓰지 않는다.

## 7. 주의

- **canonical 어투를 고치기 전에 override CSV 를 볼 것.** override 가 걸린 canonical 은
  "그 방향으로 바꾸면 안 된다"는 기록이다. 2026-08-27에 `243/883` 을 존댓말로 고쳤다가
  게이트가 잡았다 — override 사유에 *"canonical 을 존댓말로 바꾸면 Tom 통화 86곳이 깨진다"*
  가 이미 적혀 있었다
- **용어 치환은 어의를 보지 않는다.** `stamina`→LIFE, 읽는 `magazine`→탄창 MAGAZINE,
  `food poisoning`→FOOD, `survival`→SURVIVAL, 동물 `snake`→코드네임, `cigarette`→`CIGARette`,
  `trevally`→`trEVAlly`. 2026-08-27에 12건을 닫았다. 새 치환을 돌릴 때는
  `[A-Z]{3,}[a-z]{2,}` 로 깨진 토큰을, 영어 원문의 어의로 오적용을 각각 확인할 것
- **`accept=yes` 인데 `korean` 이 비면 그 행이 원문을 지운다.** make-translation이 빈
  문자열을 써서 도너 3행이 48곳을 널 바이트로 덮고 있었다(2026-08-23 복원). 앞으로
  `accept` 를 켤 때는 한국어가 있는지 같이 볼 것
- **`is_donor=yes` 행은 `expand_locations` 가 중복 위치를 건너뛴다.** 그래서 그 행을
  고쳐도 정본 위치 하나만 바뀐다. 검증에서 "missing"으로 뜨는데 결함이 아니다
- **검증 도구의 `--applied` 는 실제 빌드 대상으로 걸러서 넣을 것.** 마스터 행을 그대로
  넣으면 `accept` 가 빈 도너 행까지 기대값에 들어가 없는 실패가 만들어진다
  (2026-08-23에 missing 233건이 이것 때문이었고, 걸러내니 39건이 됐다)
- **고유명사를 한글로 바꾸면 조사가 어긋난다.** `The Pain가` → `더 페인이`. 단 `이` 는
  주격조사이자 계사 어간이라 뒤에 한글이 이어지면 건드리면 안 된다
  (`어떤 스네이크이던` → `스네이크가던`이 되던 결함)
- **말투 분류에서 조사 `까지`/`마다` 를 종결어미로 오인하지 말 것.** `버섯까지...` 의
  `지` 때문에 멀쩡한 존댓말 행이 "혼용"으로 뒤집혔다
- **상대 분기를 가로지르는 바이트 패턴으로 버전 간 검색을 하지 말 것.** `b`/`bl`
  변위는 재컴파일마다 바뀐다. 08-21에 이걸로 "1.1엔 CPP 코드가 없다"는 오진이 나왔다
- **`Romforge/output/unpacked`는 이제 1.1 트리다.** 그 경로를 "1.0 프로덕션"으로
  하드코딩해 둔 도구가 조용히 틀린 이미지를 읽고 있었다. 1.0은
  `unpacked-v0.93a-staging`이다 (압축 해제 크기 1.0 = 8,478,720 B, 1.1 = 8,744,960 B)
- **`errors: []`는 "할 일 없음"이 아니다.** 적용 기록만 있고 바이너리에 안 실린
  5건이 있었다
- **byte-fit PASS 기록은 바이너리가 바뀌면 재검증할 것.** 08-17 PASS 3건이 지금 FAIL
- **PERSONAL DATA는 마스터에 한국어가 있지만 바이너리는 영문이 결정 사항.**
  단순 재빌드가 되돌린다 — `40_build_input/2026-08-22/hold-locations.json`으로 제외
- **`5C 6E`를 파일 전체에서 바이트로 세지 말 것.** 한글 토큰 `특`(845C)이 0x5C를
  꼬리 바이트로 쓴다. clean/이전 빌드와 상대 비교할 것
- **`fixed-layout` 분모 2,326과 2,257은 다른 단계의 수다.** 2,326은 hold 필터 이전,
  2,257은 hold 적용 후 실제로 다시 쓰는 GCX 레코드 수다. 2026-08-23 재빌드도 2,257이다
- **크기로 동일성을 판단하지 말 것 (R4).** 항상 SHA-256
- **게이트의 `DAT read-back matches master` 는 실측이 아니다.** 저장된 evidence
  파일을 읽는다. override 를 쓴 빌드는 역판독을 따로 돌릴 것
- **`english` 열이 깨진 행이 QA 정확도를 직접 깎는다.** 371행 복구로 speaker
  coverage가 518→886(+71%)이 됐다. 원인은 master가 잘못된 codec.dat(JP 타이틀)에서
  만들어진 잔재다. clean DAT의 같은 (gcx,resource)에서 결정적으로 복구할 수 있다 —
  **fuzzy 추측 금지**
- **오배치는 `offset` 경로가 아니다.** 지금까지 확정된 4건이 `review_record_entry` 2 +
  `normalized_english` 2이고 `offset`은 0건이다. offset 407행을 위험 풀로 지목하던
  가정은 근거가 없다
- **게이트 두 항목이 실측이 아니다** — `DAT read-back matches master`(저장된 evidence
  JSON)와 `register QA 1,335 closed`(`not re-run by policy`)
