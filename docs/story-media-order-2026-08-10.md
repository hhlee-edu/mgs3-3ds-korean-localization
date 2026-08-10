# movie/demo story playback-order extraction (2026-08-10)

## Required output

The target is story control-flow order, not physical DAT order:

```text
order,stage,script_file,script_offset,type(movie/demo),scene_id,
descriptor/resource_id,source_en
```

Repeated calls and conditional paths must remain separate rows. Physical record
order is used only to join a confirmed scene or descriptor to English text.

## Static asset audit

The extracted PS2 tree contains 156 stage directories, 156 `.02` files and 157
`.01` overlays. Every tested `.02` parses as the same GCX container family used
by the codec tooling. The corresponding 3DS RomFS contains 169
`stage/*/scenerio.gcx` files.

The `.01` overlays contain the media runtime, including
`ANewMpegPssMovieStrProg`, `CODEC_REQ_MOVIE_START`, `NewRadioMovie`,
`NewStreamIpuDriver`, and `NewDemoCamera`. This establishes loader ownership but
does not establish story order or a scene argument.

The old `tools-mgs/gcx-decompile.c` table identifies legacy GCL hash `0xA242`
as `demo`. A structured scan found no such hash in decrypted script resources
of either the PS2 `.02` files or the 3DS `scenerio.gcx` files. Apparent raw hits
occur in procedure/native regions and fail instruction-boundary and container
checks. They must not be reported as media calls.

The procedure areas are platform-specific executable/compiled code rather than
the legacy command stream expected by that decompiler. Consequently a simple
hash scan cannot produce a trustworthy call-order table.

## Confirmed opening runtime anchors

The 2026-08-10 controlled runtime test establishes this prefix:

1. demo scene 127, records 287..291: opening flight over Pakistan through
   `Spread your wings and fly! God be with you!`;
2. movie opening sequence: Sokolov explanation;
3. following parachute dialogue and landing transitions;
4. gameplay return and first codec call.

This is evidence for ordering, but it is not yet evidence for the exact stage
script offset or the movie scene/descriptor value. Unknown fields must remain
unknown rather than being inferred from DAT record zero.

`demo_scene_map.json` currently groups records 287..296 as scene 127. English
inspection disproves that boundary: records 292..296 contain unrelated The End
and combat dialogue, while the runtime-observed opening ends in record 291.
Padding-derived scene grouping is therefore provisional and cannot be used as a
story-order authority. `analysis/story_media_order/opening_runtime_anchors.csv`
contains the two confirmed opening-order anchors with unknown static fields
left explicit.

## Extraction method

Static control flow remains the preferred source for stage, branch and duplicate
call sites. Runtime instrumentation will supply the consumer PC and scene or
descriptor argument at each actual invocation. That PC is then mapped back to
the owning `scenerio.gcx` procedure and offset. The media parser joins the
confirmed ID to its English type-1 subtitle stream.

The next instrumentation must log only the movie/demo request boundary. Broad
RomFS-read logging is unsuitable: MGS3D uses a shared binary RomFS handle and the
earlier broad trace was noisy enough to trigger the diagnostic slow-memory/GPU
failure. The call-boundary log needs sequence number, PC/LR, r0-r3, stage name,
media type, and the selected scene/descriptor. Conditional and repeated runtime
occurrences are preserved verbatim.

## Confidence rule

A final row is `confirmed` only if a script call site and runtime-selected ID
agree, or if static decoding independently proves both. DAT physical order alone
is never sufficient. Rows based only on observed playback are retained as
runtime anchors and are not promoted to the requested final CSV.

## Runtime boundary investigation

Targeted RomFS reads established the real opening media blocks without using
DAT order as story order:

- demo scene 127 read: demo file offset `0x26103700`, covering record 287 at
  `0x26108C30`; completion PC/LR `0x00837018/0x00836524`;
- following movie read: a `0x10000` aligned block beginning `0x1120` before the
  confirmed movie base; the same common asynchronous FS completion chain was
  used.

The completion stack is an archive worker chain (`0x001520B8 -> 0x00132EA4 ->
0x0014FF00 -> 0x0011A834`) and is not the story command caller. It is useful for
proving which data was read, but must not be reported as the movie/demo request
PC.

Targeted inspection of the decompressed 3DS command registration tables found
that commands use the project's 24-bit string hash, not the legacy 16-bit
constant:

- `strcode24("demo") = 0x33A20F`, registered handler `0x00409DB0`;
- `strcode24("movie") = 0x09658C`, registered handler `0x0079F6B4`;
- checks: `strcode24("if") = 0x0D86` and `strcode24("eval") = 0x34648C`
  match entries in the same table.

The demo handler calls the generic argument decoder at `0x0022F35C`; the first
decoded value is available at `0x00409DD0`. The movie handler has the analogous
point at `0x0079F6C0`. A runtime hit at `0x00409DD0` produced `r0=0x10000000`,
but it occurred around six seconds into startup, before scene 127 was read.
It is therefore an initialization command and is not a scene-127 ID.

The attempted GDB breakpoint and instruction-substitution probes are rejected
as evidence. Both perturbations reproducibly reached an unrelated invalid GPU
address (`0x2888E4E4` at guest PC `0x00161470`) and Vulkan assertion at roughly
50 seconds. Repeating those probes would only ask the user to replay a known
unstable diagnostic. Azahar was restored to upstream Dynarmic/FS code and GDB
was disabled after the tests.

The next safe approach must observe the argument decoder without pausing or
substituting a guest instruction—for example, a host-side Dynarmic IR callout
that preserves the translated ARM instruction exactly, validated first against
an uninstrumented runtime hash/trace. Until then, neither `r0=0x10000000` nor
the registered `movie` handler is promoted to a story scene mapping.

### Non-invasive tick-marker probe

A replacement probe was compiled in the external Azahar worktree. Dynarmic's
existing per-instruction tick callback marks translated blocks containing
`0x00409DD0` or `0x0079F6C0`. At the normal block-end tick callback it removes
the marker before updating emulated time and logs PC/LR plus r0-r12. It neither
replaces a guest instruction nor pauses execution, writes guest memory, or
changes the effective tick count. Runtime output is not evidence until this
build completes the opening path without the prior diagnostic crash.

The runtime validation failed: with the ROM path correctly passed, Azahar
terminated about 5.7 seconds after boot, before a usable media event was
recorded. The tick-marker patch was removed and the stable bundle rebuilt.
This probe is rejected as evidence and must not be retried.

Static disassembly supplies a safer next boundary. The `movie` handler calls
the common argument reader at `0x0022F35C`, stores its return value at offset
`+4` of the global request object, and writes request type `5` at offset `+0`.
The `demo` handler preserves the same reader's first return value in `fp` and
passes it unchanged to `0x004449CC` and as argument r3 to `0x004BC2DC`.
Both therefore consume the tagged value decoded by `0x00171C7C`; they do not
accept a plain DAT record offset directly. The decoder dispatches on the high
nibble of the script byte and handles 1-, 2-, 3-, and 4-byte immediates plus
string/reference forms. Reconstructing this decoder for `scenerio.gcx` is now
the preferred route to a static call-site scanner.
