# Components

A component is anything with `render(width) -> list[Line]`. That single
protocol is the whole contract.

## The protocol

- **`render(width)` returns rows.** One `Line` per visual row, each already
  wrapped and sized. A component never paints, scrolls, or touches a screen.
- **`width` is the full painting width** — on a real screen that is
  `screen.width`; a `Row`/`Column` child gets the width its parent gives it.
  The painter only counts rows; components own their own wrapping and
  truncation.
- **`Line`** is an immutable run of styled **`Segment`**s (`text` + `Style`
  + the two inline payloads below), with `width` (display columns via
  wcwidth), `fit(width)` (truncate-with-ellipsis) and `pad_to(width)`.
  `Line`, `Segment` and `Style` live in the kernel
  (`mocode_tui.core.lines` / `mocode_tui.core.style`) and are exported at
  the package root.
- **A segment can carry an inline payload: `link` and `action`.** `link` is
  an url the **terminal** is told about — `Line.styled()` wraps that
  segment's text in the OSC 8 pair, so a terminal opens a real hyperlink
  (its own cmd+click included) and a terminal that does not know OSC 8
  ignores both halves — while `action` is the name the **application**
  gives to a click on that run. `link` is part of the segment's value (a
  changed link must repaint the row); `action` is metadata that never
  reaches a byte, so it is excluded from equality. The pure
  `mocode_tui.core.action_at(line, col) -> (action, start, end) | None`
  resolves which run a column landed on (display columns, the interval
  left-closed and right-open); a component's hit testing reads its **last
  render's row table** through it, never the host's coordinates —
  `Text`/`Markdown` do exactly that (their entries below, and the
  build-your-own recipe farther down).
- **Sealing is a cache hint, not a render mode.** `BlockState` is
  `OPEN`/`SEALED` only — a sealed block renders once per width and is cached;
  an open block re-renders every frame. There is no "inline" or "committed"
  render mode; the same `render(width)` runs in both states.
- **Editing keys arrive as events, not coordinates.**
  `Input` / `Editor` / `Palette` consume an event
  through `handle(event)` and answer `True` when they consumed it. The
  wrap geometry that `move_up`/`move_down` follow comes from the component's
  last render (80 columns before the first render), not from the event — a
  host that renders a field at 40 columns and then feeds it a `down` moves
  inside the geometry the user actually saw, and a component never asks the
  host to pass a width back in. A key's `name` is the decoder's spelling:
  the arrows `up`/`down`/`left`/`right`, `home`/`end`,
  `page_up`/`page_down`, `enter`, `escape`, `tab`, `backspace`, `space`, the
  controls `c-a`…`c-z`, and the shift chords
  `s-up`/`s-down`/`s-left`/`s-right`/`s-home`/`s-end` (the `ESC [ 1;2 X`
  letters) — a hyphen for chords, an underscore for words.
- **Interaction is a set of small protocols, not a manager.** A component
  declares what it can do and the host (or an assembly tier) writes it:
  `Clickable` (`click(row, col) -> bool`), `Activable` (`activate() -> bool`),
  `Focusable` (`focused: bool`), `Hoverable` (`hover: bool`, plus the
  optional row-level `hover_at(row, col) -> bool`) and `Container`
  (`child_at(row, col) -> (component, row, col) | None` — a component *of*
  children, translating a cell into a child's own coordinates). A component
  never learns a manager exists, and a container only routes coordinates: it
  proxies no `handle` / `move` / `activate` / `focused`.

Every component below is importable straight from `mocode_tui`, and from
`mocode_tui.widgets`, the generic component library's own facade.

### Interaction: handle, click, move, select, activate

Interactive components add controller methods beside the render protocol;
the host routes input, and the component owns its own arithmetic.

| Method | Components | Contract |
|---|---|---|
| `handle(event) -> bool` | `Input` / `Editor` / `Palette` | `True` = consumed; `False` hands the event back to the host, which is where the submit gesture lives |
| `click(row, col) -> bool` | `Input` / `Editor` / `Select` / `Confirm` / `Tabs` / `Tree` / `Table` / `Autocomplete` / `Text` / `Markdown` | `row`/`col` are 0-based in the component's own render; title offsets, window scroll, the strip's segment widths and the row's meaning are the component's arithmetic, never the host's (`col` carries no default and a row-shaped component that ignores it says so in its docstring). A text field places the caret: the shell restores its rendered window and `TextBuffer.place` maps the cell back to the logical position (wide clusters fold onto their character, a click past a row's text onto its end, the prompt's indent onto the row's start); a table reads the row it landed on off its own row layout, so a rule or the header takes no click; `Text`/`Markdown` resolve the cell against their **last render's row table** through `action_at` and consume only a cell inside a segment that carries an `action` (`Markdown`'s links land their url in `chosen`) — a plain run declines and the host's own policies still get their turn |
| `hover: bool` | `Button` / `Checkbox` / `Link` / `Select` / `Confirm` / `Autocomplete` / `Input` / `Editor` / `Table` / `Tabs` / `Tree` / `Text` / `Markdown` | the pointer tier's flag, the peer of `focused`: `Pointer` sets it while the pointer is over the leaf and the component renders by it (the theme's `hover` band over its whole block — for per-row marks use `hover_at`). Hover needs `TUI(hover=True)` (DECSET 1003): under the default 1002 a button-free motion is never reported. On `Text`/`Markdown` the flag paints nothing by itself: their highlight is the inline span, so the flag is only the protocol's own (`Pointer` sets it and calls `hover_at` on the same move) |
| `hover_at(row, col) -> bool` | `Select` / `Confirm` / `Autocomplete` / `Tabs` / `Tree` / `Table` / `Text` / `Markdown` | the optional row-level half of hover: mark the row under the pointer in the component's own coordinates and answer whether the render changed; `row < 0` means the pointer left and clears the mark byte-for-byte back to the un-hovered output. `Pointer` calls it, the component keeps the state. The inline pair marks the **span** under the pointer instead of a whole row: the hit is a segment with an `action`, the highlight is the theme's `hover` merged over that segment on the render's copy, and a move within one span answers `False` |
| `child_at(row, col) -> (Component, row, col) \| None` | `Row` / `Column` / `Padding` / `Panel` | the container's coordinate door, read off the container's **last render** (the `TextBuffer.move_up` precedent): the child that owns the cell, re-expressed in the child's own coordinates, or `None` for the container's own cells (borders, pads, gaps, the blank filler below a shorter child). `Pointer` and `FocusRing.click` run `descend` first, so a click through a wrapper lands on the leaf; containers never proxy the leaf's verbs |
| `move(delta) -> bool` | `Select` / `Confirm` / `Autocomplete` / `Tabs` / `Tree` / `Table` | the menus (`Select` / `Confirm` / `Autocomplete`) **wrap** their ends and take `wrap=False` to clamp; `Tabs` / `Tree` clamp, and so does `Table` — a data view stops at its edge, a menu is a cycle (D10); `True` when the cursor moved; a step clears a pending `chosen` |
| `select(index) -> bool` | `Tabs` | clamped into range; `True` when the selection changed (setting a value is not activation) |
| `activate() -> bool` | `Select` / `Confirm` / `Autocomplete` / `Tree` / `Table` | the one activation verb: a menu takes the option under its cursor into `chosen` (`False` for an empty list; the host reads `chosen` once, and `move` / a re-filter clear it), the tree expands/collapses the node under its cursor (`False` on a leaf), the table takes the data row's index into `chosen` (`False` for an empty table) |

A click reaches a component through the driver: `hit_test` resolves the cell
to a `Hit`, and the host calls `hit.block.component.click(hit.row, hit.col)` —
the block-internal cell, already the coordinates the table above expects. A
click through a wrapper takes one more step: `hit_component(x, y)` (or a
`descend` call) walks every container's `child_at` first, and the leaf is
what gets the click. Hover takes one more mode: `TUI(hover=True)` opens
DECSET 1003, and the `Pointer` tier writes the flags
(`docs/DESIGN.md` has the rationale). A host that wants the toolkit to route
for it opts into `FocusRing` (one
line; see the Focus section below), which dispatches the keys a focused
target owns, cycles the focus and runs the click policy — the components
themselves stay exactly as this table describes them.

