# 세션 인계 (2026-08-05) — PS2대응없음 수기 번역 1차 병합

## 재개 시 가장 먼저 볼 것

커밋 `26729e4`까지 반영됨. RomForge romfs의 `codec.dat`는 현재
SHA-256 `e55644c731e7f3819292d4f6c61055c10c40196e902bc15d2269c1976127e93f`
(2,149/7,634 반영, 구조 검증 통과, **실기/Citra 미검증**). CCI 패킹
전 이 문서 "중요 경고" 섹션과 축약 1라운드 결과를 먼저 읽을 것.

미결정 사항(2026-08-05 오후 해결됨): 남은 5,485행 축약 작업 우선순위
질문 — 결론과 구현은 아래 "우선순위 재계산 (2026-08-05 오후)" 섹션
참고. **최신 파일 구성 (`_5485/_5310/_5224/_skip_86/_skip_23` 전부
삭제됨, 2026-08-05 저녁 최종본):**
- `translator_worklist_4994.csv` — 일반 작업 대상(C_partial +
  B_donor_but_unselected), 기존 `translator_worklist_README.md` 규칙
  그대로 적용.
- `translator_worklist_skip_6_try.csv` +
  `translator_worklist_skip_6_try_PROMPT.md` — 3개 GCX/6행, 예산이
  0보다는 크지만(글자 1~3종) 극도로 빠듯해서 완전히 다른 전용 규칙
  (레코드당 극소수 글자 팔레트 공유)이 필요 — 반드시 이 프롬프트를
  따로 줄 것, 일반 규칙 문서를 주면 안 됨.
- `translator_worklist_skip_17_leave_english.csv` — 17행, 예산이
  **정확히 0바이트**라 한글을 단 한 글자도 못 쓴다. 번역가에게 줄
  필요 없음 — 아무것도 안 해도 원문 영어가 그대로 남는다(이미 라이브
  상태와 동일). 기록용으로만 보관.

### 다시 묻지 말 것 — 용량 확장 아이디어 2건은 기각됨

2026-08-05 오후, 축약만으로 5,485행이 다 안 될 수 있으니 (1) fr/es
전체 삭제로 전역 용량 풀을 만들거나 (2) 전체 번역본 기준으로
글리프셋을 재선정하는 방안을 먼저 검토하자는 질문이 나왔다. 조사
결론:

- **글리프 슬롯은 병목이 아니다.** GCX 레코드당 상한 1,020개, 실제
  사용은 60~100개 수준. 병목은 "레코드당 몇 종류의 새 한글 글자를
  써야 하는가"(글리프 다양성 비용, 글자당 64바이트)이지, 슬롯 개수
  자체가 아니다.
- **fr/es 전역 삭제(레코드 경계를 넘는 공용 풀)는 불가능.** 도너
  재확보는 이미 레코드 단위로는 최대치로 적용 중이고, 레코드 경계를
  넘는 바이트 재배분은 "레코드 오프셋/크기 불변" 절대 조건과
  충돌한다. 이 조건을 완화한 `--grow-records`는 이미 실기 부팅 정지를
  낸 전력이 있어 재시도 대상이 아니다.
- **전체 코퍼스 기준 글리프 재선정도 불필요.** 글리프가 병목이
  아니므로 재선정해도 남는 5,485행 중 얼마가 더 들어갈지에 실질적
  영향이 없다.

즉 남은 유일한 레버는 우선순위 선정 + 표적 축약이며, 이미
`tools/mgs3d_leftover_priority.py`로 구현했다.

## 우선순위 재계산 (2026-08-05 오후)

`analysis/ps2_korean/full_build/select_report_r2.json`(GCX별
candidates/selected/excluded/donor_savings)을 직접 분석해 남은
5,485행을 세 버킷으로 나눴다. 이후 같은 날 오후에 아래 "267행 재확보
시도"에서 6개 GCX가 A→B로 옮겨졌고, 다시 사용자 요청으로 GCX13의
175행(대사가 아님)이 완전히 삭제되어 **최종 5,310행**이 됐다. 최신
파일은 `translator_worklist_5310.csv`(구 `_5485.csv`는 삭제됨).

- `A_no_donor` (86행 / 41개 GCX, 최종): `donor_savings == 0` — 새 글자
  1개(64바이트)조차 예산이 없어 구조적으로 거의 불가능.
- `B_donor_but_unselected` (2,341행 / 1,157개 GCX, 최종): 도너 여유는
  있는데 하나도 안 들어감. `glyph_deficit_bytes`(= 이 GCX 남은
  텍스트의 고유 신규 한글 글자 수 × 64 − donor_savings) 오름차순
  정렬.
- `C_partial` (2,883행): 이미 일부 선택됨 — `excluded` 오름차순.

실측 근거(GCX 563/294/345/316/142/34 표본, `select_report_r2.json` +
라이브 `codec.dat`에서 직접 계산): 이 GCX들은 한글 문자열 자체는
원문 영어보다 바이트가 적게 들지만(문자열 길이는 문제 아님), 이
레코드에 PS2 매칭 대사가 전혀 없어(`old_count=0`) 필요한 60~100개
고유 한글 글자가 전부 신규 글리프(글자당 64바이트)라 도너 여유
1,000~1,200바이트로는 어림도 없었다. → 병목은 문자열 길이가 아니라
"이 레코드에서 몇 종류의 서로 다른 한글 글자를 새로 써야 하는가".

구현: `tools/mgs3d_leftover_priority.py <select_report.json>
<worklist.csv> <output.csv>` — 기존 워크리스트에
`bucket`/`donor_savings_bytes`/`glyph_deficit_bytes`/`note` 컬럼을
추가하고 위 순서로 재정렬. `translator_worklist_README.md`에도 버킷
설명을 추가함.

이 단계는 분석/데이터 준비만 했다 — 라이브 RomForge `codec.dat`나
`full_codec_r2.dat`는 건드리지 않았다. 실제 반영률 재검증은 번역가
작업 이후 별도 세션.

### GCX13 175행 완전 제외 (2026-08-05 오후)

