# MGS3D Global Korean Glyph Page Runtime Verification

## 판정

page 1은 재사용할 수 있는 NULL slot이 아니다. 새 Azahar cold-boot 세션에서 guest GDB로 `0x00A46FD8`을 읽었을 때 초기화 완료 직후부터 `0x087A973C`이 들어 있었고, 12초 뒤에도 동일했다. 따라서 기존 page를 덮어쓰지 않는다는 원칙상 CASE A POC는 수행하지 않았다.

이 결과가 page 1 token의 실제 화면 사용까지 증명하지는 않는다. 정확한 판정은 **항상 초기화됨, 전역 미사용은 미증명, 덮어쓰기 불가**다. page 1을 조건부 재사용하는 실험도 하지 않는다.

## 재현 환경

- emulator: locally built Azahar
- guest debugger: Azahar GDB stub, TCP 24689
- GDB: `C:\devkitPro\devkitARM\bin\arm-none-eabi-gdb.exe`
- controller: `tools/citra_gdb_mi_controller.py`
- test CCI: archived isolated test CCI; live Romforge/RomFS는 수정하지 않음
- table width: ARM `ldr [base,index,lsl#2]` 및 setter의 32-bit `str`에 따라 pointer당 4B

Azahar는 프로세스당 GDB 연결을 한 번만 정상 초기화한다. 포트 probing 접속은 stub을 종료시키므로 하지 않았다. 설정 파일 원본은 `qt-config.ini.global-glyph-poc.bak`으로 보존했다.

## Runtime dump

| state | p0 | p1 | p2 | p3 | p4 | p5 | p6 |
|---|---|---|---|---|---|---|---|
| first attach after init | `08688578` | `087A973C` | `08954BB4` | `00000000` | `08964AB4` | `08698478` | `086A8378` |
| 12 seconds later | same | same | same | NULL | same | same | same |

관계도 정적 분석과 일치한다.

- `p4 - p2 = 0xFF00`
- `p5 - p0 = 0xFF00`
- `p6 - p5 = 0xFF00`

즉 p0/p5/p6은 연속 3-bank font, p2/p4는 연속 2-bank font이며, p1은 별도 allocation이다.

CSV: `analysis/glyph_page_runtime_dump.csv`

## Registration trace

fresh boot에서 `0x0010A894`에 breakpoint를 시작 전에 설치했다. 첫 호출은 다음과 같다.

```text
r0 = 0x00000002
r1 = 0x0885D93C
pc = 0x0010A894
lr = 0x001042B0
table before call = all zero
```

caller는 `0x001042A0..0x001042AC`이다.

```text
0x1042A0 bl 0x10830C
0x1042A4 mov r1,r0
0x1042A8 mov r0,#2
0x1042AC bl 0x10A894
```

따라서 boot의 첫 setter call이 p2와 p4를 등록한다. 반복 software breakpoint 재개 중 devkitARM GDB 14.1이 다른 guest thread의 step-over에서 assertion failure를 일으켰다. 이 실패 이후의 반복 hit는 증거로 사용하지 않았다. p1의 writer/caller는 아직 확정하지 않았지만, 최종 non-NULL이라는 안전 판정에는 영향이 없다.

## CASE 분기

- CASE A (항상 NULL): 부정됨
- CASE B (조건부/별도 용도): 실제 token 소비처는 아직 미확정
- CASE C (정상 초기화되어 재사용 불가): 안전 설계 관점에서 채택

page 1이 title/movie/demo/codec에서 실제로 draw되는지와 무관하게, 이미 유효한 font allocation을 가리키므로 Korean page로 덮어쓰지 않는다.

## Page 7 decoder 영향 범위

전 text image에서 정확한 ARM `bic ..., ..., #0x6000`은 42곳이지만 그래픽 상태 bit mask 등 동명이 많다. token stream과 직접 연결된 cluster는 다음과 같다.

### Glyph bitmap lookup

- `0x0015E600` — main draw lookup
- `0x0015EC58` — second draw lookup

두 곳 모두 mask 후 static 81/82/83 또는 generic page table 계산을 한다. 실제 bitmap 선택을 바꾸려면 두 곳 모두 Korean range를 먼저 분기해야 한다.

### Width/placement

- `0x00184398`
- `0x0018445C`

두 곳 모두 mask 후 `0x8100` 이상이면 width 16을 선택한다. 현재 `A0xx & ~0x6000 == 80xx`이므로 draw만 수정하면 Korean token이 variable-width/ASCII 쪽으로 잘못 분류될 수 있다. 두 width path도 반드시 Korean range를 mask 전에 16px로 처리해야 한다.

### Parsing, wrapping, control-token comparisons

- `0x0015E0E8`, `0x0015E154`, `0x0015E1F8`, `0x0015E240`, `0x0015E290`
- `0x0015E420`, `0x0015E5A4`
- `0x00183A04`, `0x00183AC0`, `0x00183C7C`, `0x00183CD0`, `0x00183E18`
- `0x00183F28`, `0x00184080`
- `0x0024FB78` — page-relative token 변환/copy

