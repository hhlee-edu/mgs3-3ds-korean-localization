# stage/scenerio.gcx 인게임 텍스트 — 분류 + 복구 가능성 조사 (2026-08-19 저녁)

**read-only.** `scenerio.gcx` 문자열 · glyph page · master stage 번역 · DAT · staging ·
build · CCI · commit · push 전부 무변경. 이번 단계는 조사 + worklist + tool 작성까지다.

## 0. 이번 세션에서 새로 확보한 authority — 영문 게임 대본

지시 §2가 지정한 GameFAQs 두 문서는 **도메인 차단(HTTP 403)** 이라 접근이 안 됐고,
Neoseeker 미러도 403이었다. 그러나 **GitHub에 같은 문서의 평문 미러가 있었다**:

```
translation/00_source/english_script/mgs3-game-script.txt
  MHamlin, "Metal Gear Solid 3: Snake Eater Game Script" v1.60 (2006-02-27)
  251,806 B / 7,424행 / sha256 802601f834c7c01a...
  출처 https://raw.githubusercontent.com/amio/mgs-scripts/master/MGS3-SnakeEater/game-script.txt
```

이것이 §2가 요구한 **화자 명시 영문 대본**이다. movie/demo 판정 5건을 이 대본으로
교차검증했고 **모순은 0건**이었다 (자세한 것은 movie/demo 리포트).

**다만 이 대본은 컷신·무전만 담는다. 인게임 적 대사(`Who's that!` 등)는 없다.**

## 1. 코퍼스 — 기존 스캔 재사용 (재분석 불필요)

2026-08-19 오전 스캔이 §5가 요구한 것을 이미 수행했다: 어휘 신호 + `0x1F` 확장문자 신호
+ EN/FR/ES 구조 블록 신호를 **서로 교차검증**했고 **불일치 0건**이다. 단순 period-3를
쓰지 않았고 가변 블록 길이를 탐색했다. 그래서 다시 만들지 않고 그대로 썼다.

| | |
|---|---:|
| scenerio.gcx 분석 | **169 / 169** |
| 문자열 location 총계 | 487,202 |
| 영어 분기 location | 130,903 |
| **한글화 대상 유니크** | **1,571** |
| FR/ES donor 유니크 | 3,308 (번역 대상에서 제외) |

## 2. 카테고리 분류

`stage-worklist-classified.csv` (1,571행). 규칙은 전부 어휘/구조 신호이고,
**규칙이 결정하지 못하면 OTHER로 남겼다.** 따라서 아래 수치는 하한이지 추정이 아니다.

| category | unique | locations |
|---|---:|---:|
| OTHER (미분류로 보존) | 652 | 70,260 |
| FLORA_FAUNA | 393 | 37,353 |
| TUTORIAL_CONTROL | 142 | 4,883 |
| ITEM_WEAPON | 121 | 10,437 |
| AREA_NAME | 76 | 10,533 |
| FOOD | 63 | 5,968 |
| TITLE_AWARD | 44 | 44 |
| MEDICINE | 32 | 2,937 |
| INJURY | 28 | 5,355 |
| **ENEMY_BARK** | **12** | **638** |
| RESULTS | 7 | 1,183 |
| **NPC_DIALOGUE** | **1** | **1** |

**중요한 사실 하나: 적/NPC 대사는 이 코퍼스의 극히 일부다.** 1,571행 중 13행뿐이고
나머지는 도감·아이템 설명·UI다. "적 병사 대사 번역"과 "stage 텍스트 한글화"는
규모가 두 자리수 다르다.

### 적 대사 블록은 구조로 특정된다

`s004a` res1270-1325 덤프로 확인한 배치(영어 → 프랑스어 → 스페인어, 블록 길이 가변):

```
res1296  EN  Speak!            res1298  FR Parle!          res1300  ES ¡Desembucha!
res1297  EN  Answer me!        res1299  FR Réponds-moi!    res1301  ES ¡Contéstame!
res1302-1305 EN Who's that! x4 res1310-1313 FR x4          res1318-1321 ES x4
res1306-1309 EN I see him!! x4 res1314-1317 FR x4          res1322-1325 ES x4
```

`x4` 중복은 랜덤 재생용이다. **번역 시 4개 location을 모두 같은 문자열로 채워야 한다.**

## 3. PS2 한국어 복구 — 핵심 결과

### 3.1 PS2 ↔ 3DS 구조 대응은 실재한다 (이번에 처음 입증)

- 스테이지 이름 **148 / 169 일치**, PS2 카탈로그에 있는 것은 98개.
- `ending` 스테이지에서 **ASCII 앵커로 런 정렬을 확인**했다:
  3DS res319 `You got an EZ GUN.` ↔ PS2 res1540 `EZ GUN<S8107> 획득했습니다`.
  앞뒤로 Single Action Army / Patriot / Camera / Tuxedo / Banana camo / DPM / AUSCAM이
  같은 순서로 이어진다. (상수 오프셋은 아니다 — 구간마다 1칸씩 어긋나므로
  **단조 정렬 + 앵커**로 풀어야 한다. 상수 오프셋을 가정하면 안 된다.)

### 3.2 적 대사는 실제로 복구됐다

