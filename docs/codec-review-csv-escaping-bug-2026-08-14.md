# codec-review → build-korean pipeline is currently broken (found 2026-08-14)

Found while verifying the capacity-recheck script against the real build code
(not part of that task; reported separately). **Not fixed** — needs a
decision first.

## What's broken

`tools/mgs3d_build.py`, when given `--codec-review <csv>`, shells out to:

```
mgs3d_script_compare.py make-translation <csv> <json> --codec romfs/codec.dat
```

`command_make_translation()` (`tools/mgs3d_script_compare.py:458-532`) takes
each accepted row's `korean` cell and does:

```python
korean = korean_plain.replace("<", "<3C>").replace(">", "<3E>").replace("\n", "<0A>")
```

before writing it into the translation JSON's `"text"` field, on the
assumption that `<`/`>` in the cell are stray literal characters that need
escaping so `parse_rendered()` doesn't misparse them as control tokens.

That assumption is false for the current CSV. Every accepted row's `korean`
cell already ends with a literal, intentional control-code token —
`<0A><00>` — following this project's own established convention (trailing
control codes are preserved verbatim when editing Korean text; see
`translation/10_master/*` editing history this session). The blind
`.replace("<", "<3C>")` re-escapes those *already-correct* tokens into
nonsense like `<3C<3E>0A<3E><3C<3E>00<3E><00>`, which `parse_rendered()`
(the actual byte-encoder used by the build) rejects outright.

## Verified, not assumed

Ran the real converter against the real current master CSV and the real
correct reference `codec.dat`, then ran the real `parse_rendered()` against
every resulting unit:

```
wrote 7372 accepted replacements to real_translation_units.json
...
ok 3  fail 7369
CodecError: literal '<' is not allowed; encode it as <3C>
```

7,369 of 7,372 accepted codec rows fail immediately. The 3 that pass are the
only rows whose `korean` cell happens to contain no embedded control-code
notation before the final `<00>`.

100% of accepted rows (7,369/7,369) were confirmed to contain the `<0A>`/`<00>`
pattern, so this is not an edge case — it currently blocks the entire
`--codec-review` path.

## Why the capacity-recheck numbers aren't affected

`tools/mgs3d_capacity_recheck.py` counts bytes directly from the CSV's
`korean` cell using the *correct* semantics (each `<XX>` token = 1 byte, same
as `parse_rendered` would produce **if given clean input**). It does not go
through `command_make_translation` at all. The capacity results in
`docs/capacity-recheck-2026-08-14.md` stand.

## Evidence this is a real, previously-unexercised bug, not a misunderstanding

- `tools/mgs3d_script_compare.py` has exactly one commit in its history
  (`2008d60`) and no test coverage — this escaping logic has never changed
  since it was first written.
- A **different**, correct converter already exists and produces clean output
  from the same kind of `<0A><00>`-annotated source text:
  `translation/40_build_input/global_page_v2/codec_natural_full_global_page.json`
  (built by `tools/mgs3d_codec_translation_merge.py`, which does no
  `<`/`>` escaping at all) — 0/26,846 units show the corruption pattern. That
  JSON is otherwise **stale** (predates today's handoff merge, QA fixes, and
  glyph-avoidance rewording), so it cannot be used as-is for the current
  master, but it proves the correct converter shape already exists in the
  codebase.

## Options (not decided here)

1. Fix `command_make_translation` to stop escaping `<0A>`/`<00>`-style tokens
   that are already well-formed, and stop unconditionally appending `<00>`
   when one is already present.
2. Regenerate a current-dated equivalent of
   `codec_natural_full_global_page.json` via the already-correct
   `mgs3d_codec_translation_merge.py` path instead of `make-translation`, and
   point `--codec-translation` at that instead of using `--codec-review`.

Both are software-core fixes, not build/staging work — flagging for your call
on which path before anyone attempts a codec build.
