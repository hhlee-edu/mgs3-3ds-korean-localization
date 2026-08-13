# MGS3D A0xx Global Korean Glyph Binary POC

## 결과

별도 `korean_page_pointer`와 A0xx token decoder를 사용하는 isolated binary POC를 구현했으나 runtime에서는 실패했다. `ABC XYZ`는 표시됐고 A0xx 세 glyph는 모두 표시되지 않았다. 후속 GDB 검증으로 storage 문제와 parser 문제를 분리했다.

## A0xx 전달 판정

문자열 parser는 high-bit 문자를 2B big-endian token으로 읽는다. control/layout 경로에서 `bic #0x6000`으로 만든 복사본을 비교하지만 원본 stream pointer는 유지되며 draw와 width 단계가 token을 다시 읽는다. 따라서 raw `A001..A3FF`는 네 terminal mask 지점에서 식별 가능하다.

정적 분석에서는 중간 parser가 stream bytes 자체를 소비하는 것으로 보이지 않았으나 runtime 조건부 breakpoint 결과가 이를 반박했다. 테스트 자막이 화면에 표시되는 동안 두 terminal draw trampoline의 raw-A0xx breakpoint는 0회였다. 따라서 A0xx identity는 그 전에 `0x2000` flag normalization 또는 관련 parser/layout state 변환으로 손실된다.

## Korean token

```text
A001 = 가 = index 0
A002 = 나 = index 1
A003 = 다 = index 2
```

전체 범위:

```python
group, offset = divmod(index, 255)
token = 0xA001 + group*0x100 + offset

within = token - 0xA000
index = within - 1 - ((within - 1) >> 8)
```

`tools/mgs3d_global_korean_glyph_poc.py`에서 1,020개 전체 round-trip을 검증한다.

## Binary layout

기존 page table은 변경하지 않았다.

### Text trampoline

- 기존 text: VA `0x00100000`, pages `0x780`, declared size `0x77F8C4`
- trampoline: VA `0x0087F8C4`, 244B
- 새 declared size: `0x77F9B8`
- page count 변화: 없음

기존 text의 마지막 할당 page 안에서 declared size만 늘렸다. 사용 영역은 원본에서 전부 zero였으며 patch tool이 이를 재검증한다.

### Glyph와 pointer

- data segment: VA `0x008BA000`, pages `0x5C`
- 기존 declared size: `0x5BF20`
- 가나다 bitmap: `0x00915F20`, 192B
- 독립 pointer word: `0x00915FE0`, 값 `0x00915F20`
- 새 declared data size: `0x5BFE4`
- page count 변화: 없음

table `0xA46FD8` 뒤를 사용하지 않았다. 기존 data segment의 마지막 할당 page를 정식 initialized-data 크기에 포함했다.

## Patch sites

| address | original | 변경 |
|---|---|---|
| `0x0015E600` | `bic r1,r1,#0x6000` | draw trampoline 1로 branch |
| `0x0015EC58` | `bic r1,sb,#0x6000` | draw trampoline 2로 branch |
| `0x00184398` | `bic r0,r0,#0x6000` | width trampoline 1로 branch |
| `0x0018445C` | `bic r1,r1,#0x6000` | width trampoline 2로 branch |

fallback은 대체된 원래 `bic`을 실행한 뒤 정확히 다음 instruction으로 돌아간다. 따라서 A0xx가 아닌 기존 token path는 원래 lookup을 그대로 사용한다.

Korean draw path는 raw high byte가 A0..A3이고 low byte가 nonzero인지 확인하고, page 내 xx00 hole을 제외한 index를 계산한다. 그 후 `*(uint32_t *)0x00915FE0 + index*64`를 사용한다.

width path는 같은 predicate에 대해 기존 fixed glyph와 같은 16px를 설정한다.

## Glyph 생성

새 rasterizer를 만들지 않고 기존 `mgs3d_gcx_font_tool.render_character()`와 `encode_glyph(..., "linear")` 경로를 재사용했다.

- font: `C:\Windows\Fonts\malgun.ttf`, 16px
- format: 16x16, 2bpp linear, glyph당 64B
- 총 192B

## Test movie

- source: `movie_live_base.dat`
- record 0, entry 4
- absolute offset: 164
- 기존 capacity: 36B
- 원문: `Jack, I've got some important news.`
- POC: `ABC 가나다 XYZ`
- encoded body: `41424320 A001 A002 A003 20 58595A 00`
- 파일 크기: 245,520B로 동일
- record/layout 이동: 없음

영문 앞뒤와 세 한글을 함께 배치하여 glyph advance를 눈으로 판정할 수 있다.

## 검증 결과

