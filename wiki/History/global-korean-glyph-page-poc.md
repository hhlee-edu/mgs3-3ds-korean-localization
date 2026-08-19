# MGS3D 전역 한글 Glyph Page POC 분석

## 결론

`0x00A46FD8`은 추정이 아니라 **renderer가 직접 읽고 font loader가 쓰는 전역 glyph page pointer table**이다. 각 page는 1,020 glyph, 각 glyph는 64B이므로 한 page의 bitmap 영역은 `0xFF00`(65,280B)이다.

후속 runtime 검증에서 page 1도 초기화 직후부터 `0x087A973C`인 non-NULL page로 확인됐다. 따라서 page 0~6 중 덮어쓸 수 있다고 증명된 slot은 없다. 특히 단순 page 7 추가는 불가능하다. renderer가 page 계산 전에 token의 `0x2000`과 `0x4000`을 flag로 제거하기 때문에 page 7 token(`A0xx`)은 별도 page가 아니라 기존 token 공간으로 alias된다. page 4·5·6 또한 초기화 코드가 실제 pointer를 기록한다. 따라서 확인되지 않은 pointer patch를 만들지 않았으며, 게임 실행 성공 조건도 달성했다고 주장하지 않는다.

현재 결과는 **구조 및 runtime table 확정 + page 재사용 POC 안전 차단 + decoder 확장 설계 완료**다. runtime 증거와 다음 설계는 `docs/global-korean-glyph-runtime-verification.md`에 있다.

## 분석 대상과 재현성

- decompressed code image: `analysis/script_ref/full_build/rebuild_2026-08-08/code_en_decompressed_verified.bin`
- size: 8,478,720B
- SHA-256: `10c7d3496a864b340a312593dfe2c44edcf99c42c7829683930d150de1a13df7`
- text VA/file mapping: VA `0x00100000`, file offset `0`, size `0x77F8C4`
- table address literal occurrences: file offsets `0xA8AC`, `0x5E878`, `0x5EF18`, `0x5435C0`

분석 도구는 hash와 네 literal 위치가 모두 일치하지 않으면 page dump를 거부한다.

## Renderer lookup 구조

두 개의 독립적인 draw path가 같은 계산을 수행한다.

- path A: `0x0015E600..0x0015E678`, table literal `0x0015E878`
- path B: `0x0015EC94..0x0015ECD8`, table literal `0x0015EF18`
- 두 literal 값: `0x00A46FD8`

path A의 핵심 명령은 다음과 같다.

```text
0x15E600  bic   r1, r1, #0x6000
...
0x15E63C  sub   ip, r1, #0x8400
          signed divide ip by 0x400
          asr   ip, ip, #10          ; page
          ...                         ; page 시작 token 산출
          sub   r1, r0, #0x8400
          sub   r1, r1, #1
          ... divide by 0x100 ...     ; xx00 hole 보정
0x15E66C  ldr   lr, [pc, #0x208]     ; *(0x15E878) = 0xA46FD8
0x15E670  ldr   r0, [lr, ip, lsl #2] ; table[page]
0x15E674  cmp   r0, #0
0x15E678  ldreq r0, [sp, #0x44]      ; NULL이면 fallback
          add   lr, r0, r1, lsl #6  ; base + index*64
```

흐름은 다음과 같이 확정된다.

```text
16-bit token
  -> normalized = token & ~0x6000
  -> static 81xx/82xx/83xx 또는 generic >= 8401 분기
  -> page = (normalized - 0x8400) // 0x400
  -> page_base = *(uint32_t *)(0x00A46FD8 + page*4)
  -> page 내부의 각 xx00 code를 제외해 index 계산
  -> glyph = page_base + index*64
```

generic page 내부 계산식은 다음과 같다.

```python
normalized = token & ~0x6000
page, within = divmod(normalized - 0x8400, 0x400)
index = within - 1 - ((within - 1) // 0x100)
address = page_pointer[page] + index * 64
```

`within == 0` 또는 `(within & 0xFF) == 0`은 glyph가 없는 `xx00` hole이다. 한 page는 네 개의 255-code 구간이므로 `4 * 255 = 1020` glyph다.

역변환은 다음과 같다.

```python
group, offset = divmod(index, 255)
token = 0x8400 + page*0x400 + group*0x100 + offset + 1
```

도구 구현은 `decode_glyph_token()`과 `encode_glyph_token()`에 있다.

## 기존 static token

같은 path에서 generic lookup 전에 다음 별도 변환이 확인된다.

| token 구간 | combined static index |
|---|---:|
| `8101..8151` | `token - 0x8101` |
| `8201...` | `token - 0x81B0` |
| `8301...` | `token - 0x825C` |