사용자가 워크리스트의 5220-5394번째 줄(A_no_donor 맨 뒤 구간)이
전부 GCX13이고, 텍스트가 `'No:2/264 page:2 radio_picture156
rd_ani_anakonda'` 같은 **동물 도감 라디오 사진 목록의 내부
라벨/식별자**지 실제 대사가 아니라고 지적함. 확인해보니 GCX13의
175개 후보 전부(100%) 이 형식이었다. 번역 대상에서 완전히 제거함
(skip 권장이 아니라 워크리스트에서 삭제) — 이 워크리스트를
처음부터 다시 만들 경우 GCX13은 다시 제외해야 한다.

### 267행(도너 0) 재확보 시도 — 부분 성공, 6개 GCX 구제

사용자 요청으로 47개 GCX(267행)에 실제로 재확보 가능한 도너가
있는지 분류기를 느슨하게 해서 확인했다. 시행착오 끝에 **일부만
안전하게 적용했다:**

1. `confident_non_english_language`의 앵커 판정 자체를 완화하는
   `weak_foreign_anchor()`(단어 매칭 1개만 있어도 앵커로 인정)를
   추가했더니, GCX375의 `'PERSONAL DATA [1/4] CODENAME:PARA-MEDIC
   ... BOSTON,MA.'` 같은 **진짜 영어 캐릭터 프로필 텍스트**가
   "PARA"(파라메딕)와 "MA"(매사추세츠 약자)가 우연히 서/불어 단어
   목록과 일치해서 "외국어"로 오분류됐다(레코드 전체가 도너 블록으로
   쓸림). 기존 코드의 `score>=3` 임계값이 정확히 이런 우연 일치를
   막으려고 있던 것이었다. → **`weak_foreign_anchor`는 폐기, 코드에
   없음.** (나중에 `--protect-review`를 올바른 파일로 바꾼 뒤
   재검증했을 때도 이 오분류는 그대로 재현됨 — 임계값을 낮추는 접근
   자체가 안전하지 않다는 뜻.)
2. 처음엔 훨씬 보수적으로 보이는 "es/fr 단어 목록에 `de` 하나만
   추가"(임계값 `score>=3`은 그대로 유지)도 안전하지 않아 보였다
   — 48개 GCX 중 20개에서 실제 번역 후보가 `language_block_donors`의
   블록 스윕에 쓸려 후보 목록에서 사라지는 것처럼 보였다(예: GCX2136
   2→1). **원인 조사 결과 이건 내 실수였다**: `--protect-review`에
   `analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv`를 넘겼는데,
   이 CSV에는 `container` 컬럼이 아예 없어서
   (`row.get("container")=="codec"` 조건이 항상 거짓) 보호 집합이
   매번 빈 채로 계산되고 있었다 — 기존 코드/파이프라인의 버그가
   아니라 잘못된 입력 파일을 쓴 것. **진짜 protect-review 파일은
   `analysis/ps2_korean/codec_ps2none_protect_review.csv`**(7,634행,
   `container,gcx,resource` 3컬럼, 전부 `container=codec`)이고, 이걸
   쓰면 후보 손실 0건이었다.
3. 올바른 protect-review 파일로 "`de` 단어 추가"만(위 1번의
   `weak_foreign_anchor` 없이) 재검증: 48개 GCX 스코프에서도, 전체
   1,687개 GCX 스코프에서도 **후보 손실 0건**, `donor_audit.py` 통과
   (overlap 0, 분류 실패 0), 새로 발견한 도너 텍스트 전부 수동
   디코드 확인 결과 실제 스페인어/불어 문장(예: `'Veo que llevas un
   uniforme de color verde.'`)이었다. 전체 파일 기준 순수하게 +51줄
   더 선택 가능(비교 기준의 다른 플래그 차이와 무관하게, with-de
   vs without-de만 비교했을 때 항상 같거나 더 많음 — 절대 줄지
   않음을 확인).
4. 결과: 47개 A_no_donor GCX 중 **6개(277, 687, 696, 1017, 1181,
   1279)가 실제로 도너 여유를 얻어 B_donor_but_unselected로 이동**
   (도합 6줄). 나머지 41개 GCX(86줄, GCX13 제외 후 기준)는 여전히
   `donor_savings==0`으로 A에 남음.

**최종 코드 상태**: `es`/`fr` 단어 목록에 `de` 추가만 유지(검증
완료, 안전). `weak_foreign_anchor`는 코드에 없음(폐기). 추가로
`mgs3d_codec_size_neutral_select.py`와 `mgs3d_codec_donor_audit.py`
양쪽에 `csv.field_size_limit(2**31-1)`를 `main()` 앞부분에 추가함
(대형 CSV를 `--protect-review`/`review` 인자로 넘길 때 필드 크기
초과로 죽는 걸 막는 순수 버그 수정, 분류 로직과 무관, 이 프로젝트의
기존 관례와 동일).

**아직 라이브 파일에는 반영 안 함**: 이번에 찾은 6개 GCX의 새 도너
여유(도합 422바이트)는 `select_report_r2.json`을 패치해서
워크리스트 우선순위 계산에만 반영했다. 실제 `codec.dat` 재빌드는
안 했다 — 다음에 실제 빌드를 돌릴 때 `--reclaim-non-english
--reclaim-language-blocks --protect-review
analysis/ps2_korean/codec_ps2none_protect_review.csv`로 다시 돌리면
이 `de` 개선이 자동으로 반영된다(코드에 이미 들어가 있음).

## 마스터 리뷰 CSV 언어 오분류 수정 (2026-08-05 저녁) — 295행

사용자가 skip 파일(당시 86행)의 특정 줄 번호들을 "전부 영어 아님"
이라고 지적하면서 발견됨. 확인해보니 **마스터 리뷰 CSV
(`codec-3ds-INTEGRATED-review.csv`) 자체가 특정 리소스를
`language=en, is_donor=no`로 잘못 태깅**하고 있었다 — 실제로는
스페인어/불어(간혹 독어 1건) 문장인데 "번역해야 할 영어"로 분류된
것. 예 (GCX1239 res33): `english` 컬럼 = `"... Ce sera notre dernier
hommage à Sokolov."`(불어)인데 `korean` 컬럼에는 이미 그 뜻을 정확히
옮긴 한글 번역이 있었다 — 번역가는 실제 내용을 보고 제대로
번역했지만, CSV가 애초에 "이건 영어"라고 잘못 표시해둔 것.

