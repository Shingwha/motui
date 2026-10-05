# Spec 03 · Driver integration: tui.selection at the composition root (Wave W3)

> ✅ 2026-10-06 — merged via selection/w3-driver.

> Branch `selection/w3-driver`. Prerequisite: **W2 merged**. Must read:
> `specs/2026-10-05-selection/00-overview.md` (D2, D3, D8).

## Goal

Wire the kernel into the frame: the `TUI` owns one optional `Selection`,
applies `highlight` between layout and paint, and invalidates on change.
After this wave a host can set a selection programmatically and see it
rendered — no gestures yet (wave 04). This is deliberately the smallest
wave: the composition point is one line, and keeping it tiny is what keeps
the overlay honest.

## Design notes for the implementer

- `app.py` (composition root — the one legal place that knows viewport,
  painter, and selection simultaneously):
  - `tui.selection` — read property returning `Selection | None`.
  - `tui.set_selection(selection: Selection | None) -> None` — stores,
    invalidates. This is the entire write API; no anchor/head sugar on
    the driver (that is gesture-level policy).
  - Frame composition becomes
    `layout = self.viewport.layout(w, h)` → `layout = highlight(layout,
    self._selection)` → `self.painter.paint(layout)` — in `_paint_at` (or
    the single frame method W1 left). `tui.rows` therefore reports the
    *presented* (highlighted) frame, so `snapshot` pins selection for
    free.
- **Reflow clears selection (D8):** the width-change detection that
  already exists in the frame path is where `self._selection = None`
    lands; document it in the `set_selection` docstring.
- Resize/scroll interactions to verify (tests): scrolling does **not**
  clear or move the selection (document addresses); reflow does; a
  removed block's rows simply stop highlighting (overlay skips).
- `core/selection.py` imports stay kernel-side; `app.py` imports
  `core.selection.highlight` — legal top-level → core direction.
- The overview's API table is binding: root does **not** grow these names
  (driver attributes, not imports); `core` facade gains
  `Selection`/`highlight`/`extract` in this wave (update
  `tests/test_api_root.py`'s core pin — an intentional, documented pin
  change; ordering convention holds).

## Work order (each task = one commit, gate green)

### T1 · The seam
- `tui.selection` / `set_selection` + the `highlight` call in the frame
  path + reflow clearing.

### T2 · Facade pin + tests
- `core` facade += `Selection, highlight, extract`; api-root pin updated.
- Tests (headless, via `headless_tui` + `_doubles`): set → paint → the
  affected rows carry the merged `SELECTION` style and untouched rows are
  byte-identical; scroll leaves it in place; reflow clears; `snapshot`
  shows it; `set_selection(None)` restores the exact un-highlighted rows.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. Inline script: headless TUI, two sealed text blocks, select across
  them, print `[seg.style == SELECTION for row in tui.rows]` summary —
   verbatim.

## Forbidden

- `keys/**`, the gesture (wave 04), `widgets/**`, `chat/**`,
  `core/selection.py` internals (read-only; report if a kernel gap blocks
  you instead of editing), `examples/**`, README, docs, `specs/**`,
  `pyproject.toml`.

## Report

Per the overview format; include the exact frame-composition diff site.