따라서 새 global page는 기존 static/custom 191칸과 주소 계산상 독립적이다. 단, 새 token 공간과 안전한 table slot이 실제로 확보되어야 한다.

## `0x0010A894` 분석

전체 함수는 다음 6개 명령이다.

```text
0x10A894  ldr   r2, [pc, #0x10]       ; 0xA46FD8
0x10A898  cmp   r0, #2
0x10A89C  str   r1, [r2, r0, lsl #2] ; table[r0] = r1
0x10A8A0  addeq r0, r1, #0xFF00
0x10A8A4  streq r0, [r2, #0x10]      ; table[4] = r1+0xFF00
0x10A8A8  bx    lr
```

- `r0`: page index
- `r1`: glyph bitmap pointer
- return value: 일반 page에서는 보장된 의미 없음; page 2일 때 `r1+0xFF00`이 `r0`에 남음
- range check: 없음
- signed/unsigned check: 없음
- mask: 없음
- hard-coded 특례: page 2 설정 시 page 4도 두 번째 1,020-glyph bank로 설정

함수 자체에 bound가 없다는 것은 slot이 무한하다는 뜻이 아니다. backing array의 실제 할당 크기보다 큰 index는 인접 BSS를 손상시킬 수 있다. 현재 코드가 확실히 쓰는 최대 index는 6이므로 최소 7-entry임만 증명된다.

직접 `BL 0x10A894` call site는 확인되지 않았다. 작은 loader helper가 간접 호출/export table을 통해 사용될 가능성이 있으며, 정적 image만으로 초기 호출 횟수와 page 1~3의 런타임 pointer 값은 확정하지 않았다.

## 직접 초기화되는 page

`0x00643554` 주변 initializer는 table literal을 읽고 다음을 기록한다.

```text
table[0] = font_base + 0x03080
table[5] = font_base + 0x12F80
table[6] = font_base + 0x22E80
```

setter는 page 2 등록 때 `table[4] = table[2] + 0xFF00`을 기록한다. 그러므로 page 0, 4, 5, 6은 대사 scan에서 token이 없어도 미사용으로 간주할 수 없다.

## Token page 범위와 flag 충돌

| page | token 범위 (`xx00` 제외) | 용량 |
|---:|---|---:|
| 0 | `8401..87FF` | 1020 |
| 1 | `8801..8BFF` | 1020 |
| 2 | `8C01..8FFF` | 1020 |
| 3 | `9001..93FF` | 1020 |
| 4 | `9401..97FF` | 1020 |
| 5 | `9801..9BFF` | 1020 |
| 6 | `9C01..9FFF` | 1020 |

page 7의 산술 base는 `0xA000`이지만 `0xA001 & ~0x6000 == 0x8001`이다. 즉 `A0xx`는 새 page 7로 도달하지 않는다. 이후 영역도 flag alias이므로, 기존 lookup을 수정하지 않고 두 번째 Korean page를 단순 추가할 수 없다.

## 구조화된 대사 token 조사

원시 binary 전체에서 우연히 나타나는 byte pair를 세지 않고 각 format parser로 실제 subtitle/string resource만 조사했다.

| 매체 | page 2 | page 3 | 기타 generic page |
|---|---:|---:|---:|
| movie 안전 기준본 | 0 | 582 | 0 |
| demo 안전 기준본 | 0 | 1,086 | 0 |
| codec 안전 기준본 | 40,902 | 0 | 0 |

CSV `analysis/glyph_page_table.csv`에는 page별 초기화 근거와 이 count가 있다. 이는 지정한 세 대사 파일의 사용량이며, UI·메뉴·다른 언어까지 포함한 전역 미사용 증명은 아니다. 정적 code image의 table은 BSS runtime object이므로 NULL pointer 값도 정적 파일에서 읽을 수 없다.

## 미사용 page 판정

- 확실한 used: page 2(codec), page 3(movie/demo)
- 초기화되지만 스캔 대사에서 미관측: page 0, 4, 5, 6
- runtime non-NULL, 기존 용도용 allocation: page 1 (`0x087A973C`)
- 확실한 NULL: 없음
- 확실한 전역 unused: 없음

따라서 기존 page를 덮어쓰지 않는다는 작업 원칙 아래 현재 선택 가능한 page는 없다. page 1의 실제 draw 소비처는 미확정이지만 non-NULL allocation이라는 사실만으로 재사용 후보에서 제외된다.

## 저장 위치 비교

