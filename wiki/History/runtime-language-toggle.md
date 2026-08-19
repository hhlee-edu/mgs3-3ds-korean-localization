# 실기 검증용 한글/영어 전환 도구

`tools/mgs3d_runtime_language_toggle.py`는 원본 번역 입력을 수정하지 않고, 실기에서 문제가
발견된 문장만 원본 영어로 되돌린 새 입력 파일을 만든다. codec의 공간 확보용 donor 항목은
목록에서 숨기고 그대로 보존하므로 고정 크기 빌드의 용량 계산을 망가뜨리지 않는다.

## 1. 결정표 만들기

```powershell
python tools/mgs3d_runtime_language_toggle.py catalog `
  analysis/script_ref/runtime-language-decisions.csv `
  --codec analysis/script_ref/codec_selected_static_media_191_fixed.json `
  --movie analysis/english_bulk_final/movie_translation.csv `
  --demo analysis/english_bulk_final/demo_translation.csv
```

생성된 CSV를 Excel에서 열고 문제가 있는 행의 `action`을 `한글`에서 `영어`로 바꾼다.
식별자는 codec의 경우 `codec:GCX:RESOURCE`, movie/demo의 경우 파일 오프셋을 사용하므로
행 순서가 바뀌어도 같은 문장을 가리킨다. `note`에는 실기 증상을 자유롭게 기록할 수 있다.

## 2. 수정된 빌드 입력 만들기

```powershell
python tools/mgs3d_runtime_language_toggle.py apply `
  analysis/script_ref/runtime-language-decisions.csv `
  analysis/script_ref/runtime-language-output `
  --codec analysis/script_ref/codec_selected_static_media_191_fixed.json `
  --movie analysis/english_bulk_final/movie_translation.csv `
  --demo analysis/english_bulk_final/demo_translation.csv
```

한두 문장만 빠르게 시험할 때는 CSV를 편집하는 대신 식별자를 직접 지정할 수도 있다.

```powershell
python tools/mgs3d_runtime_language_toggle.py apply `
  analysis/script_ref/runtime-language-decisions.csv `
  analysis/script_ref/runtime-language-output `
  --codec analysis/script_ref/codec_selected_static_media_191_fixed.json `
  --english codec:15:14
```

출력:

- `codec_translation.json`
- `movie_translation.csv`
- `demo_translation.csv`
- `language-toggle-report.json`

codec에서 제거된 한글 번역 항목은 빌드시 원본 `codec.dat`의 영어 문자열을 그대로 유지한다.
movie/demo CSV는 해당 행의 `accept`만 비활성화하므로 원본 데이터가 유지된다.

## 3. 안전 규칙

- 항상 깨끗한 원본 3DS DAT에 출력 번역 파일을 적용한다.
- 이미 패치된 DAT 위에 다시 패치하지 않는다.
- `safe-fixed`/고정 레코드 모드로 빌드한다.
- 빌드 후 `mgs3d_verify_build.py`로 전체 크기와 모든 레코드 경계를 확인한다.
- 결정표에서 `영어`를 다시 `한글`로 바꾸고 적용하면 해당 번역이 복원된다.