## Styling: Style and Theme

`Style(fg=..., bg=..., ...)` is frozen and hashable (so `prefix()` is
memoized per instance) and takes a color in one of three forms:

- a **named 16-color** from `core.style.FG_CODES` (`"red"`,
  `"bright_black"`, …); unknown names raise `KeyError` from `prefix()`;
- a **`"#rrggbb"` string** or an **`(r, g, b)` tuple** — both emit 24-bit
  truecolor SGR (`38;2;r;g;b` / `48;2;r;g;b`). Truecolor is a superset of
  the named set, so old named styles keep working unchanged.

Attributes are `bold`, `dim`, `italic`, `underline`, `reverse`, `strike`
(SGR `9`, crossed-out); `merge(other)` OR-sets the booleans
and lets `other`'s colors win — the operation a component uses to layer an
emphasis onto a base band. An attribute-only style (no `fg`/`bg`) merges
*under* whatever run it lands in, which is how `**bold**` inside an accent
heading stays accent.

**`Theme`** (a frozen dataclass, `DEFAULT_THEME` as the shipped instance) is
the one place every semantic default lives. A component takes an explicit
`style=...` (which always wins) plus `theme=Theme | None`, and resolves each
style **once, at construction**, as **explicit > theme field >
`DEFAULT_THEME`** — storing the resolved `Style` (or the resolved `Theme`,
when the choice depends on a mutable attribute). A
`render(width)` call looks its styles up rather than resolving them.
`replace(DEFAULT_THEME, accent=...)` still restyles a whole family of
components at once, and nothing global is mutated. Equality is field-wise,
so a custom theme never compares equal to `DEFAULT_THEME` unless every field
matches.

| Theme field | Default | Used for |
|---|---|---|
| `dim` | dim | secondary rows, placeholders, the `Editor`'s dim states |
| `muted` | `#8b949e` gray | secondary text (thinking, quote bars, fence lines) |
| `accent` | `#58a6ff` soft blue | prompts, the working label, syntax keywords, the menu cursor row |
| `success` | `#4bb563` soft green | success, `+` rows, ✓, the `ProgressBar` fill |
| `error` | `#e5534b` soft red | errors, `-` rows, a dangerous `Confirm` |
| `warning` | `#d29922` amber | warnings, notice titles |
| `border` | no color (terminal default fg) | rules, panel borders |
| `code` | `#a5d6ff` ice blue | untagged/unknown fence code, syntax `builtin` |
| `cursor` | reverse video | the block cursor (`Input` / `Editor`) |
| `selection` | `reverse` | `Tabs` / `Tree` cursors and the `Table` row band (its `selected_style` default); pass it as a menu's `selected_style` for a reverse-video band — the menus themselves default to `accent` |
| `heading` | `#e3b341` gold | the Markdown heading ladder's base |
| `link` | `#58a6ff`, underlined | Markdown link labels (never bold) |
| `inline_code` | `#f778ba` pink | inline `` `code` `` runs |
| `list_marker` | `#bc8cff` purple | list bullets / numbers |
| `hover` | reverse video | the pointer tier's hover band (the `Hoverable` components) |
| `table_border` | no color | `Table` grid lines (`Table(border_style=...)` tints them) |
| `first_column` | no color (plain) | `Table` data rows' first column |
| `scrollbar` | dim | the `Scrollbar` track (`░` cells) |
| `scrollbar_thumb` | no color (plain fg) | the `Scrollbar` thumb (`█` cells) |
| `toast` | reverse + dim | the `Toasts` band |
| `headings` | derived from `heading` | the Markdown heading ladder (read-only property) |
| `notice_levels` | derived from `warning`/`error` | the `Notice` level labels |

The semantic colors mirror the exported `core.style` constants (`DIM`,
`MUTED`, `ACCENT`, `SUCCESS`, `ERROR`, `WARNING`, `BORDER`, `CODE`,
`CURSOR`, `SELECTION`, plus the markdown palette `HEADING`, `LINK`,
`INLINE_CODE`, `LIST_MARKER`); the band colors and the table defaults live
only in `Theme`. **Bold is reserved for the `**…**` syntax itself and
strike for `~~…~~`**: none of the markdown-facing defaults (the heading
ladder, the link, inline code, list markers, the table header, the table
first column) is bold or struck — structure reads by color instead of weight
(syntax highlighting's keyword=accent aside).

## widgets — text & structure

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. `theme` is read for one thing: the `hover` band an inline span merges. `Hoverable` + `Clickable` over the row table of its last render: `hover_at(row, col)` marks the span under the pointer (a segment with an `action`) and `click(row, col)` lands that payload in `chosen` (read once by the host; a plain run declines). The default rows are verbatim and carry no payloads — a subclass that returns its own `Line` values from `_rows_for` inherits the hit testing unchanged. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, gap=1, divider_max_width=80)` | Rule-registry engine: paragraphs, `#`–`######` headings, fenced code, lists, block quotes, GFM tables, thematic breaks, inline `` `code` ``/`**bold**`/`~~strike~~`/`*italic*`/`[t](u)`; unknown constructs degrade to paragraph. A link's label segment carries `link=url` (OSC 8 bytes around the label — a real terminal hyperlink) and `action=url`; the component is `Hoverable` + `Clickable`: a click on a label lands the url in `chosen` (read once by the host) and the pointer's span takes the `hover` band. See below. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None, theme=None, max_width=None)` | Full-width rule from one repeated character; a `label` embeds `char*2 + " " + label + " " + char*fill` (e.g. `── ⠋ Working ───`) across the full width, an over-wide label is ellipsize'd to `width - 4`, and `label`/`label_style`/`max_width` are mutable attributes. |
| `Notice` | `Notice(text, *, level="info", theme=None)` | One message row; `warn`/`error` prepend a styled label from the theme's `notice_levels`. Any other level degrades to plain `info`. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None, theme=None)` | Child inside a single-line box; titled top border when it fits. |
| `Row` | `Row(children, *, widths=None, gap=1)` | Side-by-side columns (fixed/flex widths), tallest child sets the height. |
| `Column` | `Column(children, *, gap=0)` | Vertical stack with `gap` blank rows between children. |
| `Spacer` | `Spacer(rows=1)` | Blank rows — the transcript rhythm's building block. |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)` | A child inset on all four sides; with `fill_style` set the blank areas are painted and merge *under* the child's colors (a filled user-band pattern). The fill is never themed. |

