# scenerio.gcx load size source — CONFIRMED (2026-08-13)

## Question

Where does the resident load size for `stage/<name>/scenerio.gcx` come from?
Candidates were: (a) RomFS filesystem file size, (b) external asset metadata,
(c) a field inside the GCX container, (d) a fixed load-request argument.

## Answer

**(a) — the RomFS file size itself.** The resident buffer is sized to the exact
byte length of the file as it exists in the built RomFS. Grow the file, the
buffer grows with it.

## Evidence

### Live measurement

Target: `C:\Users\hhlee\Desktop\Romforge\output\MGS SNAKE EATER 3D_Repack______.cci`

Statically confirmed beforehand that this CCI is the 169-stage patched build:
the Korean glyph page's 48-byte signature occurs **exactly 169 times** in the
image, and the `title` file sits at CCI offset `0xE301B2F0` with its patched
Korean page present at `+0x794B4`.

Resident stage at measurement time was `v001a`:

| item | value | how obtained |
|---|---|---|
| `table[2]` | `0x08982744` | `-data-read-memory-bytes 0x00A46FE0 4` |
| buffer base | `0x0892BE60` | `find /w 0x08000000, 0x09200000, 0x4EE76D54` (GCX seed) |
| page2 offset | `0x568E4` | `table[2] - base`; matches manifest `v001a` row exactly |
| descriptor | `0x0886A3A8` | `find /w 0x08000000, 0x09200000, 0x0892BE60` |
| descriptor `+0x00` | `0x02180720` | resource-class tag |
| descriptor `+0x04` | `0x0892BE60` | buffer pointer |
| **descriptor `+0x08`** | **`0x000BC7E4` = 772,068** | **the read size** |

`772,068` is exactly `v001a`'s **patched** file size (`new_size` in
`patch_manifest_v2.json`). It is *not* the pre-patch size (554,721) and *not*
the true original (489,441). The size tracked the file.

Descriptor record layout: `{u32 tag, u32 ptr, u32 size, u32, u32}`, stride
`0x14`. The tag `0x02180720` was also seen on the `title` entry in the previous
session, so it is a resource-class constant, not a per-file hash — it can be
searched for directly to find these descriptors.

### Korean page is resident — 192/192 bytes

```text
korean page VA = table[2] + 0x56000 = 0x089D8744
               = buffer_base + 0xAC8E4   (= manifest korean_offset for v001a)
```

Read back as three 64-byte chunks and compared against the file's Korean page:
**all 192 bytes identical.** This is also precisely the address the existing
renderer trampoline computes from `*(0x00A46FE0) + 0x56000`.

## Consequences

1. **The 2026-08-12 "candidate 1 (EOF append) is refuted" conclusion is wrong**
   and is retracted. Appended bytes past the original EOF *do* reach resident
   memory.
2. The v1/v2 failures were caused by the **address constant K**, not by load
   size. v2 used `K=0x35000`; the current 169-stage build uses `K=0x56000`,
   which measures correct.
3. No metadata patch, no new loader, and no async-completion handling are
   needed for the glyph page to be resident.

## Ruled out statically (same session)

- **No self-size field in GCX.** Whole-file `u32 == filesize` scan across
  `title`, `title0`, `v001a`, `r_sna01`: zero hits. (Extends the earlier
  "first 0x600 only" check.)
- **`scenerio` and `.gcx` are not strings in `code.bin`.** Stage paths are
  built as `stage/%s/` (string at VA `0x0088F270`, builder at `0x0012F324`,
  plus a bare `stage/` at `0x0088F27C`); the leaf name is data-driven. The
  extension table at `0x00908368` (stride 8) holds `'gcx'` at `0x009083E8`.
- **`FSFILE_GetSize` (IPC `0x08040000`) has exactly one stub**, `0x008370DC`,
  wrapped by `0x008671B4`, which has **zero direct `BL` callers** — it is
  reached only through vtable slot `0x008ADE24`. File-size queries are behind
  virtual dispatch, which is why no direct static call chain to a stage load
  was ever found.
- Resource name table at `0x008B697E..0x008B6A8C` contains `stage.dat`,
  `codec.dat`, `movie.dat`, `bgm.dat`, `demo.dat`, `slot.dat`, `vox.dat` plus
  `_2`/`_3`/`net/` SKU variants; Table A at `0x009084A0` indexes them with a
  `0x18` stride. The shipped RomFS has no `stage.dat` — stages ship loose.

## Not done this session

- Writer PC/LR trace for the size word: **skipped deliberately.** Once the size
  was shown to equal the RomFS file size, identifying the writer had no
  remaining decision value.
- A separate `title`-only `+0xFF00` POC: **unnecessary.** The existing
  169-stage build already does more than that, and it measured correct.
- No CCI was rebuilt, no metadata/code/GCX modified. Read-only session.

## Next action (exactly one)

Boot the **existing** `MGS SNAKE EATER 3D_Repack______.cci` and visually check
whether `0x8401..0x8403` render as Hangul. Do not rebuild anything first — the
data residency and the pointer arithmetic are already verified, so the only
untested link left is the renderer trampoline.

## Log

`analysis/gdb_size_source_20260813.log`
