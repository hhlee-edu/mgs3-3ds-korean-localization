# Result: all six checks pass on hardware

Date: 2026-08-20. **Staged, hardware-verified, not committed and not shipped.**

## The candidate

| file | SHA-256 | what it is |
|---|---|---|
| `exefs/code.bin` | `2b115156b5f2ce831f13cfe14d536e937ab20344d5beea3e2a88960e7db628b5` | alias range `0xA0..0xA3` -> `0xA4..0xA7`, 12 bytes |
| `exheader.bin` | `2bca5dcbae016722…` | production |
| `romfs/codec.dat` | `52e6f4176fce68e020c54251df7fc4537d70b589e46dcd43fe37d5d1bc81b2b5` | PERSONAL DATA clean English, every other translation kept |
| `romfs/movie.dat` | `c48d8cc807ea2b8e…` | production |
| `romfs/demo.dat` | `c44bb512a6a1d017…` | production |
| `stage/r_sna01/resident.hpk` | `4a03cecbb5c38921…` | production |
| `stage/r_sna02/resident.hpk` | `b08b3125394629ec…` | production |
| `stage/v000a_0/cache.hpk` | `e02312fc2a52a954…` | production |
| `stage/r_sna01/scenerio.gcx` | `843c8984395a5667caba06396b1433a6ed7c947ac290568071d5eaef1dca3272` | repad + resource 479 `'SAVE\0'` held at clean ASCII |
| `stage/*/scenerio.gcx` (168 others) | `builds/diag-2026-08-20-stage-repad` | repad padding policy |

924 files, 0 added, 0 removed, 177 differ from clean, no diagnostic variant present.

## Hardware

The Boss, Major Tom, the SAVE label, the title save-slot area name, PROFILE 04/04
and ordinary Korean output: **all six correct in one pass.**

That also closes two things that were still open going in:

- **titlearea** had never been re-tested after the repad fix. It is fixed.
- **PROFILE's second independent cause** -- the production stage files reproduced
  PROFILE on their own before the repad fix. The candidate ships production stage
  files and PROFILE is correct, so repad closed that path too.

## What actually caused what

| defect | cause | fix |
|---|---|---|
| The Boss shows EVA | `stage/v001a` translated payload, specifically the trailing-NUL padding the builder wrote into every shortened slot | padding policy: keep the clean terminator run, fill slack with `0x20` |
| Major Tom name missing | same | same |
| SAVE label missing | `stage/r_sna01` resource 479, the literal `'SAVE\0'` UI label, being translated | permanent translation exclusion |
| title save-slot area name | `stage/title` | closed by the padding fix |
| PROFILE 04/04 | `codec.dat` PERSONAL DATA translated to Korean | PERSONAL DATA kept in clean English by decision |

The padding bug was one line in `tools/mgs3d_stage_apply.py`. It added 17,269
surplus terminators to `v001a` alone; across all 169 stage files the trailing-NUL
total was 2,475,910 against clean's 916,412. The corrected build sits at 830,544,
max run 9 against clean's 9 and the old build's 122.

## Method note worth keeping

Two attributions from the file-level bisection were wrong, and both were caught
by set algebra rather than by assumption:

- `r_sna01` and `r_sna02` `scenerio.gcx` are byte-identical, yet the bisection
  split them. The discriminator was which stage is resident when the symptom is
  observed, not file content.
- PROFILE resolved to `v007a_0` purely by elimination -- it was applied in only
  one verdict round out of thirteen. Restoring all 71 of its translated resources
  (making the file byte-identical to clean) did not cure PROFILE, which refuted
  the attribution outright.

Keeping candidate sets per symptom and recomputing them from the journal, instead
of hardcoding a single culprit, is what surfaced both.

## Open, deliberately

- **40 dialogue lines held at source English.** Adopting this `codec.dat` removes
  the byte subsidy the Korean PERSONAL DATA used to give, so 40 non-PERSONAL-DATA
  units across 31 GCX records stay English. `d2-shortening-worklist.csv` lists
  each with its exact deficit (290 B total). Translator work, not a build fix.
- **PERSONAL DATA renders in English by decision**, not as a defect.
