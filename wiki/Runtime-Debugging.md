# Runtime Debugging (Citra/Azahar + GDB)

Confirmed working recipe for GDB-attaching to the 3DS emulator for this
project. **Read this fully before attempting an attach** — several steps here
exist specifically because skipping them wastes the one-shot session (below).

## Core rule: never probe the stub port

**Do not connect-then-close to check if the GDB stub is up** — not with a raw
socket, not with `Test-NetConnection`. Both have been mistaken, twice, for
diagnosing a broken server: TCP `recv()` returning 0 on disconnect looks
identical whether it's a probe or a real failed attempt. In reality, probing
**consumes the stub's one accept**, and the following real attach then dies
with `^error,msg="Remote replied unexpectedly to 'vMustReplyEmpty': timeout"`.
That error string is the signature of a *used-up* stub, not a broken one.
There is no safe way to check the port — fixed-wait ~18–20s after launching,
then attach.

## Setup

1. `qt-config.ini` (`C:\Users\hhlee\AppData\Roaming\Azahar\config\qt-config.ini`,
   `[Debugging]`): set **both** `use_gdbstub=true` and
   `use_gdbstub\default=false` — the `\default` flag wins on the next load if
   left stale, silently resetting the real value back to `false` with no error
   anywhere. Confirm by checking the log stalls early (mid-renderer-init), not
   by trusting the file.
2. Same file: `graphics_api=1` (OpenGL), not `2` (Vulkan). Vulkan self-crashes
   under sustained play (`RendererVulkan::LoadFBToScreenInfo` assertion,
   observed at guest t=106–117s) — OpenGL gives a much longer attach window.
   Restore to `2` when done.
3. Before attaching: `tasklist` for stray `python.exe` / `arm-none-eabi-gdb.exe`
   / `azahar.exe` and kill leftovers. A stale daemon can squat on the control
   port and silently steal commands meant for the new one.

## Launch

```powershell
Start-Process -FilePath $exe -ArgumentList "--gdbport=24689", "`"$cci`"" -WorkingDirectory $dir -PassThru
```

- `-WorkingDirectory` must be the folder containing `azahar.exe` itself, or the
  portable build silently fails to find its DLLs (no window, no error).
- Any spaced path needs its own embedded quotes inside the array element —
  PowerShell does not auto-quote. Always use `--gdbport=24689` (`=` form, not
  space-separated — `-g 24689` gets misparsed as two file arguments).
- Confirm the halt via
  `C:\Users\hhlee\AppData\Roaming\Azahar\log\azahar_log.txt` showing
  `Debug.GDBStub GDBStub::Init: Starting GDB server on port 24689...`.

## Attach and use

- Attach: `tools/citra_gdb_mi_controller.py --daemon --log <path>` (real
  `arm-none-eabi-gdb.exe`, devkitPro, MI protocol).
- Talk to it only via `python tools/citra_gdb_mi_controller.py --command <cmd>`
  (control port 24700): `snapshot` (interrupt + registers + stack +
  disassembly in one shot — the most useful single command), `continue`,
  `interrupt`, or `mi "<raw MI command>"`.

## One-shot constraint — no exceptions found

If the connection drops, it **cannot** be revived without fully closing and
relaunching `azahar.exe`. Toggling the Debug-menu checkbox off/on does not
re-trigger `GDBStub::Init`; restarting the game within the same process
instance doesn't either. **Plan the exact sequence of snapshot/breakpoint calls
before attaching** — each attach is a single precious shot from boot.

## MI quirks

- `-data-read-memory-bytes` is reliable only up to **64 bytes** per call —
  larger reads return `Unable to read memory` even for valid addresses. Chunk
  big dumps into 64 B reads.
- Never build a console command like `find /w 0x08000000, 0x09200000, 0xVALUE`
  as a PowerShell argument — PowerShell rewrites hex/comma tokens and GDB
  answers `Problem parsing arguments`. Send the exact string from Python over
  the control socket instead.
- Raw MI `-break-watch *(unsigned int*)0xADDR` fails
  (`Garbage following <expression>`) on devkitARM gdb 14.1 — use the console
  form: `-interpreter-exec console "watch *(unsigned int*)0xADDR"`.
- **Watchpoints register but often never fire** (dynarmic's JIT fast-path
  memory access plausibly bypasses the stub's check) — prefer execution
  breakpoints (`-break-insert *0xADDR`), proven to work with real hits and
  real register state. Use a watchpoint only when there's no code address to
  break on.

## Finding a heap object without a fixed address

Search live memory for a known *content* constant rather than reusing a
recorded address — heap layout shifts between builds as patched asset sizes
change it. Two-step pattern:
```text
find /w 0x08000000, 0x09200000, 0x4EE76D54   # e.g. the GCX file seed -> buffer base
find /w <range>, <that base>                  # -> the descriptor that owns it
```

Full incident history and additional gotchas:
`feedback-citra-azahar-gdb-debugging` memory (persists across sessions,
referenced from [Decisions](Decisions.md) context).
