# REMAP 근거 복원 — 15분 조사 결과 (2026-08-19)

**read-only.** master·`movie.dat`/`demo.dat`·빌드·스테이징·commit 전부 무변경.

## 결론

| 질문 | 답 |
|---|---|
| 한국어 sequence source 복원 | **성공** |
| 복원 행 수 | **2,958 / 3,031 (97.6%)** |
| MISPLACED 95 중 기존 자료로 자동 REMAP 가능 | **0** |
| 이유 | 기존 정렬 산출물 **전부가 오배치의 원천**이다 |
| 그래도 재정렬은 가능한가 | **가능하다** — 입력 두 축이 모두 확보됐다 |

## 1. `korean_sequence`는 전역 인덱스가 아니라 **page 내 인덱스**였다

지난 세션에 `korean_sequence`를 `script_ref_mgs3_script.csv`의 전역 행 번호로 해석해
30/366밖에 안 맞았다. 그게 오해였다. 값의 범위가 **0~266**이고 distinct도 266인데,
the script reference 대본은 4,071행이다. **`page` 열과 짝을 이루는 페이지 내 번호**다.

`en_{demo,movie}_korean_matches.csv`는 `page`를 **버리고** `korean_sequence`만
남겼기 때문에 해석이 불가능했던 것이다. `page`를 보존한 파일이 있다:

`analysis/mgs3_korean_english_alignment.csv` (3,031행)
— 열: `confidence, page, korean_sequence, korean_speaker, korean, english_sequence, english_line, english_speaker, english`

**`(page, korean_sequence)` → `script_ref_mgs3_script.csv`의 `(page, sequence)`:
2,958 hit / 73 miss = 97.6%.** 한국어 대본 순서는 복원됐다.

## 2. 그런데 기존 정렬은 전부 오배치의 원천이다

생성 코드는 `tools/mgs3d_english_korean_match.py`다. `alignment_index()`가 정렬
CSV를 **정규화된 영어 문자열**로 색인하고, DAT의 영어로 조회해 한국어를 가져온다.
즉 `en_*_korean_matches.csv`는 정렬 CSV의 그림자일 뿐이다.

그리고 `analysis/mgs3_korean_english_alignment_dp.csv`(1,389행, `english_sequence`
distinct 1,389 = 1:1 단조)는 **이미 DP 단조 정렬 산출물**이다. 여기서 REMAP이
나올 줄 알았으나:

```
MISPLACED(offset) 95행
  english_sequence 보유            : 95 / 95
  DP 정렬에 한국어 존재            : 95 / 95
  DP 한국어가 master와 다름(=remap): 0
  DP 한국어가 master와 동일        : 95
```

그리고 결정적으로, 그 95행에 대해 **DP 행의 `english`는 실제 DAT 대사와 일치한다
(95/95).** 즉 영어는 제대로 짚었는데 **거기에 엉뚱한 한국어가 붙어 있다.**

**오배치의 뿌리는 `mgs3_korean_english_alignment_dp.csv` 자신이다.**
`exact-unique-korean`은 그 오류를 하류로 복사했을 뿐이다. `confidence`는 대부분
`medium`(1,326/1,389)이라 신뢰도 게이트도 사실상 없다.

**따라서 기존 정렬 산출물은 어느 것도 authority로 쓸 수 없다.**
(사용 금지: `en_*_korean_matches.csv`, `mgs3_korean_english_alignment.csv`,
`mgs3_korean_english_alignment_dp.csv`)

## 3. 그러나 재정렬 입력은 두 축 모두 확보됐다

| 축 | 자료 | 상태 |
|---|---|---|
| 한국어(순서 보존) | `translation/20_matching/script_ref/script_ref_mgs3_script.csv` 4,071행, `(page, sequence, kind, speaker, text)` | **화자까지 있다** |
| 영어(순서 = 게임 순서) | master `current/{movie,demo}.csv`의 `preview`, `(record, entry)` | **DAT와 2,917/2,917 일치 검증됨** |
| 연결 다리 | `english_sequence` → DAT 키 342개(61개는 다중) | 앵커로만 사용 |

`script_ref_mgs3_script.csv`의 `speaker` 열은 덤이 아니다 — movie/demo에 없던
**화자 정보**이므로, 재정렬이 성공하면 codec처럼 확정 화자 기반 말투 검수가 가능해진다.

## 4. 다음 실제 교정 절차 (미실행, 설계만)

1. **새 단조 정렬을 만든다.** `exact-unique-korean` 금지. 축은
   the script reference `(page, sequence)` 오름차순 × DAT `(record, entry)` 오름차순.
   monotone DP: 두 축 모두 전진만 허용, 건너뛰기에 gap 패널티.