### 조사 범위와 방법

1. 전체 7,634개 후보 중 각 후보 리소스 자체의 텍스트에 대해
   `language_scores()`(en/es/fr/de/it 단어 점수)를 계산 — 자기
   자신이 번역 대상(영어)이 아니라 이미 다른 언어인 걸 찾는 것.
2. 느슨한 기준(en 점수 0 + es/fr/de/it 아무거나 1점 이상)으로 337개
   → de/it 카테고리가 "PARA-MEDIC"의 "para", "Don't die"의 "die"
   같은 **진짜 영어 단어의 우연한 오분류**를 다수 포함한다는 걸
   확인(예: "Don't die on me, Snake."가 독일어로 오탐) → es/fr만
   남기니 290개.
3. 라이브 `codec.dat`에서 원본 바이트를 직접 디코드해 35~40개씩
   두 차례 무작위 샘플 검증 — 전부 진짜 스페인어/불어 확인. 단
   16개는 실제로는 **일본어(Shift-JIS)가 서양 인코딩으로 잘못
   디코드된 잔재**였다("Para-Medic"만 ASCII로 살아남고 나머지는
   깨진 글자, `\x1f` 서양 악센트 제어바이트 패턴과 다름 — 구분
   가능). 이것도 제외 → **274개 확정(자동 검증)**.
4. 사용자가 skip_86 파일에서 직접 44개 줄 번호를 짚어줌 — 대조해보니
   23개는 위 274개와 겹치고, **21개는 너무 짧은 문장이라("Je
   sais.", "Eso parece." 등) 자동 분류기가 놓친 것**이었다(직접
   읽어서 확인, 전부 진짜 서/불어). 수동으로 언어 태그 지정해서
   추가 → **최종 295개**.

### 영향 범위

- 전체 7,634개 후보 중 295개(3.9%)가 대상.
- 이 중 **2개는 이미 라이브 `codec.dat`에 한글로 빌드돼 있었다**
  (스페인어/불어 리소스 슬롯에 한글 텍스트가 들어간 상태). 사용자
  확인: **이 SKU는 영어(슬롯 0) 텍스트만 화면에 표시하고 서/불어
  슬롯은 아예 안 읽으므로 무해함** — 되돌릴 필요 없음, 그냥 죽은
  데이터로 남겨둠.
- 나머지 293개는 아직 안 들어간(excluded) 상태였음 — 즉 잘못된
  분류 때문에 "도너로 못 씀(보호 대상)" 상태로 묶여 있던 진짜
  스페인어/불어 텍스트였다.

### 적용한 수정

1. **마스터 CSV 정정**: `analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv`
   에서 295행의 `status`를 도너 행과 동일한 값으로, `is_donor=yes`,
   `language`를 실제 언어(es/fr)로 변경 + `note`에 사유 기록. 수정
   전 백업:
   `codec-3ds-INTEGRATED-review.csv.bak-2026-08-05-pre-lang-fix`.
2. `mgs3d_codec_ps2none_translation_build.py`로 재생성한 클린 번역
   JSON은 7,634 → **7,339개**(295 감소)로 정확히 일치.
3. 새 `--protect-review` CSV(7,339행)를 이 후보 집합으로부터 직접
   재생성(공식 `codec_ps2none_protect_review.csv`와 동일 스키마).
4. `--reclaim-non-english --reclaim-language-blocks --protect-review
   <새 파일>`로 전체 1,687개 GCX 재계산, `donor_audit.py` 통과
   (overlap 0, 분류 실패 0, donor_count=71,876 — 원래 프로덕션
   빌드의 71,892와 거의 동일한 규모).
5. **중요한 방법론적 함정**: 이 재계산(2개 플래그만 사용)을 곧바로
   워크리스트에 반영하려다, 실제 프로덕션 빌드(`select_report_r2.json`,
   알 수 없는 추가 플래그/`--donor-report` 사용 추정)보다 **낮은
   `selected`/`donor_savings` 값을 내는 GCX가 상당수(207개 중 157개!)
   있다는 걸 발견** — 예: GCX106은 원본이 `donor_savings=14`인데
   최소-플래그 재계산은 0으로 나옴. 원인 불명(아마 `--donor-report`가
   재사용하던 사전 검증 도너 목록에 이 최소 플래그 조합으로는
   재현 안 되는 항목이 있었던 것으로 추정). → **해결책: 언어 오분류
   295개가 걸린 207개 GCX에 대해서만, `donor_savings`를
   `max(원본값, 재계산값)`으로 패치**(더 나빠지는 경우는 원본 유지,
   더 좋아지는 경우만 반영). 나머지 1,480개 GCX는 원본
   `select_report_r2.json`(=라이브 빌드와 100% 일치) 그대로 유지.

### 최종 결과

- skip 파일 86행 중 **45행 삭제**(그 자체가 오분류된 후보였음),
  **18행 구제**(같은 GCX의 다른 후보를 위한 도너 여유가 새로
  생겨서 일반 워크리스트로 이동), **23행만 남음**(20개 GCX, 진짜
  도너 0).
- 전체 5,017개 leftover 중 재계산 결과: `C_partial` 454 GCX/2,725행,
  `B_donor_but_unselected` 1,168 GCX/2,269행, `A_no_donor` 20 GCX/23행.

### 23행 추가 세분화 (2026-08-05 저녁) — "영어로 두거나 글리프 재사용 안 되나" 질문

사용자가 "skip 대상은 그냥 영어로 두거나, 글리프 재사용은 안 되나"
질문. 답:
- **영어로 두는 건 이미 기본 동작.** 번역이 선택 안 되면(예산 초과)
  빌드는 그냥 원문 영어를 유지한다 — 번역가가 따로 할 일 없음.
- **글리프 재사용(다른 GCX와 공유)은 파일 포맷상 불가능.** 글리프
  테이블이 레코드마다 완전히 독립적이라는 건 이미 확인된 사실
  (`tools/mgs3d_gcx_font_tool.py`) — 다른 레코드에서 이미 쓴 흔한
  글자도 이 레코드에서는 새 글자 취급된다.

