# codec 실기 QA Round 5 — 검증 방법 자체의 결함 (2026-08-17)

기준: staged `codec.dat` v0.88 `6bdec076…` (해시 확인 완료). **CCI는 만들지 않았다.**

> **본 문서는 sanitized 판이다.** 저장소 정책상 Konami 스크립트와 그 번역문은 커밋하지
> 않는다. 각 항목은 `gcx:resource` 좌표와 수치로만 지칭한다. 대사 원문이 포함된 전체
> 기록과 evidence 덤프는 로컬 백업
> `3dsmetal-backups/2026-08-17-round5-pre-git-cleanup/docs-unsanitized/` 에 있다.

## 이번 라운드의 답

> "왜 master와 staged 검증에서는 정상이라고 판단했는데 실제 게임에서는 다른 결과가 나왔는가?"

**codec은 canonical location만 검사하고 있었고, movie는 아예 다시 빌드되지 않았다.**

| 검사 | 결과 |
|---|---|
| accepted master 행의 한국어가 **canonical location**에 있는가 | **22,818행 중 불일치 0** |
| 같은 문자열의 **모든 location**이 한국어인가 | **224행이 KO/영문 혼재**, 영문 7,563 위치 |
| staged `movie.dat`이 master와 일치하는가 | **689행 중 3행 불일치** |
| staged `demo.dat`이 master와 일치하는가 | 2,228행 중 **0행 불일치** |

canonical 검사가 100% 통과하기 때문에 지금까지의 모든 게이트가 PASS였다. 결함은
**오직 중복 location에만** 있었고, 어떤 게이트도 그곳을 보지 않았다.

새 도구 `tools/mgs3d_codec_partial_application.py`가 이 구멍을 막는다.

---

## [1] 앵커 A — 초반 배낭 튜토리얼 1행 · `PARTIAL_APPLICATION`

전수검색 결과 codec 전체(601,657 리소스)에서 정확히 3곳.

| location | staged v0.88 판정 |
|---|---|
| `20:17` | KO |
| `52:34` | **LATIN (영문 잔존)** |
| `53:47` | **LATIN (영문 잔존)** |

master 행은 셋을 모두 `locations`에 갖고 `accept=yes`인데
`translate=no / language=es / is_donor=yes` 였다.

### 왜 도너로 찍혔나 — 재현 가능한 메커니즘

`tools/mgs3d_codec_langid.py`의 코퍼스 기반 분류기가 이 행을 **donor로 오판**한다:

```
donor-only 토큰 적중    : 1개    (아이템명 토큰 하나)
english-only 토큰 적중  : 0개
verdict                : donor
```

문제의 토큰은 **아이템 이름**이다. 프랑스어/스페인어 분기도 아이템명은 영어 표기를
그대로 쓰기 때문에 그 토큰이 donor-only 어휘에 들어갔다. **토큰 1개·영어 증거 0개**로
도너 판정이 나면서 2026-08-16 도너 재분류가 이 행을 도너로 바꿨고, 중복 전파 대상에서
빠졌다. canonical `20:17`은 그 이전 라운드에서 이미 한국어가 기록돼 있었으므로 canonical
검사는 계속 통과했다.

**원인 분류: `DUPLICATE_ENGLISH` + `NORMALIZATION_MISMATCH`(도너 오분류)**

### v0.88의 "번역한 95문장 staged 영어 0"과의 관계

그 검사는 **그 라운드에서 새로 번역한 95문장**만 대상으로 했다. 이 행은 그보다 앞선
라운드에서 이미 승인·번역된 기존 행이라 검사 범위 밖이었고, 도너 재분류로 전파에서
빠진 시점도 그 이후다. 즉 **범위 밖 + 대표 location만 검사** 두 가지가 겹쳤다.

이 건은 새로 발견된 것이 아니다. `translation/10_master/pending/runtime-corrections.csv`의
마지막 행이 v0.69 실기 결과로 같은 구간의 영문 잔류를 `status=pending`으로 남겨 두고
"정확한 GCX/offset은 다음 재현 때 캡처 필요"라고 적어 둔 그 증상이며, 이번에 좌표가
특정되어 `resolved`로 종결했다.

---

## [2] 앵커 B — 강하 직전 무전 1행 · codec이 아니라 movie, `BUILD_NOT_APPLIED`

