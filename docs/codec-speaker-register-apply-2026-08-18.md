# codec 화자 말투(register) 확정 교정 — master 적용 + 재빌드 + 재스테이징 (2026-08-18)

외부 대본(GameFAQs CODEC script / Fandom radio conversations)으로 **화자가 확정된**
codec 행만 대상으로, 확정 말투 규칙과 어긋나는 행을 개별적으로 다시 쓰고 master →
빌드 → 스테이징까지 반영했다. **CCI는 만들지 않았다. commit/push도 하지 않았다.**

확정 규칙 (대사집 대사집으로 검증됨):

| 화자 | 말투 |
|---|---|
| Para-Medic, EVA | 존댓말 |
| Zero, Sigint, Snake, The Boss | 반말 |

---

## 1. 먼저 나온 것 — 말투 분류기 자체가 두 번 틀렸다

`tools/mgs3d_confirmed_register_qa.py`의 `classify_register()`에 **한글 자모/음절
합성에서 오는 버그가 두 개** 있었고, 둘 다 대상 행 목록을 바꿔 놓았다.

### 1-1. `ㅂ니다`는 합성 한글과 절대 매칭되지 않는다

원래 POLITE 목록은 `습니다|ㅂ니다|입니다|합니다|됩니다|갑니다|옵니다` 였다.
`ㅂ니다`는 **자모 U+3142 + 니다** 이고, `겁니다`는 **겁(U+ACC1) + 니다** 다.
따라서 `ㅂ니다`는 죽은 패턴이었고, 열거되지 않은 `겁니다 / 줍니다 / 압니다 /
아닙니다 / 뛰어납니다 / 모릅니다 …`가 전부 **plain으로 오분류**됐다.

- 존댓말 화자(Para-Medic·EVA): 이미 올바른 존댓말 행이 MISMATCH로 잡혔다 → **오탐**
- 반말 화자(Zero·Sigint·Snake·The Boss): 존댓말 행이 MATCH로 통과했다 → **미탐**

### 1-2. 그렇다고 `니다`/`니까`로 바꾸면 이번엔 과탐이다

`니다`는 **아니다**를, `니까`는 연결어미 **-으니까**(그러니까, 싶으니까, 다니니까)를
그대로 삼킨다. 실제로 `-아니다`로 끝나는 Zero 행 1건과 `-으니까`로 끝나는 Snake 행
2건이 polite로 뒤집혔다.

### 1-3. 확정 판정 — 앞 음절의 종성이 ㅂ이어야 한다

`-ㅂ니다 / -ㅂ니까`의 정의 그대로, `니다`/`니까` **바로 앞 음절의 종성이 ㅂ**인지
검사하는 `has_hapnida()`를 넣었다. 한글 음절 공식에서 종성 ㅂ의 인덱스는 17이므로
`(ord(c) - 0xAC00) % 28 == 17`.

| 문자열 | 앞 음절 | 종성 ㅂ | 판정 |
|---|---|---|---|
| 겁니다 / 습니다 / 입니다 / 아닙니다 | 겁·습·입·닙 | O | polite |
| 아니다 | 아 | X | plain |
| 그러니까 / 싶으니까 / 다니니까 | 러·으·니 | X | plain·unknown |

### 대상 행 수의 변화

| 단계 | actionable MISMATCH |
|---|---|
| 원본(죽은 `ㅂ니다`) | 1,285 |
| `니다`/`니까` 단순 매칭 | 1,342 (오탐 29 제거, 과탐 86 유입) |
| **종성 ㅂ 검사 확정** | **1,335** |

이미 작성해 둔 수정안 중 **15건은 원래 올바른 존댓말 행**이었고(1-1의 오탐),
적용 대상에서 제외했다. 승인된 번역을 이유 없이 흔들지 않기 위해서다.

### 남은 한계 (의도적)

PLAIN 목록에 `-해.`형 종결(`X + 해.`)이 없어 그런 절은 `unknown`으로
빠진다. 미탐 쪽이라 잘못 고칠 위험은 없고, 확정 MISMATCH만 다루는 이번 범위에서는
보수적으로 두는 편이 맞다고 판단했다.

---

## 2. 수정 방식 — 일괄 어미 치환을 하지 않았다

각 행마다 **(find, replace) 쌍을 그 행에만 스코프**해서 적용했다. 이렇게 하면
`<0A>`/`<00>`/아이콘 토큰은 **구조적으로** 보존된다 — 토큰 레이아웃을 건드리는
코드가 없고 토큰 사이의 텍스트만 바뀐다.