이 경로들은 line break, numeric/control token, cursor advance 및 token 변환을 수행한다. 모두 수정 대상이라고 단정할 수는 없지만 A0xx를 먼저 별도 문자로 분류하지 않으면 mask 후 80xx control/ASCII 영역과 충돌할 수 있다. 실제 patch 전에 각 branch의 input/output contract를 테스트해야 한다.

최소 확정 수정점은 draw 2 + width 2 = 4곳이다. 안전한 decoder 확장에는 위 parser/layout cluster까지 포함한 회귀 검증이 필요하므로 “한 instruction patch”가 아니다.

## 확장 방식 비교

### A. 기존 page table 확장

- A0xx를 page 7로 유지하도록 모든 관련 mask/validation을 변경해야 한다.
- renderer 두 곳은 `table[7]`을 읽게 됨.
- 기존 table은 BSS에서 최소 7-entry만 증명됐으며 `table+0x1C`가 안전한지 미확정이다.
- writer/initializer도 8-entry table lifetime을 보장하도록 바꿔야 한다.
- 인접 BSS corruption 위험이 가장 큼.

판정: 권장하지 않음.

### B. Korean 전용 pointer

개념 설계:

```text
raw token이 A001..A3FF이고 low byte != 00이면
    Korean index = xx00 hole을 제외한 index
    base = korean_page_pointer
    glyph = base + index*64
그 외
    기존 mask와 page table lookup을 그대로 실행
```

- 기존 table 크기와 page 0~6 registration을 변경하지 않는다.
- draw 2곳에서 A0 range를 기존 mask 전에 분기한다.
- width 2곳에서 같은 range를 고정 16px로 분류한다.
- parser/layout에는 Korean token을 ordinary 2-byte glyph로 유지하는 공통 predicate가 필요하다.
- pointer는 table 바로 뒤가 아니라 별도의 검증된 writable storage에 둔다.
- movie/demo/codec 모두 같은 renderer와 pointer를 사용하므로 lifetime만 resident하게 확보하면 공용 가능하다.

판정: 최소 위험안. 기존 page table 확장보다 안전하다.

## Storage 설계

POC의 192B를 code.bin의 우연한 zero run에 넣는 것은 미사용 증명이 아니다. production 한 page는 65,280B이고 현재 translation corpus는 resident lifetime을 요구한다. 권장 구조는 resident asset에 Korean bitmap을 저장하고 초기 font load 완료 시 별도 `korean_page_pointer`를 한 번 설정하는 것이다.

신규 asset loader가 부담되면 isolated POC에서만 executable segment를 정식 확장하고 exheader segment size/repack을 함께 갱신하는 방식을 비교할 수 있다. trailing 224B padding이 보인다는 이유만으로 loader가 복사한다고 가정하지 않는다.

## 현재 번역 corpus의 이론 용량

현재 존재하는 자료만 읽었으며 번역을 만들거나 수정하지 않았다.

| source | unique Hangul syllables |
|---|---:|
| review v10 | 799 |
| codec translation JSON | 1,068 |
| movie CSV | 565 |
| demo CSV | 733 |
| four-source union | 1,119 |

한 Korean page만으로 모든 1,119자를 직접 담으면 99칸 부족하여 2 page가 필요하다. 그러나 현재 고정 shared glyph 191자는 모두 union에 포함된다. 기존 191자를 유지하고 **나머지만 Korean page로 보내면 928자**, 한 page에 들어가며 92칸이 남는다.

```text
전체 사용 한글: 1,119
기존 static/shared Hangul: 191
Korean page 필요 glyph: 928
Korean page capacity: 1,020
필요 신규 page: 1
남는 slot: 92
```

## 구조적 질문 답변

1. page 1은 미사용인가? **아니다. 최소한 항상 non-NULL로 초기화되며 재사용 안전성이 없다.** 실제 draw 소비처는 별도 미확정이다.
2. page 1을 세 매체가 공용 접근 가능한가? renderer table은 공용이나 기존 allocation을 덮어쓸 수 없으므로 POC 대상으로 사용할 수 없다.
3. page 1 token은 code patch 없이 처리되는가? generic page 1 token `8801..8BFF`는 기존 decoder가 정상 처리한다. 그러나 pointer가 기존 font용이다.
4. page 7 alias 제거 수정 경로는? bitmap lookup 2곳과 width 2곳이 최소 확정이며 parser/layout/transform cluster의 회귀 검증이 추가로 필요하다.
5. width/layout도 같은 token mask를 쓰는가? 그렇다. `0x184398`, `0x18445C`에서 직접 확인했다.
6. table 확장과 별도 pointer 중 안전한 것은? **별도 Korean pointer 방식**이다.
7. 한 page로 전체를 수용하는가? 전체 1,119자를 모두 신규 page에 넣으면 불가. 기존 static 191자를 유지하면 신규 928자로 한 page에 수용 가능하다.

## 종료 상태

- page 1 Korean POC: 안전 조건 불충족으로 미생성
- decoder binary patch: 설계 단계이므로 미실행
- `tools/mgs3d_global_korean_glyph_poc.py`: CASE A가 아니므로 미생성
- 원본 DAT/code.bin/RomFS: 변경 없음
- 다음 구현 후보: 별도 resident Korean pointer + A0xx predicate를 draw/width/parser에 공통 적용하는 isolated code patch POC
