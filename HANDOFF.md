# HANDOFF — MGS3D Korean Glyph Integration

## 다음 세션 체크포인트 (2026-08-19 저녁)

> ## 개발 staging = **CPP-on** 기본 (2026-08-19 최종 확정)
> 개발·실기 검수 편의를 위해 **개발 staging의 기본 상태는 CPP-on**이다.
> 최종 릴리즈는 동일한 확정 공통 빌드에서 **CPP-off 호환판** / **CPP-on판(New 3DS 계열
> + 에뮬레이터)** 으로 분기하고, **사용자용 범용 패처는 제공하지 않는다** —
> `docs/RELEASE-PACKAGING-POLICY.md` 기준.
>
> - `exefs/code.bin` **`4e693f32b1b20d99705576a209efca4671f80fad71930650c5befe2d46527cb4`** (CPP-on)
> - CPP-off 기준본: `archive/pre-cpp-20260819/code.bin` `b9514ec5da8897db…`
> - 두 이미지 차이는 압축 해제 기준 **21바이트, 전부 `0x0010AEF6..0x0010AF0B` 안. 창 밖 차이 0**
> - renderer 6훅 **6/6 불변**, 리터럴 풀 `0x008E1618` 정상
>
> **재적용 시 반드시 `--output`으로 workdir를 staging 밖에 둘 것.**
> 그러지 않으면 `code.blz.bin` / `code.decompressed.bin`이 exefs에 쌓인다
> (2026-08-19에 실제로 발생해 정리함). staging exefs에는 `banner/code/icon/logo`만 있어야 한다.
>
> **exefs 중간 산출물 정리(같이 확정).** `code.blz.bin` / `code.decompressed.bin`은
> 원래 스테이징 레이아웃에 없던 파일이다 — `mgs3d_cpp_default_patch.py`가 workdir
> (= exefs)에 남긴 부산물이고, CPP 작업 이전 아카이브 스테이징의 exefs에는 `code.bin`
> 하나뿐이었다. 저장소의 모든 도구도 `exefs/code.bin`만 읽는다. 그래서 재생성이 아니라
> **아카이브 후 제거**했다. **CPP 패치를 다시 돌릴 때는 `--output`으로 workdir를
> 스테이징 밖으로 빼서 이 부산물이 exefs에 남지 않게 할 것.**
>
> codec.dat `b6e30310…` / movie.dat `c48d8cc8…` / demo.dat `c44bb512…` /
> exheader.bin / scenerio.gcx 169개 전부 무변경. CCI·commit·push 없음.

> ## ⚠️ codec production build에는 `mgs3d_codec_expand_locations`가 **필수**
> **`tools/mgs3d_build.py`를 그대로 쓰면 codec 빌드가 실패한다** — 확장 단계가 없다.
> master는 동일 문자열을 1행으로 접고 나머지를 `locations` 열에 두는데,
> `make-translation`은 canonical 1개만 내보낸다. byte 예산은 **GCX 단위 풀**이라
> 빠진 위치의 바이트가 풀에서 사라지고 **멀쩡한 번역이 용량 초과로 실패**한다.
> 실측: GCX 44는 확장 없이 3행/73B(+10B 초과, 실패) → 확장 후 17행/2,048B(성공).
> 전체 8,994행 → 225,307 units.
> **`exceed fixed region by N bytes`가 뜨면 번역 길이가 아니라 확장 누락을 먼저 의심할 것.**
> donor accept 해제나 행 제외로 대응하면 멀쩡한 번역을 잃는다.
> 올바른 순서와 상세는 `wiki/Build-System.md` 최상단 참조.

> ## codec 번역 트랙 종결 (2026-08-19)
> 최종 게이트 **9/9 PASS**, location coverage **100%** (233,427 / 233,427).
> 이번 적용: **46행** (신규 번역 40 / 기존 복구 2 / 복구 후 축약 4), HUMAN **0**.
> 함께 처음으로 DAT에 실린 것: **말투 QA 1,333행** — master에는 2026-08-18부터
> 있었으나 codec.dat에 빌드된 적이 없었다. 이번 빌드가 최초 반영본이다.
> overflow 0 / missing glyph 0 / Hangul glyph 추가 0 / 레코드 크기 변화 0 /
> DAT 역판독 46-46 일치.
> **최종 codec.dat SHA256 `b6e303105a08bfc905fe7e3ac6e4cd450f22dff228b066198bee7d751403f981`**
> staging 반영 완료 (이전 `b29807f8…`). 근거: `docs/evidence/2026-08-19-codec-residual/`.
> DONOR_ERROR 947 / VALID_ENGLISH 94 / KEEP_ENGLISH 13은 번역 대상이 아니며
> coverage 분모에서 제외한다 (`tools/mgs3d_codec_final_gate.py`가 규칙을 구현).
> CCI·release·commit·push·버전 태그 없음.

> **새 authority 확보 — 영문 게임 대본.** GameFAQs·Neoseeker는 둘 다 HTTP 403이지만
> 같은 문서(MHamlin, MGS3 Game Script v1.60)의 평문 미러가 GitHub에 있다.
> `translation/00_source/english_script/mgs3-game-script.txt` (251,806 B / 7,424행).
> **화자가 명시된 컷신·무전 대본이다.** movie/demo 판정 5건을 이걸로 교차검증했고
> 모순 0건. 앞으로 화자/장면 판정은 Shinsnote(한국어) + 이 대본(영어) 2중 근거로 한다.
> **단, 인게임 적 대사(`Who's that!` 등)는 이 대본에 없다.**

> **movie/demo — master 반영 + DAT 재빌드 + staging 완료 (2026-08-19 저녁). HUMAN 0.**
> 총 **191행** 반영: 오배치 REPLACE 72 + 오탈자 T1/T2/T3 + 말투 FIX 91 + overflow 축약 8
> + HUMAN 해소 2 + NO_SOURCE 신규번역 17 + 고유명사 교정 1.
> 백업 `demo.csv.bak-pre-misplaced-recovery-20260819`, `*.bak-pre-finalize-20260819`.
> 인코더 게이트: **movie 107/107 · 689/689, demo 328/328 · 2,228/2,228,
> font_deficit 0, missing_characters 0, overflow 0.**
> DAT는 clean-tree에서 `--fixed-layout-reclaim`으로 재빌드(크기 무변동, +0 바이트),
> 실제 DAT 바이트 역판독 **119/119 일치**.
> staging `Romforge/output/unpacked/partition0`: **18개 중 movie.dat·demo.dat 2개만 변경**,
> codec.dat·slot.dat·vox.dat·code.bin·exheader.bin·scenerio.gcx 169개 전부 무변경.
> **CCI·release·commit·push는 하지 않았다.**
> 남은 보류: **0** (backlog CSV의 27건은 전부 해소됨).

> **말투 FIX 91건 전부 적용 완료.** 오배치 세트와 교집합 0이었고 master 드리프트도 0이라
> 충돌 없이 들어갔다. 화자 말투는 Shinsnote로 검증: 스네이크=해라체, 소령=하게체,
> 소코로프=하오체(master 레코드 내부 관행과 일치). 재분류 근거는
> `docs/evidence/2026-08-19-media-misplaced-recovery/media-register-fix-reclassified.csv`,
> 적용 내역은 `media-finalize-applied.csv`.

> **stage/scenerio.gcx — 적/NPC 대사는 1,571행 중 13행뿐이다.**
> 나머지는 도감·아이템·UI다. 규모 인식을 여기서 맞출 것.
> **PS2 STAGE.DAT이 stage의 유일한 한국어 authority다 — Shinsnote는 stage를 커버하지
> 않는다(완전해독 58행 대조, 일치 0건).**
> 적 대사 3종은 이미 복구됐다: `I see him!!`→**있다!!**(occurrence 228=228 정확 일치),
> `Who's that!`→**누구냐!**, `Speak!`→**말해!** (전부 미해결 토큰 0).
> `Answer me!`는 로컬 글리프 `L229` 하나가 막는다 — OCR이 `=`로 오독. 추측 금지.
> **최대 레버리지는 미상 static 토큰 43개** — 이것만 풀면 PS2 stage 해독이
> 59 → 196행(12.7%)으로 세 배가 된다. OCR 임계값 낮추기는 금지.
> 조사 리포트: `docs/evidence/2026-08-19-stage-recovery/STAGE-RECOVERY-SURVEY.md`

> **위험: 상수 오프셋 금지.** PS2↔3DS 리소스 런은 대응하지만 오프셋이 구간마다 어긋난다
> (`ending`에서 -1221과 -1222가 공존). 반드시 ASCII 앵커 + 단조 정렬로 풀 것.
> movie/demo에서 exact-unique 매칭이 대규모 오배치를 만든 전례를 반복하지 말 것.


## 중요 결정사항

> **[`docs/RELEASE-PACKAGING-POLICY.md`](docs/RELEASE-PACKAGING-POLICY.md) — 릴리즈/배포 방침 (2026-08-19 확정).**
> 배포 관련 결정은 이 문서가 기준이며, 다른 문서와 충돌하면 이 문서가 이긴다.
> 요약: **개발 중에는 staging 트리 하나만** 유지하고 실기용/에뮬용을 분리하지 않는다.
> **최종 릴리즈에서만** 하나의 확정 한글판에서 실기용(CPP 없음)과 에뮬용(마지막
> 단계에 CPP 패치 적용)을 각각 완성된 패치로 만들고, 두 산출물의 차이가 CPP 외에
> 없음을 SHA/diff로 검증한다. 사용자용 범용 패처·옵션 체크박스·CPP 단독 도구는
> 배포물로 만들지 않는다. 최종 패치 형식(xdelta/BPS/LayeredFS/RomFS)은 미확정.
> 결정 ID: `wiki/Decisions.md` DEC-019 ~ DEC-022.

> **릴리스 규칙 (2026-08-19).** 이후 **모든 버전은 사용자 승인 없이 올리지 않는다.**
> 빌드·스테이징·문서화까지는 진행하되, 배포·commit/push는 승인 후에만.

## ▶ 오후 재개는 이 문서부터 (2026-08-19)

> **[`docs/HANDOFF-2026-08-19-afternoon.md`](docs/HANDOFF-2026-08-19-afternoon.md)**
> 오전 세션 전체가 read-only 분석이었다 — master·DAT·빌드·스테이징·commit 전부 무변경.
>
> **오후 첫 작업**: movie/demo 오배치 수동 문맥 검수 312행.
> 시작 행 = `output/media-register-qa/media-offset-verdicts.csv`의
> `verdict=UNREVIEWED` 첫 행 **`demo r0 e30`**
> (이전 메모의 `demo r5 e5`는 우선순위 flag 기준이었다 — **정정**).
>
> 금지: 자동 재정렬 재시도, 말투 FIX 91건 적용,
> `en_*_korean_matches.csv`·`mgs3_korean_english_alignment*.csv`를 authority로 사용.

## NEXT — 재정렬 트랙 중단, 수동 검수로 복귀 (2026-08-19)

**[`docs/evidence/2026-08-19-media-offset-audit/REMAP-SOURCE-RECOVERY.md`](docs/evidence/2026-08-19-media-offset-audit/REMAP-SOURCE-RECOVERY.md) 부록 1·2를 읽어라.**
read-only. master·DAT·빌드·스테이징·commit 전부 무변경.

**자동 재정렬 2회 시도, 2회 모두 게이트 실패.**

| 시도 | 게이트(확정 KEEP 107행 재현) | MISPLACED 95 자동 REMAP |
|---|---:|---:|
| 1차 `mgs3d_media_realign.py` | 0 / 107 | 0 |
| 2차 `mgs3d_media_realign2.py` | **3 / 107 (2.8%)** | 1 |

2차에서 1차의 결함은 실제로 고쳤다. **(record, entry) 순서 = 스토리 순서임을 검증**
했고(1차의 58%는 앵커 오염이었다 — `english_sequence` 값 `71`·`339`·`1254`·`1424`가
각각 20·12·11·5행에 중복. 정제하면 **movie 96.8% / demo 85.4% 단조**), 윈도 앵커도
유니크 위치 + LIS 백본으로 바꿨다. 그래도 실패했다.

**근본 원인(측정값): master 한국어 2,917행 중 Shinsnote 대본에서 위치가 잡히는 행이
213~225행(7.4%)뿐이다.** 나머지 92.5%는 정규화·축약·재번역을 거쳐 원문과 더는 같지
않다. 앵커 밀도가 부족하고, 앵커 없는 구간은 EN↔KO 점수(고유명사·숫자·길이비)로
다리를 놓지 못한다. LIS 백본도 정상/오배치를 구분 못 했다(KEEP 61/107 vs
MISPLACED 47/95 — 비율이 같다). **파라미터 문제가 아니다.**

**결정: 재정렬 트랙 중단.** 다시 하려면 **의미 기반 이중언어 정렬기**(문장 임베딩)가
필요하고 현재 프로젝트 자산에 없다.
**검증된 경로인 312행 수동 문맥 검수로 복귀한다** — 확정된 95 MISPLACED / 107 KEEP도
전부 그 방식으로 얻었다. 시작점: `media-offset-verdicts.csv`의 `verdict=UNREVIEWED`
첫 행 **`demo r5 e5`**.

**게이트는 유지한다** — 앞으로 어떤 자동 정렬이든 **KEEP 107행 107/107 재현**을 먼저
넘어야 한다. 말투 FIX 91건은 계속 보류.

## NEXT — REMAP 근거 복원: 한국어 순서는 살아 있다, 기존 정렬은 전부 못 쓴다 (2026-08-19)

**[`docs/evidence/2026-08-19-media-offset-audit/REMAP-SOURCE-RECOVERY.md`](docs/evidence/2026-08-19-media-offset-audit/REMAP-SOURCE-RECOVERY.md) 를 읽어라.**
read-only. master·DAT·빌드·스테이징·commit 전부 무변경.

**한국어 sequence source 복원 = 성공 (2,958/3,031 = 97.6%).**
지난 세션의 "복원 불가" 판단은 **틀렸다.** `korean_sequence`는 전역 인덱스가 아니라
**`page` 내 인덱스**(0~266)였고, `en_*_korean_matches.csv`가 `page`를 버려서 해석이
안 됐던 것이다. `page`를 보존한 파일이 있다 —
**`analysis/mgs3_korean_english_alignment.csv`**(3,031행). 거기의
`(page, korean_sequence)`가 `shinsnote_mgs3_script.csv`의 `(page, sequence)`로
**97.6% 해석된다.**