**이 문장은 codec.dat에 존재하지 않는다.** 사용자가 기억한 옛 문구도 세 DAT 어디에도
없다(movie/demo는 raw 바이트 검색 + positive control로 방법 검증, codec은 복호화 후 검색).

실제 위치는 **`movie.dat` record 1 / entry 11 / offset 2800**이다.

| 출처 | 상태 |
|---|---|
| `movie.csv.bak-pre-shorten` | 구 문구 |
| `movie.csv.bak-pre-usercorr-20260816` | 구 문구 |
| **`movie.csv` (현재 master)** | **수정된 문구** |
| **staged `movie.dat` 7978657c…** | **구 문구** |

즉 **사용자는 실제로 고쳤고 master에 반영돼 있으나, movie.dat이 그 뒤로 재빌드되지
않았다.** 사용자가 기억한 표현은 같은 계열의 옛 문구였다.

**원인 분류: `BUILD_NOT_APPLIED`**

같은 라운드의 사용자 수정 3건 전부가 미반영이었다 — `1/11`(offset 2800), `5/5`(10696),
`7/9`(15352). 재빌드로 3/3 반영 확인.

**번역 자체는 재검토 결과 바꾸지 않았다.** 현재 master 문구는 화자 관계(상급자 → Snake,
반말)와 원문의 경고 태도에 맞고 이미 사용자가 직접 고른 표현이다.

---

## [3] 앵커 C — SAVE 후 Para-Medic 영화 화제 통화 · MISALIGNMENT가 아니라 SPEECH_LEVEL_ERROR

`gcx 2173` res 10–40, **31행**. 같은 블록이 `gcx 2210`, `gcx 2211`에도 복제돼 있다.

화자는 어미가 아니라 **English 문답 관계 + 스페인어/프랑스어 도너 순서**로 확정했다
(도너는 화자 구조를 보존한다: ES `res 64` = EN `res 31`, ES `65` = EN `32`, ES `66` = EN `33` …).

- **Para-Medic 20행 / Snake 11행**
- **MISALIGNMENT: 0** — 모든 한국어가 자기 English와 의미상 대응한다
- **SPEECH_LEVEL_ERROR: 13** — Para-Medic 대사가 반말, Snake 대사가 존댓말로 뒤집힘
- **MEANING_ERROR: 5** — 인사말 오역, 일부 명사 미번역 잔재, 어순 붕괴

사용자가 "화자가 완전히 뒤섞여 있다"고 느낀 것은 **어체가 교차로 뒤집혀** 있었기
때문이며, 한국어가 다른 발화에 붙은 오정렬은 아니었다.

**16행 수정**: `res 10, 11, 18, 19, 20, 21, 22, 25, 27, 28, 29, 31, 34, 35, 38, 39`.
페이지에 없는 글자 1개를 회피하기 위해 `res 22`를 동의 표현으로 바꿨다 — **신규 글리프 0**.
블록 전체 인코딩 바이트 델타 **−30**.

전 행 대조표(English/Korean 포함)는 커밋하지 않는다. 로컬 백업의
`docs-unsanitized/evidence/2026-08-17-codec-round5/godzilla-block.csv` 참조.

### [D] SAVE 인접 Para-Medic 블록

이 블록의 앞은 `res 5–9`의 PERSONAL DATA 카드로, 통화 대사가 아니라 프로필 카드다.
즉 **통화 경계가 그 앞에서 끊긴다.** 지시대로 확장을 중단했다.
(PERSONAL DATA 카드의 부분 미번역은 별개 항목 — 대사가 아니라 카드 서식이고 원인이 다르다.)

---

## [4] PARTIAL_APPLICATION 전수조사

`tools/mgs3d_codec_partial_application.py --codec <staged>`

| | |
|---|---|
| locations 있는 master 행 | 22,818 |
| 그 중 복수 location | 16,593 |
| 검사한 location | **435,602** |
| KO / LATIN / EMPTY / MISSING | 224,222 / 211,332 / 48 / 0 |
| **PARTIAL_APPLICATION 행** | **224** (영문 7,563 위치) |

224행을 **staged에 실제로 들어 있는 Latin 텍스트**로 재분류했다. 선언된
`language`/`is_donor` 컬럼은 신뢰할 수 없고, `langid`도 양방향으로 틀린다 — 명백한
영어인 프로필 카드 행을 donor로, 앵커 A 행도 donor로 판정했다.

