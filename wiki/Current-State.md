# Current State

The technical single source of truth. Reconciled 2026-08-13 from `docs/WIKI.md`,
`docs/INDEX.md`, `HANDOFF.md` and the dated docs in `wiki/History/`. Where two
documents disagreed, the newer *evidence* wins and the older claim is recorded
under Invalidated — never deleted, never silently overwritten. See
[Decisions](Decisions.md) for *why*, [History](History/) for the raw session
record.

---

## Confirmed

### v0.93c — 네 컨테이너 스테이징 + 교차 검증 도구 (2026-08-22, newest)

전체 기록: [`docs/HANDOFF-2026-08-22.md`](../docs/HANDOFF-2026-08-22.md).
자료 색인: [`docs/SOURCES.md`](../docs/SOURCES.md).

- **텍스트 컨테이너는 다섯이다** — `codec.dat` · `movie.dat` · `demo.dat` ·
  `stage/*/scenerio.gcx` · **`vox.dat`**. `vox.dat`은 2026-08-21에 발견됐고
  6개월 가까이 "clean과 바이트 동일"이라는 기록만으로 지나쳐졌다.
  **무변경 확인은 안전성의 근거이지 범위의 근거가 아니다.**
- **번역 오매핑은 문자열 유사도로 안 잡힌다.** 한국어 자체는 멀쩡하고 영어와는
  언어가 달라 비교가 성립하지 않는다. 우리 번역과 한국어 대사집이 둘 다 서사
  순서를 갖는다는 점을 이용해 정렬해야 드러난다
  ([`docs/crossvalidate.md`](../docs/crossvalidate.md), 검출기 D1~D9).
- **정렬 기반 검출만으로는 부족하다.** 실플레이 발견 5건 중 D1~D4가 잡은 것은
  1건. 정렬에 의존하지 않는 D5~D8을 넣고 4/5가 됐다.
- **`vox.dat`은 자기 안에 대조 기준을 갖고 있다.** 큐마다 EN + FR/DE/IT/ES가 같은
  타이밍에 들어 있어 모든 줄에 전문 번역 4개가 정렬돼 있다
  ([`docs/vox-donor-check.md`](../docs/vox-donor-check.md)). 외부 자료가 필요 없다.
- **바이트 예산 통과와 화면에 들어가는 것은 다른 문제다.** vox 자막 31곳이
  `max_bytes`는 통과하면서 줄바꿈이 사라져 가로로 넘쳤다.
- **byte-fit PASS 기록은 바이너리가 바뀌면 못 믿는다.** 2026-08-17에 PASS로
  기록된 3건이 현재 바이너리에서 FAIL(2~5바이트 초과). 1바이트 여유로 통과한
  기록이 여럿이었고 그 사이 레코드 구역이 바뀌었다.
- **`errors: []`는 "할 일 없음"이 아니다.** 적용 기록만 있고 바이너리에 안 실린
  5건이 있었다 — `accept` 공란 + 낡은 `blocker`, 그리고 병합 전 마스터로 만든
  빌드 입력.
- **PERSONAL DATA 영문 유지는 결정 사항이고 마스터에는 한국어가 남아 있다.**
  단순 재빌드는 그 결정을 되돌린다. 빌드 입력에서 26,919곳을 제외해야 한다
  (`translation/40_build_input/2026-08-22/hold-locations.json`). 같은 방식으로
  도너 FR/ES 9곳의 회귀도 걸러진다.


### v0.81 hardware defects — root-caused 2026-08-16 (newest)

Full evidence: [`docs/v0.81-hardware-defects-rootcause-2026-08-16.md`](../docs/v0.81-hardware-defects-rootcause-2026-08-16.md).
Analysis only — no data, apply, staging or build change was made.

- **Codec English residue is a duplicate-propagation gap, not a fitting
  problem.** The master CSV dedupes strings and records every position in
  `locations`; the build input holds **only the canonical `(gcx, resource)`**.
  Attribution over all **211,458** English display_text location instances in the
  staged `codec.dat`, zero residual: duplicate never written **193,138
  (91.34%)**, master has no Korean 10,265 (4.85%), Korean in build 8,009
  (3.79%), **byte-capacity drops 30 (0.01%)**, `accept≠yes` 16 (0.01%).
  Measured directly: canonical locations 7,971 Korean / duplicates **0 Korean,
  193,162 English**.