23행을 `gcx_max_new_hangul_chars`로 다시 나눔:
- **17행(17개 GCX)은 예산이 정확히 0** — 한글 1글자조차 불가능.
  번역가에게 줄 필요 없음 → `translator_worklist_skip_17_leave_english.csv`
  로 분리, 아무 작업 없이 그대로 둔다.
- **6행(3개 GCX: 332, 852, 392)만 예산이 1~3글자로 0보다 큼** —
  시도해볼 가치 있음 → `translator_worklist_skip_6_try.csv` +
  `translator_worklist_skip_6_try_PROMPT.md`로 분리.

### 최종 워크리스트 파일 구성

`translator_worklist_4994.csv`(일반) + `translator_worklist_skip_6_try.csv`
+ `translator_worklist_skip_6_try_PROMPT.md`(예산 있는 극한 케이스) +
`translator_worklist_skip_17_leave_english.csv`(예산 0, 작업 불필요,
기록용). 이전의 `_5224`/`_skip_86`/`_skip_23`은 전부 삭제됨.

라이브 RomForge `codec.dat`는 이번에도 손대지 않음(해시
`e55644c7...` 세션 내내 불변). 이번 수정은 전부 마스터 CSV +
워크리스트 재계산이며, 실제 `codec.dat` 재빌드는 다음 세션 과제.

### AI 일괄 축약 시도 — 실패, 되돌리고 "부족량 컬럼" 방식으로 전환

사용자 요청으로 `translator_worklist_4994.csv` 상위 100행을 Haiku
에이전트로 축약 시도. 에이전트는 정성적 규칙(`rare_chars` 회피,
영어 혼용, 전보체 압축)만으로 전부 균일하게 최대 압축했다. 실제
정확한 공식(`도너여유 + (원본바이트 - 인코딩바이트) - 신규글리프바이트`)
으로 검증해보니:
- 여러 줄은 **원래 번역 그대로도 이미 충분**했는데(예: GCX121은
  손 안 대도 +17) 불필요하게 텔레그램체로 잘림("Snake, hasta
  luego." → "Snake, ADIOS" 등).
- 반대로 GCX606/1591 등 진짜 어려운 줄은 **에이전트가 최대로
  압축했는데도 여전히 부족**(-138, -342).
- 형식 위반도 있었음: 리터럴 `>` 11건(구분자로 오용), 폰트에 없는
  화살표 기호 `↑`/`↓` 3건 — 전부 수동으로 고침.

**결론**: 균일 압축은 잘못된 접근. 사용자 판단: 이건 AI가 번역
문장을 직접 쓰는 게 아니라 **번역가에게 맡기는 게 맞고**, AI는
"얼마나 부족한지" 정확한 숫자만 계산해서 주면 된다. → 100행의 AI
초안은 전부 지우고, 대신 전체 4,994행에 정확한 부족량 컬럼을 추가:

- `original_resource_bytes`: 이 줄의 원본 바이트 상한.
- `current_new_hangul_chars` / `current_glyph_bytes`: 지금(축약 전)
  번역이 이 레코드에서 새로 필요로 하는 고유 한글 글자 수와 그
  글리프 비용.
- `gcx_donor_savings_bytes`: 이 레코드의 재확보 여유 총량.
- `line_net_bytes` = `도너여유 + (원본바이트 - 지금 번역 인코딩바이트)
  - 지금 번역 글리프바이트`.

**1차 계산 버그 발견 및 수정 (같은 날 저녁, 사용자 질문
"그럼 전체 다 손보라는거야?"로 발견):** 처음엔 GCX의 도너 여유
전체를 이 줄 혼자 쓰는 것처럼 계산해서 1,148행이 "이미 충분(안
줄여도 됨)"으로 잘못 나왔다. 실제로는 같은 GCX에 **이미
반영(selected)된 형제 줄이 있으면 그 여유를 먼저 가져간다** — 이걸
안 빼고 계산한 게 원인. 마스터 CSV에서 이미 반영된 형제 줄들의
실제 번역문을 가져와 그 소모분(문자열 절약분 + 글리프 비용)을
먼저 빼고 재계산: **4,994행 중 4,991행이 부족(음수), 정말로 안
줄여도 될 수도 있는 건 3행(GCX2180/1721/1070)뿐.** 즉 사실상
전부 손봐야 한다는 게 정확한 결론. (형제 줄 15건은 마스터 CSV의
`korean` 필드에 이스케이프 안 된 리터럴 `<`가 있어 파싱 실패 —
해당 GCX는 소모분 계산에서 제외돼 약간 더 낙관적일 수 있음, 무시할
수준.)

번역가용 README에 "부족량 계산" 섹션으로 사용법 설명 추가(수정된
정확한 수치 반영). 이 교훈(균일 압축 금지, GCX 내 형제 줄의 예산
소모까지 계산해야 진짜 정확함, AI는 데이터 준비만 하고 번역은
사람이)은 메모리에도 저장함
(`feedback_mgs3d_translation_shortening_approach.md`).

### 다시 확인할 것

이번 수동 검증(21개)에서 드러났듯, 자동 분류기는 여전히 **아주
짧은(2~3단어) 서/불어 문장을 놓친다.** 293개 전부를 찾았다고
장담할 수 없음 — 번역가나 다음 세션에서 "이거 영어 아닌 것 같다"
싶은 줄을 보면 바로 알려줄 것. 마스터 CSV의 `note` 컬럼에
"[2026-08-05: language mislabel fix...]"로 검색하면 이번에 고친
295건을 전부 찾을 수 있다.

## 배경

`docs/ps2-port-handoff-2026-08-03.md`가 여전히 파이프라인 전체의 기준
문서다. 이 문서는 그 이후 진행된 작업 하나만 다룬다.

최우선 목표는 변하지 않았다: **PS2 정식 한글판 텍스트·글꼴 자산을 3DS판에
이식하는 것**이며, 새 번역을 만드는 것이 아니다. 다만 PS2에 대응 문장이
없는 위치(`status=PS2대응없음`)는 PS2 자산을 이식할 수 없으므로 3DS 영어
원문에 직접 한국어를 수기로 입력해야 한다. 이번 작업은 그 수기 번역 결과를
마스터 리뷰 CSV에 반영하는 병합 작업이다.