## widgets — input & choice

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, prompt_style=None, cursor_style=None, focused=True, theme=None, keymap=None)` | Single-line cursor-editable field (`insert`/`backspace`/`delete`/`move_*`/`home`/`end`/`clear`); up/down follow wrapped rows; an empty focused field shows its placeholder dim and **no cursor cell** (the block appears with the first typed character; an empty field with no placeholder shows the block alone). Keys route through the component's **keymap** at `handle(event)`, answering `True` when consumed — the driver feeds keys, it reads none. A multi-line `Paste` is folded into the single line: every run of newlines becomes one space (`"a\r\nb"` pastes as `"a b"`), so a paste never adds a row; an explicit `insert("\n")` keeps its newline. `.text` and `.cursor -> (row, col)` read the buffer; `cursor_position(width)` reports the block-cursor cell for an IME anchor; `click(row, col)` places the caret at that rendered cell (the prompt's columns and a wrapped row's indent fold onto the row's start, a click past the text onto its end). `focused` is the flag the focus tier writes (`FocusRing`), so a ring of fields toggles their block cursors without the fields changing. |
| `Editor` | `Editor(*, text="", placeholder="", style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `.text` and `.cursor -> (row, col)` read the buffer; `newline`/`insert` (a multi-line `Paste` keeps its newlines verbatim) / merged `backspace`; `max_rows` caps the rendered rows with a sliding window on the cursor; `click(row, col)` places the caret, the window's first rendered row added back onto `row` first so "the third row on screen" always means the third rendered row. The placeholder rule matches `Input`'s. `enter` is unbound in the host-submit keymap (`EDITOR_SUBMIT_KEYMAP`) so it stays the host's submit gesture. `focused` is the flag the focus tier writes, exactly as on `Input`. |
| `Select` | `Select(options=(), *, title="", max_rows=8, wrap=True, marker="→", focused=True, label_style=None, selected_style=None, description_style=None, title_style=None, theme=None)` | The menu: vertical `Option(label, value, description)` rows with the cursor row led by `marker` (default `→`) in `selected_style` (default: the theme's `accent`), every description in one column measured over the whole option list. `move(delta)` wraps the ends (`wrap=False` clamps) and clears a pending `chosen`, `index` clamps on assignment, `selected` reads, `activate()` takes the cursor's option into `chosen` (the host reads it once), `click(row, col)` answers a mouse hit (the column is ignored: a row owns the width); a list longer than `max_rows` renders a window that keeps the cursor visible plus an `(i/n)` counter row; `focused=False` renders the cursor row in `selected_style.merge(theme.dim)` (the description column keeps its own `dim`). `Autocomplete`'s base class. |
| `Confirm` | `Confirm(message, *, danger=False, theme=None)` | Yes/No `Select`; `danger` styles the message in `ERROR`; `move(delta)` / `click(row, col)` / `focused` forward to its `Select` (the column is ignored), `activate()` lands `Option("Yes", True)` / `Option("No", False)` in `chosen`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |

## widgets — the action primitives

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Button` | `Button(label, *, style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | The smallest interactive unit: one row, `" label "`, `fit` to the painting width. The base style is `style` or the theme's `accent`; `hover` merges `hover_style` or the theme's `hover`, `focused` merges `focus_style` or the theme's `cursor`. `click(row, col)` (any cell — the whole row is the control) and `activate()` are the same operation and both always answer `True`, landing `True` in `chosen` for the host to read once and reset. |
| `Checkbox` | `Checkbox(label, *, checked=False, theme=None, focused=False)` | `Button`'s toggling sibling: one row, `[x] label` / `[ ] label`, same bands. `click` / `activate` flip `checked` and mirror the new value into `chosen` (read once, reset by the host); both always answer `True`. |
| `Link` | `Link(text, *, style=None, hover_style=None, theme=None)` | One clickable row rendered in the theme's `link` band; `hover` merges the theme's `hover`. Deliberately **not** `Activable` — a link is not a focus target's main operation (the keyboard door belongs to the widgets a ring registers). A click on any cell lands `True` in `chosen`. |

## widgets — data & progress

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, selected_style=None, aligns=None, focused=True, theme=None)` | Full box grid (`┌─┬─┐` top, a `├─┼─┤` rule between every pair of rows, `└─┴─┘` bottom) with uncolored rules by default; cells are `str`, `(str, Style)`, or styled `Segment` runs (inline markup); per-column `aligns` (`left`/`center`/`right`); natural column widths, proportional shrink + ellipsis when over width, never stretched below natural size. Optional **row cursor**: `index` is a data row (never the header or a rule; `None` by default, clamped on assignment, `None` again for an empty table) and `selected` reads that row's raw cells; the cursor row renders *every* one of its data cells in `selected_style` (default the theme's `selection`) — the header and the grid lines stay untouched, and the row count and column budgets are the same with or without a cursor. `move(delta)` steps it and **clamps** at the ends (a data view, not a menu cycle), `click(row, col)` maps a rendered row onto a data row through the table's own layout (the column is ignored: a data row owns its width), `activate()` takes the row's index into `chosen` (the host reads it once; `move` and a landing click clear it), `focused=False` renders the band in `selected_style.merge(theme.dim)`. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│", focused=True, theme=None)` | One row of tab labels, the active one emphasized and `│`-separated; `select(index)` selects (clamped), `move(delta)` steps, `click(row, col)` maps the cell against the strip's own render, `active` reads; `focused=False` renders the active label in `active_style.merge(theme.dim)`. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, focused=True, theme=None)` with `TreeNode(label, children=(), *, expanded=False)` | Indented tree; `expanded` flips a node's children in place; `move(delta)` / `click(row, col)` steer (the column is ignored: a node row owns the width), `activate()` expands/collapses the node under the cursor (`False` on a leaf), `selected` reads; a cursor style marks the row, and `focused=False` renders that row in `cursor_style.merge(theme.dim)`. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)` | Determinate bar: filled `█` run over shaded `░` run inside `[ ]`, clamped to `[0, 1]`; `fraction` is a mutable attribute that re-clamps on assignment. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, wrap=True, label_style=None, selected_style=None, description_style=None, theme=None)` | The filter layer of the menu family: a `Select` subclass whose **rows are the current matches** — `set_query(text)` keeps prefix matches first, then substring matches (case-sensitive; an empty query matches all), resets the cursor and clears a pending `chosen`. The window, `(i/n)` counter, description column (measured over the whole option universe, so it never jumps while filtering), wrapping cursor and `activate()`/`chosen` are the inherited `Select` behaviour. The engine `Palette` is built on. |

## widgets — the status row and the palette

| Component | `__init__` sketch | Capabilities |
|---|---|---|
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-column row: left part at column 0, right part one column short of the width, computed gutter between (at least one column); `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. Over-wide rows keep the left part and ellipsize the right tail. |
| `Palette` | `Palette(commands, *, theme=None, max_rows=8)` | The **self-contained** command palette: its own query `Input` row (`.input`, `.list` are the composed widgets) over an `Autocomplete` filtered by that row's text. `open()` resets the query and the list; `handle(event) -> bool` consumes up/down/enter/escape — a consumed `enter` lands the highlighted command's `value` in `chosen` (`None` when nothing matches or the palette was dismissed), and the host reads `chosen` once and dispatches it — and routes every other event through the query row. Renders zero rows while closed. |

## The frame tier — Pane, split, chrome, overlays

The frame model's public face, all of it host policy over the driver's
`tui.frame` seam (the tiling, its focus, its overlay registry, each pane's
last layout). `mocode_tui.chrome` is the assembly tier — the peer of
`mocode_tui.gesture` — and the three space claims it implements (pane /
chrome / overlay) are the design constitution in
[`docs/DESIGN.md`](DESIGN.md).

### `Pane` and `split` — the rectangles

```python
tui.split("vertical" | "horizontal", *, ratios=(1, 1), min_size=1, separator=True) -> tuple[Pane, ...]
left, right = tui.split("vertical", ratios=(2, 1))   # transcript | preview
left.document; left.viewport; left.focus()   # the Pane handle
left.split(...)                              # divide it; returns the children
left.close()                                 # the un-split: a leaf leaves
```

`tui.split` divides the **focused** pane and returns the children in paint
order — one code path with `Pane.split`. The first child keeps the split
pane's id, document, viewport and chrome, so a host's blocks and any chrome
registered before the split ride the division; every child after it opens
over a fresh, empty document (`right.document.add(...)` is the preview side
of the split). A split leaves focus where it was, and re-divides the tiling
immediately, so the returned panes already hold their rectangles. The 1-cell
separator is inter-pane chrome (budgeted, never a gap) themed by focus — the
tmux convention: the theme's `accent` beside the focused pane, its `border`
otherwise — and `separator=False` leaves the panes abutting. There is no
`Theme.separator` field: a host wanting a different look splits with
`separator=False` and registers its own chrome on the pane (the recipe
below). A resize re-divides the same tree in place: every pane keeps its
viewport, its chrome and its scroll state.

`close()` is the division's symmetric — the un-split, and the kernel's only
structural removal. A **leaf** pane (one with no children) leaves its
parent's tiling: with siblings remaining the parent re-divides its rectangle
over the survivors, its `ratios` trimmed to the surviving count in order,
and when exactly one survivor remains the parent **collapses** to it, keeping
its own id and rectangle and taking the survivor's window (its `viewport`,
and the chrome and document that come with it). Rectangles are rewritten in
place — the frame object is never replaced — so the next composition paints
the new tiling, and a collapsed frame is the single-pane pass-through again:
the next frame composes the pane's own layout.

**The id rule.** A pane's id is its identity in the frame — what a host
registers chrome on, what `frame.focus` keys — and a collapse keeps the
*parent's*. A split's first child shared it already, so collapsing onto the
first child is invisible to every id a host holds: a scrollbar on
`"primary"` and the `"primary"` focus key both ride on. A survivor that was
a later child takes an id (`"primary-1"`) that dies with the split
(`frame.pane("primary-1")` answers `None` from then on), and a focus keyed
on it falls to the pane that took its rectangle. A re-divide changes no id
at all — survivors keep the ones they were given at split time, so a trimmed
set's numbering may start above zero. Nothing is ever renumbered: an id a
host holds must not move under it.

**The separator** is chrome of the pane before the gap, so it dies with the
adjacency it divides: a close strips, from the pane before the closed gap,
the chrome the split's orientation names on that edge — identified by
`Chrome.name` (`SEPARATOR_CHROME_NAME`: the kernel's neutral divider and the
driver's themed one both register under it, and a scrollbar column shares
the edge and the size, which is why the mark and not the geometry decides)
rather than by guessing. No divider is invented between the survivors:
closing the middle of three leaves the two abutting, and a host wanting one
back registers its own chrome on the pane now before the new gap. **Focus**
falls back when the focused pane closed — to the collapsed parent, or to the
survivor that takes the closed child's place. A root pane (one no split
holds), a container (an already-split pane) and a second close of the same
pane all raise `RuntimeError`.

### `Scrollbar` — the reference chrome

```python
Scrollbar(tui, *, pane=None, size=1, min_thumb=1, style=None, thumb_style=None, theme=None, scroll_tick=0.05)
scrollbar = Scrollbar(tui)            # pane=None: the frame's first pane
scrollbar.handle(event) -> bool       # the consume-one-event contract
scrollbar.detach()                    # unregister + cancel the ticker
```

Constructing the bar registers a right-edge `Chrome` on its pane (an id the
frame does not hold raises `ValueError`); the budget is negotiated at the
next composition and the pane's viewport re-wraps at the reduced width.
`detach()` is the symmetric unregister (`Pane.remove_chrome`), and the
registration rides a retile: a split keeps the pane's id on its first child
and a collapse keeps the parent's, so a bar on the transcript survives the
division and the un-split alike. The strip paints from the
pane's last layout alone — `offset` / `total_rows` are the only view state a
painter reads — and the thumb geometry is pure arithmetic over them (a small
window over a long document is a short thumb; a document that fits paints a
plain track). `handle(event)` is the bar's own gesture: a left press in the
strip is consumed (grab-and-drag on the thumb, anchored so it never jumps; a
held track click pages and repeats), every other event — every key, every
paste, every wheel report, every press outside the strip — passes through.

### `Toasts` — the reference overlay

```python
Toasts(tui, *, ttl=4.0, max_shown=3, corner="top-right", style=None, theme=None)
toasts = Toasts(tui)                  # registers the overlay on the frame
toasts.show("Copied 2 lines")         # a str, or any Component
toasts.handle(event) -> bool          # dismiss the toast under the pointer
toasts.detach()                       # unregister + cancel the ticker
```

`show` takes a plain string (wrapped in a `Text`) or any `Component` — a
toast can be a `Notice`, a `Spinner`, a host's own renderable — plus an
optional per-toast `style` (it wins over the controller's) and `ttl`. A show
past `max_shown` evicts the oldest; the stack grows away from `corner`, one
blank row between neighbours, and never covers more than half the frame. The
paint is the pure half (`frame -> layout`, the frame's rows and the live list
its only inputs) and the controller owns everything time- and input-shaped:
one `tui.every` ticker checks expiry against `tui.clock()`, and `handle`
consumes a press inside a toast's own rectangle to dismiss it. `detach()`
unregisters the overlay (`Frame.remove_overlay`) and cancels the ticker.

### The dispatch order

One rule everywhere, and it is geometric: a host routes every event through
the chrome before any content gesture and before its own dispatch, with the
overlays between the chrome and the gestures.

```python
scrollbar = Scrollbar(tui)            # chrome, first
toasts = Toasts(tui)                  # overlays, next
gesture = SelectionGesture(tui)       # content gestures
ring = FocusRing([menu, tree])        # widget focus, after the gestures
event = await tui.read_key()
if not scrollbar.handle(event):       # 1. chrome
    if not toasts.handle(event):      # 2. overlays
        if not gesture.handle(event): # 3. gestures
            if not ring.handle(event):# 4. the focused widget
                ...                   # 5. the host's own dispatch
```

Three rules make the order exact. **Chrome first, and geometrically:** the
bar's strip is derived from its pane's rectangle, so it routes before any hit
test runs — a press that reached a hit test first would anchor a selection on
the text under the strip. **Overlays after chrome, before gestures, also
geometrically:** an overlay's band is derived from the frame's rectangle the
same way, so a press inside a toast has to be consumed before a hit test
runs, and placing overlays after the chrome keeps the bar's own columns the
bar's. **Gestures before the host's dispatch:** the bar, the overlays and the
gesture speak the same consume-one-event contract, so a controller that
consumed an event leaves no trace in the host's state. **The wheel is
nobody's chrome:** `read_key` intercepts `scroll_keys` before the host loop
runs, so a
wheel report never reaches `Scrollbar.handle` — one that does (a host that
deleted the binding) passes through untouched. A host with a cell-level
affordance of its own — foldable tool calls, whose chevron row
owns its click — resolves those cells between the overlays and the gesture:
the row is the call's, every other cell is the gesture's.

A focus ring joins after the gestures (step 4): the keys a focused widget
owns route before the host's own dispatch, and the host routes the cycle key
(`tab`) to `focus_next` itself — the ring binds nothing. The mouse takes a
different door: the gesture consumes the press, and the stationary click goes
one level further — the shipped answer is a mounted `Pointer`, which resolves
the cell, descends to the leaf and runs the ring's policy; the gesture owns
the press, the pointer owns the hover and the click, the ring owns what the
click *means* (dispatch, focus, activate). A host that dispatches the click
itself still calls `ring.click(tui.hit_test(event.x, event.y))` — the Focus
section below has the full wiring.

### Build your own chrome — a 2-column rail

A chrome is one `Chrome(edge, size, paint)` value whose `paint` is a pure
function of the pane's last layout and the strip's length. The reference
recipe is a line-number rail: two budgeted columns on the left edge, numbered
from the layout's `offset` over its `total_rows` — no viewport attribute is
ever touched.

```python
from mocode_tui import DEFAULT_THEME, Line, Style, Theme

from mocode_tui.core.frame import Chrome


class LineNumberRail:
    """A 2-column gutter: chrome that numbers the rows it sits beside."""

    def __init__(self, *, style: Style | None = None, theme: Theme | None = None):
        self._style = style or (theme or DEFAULT_THEME).dim  # resolved once

    def chrome(self) -> Chrome:
        # "left", 2: the budget asked of the pane; the paint below fills it.
        return Chrome("left", 2, self._paint)

    def _paint(self, layout, length: int) -> list[Line]:
        # layout.offset / layout.total_rows: the pane's scroll state as it
        # was laid out — the only view a painter reads.
        first = layout.offset + 1
        rows = []
        for index in range(length):
            number = first + index
            if number > layout.total_rows:            # past the document
                rows.append(Line.filled(2))           # a blank rail cell
                continue
            rows.append(Line.from_text(f"{number:>2}"[-2:], self._style))
        return rows                                   # each row exactly 2 wide


rail = LineNumberRail().chrome()
tui.frame.pane("primary").add_chrome(rail)   # the budget negotiates at the next composition
```

That is the whole surface: `add_chrome` registers (the pane's viewport
re-wraps at the reduced width), `remove_chrome` unregisters by identity, the
compositor clips a budget that would squeeze the viewport out, and a
`size: 0` chrome is a legal no-op seam. Chromes stack — several on one edge
sit outermost-first, budgets add — so a rail beside a gutter is two chromes.

### Build your own overlay

An overlay is the other half of the registry: any object with
`paint(frame) -> layout`, registered with `tui.frame.add_overlay` and
unregistered by identity with `remove_overlay` (a missing entry raises —
test membership first to keep a `detach()` idempotent). The worked example
ships in the driver: the selection highlight is overlay #1, a `paint` that
marks the focused pane's own layout and splices the marked rows back through
`Frame.with_pane_rows` — the same column splice the compositor runs and a
toast paints with. `Toasts` is the reference *controller* over that protocol
(registration at construction, time on the pump's clock, input on its own
geometry); a minimal overlay of your own is the `Toasts.paint` shape — read
`frame.layout`, rewrite rows, hand the layout back (unchanged, when there is
nothing to paint).

### Build your own container — let a custom wrapper take clicks

A component that wraps children is one `child_at` method away from being
clickable through: the container records its children's rectangles at render
time and translates a cell into the child's own coordinates. That is the
whole protocol — `Pointer` and `FocusRing.click` run `descend` first, so a
cell a wrapper swallowed would otherwise stop at the wrapper.

```python
from mocode_tui import Component, Line


class Stack:
    """A vertical composite whose children stay clickable through it."""

    def __init__(self, children: list[Component]):
        self.children = list(children)
        self._spans: list = []    # empty until the first render: every cell declines

    def render(self, width: int) -> list[Line]:
        self._spans = []          # (child, first_row, height): this render's geometry
        rows: list[Line] = []
        for child in self.children:
            child_rows = child.render(width)
            self._spans.append((child, len(rows), len(child_rows)))
            rows.extend(child_rows)
        return rows

    def child_at(self, row: int, col: int):
        for child, first, height in reversed(self._spans):   # the last painted wins
            if first <= row < first + height:
                return child, row - first, col                # the child's own cell
        return None                                           # our own cell: nobody
```

Three rules, the same the built-in containers follow. **The geometry comes
from the last render** — a stack that has never rendered declines every cell
(the `TextBuffer.move_up` precedent), and no hit test ever invents a layout.
**The coordinates are translated** — the child receives its own
block-internal cell, so its own `click`/`hover_at` arithmetic just runs.
**Nothing else is proxied** — `handle` / `move` / `activate` / `focused`
stay the leaf's, so keyboard focus registers the child itself and
`Padding(Editor)` needs the editor in the ring for keys while its click
still descends.

### Build your own inline action — a row of clickable spans

A component with inline actions is one `action_at` call away from clickable
**and** hoverable: build the row's `Line` with the payloads, hand the row
table of your last render to `action_at`, and consume only what carries an
`action` — a miss declines, so the host's other policies still get their
turn. The `link` half is the terminal's: `Line.styled()` wraps the run in
the OSC 8 pair, so a terminal opens a real hyperlink over exactly that run.

```python
from mocode_tui import Line, Segment, Style
from mocode_tui.core import action_at    # the kernel's inline-action lookup

HOVER = Style(reverse=True)   # or the theme's ``hover`` band


class Chips:
    """One row of labelled chips; each chip is clickable and hoverable."""

    def __init__(self, chips: list[tuple[str, str]]) -> None:
        self.chips = chips                        # (label, action) pairs
        self.hover = False                        # Hoverable's one flag
        self.chosen: str | None = None            # the host reads it once
        self._rows: list[Line] = []               # last render's row table
        self._span: tuple[int, int, int] | None = None

    def _base_rows(self, width: int) -> list[Line]:
        """The row, every chip carrying its action (and a link when it has one)."""
        parts: list[Segment] = []
        for label, action in self.chips:
            if parts:
                parts.append(Segment(" \u00b7 "))
            parts.append(Segment(label, Style(underline=True), action=action))
        return [Line(parts).fit(width)]

    def render(self, width: int) -> list[Line]:
        rows = self._base_rows(width)
        self._rows = rows                         # the hit testing's geometry
        if self._span is not None:                # the hover post-transform
            index, start, end = self._span
            rows[index] = rows[index].merge_span(start, end, HOVER)
        return rows                               # a fresh list, always

    def hover_at(self, row: int, col: int) -> bool:
        hit = action_at(self._rows[row], col) if 0 <= row < len(self._rows) else None
        span = None if hit is None else (row, hit[1], hit[2])
        changed = span != self._span
        self._span = span
        return changed                            # True = repaint

    def click(self, row: int, col: int) -> bool:
        hit = action_at(self._rows[row], col) if 0 <= row < len(self._rows) else None
        if hit is None:
            return False                          # not a chip: consume nothing
        self.chosen = hit[0]
        return True
```

The same four rules the library's own `Text`/`Markdown` follow. **The hit
test reads the last render's row table** — the geometry the user is looking
at, never a re-render. **The payload is the address** — `action_at` answers
`(action, start, end)` in display columns (left-closed, right-open), so a
wide cluster owns both of its cells and a click at either one hits. **The
hover is a copy** — merge the band into the hit row (`Line.merge_span`) in
`render` and leave the row you cached alone, so clearing the hover hands
back the un-hovered bytes exactly. **A miss declines** — return `False` from
`click` and the host is free to route the cell on. And put the url in
`link` too when the chip should be a real terminal hyperlink: the bytes are
free, and one component then serves the mouse and the terminal's own
cmd+click at once.

### Assembling an app — the footer-band recipe

The library ships **no app shell**: no chat layer, no pinned input box, no
demo mode to copy. A host assembles its own from three pieces — the body
document the panes render, a footer `Document` holding the input and status
rows, and `tui.add_band(viewport)`, which parks that footer's viewport in the
frame's bottom band: full width, beneath every pane, outside every split, so
a pane division never cuts it in half. The runnable version of this snippet
is the `## Building your own shell` block in `README.md`, executed headless
by `tests/test_readme_examples.py`:

```python
import asyncio

from mocode_tui import EDITOR_SUBMIT_KEYMAP, Editor, Key, StatusLine, Text, TUI
from mocode_tui.core import Document, Viewport


async def session(tui):
    footer = Document()                           # the shell's own footer document
    editor = Editor(keymap=EDITOR_SUBMIT_KEYMAP)  # enter stays the host's submit gesture
    footer.add(editor, id="input")                # the pinned input row
    footer.add(StatusLine(left=("ready",)), id="status")
    tui.add_band(Viewport(footer))                # park the footer under the pane area
    while True:
        key = await tui.read_key()
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break                                     # EOF, or the quit gesture
        if isinstance(key, Key) and key.name == "enter":
            tui.add(Text(f"you: {editor.text}"))      # the submit gesture is the host's
            editor.clear()
            continue
        editor.handle(key)                            # every editing key, and a Paste
    tui.stop()

asyncio.run(TUI().run(session))
```

`Document` and `Viewport` are the two deeper seams the recipe reaches for;
both stay public at `mocode_tui.core`. The assembly grows with one line per
tier, and each line is a decision — the dispatch order above is what orders
them:

```python
from mocode_tui import Option, Palette

palette = Palette([Option("/help", value="help", description="the command list")])
footer.add(palette, id="palette")   # `/` opens it: a self-contained panel with its
                                    # own query row (route it first while it is open)
scrollbar = Scrollbar(tui, pane="primary")   # chrome: budgets the pane's edge column
toasts = Toasts(tui)                         # overlays: after the chrome, before the gestures
gesture = SelectionGesture(tui)              # the drag owns press/motion/release
ring = FocusRing([editor, menu, tree])       # the focused widget's own keys, after the gestures
pointer = Pointer(tui, ring=ring)            # hover + stationary clicks (TUI(hover=True))
```

Two facts keep the assembly honest. **No component here is an app**: the
footer's `Editor` is a field and `StatusLine` is a row, and the submit — the
one piece of behavior the library refuses to own — is the five lines inside
the loop above. **The band is not a pane**: it takes no focus and no split, a
wheel over it scrolls the focused pane, and its height is its content's
(`Viewport.natural_height`), so an opening palette pushes the pane area up
exactly as a pinned block would.

For the exhibits-instead-of-an-app shape, `examples/demo.py` is the reference
the other way: a gallery of twelve pages with **no input box anywhere** and a
modal `Palette` overlay that closes the moment a command is taken.

## Selection

Selection is another assembly that touches the driver — the peer of the
`chrome` controllers (`Scrollbar` / `Toasts`), not a `render(width)`
component. The mechanism is the kernel's (`mocode_tui.core.selection`: the
`Selection` model, the `highlight` overlay, `extract`) and the driver's
(`tui.selection` reads, `tui.set_selection` writes and invalidates); every
behavior is one policy object (`mocode_tui.gesture`) a host opts into with
a single line. The rationale — document-space addresses, the overlay at the
composition root, the mode table, OSC 52's contract — is `docs/DESIGN.md`;
this section is the handbook: the constructor, the state machine, the
primitive, and the cookbook of replacement points.

