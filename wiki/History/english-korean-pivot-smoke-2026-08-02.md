# English-to-Korean pivot smoke test — 2026-08-02

The production direction is now the Western release directly to Korean. The
Japanese glyph-reconstruction experiment is not an input to this pipeline.

## Confirmed Western container structure

- `codec.dat` contains 2,326 GCX records. Localized dialogue is stored in
  English, Spanish, and French blocks after shared resources.
- `movie.dat` and `demo.dat` multiplex Western subtitle languages as entry
  types 1 through 5. Type 1 is English; type 7 is the observed local-glyph
  form used by Japanese records.
- The Western movie parser/rebuilder round-trips the unmodified file byte for
  byte with SHA-256
  `745fef1e55af881e8594c8b25d2b8487f8aac54418573e943d86ac95f44a72b6`.

## Korean insertion smoke outputs

| Container | Source line | Korean probe | Structural result | Output SHA-256 |
| --- | --- | --- | --- | --- |
| codec | GCX 15/resource 14, `Do you copy?...` | `들리나?` | 2,326 records retained; only GCX 15 changed; font 0→3 glyphs | `6f9d561b9b1a1bc14e9c77b5373b676f6bdc15809898a18d2d5ea656de1f2007` |
| movie | type-1 offset 292, `Jack, I've got some important news.` | `중요한 소식이 있어.` | 108 records retained; only record 0 changed; font 0→8 glyphs | `d63e1942601eac17f03f0c247950691f794b5ed7bbeb68d36461096b4522b55b` |
| demo | type-1 offset 2,669,172, `Listen up, Jack.` | `잘 들어, 잭.` | 333 records retained; only record 0 changed; font 0→4 glyphs | `3ac4cdc2af5fd6a23dc7292b239da8e5a6363a58d7fe83a0ae277963c4a96b6e` |

The movie/demo builder gained `--grow-records`, which repacks changed Western
records, appends newly rendered Hangul glyphs, updates entry/text/font/record
sizes, preserves timing tails and untouched record payloads, and reparses the
complete output as a postcondition. These are structural smoke tests; runtime
rendering still requires repacking and launching the game.

## Existing Korean-script matcher connection

`tools/mgs3d_english_korean_match.py` directly matches actual Western game
strings against `analysis/mgs3_korean_english_alignment_dp.csv`, preserving
GCX/resource identities or movie/demo byte offsets.

| Container | English game rows scanned | Exact English matches | Rows with one Korean candidate |
| --- | ---: | ---: | ---: |
| codec | 601,479 | 21,082 | 7,608 |
| movie | 689 | 51 | 33 |
| demo | 2,250 | 457 | 333 |

The generated CSVs deliberately leave `accept` blank. Exact game-to-GameFAQs
English identity proves the English lookup, but does not prove the older
GameFAQs-to-the script reference Korean DP alignment. A witnessed medium-confidence
counterexample maps `Be careful. You might not have a choice.` to an unrelated
Korean sentence. Production builds must therefore use context-reviewed rows,
not bulk-approve these counts.

## Verification

- Main tool suite: 71 tests passed.
- Matcher suite: 5 tests passed.
- External RomForge source files were read only and were not overwritten.
