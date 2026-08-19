# 오후 재개용 핸드오프 (2026-08-19 오전 세션 종료 시점)

**오전 세션은 전부 read-only 분석이었다. 아무것도 적용하지 않았다.**

| 대상 | 상태 |
|---|---|
| `translation/10_master/current/*.csv` | **무변경** (`git status` clean) |
| `analysis/`, `translation/20_matching/` | **무변경** |
| RomForge 스테이징 `romfs/*.dat` | **무변경** (타임스탬프 08-16/08-17 그대로) |
| CCI / 빌드 | **미생성** |
| commit / push | **없음** |

> 릴리스 규칙(2026-08-19)은 그대로 유효하다 — **모든 버전은 사용자 승인 없이 올리지 않는다.**

---

## 0. 오전에 무엇이 밝혀졌나 (3줄)

1. **인게임 적/NPC 대사는 네 번째 텍스트 컨테이너에 있다** — `stage/*/scenerio.gcx` 169개,
   유니크 1,571행 / 149,592 location이 **100% 미번역**. 빌드 누락이 아니다.
2. **movie/demo에 한국어가 다른 대사 자리에 앉은 행이 최소 95개 있다.** 영어 쪽은 멀쩡하다
   (master `preview` ↔ 실제 DAT 2,917/2,917 일치). 게임에서 그대로 나온다.
3. **그 오배치를 자동으로 되돌리는 시도는 2번 다 실패했고, 원인이 측정으로 확정됐다.**
   → 수동 문맥 검수로 복귀한다.

---

## 1. 오후 첫 작업 — 이것부터 하면 된다

### movie/demo 오배치 수동 문맥 검수 (312행)

```
파일: output/media-register-qa/media-offset-verdicts.csv
필터: verdict = UNREVIEWED
정렬: media, record, entry
시작 행: demo r0 e30          <- 여기서 시작
끝  행: movie r49 e14
분포: demo 288 / movie 24, 127개 레코드에 걸쳐 있음
```

> ⚠️ 이전 메모에 적힌 `demo r5 e5`는 **우선순위 flag 기준** 첫 행이었다.
> 실제 UNREVIEWED 첫 행은 **`demo r0 e30`**이다. 이쪽이 맞다.

**검수 방법 (오전에 95행을 확정한 것과 동일한 방식):**

레코드 하나 = 컷신 하나이고 엔트리는 재생 순서다. 한 행만 보지 말고 **그 레코드 전체를
순서대로 읽고** English ↔ Korean이 같은 대사인지 본다. 문맥 덤프 명령:

```
python - <<'EOF'
import csv, io, collections
csv.field_size_limit(10**9)
ctx=list(csv.DictReader(io.open("output/media-register-qa/media-register-context.csv",
                                encoding="utf-8-sig", newline="")))
by=collections.defaultdict(list)
for r in ctx: by[(r["media"], int(r["record"]))].append(r)
for r in sorted(by[("demo", 0)], key=lambda x: int(x["entry"])):
    print("e%-4s %-56s| %s" % (r["entry"], r["english"][:56], r["korean"][:56]))
EOF
```

**판정은 4종으로 제한한다** (오전과 동일):
`KEEP` / `MISPLACED` / `REMAP` / `HUMAN`. **HUMAN을 억지로 줄이지 마라.**

**판정을 남기는 곳**: `docs/evidence/2026-08-19-media-qa/verdicts.py` 의 `MISMAPPED`
리스트에 `("demo", record, entry)` 추가. KEEP 근거도 남기면 다음 라운드에서 같은 행을
다시 열지 않는다. 그다음 재생성:

```
python tools/mgs3d_media_offset_verdict.py --outdir output/media-register-qa
```

### 판정 기준으로 쓸 수 있는 단서

- **확정 오배치 95행은 거의 전부 문장부호 앞 공백**(`몰라 .`)을 달고 있다 — the script reference
  표의 표기 습관이 남은 행이다.
