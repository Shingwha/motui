# Spec 03 · Scrollbar: the first pane chrome (Wave W3)

> Branch `chrome/w3-scrollbar`. Prerequisite: **W2 merged**. Must read:
> `specs/2026-10-06-frame-chrome/00-overview.md` (D2, chrome tier).

## Goal

`Scrollbar` — the reference chrome: a budgeted right-edge strip whose
thumb maps the pane's `offset/total_rows`, with drag and track-click
input. Root grows to 66. The demo stays untouched (attaches in W6).

## Design notes

- New assembly module `src/mocode_tui/chrome.py` (peer of
  `selection.py`): `Scrollbar(tui, *, pane=None (primary), size=1,
  min_thumb=1, style=None, thumb_style=None)` — construct = attach
  (register the pane chrome), `detach()` = unregister. Styles resolve
  via the charter (explicit > theme > DEFAULT; a `Theme.scrollbar`
  field may be added following the Theme's frozen-replace pattern —
  decide while implementing; if added, update the theme table tests).
- Thumb geometry (pure, in the chrome's paint): `thumb_len =
  max(min_thumb, round(viewport_rows * height / total_rows))`, clamped to
  the strip height; `thumb_pos = round(offset * (height - thumb_len) /
  max(1, total_rows - viewport_rows))`. Track cells are the strip's
  un-thumb cells. All arithmetic documented — this is the kind of math
  a spec must pin so tests can too.
- Input (`handle(event) -> bool`, the established contract): a press in
  the strip column routes to the bar — on the thumb: grab-and-drag
  (motion maps the thumb's center to offset); on the track above/below:
  jump one viewport page toward that side, and while held, repeat on a
  `tui.every` ticker (the selection-autoscroll pattern: document-space
  arithmetic, stop on release/edge-exit/detach); wheel events pass
  through (`scroll_keys` already owns them). Strip hits resolve through
  the frame table's pane span BEFORE any content hit_test — the host's
  dispatch order (chrome before gestures before own dispatch) is
  documented in the module docstring.
- The chrome's `paint` is a pure function of the pane's `ScreenLayout`
  (offset/total_rows from W1) — never reads live viewport attributes.

## Work order (each task = one commit, gate green)

### T1 · The chrome (geometry + paint)
- Strip rendering with the documented geometry; kernel-level tests over
  `_doubles` layouts (offset/total edge cases: empty doc, doc shorter
  than window, offset 0, offset at max).

### T2 · The gesture (drag + track-repeat)
- `handle` + the every ticker; headless tests via ScriptedKeys + `_clock`
  (drag maps positions exactly; track repeat advances pages and stops on
  release; pass-through of non-strip events).

### T3 · Root pin + theme decision
- Root 65→66 (`Scrollbar`), api-root pin; theme field decision recorded
  either way; module docstring documents dispatch order.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff (nothing attached to the demo).
3. Inline script: a 100-row document in a 10-row headless pane, attach a
   Scrollbar, scroll to offset 45, paint, print the strip column's row
   texts (track/thumb glyphs) — verbatim.
4. `uv run python -c "import mocode_tui; print(len(mocode_tui.__all__))"`
   → 66.

## Forbidden

- `core/**` beyond the theme-field decision (read-only otherwise; a gap
  in the W2 registration surface gets reported, not patched),
  `app.py`, `keys/**`, `widgets/**`, `chat/**`, `examples/**`, README,
  docs, `specs/**`, `pyproject.toml`.

## Report

Per the overview format; include the theme-field decision and the exact
dispatch-order contract.