**그런데 MISPLACED 95행의 자동 REMAP은 여전히 0이다 — 기존 정렬 전부가 원천이기 때문이다.**
`analysis/mgs3_korean_english_alignment_dp.csv`(1,389행, english_sequence distinct
1,389 = 1:1 단조)는 이미 DP 단조 정렬인데, 95행 전부에서 **DP의 한국어 = master의
한국어**였고 동시에 **DP의 `english` = 실제 DAT 대사(95/95)**였다. 즉 영어는 제대로
짚고 **엉뚱한 한국어를 붙였다** — 오배치의 뿌리는 DP 정렬 자신이고
`exact-unique-korean`은 그걸 하류로 복사했을 뿐이다. `confidence`도 1,326/1,389가
`medium`이라 게이트 구실을 못 한다.

**authority 사용 금지 목록(확정):** `en_{demo,movie}_korean_matches.csv`,
`mgs3_korean_english_alignment.csv`, `mgs3_korean_english_alignment_dp.csv`.

**재정렬 입력은 두 축 모두 확보됐다:**
한국어 = `shinsnote_mgs3_script.csv` 4,071행 `(page, sequence, kind, **speaker**, text)`,
영어 = master `current/{movie,demo}.csv` `preview` (DAT와 2,917/2,917 검증됨).
**Shinsnote의 `speaker` 열은 movie/demo에 없던 화자 정보다** — 재정렬이 성공하면
codec처럼 확정 화자 기반 말투 검수가 가능해진다.

**다음 절차(설계 완료, 미실행):** monotone DP 재정렬(두 축 전진만, gap 패널티) +
**고유명사·숫자 앵커**를 점수에 필수 포함 + 확정 조건 3개(경로 위 · 앵커 1개 이상 ·
좌우 이웃 2행 일관) 전부 만족할 때만 자동 REMAP, 아니면 HUMAN.
**검증 게이트: 확정 KEEP 107행을 먼저 107/107 재현**해야 정렬을 신뢰한다.
앵커 없는 짧은 대사(`그래 ?`, `음 .`)는 원리적으로 자동 확정 불가 — 이번 오배치가
정확히 그 집합이다. 실패 시 312행 수동 검수(`demo r5 e5`부터)로 복귀.

## NEXT — offset 오배치 전수 감사 체크포인트 (2026-08-19)

**[`docs/evidence/2026-08-19-media-offset-audit/README.md`](docs/evidence/2026-08-19-media-offset-audit/README.md) 를 읽어라.**
read-only. master·DAT·빌드·스테이징·commit 전부 무변경.

**offset 514행 중 KEEP 107 / MISPLACED 95 / REMAP 0 / UNREVIEWED 312.**
확정 시트: `output/media-register-qa/media-offset-verdicts.csv`.

**핵심 발견 — 근거로 쓰려던 파일이 원인이었다.** `20_matching/en_{demo,movie}_korean_matches.csv`
는 영어 DAT 키라 독립 검증용으로 보였지만, **손으로 확인한 오배치 95행 전부가 그 파일에
같은 키·같은 한국어로 들어 있다(95/95).** master offset 행의 **출처**이므로 대조하면 항상
일치한다 — 첫 자동 감사가 KEEP 215를 낸 이유다.

**메커니즘:** 그 표의 `match_status`가 **`exact-unique-korean`**(demo 457 중 333) —
**한국어 문자열의 유일성으로만 매칭**하고 시퀀스를 안 본다. `그래 ?`·`몰라 ?`·`음 .`
같은 짧은 대사가 대본 아무 데나 붙는다. 정상 구간은 `en_seq - ko_seq` 델타가 +5로 일정한데
오배치는 `265/144`, `476/2`, `501/50`처럼 튄다.
**따라서 연속 drift block이 아니라 산발성 오배치다 — LIS 분석에서도 block 0개.**

**REMAP 0인 이유:** `korean_sequence`가 가리키는 중간 한국어 리스트가 보존돼 있지 않다
(`shinsnote_mgs3_script.csv` 30/366, `classified` 30/366, `movie_demo_only` 0/366).
**기존 산출물만으로는 remap 불가** — Shinsnote 대본을 영어 DAT 순서에 맞춰 **재정렬**해야
하고, 그때는 `exact-unique-korean`이 아니라 **단조 시퀀스 정렬**을 써야 한다.

**스크리닝 신호는 약하다.** LIS backbone 이탈 표시는 손으로 읽은 오배치의 94%를 잡지만
508행 중 419행을 flag한다. 미검토 flag 상위 22행 표본은 **거의 전부 정상**이었다
(`You OK? → 괜찮아?`). **312행 자동 판정 금지, 읽는 순서 힌트로만 쓸 것.**

**더 쓸모 있는 단서:** 확정 오배치 95행은 거의 전부 **문장부호 앞 공백**을 달고 있고,
UNREVIEWED 312행은 그 공백이 없다. **정규화를 거친 행 = 재작성된 행**이라는 가설을
다음 세션에서 검증할 것.

**다음 세션 시작:** `media-offset-verdicts.csv`의 `verdict=UNREVIEWED` 첫 행 **`demo r5 e5`**.
**말투 FIX 91건은 계속 보류** — 오배치 정리 전 적용 금지.

## NEXT — 인게임 대사 텍스트 경로 발견 + movie/demo 문맥 검수 (2026-08-19)

분석·판정만 했다. **master·빌드·스테이징 전부 무변경.**

### 1. 인게임 적/NPC 대사는 codec/movie/demo에 없다

**[`docs/ingame-stage-text-english-residue-2026-08-19.md`](docs/ingame-stage-text-english-residue-2026-08-19.md) 를 읽어라.**

`stage/<이름>/scenerio.gcx` **169개 파일**이 네 번째 텍스트 컨테이너다 —
codec.dat 레코드와 **완전히 같은 GCX 포맷**이라 `GcxRecord`가 그대로 파싱한다
(디스크에서 정렬 패딩이 없을 뿐, 복사본을 패딩하면 풀린다). 여기에 적 경계 대사
(`Who's that!` 52스테이지 208곳), 무기·식량·약품 설명, 동식물 도감, 부상 이름,
지역명, RESULTS 화면, 칭호, 조작 도움말이 **전부 영어 원문 그대로** 들어 있다.

**미번역이지 빌드 누락이 아니다.** 스테이징된 169개의 문자열 영역이 영어 원본과
**169/169 SHA 동일**(글리프 페이지만 EOF에 덧붙어 있다).

**잔존량: 유니크 1,571행 / 149,592 location / 89,070 B** (prose 1,065).
언어 분기는 **EN/FR/ES 3개뿐**(독일어·이탈리아어 없음), 가변 길이 블록 3연쌍이라
period-3 가정은 81%밖에 설명 못 한다. 구조 판정과 어휘 판정 **불일치 0건**,
donor:english location 비 **정확히 2.000**으로 교차검산됐다.

**번역 정본:** 프로젝트 내부엔 없다(매칭 8건 전부 오탐). PS2 한국어 STAGE.DAT은
이미 추출·카탈로그돼 있으나(`analysis/ps2_korean/stage_text_catalog.csv` 90,216행)
**해독률이 1,548행 중 58행**이다 — codec 때 쓴 로컬 글리프 OCR 파이프라인을 stage용으로
끝까지 돌린 적이 없다. 용량은 여유롭다(donor가 영어의 2.55배, 169/169 스테이지 마진 양수).

도구: `tools/mgs3d_stage_text_scan.py` (읽기 전용),
증거: `docs/evidence/2026-08-19-stage-text-scan/`.

**주의: stage 텍스트는 `originals/3ds_pristine/`(일본판)이 아니라
`experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/`(영어판)를 봐야 한다.**

### 2. movie/demo — 말투보다 먼저, 대사 116행이 남의 자리에 있다

**[`docs/movie-demo-contextual-qa-2026-08-19.md`](docs/movie-demo-contextual-qa-2026-08-19.md) 를 읽어라.**

말투 검수를 하려고 문맥 순서로 읽다가 **한국어가 다른 대사 자리에 들어간 116행**을
찾았다. 영어 쪽은 멀쩡하다 — master 2,917행의 `preview`를 실제 DAT 엔트리와 대조해
**2,917/2,917 일치**. 원인은 `translation_source=offset` 514행이 **일본판 DAT 기준**
비교표에서 바이트 오프셋으로 옮겨온 것이라는 점이고, 문장부호 앞 공백(`좋아 , `)이
그 지문이다(offset 행의 36.6% vs 다른 소스 1% 미만). **116은 하한** — 나머지 326개
offset 행은 아직 안 읽었다.

**말투 자체는 대체로 멀쩡했다.** 두 말투가 섞인 75레코드 중 55행은 정상(EVA 존댓말,
볼긴/보스에게 보고하는 부하, 하오체 소코로프 장면의 스네이크 반말). 진짜 흔들림은
**12행**, 거의 전부 **스네이크가 제로에게 존댓말**을 쓰는 codec↔demo 불일치다.

제안 시트 `output/media-register-qa/media-qa-proposals.csv` (509행):
**FIX 91**(전부 바이트 검증 통과) · KEEP 55 · REVIEW 131 · HUMAN 232
(오배치 116 / 고유명사 표기 분열 78 / 한국어 속 영어 잔존 34 / 기타 4).

분류기 수정 2건: **하오체를 독립 클래스로** 분리(소코로프 `-거요`가 존댓말로 잡히던
문제, 하오체 레코드 안에서만 재판정하는 2-pass), **`-십시오`가 하오체로 오분류**되던
문제(`시오`가 `보십시오`를 삼킴). **codec 분류기는 건드리지 않았다.**

판정 근거는 `docs/evidence/2026-08-19-media-qa/verdicts.py`에 행 단위로 남겼다(KEEP 포함).

**순서 제안:** 오배치 116행 → 나머지 326 offset 행 검수 → FIX 91 적용 →
고유명사 표기 정책 → 영어 잔존 34행 재번역. **말투만 먼저 고치면 통째 교체 때 날아간다.**

## NEXT — v0.9 CPP 강제 패치 테스트 빌드 스테이징 완료 (2026-08-19)

**[`docs/v0.9-cpp-test-staging-2026-08-19.md`](docs/v0.9-cpp-test-staging-2026-08-19.md) 를 읽어라.**

`code.bin` **하나만** 바뀌었다: `b9514ec5…` → **`4e693f32b1b20d99…`**
(압축 크기는 5,264,540 B로 이전과 **우연히 같다** — SHA로 구분할 것).
`codec.dat b29807f8…`·`movie.dat`·`demo.dat`·`exheader.bin` 전부 그대로.
되돌리기: `Romforge\archive\pre-cpp-20260819\code.bin` 복구. **CCI 미생성.**

패치는 `0x0010AEC0` 강제 루틴의 "꺼짐" 갈래 6워드(24 B)를 **"꺼져 있으면 켠다"**로
교체한 것이다 — `config+8` bit0을 세우고 `0x0010AEDC`(진짜 켜짐 갈래)로 합류시켜
프리셋 3과 컨트롤 표를 게임 자신의 경로로 채우게 한다. 코드 케이브 불필요, 크기 동일,
exheader 무변경. 도구: `tools/mgs3d_cpp_default_patch.py` (앵커 5개 검증 → 교체 →
BLZ 재압축 → 왕복 검증, 재실행 안전).

검증: 압축 해제 이미지 차이 21 B(전부 패치 구간 안), 글리프 패치 6곳·트램폴린
`0x0087F8C4..0x008838C3` 무변경, BLZ 왕복 OK, 교체 구간 진입 분기는 `0x0010AED8`
하나뿐(점프테이블 참조 없음).

**아자르 테스트**: 세이브는 쓰던 것 그대로. 아자르 입력에 **ZL·ZR·오른쪽 스틱이
바인딩돼 있는지 먼저 확인**(CPP 스킴은 `R→ZR`, `L→ZL`). 오른쪽 스틱으로 카메라가
움직이면 성공. 안 되면 `builds/cstick-test-2026-08-18/A_basic_savedata`로 재시도해
원인을 가른다. **옵션 메뉴는 열지 말 것**(켜기 동작은 여전히 애플릿 → 먹통).

배포 위치는 **마지막 옵션**으로 합의됨: 최종 산출물(CCI 또는 .3ds)에 마지막 단계로
`code.bin`만 다시 패치. 구형 3DS(CPP 미장착)에서는 조작이 깨지므로 **기본 빌드가
아니라 별도 옵션 빌드**로 낸다.

## NEXT — CPP를 기본값으로: 가능하다 + 어제 패처의 결함 수정 (2026-08-19)

**[`docs/cstick-default-scheme-feasibility-2026-08-19.md`](docs/cstick-default-scheme-feasibility-2026-08-19.md) 를 읽어라.**

안드로이드에서 세이브 파일을 만지기 어렵다는 문제 → **세이브 없이 `code.bin`
패치로 기본값을 바꿀 수 있다.** `code.bin`은 BLZ 압축이라 그냥 검색하면 안 나온다
(`tools/nintendo_blz.py`로 풀어야 한다. 5.26 MB → 8.48 MB, VA = 파일오프셋+0x100000).

압축 해제 이미지에서 확인한 구조:

- `0x0088F470` **컨트롤 프리셋 4개**(0x100 간격). preset[0] = CPP-off 세이브의
  `0x3C..0xF7`과 바이트 동일, **preset[3] = CPP-on 세이브와 바이트 동일**.
- `0x0012BD8C` `apply_scheme(i)` — preset[i] 47워드를 config+0x38에 복사하고
  config+0x138에 i를 저장. 세이브는 `u32 CRC || config`라 **config+X = 세이브 X+4**.
- `0x0010AEC0` **강제 루틴** — `config+8` bit0(= 세이브 `0x0C` bit0)이 켜져 있으면
  scheme 3, 꺼져 있으면 scheme 0을 **강제한다**.
- 켜기 `0x0082C9F0`(`flags |= 1`), 끄기 `0x00116B50`·`0x001319A0`·`0x007FD6F4`·
  `0x007FDBDC`. **끄는 쪽은 애플릿을 부르지 않는다** — Citra 먹통은 켤 때뿐.

