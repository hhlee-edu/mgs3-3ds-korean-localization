# 실기 최종 QA 결함 4건 — 원인/소스 확정 보고 (2026-08-20)

**1부(아래)는 READ-ONLY 원인 조사**이고, 조사 시점의 staging은
codec.dat `e9026a5e8fe50358…` (diag-2026-08-20-codec-pd77)이다.
**2부 "적용 결과"에서 #4와 #3을 수정해 재빌드·스테이징했다**
(codec.dat `72936022de47a5f8…`). **CCI 미생성, commit/push 없음.**

대상 스테이징: `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0`
기준 clean: `experiments/2026-08-13-clean-glyph-baseline/clean-tree/`

요약: **2건 원인 확정, 1건 구조 정상 확인 + 잔여가설, 1건 원인 배제(우리 변경분 아님)**

| # | 증상 | 상태 |
|---|---|---|
| 4 | 140.85 영어 잔존 | **확정** — 전파 게이트가 4곳 중 2곳 skip |
| 3 | Chin up! = 턱을 위로 | **확정** — master가 애초에 수정된 적 없음 |
| 1 | PERSONAL DATA 깨짐 | 구조는 정상, **행폭 초과 2행 발견**(런타임 미검증) |
| 2 | 무전 UI 이름 매핑 | **codec.dat 원인 배제** — 인덱스 시프트 0 |

---

## #4 — `I suppose calling me "Snake" was your idea of a joke, too.` (140.85)

### 실제 source / record / offset

| 항목 | 값 |
|---|---|
| master | `translation/10_master/current/codec.csv` 데이터 행 **2701** (파일 1444행) |
| canonical | GCX **16** / resource **22** |
| locations | `16:22 ; 17:35 ; 52:22 ; 53:35` (occurrences 4) |
| 상태 | `translate=yes accept=yes language=en is_donor=no` — **FR/ES donor 아님** |
| korean | master에 한국어 존재 |

### staged codec.dat 실측

```
16:22  len=43  → 한국어 적용됨      OK
52:22  len=43  → 한국어 적용됨      OK
17:35  len=60  → 영어 그대로        FAIL
53:35  len=60  → 영어 그대로        FAIL
```

### 원인 (확정)

clean codec.dat에서 **같은 문장이 줄바꿈 위치만 다르다**:

```
16:22 / 52:22   I suppose calling me "Snake" was<0A>your idea of a joke, too.<0A><00>
17:35 / 53:35   I suppose calling me "Snake" was your idea<0A>of a joke, too.<0A><00>
```

둘 다 60바이트지만 **바이트가 다르다.** master는 `english` 열을 줄바꿈→공백으로
정규화해 4곳을 1행으로 접었고, `raw_text`에는 canonical 변형 하나만 남겼다.

`tools/mgs3d_codec_expand_locations.py` 는 중복 위치로 전파할 때
**`if target != source:` 바이트 완전 일치**를 요구한다(다른 문자열을 덮어쓰지 않기 위한
안전장치). 17:35 / 53:35 은 이 검사에서 탈락한다.

빌드 리포트가 이를 이미 기록하고 있었다 —
`builds/v0.9{1,2,3}-*/dryrun/expand-report.json`:

```json
"skipped_total": 570,
"skipped_by_reason": {"original bytes differ from canonical": 570},
"skipped": [ {"canonical":[16,22],"location":[17,35],"reason":"original bytes differ"},
             {"canonical":[16,22],"location":[53,35],"reason":"original bytes differ"} ]
```

**v0.91 / v0.92 / v0.93 세 빌드 모두 570건 동일.**

`--text-identity` 옵션이 공백 정규화 비교(`same_sentence`)로 이 집합을 구제하도록
이미 구현돼 있으나, **세 빌드 모두 이 옵션 없이 돌았다**
(리포트의 `accepted on decoded-text identity` 가 0이라 확인됨).

### 기존 gate가 못 잡은 이유 (확정)

`tools/mgs3d_codec_final_gate.py` 의 커버리지는

```
coverage = accepted_locations / translatable_locations
```

인데 `accepted_locations` 는 **master에서 `accept=yes` 행의 `occurrences` 합**이다.
**빌드된 DAT 바이트를 다시 읽지 않는다.** 전파가 skip돼도 커버리지는 100%로 계산된다.

