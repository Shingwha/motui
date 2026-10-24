# W1 · The band knows its region (single wave)

Four tasks, one gate. T1–T3 land as one commit (`frame: a chrome band names
the region it decorates`); T4 is the release bundle.

## T1 · Kernel + the one consumer

### `src/motui/core/frame.py`

1. `_SCOPES = ("pane", "body")` beside `_EDGES`.
2. `Chrome` gains `scope: str = "pane"` after `name` (positional callers keep
   working), and `__post_init__` validates it:
   - unknown scope → `ValueError`;
   - `scope="body"` with a `top`/`bottom` edge → `ValueError`: a top/bottom
     band owns rows and cannot share the window's.
3. New pure helper beside `_band_of`:

   ```python
   def _body_band(band: Rect, layout: ScreenLayout) -> Rect | None:
       """``band`` clipped to the layout's scrolling window (a body band's extent)."""
       start = min(max(0, layout.viewport_start), band.height)
       height = max(0, min(len(layout.body_rows), band.height - start))
       if height == 0:
           return None
       return Rect(band.x, band.y + start, band.width, height)
   ```

4. `_plan_chrome`: after `_band_of`, clip a body band and skip a clipped-away
   one; `length` is then the band's own extent, so `paint` receives the
   window's height and never has to pad.
5. `Pane.band`: `scope="pane"` answers the geometric band as today;
   `scope="body"` answers `_body_band` against the frame's last pane layout,
   and `None` when there is none yet (documented: a window that has never
   been laid out has no strip). The negotiation memo is untouched.

### `src/motui/app/scrollbar.py`

- `Chrome("right", size, self._paint, scope="body")` -- the whole consumer
  change. No arithmetic, cache, gesture or lifecycle code moves.
- Docstrings: the module header and `_paint`/`_strip`/`_geometry` say the
  strip is the pane's **window**, so the thumb length, travel, drag mapping
  and press region are the state being mapped.

## T2 · Tests

`tests/app/test_scrollbar.py` (replace one, add four; the rest must not change):

1. Replace `test_the_strip_runs_the_whole_pane_height_including_a_pinned_footer`
   with `test_the_strip_is_the_scrolling_window_between_pinned_regions`:
   a one-row top pin, a two-row bottom pin, 10-row pane → the strip column
   carries track/thumb on the 7 window rows only, and the pinned rows' column
   is a space.
2. `test_a_press_over_a_pinned_region_is_not_the_bars` -- press on the
   footer's column answers `False`, press in the window answers `True`.
3. `test_a_drag_maps_the_window_not_the_pane` -- pick numbers whose expected
   offset differs between the two extents (window height 7 with a 2-row
   footer, 100-row document), so the old extent fails the test.
4. `test_a_pane_filled_by_fixed_regions_paints_no_strip` -- no window: the
   column stays blank and every press passes through.
5. `test_a_divider_and_a_bar_stack_on_a_shared_edge` -- a `scope="pane"` right
   band (the split separator) spans every row while the bar beside it covers
   the window only: the exact geometry a split pane with a pinned composer has.

`tests/core/test_frame.py`:

6. `test_chrome_rejects_an_unknown_scope` and
   `test_a_body_scope_refuses_a_top_or_bottom_edge`.
7. `test_a_body_band_is_the_window_and_none_before_the_first_composition` --
   `Pane.band()` for both scopes, before and after `Frame.compose`.
8. Extend `test_chrome_painters_read_the_pane_layout_and_the_strip_length`
   with the body case: `length == len(layout.body_rows)`.

The 912 tests that do not touch pinned regions are the regression proof that
no-pin behavior is byte-identical.

## T3 · Documentation

- `core/frame.py`: `Chrome` docstring gains the scope paragraph (divider =
  pane, bar = body) and the budget sentence (a body band still costs its
  column from the pane's width, so a fixed region shows that column empty);
  `_plan_chrome`'s "shares its rows with the viewport" becomes exact for both
  scopes; `Pane.band` documents the layout dependence and the `None` cases.
- `app/scrollbar.py`: module docstring -- the bar is the rail of the pane's
  window, not of its edge.
- `docs/CONTRACT.md`: §2 (`band()` scope semantics), §6 (the Scrollbar
  sentence).
- `docs/DESIGN.md`: the three-claim table's Chrome row, the scroll-state
  section, and the "Extend here" note (a new decorated region belongs in
  `Chrome.scope` + `_plan_chrome`) plus the recorded known limitation
  (region-scoped budgets).
- `docs/COMPONENTS.md`: the Scrollbar section.

## T4 · Release (separate commit)

`pyproject.toml` 1.2.2 → 1.2.3; `CHANGELOG.md` dated section (`Fixed`: the
bar's extent and the press over a fixed region; `Added`: `Chrome.scope`);
`docs/releases/1.2.3.md`. No tag, no publish -- those wait for the user.

## Gates (every commit)

```bash
uv sync --locked
uv run pytest -q -p no:cacheprovider
uv run python tools/golden.py --check
uv run python tools/framebench.py
uv run python -m motui < /dev/null
uv run python -m motui --pages
```

Plus the cross-repo proof: the consumer's TUI suite (96 tests) runs green
against this worktree's `src/` with **zero** consumer changes.

## Acceptance (paste true output)

1. `pytest` count with the five new tests and the one replaced test.
2. `golden --check`: 57 topics, none re-recorded.
3. `framebench`: `render-hash` unchanged (the demo has no pinned regions and
   no panes with pinned blocks, so nothing moves).
4. The two piped demo entries: no diff.
5. The consumer run: its whole TUI suite green with `PYTHONPATH` pointed at
   this worktree.

## Forbidden

- `core/viewport.py`, `core/block.py`, `core/lines.py`, the `app/` driver and
  overlays, `widgets/`, `demo/`, `golden/` -- this wave touches two modules
  and their tests.
- Any consumer (`mocode`) source edit: its side of this wave is a dependency
  bump and one regression test, nothing else.
