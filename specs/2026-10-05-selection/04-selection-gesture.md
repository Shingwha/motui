# Spec 04 · SelectionGesture: the policy tier (Wave W4)

> Branch `selection/w4-gesture`. Prerequisite: **W3 merged**. Must read:
> `specs/2026-10-05-selection/00-overview.md` (D3–D6, D8) — this wave is
> where every policy decision lands, and none of them may leak downward.

## Goal

The assembly-level controller that turns mouse events into selection
state, auto-scrolls at the viewport edge on a pump timer, selects words on
double-click, and runs the `on_end` hook (default: copy via OSC 52).
Hosts opt in with one line; every behavior is replaceable or disableable.

## Design notes for the implementer

- **New top-level module `src/mocode_tui/selection.py`** (peer of
  `app.py` / `testing.py`; imports core + app — the assembly tier).
  Ships: `SelectionGesture`, `copy_on_select`. Root grows to 65 names
  (`SelectionGesture`, `copy_on_select`) — update the api-root pin
  (intentional, documented).
- **Constructor**: `SelectionGesture(tui, *, on_end=copy_on_select,
  scroll_rows=2, scroll_tick=0.05, double_click_seconds=0.35)`.
  `on_end=None` selects without any effect. `on_end` receives the
  `Selection`; `copy_on_select(tui, selection)` = `extract` +
  `screen.copy` (a two-line function — its smallness is the proof that
  the mechanism/policy split worked).
- **`handle(event) -> bool`** — the established consume-a-key contract
  (`Input.handle_key`, `Editor.handle_key`): returns `True` when the
  event advanced the gesture. It consumes: left-press (anchors, cancels
  autoscroll), motion while dragging (extends), left-release (finalizes).
  It passes through everything else. The host's dispatch loop is
  `if not gesture.handle(event): …own dispatch…`.
- **Drag geometry (D1/D4)**: press → `hit_test` → anchor; motion →
  `hit_test` → head; `Selection.between(anchor, head)`. Wheel **during**
  a drag shifts content under a still pointer — extend the head by the
  same signed row count (pure document-space arithmetic, one code path
  shared with autoscroll).
- **Edge auto-scroll (D4/D5)**: motion landing on the first/last row of
  the **viewport region** (from the last layout's `viewport_rows` bounds;
  never the pinned rows) starts a `tui.every(scroll_tick, …)` handle that
  scrolls `scroll_rows` per tick and extends the head by the same amount;
  it stops on edge-exit, release, detachment, or the document's end
  (viewport pinned at bottom/top). Never re-`hit_test` inside a tick —
  the identity "scroll n rows ⇒ content under a fixed screen row moves n
  document rows" is the mechanism. Block-boundary crossings and clamping
  to the document's first/last row must be handled by the same walk.
- **Double-click word select**: the controller tracks the last press
  (cell + `_clock()` time); a second press within
  `double_click_seconds` at the same cell selects the maximal
  non-whitespace run around the cell on that row (CJK included). No
  triple-click (out of scope). Timestamps live in the controller — the
  event model stays timeless.
- **Lifecycle**: zero-width press-release at one cell **clears** the
  selection and does not fire `on_end` (never clobber the clipboard with
  a click). A completed drag fires `on_end(selection)` once; the
  highlight stays until the next press (users verify what they copied).
  `detach()` cancels the autoscroll handle and clears — the
  `EveryHandle`/Composer cleanup convention. Reflow already cleared the
  selection at wave 03; a gesture still mid-drag across a reflow ends
  the drag cleanly.
- **Testing (headless, the `_clock` seam)**: inject press/motion/release
  sequences via `ScriptedKeys`; drive autoscroll by advancing the clock
  and asserting (a) the viewport offset moved, (b) the selection extended
  by exactly `ticks × scroll_rows` document rows, (c) the ticker stops at
  the document end, (d) `on_end` fired once with the extracted text,
  (e) a plain click cleared without firing. Use `RecordingScreen` to
  assert the OSC 52 bytes landed on the headless stream.

## Work order (each task = one commit, gate green)

### T1 · Press / drag / release / clear
- Anchoring, extension, finalization, `on_end`, zero-width clear,
  `handle` contract, `copy_on_select`.

### T2 · Edge auto-scroll + wheel-during-drag
- The `every` ticker, document-space head arithmetic, stop conditions,
  detach cleanup, wheel co-extension.

### T3 · Double-click word select + root pins
- Time-window tracking, word-run selection; root 63→65 + api-root pin
  update; demo untouched.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. Inline headless script: 200-row document, press at viewport bottom
  edge, advance `_clock` by 10 ticks, print viewport offset + selection
  head row + `RecordingScreen` tail showing the OSC 52 emission on
  release — verbatim.
4. `uv run python -c "import mocode_tui; print(len(mocode_tui.__all__))"`
   → 65.

## Forbidden

- `core/**` (read-only — a kernel gap gets reported, not patched),
  `keys/**`, `widgets/**`, `chat/**`, `app.py` (read-only; wave 03 landed
  the seam), `examples/**`, README, docs (wave 05), `specs/**`,
  `pyproject.toml`.

## Report

Per the overview format; include the ticker's stop-condition list and the
word-run rule as implemented.
