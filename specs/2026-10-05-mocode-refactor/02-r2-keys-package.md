# Spec R2 · `keys.py` → `keys/` package (events / decoder / sources / console)
> ✅ 2026-10-05 @ merged to main (R1 703/2, R2 698/1, R3 701/2, R4 703/2, R5 700/1, R6 202/1 — final gate)

> Branch `refactor/r2-keys-package`; worktree `~/.worktrees/mocode-tui/refactor-r2-keys-package`;
> depends on: R1 merged; deep-read: `00-overview.md`, `docs/DESIGN.md` (Keys section).

## Goal

`keys.py` is 881 lines mixing four concerns: the event model, a pure decoder,
runtime key sources, and ~200 lines of Windows console plumbing (ctypes
structures, virtual-key tables, console-record mapping). Split it into the
`keys/` package below so the decoder stays pure and platform-free, the Windows
path is isolated, and each concern is reviewable on its own. **The public
import surface does not change**: `from mocode_tui.keys import Key, KeyDecoder,
KeySource, MouseEvent, Paste, RawTerminalKeys, ScriptedKeys` keeps working, and
the package-root imports in `src/mocode_tui/__init__.py` need no edit.

## Target layout

```
src/mocode_tui/keys/
  __init__.py    # re-exports the seven public names (+ two transitional seams, see T4)
  events.py      # Key, MouseEvent, Paste, KeySource protocol
  decoder.py     # KeyDecoder, _char_key, key tables (_FINAL_KEYS, _TILDE_KEYS, ...),
                 #   _PASTE_* markers, SGR mouse report decode
  sources.py     # ScriptedKeys, RawTerminalKeys, _stdin_fd, _SETTLE_SECONDS,
                 #   _CONSOLE_BATCH (imports windows helpers from .console)
  console.py     # everything Windows: mode bits, _VK_KEYS, _key_from_console_event,
                 #   _key_from_values, _console_record_events, keys_from_console_events,
                 #   ctypes structs, _kernel32, windows_input_mode
```

`decoder.py` must not import anything platform-specific; `console.py` may
import `Key`/`KeyDecoder` from its siblings. `git mv` history is nice-to-have;
content placement is what matters.

## Write scope (exclusively yours)

- `src/mocode_tui/keys.py` (deleted) and the five new `src/mocode_tui/keys/*.py`
- `tests/test_keys.py`, `tests/test_keys_windows.py`
- nothing else — do NOT touch `src/mocode_tui/__init__.py`, `app.py`, `testing.py`,
  components, docs, demo, or any other test file.

## Tickets (one commit each)

### T1 — create the package, move code verbatim

Move the code into the four modules with **no logic edits**, keeping every
docstring. `keys/__init__.py` re-exports the seven public names in
`__all__`, plus (T3) the two transitional seams. `sources.py` keeps
`import time`, `os`, `select`, `queue`, `threading`, `asyncio`, the executor
bridge and both reader paths. `console.py` keeps `ctypes` and the Windows-only
imports (`msvcrt` stays imported lazily inside `RawTerminalKeys._start_windows`
in `sources.py` as today).

### T2 — internal import rewire

Within the package use relative imports (`from .events import Key, Paste`,
`from .decoder import KeyDecoder`, `from .console import windows_input_mode,
_key_from_console_event, _console_record_events`). Verify `grep -rn "from .keys
import\|import keys" src tests` shows nothing stale outside `keys/__init__.py`.

### T3 — keep the transitional seams until R6

`keys/__init__.py` additionally exposes `windows_input_mode` and
`keys_from_console_events` (imported from `.console`, documented as the console
module's stable test seams). These stay out of `__all__`; R6 decides their
final shape. `RawTerminalKeys`'s settle-window behavior keeps working through
`_SETTLE_SECONDS` living in `sources.py`.

### T4 — trim the fragile Windows-plumbing tests (this wave, not R6)

In `tests/test_keys_windows.py` delete (these are ratified fragile tests —
they assert SDK struct sizes/offsets, never-called kernel32 prototypes, or
monkeypatch a module-global clock):

- the ctypes structure size/offset asserts (`skipif os.name != "nt"` tier),
- the kernel32-prototype static asserts,
- the tests that monkeypatch `keys_mod.time` / `keys_mod._SETTLE_SECONDS`
  (the "settle window math" and "settles only after the window" ones).

Keep the settle-window *behavior* test but drive it with real time: the
default window is 50 ms — write to the pipe, wait past it, assert the escape
key arrives (a real `asyncio.sleep(0.12)` with a generous pytest timeout is
acceptable; `pyproject.toml` already sets `timeout = 30`). Keep the
`windows_input_mode` pure tests (3–4 of them) and the record-mapper tests via
the public-ish seams. Update the module docstring to describe the new testing
tiers (the old one describes ctypes tiers you just removed).

### T5 — keep everything else in the two test files behavior-identical

`tests/test_keys.py` must pass unedited (it imports only public names). For
`tests/test_keys_windows.py`, only the deletions/rewrites in T4 plus import
fixes; do not rewrite passing tests. If `keys_mod` is still used in the file,
point it at the new package (`from mocode_tui import keys as keys_mod`) so the
remaining seams resolve.

## Acceptance (run in your worktree, report real output)

1. `uv run pytest -q` — green; report the exact line (expect 716 minus ~10
   fragile tests, give the real number).
2. `uv run python -c "import mocode_tui.keys as k; print(k.__file__)"` — a path
   inside `.../keys/__init__.py`.
3. `uv run python -c "from mocode_tui.keys import Key, KeyDecoder, KeySource, MouseEvent, Paste, RawTerminalKeys, ScriptedKeys; from mocode_tui import TUI; print('ok')"`.
4. `uv run python -c "
from mocode_tui.keys import KeyDecoder
d = KeyDecoder()
print(d.feed(b'\x1b[A'), d.feed(b'x'), d.settle())"` — `[Key(name='up')] [Key(name='x', char='x')] []`.
5. `uv run python examples/pi_demo.py < /dev/null > out.txt; echo exit=$?; sha256sum out.txt` —
   equals the R0 baseline `71d09ff2…c9a1c981`.

## Red lines

- No behavior change in the decoder or the sources; a pure move plus the T4
  deletions. If a test fails because of a *move* mistake, fix the move; if it
  fails because of a design flaw you discover, stop and report.
- Do not touch other modules or docs (DESIGN.md's Keys section stays accurate
  as-is: it names no file paths).

## Report format

Ticket status table / commit hashes+messages / real outputs for the five
acceptance commands / list of deleted tests with reasons / deviations & open
questions.