- **Real codec Korean reach is 3.79% of in-game locations** (3.0% counting
  dialogue only), not the 8,441 units the build reported. The optional-call
  library records (gcx ~1403-1459, ~1,764-1,792 lines each) are **0%**.
  `resource 0-13` of every GCX is a PERSONAL DATA/PROFILE prologue cloned from
  gcx 15, so every codec screen shows an English info card.
- **Propagation looks byte-feasible** — Korean is *shorter* than the English in
  the big records (gcx 1412: 116,455 → 82,866 B, −33,589). Estimate; re-run the
  real per-GCX capacity gate before relying on it.
- **The `추`/`션` corruption is the same defect as `억`, and the same family as
  the v0.69 외/워/백/업/팀 report.** Both post-v0.80 reports are consecutive
  subtitles in **demo record 5, offsets 11,537,428 and 11,537,816** (the opening
  cutscene). In each line the broken characters are *exactly* the global-page
  (`0x84xx-0x87xx`) ones; all fixed (`0x81xx-0x83xx`) characters render. Across
  every hardware report: 11/11 broken are global-page, 39/39 correct are fixed.
- **That defect is not a data defect.** Verified byte-perfect: `추`=`845E`
  (index 93), `션`=`84E0` (index 223), `억`=`846E`; bitmaps non-blank and
  correctly formed at 16×16 2bpp; **169/169** staged `scenerio.gcx` carry the
  exact 65,280 B page; staged `demo.dat`/`movie.dat` bytes correct at all three
  offsets.
- **Exposure:** global-page characters are 17.6% of all Korean characters, but
  **78-87% of accepted lines contain at least one** (movie 83.7%, demo 78.0%,
  codec 87.0%). Respelling around it is not viable — all 931 characters are
  affected.
- **The shipped CCI carried correct data.** Scanning
  `Romforge\output\MGS SNAKE EATER 3D_Repack___.cci` (3,303,145,472 B,
  2026-08-16 01:28 — the tested build) finds the exact Korean byte strings for
  all three reported lines: the `추`/`션` demo subtitle ×1, the movie one ×1, and
  the `억` subtitle ×2 (matching demo offsets 11,537,428 and 533,694,288). So the
  corruption is not a build or packaging fault.

### Duplicate propagation — dry run 2026-08-16

Full evidence: [`docs/duplicate-propagation-dryrun-2026-08-16.md`](../docs/duplicate-propagation-dryrun-2026-08-16.md).
Scratch only; **nothing staged**.

- **Propagation costs no bytes — it frees them.** New tool
  `tools/mgs3d_codec_expand_locations.py` expands 8,478 → **201,482** units; the
  shipped capacity gate then drops **0** with **0 failing GCX**. The same gate on
  the canonical-only input reproduces v0.81 exactly (8,478 → 8,441, 37 dropped,
  31 failing), which is what makes the expanded verdict credible.
- **Why:** replacing more strings makes a record *smaller*. Korean at 2 bytes per
  syllable is shorter than the long English sentences, so once every string in a
  record is replaced it shrinks well under its original size. The 31 failures came
  from swapping only one or two strings each — individually longer than the short
  English they replaced, with no compensating saving. **The 37 codec rows the
  worklist tracks as capacity drops are an artefact of propagating too little.**
- **Verified layout-neutral.** Rebuilding every record with
  `preserve_layout=True`: 2,264 of 2,326 records changed, **0 changed size**,
  total `67,204,976 → 67,204,976` (delta +0), sha256 `40eead32…`.
- **Reach measured on the built file: 3.79% → 94.94%** (+192,759 locations), and
  the `dropped_for_capacity` category goes to **0**. The residual is the 10,265
  locations whose master row has no Korean at all.
- **`mgs3d_codec_tool.py apply` is the wrong tool for a safe codec build** — it
  omits `preserve_layout=True`, so it may grow records, and it is quadratic
  (`record.resources()` once per unit, each re-decrypting the record's whole
  string region: 13+ min without finishing at 201,482 units).
- The expander's byte-identity guard refused **411** locations across 16 canonical
  rows, all French case differences — which surfaced that **42 accepted non-donor
  rows are actually French (34) or Spanish (8)** mislabelled `language=en`.

### New tools (2026-08-16)

