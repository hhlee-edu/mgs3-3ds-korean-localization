# movie/demo 오배치 복구 — 적용 직전 검증 (2026-08-19 저녁)

**read-only.** master · `movie.dat` / `demo.dat` / `codec.dat` / `scenerio.gcx` · staging ·
build · CCI · commit · push 전부 무변경. 적용은 승인 후 별도 단계다.

## 1. 결론

| 항목 | 수 |
|---|---:|
| 실제 적용 가능한 REPLACE (`APPLY_NOW`) | **72** |
| 중복 확장 후 총 변경 위치 | **80** (중복 확장으로 늘어난 신규 위치 0) |
| byte PASS / FAIL | **72 / 8** |
| 보류(`OVERFLOW_HOLD`) | **8** |
| KEEP 복귀 확정 | **3** |
| HUMAN 잔류 | **2** |
| NO_SOURCE | **17** |
| 사용자 승인 필요한 오탈자 | **3** |

98행 + extra suspect 4행 = **102행**을 처리했다.
102 = REPLACE 80 + KEEP복귀 3 + HUMAN 2 + NO_SOURCE 17.

## 2. extra suspect 4건 — 전부 MISPLACED 확정

네 건 모두 `verdict=KEEP` 이었으나 대본 대조에서 오배치로 확정됐고, 복구 한국어도 HIGH다.
`media-recovery-verdicts.csv` 에 근거를 담았다.

```
demo r141 e3   No, don't...!                    뭐라고 ?              -> 그만둬!!                     (seq2845)
demo r154 e4   So you see, it is already...     문득 생각난 건데 ...   -> 이제 알겠지. 너무 늦었다는 의미를. (seq2869)
demo r156 e29  EVA?                             음 .                 -> 에바?                        (seq2881)
demo r240 e21  I never thought I'd see you...   공포 ! 공포다 ! ...    -> 처음으로 당신의 약한 소릴 들었어.  (seq3793)
```

네 건 모두 앞뒤 엔트리가 이미 확정된 시퀀스에 물려 있어 슬롯이 양쪽에서 잠긴다.
넷 다 중복 레코드가 없다.

## 3. HUMAN 5건 — 3건 KEEP 복귀 확정, 2건 잔류

**KEEP 복귀 확정 3건.** 셋 다 위치가 맞고, EN↔KO 차이는 일본어 원문과 영어 로컬라이즈의
차이지 오프셋 오류가 아니다. §8 원칙(위치 기준 판정)에 따라 KEEP이다. 패치 대상에서 제외했다.

| 행 | 근거 |
|---|---|
| `demo r29 e13` | e3=763, e8=765, **e13=766**, e18=767, e23=768, e28=769 단조. 현재 한국어가 곧 seq766(볼긴). |
| `demo r61 e30` | e15=1311, e20=1312, e25=1313, **e30=1314**, 1315가 패러메딕 무전 착신. |
| `movie r18 e4` | 델타 +6으로 앵커된 이웃 8행(movie r13~r17, 전부 KEEP)과 동일. **`병기도`의 보조사 `도`가 그 위치를 요구**하고(직전 r17 e13이 "옮겨졌다"를 공급), movie.csv 전체에 이 한국어의 중복이 없어 도너 슬롯 자체가 존재하지 않는다. |

`movie r18 e4` 는 위치는 KEEP이지만 `him` ↔ `병기` 내용 차이가 남아 있다. 후속 품질 QA
항목으로 넘긴다 — 오배치 교정 대상은 아니다.

**HUMAN 잔류 2건.**

| 행 | 쟁점 |
|---|---|
| `demo r146 e2` | **단위 충돌.** 복구 원문은 미터법(`그 거체가 480km 이상으로...?`), 같은 레코드의 KEEP 이웃은 영어 재번역이라 야드파운드법(`2,500마일에서 6,000마일로`). 원문 복원이냐 이웃에 맞춘 `시속 300마일`이냐를 사람이 정해야 한다. |
| `demo r15 e29` | `Hmm...` 은 비언어 감탄사라 전사본이 생략. 장면·화자는 확정. |

## 4. 중복 레코드 확장 — 신규 위치 0

전 master를 대상으로 **영어 본문 + 직전/직후 영어까지 일치**하는 엔트리를 찾아 중복군을
계산했다. 이 국소 문맥 조건이 있어야 "같은 대사"가 아니라 "같은 장면의 같은 슬롯"이 된다.

```
DUP01  demo r100 e0   <->  r106 e4     둘 다 APPLY_NOW
DUP07  demo r100 e30  <->  r106 e34    둘 다 OVERFLOW_HOLD
DUP11  demo r101 e24  <->  r107 e28    둘 다 APPLY_NOW
DUP70  demo r192 e15  <->  r193 e15    둘 다 OVERFLOW_HOLD
```

- 중복군 4개, 위치 8개. **8개 전부 이미 개별 REPLACE 대상이었으므로 확장으로 늘어난 신규
  위치는 0이다.** 리뷰어의 98행이 이미 양쪽을 모두 잡고 있었다.
- 각 쌍의 제안 한국어가 **문자열까지 동일**한 것을 확인했다.
- **어느 중복군도 APPLY/HOLD로 갈라지지 않는다.** 한쪽만 패치되어 같은 장면이 두 번
  다르게 보이는 사고는 발생할 수 없다.
- extra suspect 4건은 중복 없음.

## 5. 바이트 검증 — 실제 인코더 기준

검증은 추정이 아니라 빌더가 쓰는 그 코드로 했다.

```
python tools/mgs3d_movie_tool.py capacity \
  experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/demo.dat \
  <master + 제안 치환> <out.json> \
  --static-allocation translation/40_build_input/global_page_v2/character-map.json
```

