# Circle Pad option freeze in Citra = unimplemented Extrapad applet (2026-08-17)

**Not our defect.** Not a renderer, `code.bin`, glyph-page or `codec.dat` problem.
No patch can fix it, and no rebuild will change it.

## Evidence

`%APPDATA%\Citra\log\citra_log.txt.old.txt` (105 MB, 2026-08-17 08:30) is the
session in which the freeze happened. Title `0004000000081E00` — MGS3D, the same
title id as the hardware Luma dump's `0x00081E00`.

At **t = 50.82** the game asks APT for a library applet and Citra refuses:

```
Service.APT <Error> applet_manager.cpp:CreateHLEApplet:534: Could not create applet 1032
Service.APT <Warning> apt.cpp:AppletUtility:694: (STUBBED) command=0X00000004
Service.APT <Warning> apt.cpp:ReplySleepQuery:944: (STUBBED) from_app_id=00000300
```

and the game retries that triple forever:

| | |
|---|---|
| applet id | **1032 = 0x408 = `Extrapad2`** — the Circle Pad Pro / 확장 슬라이드 패드 library applet (the `0x4xx` alias a game uses to *request* `0x208 Extrapad`) |
| retries | **193,580**, from t=50.82 to t=70.50, then the log ends |
| other applet ids that failed | **none** — `Could not create applet` appears for 1032 and nothing else |
| guest exceptions in the whole session | **0** — no Data Abort, no `svcBreak`, no undefined instruction |
| emulator state | alive and still logging throughout — Citra did not crash |

Immediately before t=50.82 the log is ordinary rendering traffic (custom-texture
lookups), i.e. the game was running normally until the option was toggled.

## Reading

The game opens the Extra Pad configuration applet when that option is changed.
Citra has no HLE implementation for it, `CreateHLEApplet` fails, the game waits
for an applet that will never start, and spins. That is a **guest-side hang
caused by an emulator gap**, not a crash, and it is reachable from stock retail
code that this project has never patched — the six patch sites are all in the
glyph draw/width/classify paths (`0x0015Exxx`, `0x0018xxxx`) and have nothing to
do with APT.

It follows that a pristine, unmodified MGS3D would freeze identically in Citra at
the same menu. That is the cheapest confirmation if one is ever wanted.

## Consequences for testing

- **Do not open the Circle Pad / 확장 슬라이드 패드 option while testing in Citra.**
  It is a known dead end and tells us nothing about the translation build.
- **Do not read this freeze as a regression** of the renderer range guard or of
  any `codec.dat` revision. A guard fix cannot and will not remove it.
- Real hardware has the applet, so this cannot be reproduced there. Per the
  2026-08-17 instruction, hardware verification is reserved for genuine 3DS-side
  defects and final release validation, so this item needs no hardware run.

## Housekeeping noted while investigating

`%APPDATA%\Citra\load\mods\` still contains `000400000007A000\romfs\codec.dat` —
the **wrong title id** (MGS3D is `0004000000081E00`), left over from the paused
codec growth experiment. It is inert because the id does not match, but it is
misleading; delete it or rename it to the correct id when that experiment
resumes.