| tool | purpose |
|---|---|
| `mgs3d_translation_coverage.py` | the missing gate: reach measured over *binary* locations, per-cause attribution, `--min-reach` threshold, detector control against the pristine build |
| `mgs3d_codec_expand_locations.py` | copy canonical translations to duplicate locations, guarded by byte identity |
| `citra_gdb_mi_controller.py anchor` | one-shot read of both glyph-base formulas (`obj[0x4C]` and `table[2]`) plus the `추`/`션` glyph slots, using no breakpoints |

### Resident asset / global Korean glyph track (newest)
- **Media max-safe01 rejected (2026-08-13):** its inherited stress trampoline
  intercepted only `0x8401..0x8440`. Runtime observation showed `양` (`0x8451`)
  and `써` (`0x84A4`) corrupted while the earlier `호프번` probe passed. This
  isolates the failure to the stale 64-glyph range bound, not page residency or
  bitmap layout. A full-range trampoline rebuild is required.
- **Clean baseline verification PASS (2026-08-13).** V0a, V0b, V0c, V1 and
  V2 passed their scoped checks on the USA baseline. The clean integrated CCI
  SHA-256 is `D5261ED99FED1FEECA7D4061B75BB9D890FF65EFDF5DD25AC987536755F3C058`.
- The controlled renderer probe displayed `ABC 호프번 XYZ`, directly
  confirming tokens `0x8401..0x8403`, the trampoline and `table[2] + K` lookup.
- Three distinct resident bases each matched the expected first 4 KiB,
  4096/4096 bytes. This is a sampled runtime PASS, not a claim that all 169
  stages were traversed in game.
- Full-page static validation PASS: 928 unique characters/tokens, no `xx00`
  token, all 928 glyph blocks nonzero, 92 zero-filled spare slots, and
  deterministic page/map reproduction.
- **Canonical-master integration correction:** the frozen clean-baseline corpus
  had 928 global glyphs, but the reorganized canonical demo master contains one
  additional required syllable, `칸` (U+CE78). The build-input v2 map preserves
  all 928 verified assignments and appends only `칸` at `0x87A4`: 929 global +
  191 shared-static = 1,120 characters, with 91 slots free.
- Current-master encoding preflight PASS: movie 689/689, demo 2,228/2,228 and
  codec 26,846/26,846 authoring units encode with the combined map. String
  capacity remains separate. Whole-record-safe subsets are movie 247 and demo
  732; maximum row-level fixed-layout subsets are movie 585/689 and demo
  1,871/2,228. All four size-preserving DAT candidates pass full content
  verification with zero appended font bytes.
- `scenerio.gcx` resident load size **= the RomFS file size itself**. Not external
  metadata, not a container field, not a fixed request argument.
  (`wiki/History/load-size-source-confirmed-2026-08-13.md`)
- **Bytes appended after EOF do become resident.** Verified byte-for-byte live.
- Korean page live comparison: **4096/4096 bytes match at three distinct
  resident bases** (the earlier 192-byte result remains valid evidence).
- `K = 0x56000` in the current 169-stage build.
- Korean page VA `= table[2] + 0x56000`, and the trampoline's own formula
  `*(0x00A46FE0) + 0x56000` resolves to that same address.
- `table[2] @ 0x00A46FE0`.
- Descriptor entry layout: `+0x00 tag / +0x04 ptr / +0x08 size`, stride `0x14`.
- Descriptor tag `0x02180720` is a **resource-class tag** for "stage scenerio",
  identical across `title` and `v001a` — not a per-file hash.
- **169 stages**; page2 offsets come from the **parser formula**.
- GCX containers have **no self-size field** (full u32 scan of 4 files, 0 hits).
- `scenerio` / `.gcx` strings are **not** in `code.bin`. Stage paths are built as
  `stage/%s/` (VA `0x0088F270`, builder `0x0012F324`); extension table
  `0x00908368` stride 8, `'gcx'` @ `0x009083E8`.
- `FSFILE_GetSize` IPC stub is unique: `0x008370DC`. Its only wrapper
  `0x008671B4` is reached solely through vtable slot `0x008ADE24`.

See [Glyph System](Glyph-System.md) for the full mechanism.

### Structure and relocation
- **The governing principle:** a structural unit's own boundary cannot move;
  growth must be funded from *that unit's own* slack — demo/movie from the
  scene's trailing zero padding, codec from donor-reclaimed bytes inside the GCX.