### `SelectionGesture` — the constructor

```python
SelectionGesture(
    tui,
    *,
    on_end=copy_on_select,   # the selection-end action; None selects with no effect
    scroll_rows=2,           # rows one edge tick scrolls — and extends the head
    scroll_tick=0.05,        # seconds between edge ticks
    double_click_seconds=0.35,  # the word-select window around the last press's cell
)
gesture.handle(event) -> bool   # True consumed, False the host's
gesture.detach()                # cancel the ticker, drop the in-flight drag
```

The gesture is single-pointer by construction: the **left** button anchors
and extends, every other button, every key, every `Paste` and every lone
motion passes through untouched. It owns its own anchor and head addresses
and mirrors the drag into the driver through `set_selection`; it keeps no
copy of the text, the rows, or the layout. Timestamps come from the
driver's public clock seam (`tui.clock()`), so the event model itself stays
timeless.

### The state machine

The host's dispatch is `if not gesture.handle(event): ...` — the same
consume-one-event contract `Input`/`Editor` answer, with one dispatch line
covering the whole feature. What the left button's reports do:

| Report | Effect |
|---|---|
| `press` (plain) | Anchors at the cell the hit test resolves. A press on blank fill, outside the last layout, or on a block removed since it retires the previous highlight and anchors nothing. A zero-width range paints nothing, so the previous highlight already yields to this press. |
| `press` on an edge row | Arms the auto-scroll ticker immediately, not only a motion: the pointer can reach the edge *before* the button goes down, and a stationary press there emits no motion to arm it with. |
| `press` again, same cell, within `double_click_seconds` | Word select: the maximal non-whitespace run around that cell on its row, measured in display columns through the same measure the kernel cuts by — a CJK character selects whole. It fires `on_end` exactly once, at the press; the release that follows finalizes nothing; and it never arms the ticker. A cell on whitespace (or past the row's text, which clamps to the last column) has no run and degrades to a plain press — a double-click between words behaves like a click. |
| `motion` while dragging | Extends the head to the cell under the pointer. A motion off the content keeps the head where it is. A cleared overlay underneath the drag (a reflow, or a host write) ends the drag cleanly rather than dragging addresses that no longer point at the same glyphs. |
| `motion` onto an edge row | Arms the edge ticker; a motion onto any other in-content row disarms it; a motion off the content disarms it too. The edge zone is the viewport region's first and last rows — the scrolling window, never the pinned footer — so dragging into the footer cannot scroll the document. |
| `release` | Cancels the ticker and finalizes. A zero-width press-release — a click — clears the selection and never fires `on_end`: the clipboard is never clobbered by a click. A completed drag fires `on_end` exactly once, and the highlight stays until the next press so the user can verify what was copied. |
| wheel while a drag is in flight | Consumed: scrolls the viewport its signed `scroll_keys` count and co-extends the head by exactly the rows the viewport actually travelled (the wheel moves the content under a still pointer; the head follows). A binding the host deleted from `tui.scroll_keys` passes through. |
| second `press` mid-drag | Re-anchors a fresh drag from the new cell; the abandoned drag never fires `on_end`. |

The armed ticker rides the pump's existing `every(seconds, fn)` handles —
the working-spinner pattern, no new mechanism. Each tick scrolls `scroll_rows`
rows and moves the head by the offset the viewport actually travelled, in
document space, never by re-`hit_test`ing the previous frame's ownership
table. It stands down on edge-exit, release, `detach()`, a reflow that
cleared the overlay underneath it, and the document end (a scroll that could
not move the viewport means the content under the pointer is frozen too).
`detach()` cancels the ticker and drops the in-flight drag so a later release
cannot finalize it; the stored overlay is the driver's, and stays as the last
frame painted it.

### `copy_on_select` — the shipped `on_end`

```python
def copy_on_select(tui, selection):
    tui.screen.copy(extract(tui.document, selection, width=tui.screen.width))
```

Two lines, and the smallness is the point: every mechanism (the range walk
of `extract`, the clipboard primitive) lives in the kernel already, and the
whole policy is "which text, which screen, once". `extract` takes `width`
keyword-only — it is the width the addresses were laid out against, and
there is no honest default — and it reads the document blocks straight, so
content the viewport has scrolled past copies exactly like the visible rows.

### `Screen.copy` — the clipboard primitive

`screen.copy(text) -> bool` emits `\x1b]52;c;<base64>\a` (built in
`core.ansi.copy_clipboard`) and reports whether it wrote. A
`TerminalScreen` writes only when live — a pipe or a file has no clipboard
and the toolkit never scatters escapes at a surface that cannot render them,
so `copy` answers `False` there. A `HeadlessScreen` is live by construction
and records the bytes: that is how a test proves a copy happened, since
nothing observable comes back from a live terminal. Even a `True` is
best-effort — terminals may refuse application clipboard writes by policy —
which is why the gesture's `on_end` hook, not the primitive, is the real
contract.

### The extension cookbook

Four worked replacement points. Between them they are the whole surface a
future feature author needs — none of the recipes below reaches into the
kernel.

**(1) Drive `tui.set_selection` from your own loop.** A search feature
highlights its hit without any gesture at all: the driver's surface is one
write, and the overlay paints it.

```python
from mocode_tui.core import Selection

# Your search found "transcript" on block "b1", rendered row 0, column 15.
term = "transcript"
anchor = ("b1", 0, 15)
tui.set_selection(Selection.between(anchor, ("b1", 0, 15 + len(term))))
# The write invalidates the frame; the pump repaints, overlay included.
```

**(2) Replace `on_end` — the `/quote` example.** This is an extension
example, **not shipped API**: the toolkit ships no `/quote` command.
It shows the hook receiving the finished range and prefilling a host editor
for an edit, through the editor's own buffer API.

```python
from mocode_tui import SelectionGesture
from mocode_tui.core import extract

def quote_on_select(tui, selection):
    """Quote the selection into the host editor: extract, prefix, prefill."""
    text = extract(tui.document, selection, width=tui.screen.width)
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    editor.clear()          # replace whatever is being typed
    editor.insert(quoted)   # a multi-line insert goes through the same buffer API
    tui.invalidate()

gesture = SelectionGesture(tui, on_end=quote_on_select)
```

**(3) Tune or retire the sub-gestures.** The three knobs and the `on_end`
switch, all constructor arguments:

```python
gesture = SelectionGesture(
    tui,
    on_end=None,                   # select without copying: no effect at selection end
    double_click_seconds=0.0,      # no word select: a live clock never reads inside a zero window
    scroll_rows=1, scroll_tick=0.02,   # a finer, slower edge crawl — v1 has no auto-scroll off switch
)
```

**(4) Restyle the highlight — own the composition root.** The kernel merges
the fixed `SELECTION` constant (`reverse`, attribute-only, so the run's
own colors survive under the overlay) and v1 has no injection point for it.
The recipe is to own the last step of the frame instead: the overlay is a
pure function over a laid-out frame, so yours composes on the kernel's and
paints through the driver's own painter.

```python
from dataclasses import replace

from mocode_tui import Line, Segment, Style
from mocode_tui.core import highlight

MARK = Style(reverse=True, fg="#ff8800")   # your highlight: reversed, your hue

def my_overlay(layout, selection):
    """The kernel's range cut, your style — the merge happens at your call site."""
    painted = highlight(layout, selection)
    if painted is layout:
        return layout    # the kernel marked nothing (None or an empty range): lazy no-op
    return replace(layout, rows=[
        Line([
            # the kernel marks the in-range pieces by merging SELECTION
            # (reverse): re-merge your own onto exactly those
            Segment(s.text, s.style.merge(MARK)) if s.style.reverse else s
            for s in row.segments
        ])
        for row in painted.rows
    ])

# At a host-owned composition root — the shape the driver's own paint runs:
layout = tui.frame.compose(tui.screen.width, tui.screen.height)
layout = my_overlay(layout, tui.selection)
tui.painter.paint(layout)
```

The re-merge keys on `reverse`, which is the kernel's documented mark; a
segment that was already reversed for its own reason (the editor's block
cursor) is indistinguishable from a marked one, so this seam fits content
carrying no cursor of its own. Note the boundary the recipe keeps (D7): the
theme's `selection` field styles the *component* cursors (`Tabs`, `Tree`,
and a menu built with `selected_style=theme.selection`) — that seam is
per-component `*_style=` arguments — while this overlay is the
document-level one. Two vocabularies, two mechanisms, never mixed.

