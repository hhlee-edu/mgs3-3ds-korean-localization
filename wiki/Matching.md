# Matching

How Korean candidate text gets attached to specific 3DS resource locations
before it can become MASTER (see [Translation](Translation.md)).

## Movie/demo: the 3-way alignment pipeline

Anchors, in order:
1. **reference English script** (GameFAQs) — the middle anchor.
2. **the script reference Korean** (`translation/00_source/script_ref/pages/`) — the Korean source.
3. **Current 3DS English subtitles**, extracted live via `mgs3d_movie_tool.py inspect`.

Already implemented in `tools/mgs3d_script_compare.py` (`align-dat` +
`merge-dat-korean`) since the earliest codec work (07-31/08-01) — when this
looked broken in 2026-08-08, the real problem was just that its *output* was
keyed to an older parser's record/entry numbering, not that the algorithm was
wrong. Fix was re-running the same pipeline against the current parser's output,
not writing a new one.

Current parser results (2026-08-08 rerun, then colour-corrected 2026-08-08 late):
after the script reference colour-box filtering (below), **movie 236/689 cards matched,
demo 949/2,250** — up from an initial uncorrected 235/935 (110→2 colour-mismatch
contamination removed).

Capacity re-check on the live files: even with the full expanded candidate pool,
only a small fraction fit without further shortening (codec-identical pattern:
`free_slots=0` dominates). Matching coverage and capacity fit are two separate
problems — solving the first doesn't solve the second.

## the script reference colour-box classification (2026-08-08)

The original the script reference author's own colour coding (grey background = cutscene,
green = codec radio) lets movie/demo vs. codec ownership be read directly from
the source instead of inferred from anchor-matching:

- `movie_demo` (grey): 933 lines
- `codec` (green): 406 lines
- `unknown` (no box, white background): 1,692 lines — mostly narration/stage
  directions, not fully verified

Classifier: `tools/mgs3d_script_ref_classify.py`, reassembling `<p>`-level
paragraphs and comparing each ancestor `<td>` background colour to the two
reference colours (rgb 235,235,235 grey / rgb 222,247,229 green) by Euclidean
distance, tolerance 10 (14 was too loose — pure white is only 20 off from grey
per channel and got misclassified). Cross-checking this against the 3-way
match results found 9% colour-mismatch contamination in the original candidate
pool (matched Korean attached to the wrong anchor); after excluding it, coverage
moved 235→236 (movie) and 935→949 (demo). Codec-side cross-contamination was
checked and found to be zero (no exact-text overlap between the live approved
codec Korean and the script reference text) — no further action needed there.

## Review states

`translation/20_matching/review/{codec,demo}/*.csv` are **completed, human-reviewed** matching
output — not raw candidates. Notably:
`translation/20_matching/review/codec/codec_korean_context_review_v3.csv` — `analysis/README.md`
states "completed 298/298 approved review" (direct quote, not inferred).

## Unmerged matching output

`analysis/script_ref/full_build/_scratch/3way/*_comparison_*.csv` (still under
`analysis/`, in-progress/unresolved, not physically moved) and similar
"matching artifact" files, confirmed 2026-08-13: most of their Korean content
has **no ID match at all** in the current master (e.g.
`demo_korean_comparison_3way.csv`: 5 exact / 882 matched keys / 889 Korean
rows) — meaning these are genuinely still-pending matching output that was
never folded into MASTER, exactly as this page describes the pipeline stage.
Not an error, not ambiguous — just not yet merged.

## Known-stale matching output — do not reuse

`translation/90_archive/stale_parser_offsets/movie_korean_comparison_exact*.csv`,
`…/demo_korean_comparison_exact*.csv` (and `_dp` variants): offsets are
keyed to the **pre-2026-08-08 parser** (558/2,091 entries) and don't line up
with the current one (108/3,480 movie, 333/11,296 demo). Re-match instead of
reusing.

## LLM draft pass (2026-08-08, unreviewed)

`tools/mgs3d_llm_translate.py` + `_worker.py` generated first-pass Korean for
cards with no the script reference match at all (not a matching failure — no candidate
exists), via local Ollama (`qwen3:8b`) using speaker/PS2-script/context/scene
budget as prompt input. Results are **draft only**, need the same human review
+ capacity check as everything else before promotion to MASTER. NAS-side worker
crashed silently on its first run from Python-3.9-only `dict | dict` syntax;
fixed to `{**a, **b}` for older-Python compatibility going forward.