`codec-final-verification.json` 의 `readback: {rows:67, ok:67}` 도
**이번 패스에 적용한 67행만** 역판독한 것이고 233,587 location 전수 검증이 아니다.

실측 (staged codec.dat 전수 스캔, `tools/mgs3d_codec_partial_application.py`):

```
locations examined 233,587
   KO     226,367
   LATIN    7,172      <- 실기에 영어로 보이는 위치
   EMPTY        48
   MISSING       0
```

**게이트가 "coverage 100.0%"라고 선언한 그 233,587 location 안에 영어가 7,172곳 있다.**

### "212건 전부 FR/ES donor" 판정 검증 → **틀렸다**

staged v0.93 기준 PARTIAL_APPLICATION **234행** 내역:

| is_donor / language | 행 수 | 영어 location 수 |
|---|---:|---:|
| yes / fr | 117 | donor 합계 6,166 |
| yes / es | 93 | |
| **no / en** | **24** | **566** |

**`is_donor=no`, `language=en` 인 행이 24행, 영어 location 566곳.**
문제의 문장은 정확히 이 집합에 있다 (`16:22`, occ 4, KO 2 / EN 2).
donor로 분류돼 제외된 게 아니라, **donor와 무관하게 전파 단계에서 skip된 것**이다.

산출물: `partial-application-staged-v0.93.json` (게임 텍스트 제거, 카운트/위치만)

---

## #3 — `Chin up!` 이 실기에서 `턱을 위로!` 로 나옴

### 실제 source / record / offset

| 항목 | 값 |
|---|---|
| master | `translation/10_master/current/codec.csv` 데이터 행 1442 (파일 1444행) |
| canonical | GCX **2154** / resource **10** |
| locations | `2154:10 ; 2210:43 ; 2211:43` (occurrences 3) |
| master korean | **`턱을 위로!<0A><00>`** |

### staged codec.dat 실측 — 3곳 전부

```
2154:10  86 80 81 05 20 81 4C 81 0E 21 0A 00  -> 턱을 위로!   master와 일치
2210:43  (동일)                                -> 턱을 위로!   master와 일치
2211:43  (동일)                                -> 턱을 위로!   master와 일치
```

### 원인 (확정) — **빌드 결함이 아니다**

`힘내!` 는 **master에 들어간 적이 없다.** 전 버전 대조 결과 전부 `턱을 위로!`:

```
translation/10_master/current/codec.csv
translation/10_master/current/codec.csv.bak-*            (23종 전부)
translation/10_master/archive/codec-older/…direct-v1.csv
translation/10_master/archive/codec-older/…direct-v2-*.csv
translation/10_master/archive/…INTEGRATED-review.csv
```

`translation/10_master/` 트리 전체에서 `힘내` **0건**.
(`힘내` 는 `00_source/script_ref` 와 `20_matching` 원본 자료에만 존재 — master 아님.)

컨테이너 범위도 확인: `Chin up!` 은 codec 3곳이 전부다.
movie.csv / demo.csv / stage authority(1,571행)에 해당 문자열 없음
(stage의 `턱` 히트 2건은 `턱시도`(TUXEDO)로 무관).

**결론: 파이프라인은 master를 3/3 정확히 반영했다. 수정이 master에 반영되지 않은 것이
원인이다.** `힘내!` 로 고쳤다는 산출물이 저장소에 존재하지 않는다 — 반영 경로를 확인해야 한다.

### 기존 gate가 못 잡은 이유

게이트는 "master ↔ DAT 일치"만 본다. 3/3 일치이므로 **정상 PASS가 맞다.**
master 자체가 의도와 다른 경우를 잡는 장치는 현재 없다.

---

## #1 — PERSONAL DATA / PROFILE 화면

PERSONAL DATA master 124행 → **27,132 location** 전수 비교.
clean 영어의 레이아웃 권위는 `0A`×9 + `00` = **10줄**.

### 구조 비교 (clean / v0.91 / v0.92 / v0.93)

| 0A 개수 (clean, v0.91, v0.92, v0.93) | location 수 |
|---|---:|
| (9, **1**, 9, 9) | 25,401 |
| (9, 9, 9, 9) | 1,731 |

**v0.91이 25,401곳에서 10줄을 1줄로 뭉갠 쪽이다.** v0.92/v0.93이 10줄 구조를 복원했다.
즉 "v0.91 정상 / v0.92 붕괴"라는 전제와 측정 결과가 반대다.

