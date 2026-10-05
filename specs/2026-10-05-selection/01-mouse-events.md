# Spec 01 · Mouse event model: release, motion, kind (Wave W1)

> ✅ 2026-10-06 — merged via selection/w1-mouse-events.

> Branch `selection/w1-mouse-events`. Prerequisite: the api-overhaul group
> fully merged (including W5 test trim). Must read first:
> `specs/2026-10-05-selection/00-overview.md` (D1–D8, red lines).

## Goal

Upgrade the input path so a gesture controller can exist: decode SGR-1006
**button release** and **motion-with-button** reports into
`MouseEvent(kind=…)`, and enable mode 1002 (button-event tracking) on live
screens. This wave is pure mechanism: nothing consumes the new event kinds
yet (the gesture is wave 04). The demo dump must not change (non-live path
emits no tracking escapes).

## Design notes for the implementer

- `MouseEvent` (in `core/events.py`) grows `kind: str = "press"` with
  values `"press" | "release" | "motion"`. Wheel events stay discrete
  reports with `kind="press"` (documented in the class docstring); the
  horizontal wheel stays dropped (the seam note remains).
- Decoder (`keys/decoder.py`, `_emit_mouse_report`): SGR finals — `M`
  without the motion bit = press, `M` **with** the motion bit (`b & 0x20`)
  = motion (button = the held button), lowercase `m` = release. The
  existing release-drop and motion-drop branches are *replaced*, not
  augmented — restructure the dispatch as a small report-class table
  (final byte → kind, motion bit, button resolution) rather than growing
  the seven-branch ladder this function was already flagged for. Malformed
  reports stay dropped.
- `core/ansi.py`: `enable_mouse_tracking()` gains `1002h` (order:
  `1000h`, `1002h`, `1006h`); `disable_mouse_tracking()` reverses exactly
  (`1006l`, `1002l`, `1000l`). These stay the only functions that build
  mouse-mode escapes.
- `core/screen.py`: `TerminalScreen(mouse=True)` now enables 1002 via the
  pair above (no separate flag — v1 has no hover use case; a `motion=`
  knob is a documented future seam, not shipped). `HeadlessScreen` records
  whatever bytes it is given; nothing else changes. NOTE the ripple: the
  byte tests that pin `enter`/`leave` output change — that is an
  intentional contract change, update them in the same commit.
- Windows console path (`keys/console.py`): the record reader must surface
  press/release/motion with the **same semantics as the VT path**. Preferred
  shape: synthesize the equivalent SGR-1006 byte payloads and feed the one
  decoder (single semantics authority); only deviate with a documented
  reason. `MOUSE_EVENT_RECORD` gives button-state transitions (press =
  newly-down bits, release = transition to zero, motion = `MOUSE_MOVED`
  flag with a nonzero state) and `FROM_LEFT_1ST_BUTTON_PRESSED` etc. map to
  left/middle/right; double-click records are reported as two presses
  (controller-side timestamps own that policy). Extend the existing
  `keys_from_console_events` test seam; do not invent a second one.
- Consumers that must keep working unchanged: `TUI.read_key`'s scroll-key
  interception (wheel names unchanged), `hit_test` callers, the demo.
  Hosts that hand-read events will now *see* motion/release events flow
  by — that is the documented behavior change of this wave, called out in
  the module docstring of `core/events.py`.

## Work order (each task = one commit, gate green)

### T1 · Decoder: release + motion + `kind`
- `MouseEvent.kind` field + docstring; `_emit_mouse_report` restructured to
  the report-class table; release/motion decode; malformed still dropped.
- Tests: extend the decoder's bytes→events table with release, motion,
  motion-with-modifier (ignored), and the kind values; assert a plain
  press decodes `kind="press"` (back-compat shape of every existing test).

### T2 · Mode 1002 on live screens
- `ansi` pair + `TerminalScreen` enablement + the enter/leave byte-test
  updates (intentional contract change — one-line rationale comment in the
  test).

### T3 · Windows console parity
- `console.py` synthesizes press/release/motion per the design notes;
  tests via the `keys_from_console_events` seam covering the three kinds
  and the double-click-as-two-presses rule.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. `uv run python - <<'PY'` feeding the decoder the byte strings for
   press/motion/release (`\x1b[<0;5;3M`, `\x1b[<32;5;4M`, `\x1b[<0;5;5m`)
   and printing the decoded `(name, kind)` — include verbatim.
4. `grep -n "1002" src/mocode_tui/core/ansi.py` — the pair, verbatim.

## Forbidden

- `widgets/**`, `chat/**`, `app.py`, `testing.py`, `core/selection.py`
  (does not exist yet — do not create it), `examples/**`, README, docs,
  `specs/**`, `pyproject.toml`.
- Consuming the new kinds anywhere (no gesture, no selection logic — pure
  decode + enable).

## Report

Per the overview format; include the console-parity decision you made
(bytes-through-decoder vs direct events) and why.