- `demo.dat` is a **130-scene multiplex container**, `kind = (stream<<16)|type`,
  every scene aligned to `0x800`, walked end-to-end with 0 desync and 0
  undecoded bytes. type=2 media payload, type=4 subtitle records, type=16 scene
  boundary, type=240 per-scene trailer.
- GCX53 relocation root cause: three procedure-table offsets past the inner
  `0x1000` boundary (`+0x64/+0x70/+0x7C`, low 24 bits). Descriptor `0x0200457B`
  selects a fixed container start and must **not** be moved with it.
  Generalized as `relocate_gcx_internal_offsets(record, old, new)`.
- `codec.dat` distributed grow is usable **when accompanied by procedure/internal
  low-24 relocation** — 7 spread GCX, +16,720 bytes, 2,312 GCX shifted,
  full 2,326-GCX / 216,705-word verifier pass, Azahar-verified.
- `movie.dat`/`demo.dat` grow relocation verified 2026-08-10, including a
  71-record grow (+225,424 B) and displacement of the real first video.
- `codec.dat` = **2,326 GCX**. 3DS `movie.dat`/`demo.dat` record structure fully
  decoded with lossless round-trip.

See [GCX Format](GCX-Format.md) and [DAT Formats](DAT-Formats.md).

### Source material
- PS2 `MOVIE.DAT` is plain MPEG-2 PS; **Korean subtitles are hardsubbed**, so no
  extractable extractable reference movie text exists. the script reference is therefore the
  effective movie/demo Korean source, not merely a diagnostic.
- The "western 5-language" `movie.dat` structure is **this project's own
  reconstruction**, not stock Japanese. The golden build depends on it, so it
  stays.
- 3DS English text is a **work-in-progress placeholder**, not shipped final text
  — reducing English to buy capacity is cheap.
- the script reference author's own colour boxes classify lines: grey = cutscene
  (movie/demo) 933, green = codec 406, no box 1,692.
- `LA2` = Nintendo DARC; `ARC` = Capcom MT Framework.

See [Translation](Translation.md) and [Matching](Matching.md).

---

## Invalidated

Each line is a claim that was believed true and is now disproven. The original
document is kept as evidence in [History](History/); only the conclusion is
retired.

| Retired claim | Superseded by |
|---|---|
| "EOF-appended data is not resident" (2026-08-12) | 2026-08-13 live byte-for-byte match |
| "Resident read extent = original file size, so append is capped" (2026-08-13, 1st session) | 2026-08-13 2nd session: size follows the RomFS file size |
| `K = 0x35000` | current build uses `K = 0x56000` |
| stage count = 91 | **169** |
| signature-only page2 discovery | parser formula (signature scan missed 78 of 169) |
| "demo growth is limited to exactly 1 record; 2+ inherently unsafe" | scene-start rule; the failing sets all happened to touch a scene before #127 |
| "a demo record has an absolute size cap around 5–6 KB" | explained by scene-boundary displacement, not a record cap |
| "codec.dat growth is impossible" | distributed grow + low-24 relocation works |
| "movie/demo grow modes are deployment-banned" | 2026-08-10 relocation validation (**note:** `docs/WIKI.md` still asserts the ban in §3.1/§6 while its own appended 2026-08-10 section contradicts it) |
| `--size-neutral-reclaim` for movie/demo | replaced by `--fixed-layout-reclaim` |
| "GCX1412 holds 986 Japanese glyphs" | measured on the JP file by mistake; EN original has 0 glyph slots |
| demo parser "2,091 entries" | **333 records / 11,296 entries** |
| Japanese source reassembly pipeline | abandoned in favour of the English→Korean pivot |
| `weak_foreign_anchor()` | removed; misclassified English as foreign |
| fixed-radius batch dialogue matching | rejected; GCX adjacency does not imply conversation |
| "codec English residue is translated text dropped for byte capacity" (v0.80/v0.81 staging docs) | 2026-08-16 attribution: capacity explains **30 of 203,449** instances (0.015%); 91.34% is the duplicate-propagation gap |
| "`억` corrupts because of a stale anchor right after a codec call ends" (v0.81 staging doc) | 2026-08-16: the line is demo record 5 @11,537,428 — the **opening cutscene, before any codec call** — and 11,537,428 is that occurrence, not an alternative location |
| "v0.80 shipped correct rendering" (v0.81 staging doc) | 2026-08-16: global-page characters still fail; `code.bin` is identical in v0.80 and v0.81, so both reports are one defect |

---

## Unverified