- **미검토 312행은 그 공백이 없다.** 표본 22행을 봤더니 거의 전부 정상이었다
  (`You OK? → 괜찮아?`, `Remember the Alamo → 알라모를 잊지 마라`).
- 따라서 **가설: 정규화를 거친 행 = 이미 재작성된 행**. 오후에 검증할 것.
  맞다면 312행 중 실제 오배치는 소수일 가능성이 크다.

---

## 2. 하지 말아야 할 것 (오전에 확정된 금지 사항)

| 금지 | 이유 |
|---|---|
| `en_{demo,movie}_korean_matches.csv`를 authority로 사용 | **오배치의 원천**이다. 확정 오배치 95행 전부가 같은 키·같은 한국어로 들어 있다(95/95) |
| `mgs3_korean_english_alignment.csv` / `_dp.csv`를 authority로 사용 | 오배치의 **뿌리**. 95행 전부에서 `english`는 실제 DAT 대사와 일치(95/95)하는데 `korean`이 틀렸다 |
| `exact-unique-korean` 방식 재사용 | 한국어 문자열 유일성으로만 매칭 → 짧은 대사가 대본 아무 데나 붙는다 |
| **말투 FIX 91건 적용** | 오배치 정리 전에 적용하면 통째 교체 때 날아간다 |
| 자동 재정렬 재시도 | §3 참조 — 전제 조건이 갖춰지지 않았다 |

---

## 3. 자동 재정렬을 다시 시도하려면 (지금은 중단)

2번 시도, 2번 다 게이트 실패:

| 시도 | 게이트(확정 KEEP 107행 재현) | 자동 REMAP |
|---|---:|---:|
| `tools/mgs3d_media_realign.py` | 0 / 107 | 0 |
| `tools/mgs3d_media_realign2.py` | 3 / 107 | 1 |

2차에서 1차 결함은 실제로 고쳤다 — **(record, entry) 순서 = 스토리 순서 검증 완료**
(오염 앵커 `71`·`339`·`1254`·`1424` 제거 시 movie 96.8% / demo 85.4% 단조),
윈도 앵커도 유니크 위치 + LIS 백본으로 교체. 그래도 실패했다.

**근본 원인(측정값): master 한국어 2,917행 중 대사집 대본에서 위치가 잡히는 행이
213~225행(7.4%)뿐이다.** 나머지 92.5%는 정규화·축약·재번역을 거쳐 원문과 더는 같지
않다. 앵커 밀도가 부족하고, 앵커 없는 구간은 고유명사·숫자·길이비만으로 다리를
놓지 못한다. LIS 백본도 정상/오배치를 구분 못 했다(KEEP 61/107 vs MISPLACED 47/95).

**재시도 전제: 의미 기반 이중언어 정렬기(문장 임베딩 등).** 현재 프로젝트 자산에 없다.

**게이트는 영구 유지** — 어떤 자동 정렬이든 **확정 KEEP 107행을 107/107 재현**하지
못하면 그 출력은 쓰지 않는다. 오전에 이 게이트가 두 번 다 나쁜 정렬을 막았다.

---

## 4. 대기 중인 다른 작업 (오배치 정리 후)

### 4-1. movie/demo 말투 제안 91건 — 준비 완료, 적용 보류

`output/media-register-qa/media-qa-proposals.csv` (509행)
**FIX 91**(전부 바이트 검증 통과) · KEEP 55 · REVIEW 131 · HUMAN 232

FIX 내역: 문장부호 앞 공백 77 / Snake 존댓말→반말 8 / Sokolov 반말→하오체 3 /
Zero 존댓말→반말 1 / 직역 2.

말투 검수 자체의 결론은 **movie/demo 말투는 대체로 멀쩡하다**는 것이다. 두 말투가
섞인 75레코드 중 55행은 정상(EVA 존댓말, 볼긴·보스에게 보고하는 부하, 하오체
소코로프 장면의 스네이크 반말). 진짜 흔들림은 12행, 거의 전부 **스네이크가 제로에게
존댓말**을 쓰는 codec↔demo 불일치다.