| 구분 | 행 | 영문 위치 | 처리 |
|---|---:|---:|---|
| **진짜 영어** | **12** | **39** | **수정** — 도너 오분류 되돌리고 전파 |
| 언어 중립(간투사·고유명사) | 6 | 171 | KEEP — 어느 분기인지 판정 불가, 표시상 동일 |
| 실제 FR/ES 도너 | 206 | 7,353 | KEEP_DONOR — 영문판 콘솔에 표시되지 않음 |

수정한 12행: `20:17` `829:16` `238:26` `1237:16` `1543:25` `2013:16` `75:14` `1763:37`
`1782:11` `753:12` `1757:26` `236:59` → `translate=yes / is_donor=no / language=en`.

`1757:26`과 `753:12`는 `english` 컬럼 자체가 깨져 있어 staged에서 읽어낸 실제 원문으로
복구했다.

---

## [5] 과거 수정 회귀

| 항목 | 결과 |
|---|---|
| codec: accepted 행의 canonical location 회귀 | **0** |
| codec: `2210:1676` SAVE 선택지 문구 | 유지됨 |
| movie: 2026-08-16 사용자 수정 3건 | **3건 전부 미반영** → 이번에 반영 |
| demo: accepted 2,228행 | **0건 미반영** |

"고쳤던 게 다시 돌아오는" 문제의 실체는 **codec의 되돌림이 아니라 movie.dat의 미빌드**였다.

---

## 파이프라인에서 고친 실제 버그

1. **`mgs3d_script_compare.py make-translation`가 현재 master를 읽지 못했다.**
   `csv.field_size_limit` 기본값 131,072자에 걸려 예외로 죽는다. master의 한 셀은
   551,512자다. 이 경로가 막혀 있으면 **master를 아무리 고쳐도 빌드에 도달하지 않는다.**
2. **`mgs3d_codec_expand_locations.py`가 상대경로 입력에서 리포트를 잃었다.**
   `Path.relative_to(ROOT)`가 예외를 던져, 문서는 쓰이고 리포트만 사라진다.
3. **`--text-identity` 누락은 조용히 568유닛을 잃는다.** 빼고 돌리면 `units`가 224,655 →
   224,087로 줄지만 어떤 경고도 없다. 이번 빌드는 v0.88과 동일하게 켜고 돌렸다.

### 성능 — `resources()` 메모이제이션

`apply`가 유닛마다 `record.resources()`를 호출하고 그때마다 레코드 문자열 영역 전체를
재복호화한다. `crypt()`는 순수 파이썬 바이트 루프로 **7.2 MB/s**, 224,655유닛 × 레코드
문자열 영역 = **59.6 GB** → CPU 99% 점유로 **140분** 경로였다(70분 지점에서 중단).

`self.raw`는 `__init__` 이후 재할당되지 않고 `replace_resources()`는 새 바이트를 반환할 뿐
레코드를 변형하지 않으므로 캐시는 항상 유효하다. 2,326레코드 601,657리소스에 대해
**캐시 결과 == 재계산 결과 (불일치 0)** 를 확인한 뒤 적용했다. **140분 → 15초.**

> **`mgs3d_codec_tool.py apply`는 스테이징 경로가 아니다.** 레이아웃을 보존하지 않아
> 67,204,976 → 63,027,152바이트로 4MB 줄어든다. 실제 경로는
> `mgs3d_build.py --codec-mode safe-fixed` → `mgs3d_gcx_font_tool.py build-korean
> --reuse-freed-font --preserve-record-layout` 이고 여기서 `final_gcx_size_delta=0`이 나온다.

---

## 빌드

```
python tools/mgs3d_script_compare.py make-translation \
    translation/10_master/current/codec.csv \
    translation/40_build_input/v0.89/codec_natural_full_global_page.json \
    --codec experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat \
    --character-map translation/40_build_input/global_page_v2/character-map.json
python tools/mgs3d_codec_expand_locations.py --text-identity \
    --translation translation/40_build_input/v0.89/codec_natural_full_global_page.json \
    --out-doc translation/40_build_input/v0.89/codec-expanded.json \
    --out-report translation/40_build_input/v0.89/codec-expand-report.json
python tools/mgs3d_codec_safe_select.py \
    --translation translation/40_build_input/v0.89/codec-expanded.json \
    --out-doc translation/40_build_input/v0.89/codec-safe-translation.json \
    --out-excluded translation/40_build_input/v0.89/codec-excluded-rows.json
python tools/mgs3d_build.py --partition experiments/2026-08-13-clean-glyph-baseline/clean-tree \
    --output-root builds/v0.89-round5/dist \
    --codec-translation translation/40_build_input/v0.89/codec-safe-translation.json \
    --codec-mode safe-fixed \
    --character-map translation/40_build_input/global_page_v2/character-map.json
python tools/mgs3d_build.py --partition experiments/2026-08-13-clean-glyph-baseline/clean-tree \
    --output-root builds/v0.89-round5/dist \
    --movie-csv translation/10_master/current/movie.csv \
    --character-map translation/40_build_input/global_page_v2/character-map.json
```

