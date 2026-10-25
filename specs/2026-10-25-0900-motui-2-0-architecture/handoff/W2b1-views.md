# W2b1 handoff · data views on the Surface contract

> Branch `2.0/w2b1-views`; base `01a5148` (main after W2a). All of T1–T6 done.
> Result: **1057 passed**; 57 golden byte-identical; render-hash unchanged; demo 70/4059 lines.

## A. Delivery surface and gates

### Signatures (all `render(self, c: Constraints | int) -> Surface`)
- `widgets/list.py:List` — window/counters unchanged; `max_height` truncates leading rows.
- `widgets/choice.py:Select` (and `MultiSelect`, `RadioGroup`, `CheckboxGroup`) — title/rows/counter unchanged; `max_height` truncates leading rows. `ContextMenu` inherits it.
- `widgets/tree.py:Tree` — visible walk, indent, fold glyphs unchanged; `max_height` truncates visible rows.
- `widgets/navlist.py:NavList` — item/group row plan and gutter unchanged; `max_height` truncates leading rows.
- `widgets/table.py:Table` — memo/natural-width cache/layout untouched; `max_height` slices the returned rows only.
- `widgets/strip.py:LabelStrip` — serves both `Tabs` and `MenuBar`; one row, `max_height == 0` paints none; `_last_width`/`_spans` still recorded.
- `widgets/rows.py:StatusLine`, `ShortcutBar`, `Notice` — one row each; `max_height == 0` paints none.
- `widgets/scroll.py:ScrollView` — window/bar/thumb geometry unchanged; explicit `height` wins over `max_height`, a natural view is capped by it.
- Every return is `Surface.clipped(rows, c.width)` (no padding), so painter bytes are the 1.x bytes.
- All children are still called with `int` (`ScrollView.child.render(inner)`); nothing depends on a child's return type beyond `list(...)`.

### Gates measured in this worktree (2026-10-25)
- `uv run pytest -q -p no:cacheprovider`: **1057 passed** (1045 baseline + 12 new).
- `uv run python tools/golden.py --check`: `57 topics match`.
- `uv run python tools/framebench.py`: `render-hash a82f7968…` (identical).
- `python -m motui < /dev/null`: exit 0 / 70 lines; `--pages`: exit 0 / 4059 lines.
- `grep -rn "def render(self, width"` over the ten assigned files: empty (exit 1).
- `ruff check .` All checks passed; `pyright` 0 errors; `lint-imports` 4 kept / 0 broken.
- `tools/api.py --check`: `179 names match`; `tools/growth.py --quick`: pass/pass/OK.
- W2a adapter: `_render_takes_constraints` true for 15 concrete views; `Section.rows(Constraints(width=10))`
  equals the direct render text for each. The Section bridge (not direct callers) consumes the 15 returns.

## B. Deviations, traps and unmigrated items

1. **`_SelectSurface` bridge (must be removed in W2c).** `app/command_palette.py` does
   `input.render(width) + autocomplete.render(width)` and `tests/widgets/test_autocomplete.py`
   compares an empty render to `[]`; both files are outside this wave's write range. `Select.render`
   therefore returns a private `Surface` subclass that supports `+`/`__radd__` and list equality.
   Plain `Surface` remains the contract; the bridge is additive and only the Select family returns it.
2. **T4 absorbed the strip base.** `Tabs`/`MenuBar` define `_layout`, not `render`; migrating them
   required `strip.py:LabelStrip.render`, so it landed in the T4 commit. T5 therefore contains `rows.py`
   only, and the strip base was not migrated twice.
3. **Table budget is not a memo key.** The full grid at a width is remembered; `max_height` slices the
   returned list. `_last_layout` stays the full grid (same rationale as Panel/Padding in W2a), so a host
   pinning rows beyond the visible budget still maps hits. Alternating budgets do not thrash the build.
4. **ScrollView priority.** The explicit `height` is the host's slot and ignores `max_height`; only a
   `height=None` view is capped. `_last_height`, `state.viewport_height`, thumb and `child_at` all use the
   effective painted height, so geometry stays consistent with the painted rows.
5. **Empty results are `Surface(width, ())`.** Four own tests changed `render(...) == []` to
   `list(render(...)) == []` (List, Tree, NavList, Select/RadioGroup); the Surface sequence protocol
   keeps every other 1.x test reading rows unchanged.
6. **No visual/behaviour change.** Every family already `fit` its rows to the width, so `clipped` is a
   no-op on them; cursor/window/scroll/selection/hit geometry tables were left untouched.
7. **`Table.header_line` recipe** in the docstring now shows a 2.0 `render(self, c)` stub returning
   `Surface.clipped(...)`; it is documentation, not code.
8. **Known merge watch:** W2b2 may add a plain-Surface `Autocomplete.render`. If it does, the palette's
   `Input + Autocomplete` still works only if the left side has a reflected concat path; W2c should
   replace the expression with `Surface` composition and delete `_SelectSurface`.
9. **Not migrated here:** `app/*` (command palette, find, modal), `demo/shell.py` (indexes `[0]` only,
   still safe), and the W2b2 content/edit family. `Autocomplete` inherits the new signature but is not
   edited by this branch.

## C. Locations and commits

- Code: `widgets/list.py:514`, `choice.py:99/663` (`_SelectSurface`, `Select.render`),
  `tree.py:411`, `navlist.py:308`, `table.py:812`, `strip.py:216`, `rows.py:123/182/250`, `scroll.py:335`.
- Tests: `tests/widgets/test_choice.py`, `test_data.py`, `test_navigation.py`, `test_menubar.py`,
  `test_rows.py`, `test_scroll.py` (12 added cases).
- commits:
  - `7371e4f` widgets: render lists and choices into surfaces under constraints
  - `1e61a5c` widgets: render trees and navigation rails into surfaces under constraints
  - `c320041` widgets: render tables into surfaces under constraints
  - `75b1209` widgets: render tab strips and menu bars into surfaces under constraints
  - `73e3bad` widgets: render status, shortcut and notice rows into surfaces
  - `fb82432` widgets: render scroll views into surfaces under constraints
  - this file (last commit)
