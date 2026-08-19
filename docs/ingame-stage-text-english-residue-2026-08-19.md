# 인게임 적/NPC 대사 영어 잔존 — 경로 특정 + 전수 스캔 (2026-08-19)

분석·계측만 했다. **번역 텍스트도, 빌드도, 스테이징도 건드리지 않았다.**

도구: [`tools/mgs3d_stage_text_scan.py`](../tools/mgs3d_stage_text_scan.py) (읽기 전용)
산출물: [`docs/evidence/2026-08-19-stage-text-scan/`](evidence/2026-08-19-stage-text-scan/)

## 0. 결론 세 줄

1. **인게임 적/NPC 대사는 codec/movie/demo 어디에도 없다.** `stage/<이름>/scenerio.gcx`
   169개 파일 안에 있고, 이 경로는 **번역 파이프라인이 한 번도 손댄 적이 없다.**
2. **빌드 누락이 아니라 미번역이다.** 스테이징된 169개 `scenerio.gcx`의 문자열 영역은
   영어 원본과 **169/169 바이트 동일**이다(글리프 페이지만 EOF에 덧붙어 있다).
3. **잔존량: 유니크 1,571행 / 149,592 location / 89,070 바이트.** codec의 94.93%
   커버리지와는 완전히 무관한 별도 텍스트 경로다.

## 1. 어디에 있는가

`stage/<이름>/scenerio.gcx`는 **codec.dat 레코드 하나와 완전히 같은 GCX 컨테이너**다 —
암호화된 문자열 영역 + 리소스 테이블 + 레코드 자체의 16×16 2bpp 커스텀 글리프.
그래서 `mgs3d_codec_tool.GcxRecord`가 그대로 파싱한다. 단 하나 걸림돌은 이 파일이
디스크상에서 GCX 정렬 경계까지 패딩돼 있지 않다는 것뿐이고, 복사본을 패딩하면 풀린다.

실제로 들어 있는 것(전부 영어 원문 그대로):

| 종류 | 예시 |
|---|---|
| **적/NPC 대사(경계·발견 반응)** | `Who's that!` · `I see him!!` · `Speak!` · `Answer me!` |
| 무기/아이템/식량/약품 설명 | `The Mosin Nagant. A tranquilizer sniper rifle, and The End's weapon of choice…` |
| 동식물 도감 | `European Rabbit. Originally from the Mediterranean region…` |
| 부상/상태 이름 | `Gunshot Wound` · `Broken Bone` · `Electrical Burn` · `Blow Sustained` |
| 지역명 | `Groznyj Grad Underground Tunnel` · `Bolshaya Past South` |
| RESULTS 화면 · 칭호 | `TOTAL DAMAGE TAKEN` · `You obtained the title "DOBERMAN".` |
| 조작 도움말 | `#{30}##{24}##{23}# : MOVE CURSOR …` |
| 난이도/옵션 설명 | `EASY : …` · `Adjust screen brightness.` |

`Who's that!` 하나만 해도 **52개 스테이지에 208 location** 있다.

### 왜 지금까지 안 보였나

`originals/3ds_pristine/`은 **일본판**이다(`codec.dat` 37 MB). 일본판 stage 텍스트는
전부 일본어 커스텀 글리프라서 영어를 찾을 수 없다. 영어 원본은
`experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/` (`codec.dat` 67 MB)다.
**stage 텍스트를 볼 때는 반드시 clean-tree를 봐야 한다** — 기존 메모의
"reference-binary gotcha"가 여기에도 그대로 적용된다.

## 2. 언어 분기 구조 (측정 결과, 가정 아님)

- stage 파일에는 **영어·프랑스어·스페인어 3개 분기만** 있다. **독일어·이탈리아어는 없다**
  (movie.dat/demo.dat에는 5개 다 있다 — 여기만 3개다).
- 3개 분기는 **길이가 같은 연속 블록 3개**로 배치되고, 블록 길이가 **가변**(1, 2, 4, 8…)이며
  **언어 순서도 고정이 아니다**(`FR,ES,EN`인 구간과 `EN,FR,ES`인 구간이 둘 다 있다).
  단순 period-3 가정은 코퍼스의 81.3%밖에 설명하지 못한다.

그래서 분류는 **서로 독립인 두 신호를 교차검증**한다:

| 신호 | 근거 |
|---|---|
| 어휘 | `0x1F` 확장문자 이스케이프는 FR/ES 분기에만 나온다 → 이 코퍼스 자체에서 donor 어휘 3,031개를 뽑는다. 영어 어휘 1,226개는 `movie.csv`/`demo.csv` preview에서 뽑는다 (codec master의 `english` 열은 **쓰지 않았다** — donor 오염이 이미 확인된 열이다). |
| 구조 | 위의 EN/FR/ES 블록 삼중쌍. 블록 길이는 최고점수 탐색으로 정한다(짧은 오매칭 하나가 뒤를 전부 어긋나게 하는 것을 막기 위해서다). |

**두 신호의 불일치는 0건이다** (`conflicts: 0`). 구조가 판정한 307,662 location과
어휘가 판정한 144,187 location이 겹치는 구간에서 한 건도 어긋나지 않았다.

독립 검산: 구조로만 푼 구간에서 donor:english location 비가 **205,108 : 102,554 =
정확히 2.000**이다(FR+ES 대 EN). 전체에서도 순수 donor 297,131 ÷ 2 = 148,566 대
영어권 149,592로 **0.7% 이내**에서 맞는다.

## 3. 잔존량