- source decompressed SHA-256 gate: pass
- 네 원본 instruction word gate: pass
- trampoline source area zero gate: pass
- data extension area zero gate: pass
- ARM branch range/alignment: pass
- patched branch target disassembly: pass
- Korean token round-trip: 1020/1020 pass
- glyph size: 3x64B pass
- BLZ compress/decompress round-trip: pass
- exheader text/data size: pass
- movie size/layout: pass
- 원본 파일 덮어쓰기: 없음
- 실제 화면: fail (`ABC XYZ`만 표시, 가나다 누락)
- isolated CCI 생성: pass (`84F480F7D2D45137A17E1F1137BE175C20EE57E6E0AC3EBA9984B7A6C65D0BC6`)
- Azahar 실행 후 15초 생존/응답: pass

## 산출물

```text
tools/mgs3d_global_korean_glyph_poc.py
analysis/global_korean_glyph_poc_2026-08-12/
  code.poc.bin
  code.poc.decompressed.bin
  exheader.poc.bin
  movie.poc.dat
  patch_manifest.json
  test_results.json
  korean_token_map.csv
  poc_trampolines.s/.o/.elf/.bin
  stage/partition0/exefs/code.bin
  stage/partition0/exheader.bin
  stage/partition0/romfs/movie.dat
  MGS3D_A0XX_GANADA_POC.cci
```

## 실행

```text
python tools/mgs3d_global_korean_glyph_poc.py --analyze
python tools/mgs3d_global_korean_glyph_poc.py --build-poc
python tools/mgs3d_global_korean_glyph_poc.py --verify
```

Romforge에는 `stage/partition0`의 세 파일만 대응 위치에 놓고 새 CCI를 생성한다. 적용 전 기존 세 파일을 hash와 함께 백업해야 한다.

## 화면 성공 판정

movie record 0 entry 4가 표시될 때 다음을 확인한다.

1. `ABC 가나다 XYZ`가 순서대로 표시된다.
2. 세 글자가 겹치지 않고 16px 단위로 전진한다.
3. ABC와 XYZ의 기존 영문 glyph가 정상이다.
4. center/box 정렬과 line wrap에 이상이 없다.
5. 다른 기존 fixed Korean/영문 subtitle에 변화가 없다.

32~64자 stress page와 928자 generator는 만들지 않았다.

### Runtime 실패 분리

v1에서는 trampoline code가 정상 로드됐지만 data trailing storage `0x00915F20..0x00915FE3`가 전부 zero였다. loader가 해당 영역을 initialized payload가 아니라 zero-fill 대상으로 처리했다.

v2에서는 bitmap을 text extension `0x0087F9B0`으로 옮겼고 runtime 192B가 build image와 일치했다. 그런데 테스트 자막 재생 동안 raw A0xx 조건부 breakpoint가 draw path 양쪽 모두 0회였다. 즉 두 terminal draw/width site만 수정하는 설계는 불충분하다.

프롬프트의 중단 조건인 “parser/layout에서 A0xx가 안전하게 전달되지 않음”이 runtime으로 확인됐으므로 추가 binary patch를 억지로 진행하지 않았다. 다음 최소 연구 대상은 `0x15E0E8..0x15E5A4`와 `0x183A04..0x184080`의 normalization cluster에서 A0xx identity를 보존하는 공통 predicate다. draw 네 곳만 수정하는 방식은 폐기한다.

Romforge live code/exheader/movie는 POC 전 hash로 복구했다.

## 실패 분류

- 즉시 crash: segment size/exheader 또는 trampoline 실행 문제
- 영문은 보이나 A0xx 누락: parser/token 소비 또는 Korean predicate 문제
- 깨진 bitmap: pointer VA/lifetime 또는 2bpp layout 문제
- 글자 겹침: width path 누락
- draw path 일부에서만 보임: 두 renderer path의 state별 사용 차이

실패 시 기존 page를 덮어쓰는 방식으로 우회하지 않는다.

## 2026-08-12 renderer 분리 POC 성공

사용자 화면 검증에서 `0x8401..0x8403` global page-0 token 세 개를 테스트용으로
가로채 resident text 영역의 `가/나/다` bitmap으로 연결한 빌드는
`ABC 가나다 XYZ`를 정상 표시했다.

따라서 text segment 내부 resident glyph의 load/lifetime, 별도 base에서
`index * 64`로 계산하는 draw lookup, 16x16 2bpp bitmap, 16px width/advance,
고정 record 크기의 movie patch는 runtime 성공으로 확정한다.

반면 raw `A001..A003`와 alias `8001..8003` 빌드는 모두 세 글자를 누락했다.
실패 범위는 glyph storage나 renderer가 아니라 A0xx가 layout/render item으로
전달되는 token namespace에 한정된다.

성공본은 기존 global page-0 slot 세 개를 진단 중 가로챈 것이므로 독립 Korean page의
최종 성공으로 주장하지 않는다. 다음 변경은 기존 page slot을 덮어쓰지 않고
Korean token identity를 layout 전체에서 보존해야 한다.
