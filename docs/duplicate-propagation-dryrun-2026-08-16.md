# Duplicate propagation — dry run (2026-08-16)

Answers the open question from
[`v0.81-hardware-defects-rootcause-2026-08-16.md`](v0.81-hardware-defects-rootcause-2026-08-16.md):
propagating the translation to every duplicate location is the one large lever for
codec English residue — **is it affordable in bytes?**

**Nothing was staged and nothing in the RomForge tree was touched.** All outputs
went to a scratch directory. The build in §4 exists only to verify the capacity
verdict.

## 1. New tool

`tools/mgs3d_codec_expand_locations.py` — copies each canonical unit's
already-escaped text to the other positions its master row names in `locations`.

A duplicate is written **only when its original bytes in the reference
`codec.dat` are byte-identical to the canonical's** — the same rule
`mgs3d_codec_duplicate_propagate.py` uses. That check earns its keep (§3).
Output is a plain `mgs3d-codec-translation-v1` document, so it feeds the existing
capacity gate unchanged.

```
units 8478 -> 201482  (+193004)
master rows expanded: 7461
skipped: original bytes differ from canonical: 411
```

## 2. Capacity verdict: it fits, with room to spare

`tools/mgs3d_codec_safe_select.py` runs the shipped
`replace_resources(preserve_layout=True)` as the fit test, per GCX.

| input | units in | units kept | dropped | GCX failing |
|---|---:|---:|---:|---:|
| current (canonical only) | 8,478 | 8,441 | **37** | **31** |
| **expanded** | 201,482 | **201,482** | **0** | **0** |

The baseline row reproduces the v0.81 staging document exactly (8,478 → 8,441,
37 dropped), which is what makes the expanded row believable.

**Replacing more strings makes records *smaller*, not larger.** Korean at 2 bytes
per syllable is shorter than the long English sentences in these records, so once
every string in a record is replaced the record shrinks well below its original
size. The 31 GCX that failed before were failing because only one or two strings
had been swapped — each individually longer than the short English it replaced —
with no compensating savings anywhere else in the record.

This also means the 37 rows the worklist tracks as codec capacity drops are an
artefact of propagating too little, not a real shortage.

Estimated deltas for the largest records (measured earlier, consistent with the
gate's verdict):

| GCX | translatable lines | English bytes | Korean bytes | delta |
|---:|---:|---:|---:|---:|
| 1412 | 1,725 | 116,455 | 82,866 | −33,589 |
| 1408 | 1,708 | 115,541 | 82,220 | −33,321 |
| 1403 | 1,685 | 113,390 | 81,046 | −32,344 |
| 243 | 887 | 54,261 | 41,987 | −12,274 |

## 3. Build verification — no record grows, file size identical

**`mgs3d_codec_tool.py apply` is the wrong tool for this check.** It calls
`replace_resources(changes)` *without* `preserve_layout=True`, so it is free to
grow records; the production codec build uses the layout-preserving path. It is
also quadratic here — it calls `record.resources()` once per unit and each call
re-decrypts that record's whole string region, so 201,482 units ran for 13+
minutes without finishing. Recorded as a hotspot; not optimised, since changing a
core build tool was out of scope for this run.

The property that actually matters was verified directly instead — group the units
per GCX, rebuild each record with `preserve_layout=True`, and require that no
record's byte length moves:

```
records 2326, gcx with changes 2264, units 201482
gcx records changed      : 2264
records whose size moved : 0
total size  67204976 -> 67204976  (delta +0)
sha256: 40eead32baa337444e7ba02b854e17472bbac8274e630b13d3167d62fadfd0b3
```

**2,264 of 2,326 records rewritten, zero size change anywhere, file size to the
byte.** That is the whole capacity question answered.

## 4. Coverage, measured on the built file

`tools/mgs3d_translation_coverage.py` over the same 211,458-location denominator
(detector control against the pristine build: 0 false positives):

| cause | v0.81 staged | propagated |
|---|---:|---:|
| **Korean in build** | 8,009 (**3.79%**) | **200,768 (94.94%)** |
| duplicate location not written | 193,138 (91.34%) | 409 (0.19%) |
| master has no Korean | 10,265 (4.85%) | 10,265 (4.85%) |
| dropped for capacity | 30 (0.01%) | **0** |
| not accepted | 16 (0.01%) | 16 (0.01%) |

**+192,759 locations**, and the capacity category disappears entirely.

The measured 94.94% is slightly under the 95.13% predicted from the document keys.
The gap is a known limit of byte-level detection, not a build fault: a handful of
accepted rows have Korean that is legitimately pure ASCII (`Snaaake!`,
`SVD를 써.`-style rows where the whole line is a proper noun), so their built bytes
contain no `0x81-0x87` lead byte and are indistinguishable from untranslated. They
are correctly in the build.

Remaining work after propagation is no longer a capacity problem — it is the
**10,265 locations whose master row has no Korean at all**.

## 5. The 411 refusals are a real finding, not noise

The byte-identity check refused 411 locations across **16 canonical rows**. Every
one is a case where the master's `locations` column names a position holding
*different* text — usually a case difference (`alors` vs `Alors`) in **French**
strings.

Following that thread: **42 accepted, non-donor rows have an `english` column that
is actually French or Spanish** (34 fr, 8 es; 30 carry `<1fXX>` accent escapes).
They are marked `language=en, is_donor=no`, so they passed the donor filter and
were translated and shipped. Some are heavily duplicated — `gcx 1403 / res 2713`
has `occurrences=62`.

This is the donor-language contamination the direct-v2 notes flagged, now
confirmed in the *current accepted set*. Per the project's absolute rule, donor
text should never have received effort. At least one is also simply wrong:

```
gcx 510 / res 41
  EN: ...Oups. Je dois y aller. A plus, Snake.
  KO: ... 이런. 정말 알레르기가 있어요. 플러스, Snake.
```

("I have to go. See you later" became "I really have allergies. Plus, Snake.")

**Not corrected here** — deciding whether to unaccept or retranslate these is the
translator's call, and it is a master-data change.

## 6. Verdict

Propagation is **byte-safe, layout-neutral, and worth ~25× the current reach**.
Nothing blocks it technically. What it needs before it can ship:

1. A decision on the 42 contaminated rows (§5) — they would be propagated too.
2. The `apply` hotspot (§3) fixed, or the production build path used instead.
3. A hardware test, which is gated on defect 2 being worth testing (§7).

## 7. What this does not change

Propagation fixes English residue. It does **not** touch defect 2 — the
global-page characters that render corrupted — which is a `code.bin` anchor
problem, not a data problem. A build carrying propagation would still show
corrupted `추`/`션`/`억`. See
[`gdb-anchor-sample-recipe-2026-08-16.md`](gdb-anchor-sample-recipe-2026-08-16.md).

Reproduce:

```
python tools/mgs3d_codec_expand_locations.py --out-doc <expanded.json> --out-report <report.json>
python tools/mgs3d_codec_safe_select.py --translation <expanded.json> \
       --out-doc <expanded-safe.json> --out-excluded <expanded-excluded.json>
python tools/mgs3d_codec_tool.py apply \
       experiments/2026-08-13-clean-glyph-baseline/clean-tree/romfs/codec.dat \
       <expanded-safe.json> <out.dat>
python tools/mgs3d_translation_coverage.py --codec <out.dat> \
       --build-input <expanded-safe.json> --strict-reference --out <coverage.json>
```