**어제 패처는 불완전했다.** 컨트롤 표 33바이트만 써서 게이트 비트와 프리셋 번호가
빠졌고, 위 강제 루틴이 그걸 preset[0]으로 되돌린다. 수정 완료 —
`enable-cpp`는 이제 `표 + 0x0C bit0 + 0x13C=3`을 모두 쓴다(`0x0C`는 비트 마스크로만).
왕복 검증 재실행 3/3 통과, `builds/cstick-test-2026-08-18/` A/B 세이브 재생성.

**주의: 메인 빌드 기본값으로 넣으면 안 된다.** preset[3]은 ZL/ZR·오른쪽 스틱을
전제해서 구형 3DS(CPP 미장착)에서는 조작이 망가진다. **별도 옵션 빌드**로 내라.

## NEXT — 확장 슬라이드 패드(CPP): 남의 세이브 배포 대신 세이브 패처 (2026-08-18)

**[`docs/cstick-save-patcher-2026-08-18.md`](docs/cstick-save-patcher-2026-08-18.md) 를 읽어라.**

배포물에 RT37 세이브를 동봉하지 않아도 되도록, **플레이어 자기 세이브에서 CPP를
켜는** 도구를 만들었다: `tools/mgs3d_save_tool.py`의 `enable-cpp` / `disable-cpp` /
`learn-cpp`. 진행도 보존, 되돌리기 가능, 재배포 문제 없음.

세이브 5개(CPP-off 2 + RT37 CPP-on 3) **그룹 차분**으로 58바이트를 얻었고 그중
**33바이트가 `0x3C..0xF7`**(스킴 id + 주 버튼 표 + CPP 표)다. 정적 검증 전부 PASS —
사용자 세이브에 enable하면 그 창이 RT37 CPP-on과 **바이트 동일**, RT37에 disable하면
진짜 CPP-off 세이브와 **바이트 동일**(3/3), 창 밖 변경 0, on→off→on 왕복 바이트 동일.

**미확정 2가지:** ① 에뮬 실동작 미확인 ② 창 밖 옵션 블록 5바이트
(`0x13C/0x140/0x15C/0x162/0x168`, on일 때만 비0, `2D`=45·`40`=64는 **카메라 감도로
추정**) — 필수면 기본 프로파일만으로는 우측 스틱 카메라가 안 움직일 수 있다.
`--with-option-block` 플래그로 A/B 테스트하면 결판난다.

**지금 실기 검증 중이면 2분짜리 캡처를 부탁한다** — 실기에서 CPP **끈** 상태 세이브
백업(Checkpoint/JKSM) → 게임 내에서 **켜고** 같은 슬롯 세이브 → 다시 백업.
이 쌍을 `learn-cpp`에 넣으면 추측이 전부 사라진다. RT37의 "토글하지 마라" 경고는
**에뮬레이터 이야기**이고 실기 토글은 안전하다(RT37 본인이 2DS에서 그렇게 만들었다).

## NEXT — 화자 말투(register) 1,333행 교정, master·빌드·스테이징 반영 (2026-08-18)

**[`docs/codec-speaker-register-apply-2026-08-18.md`](docs/codec-speaker-register-apply-2026-08-18.md) 를 읽어라.**

외부 대본으로 화자가 확정된 행만 대상으로 말투를 고쳤다. Para-Medic·EVA 존댓말,
Zero·Sigint·Snake·The Boss 반말. **MISMATCH 1,335 → 적용 1,333, HUMAN 2**
(HUMAN 2건은 2026-08-18 사용자 판단으로 **둘 다 KEEP 종결** — 텍스트 변경이 없어
재빌드·재스테이징 불필요, `codec.dat b29807f8…` 그대로 유효).
(Para-Medic 329 / Sigint 319 / Zero 298 / EVA 149 / Snake 135 / The Boss 103,
존댓말→반말 855 · 반말→존댓말 478.)

**먼저 분류기가 두 번 틀렸다.** `ㅂ니다`는 자모라 합성 한글(`겁니다`)과 절대
매칭되지 않아 죽은 패턴이었고, 그렇다고 `니다`/`니까`로 바꾸면 `아니다`와
연결어미 `-으니까`를 삼킨다. **앞 음절의 종성이 ㅂ인지** 검사하는 것이 정답이다
(`(ord(c)-0xAC00)%28==17`). 대상 행이 1,285 → 1,342 → **1,335**로 움직였고,
이미 써 둔 수정안 15건은 **원래 올바른 존댓말 행**이어서 취소했다.

**canonical만 검증하면 또 놓친다.** 행의 `locations` 전부에 새 문자열을 넣고
레코드를 다시 조립하자 **16개 레코드가 추가로 byte-fit 실패**했다 — canonical에는
여유가 있고 중복 위치에 없는 occurrence 5~87짜리 문자열들이다. 전부 문장을 줄여
해소했다. 최종적으로 31,509 location 중 31,506이 canonical과 바이트 동일,
나머지 3은 v0.89에서도 제외돼 있던 프랑스어 도너 위치다.

전 게이트 PASS: size delta +0, record/block_start/size/resource drift 0,
KO→EN 회귀 0, 신규 glyph 0, control token drift 0, 앵커 A 3/3 · C 16/16,
PARTIAL_APPLICATION 212 → 212(전부 FR/ES 도너).