## 무엇을 했나

입력 파일:

- `analysis/ps2_korean/codec-3ds-INTERGRATED-review.csv_trans/1999final.csv`
  — `status=PS2대응없음`인 9,116행 중 1,999행을 뽑아 수기 번역용으로
  내보낸 작업본. 1,999행 중 720행에 `korean` 컬럼이 채워져 있고 1,279행은
  아직 비어 있다.
- `analysis/ps2_korean/codec-3ds-INTERGRATED-review.csv_trans/trans1999.csv`
  — 같은 1,999행의 축약 컬럼 작업본(참고용, 이번 병합에는 사용하지 않음).
- `docs/codec-3ds-remaining-1999.csv` (저장소 루트, 미추적) — 같은
  1,999행의 번역 이전 원본. `korean`이 전부 비어 있다. 이번 작업의 대상이
  아니며 참고 스냅샷으로만 남긴다.

대상 파일(마스터):

- `analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv` (전체 22,362행)

병합 전 확인한 사항:

- `1999final.csv`의 1,999개 (`gcx`,`resource`) 키가 마스터의
  `status=PS2대응없음` 9,116행 중 정확히 1,999개와 1:1로 일치하고 중복이나
  불일치가 없다.
- `korean` 컬럼을 제외한 모든 컬럼(`translate`,`accept`,`priority`,
  `status`,`language`,`is_donor`,`text_kind`,`blocker`,`occurrences`,
  `locations`,`gcx`,`resource`,`english`,`replacement`,`missing_count`,
  `missing_glyphs`,`record_headroom`,`raw_text`,`note`)은 두 파일에서
  완전히 동일했다. 즉 이번 병합은 순수하게 `korean` 값만 옮기는 작업이다.

수행한 작업:

1. 병합 전 마스터를
   `analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv.before-1999-merge-2026-08-05.bak`
   로 백업했다 (`analysis/`는 `.gitignore`로 전체 미추적이라 git 안전망이
   없음).
2. `1999final.csv`에서 `korean`이 비어 있지 않은 720행을 (`gcx`,`resource`)
   키로 마스터에 반영했다.
3. 병합 전/후 마스터를 전체 필드 비교로 검증했다:
   - 전체 행수 22,362 → 22,362 (변화 없음)
   - 변경된 값은 `korean` 필드 720건뿐, 다른 모든 필드는 0건 변경
   - 변경된 720행은 전부 `status=PS2대응없음`이었다 (예상대로)

결과: 마스터 CSV의 `PS2대응없음` 9,116행 중 720행이 이제 한국어 번역을
포함하고, 8,396행은 여전히 비어 있다 (이 중 1,279행은 `1999final.csv`
작업본에 있지만 아직 미번역, 나머지는 애초에 1,999행 배치 밖).

## 반영되지 않은 것 / 주의

- `analysis/ps2_korean/codec-3ds-INTERGRATED-review.csv_trans/codec-3ds-INTEGRATED-review.csv`
  (작업 폴더 안의 사본)는 병합 전에는 마스터와 바이트 동일했지만, 이번
  병합으로 마스터만 갱신했으므로 **이제 이 사본은 구버전이다.** 착각하지
  말 것.
- 이 병합은 리뷰 CSV 단계 갱신일 뿐이다. 이 마스터 CSV
  (`codec-3ds-INTEGRATED-review.csv`)를 직접 소비해 codec.dat/HPK를
  재빌드하는 자동화 도구는 아직 저장소에 없다 (`tools/`에서 해당 파일명을
  참조하는 스크립트 없음 확인함). `tools/mgs3d_english_review_to_build.py`는
  `disposition`/`container` 컬럼을 요구하는 다른 스키마이고,
  `tools/mgs3d_codec_untranslated_select.py`는 `미선택`/`문자열초과`
  상태의 PS2 후보 선택용이라 `PS2대응없음` 경로와는 다르다. 다음 빌드
  단계로 넘어가려면 이 마스터 CSV의 `korean` 값을 실제 GCX 문자열 공간에
  맞춰 넣는 변환 도구가 별도로 필요하다.

## 다음 작업

1. 남은 1,279행(`1999final.csv` 기준) 수기 번역 계속 진행.
2. `PS2대응없음` 경로 전용으로 마스터 CSV의 `korean` 값을 GCX 문자열
   공간·글리프 제약에 맞춰 검증하고 빌드 입력으로 변환하는 도구 작성
   (기존 `mgs3d_codec_untranslated_select.py`/`mgs3d_english_review_to_build.py`
   패턴을 참고하되 스키마가 다름을 감안).
3. 나머지 8,396행 중 `1999final.csv` 배치 밖에 있는 행들도 같은 방식으로
   배치 작업 계획 수립.

## 진행률 점검 (2026-08-05, 병합 직후)

CCI 빌드는 사용자가 RomForge 도구로 직접 수행한다. 이 저장소/CSV
작업의 역할은 RomForge unpacked 경로(`C:\Users\hhlee\Desktop\Romforge\output\unpacked\...`)
에 들어갈 파일을 준비하는 것까지다.

마스터 `codec-3ds-INTEGRATED-review.csv` 기준 (전체 22,362행,
`외국어분기` 12,792행은 donor라 번역 대상 아님):

| status | 총 행수 | korean 채움 | 비율 |
|---|---|---|---|
| PS2대응없음 | 9,116 | 7,640 | 83.8% |
| 미선택 | 451 | 451 | 100% |
| 문자열초과 | 3 | 3 | 100% |
| 외국어분기(제외) | 12,792 | 0 | 해당없음 |
| **번역 대상 합계** | **9,570** | **8,094** | **84.6%** |

`PS2대응없음` 잔여 1,476행 내역:
- 1,279행: `1999final.csv` 작업 배치 안에 있고 아직 미번역 (진행 중인 배치).
- 197행: 그 배치 밖에 있고 아직 어떤 작업본에도 뽑히지 않음.

`미선택`/`문자열초과`는 이미 한국어가 채워져 있지만 이건 번역 문제가
아니라 GCX 고정 문자열 공간·정적 글꼴 슬롯에 못 들어가는 용량 문제다.

