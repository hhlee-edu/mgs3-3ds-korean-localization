# movie/demo 오배치 98행 복구 조사 (2026-08-19)

**read-only.** master · `movie.dat` / `demo.dat` / `codec.dat` / `scenerio.gcx` · staging ·
build · CCI · commit · push 전부 무변경. 입력 `media-offset-verdicts-reviewed.csv` 도 무변경.

## 1. 결과

| MISPLACED | REPLACE | HUMAN | NO_SOURCE |
|---:|---:|---:|---:|
| **98** | **76** | **5** | **17** |

replacement confidence

| HIGH | MEDIUM | LOW | (없음) |
|---:|---:|---:|---:|
| 75 | 2 | 0 | 21 |

speaker confidence — 98행 기준

| HIGH | MEDIUM | LOW | UNKNOWN |
|---:|---:|---:|---:|
| 79 | 15 | 0 | 4 |

speaker confidence — `media-speaker-context.csv` 390행 전체 기준

| HIGH | MEDIUM | LOW | UNKNOWN |
|---:|---:|---:|---:|
| 323 | 52 | 11 | 4 |

## 2. 사용한 authority

**1순위 — the script reference 한국어 원본 스크랩**
`translation/00_source/script_ref/original_scrape/메탈기어솔리드3매뉴얼-한글대사(1..20).txt`

대사집을 서사 순서로 옮긴 20페이지 전사본이다. 파싱 결과 **4,091행,
그중 3,028행이 명시적 화자 라벨**(`스네이크 :`, `소령 :`, `오셀롯 :` …)을 달고 있다.
이 프로젝트에서 이 파일이 화자 authority로 쓰인 것은 이번이 처음이다.

**보조 — master 레코드 문맥**
`translation/10_master/current/{demo,movie}.csv` 의 `preview`(영어) + `korean`.
레코드 단위로 전체 엔트리를 순서대로 읽어 장면을 특정했다.

**사용하지 못한 자료 — GameFAQs**
지시받은 두 문서 모두 **HTTP 403** 이다 (도메인 차원 봇 차단).

```
/ps2/914828-metal-gear-solid-3-snake-eater/faqs/34684  (Full Game Script)  -> 403
/ps2/914828-metal-gear-solid-3-snake-eater/faqs/43456  (CODEC Script)      -> 403
```

따라서 **영어 대본 교차검증은 이번 작업에 존재하지 않는다.** 지시대로 화자를 지어내지
않았고, 근거가 없는 행은 `speaker=UNKNOWN` 으로 남겼다.

## 3. 사용 금지한 자료 (지시 §5 준수)

다음은 **한 번도 참조하지 않았다.**

- `translation/20_matching/en_demo_korean_matches.csv`
- `translation/20_matching/en_movie_korean_matches.csv`
- `mgs3_korean_english_alignment` 계열
- `exact-unique-korean` 매칭 결과
- 과거 `korean_sequence` 자동 매칭 결과

"이 한국어가 대본에 한 번밖에 없다"는 이유만으로 REPLACE 한 행도 없다. 모든 REPLACE는
**같은 레코드의 앞뒤 엔트리가 대사집의 연속 구간에 단조로 맞물리는 것**을 확인한
뒤에만 부여했다. 각 행의 `note` 열에 그 lock을 전부 적어 두었다 (예: `e4=2155, e14=2157,
e19/e24=2158, e29=2159, e34=2160`).

## 4. 자동 정렬은 시도하지 않았다 — 다만 왜 불가능한지는 수치로 확인했다

지시 §6에 따라 LIS · exact match · fuzzy 자동 REMAP · 파라미터만 바꾼 재시도는 하지 않았다.
대신 "기계적 정렬이 왜 3번째도 실패할 수밖에 없는가"를 측정했다.

| 측정 | 결과 |
|---|---|
| master 한국어가 대사집 원문과 그대로 일치하는 비율 | **462행 중 187행 (40%)** |
| MISPLACED가 있는 73개 레코드 중 verbatim 앵커로 위치가 잡히는 레코드 | **73개 중 4개 (5%)** |
| demo 레코드 번호 ↔ the script reference 서사 순서의 단조성 | **36개 중 16개가 역전** |

세 번째 수치가 결정적이다. **`demo.dat` 의 레코드 번호는 이야기 순서가 아니라 에셋
순서**이므로, 레코드 간 보간·전역 단조 정렬은 원리적으로 성립하지 않는다. 자동화 여지는
레코드 *내부*에만 있고, 그 내부조차 master의 60%가 재작성돼 앵커가 부족하다.

실제로 레코드 내부 보간을 구현해 보니 98행 중 59행에 창이 잡혔으나, 그 창들이 짧은 대사
구간(`어...`, `그래.`)으로 붕괴하는 것을 확인하고 **폐기**했다. §6이 경고한 실패 그대로였다.

**그래서 이번 복구는 전량 사람이 장면을 읽어서 했다.** 레코드 문맥 → 내용어로 대사집
검색 → 해당 장면 전체를 읽고 앞뒤 대사로 위치 확정, 의 순서다.