## Focus

Focus is the second assembly that touches the driver — the peer of
`SelectionGesture`, and a *layer*, never a component's responsibility.
A component only declares that it can be focused: one read-write flag,

```python
from mocode_tui.core import Focusable   # the protocol: `focused: bool`

class Gauge:              # any component may be a focus target
    focused = True        # the ring rewrites this as the focus moves
```

and one rendering rule — **unfocused means the cursor style merged with
`theme.dim`**: `Select`'s marker and label (`selected_style.merge(dim)`,
the description column keeps its own `dim`), `Tree`'s `cursor_style`, and
`Tabs`' `active_style`. The hue survives, the weight drops, and no new
theme field appears. `Input`/`Editor` already had the flag (it draws — or
omits — their block cursor), so they satisfy the protocol unchanged.

Everything else lives in `mocode_tui.focus.FocusRing`, a host opts in with
one line, and the component never learns a manager exists:

```python
from mocode_tui import FocusRing

ring = FocusRing([menu, tree])        # the first target is focused at once
event = await tui.read_key()
if event.name == "tab":
    ring.focus_next()                 # the host owns the cycle key
elif not ring.handle(event):
    ...                               # the host's own dispatch
# a mouse hit from tui.hit_test(x, y) runs the click policy:
ring.click(hit)
```

