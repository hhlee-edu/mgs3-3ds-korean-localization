# Stage `language=unknown` adjudication — 2026-08-21

The claim that arrived as a work order was **114 resources / 10,389 locations of
missing stage translation**. Reproduced exactly, then split by evidence: only
**67 resources / 6,360 locations** are a real gap. Applying the other 47 would
have written Korean into the Spanish branch.

## The gap is an application gap, not an authoring gap

`stage-translation-working.csv` has 1,571 rows. 1,257 carry `current_korean`
(status `UNTRANSLATED` = "Korean exists, not yet in the build" — the name is a
trap). Their `occurrences` sum to exactly **104,173**, matching the master count.

The 314 rows with no Korean are **all deliberately empty**, no exceptions:

| status | rows | why |
|---|---|---|
| `KEEP_ENGLISH` | 131 | fixed slot too small, or romanized proper noun (`SCOPE`, `LEECH`, `Rassvet`) |
| `DONOR_MISCLASSIFIED` | 183 | FR/ES text mis-scanned as English (`Egouts de Groznyj Grad`, `: RETOUR`) |

There is nothing in that CSV to translate. Filling those 314 would produce
Korean that cannot fit plus Korean rendered from French.

## Root cause of the 10,389

`tools/mgs3d_stage_apply.py` built its target set as

```python
if row["language"] == "english" and row["raw_hex"] in translations:
```

Locations labelled anything else were dropped **with no error and no report
entry**. The dry-run printed `errors: []` while 10,389 locations stayed English.
That silence is why this survived four builds.

104,173 − 93,784 applied (93,783 changed + 1 permanently excluded) = **10,389**.

## Splitting the 10,389 by evidence

| bucket | resources | locations | verdict |
|---|---|---|---|
| `donor` / basis `structure` | 46 | 3,835 | **correctly blocked** — inside FR/ES blocks |
| `unknown` / basis `none`, adjudicated Romance | 1 | 194 | **correctly blocked** — `WIG : Interior` |
| `unknown` / basis `none`, adjudicated English | **67** | **6,360** | **real gap** |

`unknown` does not mean "suspicious". It means the scanner had no vocabulary
evidence of its own AND block detection never reached the resource — which is
precisely what happens to short UI labels carrying no English function word.

### Adjudication method

Per location: nearest non-zero language vote to the left and to the right, using
the existing `EN` / `NON_EN` regexes, plus accent-escape (`0x1F`) density within
±8 resources. A ±40 window was tried first and rejected: language blocks are
adjacent, so a wide window straddles a boundary and reports MIXED as a
measurement artifact rather than as evidence.

Over all 6,554 `unknown` locations:

```
ENGLISH                    6172
STRADDLE_ROM_to_EN          274
ROMANCE                       98
EDGE_left_none_right_EN        9
EDGE_left_EN_right_none        1
```

The two non-unanimous resources were adjudicated individually:

- **`WIG : Interior`** — Romance evidence **1 resource away**, 296 accent-escape
  resources within ±8. Neighbours: `Pista de aterrizaje de Groznyj Grad`,
  `Completada la Misi<1f>tn Virtuosa`, `Laboratorio de armas`. Sits inside the
  Spanish block; Spanish left this string in English, which is exactly the trap
  `mgs3d_stage_language_blocks.py` was written to catch. **BLOCKED.**
- **`Baltic Hornets' Nest`** — nearest Romance evidence **33 and 81 resources**
  away, and **zero** accent escapes within ±8 at all 178 locations. Neighbours:
  `Indian Gavial`, `Vampire Bat`, `Emperor Scorpion`, `Tree Frog`. A Spanish
  fauna list would carry accents (`Murci<1f>elago`). **ENGLISH.**

The `RESULTS`-screen labels report one BOUNDARY location each purely because
they are resource 0 of their record and have no left neighbour.

## What the 67 are

Player-visible English. 62 of them were never translated anywhere in the game.

- **CURE injury menu** — `Gunshot Wound`, `Stab Wound`, `Electrical Burn`, `Burn`, `Sprain`, `Broken Nail`, `Blow Sustained`
- **Mission results screen** — `RESULTS`, `CONTINUES`, `ALERT MODE`, `SERIOUS INJURIES`, `MEALS EATEN`, `KINDS`, `PLANTS & ANIMALS CAPTURED`
- **Options menu** — `Select language.`, `Adjust screen position.`, `Adjust screen brightness.`
- **Camo descriptions** — `Woodland: For use in forested areas.`, `Splitter: For indoor-ops.`, `Kabuki: ...`
- **EVA prompts** — `Feed EVA.`, `Cure EVA.`, `Nothing in cage.`

## `r_sna02` — the same defect class, fixed at the source

`PERMANENT_EXCLUSIONS` was keyed `("r_sna01", 0, 479)` only, so the SAVE channel
label was held clean in `r_sna01` and translated in `r_sna02`.

A full-tree equivalence check (all 924 files, grouped by content hash) found
**20 duplicate groups covering 217 files, and exactly one group split in
staging** — `r_sna01`/`r_sna02` `scenerio.gcx`. The other 19 are intact.

The 4 differing bytes are at file offset `0x12F38`. The GCX body is not plain
text, so `'SAVE'` does not appear as a literal; XOR-ing each file's bytes against
its expected string yields the **same keystream `9a e2 fb f0`**, confirming
r_sna01 holds `SAVE` and r_sna02 holds the translated string:

```
r_sna01  c9 a3 ad b5  ^ 'SAVE'            = 9a e2 fb f0
r_sna02  18 f1 7a c6  ^ 82 13 81 36       = 9a e2 fb f0
clean    c9 a3 ad b5
```

Both keys are now excluded, and the new build has `r_sna01 == r_sna02` again.

## Tool changes

| file | change |
|---|---|
| `tools/mgs3d_stage_apply.py` | `PERMANENT_EXCLUSIONS` covers both r_sna01 and r_sna02; `--resolved-english` admits adjudicated `unknown` locations; report gains `held_total` / `held_locations` / `held_resources` so a held location can never again be silent |
| `tools/mgs3d_stage_final_gate.py` | knows the same adjudicated set; **new check: a permanently excluded location must come out byte-identical** |

The gate previously had no exclusion check at all — the exclusion lived only in
the writer, which is why the r_sna02 divergence passed every gate.

## Build and verification

`builds/diag-2026-08-21-stage-unknown-language/`

```
apply    changed_resources 100142   held_total 4029   errors 0
         held: donor/structure 3835, unknown/none 194   admitted 67
gate     169/169 files, pass True, errors 0
         fr_es_unchanged True   control_code_preserved True
         permanent_exclusions_intact True
```

Accounting: 93,783 → 100,142 = **+6,360 admitted − 1 newly excluded (r_sna02)**.

**Negative test** (the check is not vacuous): re-introducing the exact r_sna02
defect into a copy of the new build makes the gate fail with one error and only
one — `permanently excluded location changed ('r_sna02', 0, 479)`.

## Staging provenance

The RomForge staging tree is the `diag-2026-08-20-stage-repad` build for
**168/169** files; `r_sna01` is the sole exception because the SAVE fix landed
there after that build. Appended glyph-page tails are identical across all 169.
Re-splicing this build would change **94** files.

## Not done

Nothing is staged and nothing is committed. `WIG : Interior` (194 locations) and
the 46 structural-donor resources (3,835 locations) remain held **by design** —
they are not a backlog item.
