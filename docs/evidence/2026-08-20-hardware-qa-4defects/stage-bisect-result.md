# Stage bisection result and root-cause analysis

Date: 2026-08-20. Status: **analysis only. Nothing modified.** No commit, no push,
no CCI. Staging still holds the final discriminator (clean v1.0 + `v001a` +
`v005a_0`).

## Bisection outcome (8 hardware rounds)

| symptom | culprit named by set algebra |
|---|---|
| save (SAVE contact label) | `romfs/stage/r_sna01/scenerio.gcx` |
| boss (The Boss -> EVA) | `romfs/stage/v001a/scenerio.gcx` |
| tom (Major Tom name) | `romfs/stage/v001a/scenerio.gcx` |
| titlearea (title save-slot area name) | `romfs/stage/title/scenerio.gcx` |
| profile (PROFILE 04/04) | `romfs/stage/v007a_0/scenerio.gcx` |

## The attribution is confounded -- and the proof is already in hand

**`stage/r_sna01/scenerio.gcx` and `stage/r_sna02/scenerio.gcx` are byte-identical**,
in clean *and* in production:

```
clean       83,478 B   sha b7aaf10dc6e0aef5   (both)
production 500,348 B   sha c325c95d8c9c1914   (both)
```

Round "optimized 16" applied `r_sna02` and SAVE came back **ok**.
Round "optimized 9" applied `r_sna01` and SAVE came back **ng**.
Two identical files cannot produce different results, so the discriminator is
not file content -- it is **which stage is resident when the symptom is
observed**.

The save data confirms it. `tools/mgs3d_save_tool.py show` reports
`room 'r_sna01'` / `stage 'v001a'`, which is exactly the pair the bisection
named for save and for boss/tom.

So the bisection did not find four corrupt files. It found **the stages that are
loaded at the moment each symptom is visible.** The defect is a property of the
production stage build in general, triggered through whichever `scenerio.gcx` is
resident.

One point the model does not yet explain: PROFILE resolved to `v007a_0` rather
than to the save's own stage. Either PROFILE was observed from a different point
in the game, or that screen pulls from a different resident stage. Worth
pinning down before acting on it.

## What is actually different in a production scenerio.gcx

Parsed with the shared GCX parser (`stage/*/scenerio.gcx` is one codec.dat
record), original region only, clean vs production:

| check | culprits | controls |
|---|---|---|
| records | 1 / 1 | 1 / 1 |
| resource count | unchanged | unchanged |
| record raw size | unchanged | unchanged |
| `string_resources_offset` / `resource_table_offset` / `font_data_offset` / `proc_offset` | **unchanged** | unchanged |
| resource `table_word` (pointer/index) | **0 changed** | 0 changed |
| resource byte length | unchanged | unchanged |
| resource data | changed | changed |

`r_sna01` 594 resources / 159 changed -- and `r_sna02`, `v007a`, `s211a` show the
**same counts** as their culprit twins. There is no structural marker that
separates culprit from control, because there is no per-file defect.

Changed resources are ordinary translations fitted into the identical byte
budget, e.g. `Bare hands:<0A>No weapon equipped...` (185 B) -> Korean (185 B).

## The one real structural change: an appended region

Every one of the 169 production stage files is **much larger than clean**
(+270 KB to +417 KB), zero-padded from the original EOF and then carrying the
Korean glyph page. Consequences measured:

- All 169 clean files parse cleanly; **all 169 production files fail** the record
  walk once it runs into the appended region. Universal, so not a discriminator
  by itself -- but it means the on-disk file is no longer a well-formed GCX.
- The appended page does **not** start at a constant offset. Measured starts run
  from `0x56025` to `0xAC8E9`; **0 of 169** start at `0x56000`, the constant the
  code cave adds in `*(0x008E1618) -> [0x4C] + 0x56000`.
- **90 of 169** stages have clean content that already extends past `0x56000`,
  `v001a` (489,441 B) among them.

## Most likely root cause

Not a corrupt scenerio.gcx, and not a pointer/index/table fault -- those are all
measured unchanged. The evidence points at **the resident Korean glyph page and
the base-pointer arithmetic that reaches it**: loading a production stage changes
the runtime font state, and any UI string drawn while such a stage is resident
loses its glyphs. That is the same mechanism as the already-documented and still
unfixed `project_mgs3d_global_page_base_bug` (table[2] is a shared font slot;
the codec steals it and the base points at zeroed memory).

Supporting detail: the clean stage text contains the `#{ ... }#` button-prompt
markup built from the alias tokens this project already found the code hooks
mis-capturing -- e.g. `Ready w/ Aim Button (<80>#<A0>{<A3><1E><80>5<C0>...`.
Production preserves those sequences unchanged.

## Minimal fix candidates -- proposals only

- **M0 (no build).** Settle the loaded-stage model against PROFILE: record which
  stage the save is in when PROFILE 04/04 is observed broken. If it is not
  `v007a_0`, that single data point either confirms the model or breaks it.
- **M1 (no code).** Rebuild one stage's `scenerio.gcx` *without* the appended
  glyph page (translation applied, page omitted) and test that stage. Separates
  "the appended page" from "the translated text" -- the two are still confounded
  in every build so far.
- **M2 (no code).** Rebuild one stage with the page appended but the text left
  clean English. The mirror of M1; together they isolate which half carries the
  defect.
- **M3 (code, last).** Instrument `*(0x008E1618) -> [0x4C] + 0x56000` under GDB
  while a production stage is resident and read the resulting base. The repo has
  a working attach recipe in `feedback_citra_azahar_gdb_debugging`.

M1 and M2 are the cheapest pair that actually splits the remaining variable.
Nothing has been changed.