## 5. 대표적인 오배치 유형

**(a) 다른 챕터의 CODEC 대사가 컷신에 들어옴 — 가장 흔함**

현재 한국어가 대사집의 특정 줄로 역추적되는 행이 **52행**이고, 그중 **31행**의 출처가
**무전(CODEC) 구간**이다. 컷신 슬롯에 무전 대사가 들어앉은 것이 단일 최대 유형이다.

```
demo r157 e7   I thought she was your lover.     <- 개가 무서운 건 나도 잘 안다 .   (seq2096, 개 관련 무전)
demo r194 e39  I've been trained to do this...   <- 디 엔드다 . 그러나 갈 수 밖에 없다 .(seq2340, 디 엔드 무전)
demo r240 e6   I'll never make it.               <- 저요 ? 저는 임무를 위해서라면...  (seq2565, 산정상 대화)
```

**(b) 같은 레코드 안에서 한두 칸 밀림**

```
demo r16 e23  Leave him. Shoot the other one!  <- 이런 말도 안 되는 ...  (= e28의 대사)
demo r41 e10  That arm still hurt?             <- 목숨은 건진 듯 하군 .  (= e0의 대사)
demo r26 e4   ...is he crying?                 <- 볼긴대령 .           (= e19의 대사)
```

**(c) 짧은 생성 대사로 채워짐**

`음 .` `그래 .` `몰라 .` `어어 ...` `네 ?` `놈 ?` 같은 1~2어절 문자열. **34행**이 이 유형이다.
`exact-unique-korean` 이 짧은 문자열을 대본 아무 데나 붙인 흔적이다.

98행의 분류 내역: 다른 위치의 대사가 그대로 들어온 것 **52행**(전부 대사집 seq로
역추적됨), 위 (c)의 생성 문자열 **34행**, 나머지 **12행**.

**(d) 동일 장면이 demo.dat에 두 번 저장돼 오배치도 두 벌**

`r100/r106`, `r101/r107`, `r179/r184`, `r180/r185`, `r192/r193`, `r178/r183` —
6쌍이 중복 레코드다. **적용 시 반드시 쌍으로 함께 패치해야 한다.**

## 6. NO_SOURCE 17행이 나온 이유

the script reference 전사본은 **컷신과 무전만** 수록하고 **부수적 NPC 대화는 수록하지 않는다.**

- **감옥 간수("조니") 대화 14행** (r178·r179·r180·r181·r183·r184·r185·r186)
  `조니` `미국인이 모두` `나쁜 녀석은 아니` `냉전을` `장남은` 전부 0건 검색.
- **단일 엔트리 레코드 2행** (r116 `How do I do that?`, r296 `Gotcha this time!`)
  형제 엔트리가 없어 장면을 고정할 방법이 없다.
- **전사본이 생략한 대사 1행** (r41 e10 `That arm still hurt?`)
  장면(더 보스 재회)과 화자는 확정했으나 해당 줄 자체가 전사본에 없다.
  (같은 유형인 r15 e29 `Hmm...` 는 감탄사라 NO_SOURCE가 아니라 HUMAN으로 분류했다 — §7 참조.)

14 + 2 + 1 = 17행.

이 17행은 **원래의 한국어가 어떤 프로젝트 산출물에도 남아 있지 않다.** 영어 대본이나
실기 관찰이 필요하다.

## 7. HUMAN 5행 — 사람이 판단해야 하는 이유

| 행 | 쟁점 |
|---|---|
| `demo r29 e13` | **위치가 맞다.** e3=763, e8=765, **e13=766**, e18=767, e23=768, e28=769로 단조. 현재 한국어 `괜찮나 ?` 가 곧 seq766이다. EN `Are we done here?` 와의 차이는 일본어 원문(`いいのか?`)과 영어 로컬라이즈의 차이지 오배치가 아니다. **KEEP으로 되돌릴 후보.** |
| `demo r61 e30` | **위치가 맞다.** e25=3313, **e30=3314**, 3315가 패러메딕 무전 착신이다. `그럼 나가시죠 ?` 는 무전을 "받다"의 뜻으로 읽으면 `Gonna get that?` 과 맞는다. **KEEP으로 되돌릴 후보** (나가다 해석만 사람이 확인). |
| `movie r18 e4` | **위치가 맞다.** 이 세트의 유일한 movie 행. 델타 +6으로, 앵커된 이웃 8행(movie r13~r17, 전부 KEEP)과 완전히 동일하다. `him` ↔ `병기` 차이는 로컬라이즈 차이거나 같은 브리핑 내 1칸 밀림인데, 영어 대본 없이는 가릴 수 없다. |
| `demo r146 e2` | **단위 충돌.** 복구된 원문은 미터법(`480km`, seq2862도 `4000km→9700km`)인데, 같은 레코드의 KEEP 행들은 영어에서 재번역돼 야드파운드법(`2,500마일에서 6,000마일로`, e37)을 쓴다. 원문을 그대로 넣으면 레코드 내부가 어긋난다. 원문 복원이냐 이웃에 맞춘 `시속 300마일`이냐는 사람이 정해야 한다. |
| `demo r15 e29` | `Hmm...` 은 비언어 감탄사라 전사본이 생략했다. 장면(오셀롯 매복)과 화자(오셀롯)는 확정. 짧은 감탄사를 사람이 채우면 된다. |