**RomForge 현재 상태 확인:**
`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\codec.dat`
(67,204,976바이트, 2026-08-03 22:12 수정)는 오늘 마스터 CSV에 반영한
720행 병합 이전에 빌드된 파일이다. 즉 오늘 작업한 번역은 아직 RomForge
쪽 `codec.dat`에 전혀 반영되지 않았다.

**결론:** 마스터 CSV의 `korean` 값을 실제로 RomForge `codec.dat`/HPK에
써 넣는 변환·빌드 도구가 없으면, CSV에 아무리 번역을 채워도 게임에는
반영되지 않는다. 다음으로 필요한 것은 이 CSV→codec.dat 인게임 병합
도구다 (마스터 CSV → 문자열 크기 검증 → GCX 레코드 재기록, 파일 전체
크기·레코드 경계 불변 조건 준수).

## 용량/글리프 사전 검증 (2026-08-05, 도구 제작 전)

빌드 도구를 만들기 전에 `PS2대응없음` 번역 7,640행(마스터 CSV 기준
korean 채워진 전체)을 실제 RomForge `codec.dat`
(`72829c26...943810`, 2026-08-05 기준 실측 SHA-256 — 문서
`ps2-port-handoff-2026-08-03.md`에 적힌 값과 다름, 사용자가 별도로
RomForge 빌드를 이미 갱신했기 때문. 항상 실측 파일을 기준으로 할 것)
기준으로 `tools/mgs3d_gcx_font_tool.py capacity`로 검증했다.

### 데이터 정합성 문제 (자동 수정함, 재현 가능)

- 제로폭 공백(U+200B) 20건 — 제거.
- 말줄임표 문자(…, U+2026) 4건 — `...`으로 치환.
- 4자리 묶음 제어토큰(`<1f22>`, `<1f40>` 등, 22개 유닛) — `render_bytes`가
  기대하는 2-hex 토큰 형식이 아니어서 `parse_rendered`가 리터럴 `<`로
  오인해 즉시 에러. `<1F><22>` 처럼 2-hex 토큰 두 개로 분리해 수정.

### 사람 검토가 필요한 데이터 결함 (6건, 자동 수정 안 함)

`korean` 컬럼에 훼손된 것으로 보이는 문자열 6건 발견. 임의로 고치지
않고 그대로 남겨둠:

- `é`/`á` 포함 3건은 프랑스어/스페인어 원문이 깨진 형태로 보임
  (예: `aétédéveloppée` ← `a été développée`가 공백 소실, `Ultim á tum`
  ← `Ultimátum`). 원래 도너 언어를 그대로 둘지 한국어로 다시 번역할지
  결정 필요.
- `·`(가운뎃점) 포함 3건은 정상적인 한국어 표기(`진정·항우울` 등)이지만
  codec 서양 문자 세트에 `·` 글리프가 없음. 대체 문자(`,`, `/` 등) 필요.

### 글리프 용량 검증 결과 (record-local 고정 레이아웃 기준)

`--preserve-record-layout` + `--reuse-freed-font` 방식(레코드 경계를
전혀 움직이지 않고, 교체되는 리소스가 놓아준 글리프 슬롯만 재사용)
기준으로:

- 대상 GCX 1,687개 중 **8개만 추가 글리프 없이 통과** (0.5%)
- 나머지 1,679개 GCX가 글리프 부족, 총 부족분 **73,513 슬롯**
- 부족분 분포: 1~5개 42건, 6~20개 426건, 21~50개 711건, 51~100개
  385건, 100개 초과 115건 (중앙값 34)
- 최악 사례: GCX 443 (부족 569), GCX 243 (부족 560), GCX 32 (부족 267)

**중요한 캐비어트:** 이 수치는 `capacity` 명령이 레코드-로컬 글리프
재사용만 계산한 결과다. 이미 실기 검증을 통과한 codec HPK 공용 정적
글꼴 페이지(`453C386E`, `81/82/83`, 165~191자, 여러 GCX가 공유)를
전혀 반영하지 않는다. 즉 최악의 경우(worst case) 수치이며, 자주 쓰는
한글 글자를 공용 정적 페이지로 옮기면 실제 부족분은 크게 줄어들 가능성이
높다. 다음 검증 단계는 이 7,634개 유닛의 글자 빈도를 집계해 공용 정적
페이지가 몇 %를 커버하는지, RomForge에 실제로 살아있는 정적 페이지
글자 집합이 무엇인지 확인하는 것이다.

**사용자 지시:** 실 적용 시 글리프·용량 문제에 대비해 번역을 균일화할
것. 영·한 혼용을 최대한 허용하고, 용량 확보를 위해 가급적 영어 사용을
권장한다. 검증(이 섹션 + 공용 정적 페이지 커버리지 확인)을 마친 뒤에
CSV→codec.dat 변환 도구 제작으로 넘어간다.

검증에 쓴 스크립트/산출물은 세션 스크래치패드에만 있고 저장소에는
없음 (`build_translation_json.py`, `ps2none_translation.json`,
`ps2none_capacity_report.json`). 재현하려면 위 절차(정합성 수정 →
`mgs3d-codec-translation-v1` JSON 생성 → `capacity` 실행)를 그대로
다시 밟으면 된다.

## 공용 정적 페이지 커버리지 시뮬레이션 (2026-08-05)

7,634개 유닛에 필요한 고유 한글 글자는 총 **1,068자**다. 라이브
RomForge HPK(`stage/r_sna01|r_sna02/resident.hpk`)에 실제로 어떤
글자가 이미 들어있는지는 비트맵 OCR 없이는 알 수 없다 (토큰 슬롯
자체엔 문자 라벨이 없고, 빌드 시점에 쓰인 배치 JSON도 지금 라이브
HPK 해시와 일치하는 사본이 저장소에 없음 — `resident_r_sna01_static_*.hpk`
6종 전부 라이브 해시와 불일치 확인함). 대신 "자주 등장하는 글자부터
공용 페이지에 채운다"는 최적 배치를 가정하고, 공용 페이지 크기별로
레코드-로컬 부족분이 얼마나 줄어드는지 시뮬레이션했다:

