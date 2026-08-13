# codec.dat distributed grow stress (2026-08-10)

## Result

The distributed codec grow build passed the whole-file static verifier and the
tested runtime path. Within the scope below, the result supports:

> codec.dat grow는 procedure/internal low-24 target relocation을 동반하면 실제 사용 가능

This does **not** mean every possible GCX, call site, or arbitrarily large
movement is proven safe. Runtime coverage was representative, not exhaustive.

## Build shape

Pristine baseline: 67,204,976 bytes, SHA-256
`19FF34D1380E1AFD3D19DFBD0C9C3DF091FBFB5743E09189B5DC943A85BF6267`.

An initial 1,675-GCX/+4,381,488-byte adversarial build was not deployed because
it moved GCX53 by `0x1B760`, outside its previously observed fixed 24 KiB read.
That would mix a read-window failure with the relocation question.

The deployed build used the normal translation/font pipeline and grew GCX 13,
100, 500, 1000, 1501, 1990, and 2200. It added 258 Hangul glyphs and 16,720
bytes. GCX13 gave GCX53 a controlled real displacement; six later sites caused
distributed reflow through the rest of the file.

- output: 67,221,696 bytes
- SHA-256: `935A409F088D6DEB113171FED313B65EA77AD05BD7744151C1638B67BE64EEA6`
- size-changing GCXs: 7
- shifted GCXs: 2,312
- procedure words audited: 216,705
- relocated procedure words: 3

| GCX | old offset | new offset | delta | old/new size | relocated words |
|---:|---:|---:|---:|---:|---:|
| 13 | `0x1C50` | `0x1C50` | 0 | 24,864 / 25,680 | 0 |
| 53 | `0x457B0` | `0x45AE0` | +816 | 13,264 / 13,264 | 3 |
| 100 | `0x8FDC0` | `0x900F0` | +816 | 5,088 / 9,664 | 0 |
| 500 | `0x8FA270` | `0x8FB780` | +5,392 | 5,328 / 8,400 | 0 |
| 1000 | `0x11BED40` | `0x11C0E50` | +8,464 | 4,928 / 6,672 | 0 |
| 1501 | `0x360F420` | `0x3611C00` | +10,208 | 3,760 / 4,976 | 0 |
| 1990 | `0x3D8B220` | `0x3D8DEC0` | +11,424 | 5,216 / 5,536 | 0 |
| 2200 | `0x3F6E140` | `0x3F70F20` | +11,744 | 5,232 / 10,208 | 0 |
| 2325 | `0x4016F40` | `0x401B090` | +16,720 | 2,096 / 2,096 | 0 |

## Static and runtime verification

`tools/mgs3d_codec_grow_verify.py` passed complete parsing of all 2,326 GCXs,
contiguous boundaries, stable procedure counts, exact GCX53 `0x1000 -> 0x1330`
relocation, high-byte flag preservation, missing/extra relocation detection,
and 24-bit overflow checks. It writes the full changed/shifted-record report as
JSON and CSV.

An apparent 865 translated-string target failure was investigated and rejected
as a coordinate-system mistake. Numeric overlap with the encrypted string area
does not make procedure targets translation-string byte anchors; relocation is
driven by a proven moved parser/container boundary.

Azahar LayeredFS runtime passed the opening and initial event, first codec,
portrait movement, dialogue, voice, close/return, same-codec recall, following
sequential radio call, and a later event radio call. LayeredFS was then restored
to the pristine hash. Citra LayeredFS and live RomForge romfs were untouched.

Reproduce the selection with
`analysis/codec_grow_stress_20260810/make_stress_translation.py`, build with
`mgs3d_gcx_font_tool.py build-korean`, then run:

```text
python tools/mgs3d_codec_grow_verify.py pristine.dat grown.dat report.json
```

Movie/demo remains deferred. Next order: movie `+0x10`, parser-entry/outer scene
reference validation, following-video playback, then the same method for demo.