| 후보 | 크기/offset | lifetime 및 공용성 | 주요 위험 | 판정 |
|---|---|---|---|---|
| code.bin 내부 zero/alignment | file size를 유지할 가능성 있음 | 상시 map이면 세 매체 공용 | zero run은 미사용 증명이 아니며 data trailing padding 224B는 3 glyph+8 pointers와 정확히 같아도 loader copy 범위가 미확정 | runtime POC 후보, 현재 보류 |
| resident.hpk | asset loader lifetime 확인 필요 | resident라면 공용 가능 | HPK offset/압축/loader pointer 조사 필요 | 장기적으로 유력 |
| 기존 font resource 확장 | resource grow 필요 | font lifetime을 상속 | 후속 offset 및 allocation 크기 변경 | POC에는 부적합 |
| 신규 asset | 기존 record 불변 | 명시적 lifetime 설계 가능 | 신규 loader와 package table 수정 필요 | 가장 깨끗하지만 구현량 큼 |
| codec/demo/movie 내부 | 해당 scene/record lifetime | 전역 공용 불가 | pinned GCX 및 record 이동 위험 | 제외 |

3 glyph 자체는 192B지만 pointer table을 안전하게 늘리거나 기존 slot을 재사용할 근거가 별도로 필요하다. code.bin data segment의 trailing page padding은 224B이나 declared initialized-data size 밖이므로 로드된다고 가정하지 않았다.

## 계획했던 Korean POC

안전한 slot이 확인되면 POC page의 index 0..2에 16x16 2bpp linear 64B bitmap `가`, `나`, `다`를 넣고, 영향이 적은 subtitle 한 줄의 복사본에 세 token만 삽입한다. 원본 DAT와 Romforge working patch는 수정하지 않는다.

현재는 slot이 확인되지 않았으므로 `tools/mgs3d_global_korean_glyph_poc.py`를 만들지 않았다. 이는 산출물 조건의 “분석이 확정된 경우에만”을 따른 것이다. 확인되지 않은 page 4/5/6 덮어쓰기나 page 7 pointer write는 crash 또는 silent memory corruption 가능성이 있다.

## 질문별 답

### Q1. movie/demo/codec에서 같은 token을 쓸 수 있는가?

renderer lookup은 공통이므로 동일 시간에 같은 global page pointer가 유효하다면 가능하다. 하지만 현재 page 2와 3은 매체별 loader가 설정하는 것으로 보이며, Korean page의 lifetime은 아직 런타임으로 증명되지 않았다.

### Q2. 한 번 저장하면 scene마다 64B가 다시 드는가?

상시 유효한 global page라면 들지 않는다. 각 문자열에는 해당 2-byte token만 필요하다.

### Q3. 문자열에는 token bytes만 증가하는가?

기존 문자 교체라면 문자당 2B를 사용한다. `TEST 가나다`처럼 문자를 추가하면 space 1B와 세 token 6B 및 terminator 여유가 필요하다.

### Q4. static/custom 191칸과 독립적인가?

bitmap pool과 lookup branch는 독립적이다. 다만 token flag 공간과 page table slot 제약은 별도 문제다.

### Q5. 한 page 최대 glyph 수는?

1,020개, 총 `0xFF00` = 65,280B다.

### Q6. 두 번째 Korean page도 추가 가능한가?

현재 token grammar 그대로는 단순 추가할 수 없다. page 7부터 `0x6000` flag mask와 alias된다. 두 번째 page에는 renderer grammar 변경, escape token, 또는 확인된 기존 page 재용도가 필요하다.

## 테스트 결과와 불변성

- token encode/decode 경계: `page 0/index 0 -> 0x8401`, `page 6/index 1019 -> 0x9FFF`
- verified code hash/literal check: 통과
- structured media page inventory/CSV 생성: 통과
- 원본 및 기존 build file 수정: 없음
- 전체 DAT rebuild: 없음
- GCX53 이동: 없음
- emulator/game 출력: 미실시
- 성공 판정 1~5: 아직 미달성

## 다음 단계

1. 기존 table은 확장하지 않고 별도 `korean_page_pointer` storage와 resident lifetime을 확정한다.
2. A0xx Korean predicate를 bitmap lookup 2곳과 width path 2곳에 먼저 설계한다.
3. parser/layout mask cluster의 A0xx 통과 조건을 회귀 분석한다.
4. isolated executable/asset에서만 `가나다` 192B와 한 줄 test patch를 생성한다.
5. 기존 glyph와 자막에 변화가 없음을 hash/화면으로 확인한 시점에 POC 성공으로 판정한다.

## 도구 사용 예

```text
python tools/mgs3d_glyph_page_analyze.py --decode-token 0x9001
python tools/mgs3d_glyph_page_analyze.py --encode-token 3 0
python tools/mgs3d_glyph_page_analyze.py --dump-pages
python tools/mgs3d_glyph_page_analyze.py --check-unused-pages
```
