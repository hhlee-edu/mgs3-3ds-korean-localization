# Stage/scenerio.gcx pretranslation handoff

## Scope

- Analysis and tool preparation only.
- No Korean translation was written.
- No `scenerio.gcx`, master, staging, codec/movie/demo, build, CCI, commit, or push was performed.
- The existing 169-file scan/worklist was reused; no new parser was introduced.

## Current analysis

- EN-visible unique rows: 1,571
- EN occurrences: 149,592
- READY rows: 3 (the already-established reference rows)
- New translation rows: 1,568
- Branch conflicts: 0
- OTHER: 652 -> 323
- OTHER reclassified: 329
  - `SHORT_LABEL`: 208
  - `SYSTEM_UI`: 59
  - `MUSIC_TITLE`: 61
  - `STATUS_MESSAGE`: 1
- Existing exact translation candidates: 1 (`SAVE` from codec: `저장<00>`); no fuzzy candidates were emitted.
- the script reference text search found 202 exact English-string hits, but they were not promoted to translation candidates because an unambiguous paired English-to-Korean record was not established; no inferred Korean was added.
- Glossary candidates: 664 repeated terms, with no newly invented Korean.

## Duplicate/group analysis

- Translation groups: 29
- Safe automatic-reuse groups: 27, covering 70 rows; theoretical reduction: 43 translation units.
- Context-review groups: 2, covering 4 rows.
- Grouping is recorded separately and does not auto-populate translations.

## Capacity and risk

- Capacity/risk fields were added for all 1,571 rows.
- The capacity value is the original fixed resource-slot byte bound; it is a preflight gate, not a translation.
- Preliminary risk counts: HIGH 1,516, MEDIUM 11, LOW 44.
- HIGH is intentionally conservative because 1,507 rows have fewer than 16 free glyph slots under the current glyph-pool estimate. Recheck this gate after the final glyph allocation policy is fixed.
- Special control/icon sequences are tracked separately; 141 rows contain known escape/icon controls.

## Apply and final-gate preparation

- Dry-run apply passed: 525 EN resources would be changed from the 3 READY rows, errors 0.
- The apply tool only targets structurally resolved EN locations, preserves FR/ES donor locations, preserves known control-token streams, enforces resource capacity/glyph encoding, and writes only to a separate output root when `--apply` is explicitly supplied.
- Final gate self-test passed against the same source tree: 169/169 before and after, parse pass, 0 changes, donor unchanged, controls preserved, errors 0.

## Files