바이트 예산이 사실상 유일한 제약이었다. 손댄 레코드는 거의 전부 여유 0이라
수정문은 **바이트 중립이거나 더 짧아야** 했다. 그래서 어미만 바꾸지 않고 문장을
같이 줄였다. 한글 음절 2B / ASCII 1B이므로 `-요` 하나를 붙이면 +2B이고, 그만큼을
같은 행 안에서 다시 벌어야 한다.

바이트를 버는 수단은 세 가지였다.

1. **바이트 중립 어미 교체** — `-야/-어/-지/-다` → `-죠` (음절 수 동일)
2. **군더더기 절 압축** — 서술을 한 낱말로 줄이기, 중복 목적어·부사 제거
   (실제로 −10B ~ −18B가 나온 행이 여럿 있다)
3. **조사·관형형 축약** — `-에는` → `-엔`, `-지는` → `-진`, `-하고 있다` → `-한다`

바이트가 안 맞아 표현을 되돌린 경우도 있다. 예를 들어 `1842:10`은 용어 통일
(한국어 낱말 → 게임 내 영문 아이템명)이 +2B라 강조 부사를 뺐고, `1358:10`은
한 음절을 줄여 존댓말 어미를 넣을 자리를 만들었다. 이런 조정이 60행 남짓 있었다.

---

## 3. 검증 — canonical 하나가 아니라 모든 location

이번 라운드의 핵심 교훈(Round 5)을 그대로 적용했다.

1. **행 단위**: `mgs3d_qa_final_verify.verify()` — 신규 glyph, control token 동일성
2. **레코드 단위**: `verify_record()` — `replace_resources(preserve_layout=True)`로
   safe-fixed 빌드와 같은 방식으로 레코드를 다시 조립
3. **전파 단위**: 행의 `locations` **전부**에 새 문자열을 넣고 다시 2번

3번에서 **16개 레코드가 추가로 터졌다.** canonical 위치에는 여유가 있는데
중복 위치의 레코드에는 없는 경우다 — occurrence 5·21·23·28·87짜리 문자열들이었다.
canonical만 봤다면 빌드까지 가서야 알았을 것이다.

```
gcx 881 (243:888/890/895, occ=87)  +14B 초과
gcx 826 (243:865/867, occ=87)      +4B 초과
gcx 2060 (443:1001/1012, occ=5)    +4B 초과
```

---

## 4. 적용 결과

| 항목 | 수 |
|---|---|
| 확정 화자 MISMATCH | **1,335** |
| 실제 수정·적용 | **1,333** |
| HUMAN 보류 | **2** |
| 분류기 오탐으로 취소 | 15 |
| byte-fit 실패로 남은 건 | **0** |

화자별:

| 화자 | 적용 | 방향 |
|---|---|---|
| Para-Medic | 329 | 반말 → 존댓말 |
| Sigint | 319 | 존댓말 → 반말 |
| Zero | 298 | 존댓말 → 반말 |
| EVA | 149 | 반말 → 존댓말 |
| Snake | 135 | 존댓말 → 반말 |
| The Boss | 103 | 존댓말 → 반말 |

방향 합계: **존댓말→반말 855**, **반말→존댓말 478**.

기존 `codec-final-revision-proposals.csv`(511행, `auto_appliable=yes` 467)와의 관계:

- 겹치는 행 **71** — 그중 **69행**은 기존 의미/용어 수정안 위에 말투 수정을 얹어
  **하나의 최종 문장으로 병합**했다(기존 수정 내용 보존).
- 충돌로 기존 수정을 버린 건 **0**.
- 나머지 **440행은 이번에 적용하지 않았다.** 말투 교정 범위 밖이고,
  "467건은 아직 적용하지 마라"가 아직 유효하다고 봤다.

### HUMAN 2건 — 종결 (2026-08-18, 사용자 판단: 둘 다 통과)

| 위치 | 화자 | 사유 | 판정 |
|---|---|---|---|
| `913:29` | Zero | Zero가 제3자(Sokolov)의 말을 인용하는 절. 인용문 안쪽 말투를 화자 규칙으로 덮어쓸 수 없다 | **KEEP** — 현행 유지 |
| `1537:10` | EVA | 어미 없는 종속절 조각(`...할 때까지...` 형태). 말투 표지가 없어 분류기 오탐이며 수정 불필요로 보이나 사람 판단이 필요하다 | **KEEP** — 현행 유지 |