### CODENAME 필드 정합성 (clean 영어 대비)

```
v0.91  : 일치  1,540 / CODENAME 소실 5,099 / 불일치 6,493
staged : 일치 13,132 / CODENAME 소실     0 / 불일치     0
```

### 글리프 무결성 (staged, 27,132 location 전수)

```
미매핑 토큰 0종 / 0회, 미매핑 포함 location 0
lead byte 분포  81:260,694  82:294,906  83:36,815  84:202,917  85:29,215  86:4,767  87:4,154
```

### 발견된 실제 이상 — **행 폭 초과 2행**

clean 영어 PERSONAL DATA의 **최대 행 폭 = 200px** (ASCII 8px / 와이드 토큰 16px 환산).
staged에는 이를 넘는 행이 있다:

| 행 내용 | 폭 | location 수 | 최초 위치 |
|---|---:|---:|---|
| `선호 영화:스파이/전쟁 영화` | **208px** | 883 | GCX 15 / res 4 / L2 |
| `선호 마스코트:KEROTAN,GA-KO` | **216px** | 692 | GCX 28 / res 17 / L7 |

합계 **1,575 location**. 둘 다 PROFILE(2페이지) 카드 항목이고, 영어 원본이 한 번도
넘지 않은 폭을 +8 / +16px 초과한다. staged 전체로는 clean 대비 폭이 늘어난 location이
7,344곳이다.

### 상태

- 확정: 문자열 구조·필드·CODENAME·글리프는 staged가 정상. **v0.91이 깨진 쪽**이다.
- 미확정: PERSONAL DATA 창의 실제 클리핑 폭이 200px인지 **런타임 미검증**.
  200px가 창 폭이면 위 2행 1,575곳이 곧 "화면 깨짐"의 원인이다.
- 다음 단계: Citra/Azahar에서 GCX 15 res 4 (선호 영화) 카드 1장만 띄워 클리핑 확인.
  **추측으로 텍스트를 줄이지 말 것** — 창 폭을 먼저 재야 한다.

---

## #2 — 하단 무전 UI 이름 매핑 (Major Tom 미표시 / The Boss→EVA)

### codec.dat 기원 배제 (확정)

| 검사 | clean 대비 결과 |
|---|---|
| GCX 레코드 수 | 2,326 = 2,326 (v0.91/v0.92/v0.93/staged 전부) |
| GCX별 resource 개수 | **0개 GCX에서 차이** |
| GCX별 record 크기 | **0개 GCX에서 차이** |
| PERSONAL DATA CODENAME 필드 | 13,132 / 13,132 일치, 불일치 **0** |
| codec.dat 내 단독 인물명 리소스 | **0건** (`MAJOR TOM`/`THE BOSS`/`EVA` 등 정확 일치 없음) |

**인덱스 시프트가 codec.dat에서 발생할 수 없다.** contact/portrait/name/frequency
테이블은 codec.dat에 문자열로 존재하지 않는다.

### 우리가 실제로 바꾼 파일 전수 (clean-tree ↔ staging, 924 파일 대조)

변경 **177개** = `scenerio.gcx` 169 + 아래 8개.

```
exefs/code.bin                    5,264,144 -> 5,264,540   (CPP 패치)
exheader.bin                      2,048 (내용만)
romfs/codec.dat                   크기 동일, 내용 변경
romfs/demo.dat                    크기 동일, 내용 변경
romfs/movie.dat                   크기 동일, 내용 변경
romfs/stage/r_sna01/resident.hpk  크기 동일, 내용 변경   <- 핸드오프 변경목록에 없던 파일
romfs/stage/r_sna02/resident.hpk  크기 동일, 내용 변경   <- 동일
romfs/stage/v000a_0/cache.hpk     크기 동일, 내용 변경   (히스토리 카드)
```

`ui/*.la2`(cockpit·resident·menu 포함), `slot.dat`, `vox.dat` 는 **전부 무변경**.
무전 UI의 초상화/이름 애셋이 이쪽에 있다면 우리 변경분은 원인이 될 수 없다.

### r_sna01 / r_sna02 resident.hpk 변경 내역 (신규 확인)

