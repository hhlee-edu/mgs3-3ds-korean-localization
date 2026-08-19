# codec 미번역 우선 선택 도구

`tools/mgs3d_codec_untranslated_select.py`는 현재 191 빌드에서 영어로 남은 공식 한글 후보를
보여 주고, 사용자가 고른 문장을 191자 공용 글꼴과 고정 GCX 문자열 공간 안에서 우선
선택한다. 들어가지 못한 문장은 원본 영어로 유지한다.

현재 생성된 검토표:

`analysis/script_ref/codec-untranslated-review.csv`

- 전체 미번역 후보: 3,641개
- 공용 글꼴에 필요한 글자가 없는 후보: 3,609개
- 글자는 있지만 고정 문자열 공간이 부족한 후보: 32개

CSV에는 원본 영어, 공식 한글, 필요한 추가 글자, GCX 여유 바이트와 안정적인
`gcx/resource` 식별자가 들어 있다. 원하는 행의 `accept`를 `yes`로 바꾸고 `priority`를
작은 숫자로 줄수록 먼저 처리된다.

## 선택 계산

```powershell
python tools/mgs3d_codec_untranslated_select.py select `
  analysis/script_ref/staging_media_minimal/codec.dat `
  analysis/script_ref/codec_translation_static_media_191.json `
  analysis/script_ref/codec_selected_static_media_191_fixed.json `
  analysis/script_ref/codec_selection_static_media_191_fixed_report.json `
  analysis/script_ref/static_media_allocation_191.json `
  analysis/script_ref/codec-untranslated-review.csv `
  analysis/script_ref/codec-priority-output
```

도구는 다음 순서로 안전하게 처리한다.

1. 현재 실기 성공한 191자 배치를 기준으로 삼는다.
2. 요청 문장에 필요한 새 글자만, 기존 한글 문장 손실이 가장 적은 선택 글자와 교환한다.
3. 각 GCX에서 번역 문장 수를 최대화하면서 요청 문장을 우선한다.
4. 글꼴 191자 또는 문자열 고정 공간을 넘는 요청은 영어로 유지한다.
5. 선택되지 않은 요청과 기존 한글에서 영어로 돌아가는 문장을 JSON 보고서에 기록한다.

주요 출력:

- `codec_selected.json`: 새 codec 빌드 입력
- `static_allocation.json`: 두 resident HPK에 동일하게 적용할 191자 배치
- `priority-selection-report.json`: 신규 한글/영어 유지/교환 손실 명세

보고서의 `returned_to_english`가 예상보다 많으면 선택 행을 줄여 다시 실행한다. 원본 파일은
변경되지 않으므로 반복 검토가 가능하다.

## RomForge에 넣을 고정 크기 파일 생성

```powershell
python tools/mgs3d_codec_untranslated_select.py build-files `
  analysis/script_ref/staging_media_minimal/codec.dat `
  analysis/script_ref/codec-priority-output/codec_selected.json `
  analysis/script_ref/codec-priority-output/static_allocation.json `
  analysis/script_ref/integrated_191_candidate/romfs/stage/r_sna01/resident.hpk `
  analysis/script_ref/integrated_191_candidate/romfs/stage/r_sna02/resident.hpk `
  analysis/script_ref/codec-priority-files
```

`codec-priority-files` 아래에 RomFS 상대 경로로 `codec.dat`와 두 HPK가 생성된다. 도구는
codec 전체 크기, 2,326개 GCX의 시작/크기/string/font/procedure 경계, 두 HPK 크기를 모두
검증하고 `build-files-report.json`에 SHA-256을 기록한다. 기존 191 빌드의 movie/demo는
그대로 사용한다.
