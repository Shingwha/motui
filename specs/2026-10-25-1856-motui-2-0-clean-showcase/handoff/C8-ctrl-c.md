# C8 · Ctrl+C is a quiet quit

> 2026-10-25, after C7 (`4d8c633`)

## Problem

`python -m motui.demo` printed a traceback on Ctrl+C.  The signal cancels
the session task; `Runtime._run` observes `CancelledError`, tears down
(on_stop / owned source / screen leave) and re-raises; `asyncio.run` then
raises `KeyboardInterrupt` at the sync entry, which was uncaught.

## Fix

- `App.run` and `Runtime.run` wrap `asyncio.run(...)` in
  `except KeyboardInterrupt: pass`.  The teardown path is unchanged; only
  the sync entry's traceback is suppressed.
- `on_stop` still runs: the cancellation unwinds `App._loop` through its
  `finally`, and `_run`'s `_teardown` still closes the owned source and
  leaves the screen.
- Two regression tests monkeypatch the sync entry's `asyncio.run` to raise
  `KeyboardInterrupt` and assert `App.run()` / `Runtime.run()` return
  quietly.

## Gates

```
pytest              1641 passed
semantic --check    5 scenes match
ruff / pyright      0 / 0
api --check         188 names
```
