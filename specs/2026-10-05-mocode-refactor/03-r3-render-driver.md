# Spec R3 · Render core + driver tidy (`Painter.throttle` out, docs sync)
> ✅ 2026-10-05 @ merged to main (R1 703/2, R2 698/1, R3 701/2, R4 703/2, R5 700/1, R6 202/1 — final gate)

> Branch `refactor/r3-render-driver`; worktree `~/.worktrees/mocode-tui/refactor-r3-render-driver`;
> depends on: R1 merged; deep-read: `00-overview.md`, `docs/DESIGN.md`.

## Goal

Remove the last piece of theatre in the render core: `Painter.__init__` takes
a `throttle` it stores and never reads (its own docstring says "accepted for
API stability only" — this group explicitly does not owe API stability for
dead weight). The real throttle lives on `TUI` and stays. Everything else in
the render core/driver is kept; this wave is small on purpose.

## Write scope (exclusively yours)

- `src/mocode_tui/painter.py`, `src/mocode_tui/app.py`, `src/mocode_tui/screen.py`,
  `src/mocode_tui/viewport.py`, `src/mocode_tui/testing.py`
- `tests/test_painter.py`, `tests/test_app.py`, `tests/test_screen.py`,
  `tests/test_viewport.py`
- `docs/DESIGN.md` (the two sentences named in T2)
- nothing else — no `keys*`, no `components*`, no root `__init__.py`, no README.

## Tickets (one commit each)

### T1 — drop `Painter(throttle=...)`

- Remove the parameter, the `self._throttle` field, and the docstring sentence
  about API stability from `painter.py`; remove `throttle=throttle` from the
  `Painter(...)` construction in `app.py` (`TUI.throttle` remains the pump's
  throttle and keeps its public attribute).
- Fix `tests/test_painter.py` / `tests/test_app.py` if any construct
  `Painter(..., throttle=...)` or assert `painter._throttle` (grep first).

### T2 — DESIGN.md truth pass for the render core

Update only what T1 changed plus any other sentence in the "The painter"
section that is now wrong. Two known drifts to fix in the same commit:

- the "Painter accepts a `throttle` for API stability but never blocks; the
  driver decides when a frame is due" sentence → the driver's `TUI.throttle` is
  the only throttle;
- the module tree comment at the bottom of README is NOT yours (R5 owns
  README) — leave it.

### T3 — `HeadlessScreen.clear()` verdict

`grep -rn "\.clear()" src examples tests` today: only `tests/test_screen.py`
uses `screen.clear()`. Decide: if after T1–T2 nothing in `src/`/`examples/`
uses it, delete the method and its test (a recorder's buffer does not need a
public reset while `output` is the documented face); if you keep it, say why in
the report. Either way the file must stay self-consistent.

### T4 — scroll-state read-only props verdict

`Viewport.offset/total_rows/viewport_height/at_bottom` are referenced only by
`tests/test_viewport.py`. They are part of the documented scroll-state surface
(DESIGN.md describes `offset` and stick-to-bottom semantics), so **keep them**;
do not add, rename or delete anything here. This ticket exists only to record
the decision — if you disagree, report it, don't act.

## Acceptance (run in your worktree, report real output)

1. `uv run pytest -q` — green; report the exact line.
2. `uv run python -c "import inspect; from mocode_tui import Painter; print(inspect.signature(Painter.__init__))"`
   — no `throttle`.
3. `uv run python -c "from mocode_tui import TUI; t = TUI(screen=__import__('mocode_tui').HeadlessScreen(), interactive=False); print(t.throttle)"`
   → `0.03`.
4. `uv run python examples/pi_demo.py < /dev/null > out.txt; echo exit=$?; sha256sum out.txt`
   — equals the R0 baseline `71d09ff2…c9a1c981`.

## Red lines

- No rendering-behavior change; the painter's frame logic is frozen this wave.
- No new public names on `TUI`/`Painter`; no renames of methods the other waves'
  files call (`flush`, `rows`, `scroll_*`, `set_cursor_anchor` stay).
- If T1 turns out to have a hidden consumer you did not expect (e.g. the demo),
  stop and report.

## Report format

Ticket status table / commit hashes+messages / real outputs for the four
acceptance commands / `HeadlessScreen.clear` verdict with the grep proof /
deviations & open questions.