빌드 입력: 8,948 → **224,659 units**, dropped 0, GCX failing 0
(v0.88 224,620 대비 **lost 0 / gained 39 / text-changed 48**).
`movie.dat`: 689/689 자막, **+0 bytes**, staged 대비 5런 51바이트만 변경.

## 게이트 결과 — 전부 PASS

| 게이트 | 결과 |
|---|---|
| codec.dat size delta | **+0** (67,204,976) |
| record count / block_start drift / record size drift / resource count drift | **0 / 0 / 0 / 0** |
| **KO → EN 회귀 (전 location)** | **0** |
| 신규 glyph | **0** (`0 Hangul glyphs added`) |
| `final_gcx_size_delta` | **0** |
| 승인 손실 / Korean 손실 / locations 손실 | **0 / 0 / 0** |
| capacity drop | **0**, GCX failing 0 |
| coverage | **95.10%**, reference 자기검증 **0 hits** |
| HPK chain gate | exit 0, `OK: no padded-slot drift` |
| **PARTIAL_APPLICATION** | **224 → 212** (진짜 영어 12행 전부 해소, 신규 혼재 0) |
| 앵커 A 전 location | **3/3 한국어** |
| 앵커 C 전 location | **16/16 한국어** |
| movie.dat 구 문구 잔존 | **0** |

`PARTIAL_APPLICATION unresolved = 0` — 남은 212행은 전부 의도적 제외다:
**FR/ES 도너 206행** + **언어 중립 6행**.

### 마지막에 드러난 것 — `locations` 그룹핑이 서로 다른 문장을 묶고 있었다

12행 중 2행은 분류를 고쳐도 전파되지 않았다. 전파 가드가 **옳았기** 때문이다:

| canonical | 중복 위치 | 관계 |
|---|---|---|
| `753:12` | `2196:14` | 구두점이 다른 **별개 문장** |
| `1757:26` | `1759:17` `1788:43` `1789:43` | 의미가 다른 **별개 문장** |

master가 한 행으로 묶어 놓았을 뿐이다. `locations`를 제거하면 locations 손실 게이트를
어기므로, 누락돼 있던 **행 2개를 append**했다(`2196:14`, `1759:17`+2). 화자는 앞뒤 English
문답으로 확정했고, 한 건은 인용 구호라 화자 추정이 불필요했다. 두 행 모두 신규 글리프 0,
원본 23바이트에 인코딩 23/13바이트로 적합.

## 스테이징

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\`

| 파일 | 크기 | sha256 |
|---|---:|---|
| `codec.dat` | 67,204,976 | `8348377cfee88d36b74adb574ffce21665b6fa71216fd10c7c8d2a251a122be2` |
| `movie.dat` | 229,376 | `a9f9ab9c9e194b22da2b3b12a283b950b46b6a059d415b88d850a1dbd0cb6272` |
| `demo.dat` | 772,935,680 | `43937073…` (변경 없음 — 미반영 0건이라 재빌드 불필요) |

이전 파일은 `Romforge\archive\pre-round5-20260817\`에 보존
(`codec.dat` `6bdec076…`, `movie.dat` `7978657c…`).
`code.bin` / `exheader.bin` / `scenerio.gcx` / `cache.hpk` 변경 없음. **CCI 미생성.**

visual QA 재생성: `output/mgs3d_visual_qa.html` (23,722행).

## 다음 실기에서 확인할 것

1. 초반 배낭 튜토리얼 (`gcx 52/53` 경로)
2. 강하 직전 무전 (`movie.dat` rec 1 / ent 11)
3. SAVE 후 Para-Medic 영화 화제 통화 전체 — Para-Medic 존댓말 / Snake 반말 교차 확인
4. The End 브리핑 (`gcx 1759`)
5. PERSONAL DATA 카드의 부분 미번역 — 이번 범위 밖, 별도 항목
