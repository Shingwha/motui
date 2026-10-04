"""Temporary diagnostic: show the input path and every key event received.

Run in the terminal where the demo misbehaves (PowerShell):

    uv run python probe_keys.py

Type characters, press Enter, use arrows/PageUp/PageDown; Ctrl-C quits.

The banner reveals:
  path      console = ReadConsoleInputW records fed to the decoder (the
            correct interactive path on Windows)
            bytes   = os.read + KeyDecoder (POSIX raw, or byte-mode console)
            line    = cooked fallback (stdin is not a console / raw entry failed)
  tty       whether Python thinks stdin/stdout are TTYs
  mode      console input mode before/after start() (0x200 = VT input bit;
            a non-zero "before" VT bit means a previous run left it dirty)

If characters never produce EVENT lines, keys never reach the reader.
If 'enter' events are missing while characters work, Enter is consumed
upstream (IME composition or selection mode).
If arrows print Key('[') / Key('A') instead of Key('up'), sequences are
still fragmenting -- report the output.
"""

from __future__ import annotations

import asyncio
import os
import sys

from mocode_tui.keys import RawTerminalKeys


def _banner(src: RawTerminalKeys) -> None:
    tty_in = sys.stdin.isatty() and "yes" or "no"
    tty_out = sys.stdout.isatty() and "yes" or "no"
    print(f"tty  stdin={tty_in} stdout={tty_out}", flush=True)
    console = getattr(src, "_console", False)
    line = getattr(src, "_cooked_fallback", False)
    path = "console" if console else ("line" if line else "bytes")
    print(f"path={path}", flush=True)
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                print(f"mode now=0x{mode.value:x} (0x200 = VT input)", flush=True)
        except Exception:
            pass


async def main() -> None:
    src = RawTerminalKeys()
    src.start()
    _banner(src)
    print("--- type, arrows, PageUp/Down, Enter, Backspace; Ctrl-C quits ---", flush=True)
    while True:
        try:
            event = await asyncio.wait_for(src.read(), timeout=30.0)
        except asyncio.TimeoutError:
            print("... 30s idle, exiting", flush=True)
            break
        if event is None:
            print("EOF", flush=True)
            break
        print(f"EVENT {event!r}", flush=True)
    src.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCtrl-C: done", flush=True)
