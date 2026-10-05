# Spec 02 · Chrome budgets and the overlay pipeline (Wave W2)

> ✅ 2026-10-06 — merged via chrome/w2-pipeline.

> Branch `chrome/w2-pipeline`. Prerequisite: **W1 merged**. Must read:
> `specs/2026-10-06-frame-chrome/00-overview.md` (the three-space-claims
> constitution, D1).

## Goal

Turn W1's frame into the extension gate: panes negotiate chrome edge
budgets before their viewport lays out, and composed frames run through an
ordered overlay pipeline before painting. The selection highlight migrates
to be overlay #1 — **rendering byte-identical** — proving the pipeline with
the one overlay that already exists. No shipped chrome/overlay yet (W3/W4).

## Design notes

- **Chrome protocol** (kernel, `core/frame.py` — the mechanism only): a
  pane chrome declares `edge: str` ("left"/"right"/"top"/"bottom"),
  `size: int` (cells), and `paint(layout, length) -> list[Line]` — one row
  per cell of the strip, each exactly `size` wide, pure. The compositor
  asks each pane's chromes for their budgets, subtracts them from the
  pane's inner rect (multiple chromes stack; budgets add; opposite edges
  both subtract), lays out the viewport in the remainder, and splices the
  strips into the pane's rectangle. `size: 0` chrome is legal (paints
  nothing, budgets nothing) — the no-op seam custom renderers grow from.
- **Overlay protocol**: `paint(frame) -> frame`, an ordered registry on
  the frame; the composition root runs it after compositing. The frame
  value passed to overlays carries the composed rows, the ownership
  table, and per-pane layouts (an overlay like a toast needs bounds; an
  overlay like the highlight needs the pane layouts).
- **Selection migration**: `tui.set_selection` unchanged; internally the
  driver registers a selection overlay wrapping the existing
  `highlight(...)` call. Multi-pane note (D7): the overlay applies to the
  focused pane's layout — with one pane, identical to today. Byte-identity
  is the gate: no re-styling, no order change, `None` still an identity.
- Registration API shape (driver-level, not root-public): panes accept
  chrome via a small explicit method; the frame accepts overlays the same
  way. Assembly modules (W3/W4) are the first consumers. Keep the
  registration surface minimal and documented — it is the customizability
  charter's front door.

## Work order (each task = one commit, gate green)

### T1 · Chrome budget negotiation in the compositor
- Protocol + budget math + strip splicing; kernel tests: stacked chromes,
  opposite edges, zero-size chrome, over-budget guards (chrome never
  shrinks a pane below 1 cell of viewport).

### T2 · Overlay registry + selection migration
- Registry, ordering, the driver's selection overlay; every existing
  selection test passes unchanged; demo byte-identical.

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. Inline kernel script: a 2-pane frame where one pane carries a 1-column
  right chrome painting a marker row — print the composed rows showing
  the strip and the re-wrapped pane content — verbatim.
4. Root stays 65.

## Forbidden

- Public API additions; `core/selection.py` (read-only); `widgets/**`,
  `chat/**`, `keys/**`, `examples/**`, README, docs, `specs/**`,
  `pyproject.toml`.

## Report

Per the overview format; include the exact registration surface you
settled on (it becomes W3/W4's foundation).
