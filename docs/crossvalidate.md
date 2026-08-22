# crossvalidate — 4자료 교차 검증

`python tools/mgs3d_crossvalidate.py --containers codec,movie,demo`

플레이 중 발견한 결함(음성은 `What was that?`인데 자막은 엉뚱한 문장)을
**한 건씩 눈으로 찾는 대신 전량에서 기계적으로 뽑아내려고** 만든 도구다.

## 왜 문자열 비교로는 안 되나

`demo 9/15`의 한국어 `칭찬하고`는 그 자체로는 멀쩡한 한국어다. 영어
`What is it?`와 비교해도 문자열 유사도는 의미가 없다(언어가 다르다). 이 줄이
결함인 이유는 **다른 장면의 번역이 들어왔다**는 것이고, 그건 *순서*를 봐야 안다.

우리 번역과 shinsnote는 둘 다 서사 순서를 갖는다. 완전일치·퍼지일치를 앵커로
두 순서를 정렬하면, 이웃과 동떨어진 장면에 붙는 줄이 드러난다.

## 검출기 9종

앞의 넷은 shinsnote 정렬에 기대고, 뒤의 셋은 정렬과 무관하다. **정렬만으로는
부족하다** — 사용자가 실플레이로 찾은 5건 중 D1~D4가 잡은 것은 1건뿐이었다.

| | 근거 | 정렬 의존 |
|---|---|---|
| `D1-order` | 정렬 백본(LIS) 위반 + 블록 합의 구간 이탈 | O |
| `D2-register` | shinsnote 화자 기준 어투 일관성 | O (앵커 부족으로 거의 미작동) |
| `D3-drift` | 제자리 유사도는 낮은데 먼 장면 줄과 강하게 일치 | O |
| `D4-fragment` | 영어는 완결문인데 한국어가 연결어미로 끊김 | X |
| `D5-terse` | 예산이 남는데 영어 대비 한국어가 과도하게 짧음 = 정보 손실 | X |
| `D6-dup` | 같은 한국어가 **컨테이너를 넘어** 다른 영어에도 붙음 | X |
| `D7-pronoun` | we/our/us ↔ 나/내, I/my/me ↔ 우리 인칭·수 불일치 | X |
| `D8-speechact` | 앞줄이 질문인데 긍정 답변(`Right.`)이 수긍(`알았어`)으로 번역 | X |
| `D9-enpos` | 영문 대사집 위치와 한국어 위치가 어긋남 | 자료 (3) 필요 |

`D2`는 자료 (3)이 들어오기 전까지 앵커 부족으로 사실상 못 돌았다. 지금은 영문
대사집이 화자를 직접 주므로 작동한다.

**주의: `-니까`를 존댓말로 오인하지 말 것.** `확실합니까?`는 존댓말이고
`필요하니까.`는 반말 연결어미다. 둘 다 `니까`로 끝나므로 앞 음절의 **종성이 ㅂ**인지로
갈라야 한다. 이 구분을 넣기 전에는 정상 반말이 대량 오탐됐다.