zlib 엔트리 **key `453c386e`**, offset `0x0929EF`(sna01) / `0x0AC47E`(sna02),
packed 7,479 / unpacked 21,128 — 양쪽 동일 교체, 압축 해제 후 **7,774 / 21,128 바이트 상이**.

엔트리 정체는 저장소에 문서화돼 있다
(`analysis/ps2_korean/analysis_bundle/formats_and_tools/ps2-korean-port-2026-08-02.md`):

> 영어 런타임의 **static dialogue font**. 런타임 주소 `0x086854F8`.
> 폰트는 엔트리 offset `0x2208` 부터, **glyph 1개당 64바이트 16x16 2bpp**.
> `81xx` = slot 0, `82xx` = slot 81, `83xx` = slot 165.

실측:

- 변경 구간 `0x2208 … 0x5205` = **slot 0 ~ 191** (전체 194 slot 중 191개)
- **오프셋/헤더 테이블(선두 0x2208 바이트)은 clean과 완전 동일** → 인덱스 시프트 없음
- 이 폰트를 담은 스테이지는 clean 전체에서 **r_sna01, r_sna02 두 곳뿐** → 패치 누락 없음

### 결론 / 미확정

- **확정: ID/index 밀림은 없다.** codec.dat·static font 헤더 모두 인덱스 보존.
  "테이블이 밀렸다"는 가설은 기각된다.
- **미확정: 잔여 메커니즘 1개.** static font의 191개 slot(`81xx`/`82xx`/`83xx`)이
  전부 한글 비트맵으로 덮였다. 무전 UI 이름 라벨이 이 토큰 대역을 쓰고 있었다면
  **인덱스가 멀쩡해도 그려지는 그림만 바뀐다** — "Major Tom 미표시 / 다른 이름 표시"와
  증상이 일치한다. 이름 라벨이 ASCII로 그려진다면 무관하다.
- 다음 단계: 실기/에뮬에서 The Boss 항목 hover 시 렌더 토큰을 확인하거나,
  `r_sna01` static font만 clean으로 되돌린 진단 빌드 1개로 증상이 사라지는지 확인.
  **추측 수정 금지 — 확인 전에는 폰트도 이름표도 건드리지 않는다.**

---

## 공통 — 게이트에 뚫린 구멍 (4건 공통 원인)

1. **커버리지가 master 선언값이다.** `accept=yes` 행의 `occurrences` 를 더할 뿐,
   빌드된 DAT를 읽지 않는다 → 전파 skip 570건이 100%로 계산된다.
2. **역판독이 표본이다.** `readback 67/67` 은 그 패스에 손댄 행만이다.
3. **전파 skip이 리포트에만 있고 게이트 실패 조건이 아니다.**
   `expand-report.json` 이 570건을 정확히 기록했는데 아무도 읽지 않았다.