### The constructor and the cycle

`FocusRing(targets=(), *, wrap=True)`. Every target must satisfy
`Focusable` — a target that cannot be focused raises `TypeError` at
construction, before the first keypress. A non-empty ring focuses
`targets[0]` and clears every other target's flag; an empty ring holds no
focus and every method degrades safely. `focus(target)` answers whether
the focus moved (an unregistered target answers `False` and leaves the
focus alone; the current target answers `False`); `focus_next(delta=1)`
cycles through the registered order, wrapping by default, clamping at the
ends with `wrap=False`, and never moving on a single-target or empty ring.

### The routing table — `handle(event)`

`handle` dispatches one `Key` or `Paste`, answering whether the ring
consumed it, in this order:

| # | Condition | Action |
|---|---|---|
| 1 | the focus is empty | `False` |
| 2 | the focused target has `handle(event)` | its answer wins — a field consumes its own keys (printables, arrows, backspace) and its `Paste`, ahead of every ring verb |
| 3 | an unconsumed `Key`: `up`/`left` or `down`/`right` | `move(-1)` / `move(+1)`; with no `move` method the arrow falls back to its own verb — `move_up()`, `move_left()`, `move_down()`, `move_right()` (the text fields' shape) |
| 3 | an unconsumed `Key`: `enter` | `activate()`; a target that is not `Activable` answers `False` |
| 4 | anything else | `False` — the host keeps routing the submit gesture, the palette, quit |

### The click policy — `click(hit)`

`hit` is what `tui.hit_test(x, y)` resolves (a `Hit`: the block, the
block-internal `row`/`col`, the pane id). One click runs four steps:

| # | Condition | Action |
|---|---|---|
| 1 | the block's component is `Clickable` | `component.click(hit.row, hit.col)` — **any** clickable component, ring target or not (a page may hold mouse-only widgets beside the ring) |
| 2 | the component is in the ring and not the current focus | focus it — the first click only moves the focus |
| 3 | the component is in the ring and already focused | `activate()` when it is `Activable` — the second click activates (standard desktop semantics) |
| 4 | always | answer whether anything consumed the click (the host repaints or toasts on it) |

### The pointer's door — hover, and the dispatch order

Hover is not the ring's: the ring routes keys and owns what a click means,
but it reads no motion report and flips no hover flag. Hover is the
`Pointer` tier's, and it needs DECSET 1003 — under the default 1002 a
button-free motion is never reported, so a hover host opens the mode with
`TUI(hover=True)`. The reference wiring routes every report through the
pointer beside the gesture and the ring (`docs/DESIGN.md` has the rationale):

```python
from mocode_tui import FocusRing, Pointer, SelectionGesture

ring = FocusRing([menu, tree])        # the first target is focused at once
pointer = Pointer(tui, ring=ring)     # hover + stationary clicks (TUI(hover=True))
gesture = SelectionGesture(tui)       # the drag owns press/motion/release
event = await tui.read_key()
if pointer.handle(event):             # a motion that moved the hover, or a click
    tui.invalidate()                  # the pointer's answer: a repaint cue
if not gesture.handle(event):         # the gesture consumes the reports it owns
    if not ring.handle(event):        # then the focused target's own keys
        ...                           # the host's own dispatch
```

Three rules make the pair exact. **The pointer never consumes:** its `True`
means "what it tracks changed" (the hovered leaf entered, left or moved to
another row of itself, or a click was dispatched), never "the event is
spent" — a drag's reports reach the gesture untouched. **The click descends
first:** `Pointer` resolves the cell through `tui.hit_test`, walks `descend`
to the deepest leaf, and runs exactly the ring's click policy above (or
dispatches the deepest `Clickable` leaf itself when no ring is mounted — a
mouse-only page needs no ring). **The hover is state, not a callback:** the
leaf's `hover` flag (and `hover_at(row, col)` where it has rows) is written
by the pointer and read by the render; `Pointer.clear()` drops the hover
after a pane switch or a resize, best-effort by design.

