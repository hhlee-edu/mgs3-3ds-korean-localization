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