169개 파일, 문자열 리소스 **487,202 location / 유니크 5,067행**.

| 구분 | 유니크 | location | 유니크 바이트 |
|---|---:|---:|---:|
| **영어 분기** | 1,388 | 119,448 | 86,284 |
| **3분기 공용**(고유명사·무기 코드 등) | 119 | 23,815 | 1,408 |
| 판정 근거 없음(내용상 영어) | 64 | 6,329 | 1,378 |
| **한글화 대상 합계** | **1,571** | **149,592** | **89,070** |
| FR/ES donor | 3,308 | 297,131 | — |
| 비서양(식별자·바이너리) | 188 | 27,493 | — |

한글화 대상 1,571행의 내용 구성: **prose 1,065 / label 364 / ui_help 142.**

"3분기 공용"은 `Rassvet`, `PATRIOT`, `AK-47`처럼 세 분기가 같은 바이트를 쓰는 문자열이다.
언어 설정과 무관하게 화면에 뜨므로 donor로도 영어로도 접을 수 없어 따로 뺐다.

워크리스트: [`stage-text-english-worklist.csv`](evidence/2026-08-19-stage-text-scan/stage-text-english-worklist.csv)
— location 내림차순, 빈 `korean` 열 포함.

## 4. 빌드 누락인가 미번역인가 — 미번역이다

스테이징 트리(`Romforge\output\unpacked\partition0\romfs`)의 `scenerio.gcx` 169개를
영어 원본과 대조했다:

- **문자열 영역 SHA-256 169/169 동일.** 텍스트는 단 한 바이트도 바뀐 적이 없다.
- 파일 크기 차이는 전부 EOF 뒤에 덧붙은 한글 글리프 페이지다(66,360~417,491 B).

즉 이 경로는 **빌드에서 빠진 게 아니라 애초에 번역 대상으로 잡힌 적이 없다.**

## 5. 번역 정본은 있는가 — 부분적으로

### 5.1 프로젝트 내부 master: 없다

1,571행을 codec/movie/demo master의 한국어와 정규화 매칭했다. **일치 8건, 전부 오탐**이다
(`NO`↔`아니`, `SAVE`↔`저장` 같은 codec 대사와의 우연한 문자열 일치). **실질 0건.**

### 5.2 대사집: 있다. 단 해독이 4%밖에 안 돼 있다

PS2 STAGE.DAT은 이미 추출돼 있고(`originals/ps2_stages/`, 156개 스테이지) 카탈로그도
이미 만들어져 있다:

| 파일 | 내용 |
|---|---|
| `analysis/script_ref/stage_text_catalog.csv` | 90,216행 / 106 스테이지 / 유니크 디코드 3,101 |
| `analysis/script_ref/stage_text_unique.csv` | 1,548행 (stage-specific 유니크) |
| `analysis/script_ref/stage_text_unique_ocr80.csv` | 같은 1,548행, 로컬 글리프 OCR 적용본 |

**PS2 유니크 1,548 대 3DS 영어권 유니크 1,571** — 같은 코퍼스로 보기에 충분히 가깝다.

문제는 해독률이다. OCR 적용본에서도 **1,548행 중 완전 해독은 58행뿐**이고 미해결 토큰이
**8,148개** 남아 있다(`<L0xx>` 로컬 커스텀 글리프, `<S81xx>` 미상 static). codec 때
쓴 토큰맵+로컬 글리프 OCR 파이프라인(`mgs3_script_ref_token_map.py`,
`mgs3_ps2_local_glyph_export.py`, `mgs3_ps2_local_glyph_ocr.mjs`)이 그대로 있으니
방법은 있지만, **stage용으로는 끝까지 돌린 적이 없다.**

그리고 PS2↔3DS stage 문자열 매칭은 **한 번도 시도된 적이 없다.**

## 6. 용량 전망 (참고)

codec과 같은 donor reclaim이 그대로 적용된다. 실측 바이트:

- 영어권 문자열 총 6,186,515 B, FR/ES donor 총 15,752,760 B → **donor가 영어의 2.55배**
- **169개 스테이지 전부 donor 마진이 양수**다. 가장 빡빡한 `s063a_0`/`init` 계열도
  donor 4,663 B 대 영어 1,478 B로 **+3,185 B** 여유.

한글 글리프 페이지는 **이미 169/169 스테이지에 붙어 있다**. 즉 글리프 쪽 준비는 끝났고,
남은 것은 번역 정본과 문자열 치환 경로다.

## 7. 다음 단계 (제안, 미실행)

1. PS2 stage 로컬 글리프 OCR을 끝까지 돌려 `stage_text_unique`의 해독률을 올린다.
   (codec 파이프라인 재사용. 58/1,548 → 목표는 codec 수준.)
2. 해독된 대사집 ↔ 3DS 영어 1,571행 매칭. codec/movie/demo에서 쓴 3-way 정렬을
   그대로 쓴다.
3. 매칭 실패분만 신규 번역 큐로. 우선순위는 location 수(= 화면 노출 빈도).
4. `scenerio.gcx` 문자열 치환 + 용량 게이트. **codec의 교훈 두 개를 처음부터 적용한다:**
   canonical 하나가 아니라 **모든 location을 검증**하고, 커버리지는 master 행 수가 아니라
   **바이너리 location 수**로 센다.

## 8. 재현

```
python tools/mgs3d_stage_text_scan.py --out docs/evidence/2026-08-19-stage-text-scan
```

기본 `--romfs`는 영어 clean-tree다. 게임 트리에 쓰지 않는다.