**Out of scope, deliberately**: no hover of the ring's own (hover is the
`Pointer` tier's, above — the ring reads no motion report), no hotkey beyond
`tab` (the ring binds nothing; the host routes `tab` to `focus_next`), no
mouse drag (press/motion/release is `SelectionGesture`'s, with the pointer
watching beside it), and no
pane/window focus (that is the frame's — `TUI.focus_at` and the pane
rectangle own which pane gets input).

## Markdown

`Markdown` (in the `mocode_tui.widgets.markdown` package) is a
**rule-registry engine**, not a regex pile. Two ordered registries do all
the work: a `BlockRule` classifies the line at the cursor — `match(lines,
i)` returns how many lines it consumes, `None` to decline — and renders
exactly those lines; an `InlineRule` recognizes one inline construct at a
position and returns `(end, segments)`. The engine walks the buffer, first
match wins, and `ParagraphRule` is the mandatory catch-all at the end of
`BLOCK_RULES`. The shipped inline registry is tried in the order
`code` → `bold` → `strike` → `italic` → `link`: the rules that share an
opening marker (bold and italic both open with `*`) are ordered
sharpest-marker-first, and a rule placed before another interrupts it.

| element | input | rendering |
|---|---|---|
| heading | `#`..`######` + space | one gold ladder from `Theme.headings`; **h1 is underlined**, h2 stands alone, h3+ keep their `###` markers (the marker is the depth cue) — no bold on the ladder |
| unordered list | `- ` / `* ` (2-space indent per level) | marker kept **verbatim** (no bullet), marker in `list_marker` purple, nesting by indent (deeper indents cap at two levels), hanging indent on wrap |
| ordered list | `N. ` | number kept verbatim, marker colored as above, nesting as above |
| block quote | `> ` | every line gets a muted `│ ` prefix; the body re-runs the block registry behind the bar and renders italic (colored/bold segments keep their own emphasis) |
| fenced code | ```` ``` ````-delimited | opening and closing fence lines render in the theme's muted; the body goes through the `Highlighter` seam (`highlighter=`, the theme's `code` style when untagged), an unclosed fence runs to the end |
| table | `\| a \| b \|` + `\|---\|---\|` | box grid via the `Table` component (uncolored `Theme.table_border`, plain header, `:--`/`--:`/`:-:` alignment, cells render inline markup, one `├─┼─┤` between every two data rows, `\|` a literal pipe) |
| thematic break | `---` / `***` on its own line | `Divider` rule capped at `divider_max_width` columns (default 80) |
| paragraph | anything else | soft line breaks join, word-wrapped |
| inline | `` `code` `` `**b**` `~~s~~` `*i*` `[t](u)` | `inline_code` pink / bold / struck (`~~…~~` is an attribute-only `Style(strike=True)`, no colour change) / italic / `link` underlined label, with the url as the label's `link`/`action` payload (the url itself is not rendered) |

**Rendering notes:** adjacent blocks are separated by exactly one blank row
— the `gap` argument (default 1; `gap=0` stacks blocks directly) —
and the source's own blank rows never add a second one. Table cells are
parsed with the inline engine, so `` `code` ``/`**bold**`/`[t](u)` render
inside a grid cell, and an escaped `\|` stays a literal pipe inside one cell
instead of splitting the row. A thematic break spans at most
`divider_max_width` columns (default 80, `None` = the full width). A link
renders its label only, styled with `Theme.link`, and keeps the url as the
label segment's payload: the row's bytes wrap the label in the OSC 8 pair (a
real hyperlink to the terminal — its own cmd+click opens it) and a click on
the label lands the url in `Markdown.chosen`. Every row a rule returns is
wrapped and `fit` to `width`, so no row ever exceeds the painting width —
and a payload rides through the wrap and the truncation: every row a long
label breaks across still answers the same url.

**Streaming is safe by construction.** `text` is mutable — assign it one
chunk at a time — and every prefix renders: a half-open fence keeps its
body, a table is only a table once header *and* delimiter row are both
present (otherwise it is a paragraph), and an unclosed
`**`/`~~`/`` ` ``/`[t](` stays literal. `StrikeInlineRule` (exported from
`mocode_tui.widgets.markdown`) is the built-in strikethrough: it declines a
`~~` run with no partner or with empty content, so a streaming prefix is
never half-struck.

