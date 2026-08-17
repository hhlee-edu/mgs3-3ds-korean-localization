# Circle Pad Pro save distribution — analysis (2026-08-17)

Assessment of `builds/MGS3D_C_stick_SAVESCITRA.rar` as a shipped workaround for
the Citra Extrapad freeze
([`citra-extrapad-applet-freeze-2026-08-17.md`](citra-extrapad-applet-freeze-2026-08-17.md)).
**Verdict: viable, ship 3 of the 4 files, with attribution and one added warning.**

## What is in the archive

RAR5, 4,778 bytes, authored 2021-10-24 by **RT37**. `readme.txt` states the saves
were made on a real 2DS with the Circle Pad Pro activated and then transferred,
"no modifications other than CPP activation", and warns: *"DO NOT attempt turning
the CPP back off and on or your game will crash."*

| member | size | sha256 (16) | CRC | stage / room | CPP |
|---|---:|---|---|---|---|
| `Normal/savedata` | 20,768 | `6dcee4d2bc450409` | OK | `v001a` / `r_sna01` | **on** |
| `Normal (alt)/savedata` | 20,768 | `6dcee4d2bc450409` | OK | `v001a` / `r_sna01` | **on** |
| `Hard/savedata` | 20,768 | `9f86a9950c1d022f` | OK | `v001a` / `r_sna01` | **on** |
| `Extreme/savedata` | 20,768 | `b643854308a5c817` | OK | `v001a` / `r_sna01` | **on** |

**`Normal` and `Normal (alt)` are byte-identical.** Ship three files, not four —
the duplicate only invites "which one do I use?".

## Verification performed

All four parse cleanly as MGS3D saves and all four pass the checksum, using a
format derived independently from the user's own save before the archive existed:

```
save[0x00] = u32 little-endian CRC32(save[4:])
```

Six saves now confirm it (user's Citra save, user's Azahar save, and these four).
`tools/mgs3d_save_tool.py` implements `show` / `diff` / `fix-crc` against it.

Same title as our build (`0004000000081E00`), same 20,768-byte layout, and all
four sit at the very beginning of the game.

## What CPP activation actually writes

Comparing the user's own CPP-off save with `Normal`, and cross-checking against
`Hard`/`Extreme` to strip out difficulty and progress noise:

- **`0x40..0xBF` — primary button-mapping table (32 × u32 HID pad masks).**
  Activation rewrites it into the dual-stick scheme: `R→ZR`, `L→ZL`, `ZL→L`,
  `ZR→R`, `Up→X`, and the four entries at `0x7C..0x88` (X/B/Y/A) are cleared.
- **`0xC0..0xF7` — a second 14-entry table that is *entirely zero* when CPP is
  off and fully populated when it is on.** This is the cleanest single indicator
  of CPP state, and it is what `mgs3d_save_tool.py` reports as
  `Circle Pad Pro / C-stick: ENABLED`.
- Header flags at `0x0C`, `0x10` and `0x3C` also change (`0x3C`: `80` → `02`,
  which looks like a control-scheme id).

**Limitation, stated plainly:** the user's save and RT37's are different
playthroughs on different consoles, so the 55 bytes that differ consistently
across all three difficulties still mix CPP state with unrelated settings
(sensitivity, sound, playtime). The two tables above are structurally
unambiguous; the remaining scattered bytes are not. Writing an in-place
"enable CPP on the player's own save" patcher would need a CPP-off/CPP-on pair
captured from **one** console — which is the only reason to prefer distribution
over patching today.

## Recommendation

**Ship the saves as an optional extra**, because it is the only workaround that
needs nothing from the user beyond copying a file:

1. Include `Normal`, `Hard`, `Extreme` only.
2. **Keep `readme.txt` and credit RT37.** This is someone else's work; the honest
   options are to bundle it with attribution intact or to link to the original.
   That is the user's call, not a technical one.
3. Add a Korean note carrying RT37's warning forward, because it applies to our
   build too and is the single most important instruction:
   > 에뮬레이터에서는 게임 내 **확장 슬라이드 패드(서클패드 프로) 옵션을 켜거나
   > 끄지 마십시오.** Citra/Azahar에 해당 시스템 애플릿이 없어 게임이 멈춥니다.
   > 이 세이브는 실기에서 미리 켜 둔 상태라 옵션을 건드릴 필요가 없습니다.
4. State that the saves start at the beginning of the game, so they replace
   progress rather than adding to it.

## Still to check before shipping

- **One Citra smoke test with our CCI**: drop `Normal/savedata` in, confirm it
  boots, the Korean text renders, and the dual-stick controls respond. Nothing in
  our patch touches the save format, so this is expected to pass — but it has not
  been run.
- Confirm the base ROM region matches what we ship. Title id agrees
  (`0004000000081E00`), which is the strongest available signal.

Install path for Citra/Azahar:

```
%APPDATA%\<Citra|Azahar>\sdmc\Nintendo 3DS\<32 zeros>\<32 zeros>\
    title\00040000\00081e00\data\00000001\savedata
```
