# Spec W1 · Kernel primitives — `Line.fill`, `ScreenLayout` geometry, `Pane.inner_rect`
> Branch `refactor/118-kernel`; after: main; read first: `00-overview.md`, `ref/industry.md`

## Goal

Land the row-sizing and layout-geometry primitives with **zero rendering change**:
`Line.fill(width, style)` joins the sizing family, `Line.pad_to` is absorbed into it,
`ScreenLayout` learns its own `width`/`height`, and `Pane.inner_rect` becomes public.
No theme change in this wave — `kernel/theme.py` and `kernel/style.py` are red-lined.

## Tickets (one commit each, in order)

### T1 — `Line.fill` added, `pad_to` absorbed

`src/motui/kernel/lines.py`:

- Add `fill(self, width: int, style: Style = NONE) -> "Line"`:
  - `width <= 0` → `Line()`.
  - `style == NONE` (the fast path; `NONE` is `Style()`, so `==` catches both the
    constant and any equal style): no gap → `self`; a gap → one plain space segment,
    byte-identical to what `pad_to` answered.
  - Otherwise: every content segment comes back through `Segment.with_style` as
    `style.merge(seg.style)` — the style is the base, the segment's own colors win
    (the Rich `Padding(style=…)` rule, `ref/industry.md` §2) — and a gap becomes one
    `Segment(" " * gap, style)`. `fill` never truncates; `fit` is the trim. The
    canonical band pipeline is `row.fit(w).fill(w, band)`.
- Delete `pad_to`. Update every docstring that names it (`filled`'s pointer to it, the
  module docstring's sizing paragraph, and `kernel/frame.py`'s `splice_row` docstring —
  see T2).
- Docstring for `fill`: state the merge direction, the no-truncation rule, the `NONE`
  fast path, and the absorption of `pad_to`.

Tests — the `Line` tests live in `tests/test_core_text.py` (confirm by grep, do not
assume): before deleting `pad_to`, capture its current answers as the expectations
`fill`'s `NONE` path must reproduce; then cover the merge-under rule, the gap segment,
no-truncation, `width <= 0`, and the empty-line case.

### T2 — the `pad_to` call sites become `fill`

Mechanical, `NONE` style, byte-identical:

- `kernel/frame.py` — `splice_row`'s five sites (`base.pad_to(x)`, both
  `slice_line(...).pad_to(...)`, `line.pad_to(width)`, `cut_line(...).pad_to(width)`),
  plus its docstring's `pad_to` references.
- `interaction/find.py` line 399 — `query_rows[-1].pad_to(room)`.
- `widgets/decor.py` line 232 — `row.fit(inner).pad_to(inner)` → `.fill(inner)`.
- `widgets/layout.py` line 111 — the same shape.

Do **not** touch `interaction/overlays.py` (`_band_row` keeps `overlay` + `filled` —
the colored-vs-attribute rule is a different rule on purpose, D7) or
`interaction/find.py` line 403 (same reason). Grep the whole tree for `pad_to` in
tests too (`tests/test_core_text.py`, `tests/test_frame.py` hold references today) and
update them to `fill` with the same expectations.

### T3 — `Panel._bare_row` recomposed through `fill`

`src/motui/widgets/decor.py`: replace `_bare_row`'s body with the composition

    (Line((Segment(" " * lead, pad),)) + row).fit(width).fill(width, pad)

where `pad = NONE` when the panel carries no ground; the `lead == 0` degradation stays
`row.fit(width)`. Keep the method's contract (its docstring) and delete the now-dead
private branches. Prove byte-identity in both modes (framed × borderless) with and
without a ground — the existing Panel tests are the evidence; add the
borderless-with-ground case if it is not covered.

### T4 — `ScreenLayout` learns its geometry

`src/motui/kernel/viewport.py`: add `width: int = 0` and `height: int = 0` to
`ScreenLayout`, populated by `Viewport.layout` from its own arguments. The defaults
keep a hand-built layout "nothing known" — the `row_blocks` precedent. Document the
fields in the class docstring (a layout describes one screen's rows *and* the
rectangle they were laid out in). Tests in `tests/test_viewport.py`.

### T5 — `Pane.inner_rect` public

`src/motui/kernel/frame.py`: a read-only `inner_rect` property on `Pane` over the
memoized `_negotiated()[0]` — one line plus a docstring ("the rectangle the pane's
viewport lays out in, chrome subtracted; `band()` is its complement"). Test in
`tests/test_frame.py` (inner rect shrinks by each registered chrome's budget;
`inner_rect` and `band()` partition the pane's rectangle).

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the passed/failed counts.
2. `uv run python tools/golden.py --check` — **zero diff**: this wave moves no pixel.
3. The framebench line and both piped demo runs from the overview's gate block.

## Red lines (zero diff outside)

`kernel/theme.py`, `kernel/style.py`, every `widgets/` file other than the two
`pad_to` lines in T2 and the `_bare_row` rewrite in T3, `interaction/overlays.py`,
`interaction/find.py` beyond line 399, `tests/golden/`, `docs/`, `specs/`.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs /
deviations and trade-offs / open questions. Blocked → stop and report the blocker; do
not self-rescue outside the write scope.