스테이징: `codec.dat` **`b29807f8…`** (이전 `8348377c…`는
`Romforge\archive\pre-register-20260818\`). `movie.dat`·`demo.dat`·`code.bin`·
`exheader.bin` 변경 없음. **CCI 미생성.** Citra 확인은 아직이다.

기존 `codec-final-revision-proposals.csv` 511행 중 71행이 겹쳤고 **69행은 기존
의미/용어 수정 위에 말투 수정을 병합**(충돌 0). **나머지 440행은 미적용**이다.

## NEXT — codec 실기 QA Round 5 완료, 재스테이징 (2026-08-17)

**[`docs/codec-qa-round5-2026-08-17.md`](docs/codec-qa-round5-2026-08-17.md) 를 읽어라.**

실기 3건의 원인이 **서로 달랐고**, 공통 원인은 **검증 방법 자체**였다.
codec은 canonical location만 검사했고(22,818행 불일치 0 — 그래서 늘 PASS였다),
결함은 **중복 location에만** 있었다. movie는 아예 재빌드되지 않았다.

1. **초반 배낭 튜토리얼 1행** — `PARTIAL_APPLICATION`. `20:17`만 한국어, `52:34`·`53:47`은 영어.
   `langid`가 아이템명 토큰 1개(도너 분기도 아이템명은 영어)만 보고 donor 판정 → 도너 재분류 →
   전파 제외. v0.69부터 `pending`으로 남아 있던 항목이며 이번에 종결.
2. **강하 직전 무전 1행** — codec에 없다. `movie.dat` rec 1/ent 11 라인이고 master는 이미
   고쳐져 있었다. **movie.dat이 재빌드되지 않았을 뿐**
   (`BUILD_NOT_APPLIED`). 같은 라운드 사용자 수정 3건 전부 미반영이었다. demo는 0건.
3. **Godzilla** — `MISALIGNMENT 0`. `SPEECH_LEVEL_ERROR 13` + `MEANING_ERROR 5`.
   화자는 English 문답 + 스페인어 도너 순서로 확정(Para-Medic 20 / Snake 11), 16행 수정.

**새 게이트: `tools/mgs3d_codec_partial_application.py`** — 모든 location을 검사한다.
**224 → 212행**, 남은 212는 전부 의도적 제외(FR/ES 도너 206 + 언어 중립 6).

파이프라인 버그 3건 수정: `make-translation`의 `csv.field_size_limit`(이게 막히면
**master를 고쳐도 빌드에 도달하지 않는다**), `expand_locations`의 상대경로 리포트 유실,
`resources()` 미캐시(59.6 GB 재복호화 → **140분이 15초로**).

전 게이트 PASS: size delta +0, KO→EN 회귀 0, 신규 glyph 0, 손실 0, capacity drop 0,
coverage 95.10%, HPK exit 0, 앵커 A 3/3 · C 16/16.

스테이징: `codec.dat` `8348377c…`, `movie.dat` `a9f9ab9c…`
(이전 파일 `Romforge\archive\pre-round5-20260817\`). `demo.dat`·`code.bin`·`exheader.bin`
변경 없음. **CCI 미생성.**

## NEXT — renderer range guard CONFIRMED FIXED on hardware (2026-08-17)

**The movie + R-button Data Abort is gone**, confirmed by the user on a real 3DS
with the range-guard build (`code.bin` `b9514ec5…`, `exheader.bin` `2bca5dcb…`).
The non-dereferencing range guard is hardware-validated, not just statically
verified. Remaining on that build: run the Citra regression list (codec
외/워/백/업/팀, demo/movie 억/추/션, mixed lines, boot→title) to confirm nothing
else moved.

### C-stick / Circle Pad Pro — solved by a save, not by code

**Read [`docs/cstick-save-distribution-2026-08-17.md`](docs/cstick-save-distribution-2026-08-17.md).**
The user found `builds/MGS3D_C_stick_SAVESCITRA.rar` — community saves (RT37,
2021) made on a real 2DS with CPP already activated, which sidestep the Citra
Extrapad freeze entirely. Verified here: all four parse as MGS3D saves, all four
pass the checksum, all sit at `v001a`/`r_sna01`, and **`Normal` and
`Normal (alt)` are byte-identical** — ship three, not four.

Save format cracked along the way: `save[0x00] = u32 LE CRC32(save[4:])`,
confirmed on six independent saves. `tools/mgs3d_save_tool.py` does
`show`/`diff`/`fix-crc` and reports CPP state. CPP activation rewrites the
primary button table at `0x40..0xBF` and populates `0xC0..0xF7`, which is **all
zero when CPP is off** — the cleanest state indicator.

Before shipping: one Citra smoke test with our CCI, a decision on attribution
(the saves are RT37's work), and a Korean note carrying RT37's warning forward —
**never toggle the 확장 슬라이드 패드 option in an emulator**, with or without
these saves.

## Renderer range guard — build and verification detail (2026-08-17)

**Read [`docs/renderer-range-guard-2026-08-17.md`](docs/renderer-range-guard-2026-08-17.md).**

**v0.83 confirmation is on hold.** A hardware Luma dump root-caused a Data Abort
**inside the v0.82 renderer guard**: it admitted a candidate pointer on `!= 0`
alone and then *read* it to check the page signature, so a stale snapshot holding
garbage (`obj[0x4C] = 0x2A68DFA8`) faulted in the guard itself — the guard could
never reject the case it existed to handle. Full decode, with the code dump
matched uniquely to the v0.82 binary:
[`docs/evidence/2026-08-17-v082-renderer-data-abort/`](docs/evidence/2026-08-17-v082-renderer-data-abort/README.md).
New parser: `tools/parse_luma_crash_dump.py`.

Fixed and staged: every pointer is now range-tested with **arithmetic only, no
load**, and dereferenced only inside a window where valid values were actually
observed (object `[0x08000000,0x1C000000)`, page base `[0x08000000,0x0C000000)`).
The unvalidated `table[2]` fallback is **gone**; when neither candidate proves
itself the glyph draws **blank** from 128 zero bytes inside the cave, with the
index forced to 0. No cache, per the measured evidence. Width/classify need no
guard — they never dereference a glyph-page pointer (verified by disassembly).

All static gates PASS: 0 unexpected changed regions, 6/6 branches on target,
exheader `.text` +944 exactly, blank zone 128 B of zeros, HPK gate exit 0,
169/169 stages resident **and 169/169 carrying the guard signature**, plus an
instruction-by-instruction guard-before-load proof on both call sites and a
replay showing the recorded crash value now skips the faulting read.

Staged: `code.bin` `b9514ec5…`, `exheader.bin` `2bca5dcb…`; previous pair
archived to `Romforge\archive\pre-range-guard-20260817\`. Only those two files
changed — `codec.dat` (v0.88 `6bdec076…`), `movie.dat`, `demo.dat`,
`scenerio.gcx`, `cache.hpk` untouched. **CCI not built.**

**Citra/Azahar is the verification gate** (2026-08-17 instruction — hardware
installation is not required for this; a real-3DS run is reserved for genuine
hardware-side defects and final release validation). Test order: codec
외/워/백/업/팀 · demo/movie 억/추/션 · **movie + repeated R input** (the crash
repro, stage `v003a`) · mixed lines and boot→title. A blank glyph is now an
expected safe outcome; the failure condition is a Data Abort or a layout shift.

**SOLVED — the Circle Pad option freeze is Citra's, not ours.**
[`docs/citra-extrapad-applet-freeze-2026-08-17.md`](docs/citra-extrapad-applet-freeze-2026-08-17.md).
Today's 105 MB Citra session log ends in a tight infinite loop: the game requests
library applet **1032 = 0x408 = `Extrapad`** (확장 슬라이드 패드) when the option
is toggled, Citra answers `Could not create applet 1032` **193,580 times** from
t=50.82 to t=70.50, and the game spins waiting for an applet that never starts.
**Zero guest exceptions in the entire session** — Citra stayed alive, so it is a
guest hang from an emulator gap, not a crash. It is reachable from stock retail
code we have never patched, so a pristine CCI would freeze identically. **No
`code.bin` change can fix it — do not read it as a regression, and do not open
that option while testing.**

## v0.83: dialogue fitting COMPLETE; repack a CCI and test (2026-08-16)

**Read [`docs/v0.83-fitting-complete-2026-08-16.md`](docs/v0.83-fitting-complete-2026-08-16.md).**

**The worklist is empty.** Every accepted line fits: movie **689/689**, demo
**2228/2228**, codec 0 capacity drops. The last 37 rows closed — 18 retranslated,
14 kept English in 3-byte slots, 1 respelled off the missing `뱌` (and accepted,
8,436 → 8,437 rows), 1 tightened, and 3 that I had wrongly filed as mismatches but
were correct Korean clause reordering across split subtitle lines.

All gates pass: sizes **delta +0** on all three DATs, codec record drift 0,
coverage **94.93%**, glyph page unchanged, HPK exit 0, 169/169 pages.

Staged: `codec.dat` `06a325de…`, `movie.dat` `7978657c…`, `demo.dat` `43937073…`;
`code.bin`/`exheader.bin` unchanged from the hardware-passed v0.82 renderer.
**CCI not built — RomForge is GUI-only, that repack is yours.**

## v0.82 fitting round 1 (superseded by v0.83 above)

**Read [`docs/v0.82-fitting-2026-08-16.md`](docs/v0.82-fitting-2026-08-16.md).**

228 rows shortened and applied (checker **PASS 228 / FAIL 0**), 14 kept English
(3-byte `No,`/`But` slots), 23 left infeasible (21 EN/KO mismatch, 1 too tight,
1 needs the missing `뱌`). Safe subsets: movie **608 → 685/689**, demo
**2045 → 2196/2228**.

All gates pass — both media DATs rebuilt at **delta +0** with +0 font bytes, codec
coverage **94.93%**, glyph page and character map unchanged (no `scenerio.gcx`
re-staging), HPK gate exit 0, 169/169 pages intact.

Staged: `code.bin` `1de8f4d9…`, `exheader.bin` `5ea5ddd5…`, `codec.dat`
`ffdc1ddc…`, `movie.dat` `b9879840…`, `demo.dat` `ce2a04bc…`.
**CCI not built — RomForge is GUI-only, that repack is yours.**

Check on hardware: the renderer regression list; the newly-visible cutscene
subtitles (most movie/demo text ships for the first time); and the 14 English
`No,`/`But` lines.

## v0.82 confirmed on hardware; remaining translation work (2026-08-16)

**Read [`docs/v0.82-confirmed-2026-08-16.md`](docs/v0.82-confirmed-2026-08-16.md).**
Hardware PASS: all glyphs render, codec reach **3.79% → 94.93%**.

Two follow-ups, both translation rather than engineering:

1. **Residual English is mostly donor.** Of 10,265 non-Korean locations, 8,889 are
   French/Spanish donor branch (no work — an English console never shows them) and
   only **313 rows / 825 locations** are genuine English. List:
   `translation/10_master/review/quality-worklist.csv` (`kind=ENGLISH`), ranked by
   `occurrences`, which after propagation *is* on-screen frequency.
2. **Awkward wording is MT register drift**, not the v0.81 shortening (only 17
   codec rows were shortened and they read fine). Proven in gcx 2181 res 21-27:
   one speaker's continuous story flips 반말→존댓말 mid-turn, calls the same person
   아버지 then 아빠, and opens a line `그것은 …` (literal "It was"). There is **no
   speaker field** in the data, so drift cannot be separated from normal
   two-speaker structure automatically — it needs conversation-ordered review.

Dialogue fitting still open at 265 worklist rows; no `korean_new` authored.

## v0.82 test build (superseded by the confirmation above)

**Read [`docs/v0.82-test-build-2026-08-16.md`](docs/v0.82-test-build-2026-08-16.md)**
for the renderer guard design and the full static verification.

Three files differ from the v0.81 staging: `exefs/code.bin` (`1de8f4d9…`),
`exheader.bin` (`5ea5ddd5…`), `romfs/codec.dat` (`ffdc1ddc…`). Previous ones
archived to `Romforge\archive\pre-v082-test-20260816\`.

The renderer now uses a **multi-candidate validating guard**: try `obj[0x4C]+K`,
validate it against the page's own bytes at `+0x0C` (`0F FF FF F0`), else
`table[2]+K`. All 931 glyphs take that one path; no per-character logic.
**No cache** — 15 runtime samples proved it cannot help (samples 10/11 share the
identical address `0x089d8744`, valid then invalid, so caching the address hands
back the stale one), and the cave is in RX `.text` anyway.

Static verification all PASS: **0 unexpected changed regions** (only the 6 patch
words + the cave), 6/6 branches on target, all symbols relocated and in-cave,
exheader `.text` +684 exactly, fixed-glyph path untouched, HPK gate exit 0,
169/169 glyph pages intact.

Regression list: codec 외/워/백/업/팀 · demo/movie opening 억/추/션 · the fixed
characters in those same sentences · no Data Abort. If it fails, roll `code.bin`
+ `exheader.bin` back to `ea2bb144…`/`39bd66cd…` to isolate the two changes.

## v0.82 earlier stages (2026-08-16)

**Read [`docs/v0.82-progress-2026-08-16.md`](docs/v0.82-progress-2026-08-16.md).**
**Nothing is staged** — the RomForge tree is still v0.81 byte for byte.

Done: the 42 misclassified rows (**reclassified as donor, not retranslated** — all
816 of their in-game positions hold French/Spanish in the game data itself);
**duplicate propagation applied and verified** (coverage **3.79% → 94.93%**,
`dropped_for_capacity` 0, record drift 0, file size delta +0, HPK gate exit 0);
worklist regenerated **302 → 265** with the codec 37 gone as predicted.

Renderer root cause is settled statically: `table[2]` is live-but-shared, and
`[obj+0x4C]` is a **snapshot frozen at scene setup** that dangles once a cutscene
reallocates the buffer — blank vs garbled is that difference. The decided fix is the
GCX parser's live pointer `*(0x00A472BC+0xC)+4+K`. Not built, by choice.

**Blocked, needs you at the emulator:** the GDB `anchor` sample
([recipe](docs/gdb-anchor-sample-recipe-2026-08-16.md)), then the renderer patch,
its regression test, the translator pass over the 265 rows, and only then staging.

## v0.81 hardware test root-caused; fitting is not the lever (2026-08-16)

**Read [`docs/v0.81-hardware-defects-rootcause-2026-08-16.md`](docs/v0.81-hardware-defects-rootcause-2026-08-16.md).**
Analysis only — no data, apply, staging or build change was made. Two defects
reported on hardware, both root-caused:

1. **Codec English residue is a duplicate-propagation gap.** The master dedupes
   strings; the build writes only the canonical `(gcx, resource)`. Of the
   **211,458** English display_text locations in the staged `codec.dat`:
   **193,138 (91.34%)** are duplicates that never received their translation,
   10,265 (4.85%) have no Korean in the master, 8,009 (3.79%) are Korean, and
   **byte capacity accounts for 30 (0.01%)**. Measured: canonical 7,971 Korean /
   duplicates **0** Korean. **Real codec reach is 3.79%, not 8,441 units.**
   `coverage-report.json` passed because it is a *glyph-page* report whose
   denominator is master rows — no gate measures translation coverage.
2. **`추`/`션` corruption is the `억` defect, and the v0.69 외/워/백/업/팀
   family.** Both reports are consecutive subtitles in demo record 5
   (@`11537428`, @`11537816`) — the opening cutscene. In each line the broken
   characters are exactly the global-page (`0x84xx-0x87xx`) ones; all fixed
   (`0x81xx-0x83xx`) characters render. Data is byte-perfect end to end, so this
   is a renderer defect in the glyph-page base. **The "stale anchor after a codec
   call" hypothesis is refuted.** 78-87% of lines carry at least one global-page
   character, so respelling around it is not viable.

### Follow-up work done the same day (2026-08-16) — still nothing staged

**1. Duplicate propagation is affordable.**
[`docs/duplicate-propagation-dryrun-2026-08-16.md`](docs/duplicate-propagation-dryrun-2026-08-16.md).
New `tools/mgs3d_codec_expand_locations.py` takes 8,478 → **201,482** units; the
shipped capacity gate then drops **0** with **0 failing GCX**. The same gate on
the canonical-only input reproduces v0.81 exactly (8,478 → 8,441, 37 dropped, 31
failing), which is what makes that credible. Replacing more strings makes records
*smaller* — Korean is shorter than the long English sentences — so the 31 failures
came from propagating too little, and **the 37 codec "capacity" worklist rows are
an artefact**. Verified layout-neutral: 2,264 of 2,326 records rebuilt with
`preserve_layout=True`, **0 changed size**, file size identical to the byte
(`67,204,976`, sha `40eead32…`). Reach measured on that build: **3.79% → 94.94%**
(+192,759 locations), with the capacity category gone to **0**.

**2. The missing gate now exists.** `tools/mgs3d_translation_coverage.py` measures
reach over *binary* locations with per-cause attribution, a `--min-reach`
threshold, and a detector control against the pristine build (0 false positives
over all 211,458 locations). Baseline saved to
`docs/evidence/coverage-v0.81-staged-2026-08-16.json`.

**3. Worklist budget model fixed.** `mgs3d_dialogue_worklist.py` now takes
movie/demo budgets from the encoder (`capacity_bytes`/`needed_bytes`) instead of
the CSV `size` column. All **17** known class-B rows now correctly report a 1-byte
deficit instead of "fits"; new `raw_budget` column gives translators the length
their own text must hit, since `wrap_like_source` adds 1-2 bytes they never see.

**4. GDB sample prepared, not run** — needs a human at the emulator.
[`docs/gdb-anchor-sample-recipe-2026-08-16.md`](docs/gdb-anchor-sample-recipe-2026-08-16.md).
`citra_gdb_mi_controller.py` gained an `anchor` command that reads both glyph-base
formulas and the `추`/`션` glyph slots in one shot, using no breakpoints.
Confirmed by scanning the tested CCI that its data was byte-correct, so the
corruption is definitely the renderer.

**5. Found, not fixed:** 42 accepted non-donor rows are actually French/Spanish
mislabelled `language=en` — see the dry-run doc §5. Translator's call.

**Known hotspot:** `mgs3d_codec_tool.py apply` calls `record.resources()` once per
unit, and each call re-decrypts the record's whole string region. Fine at 8,478
units, ~20 minutes at 201,482. Worth caching before propagation becomes routine.

## v0.82 plan recorded (2026-08-16) — superseded above

**Read [`docs/v0.82-plan-2026-08-16.md`](docs/v0.82-plan-2026-08-16.md).**
Its fitting priority no longer holds; its set-difference accounting and the
movie/demo budget-model defect do.

Accounting for 586 → 301 applied → 302 remaining, by set difference: **284
edited rows entered the build, 17 were edited but still fall short, 285 were
never edited. Zero rows were newly added and zero were reclassified.**

The 17 shortfalls share one cause: they were shortened to land exactly on the
budget the worklist showed, and the movie/demo encoder needs 1–2 bytes more than
the raw encoded length. **The worklist's movie/demo budget model is optimistic —
leave at least 2 bytes of slack until it is fixed.**

Also recorded there, so it is not repeated: the capacity report's record-level
`safe:false` flag does **not** mean a whole record is dropped. The build uses
`--max-safe-csv`, exclusion is per row, and excluded rows match deficient entries
one-for-one. Record-level aggregates must not be used to plan this work.

## v0.81 staged: final dialogue fitting, round 1 (2026-08-16)

**Read [`docs/v0.81-staging-2026-08-16.md`](docs/v0.81-staging-2026-08-16.md).**
Purpose: **final dialogue fitting**. No CCI built.

~~The English still on screen was never untranslated -- it was translated text
dropped for byte capacity.~~ **Wrong — corrected 2026-08-16, see the top of this
file.** 301 of the 586 worklist rows were filled and applied
(checker: PASS 301 / FAIL 0), giving:

| | v0.80 | v0.81 |
|---|---:|---:|
| codec units in build | 8,303 | **8,441** |
| codec units dropped | 175 | **37** |
| movie subtitles | 588 | **608** |
| demo subtitles | 1,919 | **2,045** |

Of the 301: **114 were not dialogue at all** -- GCX 13 is the encyclopedia index,
whose "translation" had replaced the `<80>` field separators with spaces and
corrupted an identifier; restoring `raw_text` fits to the byte. The other **187
are shortened dialogue that has not had a translator's read** and can be revised
in the same one-file loop.

Staged: `codec.dat` `80f78457…`, `movie.dat` `54bc9566…`, `demo.dat` `8612ec45…`.
978 files in the tree, exactly 3 changed, all sizes unchanged, HPK gate exit 0.
Glyph page, `code.bin`, `scenerio.gcx` and `cache.hpk` untouched this round.

**Worklist now 302 rows** (was 586): `translation/10_master/review/dialogue-worklist.csv`.
Loop is one file → `mgs3d_review_check.py` → `--apply` → rebuild.

**Open:** `억` renders corrupted right after a codec call ends. Data verified
clean end to end (map, token map, 931/931 bitmaps, 63/63 built units). That line
has exactly one global-page character and thirteen static ones, so the leading
hypothesis is a transient stale anchor at the codec→cutscene transition, not a
glyph defect. Same line exists at demo offsets `11537428` / `533694288` -- if it
reads fine when not reached straight after a codec call, that confirms it.

## v0.80 CONFIRMED ON HARDWARE; one-file dialogue worklist (2026-08-16)

**v0.80 works.** Anchor fix, 감/달 relocation and the approvals all verified on
real hardware. Korean now renders in codec conversations.

**Next work is in one place:** `translation/10_master/review/dialogue-worklist.csv`
— every line that still shows English, all three media in one file. See
[`translation/10_master/review/README.md`](translation/10_master/review/README.md).

The remaining English is **not untranslated** — it is translated text dropped for
byte capacity: demo 309 + codec 176 + movie 101 = **586 lines**. 543 are over
budget, median overage **3 bytes (2 Hangul)**, and 493 need ≤3 characters cut.

Workflow: fill `korean_new` → `python tools/mgs3d_review_check.py` →
`--apply` writes only the rows that fit into `current/*.csv`
(precondition-checked, masters backed up).

New tools: `mgs3d_dialogue_worklist.py`, `mgs3d_review_check.py`,
`mgs3d_codec_review_export.py`, `mgs3d_codec_safe_select.py`.

**Speaker data does not exist in the game.** `radio_picture` ids appear only in
the encyclopedia index; `20_matching/mgs3d_script_comparison.csv` has speakers
for 3,031 rows but is keyed to stale parser offsets (2,719/3,031 keys absent from
the master, text similarity ~0.10 on the rest). Speakers are therefore derived
from vocatives within each conversation — 176 of 586 rows, labelled
`vocative`/`mentioned` — and left blank rather than guessed elsewhere.

## v0.80 staged: approvals + 감/달 relocation + encoding cleanup (2026-08-16)

**Read [`docs/v0.80-staging-2026-08-16.md`](docs/v0.80-staging-2026-08-16.md).**

Three changes on top of the anchor fix below, all staged, **no CCI built**:

- **1,106 already-translated codec rows approved** (`accept=yes` 7,372 → 8,478).
  They were translated and QA'd but never approved, so they shipped as English.
  Capacity dry-run first: zero new failures. One row held back (gcx 724/14 needs
  `뱌`, absent from the page).
- **감/달 moved off their control-code tokens** — 달 `0x8309` → `0x87A5`,
  감 `0x8308` → `0x87A6`; verified in the built binary. See
  [`docs/gam-dal-control-code-fix-2026-08-15.md`](docs/gam-dal-control-code-fix-2026-08-15.md).
- **39 encoding-preflight failures fixed** (Spanish `¿`/`¡` residue, zero-width
  spaces, `<제목>` brackets, `×`, `·`). `coverage-report.json` is **PASS** for the
  first time — `all_authoring_text_encodes` had always been failing.

Build: **+1,257 codec lines** vs v0.69 (8,303 units vs 7,046). New tool
`tools/mgs3d_codec_safe_select.py` reconstructs the never-committed byte-capacity
safe-subset generator. All staged file sizes unchanged; HPK gate exit 0.

**Do not run `tools/mgs3d_clean_glyph_v1.py` against live staging** — it resets
every whitelisted partition0 file to the clean baseline first and would destroy
the staged `code.bin`, DATs and `cache.hpk`.

Codec translation is effectively complete: of the 1,094 rows without Korean,
803 are FR/ES donor residue, 90 internal identifiers, 90 short tokens, and only
~20-40 are real English (mostly PERSONAL DATA profile cards). Worklist:
`translation/10_master/review/codec-review-worklist.csv`.

## Korean base re-anchored, staged (2026-08-15)

**Read [`docs/korean-base-obj-snapshot-2026-08-15.md`](docs/korean-base-obj-snapshot-2026-08-15.md).**

Root cause is closed and the fix is staged. `table[2]` is a per-screen slot: in a
codec conversation the engine points it at the loaded **codec.dat** GCX record's
own glyph area (proved byte-exact: `table[2]` buffer == codec.dat offset
`0x78A77C`, 8192/8192), so `table[2]+0x56000` left the resident scenerio.gcx
buffer entirely. Option 2 (pointer cache/refresh) is therefore **dead** — the
data is not in that buffer at any offset.

The fix uses the engine's own per-object snapshot instead:
`obj = *(0x008E1618)` (single-writer global, writer `0x007801C4`), Korean base =
`obj[0x4C] + 0x56000`, with a NULL fallback to the old `table[2]` path. Verified
live during a failing conversation: `obj[0x4C]=0x08982744 != table[2]=0x15A278DC`
and `obj[0x4C]+0x56000` matched the staged page 64/64.

Only `korean_draw_1/2`'s `KOREAN_BASE` changed. All static gates PASS; staging
tree diff is exactly 2 files. New staged `code.bin`
`ea2bb144194cd5509ce5340715e4c003fee7bd65e49bf1c40f381efae4bee20c`, `exheader.bin`
`39bd66cdc9b90aefdf2ff997c6e71ac120c668de4c97f9f79a92920082f1d87d`; previous pair
archived to `Romforge\archive\pre-objsnapshot-20260815\`. **No CCI built** —
RomForge is GUI-only and is the repack step; see §5 of that doc.

## NEW — global-page blank-glyph bug ROOT-CAUSED at runtime (2026-08-15, latest)

**Read [`docs/global-page-render-path-audit-2026-08-15.md`](docs/global-page-render-path-audit-2026-08-15.md) first.**
Nothing was modified this session — no `code.bin`, no trampoline, no CCI, no
glyph-slot reassignment. Analysis and measurement only.

### What the bug actually is

Not "nine specific characters". **The entire 929-character global glyph page
renders blank in the codec screen while the 191 static characters render
correctly.** Proven live under Azahar+GDB:

| slot | boot | **codec (broken)** | **in-game (working)** |
|---|---|---|---|
| `table[0]` | `0x08688578` | `0x08688578` | `0x08688578` |
| `table[1]` | `0x087A973C` | `0x087A973C` | `0x087A973C` |
| **`table[2]`** | `0x08954BB4` | **`0x15A278DC`** | `0x08852520` |
| `table[4]` | `0x08964AB4` | `0x15A377DC` | `0x08862420` |

`table[4] == table[2] + 0xFF00` in every sample — the signature the setter at
`0x0010A894` writes only for index 2. So `table[2]` really is a **shared font
slot that seven different call sites reassign**, and the trampoline's
`korean_page_base = *(0x00A46FE0) + 0x56000` depends on it.

In the codec, `table[2]+0x56000` = `0x15A7D8DC` and that memory is **all
zeros** — the renderer is faithfully drawing a 64-byte run of zeros. In the
working context, `table[2]+0x56000` = `0x088A8520` and the 64 bytes there are
**byte-identical to the staged page**.

Natural experiment that confirms the split by eye: the codec save prompt
`게임을 저장하시겠습니까?` has exactly one global-page character — `임`
(`0x8422`) — and ten static ones. Only `임` is invisible.

### Conclusion on the fix formula

- **`table[0] + FIXED_OFFSET` is impossible.** `table[0]` is constant across all
  three samples but the page distance is not (`0x0032263C` / `0x0D3F5364` /
  `0x0021FFA8`). Structural: `table[0]` lives in the font archive (loaded once),
  the page lives in the per-stage `scenerio.gcx` buffer whose `page2_offset`
  ranges 49,872–369,396 across the 169 stages.
- **The `0x56000` offset is correct**; only the pointer is unreliable.
- Two candidate fixes, neither implemented — see the audit doc §7.
  Minimal: validate `table[2]+0x56000` against a known page signature and fall
  back to a private cached copy. Structural: relocate the glyphs into
  `table[0]`'s font page (a font page is `0xFF00` = 65,280 bytes, **exactly** the
  Korean page's size, and the engine already routes `0x84xx-0x87xx` there).

### Option 3 (relocate into `table[0]`'s font page) — probe prepared, not yet run

New evidence folder:
[`docs/evidence/2026-08-15-fontpage0-probe/`](docs/evidence/2026-08-15-fontpage0-probe/README.md).

- **Static result, done:** the pristine Western `codec/movie/demo.dat` reference
  **zero** page-0 tokens (`0x8401-0x87FF`, flag-normalized so `0xA4xx-0xA7xx`
  counts too). Page 2 is the only generic page retail dialogue uses (68 tokens,
  codec) — consistent with `table[2]` being a live shared slot. Caveat: those
  three DATs are dialogue only; UI/menu text was not scanned.
- **Runtime result — VERDICT: `table[0]`'s page is NOT free, Option 3 as framed
  is not supported.** Measured with `tools/mgs3d_fontpage0_probe.py` (read-only)
  across two independent Azahar launches at the title screen:
  - `table[5] == table[0]+0xFF00`, `table[6] == table[0]+0x1FE00` confirmed live;
    `table[0] = 0x08688578` reproduced.
  - **1005 of 1020 slots non-zero**, 946 distinct slot values, and the two
    captures are **byte-identical 65280/65280 across separate processes** — so it
    is deterministic asset content, not heap garbage.
  - It does not render as readable characters under any of ~40 searched layouts,
    but its glyph-coherence score under the renderer's own format (3.26 for slots
    0-199, 3.87 for 400-599) matches the staged Korean page (3.47), while the
    page tail (slots 800-999) scores 9.37 (noise).
  - The buffer region immediately *before* `table[0]` decodes into **legible
    Hangul** under that same format, proving the decoder is right and the
    surrounding buffer is a glyph store.
  - So roughly the first 600-790 slots hold real glyph-textured content that a
    wholesale replacement would destroy. Whether it is ever drawn is unproven;
    the burden is now on proving it dead.
  - Not run: `--registry` resolution of `0x6E383C45` (session ended first; it
    does not change the verdict). A `-data-read-memory-bytes` gotcha was also
    closed out — bulk 1024-byte reads were **verified** against 64-byte reads,
    so they are trustworthy on this stub after all.

### Two other results from the same audit

- **Yesterday's `korean_layout_classify` fix is a proven no-op** for every
  assigned character — see §3 of the audit doc. It is harmless and need not be
  reverted, but it does not fix anything and a CCI built to test it would test
  nothing. The `missing_glyphs` evidence that motivated it is also invalid:
  865 of the 1,120 assigned characters carry that flag.
- **New real defect, not fixed:** `감` (`0x8308`) and `달` (`0x8309`) collide
  with control-code tests in the layout engine (`0x00183D68`, `0x00183D70`, and
  three mirrors) and are consumed instead of drawn. Cheapest fix is reassigning
  those two characters to free global-page slots — data only, no code patch.
  Do **not** allocate `0x8100`, `0x81B0`, `0x825C`, `0x8301`, `0x831E` either.

### Environment left behind

Azahar (with the 2026-08-15 00:15 CCI) and the GDB daemon were still running at
handoff; close Azahar normally when done. `qt-config.ini` was restored to
`use_gdbstub=false` so the next launch boots normally instead of stalling for a
debugger.

## SUPERSEDED — `korean_layout_classify` renderer fix, staged (2026-08-15)

> Superseded the same day: the fix is a no-op (audit doc §3). The staging and
> tooling record below is still accurate; its *diagnosis* is not.

Root-caused and fixed the hardware "characters render blank" bug reported
live during v0.69 testing (듣/얼/마/임/백/업/외/워/팀 and more — 434 codec
rows carry the tell-tale stale `missing_glyphs` flag). **Not a translation
or data bug** — character-map, glyph bitmap page, built codec.dat bytes,
and all early-stage `scenerio.gcx` page-append content were all verified
correct. The bug is in the renderer patch itself: of the six trampoline
functions `tools/mgs3d_clean_glyph_v2.py` injects into `code.bin`,
`korean_layout_classify` (0x00183A04 → 0x0087FA80) never got the
`0x84xx-0x87xx` global-page range check that the other four (draw_1/2,
width_1/2) already have correctly — it only recognised the legacy
`0xA0xx-0xA3xx` range and fell through to a raw bic-mask fallback for every
global-page Hangul token, so layout/line-wrap logic never recognized them
as Korean even though draw/width could render them fine.

Fixed in `experiments/korean_eof_append_poc_2026-08-12/poc_trampolines.s`
(mirrors the already-correct pattern from the other four functions); new
tool `tools/mgs3d_layout_classify_fix.py` re-assembles and patches an
already-built V2 `code.bin` in place with strict verification (refuses an
unrecognized input hash, confirms the five other trampoline functions
decode identically except for one expected literal-pool relocation,
recompresses via 3dstool, verifies the round-trip). All 6 original branch
patch sites stayed byte-identical — this is a single-function, body-only
patch. Staged to `exefs/code.bin` + `exheader.bin` in RomForge (previous
files archived, not deleted, to
`Romforge\archive\pre-layout-classify-fix-20260815\`). **No CCI built.**
Full writeup, including the live-GDB confirmation attempt (unconditional
breakpoint hits proved the fallback path is reachable; conditional
breakpoints crash this GDB/stub combination — new recipe gotcha) and what's
still open:
[`docs/korean-layout-classify-fix-2026-08-15.md`](docs/korean-layout-classify-fix-2026-08-15.md).

## v0.69 re-staged with pending corrections (2026-08-14, latest)

Re-ran the full capacity recheck + rebuild + stage cycle after merging the 4
pending corrections into `current/`. One of them (demo offset 11537816,
"지금부터... 버추어스 미션을 개시한다.") is **2 bytes over its fixed slot** — kept
correct in `current/demo.csv`, but excluded from this build's derived safe
CSV (falls back to English on-screen for now) rather than reintroducing the
confirmed-wrong old line. The other 3 corrections (movie wordplay fix, demo
mis-mapping fix, codec SAVE-menu wording) build clean. Same verification
depth as before: 0 build errors, 0 layout/offset drift on all three `.dat`,
`audit-existing` gate clean. Full detail:
[`docs/v0.69-safe-staging-round2-2026-08-14.md`](docs/v0.69-safe-staging-round2-2026-08-14.md).
Round-1 staged files archived to
`Romforge\archive\pre-v0.69-safe-round2-20260814\`. **No CCI built.**

## pending corrections merged, history card staged (2026-08-14, earlier)

`translation/10_master/` was reorganized (by the user) into
`current/{codec,movie,demo}.csv` (single canonical) +
`pending/runtime-corrections.csv` (single correction point) — see
`translation/10_master/README.md`. Reviewed and merged 4 hardware-tested
corrections (movie/demo mistranslation + subtitle mis-mapping, codec SAVE
menu wording); regenerated `translation/40_build_input/global_page_v2` from
the new `current/` layout, fixing `tools/mgs3d_global_page_build_input.py`
which still referenced pre-reorg filenames. Also staged the (already-fixed
in v0.68 but never staged) history-card ETC1 fix — the user's hardware
report of "rainbow noise over English text" matches exactly the *original*
unfixed corruption, confirming the tested CCI predated this session's
staging. Full detail:
[`docs/v0.69-pending-corrections-and-history-fix-2026-08-14.md`](docs/v0.69-pending-corrections-and-history-fix-2026-08-14.md).

**Still open, not resolved:** 4 reported glyphs render as "x" on hardware
(듣/얼/마/임) despite verified-correct character-map data, token-map data,
and non-blank glyph bitmaps — root cause needs live debugging or a
per-stage page-completeness audit, both beyond static analysis. See that
doc's §3.

**Not re-staged:** RomForge's codec/movie/demo.dat still reflect the
pre-this-round `v0.69-safe` build; the 4 text corrections above exist in
`current/` but weren't rebuilt into a new staged `.dat` (wasn't asked for
this round).

## v0.69 safe staging (2026-08-14) — no CCI built

Staged a byte-capacity-safe codec/movie/demo build to
`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\`
(codec.dat, movie.dat, demo.dat only — `cache.hpk` untouched). **The user
does the CCI repack and hardware/Citra test**; nothing beyond staging was
done here.

Along the way, fixed two real, previously-live tool bugs (details below and
in the staging doc): the codec CSV→JSON converter was corrupting 7,369/7,372
accepted rows, and `mgs3d_build.py` never wired the global glyph page into
either the codec or the movie/demo build path. Both fixed in
`tools/mgs3d_script_compare.py` / `tools/mgs3d_build.py`.

Excluded from this round (masters untouched, exclusions live only in derived
`translation/40_build_input/v0.69-safe/*` copies): codec 329/7,372 accepted
rows (22 MUST_SHORTEN GCX + 44 REVIEW GCX, no donor reclaim applied + 33
pre-existing broken-token rows), movie 101/689, demo 308/2,228 — all by real
byte-capacity failure, verified against the actual build code end-to-end (0
errors, 0 layout drift, 0 offset drift on the resulting three `.dat` files).
Full detail, exact exclusion reasons, hashes, and reproduction commands:
[`docs/v0.69-safe-staging-2026-08-14.md`](docs/v0.69-safe-staging-2026-08-14.md).

Previously-staged `romfs/{codec,movie,demo}.dat` (dated 2026-08-13, not
re-verified by this task) were moved, not deleted, to
`C:\Users\hhlee\Desktop\Romforge\archive\pre-v0.69-safe-20260814\`.

## NEW — byte-capacity recheck vs. final natural translation (2026-08-14, analysis only)

Glyph scarcity is solved (see v0.68 below); this checks the *separate* real
byte/structural capacity of each GCX record (codec) / subtitle entry
(movie, demo) against the final, unshortened translation. **431 lines total
actually need shortening** (codec 22 GCX + movie 101 + demo 308) — versus
roughly 10x that many previously excluded/shortened under the old
glyph-diversity gate (1,500+ lines recover to natural-level translation:
codec 31, movie 341+3, demo 1,189+59). Full report, MUST_SHORTEN list, and
calculation basis (verified against the literal running build code):
[`docs/capacity-recheck-2026-08-14.md`](docs/capacity-recheck-2026-08-14.md).
No translation text or `.dat` file was touched.

**Also found while verifying that script against the real build code (not
fixed, needs a decision):** `mgs3d_build.py --codec-review`'s CSV→JSON
conversion step corrupts/crashes on 7,369 of 7,372 accepted codec rows —
unrelated to capacity, blocks any codec build via that path today. Details:
[`docs/codec-review-csv-escaping-bug-2026-08-14.md`](docs/codec-review-csv-escaping-bug-2026-08-14.md).

## v0.68 (2026-08-14) — QA pass, ETC1 history-card fix, glyph impact cleared

Full write-up: [`docs/v0.68-release-notes.md`](docs/v0.68-release-notes.md).

- **History card corruption is SOLVED.** BCLIM format 10 is **ETC1**, not the
  4-bit luminance image `mgs3d_history_texture.py` assumed — it wrote raw
  nibbles into a block-compressed slot. Format enum derived by measuring
  sibling BCLIMs (`black.bclim` was the control), storage rules confirmed by
  decoding the pristine English card back to its real sentence. New tools:
  `tools/mgs3d_bclim.py` (codec) and `tools/mgs3d_history_texture_v2.py`
  (rebuild, reusing the fixed padded-slot HPK rule). Verified end to end on a
  rebuilt archive; **not yet on hardware.**
- **Translation QA**: new `tools/mgs3d_translation_qa.py`. The handoff merge
  introduced **no regressions** (josa/pronoun/glyphcase regressions in merged
  rows: 0; control codes: 0 drift; new donor-rule violations: 0). Fixed 81 josa
  errors, 3 register clashes, 87 `당신` MT-residue rows. Remaining `당신` (41)
  are all in documented skip classes. movie/demo `당신` intentionally left —
  it is natural cutscene address, not MT residue.
- **Glyph impact cleared.** Applying the current text needed 10 syllables the
  1,120-slot page does not contain (9 introduced by direct-v2 work, 1
  pre-existing). Reworded those 10 lines instead of extending the page, so the
  existing verified glyph page covers everything: **0 missing, 29 slots free.**
  Total Korean text also shrank 3,735 characters.
- Still open and unchanged: `glyphcase` inconsistency (40 rows, needs a
  convention decision), 538 pre-existing donor-source rows carrying Korean from
  v1, and the pristine-HPK tail walk question.

## NEW — history-card glyph corruption on hardware (2026-08-14, analysis only)

**Hardware test of the packer-fixed build: crash is gone, but the opening
history card's Korean glyphs are all illegible/corrupted. Demo and other
Korean text display normally. `codec.dat` is excluded (still mid-translation,
unrelated to rendering). Not fixed — documentation and analysis only, by
instruction.**

Full analysis, evidence images and extracted BCLIM members:
[`docs/evidence/2026-08-14-history-texture-corruption/README.md`](docs/evidence/2026-08-14-history-texture-corruption/README.md).

This is a **second, independent defect** from the HPK cursor-drift crash below
— it is about pixel-data correctness inside one texture, not archive-chain
integrity, and the crash fix is unaffected and now hardware-confirmed working.
Summary:

- The user's hardware build used
  `builds/current/mgs3d-v065-hpk-cursor-fix/romfs/stage/v000a_0/cache.hpk`,
  confirmed sha256 `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`
  — the corrected archive from the RESOLVED section below. **No Data Abort.**
  That is the first hardware confirmation the cursor-drift fix works.
- `tools/mgs3d_history_texture.py`'s pixel-layout model
  (`encode_l4_bclim`/`decode_a4_bclim`: 8x8 Morton tiling, stride = declared
  width 400, 4 bits/pixel) is demonstrably wrong for this asset. Proof:
  decoding the **pristine, untouched, hardware-correct** English texture
  through this exact code produces illegible noise, under every layout
  variant tried (stride 400, stride 512, linear, linear+vflip,
  tiled+byteswap — five hypotheses, all failed).
- The payload is 16,384 bytes for a 64-row, 4bpp image, which implies 512
  texels/row, not the 400 the tool assumes — but stride 512 alone doesn't fix
  the decode either, so the defect is not simply "the width constant is
  wrong."
- The tool's own decode of its own encode looks legible — that is a false
  positive: encode and decode share the same wrong formula, so they agree
  with each other while both disagreeing with the real hardware layout.
  `wiki/History/version-0.65.md` already flagged this exact path as
  hardware-unvalidated before this session; this test is the first time it was
  actually checked, and it failed.
- The Morton/Z-order primitive itself is not the suspect — an identical
  formula is validated working elsewhere (`tools/mgs3d_gcx_font_tool.py:34-39`,
  a different 2bpp/16x16 glyph asset). The bug is specific to this L4/A4
  400x64 asset's stride/format assumptions.

**Next step (not performed):** get a hardware/emulator texture-dump ground
truth for the pristine English member (not a LayeredFS substitute image) to
read the real layout directly instead of guessing further, then re-derive
`encode_l4_bclim` from that. Full detail in the linked evidence doc.

## RESOLVED — hardware Data Abort / HPK cursor drift (2026-08-14)

**Root cause found and reproduced. Hardware-confirmed fixed (see the section
above): the corrected archive produced no Data Abort.**

Full evidence, decoded dump, disassembly and reproduction:
[`docs/evidence/2026-08-14-hpk-cursor-drift/README.md`](docs/evidence/2026-08-14-hpk-cursor-drift/README.md).
The hardware dump is committed at
`docs/evidence/2026-08-14-hpk-cursor-drift/hardware-crash-v2.dmp`
(sha256 `2840ad54c2239aa556775a2e6743db4c762b4ea3ac11f2689f69ac68ee9d0115`).

### Root cause

`tools/mgs3d_history_texture.py:105-107` rewrites the HPK header's `packed`
field to the **new, smaller** compressed length while zero-padding the physical
slot back to the **old** length:

```python
struct.pack_into("<II", hpk, offset + 4, len(patched_darc), len(packed))
hpk[start:start + old_packed_size] = packed.ljust(old_packed_size, b"\0")
```

The retail loader is strictly sequential — `pos += 12 + packed`, no seeks, no
offset table — so keeping offsets fixed *physically* does not keep them fixed
*logically*. From the patched entry onward the loader runs `old - new` bytes
early, walks the zero padding as empty 12-byte headers, and finally reads a
header straddling the last `(old - new) mod 12` padding bytes.

For v0.65 the affected entry is **entry 31, key `309d745f`** — the Cold War
history texture, the one entry that patch touches. `old_packed_size = 3884`,
`new_packed_size = 3146`, so the slot carries **738 bytes of zero padding**.

A header whose `packed` field is 0 still consumes its 12 bytes and is otherwise
skipped (`0x0014F024` → `0x0014F0BC`), so the loader eats the padding as empty
12-byte headers:

```
738 = 12 × 61 + 6
```

61 empty headers, then 6 bytes left over. The loader therefore reads entry 32's
header **6 bytes early**, from `0x494951` instead of `0x494957`, and decodes
`packed = 0x03A00EB1` (60.8 MiB). That allocation fails and returns NULL, the
NULL is not checked, and a memcpy writes to address 0 → Data Abort.

Reproduction is exact: re-running the patch on the clean archive yields sha256
`4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`, the
recorded v0.65 HPK hash, and reproduces the identical bad header offset and
`0x03A00EB1` value. No font size in the usable range yields zero padding, so
**every** archive this tool has produced is affected.

### Corrected crash facts

| | recorded 2026-08-13 | actual (dump) |
|---|---|---|
| PC | `0x00183A4C` | **`0x0018344C`** (`stmia r0!, {r3,r12}`, `r0=0`) |
| LR | `0x00165168` | **`0x00165160`** (return of `bl memcpy` at `0x0016515C`) |

`DFSR=0x805` (write, section translation fault), `FAR=0`, `r6=r8=0x03A00EB1`.
The 96-byte code dump matches the V2 build byte-for-byte at `0x001833F0`.

### Retired hypotheses — withdrawn as causes of this crash, do not resume

All five are ruled out for **this** Data Abort. None of them is re-opened by
anything in this section.

1. **`scenerio.gcx` +399 KB causing RAM exhaustion.** Not the cause. The
   oversized allocation is `0x03A00EB1` (60.8 MiB), read directly out of a
   misparsed HPK header; it has no relation to the 399 KB appended to
   `scenerio.gcx`.
2. **The Korean glyph page itself.** Not the cause. The appended page at
   `0x622DC` matches `korean_page_full.bin` and is never touched on the faulting
   path.
3. **V2 trampoline / text pointer.** Not the cause. The branch word at
   `0x00183A04` → `0x0087FA80` is intact. The 2026-08-13 "invalid text pointer
   in the trampoline path" assessment rested on the misread PC `0x00183A4C` and
   is withdrawn.
4. **Alignment.** Not the cause. HPK entries are tightly packed at arbitrary
   (often odd) offsets by design; entry 31's header sits at `0x493A1F` and the
   chain is byte-exact. No alignment rule is violated.
5. **HPK loader header/cursor arithmetic error.** Not the cause. The loader is
   correct: `0x0014F00C` always requests 12, `0x00165110` advances
   `[stream+0x0C]` by exactly the bytes copied, and all four read paths in
   `0x00164774` consume exactly `packed`. The only sub-request advance is the
   EOF path (`0x001651A4`), which did not apply. **The cursor never lost 6
   bytes — the archive handed the loader a size that disagreed with its own
   physical layout.**

Two further notes:

- The requested dynamic Azahar/GDB cursor observation is **complete/unnecessary**
  — the hardware dump already contained the value it was meant to capture
  (`[stream+0x0C] = 0x1495D` → absolute `0x49495D`). Do not restart that session.
- The `0x001648DC` missing NULL check is **not** the fix. Recorded as a
  diagnostic-only candidate: adding it would convert the crash into silent
  asset loss and hide the real defect. Do not apply it as a solution.

### Packer fix — DONE (2026-08-14)

`tools/mgs3d_history_texture.py` now leaves the entry header untouched and pads
the zlib stream back up to the original `packed_size`, matching the pattern in
`tools/mgs3d_hpk_static_korean.py:120-125`. The logical chain and the physical
layout agree again. Two self-checks were added that abort the patch if the
header ever changes or if the padded slot fails to decompress, plus a comment
naming this crash so the size field is not "optimised" back in.

The fix was verified by building a corrected archive from the clean source. That
archive was **not** left staged — build preparation is the user's step. Rebuild
it during build prep with the tool's normal entry point, using the clean
`cache.hpk` as source and `malgun.ttf` size 12:

- expected sha256 `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`
- expected size 6,453,287 bytes (unchanged from the clean archive)
- for reference, the defective build was `49447057…`; anything producing that
  hash again means the fix was lost

Verification performed on that build:

- Header at `0x493A1F` byte-identical to the clean archive
  (`key 309d745f`, unpacked 18856, packed 3884); file size unchanged.
- Every byte outside entry 31's payload slot byte-identical to the clean archive.
- Slot decompresses to 18856 bytes; the DARC keeps all 7 members with an
  identical member table, and exactly one member's bytes differ —
  `timg/cold_war_text_eng_alp_ovl.bclim`, the intended target.
- `tools/mgs3d_hpk_chain_check.py` exits 0, and `--reference` against the clean
  archive reports all 133 walked entries identical.
- The defective `49447057…` archive is **not present anywhere on this machine**;
  nothing on disk needs to be purged.

Residual assumption: the game's inflate ignores the 738 trailing zero bytes in
the slot. This is standard zlib behaviour and is the same assumption
`mgs3d_hpk_static_korean.py` has always relied on, but it has not been
re-confirmed on hardware for this specific entry.

### Second hardware crash (Luma dump 00000002) — same defect, fix was not in the build

A second physical crash was captured after the packer fix landed in the
repository. It is **not a new failure**: the dump differs from the first in 8
bytes total (`fpinst`/`fpinst2` dead FPU state and two stack bytes). Every
meaningful value is identical, including the stream state
(`cursor=0x1495D`, absolute `0x49495D`) and `r6=r8=0x03A00EB1`.

That cursor is only reachable from an archive whose entry 31 declares a short
`packed` size, so the CCI that crashed **still contained the defective
`cache.hpk`**. The fix was never in that build — most likely the previously
staged archive was reused rather than regenerated.

**Trap to avoid:** the corrected archive is the *same size* as the defective one
(6,453,287 bytes). Size cannot tell them apart. Compare SHA-256 or run the gate.

| archive | sha256 |
|---|---|
| defective | `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d` |
| corrected | `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc` |

### Crash-fix hardware validation — DONE

The corrected `cache.hpk` (`d46373e1...`) was built, staged at the canonical
RomForge path, packed into a CCI, and tested on real hardware: **no Data
Abort.** This closes out the cursor-drift crash end to end. What remains open
from that work is only the low-priority pristine-HPK-tail TODO below, which
was already known not to block anything.

### Next task — top priority

**Investigate the history-card glyph corruption** found by that same hardware
test — see the `NEW` section at the top of this file and
[`docs/evidence/2026-08-14-history-texture-corruption/README.md`](docs/evidence/2026-08-14-history-texture-corruption/README.md).
Per instruction this session was documentation/analysis only; the actual fix
has not been attempted. Recommended starting point: get a hardware/emulator
texture-dump ground truth for the pristine English member instead of guessing
more layout variants (five were already tried and failed).

No CCI has been built and no game binary has been modified as part of *this*
history-texture investigation.

### Low-priority TODO — pristine HPK tail is not fully modelled

Recorded, deliberately not investigated:

- The pristine retail `cache.hpk` is **also** not fully walkable to EOF under
  the current sequential HPK model. The walk stops around key `3e6af67a`, whose
  `packed` field reads `0xbf1d1192`.
- So there is a later archive structure that `tools/mgs3d_hpk_chain_check.py`
  does not yet explain.
- It occurs in the **unmodified retail file**, so it is not connected to the
  Korean patch work and not connected to this crash.
- It is a separate problem from the entry 31 (`309d745f`) → entry 32 failure
  documented above.
- It does **not** block the packer fix or the rebuild.
- Do not investigate it now.
- `mgs3d_hpk_chain_check.py` must keep reporting this tail condition as a
  **NOTE, not a FAIL** — otherwise the gate would reject known-good archives.
  Only the padded-slot signature is a FAIL.

### Canonical RomForge staging correction (2026-08-14)

The only canonical RomForge output root is:

`C:\Users\hhlee\Desktop\Romforge\output`

Do not use `C:\Users\hhlee\Desktop\metagear3d\romforge\output`. That parallel
tree caused the corrected HPK to be staged in one location while a CCI was
packed from another. The repeated hardware crash was a build-lineage failure,
not a new crash mechanism.

Current canonical staging file:

`C:\Users\hhlee\Desktop\Romforge\output\unpacked\partition0\romfs\stage\v000a_0\cache.hpk`

- SHA-256: `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`
- chain checker: exit 0, `OK: no padded-slot drift` (the known pristine-tail
  condition remains a NOTE)

Before the next CCI is created, re-run the chain checker and SHA-256 on that
exact path. After creation, extract the CCI and verify that its internal
`stage/v000a_0/cache.hpk` has the same corrected SHA-256. Do not promote to
v0.67 until the hardware result is reported.

Output cleanup: only `unpacked/` remains directly under the canonical output
root. Other backup/experiment folders were moved without deletion to
`C:\Users\hhlee\Desktop\Romforge\archive\output-20260814`. The
seven-underscore CCI was extracted and identified as the controlled
`ABC 호프번 XYZ` probe, not the golden build, and moved to
`output-20260814\cci-abc-hofbeon-probe`.

The canonical unpacked tree is now the v0.67 hardware candidate staging:

- V2 `code.bin`: `8c542191bdc62dffbd851d730dac14bc4dcf14208e54b4d15dbd409c885da7d0`
- V2 exheader: `2268b757185418b3c2c334048fc6b8bbdfcc9508786e06c126707b12522ce1ab`
- v0.65 `codec.dat`: `86cc8e12504e517fd0916de95e3f7a46b7f00b9c6859c28338d187334493c524`
- v0.65 `movie.dat`: `0f7e4c961ca4d10c19a46a7076ca0155a0531ed8b10f1a54b62d382a957945dd`
- probe-free `v000a_0/scenerio.gcx`:
  `badca5afc7e1a372b43cf1d60366732d229d3623f92ce1d525ddd8a097f0354d`
- corrected `v000a_0/cache.hpk`:
  `d46373e1c042c37d9a76fa221dee4d79381c6b8cc31e9e9d535f98c43491dacc`

## movie/demo autonomous batch cleanup (2026-08-14) — converged, done

User stepped out and asked for autonomous batch processing ("외출할거니 일괄
처리해둬"). Ran the contamination hunt to convergence using three methods
(length-ratio z-score at progressively lower thresholds, duplicate-korean-text
scan, and manual context reads of everything adjacent to a confirmed defect),
verifying every candidate against context before fixing, same precondition-
check-then-apply discipline as before.

- **movie: confirmed fully clean.** Re-scanned down to `|z|≥2.0` (37
  candidates) — 0 additional real defects; all were legitimate EN→KO
  word-order splits or natural short-answer expansion. No more edits needed.
- **demo: 46 more rows fixed this session** (3 from a duplicate-text re-scan,
  24 from a `2.0≤|z|<3.0` sweep, 19 from tracing what that sweep's
  re-verification surfaced) — cumulative **115 demo rows fixed today**
  across all rounds. `|z|≥3.0` still reports 55 candidates, but the top ones
  are all reverified as correct; diminishing returns reached (variance keeps
  shrinking each round, so previously-normal rows keep looking like new
  outliers). Judgment call: stopped here rather than chasing an
  ever-lower threshold.
- Full tables and the explicit stopping-point reasoning:
  `translation/10_master/movie-demo-batch-cleanup-2026-08-14.md`.
- Final hashes: `movie_natural_full.csv`
  `a022c716c9b4c047c3c19505e2ba54e328479a233c63aa45a816bc9ee15b4da9`
  (unchanged this session), `demo_natural_full.csv`
  `d386d0b189234ccea8d9dfb1083c005691307d6b66301916f81c12f769a4326e`.
- **Caveat that still stands**: this method catches "a whole other scene's
  line landed here" contamination, not subtler mistranslation/register issues
  of similar length. Don't read "converged" as "movie/demo translation is
  fully verified" — only that this specific contamination pattern is
  exhausted to the point of steep diminishing returns.

## movie/demo full trace-and-fix (2026-08-14) — done, 70 rows fixed total

Follow-up to the light audit below, per explicit instruction ("수정해줘" →
"하나씩 추적 수정" — fix them, tracing each one individually). All 75
candidates from the light audit (movie 7 + demo 75, movie's first 3 clusters
already fixed there) were traced one at a time against surrounding rows before
touching anything.

- **movie: 5/7 remaining candidates were false positives** (legitimate EN→KO
  word-order reordering split across two subtitle cards, not contamination).
  2 were real and fixed (`1590`, `1600`).
- **demo: 17/75 were false positives**, same reordering pattern or a
  proper-noun the checker's name list didn't recognize. **58 were real
  contamination** (korean holding a different scene's dialogue entirely) —
  fixed, plus 4 more cells in the same off-by-one shift chains that weren't
  individually flagged but were clearly part of the confirmed defect (verified
  the same way movie's rec-92 cluster was: two demo copies of that exact scene,
  rec 275 and rec 305, had the identical shift). 62 demo cells changed total.
- Every change was precondition-checked (script aborts if the file's current
  value doesn't match what was traced) before writing, and structurally
  verified after (0 non-korean-column diffs, row counts unchanged).
- Full before/after tables and confidence caveats:
  `translation/10_master/movie-demo-full-trace-fix-2026-08-14.md`.
- **Round 2 (same session, user said "다음"):** 7 more contaminated cells
  noticed by eye while reading context (not from a systematic rescan) — demo
  idx 2759, 3026, 3031, 5196, 6856, 8847, 8852 — traced and fixed the same way.
  demo final sha256 `d1336a1857c7ebfcb9a34b34a83f709eec0f9082bd93af01d0c2c49c5371a523`.
  These were spotted incidentally, not via a full rescan, so more of the same
  contamination likely remains undiscovered in movie/demo.

## movie/demo full light audit (2026-08-14) — movie fixed, demo scoped out

Full statistical scan (length-ratio z-score + missing-proper-noun heuristics)
across all 2,917 movie+demo rows, per user request ("전체 검수, 비교적 가볍게").
Confirms the cross-scene contamination flagged below is **not isolated** — it's
a real pattern with many instances, concentrated far more heavily in demo.dat.

- **movie: 3 cascading off-by-one shift clusters found and fixed (8 rows)** —
  traced each to its correct row using neighbouring content as ground truth,
  pre-condition-checked before writing, verified 0 non-korean-column diffs.
  4 more length-outliers checked and confirmed benign (natural EN→KO
  expansion, not contamination). 7 additional suspects found via the
  missing-proper-noun heuristic are **not yet traced/fixed** (8 others in that
  list were false positives — Khrushchev already correctly rendered as
  흐루쇼프/후르시쵸프, just missing from the checker's name dictionary).
- **demo: 27 length-outliers + 48 proper-noun-mismatch found, none fixed.**
  Confirms the two clusters found last session (rec 228-229, rec 235-236) are
  part of this same wider pattern, not separate incidents. Scale is
  meaningfully larger than movie's — tracing each would mean redoing what was
  just done for the movie clusters, dozens of times over, which exceeds
  "가볍게". Left for a scoped decision: trace-and-fix row by row like movie, or
  treat as a matching/alignment-algorithm problem to be rerun.

Full detail, tables, and the exact top demo examples:
`translation/10_master/movie-demo-light-audit-2026-08-14.md`.

## movie/demo remaining untranslated text (2026-08-14) — done, one issue flagged

Scanned `translation/10_master/bundle_natural_full/{movie,demo}_natural_full.csv`
(the movie/demo translation authority per `wiki/Translation.md`) for cells with
no Hangul at all. Most hits were correctly-English proper nouns (Snake, Boss,
EVA, Ocelot, C3...); 16 were genuine blank/placeholder defects (`.`/`...`/`!`
with the real content missing). **15 fixed directly in `demo_natural_full.csv`**
(structural diff clean: exactly 15 `korean` cells changed, no other column
touched). 1 (`movie_natural_full.csv` idx 1024) left alone — its content is
already fully present in the previous card (`idx=1019`) due to EN/KO word-order
reordering; filling it would duplicate "일주일 전". Full detail, before/after
table and reasoning: `translation/10_master/movie-demo-untranslated-2026-08-14.md`.

**Bigger issue found, not fixed, out of this task's scope:** several rows have
a `korean` value that belongs to a *different, unrelated scene* than their own
`raw_text` (not blank — wrong content). Example: demo idx 7572/7591/7601/7746/
7756/7766, movie idx 1034/1044. This looks like a 3-way alignment/matching
defect, not a missing-translation gap, and is potentially large in scope
(not yet measured). See the "별도로 발견한, 더 큰 문제" section in the doc above.

## direct-v2 Translation Quality Pass (2026-08-14)

Separate track from the glyph/hardware work below — codec.dat Korean
meaning/register quality pass, ignores byte/glyph capacity entirely (that's a
later stage). **Read `translation/10_master/direct-v2-RESUME.md` first**, not
this section, for exact resume steps; this is just a pointer.

- Batches 1-10 applied, **335/22,362 rows fixed**. Batches 1-7 (217 rows)
  were independently re-verified this session (structural diff clean, 7-entry
  changelog spot-check matched byte-for-byte).
- `direct-v2-worklist.json` (defect list) was stale and has been regenerated;
  its generator script (`worklist_build.py`) was lost from an old scratchpad —
  rewrite and commit it under `tools/` or `translation/10_master/` next time,
  don't leave it in a scratchpad again.
- **D2_missing (737 rows) is split into its own pre-processing track by user
  directive** — badly contaminated with mistagged Spanish/French donor text
  (GCX 443's entire D2_missing bucket, 49 rows, turned out to be 0% English).
  Needs GCX-level EN/FR/ES/DE/IT/unknown classification before any
  `D2_missing_en` translation starts; that classification hasn't begun.
- **Handoff file merged back — done (2026-08-14).** The full handoff CSV
  (`translation/10_master/direct-v2-FULL-HANDOFF.csv`, 1,528 data rows) came
  back with `final_korean` filled for 795 rows. **Important:** per that file's
  own `direct-v2-RESUME.md` trail, it was filled by an AI session running in a
  *different* environment (no access to this repo's v1/v2 CSV), not by an
  external human translator — that session did the fill plus three self-QA
  passes (register recheck, re-reading the 318 "no defect" D6_mix rows that
  had only been ending-checked and finding 14 more real mistranslations there,
  and a josa/particle consistency sweep after English proper nouns). This
  session verified rather than trusted that record: cross-checked specific
  logged fixes against the merged file and re-ran the known-bad-josa-pattern
  search against the 795 merged rows (0 hits; 16 remain elsewhere in the
  22,362-row file, outside this merge's scope).
  Merged into `codec-3ds-INTEGRATED-review-direct-v2.csv`: 507 rows actually
  changed, 288 rows confirmed by the translator as not actually defective
  (concentrated in D6_mix, matching the already-documented over-detection
  issue). D6_mix (487) and D3_abbrev (46) are now **fully resolved**.
  D2_missing's required GCX-level language classification is also done — all
  734 rows were individually read; 693 confirmed non-English (excluded for
  good) and 41 translated. Structural diff clean (row count/columns/keys
  unchanged, 0 non-korean-column diffs). Full tables:
  `translation/10_master/direct-v2-batch11-15-changelog.md`.
- **Remaining**: D4_mt_other (3 rows), broken_english (37, needs context
  restoration, not translation), and 16 stray josa errors found outside this
  merge's scope (locations in the changelog).

## Hardware crash investigation handoff (2026-08-13) — SUPERSEDED

> **Superseded 2026-08-14 by the RESOLVED section at the top of this file.**
> Its `PC=0x00183A4C` / `LR=0x00165168` are misreadings of `0x0018344C` /
> `0x00165160`, and its "primary suspect: Korean trampoline text pointer"
> assessment is withdrawn. The build-lineage hashes below are still correct and
> still useful, with one correction: the noted absence of the v0.65 HPK hash
> from `.tmp/cci-831-verify` is not a stray "build-lineage mismatch" — the
> crashed hardware CCI carried V2 `code.bin` **together with** the v0.65
> `cache.hpk` (`49447057…`), which is precisely the archive that crashes.
> `.tmp/cci-831-verify` is a different extraction that pairs V2 code with the
> clean HPK. Retained below for the hash record only.

Original 2026-08-13 text follows.

Hardware crash dump evidence:

- stage resource string: `stage/v000a_0/cache.hpk`
- stage identifier: `v000a_0`
- `PC=0x00183A4C` *(incorrect; actual `0x0018344C`)*
- `LR=0x00165168` *(incorrect; actual `0x00165160`)*

Read-only investigation result (no fix applied):

- The crashed CCI's ExeFS lineage is now exact. Extracting the `.code` member
  directly from `.tmp/cci-831-verify/exefs.bin` produced 5,264,416 bytes,
  SHA-256 `8c542191bdc62dffbd851d730dac14bc4dcf14208e54b4d15dbd409c885da7d0`.
  It is byte-identical to
  `experiments/2026-08-13-clean-glyph-baseline/V2-code.bin`; its decompressed
  SHA-256 is `105c8a1575dd3c0a65dc89ac6e81aa7e3eb9710f1c9449a00894cfb32cbc5ffa`.
  The CCI exheader is likewise the recorded V2 exheader (SHA-256
  `2268b757185418b3c2c334048fc6b8bbdfcc9508786e06c126707b12522ce1ab`,
  text size `0x77FABC`). All six patch words and the 504-byte trampoline hash
  `7298c10440b09e04aff1a705c1c85c0ce6895ee8ba7db4074ce4c2d1bfe4607d`
  match `V2-build-manifest.json` exactly.
- Do not use the current RomForge staging `code.bin` to interpret this crash.
  It is a later, different build: 5,264,412 bytes, SHA-256
  `de35b86eb0f6e8ef72b87faee567fb4f6aae5560307d57ae282cdf60b45f7308`,
  decompressed SHA-256
  `b2ab3030e0eb4fc3f912187a73ddf90fdf83def4bc696a116de3083a6eb35a8f`.
  Its six branch words target a different 456-byte trampoline layout and its
  exheader text size is `0x77FA8C`.
- The current extracted build at `.tmp/cci-831-verify` has a `v000a_0/cache.hpk`
  that is byte-identical to the clean glyph source: size `6,453,287`, SHA-256
  `145a82e9acba662afb024baadd0a25ec1eabca2c1006be26eb5891670561bbc0`.
  All 147 verified zlib entries have identical key order, offsets,
  packed/unpacked sizes, decompressed hashes, gaps, and effective alignment.
- `data.cnf` is unchanged. Within `v000a_0`, the localization build changed
  `scenerio.gcx`:
  - clean: 68,829 bytes, SHA-256
    `c126d93f3437715d5b834962e9e02d0d067061066202a679e2397310874aa420`
  - current: 467,420 bytes, SHA-256
    `badca5afc7e1a372b43cf1d60366732d229d3623f92ce1d525ddd8a097f0354d`
  - its original 68,829-byte prefix is intact;
  - the 65,280-byte Korean page begins at offset `402,140` (`0x622DC`) and
    matches `glyph/pages/global_korean_page_v2/korean_page_full.bin`;
  - recorded address formula: `49,884 + 0x56000 = 402,140`.
- `PC=0x00183A4C` is `ldrhhs r0, [r4]` in the text/layout decoder. A fault there
  indicates an invalid/unreadable text pointer in `r4`, not an HPK table read.
- The same function was directly modified by the Korean renderer patch at
  `0x00183A04`: the original `bic r1,r1,#0x6000` branches to the Korean token
  classifier trampoline at `0x0087FA80`. The code/scenerio glyph path is thus
  substantially more relevant than `cache.hpk`.
- `LR=0x00165168` lies in a buffer-copy loop following a call to the memcpy-like
  routine at `0x001833FC`; it does not identify an HPK loader. Do not treat the
  live LR as a reliable caller without stack unwind evidence.
- The documented v0.65 Cold War HPK hash
  `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`
  is not present in `.tmp/cci-831-verify`. Reproducing that patch changes only
  HPK key `309d745f`, keeps every entry offset fixed, and produces the recorded
  hash. This is a build-lineage mismatch, not evidence of current HPK damage.

Current assessment *(withdrawn 2026-08-14 — see the RESOLVED section)*:

1. ~~Primary suspect: invalid text pointer or pointer-advance/classification
   interaction in the `0x00183A04` Korean trampoline path.~~ Wrong; the
   trampoline is intact and uninvolved.
2. ~~Closely related changed resource: `stage/v000a_0/scenerio.gcx`.~~ Not
   involved in this crash.
3. ~~Low-priority suspect: current `cache.hpk`.~~ This was in fact the cause —
   but the v0.65 patched archive, not the clean one that was compared.
4. ~~Root cause is not proven because the full register set, fault address, and
   stack unwind were unavailable.~~ They were available all along, inside the
   crash dump; it had simply not been decoded.

Next read-only checks *(all closed 2026-08-14)*:

1. Closed: the full register set, `FAR=0`, `DFSR=0x805` and the 960-byte stack
   were decoded from the dump. `r4` is the stream object on the stack, not a
   text pointer.
2. Closed: the crashed CCI is the recorded V2 code and exheader.
3. Closed: the live LR is `0x00165160`, the return of the `bl memcpy` at
   `0x0016515C`; no unwind was needed.
4. Closed: neither `code.bin` nor `scenerio.gcx` is implicated, so no isolation
   build is required.

## Version 0.65 Handoff (2026-08-13)

Version 0.65 is committed and pushed as `fee6d82`, tagged `v0.65`. The local
RomForge `output/unpacked` staging tree is ready to repack for hardware testing;
the CCI itself has intentionally not been built yet.

Changes already present in RomForge staging:

- The opening Cold War history card is patched natively in
  `stage/v000a_0/cache.hpk`, not in `demo.dat`. Its resource chain is HPK key
  `309d745f` -> DARC -> `timg/cold_war_text_eng_alp_ovl.bclim` (400x64 L4).
  A Citra custom-texture probe confirmed the correct screen. The native BCLIM
  still needs hardware validation.
- The first briefing's duplicated Jack subtitle slots now read
  `버추(가상)미션?`; both remain inside their original 20-byte capacities.
  Existing normalization already corrected three `버츄어스 미션` occurrences
  to `버추어스 미션`.
- Corrupted GCX 13 was confirmed to be the 264-entry internal encyclopedia
  index, not dialogue. The entire same-offset/same-size record was restored
  byte-for-byte from the pristine Western codec (`0x1C50`, 24,864 bytes).

Prepared staging hashes:

- `codec.dat`: `86cc8e12504e517fd0916de95e3f7a46b7f00b9c6859c28338d187334493c524`
- `movie.dat`: `0f7e4c961ca4d10c19a46a7076ca0155a0531ed8b10f1a54b62d382a957945dd`
- `stage/v000a_0/cache.hpk`: `4944705794712ed6d7ea2518d1a394d02abcd9933083843f5054ca2dfd9cf87d`
  — **DEFECTIVE, do not ship.** This is the archive that causes the hardware
  Data Abort (738 bytes of zero padding in entry 31). Must be rebuilt after the
  packer fix; see the RESOLVED section at the top.

Validation completed: `codec.dat` parses as 2,326 GCX records / 601,657
resources; `movie.dat` round-trips byte-identically; the patched HPK zlib entry
decompresses and inventories correctly; all 140 unit tests pass (two Windows
temporary-directory ACL failures were rerun successfully with permission).

Next session:

1. Repack the already-prepared RomForge staging tree as the v0.65 CCI.
2. Test on hardware with no Citra custom-texture dependency.
3. Verify the opening history card first, then the first briefing wording.
4. Smoke-test the codec encyclopedia/radio-picture area affected by GCX 13.

Reproduction tools and detailed record:

- `tools/mgs3d_history_texture.py` — **contains the padded-slot defect**
- `tools/mgs3d_hpk_chain_check.py` — gate that detects it
- `tools/mgs3d_hpk_inventory.py`
- `tools/mgs3d_v065_media_fix.py`
- `tools/mgs3d_restore_gcx.py`
- [Version 0.65 checkpoint](wiki/History/version-0.65.md)

## Current Goal

Continue canonical translation integration using the append-only 929-character
global map plus the exact 191-character shared-static allocation.

## V2 HPK Cursor Drift Investigation (2026-08-14) — CLOSED

> **Closed the same day. See the RESOLVED section at the top of this file.**
> Every confirmed observation below held up, including the six-byte drift and
> the `0x00494951` header offset. The open question — where the cursor lost six
> bytes — is answered: it did not. The header read always consumes 12, and
> `0x00165110` has no under-advance path outside EOF. The six bytes are the
> residue (`738 mod 12`) of zero padding written into entry 31's slot by
> `tools/mgs3d_history_texture.py`, which the loader consumed as 61 empty
> headers. The three requested dynamic observations are moot; the dump already
> held the cursor value. Retained below for the static-analysis record.

Scope is the initial V2 crash build only. Its `code.bin` SHA-256 is
`8C542191BDC62DFFBD851D730DAC14BC4DCF14208E54B4D15DBD409C885DA7D0`
(504-byte trampoline; six V2-manifest patches). Do not substitute the current
RomForge `DE35B86E...7308` build.

Confirmed from the hardware dump:

- The physical 3DS produced the `PC=0x0018344C` Data Abort (`FAR=0`). This is
  not an Azahar crash or emulator result.
- That hardware Data Abort ultimately parsed the next HPK header from absolute offset
  `0x00494951`; the 12 bytes there decode the third word as `0x03A00EB1`.
- The valid next header starts at `0x00494957`, exactly six bytes later, and is
  `f642b10e a0030000 5a010000`.
- The resulting `0x03A00EB1` allocation request is downstream evidence of the
  misaligned header, not the current root-cause target.
- Previous entry 31 is key `309d745f`, header offset `0x00493A1F`, unpacked
  size `0x49A8`, and packed size `0x0F2C`. Its zlib stream consumes all 3884
  packed bytes; do not re-investigate zlib consumption.

Static initial-V2 loader path:

- `0x0014F018 -> 0x00165110` reads the complete 12-byte HPK header.
- `0x0014F02C` loads `packed_size`; `0x00164780` retains it in `r6`.
- `0x001648F4` requests exactly `r6` bytes from the stream.
- `0x00165198 add r1,r1,r6` / `0x0016519C str r1,[r4,#0xC]` is the local
  cursor update. The expected calculation is
  `0x00493A1F + 0x0C + 0x0F2C = 0x00494957`.
- No explicit `-6` cursor/seek arithmetic was found in the restricted static
  path. Crucially, the value written at `0x0016519C` has **not** been observed
  dynamically; `0x00494957` there remains a static inference.

Only next diagnostic requested:

Observe these three values dynamically in the initial V2 crash CCI while entry
31 is processed, and stop:

1. Immediately before entry 31: stream absolute cursor at `0x0014F018`;
   expected `0x00493A1F`.
2. Immediately after `0x0016519C`: stream absolute cursor; expected
   `0x00494957`.
3. Immediately before entry 32 header read at `0x0014F018`: expected
   `0x00494957`.

The first appearance of `0x00494951` is the only desired result. Do not expand
static analysis, patch the 60.8 MiB request, shrink the `0x80000` buffer, remove
cache resources, modify binaries, or build another CCI.

Dynamic attempt status:

- A fresh Azahar/GDB session accepted both breakpoints, but the target
  `v000a_0` entry path was not reached within the short observation window, so
  none of the three values was captured.
- Azahar was used only for an attempted dynamic observation; it did not produce
  the original Data Abort or the `0x03A00EB1` value.
- Earlier Azahar debugging attempts showed a debugger breakpoint-cache/assertion
  problem. This assertion is separate from the physical-device crash. Do not
  spend time repeatedly repairing that environment. The last attempt was
  stopped cleanly and Azahar configuration was restored byte-for-byte (backup
  SHA-256 `55593EF2FF4DEF10FE91A10B71BF5EFA10A3E9B0AC9BECF0E582B5E3085AEBD7`).

## Work Completed This Session

- USA clean baseline V0a/V0b/V0c PASS.
- K Gate PASS: all 169 stages use parser-relative `K = 0x56000`.
- Glyph layout: MSB-first, linear row-major, no vertical flip.
- V1 data-only and V2 trampoline PASS.
- Controlled renderer probe displayed `ABC 호프번 XYZ`.
- Three distinct resident bases matched Korean page data 4096/4096 bytes.
- Full 928-glyph page/map deterministic validation PASS.
- Probe-free clean integration CCI produced and manifested.
- Canonical master exposed one additional syllable (`칸`); append-only v2 now
  preserves 928/928 old assignments and adds it at `0x87A4`.
- Combined 1,120-character coverage and encoding preflight PASS.
- Size-preserving media candidates built and content-verified. Whole-record
  safe: movie 247/247, demo 732/732. Maximum row-level safe: movie 585/585,
  demo 1,871/1,871. They are partial subsets, not full master builds.

## Current Blocker

Full natural movie/demo text still exceeds fixed string capacity in many
records. A deliberate relocation/shortening decision is required; do not
silently treat the partial safe DATs as complete.

## Read These Wiki Pages

1. [Current State](wiki/Current-State.md)
2. [Glyph System](wiki/Glyph-System.md)
3. [Translation](wiki/Translation.md)
4. [Build System](wiki/Build-System.md)
5. [Decisions](wiki/Decisions.md)

## Next First Task

**Superseded — the packer fix landed and was hardware-tested (see the RESOLVED
and Canonical RomForge sections above).** No Data Abort on hardware. Current
top task is the NEW section at the top of this file: the history card renders
but its glyphs are corrupted, which is an unrelated pixel-layout bug in the
same tool. Analysis only has been done so far; the fix has not been attempted.

Do not rebuild the old `demo.dat` history-subtitle probe; it targeted the first
spoken demo line and was the wrong resource.

## Cautions

- Do not overwrite `translation/10_master/` with encoded or shortened data.
- Do not include the controlled `ABC 호프번 XYZ` movie probe in clean builds.
- Do not resume exhaustive GDB traversal, save manipulation, cheats or
  equipment preparation.
- Do not generalize the three-stage runtime sample to all 169 stages.

## Key Artifacts

- `docs/evidence/2026-08-14-hpk-cursor-drift/` (tracked: hardware dumps + full
  crash analysis; note `experiments/` is gitignored, so irreplaceable primary
  evidence belongs here instead)
- `docs/evidence/2026-08-14-history-texture-corruption/` (tracked: extracted
  BCLIM members + decode attempts for the glyph-corruption analysis above)
- `experiments/2026-08-13-clean-glyph-baseline/clean-build-manifest.json`
- `experiments/2026-08-13-clean-glyph-baseline/runtime-verification.txt`
- `experiments/2026-08-13-clean-glyph-baseline/full-page-rebuild-audit/full-928-validation.json`
- `experiments/global_korean_page_build_2026-08-12/korean_token_map_full.csv`
- `translation/40_build_input/global_page_v2/`
- `glyph/validation/global_page_v2/` (15 labelled review sheets)
- `experiments/2026-08-13-clean-glyph-baseline/media-candidate-manifest.json`