### The render context

Rules are dep-free singletons — no theme, no registry, no highlighter of
their own — so one instance serves every `Markdown`. What a rule needs to
render arrives in one frozen **`RenderContext`**
(`mocode_tui.widgets.markdown.RenderContext`), which `Markdown` builds once
at construction:

| field | meaning |
|---|---|
| `theme` | the resolved `Theme` (`DEFAULT_THEME` when none was passed) |
| `highlighter` | the fenced-code engine, or `None` (the fence then derives one from the theme) |
| `divider_max_width` | the thematic-break cap the component was built with |
| `block_rules` | the **live** block registry of the document being rendered |
| `inline_rules` | the **live** inline registry |

Because the context carries the *live* registries, a custom rule reaches
every built-in block — quote bodies, list continuations and the paragraph
catch-all that yields to higher-priority rules all re-run the same registry
— with no re-binding of any kind. There are no `with_*` cloning
conventions: extending is "implement the protocol, read the ctx".

### A custom inline rule, end to end

The smallest useful extension is one `InlineRule`. An inline rule is
`name` + `match(text, pos, ctx)`; it returns `(end, segments)` when the
construct starts at `pos` and `None` to decline. A style that sets a color
is absolute; an attribute-only style merges onto the surrounding run's base
style.

```python
from mocode_tui import Markdown
from mocode_tui.core.lines import Segment
from mocode_tui.widgets.markdown import INLINE_RULES


class MentionRule:
    """@handle in the theme's accent -- one inline rule, end to end."""
    name = "mention"

    def match(self, text, pos, ctx):
        if text[pos] != "@":
            return None                      # decline: not ours
        end = pos + 1
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1
        if end == pos + 1:
            return None                      # a lone "@" is not a mention
        return end, [Segment(text[pos + 1 : end], ctx.theme.accent)]


md = Markdown("hi @shipped", inline_rules=[MentionRule(), *INLINE_RULES])
for row in md.render(40):
    print(row.text)                        # "hi shipped"
    print([(s.text, s.style.fg) for s in row.segments])
```

That is the whole integration surface:

- **Register by prepending.** `inline_rules=[MyRule(), *INLINE_RULES]`
  (and `block_rules=[MyBlockRule(), *BLOCK_RULES]`) — order is the match
  priority, so put a rule before any rule whose marker it opens with.
- **Read what you need off `ctx`.** `ctx.theme` follows the component's
  `theme=`, so the rule restyles with the document instead of hard-coding a
  color.
- **No cloning.** A custom block rule reaches quote bodies and list items
  automatically, and the paragraph catch-all yields to it, because the
  context carries the live registry.

**Math is the documented extension point, not a feature.** `$...$` slots in
as one more `InlineRule` (and `$$...$$` display equations as one more
`BlockRule`); the registries are the only integration surface, so nothing in
the engine needs to change when it lands.

### Highlighting

`Markdown(..., highlighter=...)` — and any component that takes the seam —
accepts a **`Highlighter`**: any object with `highlight(code, lang) ->
list[Line]`. The built-in `RegexHighlighter` (in
`mocode_tui.widgets.syntax`) colors 16 languages — Python, JavaScript,
TypeScript, bash/shell, JSON, YAML, TOML, Markdown, diff, Rust, Go, C, C++,
HTML/XML, CSS and SQL — under 32 tag keys, aliases included, with five token
classes: `comment` muted + italic, `string` success, `number` warning,
`keyword` the accent's hue, `builtin` the theme's `code` ice blue. **No
token carries weight** — code stays weight-neutral, so the only bold left in
a default render is the `**…**` syntax itself, and the only struck run is
`~~…~~`. Matching is per-line and first-match-wins, and text no rule claims
keeps the theme's `code` style.

`default_highlighter()` shares the stock instance (building one compiles
every rule, so components share rather than rebuild),
`RegexHighlighter(theme=…, languages=…)` restyles or extends the table, and
`highlight(code, lang)` is the convenience entry point. Injecting your own
object replaces the engine entirely — the protocol is the integration
surface.

## Building your own component

A component is one class with `render(width)`. The protocol is
`mocode_tui.Component`:

```python
from mocode_tui import DIM, Line, Segment, Style, SUCCESS


class ProgressBar:
    """A determinate progress bar -- a custom component, not a library one."""
    __slots__ = ("fraction", "label")

    def __init__(self, fraction: float, label: str = ""):
        self.fraction = min(1.0, max(0.0, fraction))  # clamp to [0, 1]
        self.label = label

    def render(self, width: int) -> list[Line]:
        lead = f"{self.label} " if self.label else ""
        lead_w = Line.from_text(lead).width
        track = max(0, width - lead_w - 2)  # room for the [ ] frame
        done = min(track, int(round(track * self.fraction))) if track else 0
        row = Line((
            Segment(lead),
            Segment("["),
            Segment("\u2588" * done, SUCCESS),         # filled: green
            Segment("\u2591" * (track - done), DIM),    # empty: shaded
            Segment("]"),
        ))
        return [row.fit(width)]  # always fit back to the painting width
```

`ProgressBar` grew up into a library component (`mocode_tui.ProgressBar`,
with `theme=`, `width_chars=` and re-clamping `fraction`); the recipe is
still the shape a custom one takes.

Rules of thumb:

- **Measure, don't guess.** Use `Line(...).width` (or `Segment` counts) for
  display width — never `len()`, which miscounts wide characters. The
  toolkit's own truth is `visible_width` (wcwidth), exported at the package
  root together with `wrap_text`; `Line.width` is its per-row face and
  `ellipsize_tail` lives in `mocode_tui.core` / `mocode_tui.core.text`.
- **Always `fit(width)`** the rows you return so a tight screen truncates
  with a `…` instead of wrapping or overflowing.
- **Resolve styles once.** Take `style=` / `theme=` and resolve
  explicit > theme > `DEFAULT_THEME` in `__init__`, not in `render`.
- **Keep it pure.** `render` must not paint, sleep, read keys, or mutate
  global state — the same component renders in any width and caches like any
  other.
- **Drive it through the driver.** Put it in a block
  (`tui.add(ProgressBar(0.4))`), mutate it over time, and call
  `tui.invalidate()`; the pump and diff handle the rest.

`ProgressBar` and any other class shaped like this drop straight into
`Document.add`, `Row`, `Column`, and `Panel` — which is exactly how the
built-ins are assembled.