4. **master 자체의 오류를 잡는 장치가 없다** (#3).
5. **렌더 폭/레이아웃 게이트가 없다.** 바이트 용량만 본다 (#1).

권고(미실행): 최종 게이트에
`mgs3d_codec_partial_application.py --only-accepted` 결과 **LATIN == 0** 을 넣고,
`expand-report.json` 의 `skipped_total` 을 0 또는 명시적 허용목록으로 강제할 것.

## 재현 방법

```bash
# 전파 skip 570건
python -c "import json;d=json.load(open('builds/diag-2026-08-20-codec-pd77/dryrun/expand-report.json'));print(d['skipped_by_reason'])"

# staged DAT 전수 영어 잔존
python tools/mgs3d_codec_partial_application.py \
    --codec "C:/Users/hhlee/Desktop/Romforge/output/unpacked/partition0/romfs/codec.dat" \
    --only-accepted --limit 25
```

---

# 적용 결과 (2026-08-20 오후)

지시 순서대로 #4 → #3 → 통합 재빌드 → #2 진단판 준비. **CCI·commit·push 없음.**

## #4 + #3 — production codec.dat 재빌드

빌드 `builds/diag-2026-08-20-codec-textidentity/`, 파이프라인은 wiki 기준 4단계 그대로이고
2단계에만 `--text-identity`를 추가했다.

```
make-translation                            -> 9,014 units (v0.93와 동일)
mgs3d_codec_expand_locations --text-identity -> 227,393 units
capacity --check                             -> 2,289/2,289 ready, deficit 0
build-korean                                 -> 0 glyph added, size delta 0
```

### expand skip: 570 → 2

| | v0.93 | v0.96 |
|---|---:|---:|
| skipped_total | **570** | **2** |
| accepted on decoded-text identity | 0 | **568** |
| original bytes differ (실제 skip) | 570 | 2 |

남은 2건은 **정상 skip이며 allowlist에 등록**했다
(`expand-skip-allowlist.json`). master `locations` 열이 잘못 묶은 경우로,
canonical 1757:26 `You've got to be kidding me.` 가 1788:43 / 1789:43 을 자기 위치로
주장하지만 그 두 곳의 실제 문장은 `You can't be serious.` 다. 전파했다면 **올바른 번역을
틀린 문장으로 덮어썼을 것**이다. 실제로 두 곳은 자기 주인(1759:17)이 이미
`말도 안 돼.` 로 번역해 두었다.

### DAT 역스캔: 비도너 영어 잔존 566 → 0

신규 도구 `tools/mgs3d_codec_dat_residue.py` (clean DAT ↔ built DAT ↔ master 3자 대조).

| | v0.93 | v0.96 |
|---|---:|---:|
| APPLIED | 226,702 | **227,271** |
| ENGLISH (clean 영어 그대로) | 6,747 | **6,181** |
| **그중 비도너 en** | **566** | **0** |
| 그중 fr/es donor | 6,181 | 6,181 |
| OTHER | 7 | 4 |

**LATIN 판정을 쓰지 않은 이유**: accept된 141행은 고유명사라 **의도적으로 ASCII로 번역**돼
있다(`Snake!`, `C3?`, `TUXEDO.`, `Mk22.`, `Object 279?`). Latin 스크립트 휴리스틱은 이
311 location을 "미번역"으로 잘못 잡는다. 그래서 "clean 영어 바이트와 아직 같은가"로 센다.

남은 6,181은 전부 fr/es donor 분기다. OTHER 4건은 location 이중 소유(위 1757:26 계열 3 +
`Remember the Alamo` 2196:14)로, **DAT에는 올바른 주인의 번역이 들어 있다** — 결함 아님.

### 회귀: 내용 변화 0

v0.93 ↔ v0.96 리소스 단위 비교:

```
records          2,326 -> 2,326
record 크기 변경     0 GCX
resource 개수 변경   0 GCX
파일 크기            67,204,976 = clean과 동일
변경된 리소스        687
   의도된 변경         569  (text-identity 568 + Chin up 1)
   trailing NUL 패딩만 118  (내용 동일, string region 재배치)
   실제 내용 회귀        0
의도했으나 무변경      2  (2210:1670 / 2211:1670 = 'Snaaake!' -> 'Snaaake!' 동일 바이트)
```

### Chin up read-back 3/3

master `턱을 위로!` → **`힘내!`** 로 변경(백업 `codec.csv.bak-pre-chinup-20260820`).
`힘`=`84D9`, `내`=`8139` 둘 다 global page에 존재, 12B → 7B 로 줄어 용량 여유.

```
2154:10  -> 힘내!<0A>
2210:43  -> 힘내!<0A>
2211:43  -> 힘내!<0A>
```

### #4 앵커 4/4

```
16:22  17:35  52:22  53:35  -> 전부 '날 "Snake"라고 부른 것도 농담이었나 보군.'
```

### 최종 게이트

`tools/mgs3d_codec_final_gate.py` 에 **신규 게이트 2개 추가**:

- `expand skips allowlisted` — `expand-report.json`의 skip이 0이거나 전부 allowlist에
  있어야 통과. skip 목록이 truncate돼도 실패.
- `DAT English residue = 0` — `dat_residue.nondonor_english_locations == 0`.

```
[PENDING] HUMAN = 0                      verdicts file absent
[PENDING] residual TRANSLATE = 0         verdicts file absent
[PASS   ] donor excluded                 927 rows / 10,768 locations
[PASS   ] valid-english excluded         94 rows / 1,170 locations
[PASS   ] capacity overflow = 0          2289/2289 GCX ready, failing 0
[PASS   ] missing glyph = 0              total_slot_deficit 0, 0 Hangul glyphs appended
[PASS   ] layout preserved               2326 records, 0 changed size
[PASS   ] register QA 1,335 closed       not re-run by policy
[PASS   ] DAT read-back matches master   227271/233456 locations, mismatch 0
[PASS   ] expand skips allowlisted       2 skipped, all 2 allowlisted
[PASS   ] DAT English residue = 0        0 non-donor English locations left
```

구조/글리프/컨트롤 게이트(별도 1-pass 검사, `dryrun/full-gate.json`):
records 2,326=2,326 · resource 개수 차이 0 · record 크기 차이 0 · 파일 크기 clean과 동일 ·
미매핑 글리프 토큰 0 · 종결자 누락 0.

**PENDING 2건은 이번 변경 때문이 아니다.** `codec-review-verdicts.csv`(수동 검수 판정)가
2026-08-20 저작권 정리 때 저장소에서 제거됐고 재생성이 불가능하다. 게이트가 죽지 않고
PENDING을 내도록 고쳤다. `codec-residual-classified.csv`는 재생성했다.

**게이트 음성 테스트(게이트가 실제로 떨어지는지 확인):**

```
v0.93 expand report -> FAIL '570 skipped, 568 NOT allowlisted'
residue 566         -> FAIL
residue 0           -> PASS
skip 목록 truncated  -> FAIL 'cannot verify 5000 skips'
```

### staging

```
codec.dat  e9026a5e8fe50358… -> 72936022de47a5f80319177a81ab6b956dd7077d3934b22d669568c8321a2690
```

staging 변경 파일 수는 그대로 **177개**(scenerio.gcx 169 + 8). codec.dat 외 무변경.

---

## #2 — 진단판 준비 완료 (production 미반영)

`builds/diag-2026-08-20-static-font/` + `tools/mgs3d_diag_static_font_swap.py`.

staged `resident.hpk` 가 clean과 다른 바이트가 **전부 font member 안에만** 있음을 먼저
검증했다 (member 밖 상이 바이트 **0**). 따라서 그 member만 clean으로 되돌리면
**다른 어떤 것도 건드리지 않는다.**

| stage | entry | member | 상이 바이트(내부/외부) | 진단본 sha |
|---|---|---:|---|---|
| r_sna01 | `453c386e` @ `0x0929EF` | 7,491 B | 7,453 / **0** | `719bfa972d26efdd` |
| r_sna02 | `453c386e` @ `0x0AC47E` | 7,491 B | 7,453 / **0** | `2fa31647c40f9b9b` |

사용법 (apply→테스트→**반드시 revert**):

```
python tools/mgs3d_diag_static_font_swap.py apply     # staging 2파일만 clean 폰트로
   RomForge 재패킹 → 무전 연락처 목록 확인
   - Major Tom 이름이 나오는가
   - The Boss 선택 시 EVA로 뜨는가
python tools/mgs3d_diag_static_font_swap.py revert    # 원상복구
python tools/mgs3d_diag_static_font_swap.py status    # 현재 어느 폰트인지
```

apply/revert 왕복을 실제로 1회 실행해 해시로 검증했고 **staging은 production 상태로
되돌려 놓았다** (`r_sna01 4a03cecbb5c38921` / `r_sna02 b08b3125394629ec`).

**판정 기준**: apply에서 이름이 정상화되면 static font가 원인. 증상이 그대로면 폰트는
무관하고 원인은 우리 변경분 밖이다 — `ui/*.la2` · `slot.dat` · `vox.dat` 는 clean과
바이트 동일이므로 후보에서 빠지고, `code.bin`(CPP 21바이트)만 남는다.

---

## #1 — 수정하지 않음 (런타임 확인 대상으로 기록)

지시대로 **손대지 않았다.** v0.96에서도 그대로 남아 있는 항목:

| 행 | 폭 | location 수 | 최초 위치 |
|---|---:|---:|---|
| `선호 영화:스파이/전쟁 영화` | 208px | 883 | GCX 15 / res 4 / L2 |
| `선호 마스코트:KEROTAN,GA-KO` | 216px | 692 | GCX 28 / res 17 / L7 |

clean 영어 PERSONAL DATA 최대 행폭은 **200px**. 위 2행만 이를 넘는다(+8 / +16px).
**창의 실제 클리핑 폭이 200px라는 증거는 아직 없다** — 런타임에서 GCX 15 res 4 카드를
띄워 재보기 전에는 텍스트를 줄이지 않는다.

구조 자체는 정상임이 재확인됐다: 27,132 location 전부 10줄(`0A`×9), CODENAME
13,132/13,132 일치, 미매핑 글리프 0.