| 영어 | EN loc | PS2 한국어 | PS2 occ | 미해결 토큰 | confidence |
|---|---:|---|---:|---:|---|
| `I see him!!` | 228 | **있다!!** | **228** | 0 | **EXACT** |
| `Who's that!` | 208 | **누구냐!** | 222 | 0 | **HIGH** |
| `Speak!` | 89 | **말해!** | 87 | 0 | **HIGH** |
| `Answer me!` | 89 | `대<L229>하라!` | 87 | 1 | UNRESOLVED |

`있다!!` 는 **occurrence 수까지 228로 정확히 일치**한다 — 우연으로 보기 어렵다.
`누구냐!`/`말해!` 는 codec에서 검증된 static 토큰 맵(824C·8143·824B·8132·811E)만으로
미해결 토큰 0으로 풀린다.

`Answer me!` 는 로컬 글리프 `L229` 하나가 막는다. OCR이 confidence 89로 `=` 라고 읽는데
명백한 오독이다. **추측해서 완성하지 않았다.**

### 3.3 그러나 stage 전체 복구는 글리프 해독이 막고 있다

PS2 stage 유니크 1,548행의 해독 상태:

| | 행 |
|---|---:|
| 완전 해독 (현재) | **58 (3.7%)** |
| 로컬 글리프만 막힘 | 385 |
| static 토큰만 막힘 | 137 |
| 둘 다 막힘 | 968 |

미해결 토큰: **로컬 글리프 915 슬롯 / 미상 static 43개**.

해독 곡선 (static 43개는 미해결로 두고 OCR 임계값만 낮춘 경우):

| OCR conf | 완전 해독 |
|---|---:|
| ≥90 | 59 (3.8%) |
| ≥80 | 63 (4.1%) |
| ≥70 | 90 (5.8%) |
| ≥60 | 114 (7.4%) |
| ≥0 (전부 수용) | 418 (27.0%) |

**임계값을 낮추는 것은 추측이므로 하지 않았다.** `L229`를 `=`로 읽은 사례가
왜 위험한지 그대로 보여준다.

**최대 레버리지는 미상 static 43개다.** 이것만 풀면 conf≥90 기준 해독이
**59 → 196 (12.7%)** 으로 세 배가 된다. 137행은 static만 풀리면 즉시 완전 해독된다.

기존 static 맵(`korean_token_map_paragraph.json`, 약 120토큰)은 **이미 전부 적용돼
있다** — 남은 43개는 그 맵에 없는 것들이다(교집합 0).

## 4. Shinsnote — stage 텍스트에는 authority가 없다

지시 §8이 경고한 대로 가정하지 않고 실제로 검정했다.

- 완전 해독된 PS2 stage 58행을 Shinsnote 4,091행과 대조 → **일치 0건.**
- 적 대사 4종의 한국어 후보도 Shinsnote에는 없다 (컷신 문맥의 유사 어휘만 나온다).

**결론: Shinsnote는 movie/demo에는 유효했지만 stage에는 쓸 수 없다.**
stage의 유일한 한국어 authority는 PS2 STAGE.DAT이다.

## 5. 예상 최종 신규 번역 필요량

| | 유니크 |
|---|---:|
| 한글화 대상 전체 | 1,571 |
| PS2에서 지금 EXACT/HIGH로 복구 가능 | **3** (적 대사) |
| PS2 완전 해독분에서 추가 회수 가능 (매칭 미실시) | ≤ 58 |
| static 43개 해결 시 도달 가능 | ≤ 196 |
| Shinsnote에서 복구 가능 | **0** |
| **현 시점 신규 번역 필요 (하한)** | **1,373 이상** |

"≤" 는 **해독은 됐지만 3DS 행과의 매칭은 아직 하지 않았다**는 뜻이다. 매칭까지 끝나야
확정 수치가 된다. 숫자를 부풀리지 않기 위해 상한으로만 적었다.

## 6. 다음 세션 우선순위

1. **미상 static 43개 식별** — 최대 레버리지. 해독 59→196.
   방법: `획득했습니다` 처럼 반복되는 정형 문구에서 토큰을 역산하고, 같은 토큰이
   나오는 모든 문자열에서 일관성을 교차검증한다. **한 문자열에서만 맞는 해석은 버린다.**
2. **로컬 글리프 `L229`** 등 고빈도 글리프 재OCR (현재 OCR은 `=` 오독).
3. **PS2↔3DS 리소스 런 정렬** — ASCII 앵커 + 단조 정렬. 상수 오프셋 금지.
4. OTHER 652행 재분류 (도감 세부 카테고리).

## 7. 산출물

| 파일 | 내용 |
|---|---|
| `stage-worklist-classified.csv` | 1,571행 분류 worklist (지시 §5 필드 전부) |
| `stage-enemy-npc-dialogue.csv` | ENEMY_BARK 12 + NPC_DIALOGUE 1 |
| `stage-enemy-bark-recovery.csv` | 적 대사 PS2 복구 결과 + confidence |
| `stage-classification-summary.json` | 카테고리별 집계 |
| `tools/mgs3d_stage_worklist_classify.py` | 분류기 (읽기 전용) |
