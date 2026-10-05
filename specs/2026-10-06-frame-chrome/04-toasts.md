# Spec 04 · Toasts: the first frame overlay controller (Wave W4)

> Branch `chrome/w4-toasts`. Prerequisite: **W3 merged**. Must read:
> `specs/2026-10-06-frame-chrome/00-overview.md` (D3, overlay tier).

## Goal

`Toasts` — transient floating notifications over the composed frame:
TTL expiry, bounded stack, optional click-to-dismiss, corner placement.
Root grows to 67. The demo stays untouched.

## Design notes

- In `src/mocode_tui/chrome.py` (beside Scrollbar): `Toasts(tui, *,
  ttl=4.0, max_shown=3, corner="top-right", style=None)` — construct =
  register the overlay; `show(content, *, style=None, ttl=None) ->
  None` where `content` is a `str` **or any Component** (the
  customizability charter: a toast can be a Notice, a Spinner, a custom
  renderable). `detach()` unregisters and cancels timers.
- A toast is a `(component, style, expires_at)` record; the controller
  owns ONE `tui.every` ticker (not one per toast) that checks expiry
  against `tui._clock()` and drops due toasts (invalidate on change).
  `max_shown` evicts oldest on overflow. The overlay's `paint` renders
  each live toast at width = its natural content width clamped to
  `min(40, frame_width // 2)`, `Line.filled` background (the band
  primitive), stacked with one blank row between, anchored at the chosen
  corner inside the frame's rows, and `.fit` to the frame width — the
  same measure-don't-guess rules components follow.
- Click-to-dismiss: `handle(event) -> bool` — a press inside any live
  toast's rectangle drops that toast. Dispatch order documented
  (overlays after chrome, before content gestures).
- Purity: the overlay `paint` is a pure function of the frame value +
  the live toast list; time and input live in the controller (the
  selection/autoscroll pattern verbatim).
- Style resolution: the toast band defaults to a reverse-video dim band
  (a `Theme.toast` field may be added following the frozen-replace
  pattern — same decision discipline as W3; record it).

## Work order (each task = one commit, gate green)

### T1 · The overlay (rendering + layout)
- Pure paint; kernel-level tests: corner anchoring (all four), stack
  order and spacing, width clamp + fit, empty state paints nothing.

### T2 · The controller (TTL + stack + dismiss)
- show/expiry/eviction via `_clock`-driven tests; click-to-dismiss hit
  math; detach cancels; `str` sugar wraps a `Text`.

### T3 · Root pin + theme decision
- Root 66→67 (`Toasts`); pin; decision recorded.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. Inline script: headless TUI, show three toasts (one a custom
   component), advance the clock past two TTLs, paint, print the
   affected frame rows — verbatim.
4. Root → 67.

## Forbidden

- `core/**` beyond the theme-field decision, `app.py`, `keys/**`,
  `widgets/**`, `chat/**`, `examples/**`, README, docs, `specs/**`,
  `pyproject.toml`.

## Report

Per the overview format; include the theme-field decision and the toast
width/clamp rules as implemented.