### 4-2. HUMAN 232건 중 정책 결정이 필요한 것

- **고유명사 표기 분열 78행** — `Sokolov`/`소코로프`, `Snake`/`스네이크`, `Boss`/`보스`.
  행 단위 수정이 아니라 **프로젝트 전체 로마자/한글 표기 정책** 결정 사안. 사용자 판단 필요.
- **한국어 속 영어 잔존 34행** — 용량에 밀린 전보식 축약. 그라닌 장면(demo r79-r86)과
  소코로프 브리핑(r21-r22)에 몰려 있다. 예: `tank엔 rocket 필요 없어!`,
  `이게 real weapon 혁명! 맞지!?`, `US family 보고 싶었어...`. 바이트 예산 동반 재번역 필요.

### 4-3. stage 텍스트 한글화 (별도 트랙, 착수 전)

`docs/ingame-stage-text-english-residue-2026-08-19.md`

- 잔존량 **유니크 1,571행 / 149,592 location / 89,070 B** (prose 1,065)
- 워크리스트: `docs/evidence/2026-08-19-stage-text-scan/stage-text-english-worklist.csv`
- **정본 없음.** 대사집 STAGE.DAT은 추출·카탈로그돼 있으나 해독이 1,548행 중 58행뿐 —
  codec 때 쓴 로컬 글리프 OCR을 stage용으로 끝까지 돌린 적이 없다. **이게 첫 단계다.**
- 용량은 여유롭다(donor가 영어의 2.55배, 169/169 스테이지 마진 양수).
  한글 글리프 페이지는 이미 169/169에 붙어 있다.
- **주의**: stage 텍스트는 `originals/3ds_pristine/`(**일본판**)이 아니라
  `experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/`(영어판)를 봐야 한다.

---

## 5. 오전 산출물 목록

### 도구 (전부 read-only)

| 파일 | 역할 |
|---|---|
| `tools/mgs3d_stage_text_scan.py` | stage/*/scenerio.gcx 텍스트 전수 스캔 + 언어 분기 판정 |
| `tools/mgs3d_media_register_qa.py` | movie/demo 말투·호칭·직역체 후보 추출(문맥 단위) |
| `tools/mgs3d_media_qa_proposals.py` | 판정 + 바이트 검증 → 제안 시트 |
| `tools/mgs3d_media_offset_audit.py` | offset 행 텍스트 역추적 |
| `tools/mgs3d_media_offset_align.py` | 시퀀스 델타 / LIS 스크리닝 |
| `tools/mgs3d_media_offset_verdict.py` | **통합 판정 시트 생성** |
| `tools/mgs3d_media_realign.py` / `realign2.py` | 재정렬 1·2차 (둘 다 게이트 실패, 보존) |

### 데이터

| 파일 | 내용 |
|---|---|
| `output/media-register-qa/media-offset-verdicts.csv` | **오후 작업 대상 시트** 514행 |
| `output/media-register-qa/media-qa-proposals.csv` | 말투 제안 509행 |
| `output/media-register-qa/media-register-context.csv` | 2,917행 문맥 덤프(검수용) |
| `docs/evidence/2026-08-19-media-qa/verdicts.py` | **사람이 읽고 내린 판정**(행 단위, KEEP 포함) |
| `docs/evidence/2026-08-19-stage-text-scan/` | stage 스캔 결과 + 영어 워크리스트 |

### 문서

- `docs/ingame-stage-text-english-residue-2026-08-19.md`
- `docs/movie-demo-contextual-qa-2026-08-19.md`
- `docs/evidence/2026-08-19-media-offset-audit/README.md` — offset 감사 체크포인트
- `docs/evidence/2026-08-19-media-offset-audit/REMAP-SOURCE-RECOVERY.md` — 부록 1·2에 재정렬 실패 기록

---

## 6. 절대 조건 (오후에도 동일)

- master 수정 금지 / `movie.dat`·`demo.dat` 수정 금지
- build / staging / CCI 금지
- commit / push 금지
- 새 번역·말투 교정 금지 (오배치 판정만)