| 공용 페이지 글자 수 | 통과 GCX | 총 부족 슬롯 |
|---|---|---|
| 0 (기준) | 8/1,687 | 73,513 |
| 100 | 31/1,687 | 28,257 |
| 165 (문서상 현재 한도) | 67/1,687 | 19,191 |
| 191 (문서상 현재 한도) | 96/1,687 | 16,663 |
| 250 | 170/1,687 | 12,121 |
| 300 | 233/1,687 | 9,202 |
| 400 | 441/1,687 | 5,156 |
| 500 | 748/1,687 | 2,879 |

**결론:** 문서에 기록된 현재 공용 페이지 한도(165~191자)로는 최적
배치를 가정해도 통과율이 4~6%에 그친다. 부족분이 의미 있게 줄려면
공용 페이지가 400~500자 규모여야 하는데, 이게 HPK 엔트리 크기
제약상 가능한지는 아직 확인 안 됨 (다음 조사 대상).

최악 사례 GCX(443, 243, 32 등)는 리소스 대부분이 서로 다른 문장이라
(예: GCX443 538개 리소스 중 532개가 서로 다른 텍스트) 문자열 중복
제거(`--alias-adjacent-strings`/`--alias-all-strings`)로는 별로
못 줄인다. 이 레코드들은 실제 번역 분량 자체를 줄이는 수밖에 없다.

**다음 조사 필요:**
1. HPK 정적 엔트리(21,128바이트 고정)가 165/191자보다 더 큰 문자
   집합을 담을 수 있는지 (엔트리 크기 자체는 절대 조건상 못 늘리므로,
   기존 비-한글 슬롯을 얼마나 더 회수할 수 있는지가 관건).
2. 라이브 HPK에 실제로 어떤 글자가 들어있는지 비트맵 OCR로 확인
   (`mgs3d_glyph_ocr.mjs`/`mgs3d_ps2_font_sheet.py` 등 기존 도구 활용).
3. 사용자 지시대로 영·한 혼용/영어 우선 축약 규칙을 세워 GCX
   443/243/32 등 고유 어휘가 큰 레코드부터 적용.

## 도너(fr/es) 삭제 + 실제 codec.dat 빌드 (2026-08-05, 완료)

공용 정적 페이지만으로는 부족(위 시뮬레이션)해서, 사용자 지시대로
**프랑스어/스페인어 도너 분기를 삭제해 그 바이트로 한글 용량을
확보**하는 경로로 진행해 실제 RomForge `codec.dat`까지 반영했다.

### 사용한 도구 (전부 기존 저장소 도구, 기존 파이프라인과 동일 계열)

- `tools/mgs3d_codec_ps2none_translation_build.py` (신규) — 마스터
  CSV의 `PS2대응없음` + `korean` 채워진 행을 `mgs3d-codec-translation-v1`
  JSON으로 변환. 정합성 수정 4종을 자동 적용:
  1. 제로폭 공백(U+200B) 제거 — 20건.
  2. 말줄임표(…) → `...` — 4건.
  3. 4자리 묶음 토큰(`<1f22>` 등) → 2-hex 토큰 두 개(`<1F><22>`) — 22건.
  4. 인용부호로 쓰인 리터럴 `<`/`>`(예: `<On the Beach>`) →
     `<3C>`/`<3E>` 이스케이프 — 3건.
  자동 수정 불가 6건(é/á/· 포함, 프랑스어/스페인어 훼손 의심)은
  제외하고 `codec_ps2none_flagged.json`에 남김 (사람 검토 필요).
  결과: 7,640행 중 7,634개 유닛의 클린 JSON
  (`analysis/ps2_korean/codec_ps2none_translation.json`).
  `python tools/mgs3d_codec_tool.py validate-translation`로 무결성
  확인 완료 (units=7634, GCX=1687, Hangul=1068).
- `tools/mgs3d_codec_size_neutral_select.py --reclaim-non-english
  --reclaim-language-blocks --protect-review ...` — 어느 번역이
  실제로 들어갈 수 있는지 선택.
- `tools/mgs3d_codec_donor_audit.py` — 도너로 지정된 리소스가 보호
  대상과 겹치지 않는지 필수 검증.
- `tools/mgs3d_gcx_font_tool.py build-korean --preserve-file-size
  --reuse-freed-font` — 실제 codec.dat 재작성 (레코드 크기 불변,
  내부 문자열/폰트 경계만 재배분).
- `tools/mgs3d_codec_offset_diff.py` (신규) — 빌드 후 모든 GCX
  레코드의 시작 오프셋·크기가 원본과 동일한지 재검증하는 독립
  스크립트. `mgs3d_verify_build.py`는 `codec_mode`가 `"...fixed"`로
  끝날 때만 이 검사를 하므로, `--preserve-file-size` 경로에는
  적용 안 돼 별도로 만들었다.

### 발견한 버그 하나 고침

`mgs3d_codec_size_neutral_select.py`의 `--reclaim-language-blocks`가
`--protect-review`를 무시하는 버그가 있었다(코드 307번째 줄,
`language_block_donors(resources, set())`로 항상 빈 보호 집합을
넘기고 있었음). 이 상태로 그냥 돌렸으면 GCX32 기준 대상 번역
54개 중 47개가 "도너"로 분류돼 조용히 지워질 뻔했다(실제 파일럿에서
확인). `protected.get(gcx, set())`을 넘기도록 한 줄 수정해서
해결 — GCX32 파일럿 결과가 candidate 7개 → 54개(정상)로 즉시
바뀌는 것으로 검증했다.

### 결과

- 도너(fr/es 등) 삭제 대상: 71,892개 리소스, 보호 대상(7,634개)과
  겹침 0건, 언어 분류 실패 0건 (`donor_audit.json`).
- 최종 선택: 7,634개 대상 중 **2,147개(28.1%)**가 실제로 codec.dat에
  들어감. GCX 1,687개 중 489개에서 뭔가는 들어갔고, 34개는 100%
  들어감(그중 최악 사례였던 GCX443 538/538, GCX243 332/332 전부
  포함 — 이 두 레코드는 도너 텍스트가 커서 통째로 해결됨).
  1,198개 GCX는 도너 여유가 없어 0개 선택.
- 빌드 산출물: `analysis/ps2_korean/full_build/full_codec.dat`,
  SHA-256 `e7dd99ba4b049a9e9bbe6d7fba996bd451a26260e5de59c23ad896914db758ae`,
  1,640개 GCX 레코드 변경, 8,595개 한글 글리프 추가.