- Exhaustive visual review of the current 929 global glyphs in natural
  translated dialogue (15 labelled review sheets are prepared).
- Exhaustive runtime traversal of all 169 stages (not required for the clean
  baseline verdict; three distinct stages were sampled).
- Whether `movie.dat` uses the same scene container as `demo.dat` (assumed, never
  directly confirmed).
- The leading ~646 KB header/index region of PS2 `DEMO.DAT`.
- Full decode of the `kind=2` block.
- The exact count at which simultaneous codec GCX grow breaks.
- The role of the 1,692 "no colour box" the script reference lines.
- Whether grow is safe for *arbitrary* GCX at *arbitrary* sizes (validated range
  only).
- The large `codec_selected_static_media*` / `early-priority-selection*` JSON
  cluster, still under `analysis/script_ref/` (not physically moved — see
  below) — confirmed to be **active in-progress translation work**
  (2026-08-13), not yet reconciled with the master corpus.
  See [Translation](Translation.md#in-progress-material).

---

## Current Build

**v0.93c — 2026-08-22.** 매니페스트: `builds/release-v0.93c/manifest.json` (R6).
CCI는 아직 만들지 않았고 실기 검증도 없다.

| 파일 | SHA-256 (16) | 출처 |
|---|---|---|
| `romfs/codec.dat` | `cb83adca9364a1a1` | `diag-2026-08-22-codec-final` |
| `romfs/movie.dat` | `72dfb3a80770e448` | `diag-2026-08-22-codec-qa377` |
| `romfs/demo.dat` | `25c8f258d95d9c7c` | `diag-2026-08-22-enscript` |
| `romfs/vox.dat` | `6788330fe623512f` | `diag-2026-08-22-vox-linebreak` |

스테이징 트리 둘 — romfs는 양쪽이 동일하고 차이는 `partition0`의
`code.bin`/`exheader.bin`/`plain.bin` 셋뿐이다.

```
Romforge/output/unpacked/                  1.1 standalone  924 files 3,257,137,963 B
Romforge/output/unpacked-v0.93a-staging/   v0.93a          924 files 3,257,034,663 B
```

**RomForge는 `unpacked/`만 본다.** 되돌리려면 폴더 이름을 맞바꾼다 — 복사가 아니라
rename.

### 골든 CCI — 바이너리는 없지만 재현 가능

- 기록된 골든: `MGS SNAKE EATER 3D_Repack_______.cci` (밑줄 7개),
  3,248,410,624 B, SHA-256 `3BD843…E6504`.
- 2026-08-13에 `C:/Users/hhlee`와 `D:` 전체의 `.cci` 11개를 해시했고 일치 없음.
  두 개가 **크기만** 같다 — 크기 충돌이지 골든이 아니다 (R4).
- 재현 입력: `archive/old-data/script_ref_archive_2026-08-07/staging_tom_codec_original_media/`.
  기록된 입력 해시 5/5가 바이트 일치한다.
- ⚠️ **이름 충돌 위험:** `Romforge/output/`이 밑줄 6개까지 차 있어 다음 repack이
  골든의 파일명을 쓴다. 리팩 전에 이름을 바꿀 것 ([R6](Conventions.md#r6-build-naming)).

## Current Data

번역 정본은 `translation/10_master/current/`에 있다. 경로는 주기적으로 바뀌므로
인용 전에 [Translation](Translation.md)과 `translation/10_master/README.md`를
다시 읽을 것.

| | 행 | 비고 |
|---|---:|---|
| `current/codec.csv` | 22,820 | 번역행 9,057 |
| `current/demo.csv` | 2,228 | |
| `current/movie.csv` | 689 | |
| `translation/vox/vox-translation.csv` | 2,691 | **정본이 `10_master` 밖에 있다** |
| `pending/runtime-corrections.csv` | 33 | 실기 교정 대기열, `status`로 관리 |

stage 정본도 아직 `10_master` 밖이다
(`translation/50_local_evidence/2026-08-19-stage-pretranslation-analysis/stage-translation-working.csv`).
**목표 형태는 `current/`에 codec·movie·demo·stage·vox 다섯 + `pending/` 하나.**

**백업은 `translation/10_master/archive/backups/`에 모았다** (2026-08-22, 41개 이동).
`translation/`은 gitignore라 git 히스토리가 없고 이 .bak이 유일한 롤백 수단이다.
46개 전부 SHA-256이 다르므로 중복 제거로 줄일 것이 없다 (R4). `INDEX.json`에 원위치와
해시가 있고, 정본별 최근 1개는 즉시 롤백용으로 원위치에 남겼다.

검수 산출물: `translation/10_master/review/crossvalidate/worklist.csv`
(통합·등급순, A 2 / B 55 / C 1,068), `translation/vox/donor-check-findings.csv`.

## Known Issues

### 해소됨 (기록 유지 — R8)

- ~~`HANDOFF.md`가 모순되는 세션 층을 쌓고 있다~~ — 2026-08-22에 R12 형식(여섯 항목)으로
  다시 씀. 과거 층은 `docs/HANDOFF-*.md`에 날짜별로 남아 있다.
- ~~RomForge romfs 트리 안에 `.bak`이 들어 있다~~ — 해소. 2026-08-22 점검에서
  두 트리 모두 이물질 0 (R7).
- ~~번역 커버리지를 재는 게이트가 없다~~ — 해소. `mgs3d_codec_final_gate.py`가
  **in-game location 기준**으로 잰다(현재 100.0000%, 233,700 locations). 그 밖에
  capacity overflow / missing glyph / layout preserved / DAT read-back /
  English residue를 함께 본다.
- ~~중복 전파 도구가 어느 빌드 절차에도 없다~~ — 해소.
  `mgs3d_codec_expand_locations.py`가 정규 파이프라인 2단계다
  (9,017 rows → 227,506 units).

### 열려 있음

- ⚠️ **`Current-State.md`의 Confirmed 절 상당수가 2026-08-16 이전 기준이다.**
  v0.93 계열, 1.1 이식, stage 언어 판정, `vox.dat` 발견이 반영돼 있지 않다.
  2026-08-22에 최신 절과 Current Build/Data만 갱신했다. 나머지는 미갱신.
- ⚠️ **정본이 세 곳에 흩어져 있다.** codec/demo/movie는 `10_master/current/`,
  vox는 `translation/vox/`, stage는 `50_local_evidence/...`. 다섯을 한자리로
  모으는 작업이 남아 있다.
- ⚠️ **`docs/WIKI.md`가 grow-mode 안전성에서 자기모순** (Invalidated 참조).
  `docs/INDEX.md`는 2026-08-12에서 멈춰 있다. 둘 다 이 페이지로 대체됐다.
- ⚠️ **골든 CCI 이름 충돌** — 다음 repack이 골든의 파일명(밑줄 7개)을 쓴다.
- ⚠️ **`builds/`가 9.9 GB이고 매니페스트가 대부분 없다.** 2026-08-22에
  `release-v0.93c/`만 R6 매니페스트를 갖췄다. `diag-*` 30여 개는 미정리.
- ⚠️ **검출기 D3/D5/D6는 근거가 하나뿐이라 오탐이 많다** (C등급 1,068건).
  영문 대사집이 2,164행뿐이라 codec 9,057행 중 428행만 붙는 것이 원인이다.

## Next

1. **CCI 리팩 + 실기 검증** — v0.93c 스테이징은 끝났고 CCI가 없다.
   리팩 전에 골든 이름 충돌을 피할 것 (R6).
2. **워크리스트 A 2건 / B 55건 검토** —
   `translation/10_master/review/crossvalidate/worklist.csv`.
3. **화자별 어투 정책 결정** — Zero/Tom의 존댓말이 프로젝트 전반에 섞여 있어
   한 줄짜리 결함으로 못 고친다. D2가 잡은 3건이 그것이다.
4. **정본 다섯을 `10_master/current/`로 통합** (R1/R3).
5. **`builds/` 정리** — 중복·구형 진단 빌드 정리와 매니페스트 부여 (R6).

## Do Not Reinvestigate

- Whether appended-EOF bytes are resident — settled, they are.
- Where the load size comes from — the RomFS file size.
- Whether GCX53 can move — it can, with low-24 relocation.
- Whether PS2 movie/demo hold extractable Korean text — they do not, hardsubbed.
- Whether codec growth is possible at all — it is.
- Any French / Spanish / German / Italian donor text as translation material.
- Whether the PS2 ISO needs recovering from the Recycle Bin — no, confirmed
  intentional, extracts are preserved.
- Whether the golden CCI can be found on disk — it can't; rebuild it from
  `staging_tom_codec_original_media/` instead.