**D6는 반드시 컨테이너를 넘어 봐야 한다.** `demo 24/14`("What are you doing
here?" → 「북동쪽이라... 알았다.」)의 한국어는 `codec 38:15`에서 왔다. demo 안에서만
세면 그 한국어는 하나뿐이라 원리적으로 안 잡힌다.

### 실측 재현율 (사용자 실플레이 발견 5건)

| 결함 | 검출 |
|---|---|
| `demo 9/15` 「칭찬하고」 | ✅ D4 |
| `demo 22/39` "take me to America" 과축약 | ✅ D5 |
| `demo 24/14` The Boss 다리 오배치 | ✅ D6 |
| `demo 29/23` "Shagohod is ours" → 「내 거」 | ✅ D7 |
| `demo 26/4` "Is he crying?" 어투 | ❌ — 영문 대사집 필요 |

**4/5.** D5~D7 추가 전에는 1/5였다.

D1이 확정한 것들:

```
demo  119/20   EN "Comrade or not, he is of no use to us now."  KO "그런 명령은 없었는데, 왜 손잡이를?"
demo  119/25   EN "I don't approve of your methods!"            KO "그 자세. 바로 그 자세다."
demo  260/5    EN "I've picked up a few new moves!!"            KO "대령님. 무언가 불었습니가?"
movie  29/14   EN "Yes, I hear you, Mr. Chairman."              KO "이 날이 오길 기다렸습니다."
codec 1037/48  EN "...would you excuse me for a moment?"        KO "스네이크, 이젠 볼긴이 타고 있는 샤고호드만..."
codec 1595/10  EN "EVA, about the contents of the backpack..."  KO "녀석은 당신을 의심하고 있었다."
codec 1597/17  EN "What about the instant noodles?"             KO "문제라도 있나?"
```

`260/5`의 `불었습니가`는 shinsnote의 **오타까지 그대로**다. 엉뚱한 위치에서
통째로 복사됐다는 직접 증거다.

D5가 드러낸 것 중 가장 큰 덩어리는 **소코로프 구출 장면(demo record 22~23)이
통째로 과축약**되어 있다는 것이다. 예산이 넉넉한데 `fear`, `US family` 같은 영어
조각으로 때워져 있었다 — 22/14는 45B 예산에 21B만 썼다.

## 지금의 한계 — 왜 정밀도가 27%인가

오탐 16건은 전부 **영어와 한국어가 서로 맞는 정상 줄**이다. 예:

```
demo 290/30  EN "This is one for the history books; the world's first HALO jump."
             KO "이것이 기록으로 남을 세계 최초의 HALO 강하가 될 거다..."   <- 정상
```

record 288~291이 HALO 강하 오프닝인데 record 번호는 뒤쪽이다. **record 순서가
서사 순서와 다르다.** 블록 합의로 상당수 억제했지만, 블록 안에 앵커가 2개 미만이면
합의가 성립하지 않아 그대로 통과한다.

진짜와 가짜를 가르는 것은 결국 **영어와 한국어가 같은 뜻인가** 하나뿐이다.
그건 지금 자료로는 기계적으로 판정할 수 없다.

## (3) 영문 대사집 — 확보됨 (2026-08-22)

저장소에 이미 있었다. `analysis/gamefaqs_mgs3_english.csv` — GameFAQs FAQ 34684
(MHamlin, *Game Script* v1.60)의 파싱본, **2,164행에 화자 37종**. 처음 조사할 때
`script_ref/`만 뒤지고 `analysis/`를 안 봐서 "없음"으로 잘못 적었다.

```
변환:  translation/20_matching/en_script/en_script_mgs3_gamefaqs.json
사용:  --en-script translation/20_matching/en_script/en_script_mgs3_gamefaqs.json
원문:  analysis/gamefaqs_mgs3_script_34684.txt
      translation/00_source/english_script/mgs3-game-script.txt   (같은 문서)
```

| 자료 | 상태 |
|---|---|
| (1) 3DS 영문 대사 | 있음 |
| (2) 현재 번역 | 있음 |
| (3) 영문 대사집 (화자 구분) | **있음** — 2,164행 / 화자 37종 |
| (4) shinsnote 한국어 | 있음 — 4,070세그 / 화자 37종 |

### 붙여 본 결과

```
codec  영문 매칭 428행 | 영·한 동시 앵커 35쌍
demo   영문 매칭 304행 | 영·한 동시 앵커 75쌍
movie  영문 매칭  46행 | 영·한 동시 앵커 16쌍
```

기대만큼 조밀하지는 않다. 대본이 2,164행인데 codec 정본은 9,057행이라 **선택 무전
상당수가 대본에 아예 없다.** 그래도 한국어 앵커 63개 대비 **영문 매칭 428행**이라
정렬 근거가 7배 늘었다.

### 이것이 연 것 둘

**D2가 살아났다.** 게임 데이터에는 화자 필드가 없고, shinsnote로 추정하려면 한국어가
먼저 정렬돼야 하는데 그게 순환이었다. 영어는 바로 붙는다. 이제 화자가 확정된 행에
대해 어투 일관성을 볼 수 있다 — `Snake의 어투는 반말 79/81인데 이 줄만 존댓말`.

**D9가 생겼다.** 영·한 동시 앵커로 두 대본의 색인을 대응시키면, 한 줄의 *영어가
대본 어디에 있는지*와 *그 한국어가 shinsnote 어디에 붙는지*를 따로 구해 대조할 수
있다. 한국어 정렬만 보는 D1과 달리 **두 자료가 서로를 반증**한다.

```
demo 122/2  EN "You think it was the American?"   KO "과연... 그것이 소문의?"
  영문 대사집: [Ocelot] 대본 832번째  ->  대응 shinsnote ~1737
  실제 한국어는 shinsnote 1010에 붙음 (거리 727)          <- 확정 오매핑
```

## 아직 남은 한계

흔한 대사는 대본에 여러 번 나온다. `I jumped into the river.` 같은 줄은 번역이
맞는데도 다른 출현에 붙어 D9에 걸린다. 예측 위치의 shinsnote 문장과도 닮으면
억제하도록 했지만 완전하지는 않다.

그리고 **대본에 없는 선택 무전은 어떤 검출기로도 화자를 못 준다.** codec 9,057행 중
영문 매칭이 428행뿐인 것이 그 한계다.

## vox는 이 도구의 대상이 아니다

shinsnote 일치 135건을 열어보면 중앙값 2글자, 129건이 5자 이하 —
`Ah.`→`아.`, `Hmm.`→`음...` 같은 우연이다. shinsnote는 컷신·무전 대본이지
게임 중 병사 대사집이 아니다. vox 2,691행은 별도 경로가 필요하다.

## 출력

`{codec,movie,demo}-findings.csv` — 열: `detector, loc, score, english, korean,
shin_speaker, shin_text, shin_pos, expected_pos, note`

**판정이 아니라 후보다.** 사람이 읽고 결정한다. 정본(`current/*.csv`)은
이 도구가 건드리지 않는다.
