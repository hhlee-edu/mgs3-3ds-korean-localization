# A/B bisection of the 177 changed files

Date: 2026-08-20. Status: **step 1 staged, awaiting CCI + hardware test.**
No commit, no push, nothing fixed.

## Where this stands

Clean v1.0 renders PROFILE, Major Tom, The Boss and SAVE correctly. All four are
therefore a **regression in our change set**, not stock behaviour. That closes
the question the clean baseline was built to answer.

Two consequences:

- **The PERSONAL DATA text is exonerated.** D2 restored all 27,132 PERSONAL DATA
  resources to clean English, byte-exact and ASCII-only, and PROFILE stayed
  broken. So the cause is in one of the other changed files.
- **The 40-line / 290 B shortening worklist is parked**, not cancelled.
  `d2-shortening-worklist.csv` stays where it is; it only mattered for a build
  whose premise has now been ruled out.

## The tool

`tools/mgs3d_diag_bisect.py` re-injects production files onto the clean tree in
named groups. Every one of the 177 files is always in a defined state --
production or clean -- so no leftovers can survive between runs, and every write
is hash-verified.

| group | files | contents |
|---|---:|---|
| `exec` | 2 | `exefs/code.bin`, `exheader.bin` |
| `font` | 3 | `stage/r_sna01/resident.hpk`, `stage/r_sna02/resident.hpk`, `stage/v000a_0/cache.hpk` |
| `codec` | 1 | `romfs/codec.dat` |
| `media` | 2 | `romfs/movie.dat`, `romfs/demo.dat` |
| `stage` | 169 | `stage/*/scenerio.gcx` |

Production sources are pinned to the binaries the defects were **actually
observed with**, not the later diagnostics: `code.bin` = `4e693f32` (CPP patch +
glyph hooks, alias still `0xA0..0xA3`) and `codec.dat` = `72936022` (v0.96).

```
python tools/mgs3d_diag_bisect.py groups
python tools/mgs3d_diag_bisect.py apply exec font
python tools/mgs3d_diag_bisect.py apply stage --slice 0:85
python tools/mgs3d_diag_bisect.py record bad --note "PROFILE broken, Boss->EVA"
python tools/mgs3d_diag_bisect.py plan
python tools/mgs3d_diag_bisect.py reset
```

`record` writes the result against the last applied set in
`builds/diag-2026-08-20-bisect/journal.json`, so the search stays auditable across
sessions.

## Step 1 -- staged now

`apply exec font`: the execution and font/HPK groups are production, **all 172
text files stay clean English**.

```
files total 924   differing from clean: 5
   exefs/code.bin                     4e693f32b1b20d99
   exheader.bin                       2bca5dcbae016722
   romfs/stage/r_sna01/resident.hpk   4a03cecbb5c38921
   romfs/stage/r_sna02/resident.hpk   b08b3125394629ec
   romfs/stage/v000a_0/cache.hpk      e02312fc2a52a954
```

`mgs3d_hpk_chain_check.py` on `cache.hpk`: `OK: no padded-slot drift`.

**Expected noise, not a defect:** clean `codec.dat` contains 227 tokens on the
static-font pages (`81xx` x169, `82xx` x47, `83xx` x11). With the Korean
`resident.hpk` staged those will draw Hangul instead of their original symbols
in stages `r_sna01`/`r_sna02`. Stray Hangul in those two stages is the test
working, not a new bug.

## Decision tree

| step 1 result | meaning | step 2 |
|---|---|---|
| **bad** | culprit is `code.bin` / `exheader` / `resident.hpk` / `cache.hpk` -- strongest prior, since Boss->EVA and a missing SAVE label are image-index outcomes that translated strings cannot explain | `apply exec` (2 files) |
| **good** | culprit is in the text set despite D2 | `apply codec` (1 file) |

From there:

```
bad  -> apply exec        bad -> apply exec --slice 0:1   (code.bin alone)
                          good -> font: apply font --slice 0:2 (resident pair)
good -> apply codec       bad -> codec.dat is the culprit, 2 CCIs total
                          good -> apply media, then bisect stage (169 -> ~8 halvings)
```

Worst case is about 10 repacks; if the prior holds and step 1 comes back bad,
the culprit is named in **3**.

## What to check each round

The same four, and nothing else: **PROFILE 04/04 PERSONAL DATA**, **Major Tom's
name**, **The Boss -> EVA**, **SAVE**. Record all four each round -- they may
not split the same way, and a round where PROFILE breaks but the contact list is
fine (or the reverse) immediately tells us #1 and #2 have different causes
inside the change set.

## Restore

```
python tools/mgs3d_diag_bisect.py reset                    # back to clean v1.0
python tools/mgs3d_diag_clean_tree_swap.py revert          # back to the D2 build
```

Backup for the full restore is verified at 177/177 files, 961 MB, in
`builds/diag-2026-08-20-clean-tree-swap/staging-backup/`.
