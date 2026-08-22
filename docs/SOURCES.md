# 참조 자료 색인

**자료가 없다고 결론내기 전에 이 문서를 볼 것.** 2026-08-22에 "영문 대사집이
없다"고 잘못 판단해 외부 수집을 시도한 일이 있었다. 실제로는 `analysis/`에 이미
있었고, `script_ref/`만 뒤진 탓이었다. 이 색인은 그 재발을 막으려고 만들었다.

## 검수 4자료

번역 교차 검증(`tools/mgs3d_crossvalidate.py`)이 쓰는 네 가지다.

| | 자료 | 위치 | 규모 |
|---|---|---|---|
| ① | **3DS 영문 대사** (게임 추출) | `translation/10_master/current/*.csv` 의 `english`/`preview` 열 | codec 9,057 · demo 2,228 · movie 689 · vox 2,691 |
| ② | **현재 한국어 번역** | 같은 CSV의 `korean` 열 | 〃 |
| ③ | **영문 대사집 (화자 구분)** | `analysis/gamefaqs_mgs3_english.csv` / `.json` | **2,164행 / 화자 37종** |
| ④ | **한국어 대사집 (shinsnote)** | `translation/20_matching/script_ref/*.json` | **4,070세그 / 화자 37종** |

### ③ 영문 대사집 상세

GameFAQs FAQ **34684** — MHamlin, *Metal Gear Solid 3: Snake Eater Game Script*
v1.60 (2006-02-27). 형식은 `Speaker: text`이고 줄바꿈으로 이어진다.

```
원문(동일 문서 2부)  analysis/gamefaqs_mgs3_script_34684.txt
                    translation/00_source/english_script/mgs3-game-script.txt
파싱본              analysis/gamefaqs_mgs3_english.csv   (sequence, line, speaker, speaker_key, text)
                    analysis/gamefaqs_mgs3_english.json
도구 입력용 변환본   translation/20_matching/en_script/en_script_mgs3_gamefaqs.json
사용                --en-script translation/20_matching/en_script/en_script_mgs3_gamefaqs.json
```

**한계: 2,164행이 상한이다.** codec 정본 9,057행 중 영어 완전일치는 428행뿐이다.
선택 무전 상당수가 대본에 없어서 그 줄들은 화자를 얻을 수 없다.

주의 — 사용자가 처음 지목한 URL은 `faqs/43456`이었으나 저장본은 **34684**다.
어느 쪽이든 브라우저 없이는 못 받는다(WebFetch **403**, 봇 차단).

### ④ 한국어 대사집 상세

`shinsnote.com/219` 외 20페이지. `page` / `sequence` / `speaker` / `text` 구조로
파싱돼 있고 서사 순서를 갖는다.

```
원문 HTML          translation/00_source/script_ref/pages/page_01_219.html … page_20_*.html
원문 텍스트         translation/00_source/script_ref/bundle_reference/*.txt (20개)
파싱본 전체         translation/20_matching/script_ref/script_ref_mgs3_classified.json  (4,070)
파싱본 codec        translation/20_matching/script_ref/script_ref_mgs3_codec_only.json  (2,098)
파싱본 movie/demo   translation/20_matching/script_ref/script_ref_mgs3_movie_demo_only.json (2,625)
```

**`script_ref`라는 이름이 오해를 부른다 — 이건 한국어 자료다.** 영문 대사집이
아니다. 2026-08-22에 정확히 이 이름 때문에 ③을 못 찾았다.

## 그 밖의 참조 자료

| 자료 | 위치 | 용도 |
|---|---|---|
| PS2 한글판 추출물 | `analysis/ps2_korean/` | 공식 한국어 대응 후보 |
| 3DS 영문 codec 원본 | `translation/00_source/codec_3ds_english/` | 원문 대조 |
| 도너 4언어 (FR/DE/IT/ES) | **게임 파일 자체** — `vox.dat` 큐, codec/movie/demo 레코드 | vox 교차 검증의 기준선 (`tools/mgs3d_vox_donor_check.py`) |
| clean 기준 트리 | `experiments/2026-08-13-clean-glyph-baseline/clean-tree/` | 모든 빌드의 입력 원본 |

**도너는 외부 자료가 아니라 게임 안에 있다.** `vox.dat`은 큐마다 EN +
FR/DE/IT/ES가 같은 타이밍에 들어 있어, 모든 줄에 전문 번역 4개가 완벽히 정렬된
대조 기준이 된다. 「도너에 노력 쓰지 말 것」 규칙은 도너를 *번역하지* 말라는 뜻이지
*증거로 쓰지* 말라는 뜻이 아니다.

## 저작권

③ ④와 `analysis/ps2_korean/`은 저작권이 있는 게임 스크립트다. **커밋 금지,
공개 금지, 세션 밖으로 대량 발췌 금지.** `.gitignore`가 `/translation/`,
`/analysis/`, `/handoff/`를 전면 제외하고 허용 목록으로 운영한다 (2026-08-20에
히스토리에서 제거하고 force push한 이력이 있다).