- `capacity_bytes = len(subtitle.original) - 4 - len(subtitle.tail)`
- `needed_bytes  = len(encode_translation(wrap_like_source(text, subtitle.raw), mapping))`
- 레코드 단위 **글리프 슬롯 예산** `font_deficit = max(0, needed_glyphs - freed_slots)` 도 함께 본다.

기준 바이너리는 clean-tree romfs다. `originals/3ds_pristine` 는 레코드/엔트리 수가 다른
별개 리전 빌드라 쓰면 안 된다 (`tools/mgs3d_capacity_recheck.py` 상단 주석).

입력은 **master 전체 2,228행에 제안 80건을 치환한 것** — 실제 빌드가 인코딩하는 그 상태다.

| 실행 | 레코드 | 행 |
|---|---|---|
| 베이스라인 (master 원본) | 328 / 328 safe | 2,228 / 2,228 |
| 제안 80건 적용 | 320 / 328 safe | 2,170 / 2,228 |
| **제안 72건 적용 (초과 8행 제외)** | **328 / 328 safe** | **2,228 / 2,228** |

엔트리 단위 대조 결과:

- `needed_bytes` 가 바뀐 엔트리 **76개 — 전부 계획된 80행 안에 있다.**
- 신규 초과 **8건 — 전부 계획된 행이다. 부수 피해 0.**
- 기존 초과가 새로 생기거나 사라진 것 없음.
- 영향받은 51개 레코드 전부 **`font_deficit = 0`** — 글리프 슬롯 부족 없음.
- `missing_characters` 0 — 폰트 매핑 누락 없음.

## 6. 초과 8행 — 자동 축약하지 않고 목록화

`media-recovery-overflow.csv`. **한 글자도 줄이지 않았다.**

| 행 | need | cap | 초과 | 제안 |
|---|---:|---:|---:|---|
| demo r192 e15 | 24 | 16 | **8** | 그렇게 말하는 당신도요. |
| demo r193 e15 | 24 | 16 | **8** | 그렇게 말하는 당신도요. (r192와 중복쌍) |
| demo r148 e31 | 27 | 22 | **5** | 말 그대로 악마의 병기군... |
| demo r100 e30 | 19 | 16 | **3** | 설마, 알아챈 건가? |
| demo r106 e34 | 19 | 16 | **3** | 설마, 알아챈 건가? (r100과 중복쌍) |
| demo r225 e5 | 14 | 12 | **2** | 속도를 더 내! |
| demo r115 e1 | 29 | 28 | **1** | 그런데 한가지 문제가 있어요. |
| demo r226 e16 | 17 | 16 | **1** | 나를 기다린다고? |

서로 다른 대사는 6개, 위치는 8개다. `r115 e1` 은 `그런데` 접속사만 빼면 들어가지만,
축약은 사람이 결정할 일이라 손대지 않았다.

## 7. 사용자 승인 필요 — 오탈자 3건

`media-recovery-typo-approval.csv`.

| ID | 위치 | 원문 | 제안 | 계획 반영 | 바이트 |
|---|---|---|---|---|---|
| T1 | demo r82 e6 | `2족 보행전자?` | `2족 보행전차?` | **반영됨** | 14/16 (여유 +2) |
| T2 | demo r203 e5 | `예, 그게 임무니가요` | `예, 그게 임무니까요.` | **반영됨** | 21/40 (여유 +19) |
| T3 | demo r101 e24 · r107 e28 | `마찬가지로..` | `마찬가지로...` | **미반영(원문 유지)** | 원문 39/40, 정규화 시 40/40 |

- T1: 앞뒤 줄(2167·2169)이 모두 `보행전차`로 적고 영어도 "A bipedal tank?"다.
- T2: `가`→`까` 오타 + 문장부호 누락 보정.
- T3: 두 점 말줄임표를 세 점으로 정규화할지 여부. 승인 시 **중복쌍이라 두 위치를 함께**
  바꿔야 하고, 그 경우 용량 40/40으로 여유가 0이 된다.

## 8. 산출물

| 파일 | 내용 |
|---|---|
| `media-recovery-patch-plan.csv` | **dry-run 패치 계획 80행** — offset, needed/capacity/deficit, byte_status, font_deficit, apply_status, duplicate_group |
| `media-recovery-overflow.csv` | 초과 8행 (축약 없음) |
| `media-recovery-typo-approval.csv` | 승인 대기 오탈자 3건 |
| `media-recovery-verdicts.csv` | extra suspect 4 + HUMAN 5 최종 판정 |
| `dryrun/demo-capacity{,-baseline,-safe}.json` | 인코더 원본 출력 3종 |
| `dryrun/demo-with-recovery{,-safe}.csv` | 검증 입력 (master 사본, master 자체는 무변경) |

## 9. 적용 시 지켜야 할 것

1. **`apply_status=APPLY_NOW` 72행만** 대상. `OVERFLOW_HOLD` 8행은 제외.
2. 중복군 4개는 **쌍 단위로** 적용 (현재 계획은 이미 쌍이 갈라지지 않게 되어 있다).
3. 적용 후 `capacity` 재실행으로 **328/328 · 2,228/2,228** 재확인.
4. 오탈자 T3는 승인 전까지 원문 유지.
5. **말투 FIX 91건은 계속 보류** — 순서는 A 위치 → B 검증 → C 화자 → D register → E fitting.

## 10. 상태 확인

```
입력 media-offset-verdicts-reviewed.csv  sha256 d6787124…09646  (무변경)
master demo.csv   3f7aebb3…5fefa   movie.csv ce71b155…e0f42     (무변경)
clean-tree demo.dat / movie.dat                                  (읽기만)
git HEAD fb9ea8f — 커밋 없음, build/CCI/push 없음
```
