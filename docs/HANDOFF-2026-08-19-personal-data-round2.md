# PERSONAL DATA 필드 복원 + donor 재분류 — dry-run 결과

상태: **scratch dry-run 완료 / PASS.** master·staged codec.dat·production build
모두 미수정. 승인 후 적용 대기.

## 1. capacity 모델 정정

이전 라운드의 `SHORTEN 3행 / deficit 18 bytes` 판정은 **잘못된 모델**에서 나왔다.
`mgs3d_personal_data_feasibility.py`가 쓴 예산은 각 중복 location의 clean 리소스
슬롯 최소값(`min(budgets)`)이었는데, 그것은 stage/scenerio.gcx의 per-resource
모델이지 codec의 모델이 아니다.

codec의 실제 게이트는 `mgs3d_codec_tool.GcxRecord.replace_resources(preserve_layout=True)`
(`tools/mgs3d_codec_tool.py:305-309`)이고, **한 GCX record의 모든 리소스를 하나의
string region으로 합친 합계**만 본다. 한 리소스가 커져도 같은 record 안에서 줄어든
다른 리소스가 충당한다.

반증도 이미 데이터에 있었다: 28/21은 `current_bytes 142`, `min_slot_bytes 139` —
현재 staged codec.dat이 이미 139바이트 슬롯에 142바이트를 쓰고 통과하고 있었다.

이번 라운드는 축약을 전혀 하지 않았고, 실제 production 경로에서 deficit 0이다.

## 2. 47행 필드 구조 복원

clean English를 authority로 10줄 구조(`0A` × 9 + `00`)를 복원했다.
L0 헤더 / L1 공백 / L2-L8 7개 필드 / L9 공백.

- **보존**: 한국어 값은 master에 있던 것을 그대로 쓴다. 문구를 재작성하지 않았다.
- **복원 1 — 소실된 label**: 압축형 행은 label 자체가 없었고(`여 28세 USA`),
  일부는 label이 붙어버렸다 — `머리:적안:갈색`(HAIR:RED + EYE:BROWN),
  `혈액형:과거 질병:통풍`(BLOOD TYPE + PAST ILLNESSES, 혈액형 값이 소실).
- **복원 2 — 잘린 원본 값**: `출생:EXETER` → `출생지:EXETER,ENG.`.
  번역 선택이 아니라 원본 데이터라 clean 값으로 되돌렸다.
- **통일**: 같은 화면에서 암호명/코드명/CODE, 나이/연령이 섞여 있던 것을
  암호명·성별·나이·국적·생년월일·출생지·주소로 통일했다.
- **오역 1건 정정**: 445/7의 `암호명: 서명`. SIGINT는 인물의 코드명이지
  "signature"가 아니다. 나머지 5개 SIGINT 행이 이미 Sigint/SIGINT를 쓰므로 맞췄다.

저작표: `tools/mgs3d_personal_data_authoring.py`

## 3. donor 오분류 2행 교정

`gcx 28 / res 21`, `gcx 28 / res 18`.

근거:

- clean codec.dat의 원문이 영어다 — `PERSONAL DATA [1/2] CODENAME:PARA-MEDIC ...`
- master에 한국어 번역이 이미 채워져 있었다.
- 그런데 `language=fr`, `is_donor=yes`, `status=외국어분기`로 표시돼 있었고,
  `mgs3d_codec_expand_locations.py`는 `is_donor == yes` 행을 통째로 건너뛴다.
- 결과: 두 행의 중복 **1,358 location이 staged codec.dat에서 영어 그대로**였다.
  (680 + 680 = 1,360 중 canonical 2곳만 한국어)

scratch에서 `is_donor=no`, `language=en`으로 교정하니 expand 단계가
225,307 → **226,665 units**로 정확히 +1,358 늘었다.

## 4. 검증 결과

```
pipeline: make-translation -> expand_locations -> capacity --check -> build-korean
source  : clean-tree codec.dat (dd6ea4b8...)

expand           8,994 -> 226,665 units  (+1,358 vs 이전 225,307)
capacity         2,288 / 2,288 ready, failing 0, total_slot_deficit 0
build            2,288 records changed, hangul glyphs added 0
                 final_gcx_size_delta = 0
built sha256     370506bef7434b9c99cf4fe01854d83626c0336c2db5640269d2aaa693924545
size             67,204,976  (staged와 동일)

47행 location            26,759
  control 0A x9 + 00     26,759 / 26,759
  한국어                  26,759
  영어 잔존                    0
donor 교정 2행           각각 1 -> 680 location 한국어
DAT read-back            47 / 47 rows, mismatch 0
layout drift             2,326 records, size changed 0
```

