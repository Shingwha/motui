# Spec 01 · The frame kernel and the single-pane migration (Wave W1)

> Branch `chrome/w1-frame`. Prerequisite: both 2026-10-05 groups closed.
> Must read: `specs/2026-10-06-frame-chrome/00-overview.md` (the
> three-space-claims constitution, D1, D7).

## Goal

Introduce `core/frame.py` — the rect algebra and the multi-pane compositor —
and migrate `TUI` onto it as a **single-pane frame**, with the demo dump
byte-identical and every existing test green. Multi-pane composition must be
exercised by kernel tests even though no public API creates a second pane
until W5: the abstraction must be real, not aspirational.

## Design notes

- `Rect` (frozen: x, y, width, height) and `split_rect(rect, orientation,
  sizes)` where `sizes` uses the fixed/flex vocabulary of the widgets'
  `Row`/`Column` (fixed cells first, flex share the remainder — same
  arithmetic family, lifted to frame level; reuse, don't re-derive).
- `Frame` composes: for each pane (its rect, its `Viewport`, empty chrome
  list for now — W2 fills it): lay out the viewport at the pane's inner
  rect, splice the returned rows into the frame rows at the right
  columns/rows, and build the **frame-level ownership table** — one
  `(pane_id, block_id, row_in_block)` (or `None`) per screen cell row,
  plus per-row column spans (a pane owning columns 0..39 of a row).
- **Per-pane `ScreenLayout`s stay exactly as they are** (selection's
  `highlight` walks them; `row_blocks`/`block_order` unchanged). The frame
  table is a NEW structure for routing — do not reshape the existing one.
- `ScreenLayout` gains `offset: int` and `total_rows: int` fields
  (defaults 0) populated by `Viewport.layout` — chrome (W3) is then a pure
  function of the layout, never of live viewport attributes.
- `app.py`: `TUI` holds `self._frame` (one pane: the primary). `_paint_at`
  becomes: refresh size → frame compose → overlay call site (still just
  selection for now, unchanged) → paint. `hit_test` routes through the
  frame table (single pane must resolve identically to today, including
  the 0-based clamp behavior and the removed-block `None`). Scroll
  facades call `self._frame.focused_pane.viewport` — one pane, same
  object as today. `tui.document`/`tui.viewport` unchanged accessors.
- Byte-identity discipline: the frame's single-pane composition must
  produce the exact row stream `viewport.layout(w, h)` produces today —
  same rows, same order, same `ScreenLayout` values inside. Where the
  compositor would rewrite rows (e.g. slicing to pane width), verify the
  full-width path is a pass-through, not a re-slice.

## Work order (each task = one commit, gate green)

### T1 · Rect + split algebra + compositor (kernel)
- `core/frame.py` with `Rect`, `split_rect`, the compositor, and the frame
  ownership table. Kernel tests: split arithmetic (fixed/flex, min sizes,
  zero/negative guards), 2-pane and 4-pane (nested) composition over
  `_doubles` rows, ownership table correctness, pane rects respected.

### T2 · ScreenLayout gains offset/total_rows
- Populated by `Viewport.layout`; existing equality users unaffected
  (defaults); kernel tests pin them against known documents.

### T3 · TUI migrates onto the frame
- `app.py` single-pane migration; `hit_test` through the frame table;
  full suite + demo byte-identity; any test that pinned the old call
  shape updates mechanically (no assertion weakened).

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-05-api-overhaul/ref/pi-demo-baseline.txt`
   — no diff.
3. An inline 2-pane kernel script (build a frame over two documents,
   compose, print the row texts and the ownership table) — verbatim.
4. `uv run python -c "import mocode_tui; print(len(mocode_tui.__all__))"`
   → 65 (root untouched).

## Forbidden

- Public API additions (root, facades) — kernel + `app.py` internals only.
- `widgets/**`, `chat/**`, `keys/**`, `core/selection.py` (read-only;
  report a gap instead of patching), `examples/**`, README, docs,
  `specs/**`, `pyproject.toml`.

## Report

Per the overview format; include the compositor's pass-through proof (how
you established the single-pane row stream is today's stream, not a
re-derivation).
