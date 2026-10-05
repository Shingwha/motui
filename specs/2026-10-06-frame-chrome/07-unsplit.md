# Spec 07 · Pane.close(): the un-split (Wave W7)

> ✅ 2026-10-06 — merged via chrome/w7-unsplit.

> Branch `chrome/w7-unsplit`. Prerequisite: **W6 merged** (plus the lead
> fixes: split-time adoption, pane-aware `copy_on_select`).
> Must read: `specs/2026-10-06-frame-chrome/00-overview.md` and
> `core/frame.py`'s `Pane`/`Split`/`Frame` as landed (W5's in-place retile).

## Goal

The tiling stops being append-only: closing a leaf pane removes it and its
sibling(s) re-expand -- the demo's `/preview` close becomes a true return
to one pane instead of a dismissed-content lookalike. This is the last
kernel gap W6 reported (its deviation #1); the demo and docs currently
paper over it.

## Design notes (binding shape, named decisions are yours to detail)

- **`Pane.close()`** on a LEAF pane (a pane with no children): the leaf
  leaves its parent's tiling; with siblings remaining, the parent
  re-divides its rectangle over the survivors (ratios trimmed to the
  surviving count, in order); when exactly one survivor remains, the
  parent COLLAPSES to it -- the parent keeps its own id and rectangle and
  takes the survivor's `viewport`/`chrome`/`document` (child 0 shares the
  parent's id already; when the survivor is a later child its own id dies
  with the split -- document this id rule in the docstring). A root pane
  (no parent) does not close (``RuntimeError`` -- a frame without panes
  has no composition; the driver may later allow an empty frame, not this
  wave). Closing twice / closing a container raises.
- **Separator chrome hygiene**: a surviving pane's divider chrome that now
  faces the screen edge (its neighbour closed) must go -- strip, from the
  surviving neighbours, the chrome registered on the edge the closed pane
  sat beyond (the split orientation's edge for the pane BEFORE the gap).
  Identify chrome by registration knowledge you control: the kernel's
  `_plain_divider` and the driver's `_Separator` are the two known
  dividers; if identity-based removal needs a mark, add one honestly
  (e.g. the `Chrome` dataclass grows an optional `name` used for
  teardown, defaulting unnamed) rather than guessing by size/edge.
- **Focus**: if the closed pane was focused, focus falls to the pane that
  now occupies its rectangle (the collapsed parent, or the surviving
  sibling nearest it). `_adopt()` runs after any children change.
- **In-place discipline**: reuse `_place`-style rectangle rewriting; the
  frame object is never replaced; retile on the next composition picks
  the new tiling up (the driver's `_tiling` cache key must not mask it --
  check `_retile`'s early-return still fires a re-place when the tree
  changed; if the cache key needs the tree, change the key, not the
  semantics).
- **Demo**: `examples/pi_demo.py` `_close_preview` calls the real
  `pane.close()`; the tab binding may now use `pane.focus()` (the adopt
  bug is fixed on main -- verify). The NEW demo baseline
  (`specs/2026-10-06-frame-chrome/ref/pi-demo-baseline.txt`) must stay
  byte-identical if the closed state renders the same (it did before);
  re-capture ONLY if the visible final frame legitimately changes, and
  then note it.
- **Docs**: DESIGN's out-of-scope "append-only tiling" bullet goes; the
  `Pane` sketch gains `close()`; COMPONENTS' split section documents the
  id rule and the separator hygiene.

## Work order (each task = one commit, gate green)

### T1 · Kernel `Pane.close()` (+ the `Chrome.name` mark if you need it)
- Close/trim/collapse, separator hygiene, focus fall-back, adoption;
  kernel tests: close one of two (collapse + id rule + divider strip),
  close one of three (re-divide), close the focused pane, errors (root,
  container, double close), rect math after close at odd sizes.

### T2 · Demo + docs on the real close
- `_close_preview` via `close()`; tab via `pane.focus()`; docs updated;
  baseline preserved (or re-captured with a note).

## Acceptance (paste true output)

1. `uv run pytest -q` — green (counts).
2. `uv run python examples/pi_demo.py | diff - specs/2026-10-06-frame-chrome/ref/pi-demo-baseline.txt`
   — no diff (or the re-capture note).
3. Inline script: headless TUI, split, fill both sides, close the second,
   paint — print the composed rows (one full-width pane again) and the
   frame's pane list — verbatim.
4. Root stays 68 (no new public names beyond the method).

## Forbidden

- `core/selection.py`, `keys/**`, `widgets/**`, `chat/**` (read-only),
  `pyproject.toml` (0.4.0 stands), `specs/**` except a baseline
  re-capture if truly needed.

## Report

Per the overview format; include the id rule and the divider-hygiene
mechanism as implemented.
