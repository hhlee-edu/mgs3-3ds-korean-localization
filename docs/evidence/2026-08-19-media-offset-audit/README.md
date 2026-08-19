# movie/demo `translation_source = offset` 전수 감사 — 30분 체크포인트 (2026-08-19)

**read-only.** master·`movie.dat`/`demo.dat`·빌드·스테이징·commit 전부 무변경.

## 결론 먼저

| | 행수 |
|---|---:|
| offset 총계 | **514** |
| **KEEP**(문맥에서 읽고 대응 확인) | **107** |
| **MISPLACED**(다른 대사의 한국어 확인) | **95** |
| **REMAP 성공** | **0** |
| **UNREVIEWED** | **312** |

`output/media-register-qa/media-offset-verdicts.csv` 가 확정 시트다.

## 1. 이번 세션의 핵심 발견 — 근거인 줄 알았던 파일이 원인이었다

`translation/20_matching/en_demo_korean_matches.csv`(457행)·`en_movie_korean_matches.csv`(51행)는
**영어 DAT 키(record, entry)** 라서 독립 검증용으로 쓰려 했다. 아니었다.

**손으로 확인한 오배치 95행 전부가 이 파일에 같은 (record, entry)·같은 한국어로 들어
있다(95/95, 유사도 1.00).** 즉 이 표는 master offset 행의 **출처**이고, master와
대조하면 언제나 일치한다 — 순환 논증이다. 첫 자동 감사가 KEEP 215를 낸 이유가 이것이다.

## 2. 오배치의 실제 메커니즘

그 표에는 정렬기가 쓴 두 인덱스 `english_sequence` / `korean_sequence` 가 남아 있다.
정상 구간은 델타가 일정하다:

```
en_seq  ko_seq   delta
    60      65      +5   The Fulton Surface-To-Air Recovery System...
    61      66      +5   Take it easy. It has been combat-proven.
    62      67      +5   Do you think Sokolov's up to it?
    66      71      +5   Sounds like she could hold her own...
```

오배치 구간은 델타가 튄다:

```
   265     144           Leave him. Shoot the other one!   -> 이런 말도 안 되는 ...
   476       2           That arm still hurt?              -> 목숨은 건진 듯 하군 .
   501      50           Cut the engine. They'll hear us.  -> ... 그럼 어떻게 된 건가 ?
   506     103           Trapped?                          -> 몰라 .
```

`match_status` 가 답이다. **`exact-unique-korean` = 한국어 문자열이 유일한지로 매칭**
했다는 뜻이고, 시퀀스를 전혀 보지 않는다. `그래 ?` / `몰라 .` / `음 .` 처럼 짧은 대사에서
대본 아무 데나 붙는다. demo 457행 중 333행이 이 방식이다.

**따라서 "한 칸씩 밀린 연속 drift block"이 아니다.** 델타가 국소적으로 일정한 구간이
없으므로 block으로 묶을 수 없다 — 짧은 대사마다 독립적으로 튄 **산발성 오배치**다.
`media-offset-alignment.csv` 의 LIS backbone 분석에서도 연속 block은 **0개** 나왔다.

## 3. REMAP이 왜 0인가

올바른 한국어를 되찾으려면 `korean_sequence` 인덱스를 실제 대사로 풀어야 한다.
그 인덱스가 가리키는 리스트가 **보존돼 있지 않다**:

| 후보 | 해석 성공 |
|---|---|
| `shinsnote/shinsnote_mgs3_script.csv` (4,071행) | 30 / 366 |
| `shinsnote/shinsnote_mgs3_classified.csv` (4,070행) | 30 / 366 |
| `shinsnote/shinsnote_mgs3_movie_demo_only.json` (2,625 segment) | 0 / 366 |

비교표(`*_korean_comparison_review.csv`)에서 한국어를 역검색하는 경로도 시도했다
(`media-offset-audit.csv`). 한국어가 그 표에 남아 있는 행이 적어 **HUMAN 274**로 끝났고,
자동 remap은 1행뿐이었다.

