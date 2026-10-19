# Spec W3a · The row-band contract
> Branch `refactor/118-bands`; after: W2 merged; read first: `00-overview.md`, `ref/industry.md`

## Goal

Every vertical row-carrying widget resolves its bands from the new vocabulary through
**one rule**, replacing today's per-widget token picks (`List` reads `selection`,
`Select` its cursor row is bare `accent`, `Tree`/`Table` read `selection`, …). The
registered default-visual change is D3: `Select`'s cursor row and `NavList`'s active
row gain the `ground_active` band under their existing accent label.

## The contract (pin it — this is the wave's centerpiece)

Each widget in the family resolves, once at construction (the charter: explicit
`style=` > theme field > `DEFAULT_THEME`):

    _ground = _pick(ground_style, "ground")           # ground_style= is the one new param
    _active = _pick(<the widget's existing cursor/selected param>, "ground_active")
    _hover  = _pick(<the widget's existing hover param where it has one>, "ground_active")

Bands per row:

- resting row → `_ground`
- engaged row (the keyboard cursor row **or** the pointer-hovered row) → `_active` /
  `_hover`
- engaged row while unfocused → that band `.merge(theme.dim)` — the existing
  dim-when-unfocused rule, unchanged

Rendering: a row is its **text-styled segments** (label styles, markers, guides — what
the widget already styles), then `.fit(width).fill(width, band)` — the W1 primitive,
the band underneath, the text styles on top. **Every row the widget emits rests on
`_ground`** — item rows, counter rows (`(i/n)`, `↑ N more`), group headers — so a
grounded widget has no holes; only the engaged row swaps the band. At the default
theme (`ground = NONE`, `ground_active = reverse`) List, Tree, Table, Radio and
CheckGroup must render **byte-identically** to before this wave.

## Tickets (one commit each)

### T1 — `List` (`widgets/list.py`)

- `_selected_style` picks `"ground_active"`; add the `_ground` pick and a
  `ground_style=` constructor parameter (the family's one new param).
- The hover pick moves to `"ground_active"` (a hovered row is the engaged row; no new
  `hover_style=` param — List has none today).
- `_row` builds its segments in their text styles (the marker seat, the mark prefix
  and the label no longer carry the band themselves) and the band is applied by the
  row pipeline; the unfocused rule merges `dim` onto the band, as today.
- `render` fits and fills every row — item rows and counter rows alike — over the
  resolved band.
- `revision()` gains the ground style beside the three it already carries.
- The class docstring states the contract in one paragraph.

### T2 — `Tree` and `Table` (`widgets/tree.py`, `widgets/table.py`)

- `Tree`: the `cursor_style` pick moves `"selection"` → `"ground_active"`; add
  `ground_style=`; the cursor row and every resting row (guides included) go through
  the fit/fill pipeline; the hover pick moves to `"ground_active"`.
- `Table`: the `selected_style` pick moves `"selection"` → `"ground_active"`; add
  `ground_style=`; the selected row's cells carry the band, the resting rows the
  ground; the hover pick moves to `"ground_active"`. The header row and the grid
  borders keep their own styles (`table_border`, `first_column`) — they are chrome,
  not row bands — but the header row still rests on the ground like any other row.
- Read each widget's own render first and follow its row structure; if a widget's row
  geometry cannot carry a whole-row band without a redesign beyond this ticket,
  **stop and report** — do not force it.

### T3 — `Select` / `Autocomplete` / `Radio` / `CheckGroup` (`widgets/choice.py`)

- `Select`: `selected_style` stays what it is — the cursor row's **label** style, still
  defaulting to the theme's `accent` — and the cursor row gains the `ground_active`
  band underneath (D3). Resting rows and the `(i/n)` counter row rest on the ground.
  Add `ground_style=`; the hover pick moves to `"ground_active"`. `Autocomplete`
  inherits — verify it overrides no row rendering; if it does, apply the same pattern.
- `Radio` / `CheckGroup`: the `focus_style` parameter is **renamed `selected_style`**
  (the row it styles is the group's selection, not the focus ring) and its default
  field moves to `"ground_active"`; add `ground_style=`. At the defaults the render is
  unchanged (both tokens are `reverse`).
- Update the module docstring's description of the family's row rendering.

### T4 — `NavList` (`widgets/navlist.py`)

- The active row keeps its accent label (`active_style`) and gains the `ground_active`
  band (D3); resting rows rest on the ground; the hover pick moves to
  `"ground_active"`; add `ground_style=`.

### T5 — tests and the golden re-record

- Update the affected widget tests (`tests/test_widgets_list.py`,
  `test_widgets_choice.py`, `test_widgets_table.py`, `test_widgets_navlist.py`,
  `test_widgets_forms.py`, and any other the grep finds). The byte-identity
  expectations for List/Tree/Table/Radio/CheckGroup must still pass unchanged; the
  Select and NavList expectations move — annotate each moved expectation with the D3
  registration.
- Re-record the golden frames (`uv run python tools/golden.py --update`) and report
  `git diff --stat tests/golden/pages/` plus a per-page note of what moved: **only
  Select cursor rows and NavList active rows may move** (the demo's menu and rail
  pages). Any other pixel moving is a finding to report, not to accept.

## Acceptance (real output in the report)

1. `uv run pytest -q` — full suite green; state the counts.
2. `uv run python tools/golden.py --check` — green, with the diff summary attached.
3. The framebench line and both piped demo runs from the overview's gate block.
4. `grep -rn '"selection"' src/motui/widgets/` answers only `textfield.py` (the
   buffer's text selection — its correct home).

## Red lines (zero diff outside)

`kernel/`, `interaction/`, `widgets/decor.py`, `widgets/layout.py`,
`widgets/delegate.py`, `widgets/markdown/`, `widgets/rows.py`, `widgets/tabs.py`,
`widgets/indicators.py`, `widgets/action.py`, `widgets/collapsible.py`,
`widgets/textfield.py`, `widgets/dialog.py`, `widgets/combobox.py`, `widgets/diff.py`,
`widgets/syntax.py`, `demo/` except through the golden re-record, `docs/`, `specs/`.

## Report format

Per-ticket status table / commit hashes + messages / the gate's real outputs / the
golden diff summary (per page, what moved) / deviations / open questions. Blocked →
stop and report.