두 건 다 **텍스트 변경이 없다**. master(`translation/10_master/current/codec.csv`)의
`korean` 값은 그대로이고, 따라서 **재빌드도 재스테이징도 필요 없다** — 스테이징된
`codec.dat b29807f8…`가 그대로 유효하다. 판정은
`translation/10_master/review/full-qa-final/codec-register-human-2026-08-18.csv`의
`decision` 열에 기록했다(`KEEP` / `applied=no (no text change)`).

말투 교정 라운드는 이것으로 **1,335건 전부 종결**(적용 1,333 + KEEP 2)이다.

---

## 5. 빌드 + 게이트 — 전부 PASS

```
python tools/mgs3d_script_compare.py make-translation \
    translation/10_master/current/codec.csv \
    translation/40_build_input/v0.90/codec_natural_full_global_page.json \
    --codec experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat \
    --character-map translation/40_build_input/global_page_v2/character-map.json
python tools/mgs3d_codec_expand_locations.py --text-identity ...
python tools/mgs3d_codec_safe_select.py ...
python tools/mgs3d_build.py --partition experiments/2026-08-13-clean-glyph-baseline/clean-tree \
    --output-root builds/v0.90-register/dist \
    --codec-translation translation/40_build_input/v0.90/codec-safe-translation.json \
    --codec-mode safe-fixed \
    --character-map translation/40_build_input/global_page_v2/character-map.json
```

빌드 입력 **8,948 → 224,659 units, dropped 0, GCX failing 0** (v0.89와 동일).
`fixed-layout ready: 2277/2277`, `final_gcx_size_delta=0`, `0 Hangul glyphs added`.

| 게이트 | 결과 |
|---|---|
| codec.dat size delta | **+0** (67,204,976) |
| record count | 2326 → 2326 |
| block_start / record size / resource count drift | **0 / 0 / 0** |
| **KO → EN 회귀 (전 location)** | **0** |
| 신규 glyph | **0** |
| control token drift (1,333행 전부, 이전 master 대비) | **0** |
| byte-fit 실패 | **0** |
| 앵커 A / 앵커 C | **3/3 / 16/16 한국어** |
| PARTIAL_APPLICATION | **212 → 212** (전부 FR 119 + ES 93 도너, 신규 0) |

전파 확인 — 바뀐 1,333행의 **31,509 location** 중:

- **31,506**이 canonical location과 **바이트 동일**
- 나머지 **3**(`442:120`, `443:464`, `444:464`)은 프랑스어 도너 문장으로,
  v0.89 빌드에서도 동일하게 제외돼 있던 기존 상태다(212건 도너 집합의 일부).
- canonical 리소스 **1,333개 전부**가 실제로 바뀌었다.

---

## 6. 스테이징

| 파일 | 이전 | 이후 |
|---|---|---|
| `codec.dat` | `8348377c…` | **`b29807f8825ea7ae8581257e22025ecffd5ec31d97391a3e650ea7b9b7db904a`** |

- 이전 파일: `C:\Users\hhlee\Desktop\Romforge\archive\pre-register-20260818\codec.dat`
- `movie.dat` `a9f9ab9c…`, `demo.dat`, `code.bin`, `exheader.bin` 변경 없음
- **CCI 미생성** — RomForge 리팩과 Citra/실기 확인은 사용자 몫

---

## 7. 남은 것

1. **Citra 확인이 아직이다.** 정적 게이트만 통과한 상태다. Para-Medic/EVA 존댓말과
   Zero/Sigint/Snake/The Boss 반말이 실제 화면에서 자연스러운지, 특히 문장을 줄인
   행들(§2)의 줄바꿈이 깨지지 않는지 봐야 한다.
2. ~~**HUMAN 2건**~~ — **종결**(§4, 둘 다 KEEP, 텍스트 변경 없음).
3. **기존 수정안 440행** 미적용. 별도 승인 후 같은 절차(전 location 검증 → 빌드 →
   게이트)로 처리하면 된다.
4. 분류기 PLAIN 목록의 `해.`형 미탐(§1) — 넓히면 대상이 늘어나므로 별도 라운드로.

## 산출물

- `translation/10_master/review/full-qa-final/codec-register-applied-2026-08-18.csv` (1,333행: before/after/화자/병합 여부/검증 결과)
- `translation/10_master/review/full-qa-final/codec-register-human-2026-08-18.csv` (2행)
- `output/speaker-register-actionable/codec-register-{audit,actionable,summary}.csv` (분류기 수정 후 재생성)
- `translation/10_master/current/codec.csv.bak-register-2026-08-18` (적용 전 master)
- `builds/v0.90-register/dist/0004000000081E00/romfs/codec.dat`