**결론: 기존 산출물만으로는 remap이 불가능하다.** 올바른 한국어는 Shinsnote 대본을
영어 DAT 순서에 맞춰 **다시 정렬**해야 나온다. 그때는 `exact-unique-korean` 이 아니라
**단조 시퀀스 정렬**을 써야 한다 — 같은 실패를 반복하지 않으려면 이것이 조건이다.

## 4. 스크리닝 신호 — 있지만 약하다

`media-offset-alignment.csv` 는 `en_seq` 순으로 `ko_seq` 의 **최장 증가 부분수열(LIS)** 을
뽑아 backbone에서 벗어난 행을 표시한다.

- 손으로 읽은 오배치 106행 중 **100행을 잡는다(recall 94%)**
- 그러나 508행 중 **419행을 flag한다** — 정밀도가 낮다
- 미검토 중 flag된 상위 22행을 표본 확인했더니 **거의 전부 정상**이었다
  (`You OK? → 괜찮아?`, `Spetsnaz? → 스페츠나츠?`, `Remember the Alamo → 알라모를 잊지 마라`)

**그러므로 이 신호로 UNREVIEWED 312행을 자동 판정하면 안 된다.** 읽는 순서 힌트일 뿐이다.

## 5. 더 쓸모 있는 triage 단서

확정된 오배치 95행은 **거의 전부 문장부호 앞 공백**(`몰라 .`)을 달고 있다 — Shinsnote 표의
표기 습관이 그대로 남은 행이다. 반대로 UNREVIEWED 312행은 그 공백이 **없는** 행들이고,
표본에서 정상률이 높았다. 즉 **어느 시점에 정규화를 거친 행은 재검토·재작성됐을 가능성이
있다.** 다음 세션의 가설로 삼고 검증할 것.

## 6. 대표 오배치 사례

```
demo r117 e10  I've got to hurry back and play my...other part.  ->  하늘을 나는 병기죠 .
demo r157 e7   I thought she was your lover.                     ->  개가 무서운 건 나도 잘 안다 .
demo r149 e20  And deploy them all over the Soviet Union?         ->  사람은 변한다 .
demo r82 e1    a bipedal tank...                                  ->  ... 향수 ?
demo r85 e15   Nice shoes...                                      ->  CQC 다 .
demo r41 e10   That arm still hurt?                               ->  목숨은 건진 듯 하군 .
```

영어 쪽은 멀쩡하다 — master 2,917행의 `preview` 를 clean-tree DAT의 해당 (record, entry)
엔트리와 대조해 **2,917/2,917 일치**. 한국어가 남의 자리에 앉아 있는 것이 맞다.

## 7. 다음 세션 시작 위치

1. **UNREVIEWED 312행**을 레코드 문맥으로 읽는다. 시작점: `media-offset-verdicts.csv`
   에서 `verdict=UNREVIEWED`, `media/record/entry` 오름차순 → **첫 행 `demo r5 e5`**.
   `screen_off_backbone=True` 130행을 먼저 보되 **정밀도가 낮다는 것을 전제로** 읽을 것.
2. §5의 가설(정규화된 행 = 재작성된 행) 검증.
3. remap은 Shinsnote 대본 **재정렬**이 선행돼야 한다. 단조 시퀀스 정렬 필수.
4. 말투 FIX 91건은 **여전히 보류** — 오배치 정리 전에는 적용하지 않는다.

## 8. 산출물 / 재현

```
python tools/mgs3d_media_offset_audit.py   --outdir output/media-register-qa   # 텍스트 역추적
python tools/mgs3d_media_offset_align.py   --outdir output/media-register-qa   # LIS 스크리닝
python tools/mgs3d_media_offset_verdict.py --outdir output/media-register-qa   # 통합 판정
```

| 파일 | 내용 |
|---|---|
| `output/media-register-qa/media-offset-verdicts.csv` | **확정 시트** 514행 |
| `output/media-register-qa/media-offset-alignment.csv` | LIS backbone, 시퀀스 델타 |
| `output/media-register-qa/media-offset-audit.csv` | 비교표 역추적 결과 |
| `docs/evidence/2026-08-19-media-qa/verdicts.py` | 사람이 읽고 내린 판정(행 단위) |