## 8. 부산물 — 98행 밖에서 발견한 오배치 의심 4행

레코드를 통째로 읽는 과정에서, **`verdict=KEEP` 인데 명백히 오배치인 행**이 나왔다.
`media-extra-suspects.csv` 에 담았다. **이번 작업에서 verdict를 바꾸지는 않았다.**

```
demo r240 e21  I never thought I'd see you act this weak.
               현재: 공포 ! 공포다 ! 보였다 , 공포가 !     <- 더 피어의 전투 대사
               해당: 처음으로 당신의 약한 소릴 들었어.   (seq3793)

demo r154 e4   So you see, it is already too late.
               현재: 문득 생각난 건데 ...
               해당: 이제 알겠지. 너무 늦었다는 의미를.  (seq2869)

demo r156 e29  EVA?          현재: 음 .        해당: 에바?                (seq2881)
demo r141 e3   No, don't...! 현재: 뭐라고 ?    해당: 그만둬!!             (seq2845)
```

**따라서 MISPLACED 98은 과소집계일 가능성이 있다.** 4행은 73개 레코드만 읽는 과정에서
우연히 눈에 띈 것이고, 전수 조사를 한 것이 아니다.

## 9. 산출물

| 파일 | 내용 |
|---|---|
| `media-misplaced-recovery.csv` | MISPLACED 98행 전체 + 복구안 (19열) |
| `media-speaker-context.csv` | 화자/장면 390행 (오배치 98 + 확정된 KEEP 292) |
| `media-extra-suspects.csv` | 98행 밖 오배치 의심 4행 |

`media-speaker-context.csv` 의 KEEP 292행은 추측이 아니다. 장면을 읽으며 기록한 record
lock을 파싱한 뒤 **① master에 실재하는 엔트리인가 ② 확정된 장면 창 안인가 ③ 엔트리
오름차순 ↔ 시퀀스 비감소인가** 3중 검증을 통과한 것만 남겼다 (검증 탈락 10쌍은 폐기).

재현:

```
python tools/mgs3d_media_misplaced_context.py --nowin --records 77,80,82 # 레코드 문맥
python tools/mgs3d_media_misplaced_context.py --grep "자본주의"           # 장면 검색
python tools/mgs3d_media_misplaced_context.py --seq 2148:2210            # 장면 정독
python tools/mgs3d_media_recovery_build.py <findings.jsonl> <suspects.jsonl>
```

## 10. master 적용 가능 여부

**아직 적용 불가 — 승인 대기.** 기술적으로는 REPLACE 76행 중 HIGH 75행이 적용 후보이나,
적용 전에 다음이 남아 있다.

1. **중복 레코드 6쌍**을 쌍으로 묶어 패치해야 한다 (§5-d).
2. **바이트 예산 검증 미실시.** 복구된 원문이 현재 문자열보다 긴 행이 다수다
   (예: `그래 ?`(5B) → `진정해.`, `음 .` → `너는?`, `아니 ..` → `...그 이상의 존재다.`).
   fitting은 §8 순서상 마지막 단계다.
3. **오탈자 보정 3건**을 리뷰어가 승인해야 한다 — `보행전자`→`보행전차`(r82 e6),
   `임무니가요`→`임무니까요`(r203 e5), `마찬가지로..`의 마침표(r101 e24 / r107 e28).
4. **HUMAN 5행 · NO_SOURCE 17행**은 적용 대상이 아니다.
5. **말투 FIX 91건은 계속 보류.** §8 순서(A 위치 → B 검증 → C 화자 → D register → E fitting)
   를 지켜야 중복 작업이 발생하지 않는다.

## 11. 상태 보존 기록

작업 시작 시점 (2026-08-19 16:58 KST):

```
입력   media-offset-verdicts-reviewed.csv  514행  KEEP 416 / MISPLACED 98
       sha256 d6787124375e676e11c75af5a525518b71b770bff4022946a562b52d46409646

git    release/v0.83 @ fb9ea8f, working tree 24 entries (사전 상태, 이번 작업과 무관)

demo.dat  (3ds_pristine) 3c451c665ea415ce7b260505eee7f1674bf2169949be90caa45f4b58f09dbe39
movie.dat (3ds_pristine) f5c8771f58ec3d2c30a825c3fb622db1fec513a6772aaaa8ef95c097499a06f6
movie.dat (build_input)  8fde5a42eae810bf21a535265911149a3b944ca934725cbe4e21eff192e2409a
master demo.csv          3f7aebb3fac61b39e2a5c0a352788519096993cccc1f55e1b3ffb6279e05fefa
master movie.csv         ce71b155a32eeefda5aefff31865d667e31cb37a302de9c438b52a94ed4e0f42
```