- 구조 검증(`mgs3d_codec_offset_diff.py`) 전부 통과: 파일 전체 크기
  67,204,976바이트로 원본과 동일, 레코드 개수 동일, 건드리지 않은
  47개 GCX 포함 전 레코드의 시작 오프셋·크기가 원본과 100% 일치.
- 내용 스팟체크(디코드해서 원문과 대조): 한글이 로컬 글리프 토큰으로
  올바르게 인코딩됨, 제어 토큰(`<0A>`, `<1F><40>` 등) 원형 보존 확인.

### RomForge 반영

- 기존 RomForge `codec.dat`를
  `codec.dat.before-ps2none-donor-build-2026-08-05.bak`로 백업
  (해시 `72829c26...` 확인, 원본과 100% 동일).
- 새 `codec.dat`(위 SHA-256)를 RomForge unpacked 경로에 덮어씀:
  `C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\codec.dat`
- **CCI 패킹은 사용자가 RomForge로 직접 진행.**

### 중요 경고 — 실기/Citra 검증 안 됨

`--preserve-file-size --reuse-freed-font` 조합과 이 규모(수천 유닛,
7만 개 이상 도너 리소스)의 도너 리클레임은 이 저장소에 실행된 전례가
없다. 구조 검증(오프셋, 파일 크기, capacity)과 텍스트 인코딩
스팟체크는 철저히 했지만, **실제 3DS/Citra에서 정상 렌더링되는지는
아직 확인 안 됐다.** CCI 패킹 후 Citra 또는 실기로 먼저 확인할 것
— 특히 대량으로 변경된 GCX(443, 243 등 큰 코덱 대화)를 우선 확인.

### 남은 미해결분 (Step 5)

- 나머지 5,487개(72%)는 이번 배치에 안 들어감 — 도너 여유 부족.
- 부족분이 큰 순으로 정렬한 GCX 목록:
  `analysis/ps2_korean/full_build/leftover_by_gcx.csv` (1,653개 GCX).
- 상위 50개 GCX의 미선택 행 729개를 뽑아
  `analysis/ps2_korean/full_build/abbreviation_candidates.csv`에
  정리함. 각 행에 "다른 미선택 행에서 2번 이하로만 등장하는 희귀
  글자"를 `rare_chars` 컬럼으로 표시해 축약 시 우선 손볼 단어를
  짚어준다. `shortened_proposal` 컬럼은 비워둠 — 번역 품질은 자동화
  위험이 커서 실제 축약 문안은 사용자 검토/작성용으로 남긴다.
- 6건(é/á/·)은 사용자 지시로 마스터 CSV에서 `korean` 값을 비워
  삭제했다(GCX/자원: 680/30, 239/26, 241/144, 1727/2541, 2203/18,
  234/20). 이 6건은 애초에 codec.dat 빌드에 들어간 적이 없어서
  (처음부터 `codec_ps2none_translation.json`에서 제외됨) 빌드
  재실행은 필요 없다. 마스터는 다시 `status=PS2대응없음`,
  `korean` 공란 상태로 돌아갔으므로 재번역 대상으로 남는다. 삭제
  전 마스터 백업:
  `analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv.before-clear6-2026-08-05.bak`.

### 재현 스크립트 (신규, 저장소에 커밋됨)

- `tools/mgs3d_codec_ps2none_translation_build.py`
- `tools/mgs3d_codec_offset_diff.py`

### 주의 — RomForge romfs 폴더는 항상 정리 상태로 유지

RomForge 리팩 도구는 `romfs` 폴더 전체를 스캔해서 그대로 패키징한다.
`codec.dat` 백업을 romfs 안에 나란히 남겼다가(`codec.dat.before-*.bak`)
CCI 용량이 비정상적으로 커지는 문제가 있었다(사용자가 직접 진단).
**백업은 항상 romfs 트리 밖(`analysis/ps2_korean/` 등)에 둔다.**
이번에 romfs 안에 있던 백업은
`analysis/ps2_korean/romforge_codec.dat.before-ps2none-donor-build-2026-08-05.bak`
로 옮겼다.

## 축약 1라운드 — GCX32 / GCX2117 (2026-08-05)

부족분 큰 순 GCX 상위에서 GCX32(54개 중 17개 미선택)와
GCX2117(31개 중 27개 미선택) 두 곳의 미선택 42행을 영·한 혼용/축약
번역으로 교체하고 파이프라인을 다시 돌렸다.

- 마스터 CSV 42행 교체 전 백업:
  `analysis/ps2_korean/codec-3ds-INTEGRATED-review.csv.before-abbrev-round1-2026-08-05.bak`
- 결과: 전체 선택 2,147 → **2,149**(+2). GCX32는 37 → 38, GCX2117은
  4 → 5.
- 구조 검증 통과(오프셋/크기 전부 동일), 도너 오디트 통과(겹침 0건).
- RomForge에 반영: 새 SHA-256
  `e55644c731e7f3819292d4f6c61055c10c40196e902bc15d2269c1976127e93f`.
  직전(2,147개 반영본)은
  `analysis/ps2_korean/romforge_codec.dat.round1-2147-2026-08-05.bak`
  로 romfs 밖에 백업.

**관찰:** 42행 축약 작업으로 겨우 2행만 추가로 들어갔다. GCX32/2117은
도너(fr/es) 텍스트가 거의 없는 레코드라(과학 강의·라디오 대화 장면)
아무리 짧게 줄여도 근본적으로 여유 공간 자체가 거의 없다 — 이미
선택 알고리즘이 가장 적합한 조합을 그리디하게 골라놓은 상태라, 축약은
"턱걸이로 몇 개 더 넣는" 정도의 한계 효과만 있다. 반대로 GCX443/243처럼
도너가 풍부한 레코드는 축약 없이도 이미 100% 들어갔다. 향후 축약
작업은 **어휘량 큰 순서보다 "부족분이 작고 도너 여유가 조금이라도
있는 GCX"부터** 하는 게 노력 대비 효과가 클 가능성이 높다 — 이 판단은
다음 라운드에서 실측으로 검증할 것.
