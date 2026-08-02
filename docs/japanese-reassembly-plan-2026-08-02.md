# Japanese source reassembly plan — 2026-08-02

## Active goal

Redefine every C/D/G character or dictionary reference and every control code
from the original MGS3D bytes, reconstruct the complete Japanese source, compare
the decoding results of all existing translation tools on identical inputs, and
regenerate Korean translation material against the reconstructed source.

The goal is not complete when one dictionary is found. It is complete only when
the target corpus has no unresolved references or unclassified tokens and the
tool comparison establishes which decoder behavior is correct for every token
class.

## Decision

The next milestone is to reconstruct the complete Japanese source text from the
already unpacked game data before doing any further translation or semantic
mapping. Existing tools and runtime-safe builders remain valid and must be
preserved.

Current codec review material contains unresolved tokens such as `<Cxxx>`,
`<Dxxx>`, and `<Gxxx>`, plus Japanese previews with missing words. Korean lines
inferred from those incomplete previews are drafts, not authoritative
translations. The token letters are provisional labels, not proof of their
runtime meaning; each class must be verified against the original bytes and
the table or code that consumes it.

## Scope to preserve

Do not discard or redesign the verified binary work:

- LA2/DARC and ARC extraction;
- codec, movie, and demo parsers;
- fixed-layout codec/demo rebuilding;
- Hangul font allocation and capacity checks;
- structural verification and runtime-test results;
- stable GCX/resource, record/entry, offset, and raw-hash identities.

Existing Korean review CSVs and generated DAT files should be retained as
historical/reference artifacts, but they must not be treated as translation
ground truth for codec text whose Japanese source is incomplete.

## Next implementation objective

Use the unpacked game resources to identify and decode every text token class,
then reconstruct the complete original Japanese text. The investigation must
cover at least:

- `<Cxxx>` character/glyph tokens, including small kana and punctuation;
- `<Dxxx>` record-local dictionary/string-fragment references;
- `<Gxxx>` global or shared glyph/string references;
- `<END>`, `<0A>`, and every other runtime layout/control token encountered.

These meanings remain hypotheses until confirmed. In particular, do not infer
that a token is a string dictionary reference solely from its displayed prefix:
the current codec preview labels parts of the `0x8C01...` range as `<Gxxx>`,
while the font tooling also uses that range as glyph indices.

During reassembly:

1. preserve control codes, line breaks, speaker boundaries, and resource IDs;
2. classify every encountered token by evidence from its backing table and
   runtime use, distinguishing glyphs, dictionary references, and controls;
3. expand local and shared references, supporting nested/recursive references
   if the format permits them;
4. render confirmed glyph tokens, including small kana and punctuation;
5. preserve controls structurally rather than dropping them from plain text;
6. detect invalid indexes, cycles, truncated entries, and undecodable bytes;
7. emit raw bytes, raw-token form, reconstructed text, and control annotations
   with source provenance;
8. report every unknown or unresolved token instead of guessing missing text.

## Completion gate

Translation and conversation mapping remain paused until a reconstruction audit
shows:

- zero unresolved C/D/G references in the target corpus;
- zero unclassified token values in the target corpus;
- zero unexplained decoding failures;
- one reconstructed result for every source resource, retaining stable IDs;
- control-code preservation verified against the original bytes;
- deterministic output from identical inputs;
- representative Japanese lines reviewed in context.

The translation-tool comparison must additionally provide:

- a fixed comparison corpus covering every observed token class and boundary;
- side-by-side raw bytes, legacy token output, reconstructed Japanese, controls,
  and Korean translation where one exists;
- documented differences between the codec, movie, demo, matcher, and any
  external/reference decoders;
- byte offsets and stable record/resource identities for every disagreement;
- an explicit disposition for each disagreement: confirmed, corrected,
  unsupported, or still unresolved;
- deterministic regression fixtures for every confirmed decoding rule.

After that gate passes, reconnect existing review rows by stable identity/raw
hash, invalidate stale inferred mappings, and re-review the Korean translation
against the reconstructed Japanese source. Capacity planning, safe-fixed
building, structural verification, and runtime testing then continue with the
existing tools.

## Resume order

1. Inventory all token values in the target corpus, retaining byte offsets and
   record/resource identities.
2. Locate the local dictionaries, shared/global tables, font/glyph tables, and
   the code or structures that consume controls.
3. Document every token class and its encoding, including unknown/reserved
   values and recursion rules.
4. Implement a read-only Japanese reassembly/export command.
5. Run the reconstruction audit over the complete target corpus and require a
   zero-unresolved report.
6. Generate new review artifacts from the reconstructed Japanese text.
7. Revalidate translations, then resume fixed-layout capacity/build work.

## Next-session execution checklist

1. Freeze a read-only baseline of the current raw dumps and record their hashes.
2. Generate a complete token-frequency inventory with representative byte-level
   examples and source locations.
3. Redefine C/D/G and control-code semantics from their backing tables and
   consumers; record evidence rather than relying on provisional token names.
4. Build a common comparison corpus and run every existing decoder against it.
5. Implement the unified read-only reassembler and add regression tests for
   glyphs, local/shared references, recursion, line breaks, termination, invalid
   indexes, cycles, and truncated input.
6. Run the full-corpus zero-unresolved audit.
7. Regenerate translation-review artifacts and mark mappings derived from
   incomplete Japanese previews as stale pending re-review.

Do not delete existing translations, review CSVs, or runtime-tested builds.
Keep them as historical evidence and reconnect valid rows through stable source
identity after reconstruction.
