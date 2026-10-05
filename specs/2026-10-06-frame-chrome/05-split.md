# Spec 05 · Splits, focus, and the Composer promotion (Wave W5)

> ✅ 2026-10-06 — merged via chrome/w5-split (+ the split-time adoption fix).

> Branch `chrome/w5-split`. Prerequisite: **W4 merged**. Must read:
> `specs/2026-10-06-frame-chrome/00-overview.md` (D4, D5, D6, D7).

## Goal

The pane tier goes public: `tui.split(...)` / `pane.split(...)`,
tmux-style separators with focus accent, pointer-routed wheel, focused
keys, and the Composer lifted to a frame-level bottom band. Root grows to
68. Single-pane behavior stays pinned-identical (the migration proof).

## Design notes

- `Pane` is the public handle: `.document`, `.viewport`, `.focus()`,
  `.split(...)`; created only by splitting (the primary pane pre-exists).
  `tui.split(orientation, *, ratios=(1, 1), min_size=1, separator=True)
  -> (Pane, Pane)` — sizes via the fixed/flex vocabulary from W1.
- **Separator**: 1-cell inter-pane chrome (the W2 mechanism), the focused
  pane's side drawn in the theme's accent when `separator=True` — the
  tmux convention; `False` leaves no gap (panes abut).
- **Focus**: `frame.focused` + `pane.focus()`; the default policy —
  a mouse press resolves to a pane and focuses it — lives in the
  driver's event path as a replaceable step (a `focus_policy=` hook on
  TUI, default set; hosts swap it). Keys/scroll facades route to the
  focused pane; wheel routes by pointer (D5): the frame table resolves
  the pane under the pointer, falling back to the focused pane.
- **`read_key`/`scroll_keys`**: interception unchanged in mechanism, the
  scroll target becomes the resolved pane (single pane = today's
  behavior, pinned).
- **Selection (D7)**: `tui.set_selection` applies to the focused pane's
  layout; `hit_test` is already frame-routed (W1). `SelectionGesture`
  needs no change for single-pane use; a multi-pane-aware gesture is
  documented future work.
- **Composer promotion (D6)**: the chat composer's five bottom-pinned
  blocks move from the primary viewport's pins to a frame-level bottom
  band (the frame reserves the band's rows below the pane area; the band
  is itself a tiny viewport region over the composer's document). With
  one pane and no split this MUST render identically to today (pinned by
  the chat tests unchanged); with a split the band spans the full width
  beneath both panes. `chat/composer.py` internals adapt; its public API
  does not change.
- `TUI.hit_test`/`rows`/`paint` semantics unchanged (frame-routed since
  W1). The demo still does not split (W6 does).

## Work order (each task = one commit, gate green)

### T1 · Public splits + Pane + separators
- `tui.split`/`pane.split`, focus accent separators; kernel + driver
  tests: rect math via ratios/fixed/flex, nested splits, separator
  rendering with focus accent both sides.

### T2 · Focus + wheel routing
- `frame.focused`, `focus_policy` hook, press-to-focus default, wheel
  pointer routing, key routing to focused pane; single-pane identity
  pins.

### T3 · Composer to the frame band
- The promotion; all existing chat tests green unchanged (the
  equivalence proof); a two-pane chat-layout test showing the band
  spanning the split.

### T4 · Root pin
- Root 67→68 (`Pane`); api-root pin; module docstrings for the new
  dispatch order (chrome → overlays → panes' content).

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. Inline script: headless TUI, `left, right = tui.split("vertical",
   ratios=(2, 1))`, transcript rows in left pane, a Markdown preview in
   right, focus right, wheel over left, paint — print the composed row
   texts showing the separator and both panes — verbatim.
4. Root → 68.

## Forbidden

- `core/selection.py`, `keys/**` (read-only), `widgets/**`,
  `examples/**`, README, docs, `specs/**`, `pyproject.toml`. `chat/**`
  is open ONLY for the composer promotion (T3) — report anything else.
- Weakening any existing chat test (they are the equivalence proof).

## Report

Per the overview format; include the band-promotion diff shape and the
focus-policy hook signature.