2. **점수는 문자열 유사도만 쓰지 않는다.** 필수 신호:
   - 고유명사/숫자 일치(소코로프, 샤고호드, 20분, 500lb …) — 언어 무관 앵커
   - the script reference `speaker` ↔ 대사 흐름의 화자 교대 패턴
   - 길이 비 (한국어/영어)
3. **confidence 기준** — 아래를 만족할 때만 자동 REMAP:
   - DP 경로 위에 있고(단조 위반 0),
   - 앵커(고유명사·숫자) **1개 이상 일치**,
   - 좌우 이웃 2행이 모두 같은 경로 위에 있음(국소 일관성).
   셋 중 하나라도 빠지면 **HUMAN**. 앵커 없는 짧은 대사(`그래 ?`, `음 .`)는
   원리적으로 자동 확정 불가 — 이번 오배치가 정확히 그 집합이다.
4. **검증 게이트**: 새 정렬을 확정된 KEEP 107행에 먼저 돌려 **107/107 재현**되는지
   본다. 재현 못 하면 정렬이 잘못된 것이다. 그다음 MISPLACED 95행에 적용.
5. 그 뒤에야 말투 FIX 91건 적용을 검토한다.

## 5. 만약 재정렬이 실패하면

312행 수동 문맥 검수 경로로 복귀한다. 시작점은
`output/media-register-qa/media-offset-verdicts.csv`의 `verdict=UNREVIEWED` 첫 행
**`demo r5 e5`**.

## 6. 재현 명령

```
# (page, korean_sequence) -> the script reference 해석률
python - <<'EOF'
import csv,io,re,unicodedata
K=re.compile(r"[0-9A-Za-z가-힣]+")
n=lambda s:"".join(K.findall(unicodedata.normalize("NFKC",s or "")))
sh={(r["page"],r["sequence"]):r for r in csv.DictReader(io.open(
    "translation/20_matching/script_ref/script_ref_mgs3_script.csv",encoding="utf-8-sig",newline=""))}
al=list(csv.DictReader(io.open("analysis/mgs3_korean_english_alignment.csv",encoding="utf-8-sig",newline="")))
hit=sum(1 for r in al if (r["page"],r["korean_sequence"]) in sh
        and n(sh[(r["page"],r["korean_sequence"])]["text"])[:16]==n(r["korean"])[:16])
print(hit,"/",len(al))
EOF
```

---

# 부록 — 재정렬 1차 드라이런: **게이트 실패** (같은 날, 10분 작업)

도구: [`tools/mgs3d_media_realign.py`](../../../tools/mgs3d_media_realign.py) (read-only)
산출물: `output/media-register-qa/media-realign-dryrun.csv`

## 결과

| 항목 | 값 |
|---|---:|
| the script reference 한국어 행(한글 포함) | 3,932 |
| master 영어 행 | 2,917 |
| DP MATCHED | 1,444 |
| **NO_WINDOW**(윈도 앵커 실패) | **1,461** |
| UNMATCHED | 12 |
| **게이트: 확정 KEEP 107행 재현** | **0 / 107** |
| MISPLACED 95행 자동 REMAP 후보 | **0** |

**게이트를 통과하지 못했으므로 이 정렬의 어떤 제안도 채택하지 않는다.**
설계대로 게이트가 나쁜 정렬을 막았다 — 이게 게이트를 먼저 만든 이유다.

게이트가 너무 엄격했던 게 아니라 **정렬 자체가 틀렸다.** 유사도 기준을 exact에서
0.5로 낮춰도 **107/107이 전부 `different(<0.5)`** 다:

```
demo r38 e0  Are the Russians going to be helping us?
     현재: 소련 측의 협력은 ?        DP: 나도야 . 1 주일만이군 .
demo r31 e34 Apparently she's Sokolov's woman.
     현재: 소코로프의 여자인 것 같습니다 .  DP: 미 정부는 관여하지 않은 것입니까 ?
```

## 실패 원인 (다음 시도에서 고칠 것)

1. **윈도 앵커를 한국어 문자열 완전일치로 잡은 것이 치명적이었다.** master 한국어는
   이후 정규화·축약을 거쳐 대사집 원문과 더는 같지 않다. 그래서 절반(1,461행)이
   `NO_WINDOW`로 빠졌고, 윈도가 잡힌 레코드도 엉뚱한 구간을 잡았다.
   → **한국어 텍스트로 앵커를 잡지 마라.** `english_sequence`로 잡아야 한다
   (DAT 키에 대응하는 값 342개가 이미 있다).

