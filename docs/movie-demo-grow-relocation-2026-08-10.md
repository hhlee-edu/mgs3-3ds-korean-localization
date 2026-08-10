# movie.dat / demo.dat grow relocation validation (2026-08-10)

## Scoped result

Codec investigation was not reopened. Movie was tested first, then demo. Both
formats were treated independently at runtime even though the existing parser
can read their subtitle records.

Pure record-tail growth did not require a codec-style low-24 relocation patch
in the tested paths. The loader accepted sequentially shifted records when the
record's own declared size and 0x10 alignment were updated.

This result applies to byte-neutral zero padding appended after a record's font
block and to the already-built movie translation grow artifact. It does not yet
prove that every translation rebuild preserves all scene metadata correctly.

## Reproducible API

`tools/mgs3d_movie_precise_relocate.py` creates byte-exact probes. Repeating
`--record` grows multiple selected records and automatically shifts all later
record/gap material while preserving it byte-for-byte:

```text
python tools/mgs3d_movie_precise_relocate.py source.dat output.dat \
  --record 0 --record 50 --delta 0x10
```

It rejects non-positive/non-0x10-aligned deltas and bad record indices, updates
the selected record size fields, reparses the full output, and writes a JSON
old/new offset report.

## movie.dat

Baseline: 229,376 bytes, SHA-256
`745FEF1E55AF881E8594C8B25D2B8487F8AAC54418573E943D86AC95F44A72B6`.

Minimal test:

- record 0: 2,080 -> 2,096 bytes;
- record 1..107: `+0x10` offset;
- output SHA-256:
  `42EB7987BEE87E9A174C137221851CE4DBF27D1C2725E7D797276DA350E6E1E2`;
- full parse and byte-identical parser round-trip passed.

Runtime passed the Sokolov explanation movie, subtitles, voice, following
parachute-dialogue scene, landing scene, gameplay return, and first radio call.

After that success, the existing full grow build was tested in isolation:

- 71/108 records grew;
- record 1..107 shifted;
- file growth: 229,376 -> 454,800 (`+225,424`);
- final record displacement: `+224,208`;
- SHA-256: `48A9DF737A59077033B0F1F10637291F4DAFEC277221351D7424E7843D3F4EBA`.

The same three movie scenes, transitions, gameplay return, and first radio call
were normal. This is strong runtime evidence that movie record reflow is usable
for the tested opening sequence. It is not exhaustive coverage of all 108
records.

## demo.dat

The test used the current live normal baseline, not the older English backup:

- size: 772,935,680;
- SHA-256: `50026766AA0308C2289D4CA668F4D4975FBCE5626E611431FCCEEECDA38938AF`.

Minimal test grew record 286 by `0x10`, moving the actual first-video record 287
from 638,618,672 to 638,618,688. Records 287..332 shifted by 16 bytes. Output
SHA-256 was
`4C558DB70CD319789DC12E384E02F6635048CB6227856DD163698A144AB898F4`.
“Flying over Pakistan” played through “May the gods be with you,” with normal
video, subtitles, audio, and handoff to the Sokolov movie.

Two additional tests then passed:

- far-apart records 50 and 286 each `+0x10`; first video moved cumulatively by
  `+0x20`, then handed off normally;
- records 0/50/100/150/200/250/286 each `+0x10`; all 333 records reparsed,
  record 287 moved by `+0x70`, and the first demo plus movie handoff were normal.

This directly revises the earlier claim that demo fails whenever two records
grow. Record count alone is not the cause. The historical multi-translation
failure must include another rebuild difference (content, per-record layout,
scene gap metadata, or scale). It must not be described as a generic relocation
failure without reproducing that specific artifact.

## Instrumentation note

The existing FS instrumentation uses the game's shared binary RomFS handle and
does not expose a movie/demo filename at the IPC layer. Expanding it to log every
RomFS read produced a noisy diagnostic build that later hit the pre-existing
slow-memory/GPU diagnostic crash. That run was discarded; no parser/consumer
divergence claim is based on it. The temporary broad logging source change was
removed.

The stable runtime tests showed no first divergence to chase: NORMAL and moved
artifacts reached the same visible playback, transition, return, and radio
states. No OLD record position had to be patched. A future investigation of the
historical translation artifact should add file identity below the RomFS
archive layer or hash the completed read buffer, without enabling the old
slow-memory GCX tracer.

## Cleanup

All movie/demo LayeredFS overrides were removed after testing. Live RomForge
files and Citra LayeredFS were not modified. Experimental artifacts remain only
under `analysis/movie_relocation_20260810/`.