staged v0.91 대비 전체 차이 28,913 리소스 중 PERSONAL DATA 밖은 2,154개인데,
**전부 후행 NUL 패딩 차이**이고 `rstrip(b'\0')` 후 내용이 동일하다. 문자열이
NUL 종료라 리더에는 보이지 않으며, record 크기 변화는 0이다. pooled string region이
재포장되면서 각 record 마지막 리소스의 패딩이 재배분된 결과다.

final gate 전항목 PASS (coverage 100.0000%).

## 5. 이번 라운드에서 건드리지 않은 것

`UNTRANSLATED_PERSONAL_DATA`: **77행 / 373 location**. 전부 영어 그대로다.
별도 신규 번역 트랙으로 남긴다.

movie.dat·demo.dat·scenerio.gcx·code.bin·exheader.bin 무수정.
master 무수정, staging 무수정, CCI 없음, commit/push 없음.

## 6. 산출물

- `tools/mgs3d_personal_data_authoring.py` — 47행 필드 분할표
- `tools/mgs3d_personal_data_fields.py` — clean 필드 구조 덤프
- `docs/evidence/2026-08-19-personal-data-round2/expand-report.json`
- `docs/evidence/2026-08-19-personal-data-round2/capacity-summary.json`
- `docs/evidence/2026-08-19-personal-data-round2/codec-final-verification.json`
- scratch 빌드: `scratchpad/pd-round/codec.dat` (production 산출물 아님)

---

# 후속 라운드 — 공란 77행 정리 (2026-08-20)

## 결론: 20행 번역, 57행은 정상 donor

`is_donor` 플래그를 **record 단위**로 검증했다. PERSONAL DATA를 담은 15개 GCX
record는 전부 내부적으로 일관된다 — 한 record는 통째로 `en`이거나 통째로
`es`/`fr`이다.

```
gcx     rows  is_donor          language        korean
15        14  no                en              14/14
28        10  no                en              10/10   <- 2026-08-19 교정 후
32         3  no                en               3/3
445       10  no                en              10/10
1480      10  no                en              10/10
359       10  no                unknown          0/10   <- 번역 대상
1500      10  no                unknown          0/10   <- 번역 대상
75         5  yes               es               0/5
315        1  yes               es               0/1
362       10  yes               fr               0/10
395       10  yes               es               0/10
567        6  yes               es               0/6
787        5  yes               fr               0/5
1489      10  yes               es               0/10
1724      10  yes               fr               0/10
```

이 표는 2026-08-19의 28/21·28/18 교정이 옳았다는 근거도 된다. 교정 전 record 28은
10행 중 8행 `no`/2행 `yes`로 **혼재**했는데, 그런 record는 그것 하나뿐이었다.
나머지 14개 record는 모두 균일하다.

- **20행 (record 359, 1500)**: `is_donor=no`, `status=PS2대응없음`.
  영어 분기인데 PS2 한국어 원본이 없어 비어 있던 것이다. → 번역 대상.
- **57행 (8개 record)**: `is_donor=yes`, `language=es/fr`. record 전체가 스페인어
  또는 프랑스어 분기다. 내용이 영어인 이유는 코나미가 PERSONAL DATA 카드 본문을
  현지화하지 않았기 때문이지, 영어 분기라서가 아니다. → **번역하지 않는다.**

## 20행 처리 방식

20행의 clean English가 **이미 번역된 47행 중 하나와 바이트 단위로 완전히 동일**함을
확인했다(20/20 일치). record 1500은 1480(EVA)과, record 359는 28(PARA-MEDIC)과
같은 카드다. 따라서 새로 저작하지 않고 **검증이 끝난 동일 카드의 한국어를 그대로
재사용**했다. 새 번역 판단이 개입하지 않으므로 위험이 없다.

`accept=yes`, `translate=yes`, `language=en`으로 바꾸고 status에 출처 행을 기록했다.

## 검증

```
expand        226,665 -> 226,825 units   (+160 = 20행 x 각 locations)
capacity      2,289 / 2,289 ready · failing 0 · deficit 0
build         2,289 records changed · glyphs 0 · final_gcx_size_delta 0
sha256        e9026a5e8fe50358f97d0b0e685cb17dfc0bd6829c244863b5c80b0eaf6fb21c
size          67,204,976

20행 location            160
  control 0A x9 + 00     160 / 160
  한국어                  0 -> 160
  read-back              20 / 20
57 donor행               213 location 전부 영어 유지
regression vs v0.92      176 리소스 차이, PERSONAL DATA 밖 16개는 전부 후행 NUL only
records                  2,326 무변화
final gate               전항목 PASS · coverage 100.0000% · read-back 67/67
```

master sha256 `2770c3c02d38ebf8`, staged codec.dat `370506be… -> e9026a5e…`.
movie/demo/stage/code.bin/exheader 무변경. CCI 없음.