- Worklist: `docs/evidence/2026-08-19-stage-translation-worklist/stage-translation-worklist.csv`
- Expanded analysis: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-worklist-expanded.csv`
- Groups: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-translation-groups.csv`
- Glossary candidates: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-glossary-candidates.csv`
- Exact existing candidates: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-existing-translation-candidates.csv`
- Summary: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-pretranslation-analysis-summary.json`
- Apply dry-run report: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-apply-dryrun.json`
- Final-gate report: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-final-gate.json`
- Apply tool: `tools/mgs3d_stage_apply.py`
- Final gate: `tools/mgs3d_stage_final_gate.py`
- Analysis tool: `tools/mgs3d_stage_pretranslation_analysis.py`

---

# Session 2 — ENEMY_BARK / NPC_DIALOGUE 번역 (2026-08-19 밤)

## 결과

- 대상 **13행** (ENEMY_BARK 12 + NPC_DIALOGUE 1) — **전부 완료**
- **신규 번역 10** / **대사집 재사용 3** (`있다!!` `누구냐!` `말해!` — 손대지 않음)
- **신규 글리프 0** · capacity 실패 **0** · HUMAN **0**
- dry-run apply: **635 EN 리소스 / 89 스테이지 / 오류 0** (기존 3행일 때 525)
- final gate: **PASS** — 169/169 파싱, changed 635, errors 0, FR/ES 무변경, 제어토큰 보존

| EN | KO | 바이트 | 출처 |
|---|---|---|---|
| I see him!! | 있다!! | 7/12 | 대사집 |
| Who's that! | 누구냐! | 8/12 | 대사집 |
| Speak! | 말해! | 6/7 | 대사집 |
| Answer me! | 대답해! | 8/11 | 신규 |
| Who's there! | 거기 누구냐! | 13/13 | 신규 |
| Who the...!! | 뭐야...!! | 10/13 | 신규 |
| Hyaaaah! | 으아아! | 8/9 | 신규 |
| Hyahya! | 야압! | 6/8 | 신규 |
| Hyeeei! | 에잇! | 6/8 | 신규 |
| Hyuuh! | 흡! | 4/7 | 신규 |
| Gwoah! | 으악! | 6/7 | 신규 |
| Huuuuhya! | 우와아! | 8/10 | 신규 |
| You Were Lucky. We'll Meet Again! | 운이 좋았군. 다음에 또 보자! | 29/35 | 신규 |

`Answer me!`는 대사집에 `대<L229>하라!`가 있지만 **L229가 UNRESOLVED**라 복구로 주장하지
않고 새로 썼다.

## 두 가지 정정 — 다음 세션이 반드시 알아야 할 것

**1. 워크리스트의 `glyph_free_min`은 이 경로에 해당하지 않는다.**
`risk_level=HIGH 1,516`은 per-record 로컬 글리프 슬롯(1,507행이 0)을 기준으로 한
보수적 추정인데, `mgs3d_stage_apply.py`는 **resident global page**
(`translation/40_build_input/global_page_v2/character-map.json`, 1,120자)로 인코딩한다.
따라서 실제 글리프 게이트는 "이 글자가 맵에 있는가"이고, 슬롯 부족은 무관하다.
codec에서도 똑같이 오해했던 지점이다. **HIGH 1,516을 번역 불가로 읽지 말 것.**

실제 예산 모델:
```
encoded = 2바이트/한글(global page) + 1바이트/ASCII + 1(NUL) + 제어바이트
gate    = encoded <= 원본 리소스 슬롯 길이   (풀링 없음, 성장 없음)
```

**2. `mgs3d_stage_apply.py` 결함을 고쳤다.**
짧은 한국어로 생긴 여유 바이트를 `replace_resources(preserve_layout=True)`가
레코드의 **마지막 리소스로 밀어내** 후행 NUL이 쌓였다. 내용은 안 바뀌지만 final gate가
"unexpected/non-EN change"로 정확히 잡아냈다 — 실측 **89개 초과 리소스(스테이지당 1개)**,
gate changed 724 vs apply 635. **각 리소스를 원래 길이로 NUL 패딩**하도록 수정했고,
이후 gate changed 635로 apply와 정확히 일치하며 PASS한다.

## 작업 방식

원본 `scenerio.gcx`와 staging은 건드리지 않았다. 분석 authority
(`stage-worklist-expanded.csv`)도 그대로 두고 **작업 사본**
`stage-translation-working.csv`에만 `current_korean`을 채웠다.
검증 출력은 `builds/v0.92-stage-bark-verify/romfs`(별도 루트).

## 산출물

- 작업 사본: `docs/evidence/2026-08-19-stage-pretranslation-analysis/stage-translation-working.csv`
- 번역 내역+예산: `.../stage-bark-translations.csv`
- dry-run: `.../stage-apply-dryrun-bark.json` · apply: `.../stage-apply-bark.json`
- gate: `.../stage-final-gate-bark.json`
- 번역 도구: `tools/mgs3d_stage_translate_bark.py`

## 남은 작업

**1,558행** (1,571 − 13). 다음 순서는 `TUTORIAL_CONTROL` 142행이다.
`has_special_control` 141행은 제어/아이콘 토큰이 있어 게이트가 토큰 스트림 일치를
요구하므로 주의할 것.

안전 재사용 27개 그룹(70행 → 43유닛 절감)과 문맥검토 2개 그룹, `SAVE` 재사용 후보는
아직 손대지 않았다. the script reference exact 202건은 여전히 authority가 아니다.

master/staging 미적용, commit/push 없음 — 별도 승인 대기.

---

# Session 3 — stage 번역 전량 종결 (2026-08-19)

1,571행 전부가 최종 상태를 가진다. **UNREVIEWED 0**.

| 상태 | 행 |
|---|---:|
| TRANSLATED | 1,257 |
| DONOR_MISCLASSIFIED | 183 |
| KEEP_ENGLISH | 123 |
| HUMAN | 8 |

이번 세션 신규 번역 1,072행 (이전 185행 유지, 재작성 없음).

## 영구 규칙 1 — english 열은 표시용이다

**stage worklist의 `english` 열은 표시용이며, raw의 줄바꿈/control 구조가
평탄화될 수 있으므로 production 저작 authority는 raw resource다.**

MEDICINE에서 실측: `english` 열을 key로 쓰면 32행 중 21행이 매칭 실패했다.
화면 레이아웃이 줄 단위이므로 `\n` 위치까지 원본을 그대로 따라야 한다.
`tools/mgs3d_stage_dump_category.py`가 raw에서 뽑은 정확한 평문을 덤프하고,
모든 batch가 그 문자열을 key로 쓴다.

## 영구 규칙 2 — 언어 분기는 인접 리소스로 판정한다

**scanner의 `language` 열은 짧은 라벨에서 신뢰할 수 없다.** 한 GCX 레코드는
같은 문자열 목록을 언어마다 한 벌씩 담고, 의학·차용어는 영어와 스페인어 철자가
같아서 scanner가 전부 english로 표시한다. hx001a record 0 실측:

```
6160 'Gastrite\n'   프랑스어 블록 (인접: Rhume / Mal au ventre / Coup reçu)
6454 'Proctitis\n'  스페인어 블록 (인접: Herida de bala / Golpe recibido)
6470 'Hypoxia\n'    스페인어 블록
6808 'Gastritis\n'  영어 블록
6794 'Hypoxia\n'    영어 블록
```

여기에 한국어를 쓰면 스페인어 분기가 깨지는데도 final gate의 `fr_es_unchanged`는
통과한다 — 그 검사는 scanner가 이미 donor로 표시한 위치만 보기 때문이다.

판정은 **clean tree에서 인접 리소스를 직접 읽어** 했다. 예:

```
ending:1099 'SRPT A'  인접 R.NI FREL / SRPT B / GRENO A  -> 프랑스어
ending:1513 'SPT C'   인접 SPT B / SPT D / RNA A         -> 스페인어
ending:713  'CRAB'    인접 FISH A / FISH B / TCHNKO      -> 영어
ending:1537 'CANG'    인접 FISH A / FISH B / TCHNKO      -> 스페인어
```

`CRAB`과 `CANG`은 인접 문자열이 같다 — 두 목록이 나란히 있고 `FISH A` 같은
약어는 양쪽에서 철자가 같기 때문이다. 그래서 **자동 판정 도구
(`tools/mgs3d_stage_language_blocks.py`)는 참고용이지 authority가 아니다.**
생존 뷰어 구간은 EN/FR/ES가 리소스 단위로 **교대**해서(hx001a:23 부근)
최근접 신호 방식이 영어 행을 donor로 잘못 표시한다. 실제 분류는 사람이 읽은
인접 근거로만 확정했다.

## 도구

| 도구 | 용도 |
|---|---|
| `mgs3d_stage_dump_category.py` | raw 기준 카테고리 덤프 (저작 입력) |
| `mgs3d_stage_plain_batch.py` | 평문 행 일괄 번역 + glyph/slot 검사 |
| `mgs3d_stage_line_batch.py` | 줄 단위 번역·재조립 (FLORA_FAUNA 전용) |
| `mgs3d_stage_control_batch.py` | control 토큰 보유 행 (범용) |
| `mgs3d_stage_mark_status.py` | KEEP_ENGLISH / DONOR_MISCLASSIFIED / HUMAN 기록 |
| `mgs3d_stage_language_blocks.py` | 언어 블록 참고 지도 (authority 아님) |

## 도구 결함 3건 수정

1. `mgs3d_stage_plain_batch.escape()` — `<`/`>`를 이스케이프하지 않아
   `DATA > TOTAL`에서 `parse_rendered`가 거부했다. 완료된 행에는 영향 없음
   (기존 값은 재이스케이프되지 않는다).
2. `mgs3d_stage_plain_batch.run_batch()` — 처리할 행이 0이면 IndexError.
3. `mgs3d_stage_final_gate.py` — donor 검사가 변경 리소스마다 location 전체를
   재순회했다. 93,784 × 828,396 ≈ 7.8e10 비교로 **끝나지 않는다**.
   donor 위치를 set으로 선계산하도록 고쳤다.

## 신규 glyph 0 유지 과정에서 교체한 표현

`됨`→`손상`, `셜`(스페셜)→`특수`, `굵`(굵기)→`지름`, `퀵`→`빠른`,
`팥`→`붉은콩`, `핍`(핍)→`Peep`. 모두 resident global page 밖 글자였고
pre-flight에서 걸러 반영 전에 교체했다.

## HUMAN 8행

slot이 3~7바이트라 의미를 지키는 한국어가 존재하지 않는 경우만 남겼다.

| category | English | slot 여유 | 이유 |
|---|---|---:|---|
| INJURY | `Cut\n` | 4 B | 열상/상처/베임 모두 4 B, 줄바꿈 자리 없음 |
| INJURY | `CUT\n` | 4 B | 위와 동일 |
| INJURY | `Cut:\n` | 5 B | 콜론까지 넣으면 6 B |
| INJURY | `LEECH` | 5 B | 거머리 6 B, 2음절 대안 없음 |
| ITEM_WEAPON | `SCOPE` | 5 B | 조준경/스코프 6 B |
| SHORT_LABEL | `EAT\n` | 4 B | 먹기 4 B + 줄바꿈 초과 |
| SYSTEM_UI | `NO\n` | 3 B | 1음절 부정어 없음 |
| SYSTEM_UI | `YES\n` | 4 B | 예는 들어가지만 NO와 짝을 맞춰야 함 |

## HUMAN 8행 → 전부 KEEP_ENGLISH (2026-08-19 결정)

fixed slot이 너무 작아 의미를 유지한 한국어가 존재하지 않고, YES/NO는 한쪽만
번역하면 UI 쌍이 깨진다. 억지 축약·의미 손실 번역은 하지 않는다.

최종: TRANSLATED 1,257 / DONOR_MISCLASSIFIED 183 / KEEP_ENGLISH 131 / **HUMAN 0**.

## 영구 규칙 3 — staged scenerio.gcx는 clean tree 파일 + EOF 상주 글리프 페이지다

**RomForge staging의 `stage/*/scenerio.gcx`를 build 출력으로 그냥 덮어쓰면 안 된다.**

2026-08-19 실측(169/169): staged 파일은 clean tree 파일과 **바이트 단위로 동일한
앞부분** 뒤에 66 KB~417 KB가 덧붙은 형태다. 그 영역에 상주 한국어 글리프 페이지가
들어 있고, **모든 파일에서 EOF로부터 정확히 65,275바이트 지점에서 시작한다.**

따라서:

- 그냥 복사하면 글리프 페이지가 사라진다.
- 파일 길이가 바뀌면 페이지 위치가 밀린다.
- `stage_records()`는 staged 파일을 파싱하지 못한다 — 파서가 덧붙은 영역까지
  레코드로 읽어 `bad GCX procedure table`로 실패한다. 레코드 구조 검증은
  **clean 길이만큼 잘라낸 뷰**에 대해 수행해야 한다.

적용은 `tools/mgs3d_stage_stage_to_romforge.py`가 담당한다.
`verified_bytes + staged_tail`로 splice하며, (1) staged 앞부분이 clean과 일치,
(2) verified 길이 == clean 길이, (3) 결과 길이 == staged 길이 세 조건을 모두
만족하지 않으면 거부한다. 덧붙은 tail은 romfs 트리 **바깥**에 먼저 백업한다(R7).

### 관련 도구 수정 — apply가 파일 길이를 보존한다

`replace_resources()`는 재구성한 레코드를 logical size로 자른 뒤 정렬 경계까지
NUL로 다시 채운다. 출고된 stage 파일은 EOF가 정렬돼 있지 않아 마지막 레코드가
**146/169 파일에서 1~15바이트 길어졌다**(추가분은 전부 NUL, 레코드 시작 오프셋은
하나도 이동하지 않음). 파일 자체로는 무해하지만 위의 65,275바이트 앵커를 밀어버린다.
`mgs3d_stage_apply.py`가 NUL 잉여분을 잘라 **원본 길이를 정확히 보존**하도록 고쳤고,
길이가 달라지면 즉시 중단한다.

## staging 적용 완료 (2026-08-19)

대상: `Romforge/output/unpacked/partition0/romfs/stage`

```
stage 파일        169
변경               154
무변경              15   (번역 대상 리소스가 없는 스테이지)
총 바이트     106,437,184   (적용 전과 동일)
글리프 페이지    169/169 파일에서 EOF-65,275 유지
```

staging 레코드 영역 게이트: changed_resources 93,784 / errors 0 / pass true /
fr_es_unchanged / control preserved / unexpected 0 / 169-169 parse.
보고서 `stage-final-gate-staged.json`, 해시 목록 `stage-staging-sha.csv`.

codec.dat·movie.dat·demo.dat·code.bin·exheader.bin 무변경.
CCI 미생성, commit/push 없음.
