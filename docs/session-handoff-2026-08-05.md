# 세션 인계 (2026-08-05) — PS2대응없음 수기 번역 1차 병합

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