2. **(record, entry) 전역 순서 = 스토리 순서라는 가정이 검증되지 않았다.**
   demo 레코드 파일 순서가 극 진행 순서라는 근거가 없다. 단조 DP는 두 축이 같은
   순서일 때만 성립하므로, 먼저 **스토리 순서 축**을 확정해야 한다. 재료는 있다 —
   `mgs3_korean_english_alignment.csv`의 `english_sequence`(0~2162)와 `english_line`.

3. **앵커 점수가 약하다.** 고유명사·숫자가 없는 짧은 대사에서 점수가 길이비에만
   의존해 사실상 무작위다. 앵커 없는 구간은 DP가 아니라 **HUMAN으로 넘겨야** 한다.

## 다음 시도의 순서 (수정된 설계)

1. `english_sequence` → DAT `(record, entry)` 대응 342개를 **앵커로만** 써서
   각 레코드의 스토리 위치를 확정하고, 그 순서가 (record, entry) 순서와 일치하는지
   **먼저 검증**한다. 불일치하면 DP 이전에 그것부터 해결.
2. the script reference 윈도는 그 스토리 위치에서 잡는다(한국어 텍스트 매칭 사용 금지).
3. 앵커 1개 이상 있는 구간만 DP를 돌리고, 나머지는 HUMAN.
4. 게이트는 그대로 — **확정 KEEP 107행 107/107 재현**. 통과 못 하면 제안 폐기.

---

# 부록 2 — 재정렬 2차 드라이런: **또 게이트 실패, 그리고 근본 원인 확정**

도구: [`tools/mgs3d_media_realign2.py`](../../../tools/mgs3d_media_realign2.py) (read-only)
산출물: `output/media-register-qa/media-realign2-dryrun.csv`

## 1차의 결함은 고쳤다

- **(record, entry) 순서 = 스토리 순서**임을 먼저 검증했다. 1차에서 58%로 나왔던 것은
  앵커 오염 때문이었다 — `english_sequence` 값 `71`·`339`·`1254`·`1424`가 각각
  20·12·11·5개 행에 중복으로 붙어 있었다. **중복 값과 빈 한국어를 제거하면
  movie 96.8%(30/31), demo 85.4%(210/246) 단조**다. 축 가정은 유효하다.
- 윈도 앵커를 **유니크 위치 + LIS 백본**으로 바꿨다(1차는 오배치 행의 한국어까지
  앵커로 써서 윈도가 오염됐다).

## 그런데 결과

| 항목 | 값 |
|---|---:|
| 유니크 위치 후보 앵커 | 225 |
| LIS 백본 앵커 | 126 |
| DP MATCHED | 2,878 / 2,917 |
| **게이트: 확정 KEEP 107행 재현** | **3 / 107 (2.8%)** |
| MISPLACED 95 자동 REMAP 후보 | 1 |

그리고 백본이 오배치를 걸러내지 못했다:

```
확정 KEEP      107행 중 백본에 오른 것  61
확정 MISPLACED  95행 중 백본에 오른 것  47
```

비율이 사실상 같다. **LIS는 정상과 오배치를 구분하지 못한다.**

## 근본 원인 (측정값)

```
master 한국어 2,917행 중 대사집 대본에서 위치가 유니크하게 잡히는 행:  213 ~ 225 (7.4%)
  (movie/demo 전용 서브셋 2,554행으로 좁혀도 213으로 거의 그대로)
```

**master 한국어의 92.5%는 이후 정규화·축약·재번역을 거쳐 대사집 원문과 더 이상
같지 않다.** 그래서

- 단조 정렬을 고정할 **앵커 밀도가 근본적으로 부족하고**,
- 앵커가 없는 구간에서는 EN↔KO 점수가 고유명사·숫자·길이비뿐이라 **다리를 놓지 못한다**.

이것이 1차·2차가 모두 게이트에서 걸린 이유다. 파라미터 조정으로 넘길 문제가 아니다.

참고로 `script_ref_mgs3_classified.csv`의 `target` 열도 신뢰할 수 없다 —
4,070행 중 `unknown` 2,284, `movie_demo` 1,363, `codec` 423.

## 결정

**재정렬 트랙을 중단한다.** 다시 시도하려면 전제가 하나 필요하다:
문자열 일치가 아니라 **의미 기반 이중언어 정렬기**(문장 임베딩 등). 현재 프로젝트
자산으로는 없다.

**따라서 검증된 경로로 복귀한다 — 312행 수동 문맥 검수.**
확정된 95 MISPLACED / 107 KEEP도 전부 그 방식으로 얻은 것이다.
시작점: `output/media-register-qa/media-offset-verdicts.csv`의
`verdict=UNREVIEWED` 첫 행 **`demo r5 e5`**.

게이트(KEEP 107행 107/107 재현)는 그대로 남긴다 — 앞으로 어떤 자동 정렬을
시도하든 이 문턱을 먼저 넘어야 한다.
