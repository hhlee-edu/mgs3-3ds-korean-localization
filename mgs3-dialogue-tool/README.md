# MGS3 대사 매칭 도구

깨진 일본어 대사 데이터를 기준으로 영문 스크립트와 한글 대사 참고자료를
빠르게 검색하고, 번역 결과를 CSV에 누적하기 위한 보조 도구입니다.

## 권장 작업 흐름

1. 영문 스크립트와 한글 블로그 1~20편을 한 번만 받아 검색 DB를 만듭니다.
2. 일본어 덤프를 검토 CSV로 변환합니다. `<G001>`, `<C123>`, `<END>` 등의
   제어코드는 `clean_japanese` 열에서 제거됩니다. 원문은 별도 열에 보존됩니다.
3. 살아 있는 일본어 단어에서 핵심어를 추정해 영문·한글 DB를 검색합니다.
4. 앞뒤 문맥을 비교해 `english_match`, `korean_reference`,
   `korean_translation`을 채웁니다.
5. `confidence`에는 `high`, `medium`, `low`, `status`에는 `approved` 또는
   `review`를 기록합니다.

단순 문자열 유사도로 일본어·영어·한국어를 자동 연결하지 않는 이유는 깨진
글자가 많고 언어가 서로 달라 오답을 자신 있게 확정할 위험이 크기 때문입니다.
DB 검색과 후보 문맥 수집은 도구가 맡고, 최종 의미 판단은 Codex 또는 사람이
담당하는 구조입니다.

## 사용법

Python 3.10 이상만 필요하며 별도 패키지는 사용하지 않습니다.

GameFAQs는 자동 다운로드를 차단할 수 있습니다. 해당 FAQ를 브라우저에서
`gamefaqs_mgs3.html` 또는 TXT로 저장한 뒤 다음처럼 실행하는 방식이 가장
안정적입니다.

```bash
cd mgs3-dialogue-tool
python mgs3_matcher.py build --english-file gamefaqs_mgs3.html
python mgs3_matcher.py stats
```

이미 파싱해 둔 한글 대사 JSON이 있으면 인터넷 접속 없이 함께 구축할 수 있습니다.

```bash
python mgs3_matcher.py build --english-file gamefaqs_mgs3.html --korean-json script_ref_mgs3_script.json
```

한글 자료만 먼저 구축하려면 다음 명령을 사용합니다.

```bash
python mgs3_matcher.py build --skip-english
```

일본어 덤프가 `japanese.txt`에 있다면:

```bash
python mgs3_matcher.py batch japanese.txt --output translation_review.csv
```

`mgs3d_game_candidates.json`을 직접 읽고 특정 GCX/resource 범위만 뽑을 수도 있습니다.

```bash
python mgs3_matcher.py batch-game-json mgs3d_game_candidates.json --gcx 243 --start 300 --end 440 --output gcx243_review.csv
```

검증된 공통 앵커 자료를 일괄 병합할 때는 다음 명령을 사용합니다. 정확한 한글 문장까지
분리된 행만 번역 후보가 되고, 근거가 충돌하거나 문장을 분리할 수 없는 행은 `blocked`로
남습니다. 이 명령은 자동 승인하지 않습니다.

```bash
python mgs3_matcher.py apply-anchor-evidence gcx243_review.csv codec_context_review.csv --output gcx243_mapped.csv
```

영문 스크립트 검색:

```bash
python mgs3_matcher.py search backpack --source english --context 8
```

한글 1편에서 백팩 검색:

```bash
python mgs3_matcher.py search 백팩 --source korean --part 1 --context 8
```

현재 예시처럼 `380~396`을 작업할 때는 `grip`, `hanging`, `backpack`,
`FPS`를 영문에서 검색하고 `매달`, `백팩`, `조준`을 한글에서 검색합니다.
자료에 없는 문장은 일본어 복원 번역으로 처리하고 `notes`에
`영문 스크립트 미수록`처럼 근거를 남깁니다.

## 일본어 입력 형식

```text
380: ただし...<END>
381: スタミナが...<END>
```

한 레코드가 여러 줄이어도 다음 `숫자:`가 나오기 전까지 하나로 합칩니다.

## 자료 출처

- 영문: GameFAQs, *Metal Gear Solid 3: Snake Eater – Game Script* by CHamlin
- 한글 참고: 대사집의 *메탈기어솔리드3매뉴얼-한글대사* 1~20편

각 자료는 번역 후보 확인용으로만 사용하고, 결과 CSV에는 필요한 대응 문장과
출처 메모만 남기는 것을 권장합니다.
