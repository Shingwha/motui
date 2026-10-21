# Components

This page is the task catalogue: what each component is for, how to construct
it, which verbs it answers, what result it leaves, and which protocols it
implements. The mechanisms behind those contracts are in
[`docs/DESIGN.md`](DESIGN.md); the non-negotiable rules are in
[`docs/CONTRACT.md`](CONTRACT.md).

Every catalogue entry uses the same template:

```
purpose -> signature -> verbs -> result -> protocols -> notes
```

## The render protocol

A component is anything with one method:

```python
def render(self, width: int) -> list[Line]: ...
```

- `width` is the full painting width. The component owns its wrapping and
  truncation; the painter only counts rows.
- Return one `Line` per visual row. A row is a tuple of `Segment` values,
  each carrying `text`, a frozen `Style`, and optional `link` / `action`
  payloads.
- `Line.fit(width)` truncates with an ellipsis, `Line.fill(width, style)`
  extends the row with a band under the content, and `Line.filled(width)`
  builds a blank row.
- `render` is pure: no painting, no scrolling, no I/O, no sleeping.

Blocks add a row cache on top. `Block.rows(width)` is the one cached read;
`Block.render(width)` is the uncached door. A block caches only when its
component implements `Revisioned` and returns a non-`None` snapshot; an
unrevisioned component re-renders on every read. There is no sealed state.
See [documents and caching](DESIGN.md#documents-blocks-and-caching).

## Global conventions

Three conventions apply to every entry below.

**`Component` is one method.** A render-only component implements
`render(width) -> list[Line]` and nothing else. `Row`, `Column`, `Spacer`
and `Text` are such renderers.

**Themed widgets inherit `Widget`.** `Widget` owns `theme`, `styles`,
`focused` and `hover`, supplies `group(name)`, and answers the interaction
verbs as no-ops: `handle(event)`, `click(row, col)`, `drag(row, col, kind)`,
`hover_at(row, col)`, `activate()`, `take_result()` and `revision()`.
A widget overrides only the verbs it takes. The capability protocol names
(`Clickable`, `Controller`, `Revisioned`, ...) are implementation
vocabulary, not facade exports; only `Component` and `Widget` are public.

**Compound widgets own focus.** A widget that routes its children's keys
through its own `handle` sets `owns_focus = True` (`Form`, `ComboBox`).
`App.add` registers the compound itself and skips its subtree, so a form's
fields are not competing focus targets. A click has two halves: the deepest
leaf gets its action (`click`), and each ancestor gets `focus_at(row, col)`
to move its internal cursor (`Form`'s field index, `Dialog`'s button index).
The focus tier focuses the nearest registered ancestor. A container is
never activated by a click on its background; activation belongs to the
leaf.

**Styles are one override value, resolved at render time.** Every themed
widget accepts:

```python
Widget(theme=None, styles=None)
```

`theme=None` inherits the App theme; `styles: Styles` replaces whole role
groups (`text`, `surfaces`, `borders`, `controls`, `rows`, `status`,
`content`, `chrome`, `overlays`, `syntax`) and leaves `None` groups to the
theme. There are **no** per-token `style=` / `hover_style=` /
`focus_style=` / `disabled_style=` / `ground_style=` / `label_style=`
arguments and no `focused=` constructor flag; assign `widget.focused`
instead. The widget reads its groups in `render`, so assigning
`App.theme` (or `widget.theme`) repaints it without a rebuild.

`Text` is the exception: a core renderer with `style=` + `theme=` and no
`styles` group. It resolves `style=` over `theme.text.base` at
construction.

## The driver in call order

```python
app.add(component, id="x", pin=None, pane=None)   # -> block id
app.get("x"); app.remove("x")                     # -> component
app.focus("x"); app.focus_next(); app.bind("c-k", cb)
app.dock(component, edge="bottom"); app.undock("bottom")
app.toast("saved"); app.open_modal(panel); app.open_palette(commands)
app.find(); app.set_focus_targets([...])
app.theme = theme                                  # repaint mounted widgets
app.run()                                          # App owns the loop
tui.add(component, id="x")                         # the low-level driver
event = await tui.read_event()                     # pure read; no policy
tui.hit(x, y); tui.hit_leaf(x, y)
```

`app.add` targets the focused pane unless `pane=` is given; an interactive
widget joins the focus ring, and a theme-less `Widget` takes the App theme.
Block ids are unique across the whole frame. `TUI.read_event` returns wheel
reports, page keys and presses untouched; `App` is what routes them.

## Text

### Text

- **Purpose:** plain, wrapped text; action spans are clickable and hoverable.
- **Signature:** `Text(text="", *, style=None, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`
- **Result:** `take_result() -> str | None` (the `action` payload under a click)
- **Protocols:** Component, Revisioned, Clickable, Hoverable
- **Notes:** a core renderer (`motui.core`, also on the root), not a
  `Widget`: it takes one explicit `style=` over `theme.text.base` and has
  no `styles` group. `text` is mutable for streaming. Each logical line is
  word-wrapped; `hover_at` marks the span under the pointer. A subclass can
  return its own `Line` values and inherit the hit testing unchanged.

### Markdown

- **Purpose:** a streaming-safe Markdown document rendered through rule
  registries.
- **Signature:** `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, styles=None, highlighter=None, glyphs=GLYPHS, gap=1, divider_max_width=80, max_width=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `fences() -> list[tuple[str, str]]`
- **Result:** `take_result() -> str | None` (a link url or a `"todo:<i>"` payload)
- **Protocols:** Component, Revisioned, Clickable, Hoverable
- **Notes:** block rules consume lines, inline rules recognize constructs.
  Unknown syntax degrades to a paragraph. `max_width` caps the document's own
  wrap width; `divider_max_width` caps thematic breaks. A task box uses
  `glyphs.check_off` / `glyphs.check_on`; bullets use `glyphs.bullets`
  (`•`, `◦`, ...) and a block quote uses `glyphs.quote`. A task box's
  payload is the task ordinal across the document; the host rewrites its own
  `text` after reading it. `styles` overrides the content/text/syntax role
  groups per instance; a theme switch clears the stream cache.

### Diff

- **Purpose:** a line-level unified diff of two texts.
- **Signature:** `Diff(before, after, *, context=3, numbers=False, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** the walk and hunks are computed once at construction; assigning
  `before`, `after`, `context`, `numbers`, `glyphs`, `theme` or `styles`
  rebuilds them. Rows are `@@` headers, `glyphs.diff_add` /
  `diff_remove` / `diff_context` lines and `… N lines` elisions. Display
  only.

### Notice

- **Purpose:** one message row with a level glyph.
- **Signature:** `Notice(text, *, level="info", glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** every level leads with one glyph from the vocabulary: `i` for
  `info` (and any unknown level), `✓` for `success`, `!` for `warn` and
  `×` for `error`. The glyph carries `text.base` for info and
  `status.success` / `status.warning` / `status.danger` otherwise; the
  message text stays plain. Truncated, never wrapped.

## Forms

### Input

- **Purpose:** a single-line editable field with a prompt and a block cursor.
- **Signature:** `Input(text="", *, prompt=None, placeholder="", mask="", glyphs=GLYPHS, theme=None, styles=None, keymap=None, read_only=False)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`, `home()`, `end()`, `undo()`, `redo()`, `cursor_position(width)`
- **Result:** none (`take_result` is not a field concept)
- **Protocols:** Component, Revisioned, Controller, Clickable, Focusable
- **Notes:** editing keys come from the keymap; `enter` is unbound by
  default. A paste is folded into one line (newline runs become spaces).
  `prompt=None` means `seat(glyphs.prompt)` (`❯ `); `prompt=""` removes the
  prompt and its seat. `read_only=True` refuses every routed event without
  touching the buffer. `mask` is display-only; `.text` stays plain. The
  body, caret, prompt, placeholder, selection and hover colors come from
  `text` / `content` / `surfaces` (or a `styles=` group override).

### Editor

- **Purpose:** a multi-line editable buffer with a block cursor.
- **Signature:** `Editor(text="", *, placeholder="", mask="", theme=None, styles=None, keymap=None, max_rows=None, read_only=False)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`, `home()`, `end()`, `undo()`, `redo()`, `cursor_position(width)`
- **Result:** none
- **Protocols:** Component, Revisioned, Controller, Clickable, Focusable
- **Notes:** a paste keeps its newlines. `max_rows` slides a window over the
  cursor. `EDITOR_SUBMIT_KEYMAP` leaves `enter` to the host and binds `c-j`
  to `newline` instead. `read_only` behaves as on `Input`. Styles resolve
  from the same role groups as `Input`.

### Checkbox

- **Purpose:** one-row checked/unchecked toggle.
- **Signature:** `Checkbox(label, *, checked=False, glyphs=GLYPHS, disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> bool | None` (the new `checked` value)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** the mark is `glyphs.check_on` / `glyphs.check_off`, drawn in
  `content.accent`; the label uses `text.base`. The empty seat collapses when
  a mark is `""`. Carries the tooltip's `hint` protocol.

### RadioGroup

- **Purpose:** a single-choice group with `(•)` / `( )` markers.
- **Signature:** `RadioGroup(labels, *, index=0, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `home()`, `end()`,
  `activate() -> bool`
- **Result:** `take_result() -> object | None` (the selected label or payload)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** rows take plain labels or `Option` values; a non-empty
  description raises at construction. `glyphs.radio_on` / `glyphs.radio_off`
  draw the mark in `content.accent`; labels use `text.base`; rows resolve
  through `theme.rows.band(...)`. The cursor steps clamped. A step, a click
  and `activate` all leave the new pick pending.

### CheckboxGroup

- **Purpose:** a multiple-choice group over a mark set, built on
  `MultiSelect`.
- **Signature:** `CheckboxGroup(labels, *, marked=(), index=0, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `home()`, `end()`,
  `activate() -> bool`, `toggle() -> bool`
- **Result:** `take_result() -> list[object] | None` (marked values in row order)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** `glyphs.check_on` / `glyphs.check_off` draw the marks in
  `content.accent`; labels use `text.base`; rows resolve through
  `theme.rows.band(...)`. A click moves the cursor and flips that row's mark;
  `activate()` is `toggle()`. `marked` is the public `MarkSet` a host may
  seed and read. Nothing marked means `None`.

### Select

- **Purpose:** the single-choice vertical option list every menu and choice
  preset builds on.
- **Signature:** `Select(options=(), *, title="", max_rows=8, wrap=True, glyphs=GLYPHS, commit=False, window=False, disabled=False, disabled_items=(), theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `home()`, `end()`,
  `activate() -> bool`
- **Result:** `take_result() -> object | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** `Select` is single-choice. `wrap` cycles or clamps, `window`
  top-sticks or centers, `commit` makes the cursor the choice.
  `glyphs.cursor` marks the cursor; descriptions use `text.muted`. A
  description column is measured over the whole option universe. A list
  longer than `max_rows` gets a window and an `(i/n)` counter. The marked
  multi-selection is `MultiSelect`; `Select` has no `multi` or `marked`.

### MultiSelect

- **Purpose:** the marked, multiple-selection variant of `Select`.
- **Signature:** `MultiSelect(options=(), *, title="", max_rows=8, wrap=True, glyphs=GLYPHS, marked=(), disabled=False, disabled_items=(), theme=None, styles=None)`
- **Verbs:** the `Select` verbs plus `toggle() -> bool`
- **Result:** `take_result() -> list[object] | None` (marked values in row order)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** `marked` is the public `MarkSet` of data-row indices;
  `toggle()` flips the cursor row's mark and `activate()` is the same
  gesture. The pending result is recomputed from the marks in row order
  (`None` while nothing is marked). `glyphs.check_on` / `check_off` draw the
  marks; the cursor, window and description behavior are `Select`'s.

### Option

- **Purpose:** a label with an optional value and description.
- **Signature:** `Option(label, value=None, description="")`
- **Verbs:** none
- **Result:** none
- **Protocols:** plain value object
- **Notes:** `value` defaults to the label at the consuming widget. The
  form groups render labels only and reject a non-empty description.

### ComboBox

- **Purpose:** the form's pick-or-type control: an input over a filtered
  dropdown.
- **Signature:** `ComboBox(options=(), *, text="", max_rows=8, theme=None, styles=None, max_drop_rows=6, glyphs=GLYPHS)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`, `open()`,
  `close()`, `child_at(row, col)`
- **Result:** `take_result() -> object | None` (the picked option's value)
- **Protocols:** Component, Revisioned, Controller, Clickable, Container, Resultful
- **Notes:** while open, `down`/`up` move the list, `enter` takes the
  highlighted value and writes its label back into the field, `escape`
  closes with nothing. Every other event goes to the field. A paste is
  never read as a key. The dropdown is painted by a host-mounted `Modal` or
  `App.open_modal`; route `combo.handle` before `modal.handle` and keep both
  open states in step. `styles` forwards to the inner `Input`.

### Autocomplete

- **Purpose:** a `Select` whose rows are the matches of a query.
- **Signature:** `Autocomplete(options=(), *, max_rows=8, wrap=True, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** `set_query(text)`, plus the inherited cursor and activation verbs
- **Result:** `take_result() -> object | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** prefix matches come first, then substring matches,
  case-insensitive; an empty query matches all. The description column is
  measured over the whole universe so it never jumps while filtering.

### Slider

- **Purpose:** a one-row stepped integer control.
- **Signature:** `Slider(value=0, *, minimum=0, maximum=10, step=1, glyphs=GLYPHS, disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> int | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** the value snaps to the `step` grid; assigning `minimum`,
  `maximum` or `step` re-clamps and re-snaps. The track repeats
  `glyphs.slider_track`, the thumb is `glyphs.slider_thumb` and the value
  text uses `text.muted`. A click maps the rendered track column to the
  nearest grid point; `activate` confirms the value. The filled/empty bands
  come from `content.accent` / `chrome.scrollbar` (or `styles=`).

### Form

- **Purpose:** labelled fields with focus, navigation, validation and a
  one-shot submission.
- **Signature:** `Form(fields, *, gap=0, index=0, on_submit=None, theme=None, styles=None)`
- **Verbs:** `handle(event) -> bool`, `move(delta) -> bool`, `focus(target) -> bool`, `click(row, col) -> bool`, `focus_at(row, col) -> bool`, `activate() -> bool`, `child_at(row, col)`
- **Result:** `take_result() -> dict[str, object] | None`
- **Protocols:** Component, Revisioned, Controller, Container, Activable
- **Notes:** the form owns its fields (`owns_focus`), so `App` registers the
  form, not each field. A click on a field runs the field's `click` (caret)
  plus `Form.focus_at` (field cursor); a direct `Form.click` does both. The
  focused field's `handle` runs first, then `tab`/`down` and
  `s-tab`/`up` step, then `enter` validates every field. Errors land back in
  each `Field.error`. A clean submit leaves `{name: value}` pending and
  calls `on_submit` once. Values come from `Field.value()` or the
  component's first `value` / `text` / `checked` / `selected` / `marked`;
  `take_result` never consumes a field's own result. Labels use
  `content.accent`; errors use `status.danger` (or `styles=`).

### Field

- **Purpose:** one form entry: a component, a name, a label and hooks.
- **Signature:** `Field(name, component, label="", validate=None, value=None, error=None)`
- **Verbs:** none
- **Result:** none (the `Form` owns the submission result)
- **Protocols:** plain value object
- **Notes:** `validate(value)` returns an error string or `None`;
  `value()` is a custom extractor and wins over duck typing. `error` is
  form-managed state a host may read and clear.

## Data

### List

- **Purpose:** a cursor over a long sequence, rendered as a window.
- **Signature:** `List(items=(), *, window=8, prefix_jump=True, glyphs=GLYPHS, disabled=False, disabled_items=(), theme=None, styles=None)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`,
  `hover_at(row, col) -> bool`, `move(delta) -> bool`, `home()`, `end()`,
  `activate() -> bool`, `toggle() -> bool`
- **Result:** `take_result() -> str | None`
- **Protocols:** Component, Revisioned, Controller, Clickable, Activable, Hoverable, Focusable
- **Notes:** the window is centered on the cursor where the ends allow, with
  `↑ N more` / `↓ N more` counter rows from `glyphs.more_up/more_down`; the
  cursor is `glyphs.cursor` and marks use `glyphs.check_on/off`. The counter
  text uses `text.muted`. Movement clamps. `handle` consumes the arrows,
  home/end and (with `prefix_jump`) a printable as a case-insensitive prefix
  jump. Marks live in `marked`; `space` stays the host's key.

### Table

- **Purpose:** a box grid with an optional row cursor and marks.
- **Signature:** `Table(headers, rows, *, aligns=None, glyphs=GLYPHS, grid=None, disabled=False, disabled_items=(), theme=None, styles=None, wrap=True, max_col_width=40, min_col_width=3)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `activate() -> bool`, `toggle() -> bool`,
  `sort_by(col, *, reverse=False) -> bool`, `set_widths(widths)`,
  `header_line(width) -> Line | None`, `header_lines(width) -> list[Line]`
- **Result:** `take_result() -> int | None` (the activated data-row index)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** there is no cursor until a host sets `index`. `grid` is a
  `Border` (default `glyphs.grid`) and its lines use `borders.grid`; the
  header uses `text.muted`. `wrap=True` (the default) wraps long cells at
  `max_col_width=40` with `min_col_width=3`; a record may span several
  visual rows, every visual row carries the record's band, and
  `click`/`hover_at` map a visual row back to its data row. `wrap=False`
  keeps the old natural-width/shrink/ellipsis behavior. `sort_by` is the
  host's reorder by a column's rendered text (stable); the cursor, marks
  and pending result follow the record. `set_widths` pins per-column
  budgets; `header_lines` returns the whole wrapped header, `header_line`
  its first visual row.

### Tree

- **Purpose:** an indented, collapsible node list.
- **Signature:** `Tree(root_nodes, *, indent=2, glyphs=GLYPHS, disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `activate() -> bool`, `filter(query) -> bool`,
  `jump(char) -> bool`
- **Result:** none (`selected` reads the node)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** only expanded nodes render; leaves keep a blank indicator
  column. The fold marks are `glyphs.fold_open` / `glyphs.fold_closed`.
  `filter` prunes to matching labels plus ancestors and draws those
  chains open without rewriting the user's `expanded` flags. `jump` is
  wrapping type-ahead over visible rows. Row bands and guides resolve from
  `rows` / `text`.

### TreeNode

- **Purpose:** one tree node: label, children and state.
- **Signature:** `TreeNode(label, children=(), *, expanded=False, disabled=False)`
- **Verbs:** none
- **Result:** none
- **Protocols:** plain value object
- **Notes:** `expanded` is a mutable attribute; `activate` flips it.

### Tabs

- **Purpose:** a horizontal content strip with one underlined active label.
- **Signature:** `Tabs(tabs, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`
- **Result:** none (`index` reads the selection)
- **Protocols:** Component, Revisioned, Clickable, Hoverable, Focusable
- **Notes:** the strip is one row. Movement clamps and steps over disabled
  indices. The separator is `glyphs.vertical_rule` with one space on each
  side. An unfocused strip drops the indicator's hue from accent to muted;
  the underline remains. Active/inactive labels and the indicator come from
  `content.accent` / `text.faint` / `controls.focus`.

### NavList

- **Purpose:** a vertical navigation rail with a bar indicator.
- **Signature:** `NavList(items, *, groups=(), index=0, disabled_items=(), disabled=False, glyphs=GLYPHS, bar_space=None, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`
- **Result:** none (`index` reads the selection)
- **Protocols:** Component, Revisioned, Clickable, Hoverable, Focusable
- **Notes:** every row has the same bar seat, so labels align. The indicator
  is `glyphs.rail`; `bar_space` is a layout override (not a glyph).
  `groups` inserts unselectable group-title rows at item positions. An empty
  list renders zero rows. No `handle`: the host routes keys.

### ProgressBar

- **Purpose:** a determinate progress bar with an optional label.
- **Signature:** `ProgressBar(fraction=0.0, *, label="", width_chars=None, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** `fraction` re-clamps to `[0, 1]` on assignment. The filled
  cells are `glyphs.bar_full` and the rest `glyphs.bar_empty`. The track
  length follows `render(width)` unless `width_chars` pins it. The filled
  band uses `content.accent`, the empty band `text.faint`.

### Spinner

- **Purpose:** a frame-cycling activity indicator.
- **Signature:** `Spinner(text="", *, frames=None, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** `advance()`
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** the host decides when to call `advance()`; `revision()` covers
  the frame, the text and the resolved style. `frames=None` uses
  `glyphs.spinner`; an explicit tuple wins.

## Layout

### Row

- **Purpose:** children laid out side by side.
- **Signature:** `Row(children, *, widths=None, gap=1)`
- **Verbs:** `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Container
- **Notes:** `widths` entries are fixed column counts or `None` for a
  flexible share. The tallest child sets the row height.

### Column

- **Purpose:** children stacked vertically.
- **Signature:** `Column(children, *, gap=0)`
- **Verbs:** `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Container
- **Notes:** `gap` blank rows sit between children.

### Padding

- **Purpose:** whitespace around a child.
- **Signature:** `Padding(child, *, left=0, right=0, top=0, bottom=0, theme=None, styles=None)`
- **Verbs:** `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Container
- **Notes:** the blank areas are filled with the `surfaces.base` group (or
  a `styles=Styles(surfaces=...)` override) and merge underneath the
  child's own segments. Insets are clipped to the painting width.

### Panel

- **Purpose:** a child inside a single-line box, or a borderless filled panel.
- **Signature:** `Panel(child, *, title="", frame=True, border=None, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Container
- **Notes:** with `frame=False` there is no border or title, the child gets
  `width - 2`, and the `surfaces.base` group becomes the panel's ground.
  `border` is a `Border` value (default `glyphs.box`): `Border.square()`,
  `rounded()`, `heavy()`, `double()`, `ascii()` or `none()`. A titled box
  embeds the title in its top edge when it fits. Border color comes from
  `borders.base`.

### Divider

- **Purpose:** a horizontal rule built from one repeated character.
- **Signature:** `Divider(*, char=None, label="", glyphs=GLYPHS, theme=None, styles=None, max_width=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** `char=None` means `glyphs.horizontal_rule`; an explicit `char`
  overrides the glyph for this instance. `label` renders as
  `── label ────` across the width; an over-wide label is ellipsized.
  The rule uses `borders.base`, the label `text.muted` (or `styles=`).
  `max_width` caps the rule.

### Spacer

- **Purpose:** blank rows as a component.
- **Signature:** `Spacer(rows=1)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** the rhythm primitive for transcripts and layouts.

### Collapsible

- **Purpose:** a titled section whose body folds away.
- **Signature:** `Collapsible(title, body, *, open=True, glyphs=GLYPHS, disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `activate() -> bool`, `child_at(row, col)`
- **Result:** `take_result() -> bool | None` (the new `open` state)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Container, Focusable
- **Notes:** only the title row is the control; its marker is
  `glyphs.fold_open` / `glyphs.fold_closed`. While open, body cells map to
  the body at its indent; the title row belongs to the wrapper. Disabled
  refuses both flips.

### ScrollView

- **Purpose:** a fixed-height window over any component.
- **Signature:** `ScrollView(child, *, height=None, offset=0, bar=False, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`,
  `drag(row, col, kind) -> bool`, `scroll_up(n)`, `scroll_down(n)`,
  `scroll_to(offset)`, `scroll_by(delta)`, `reveal(row)`,
  `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Controller, Clickable, Container, Scrollable
- **Notes:** `height=None` shows every row and makes scrolling a no-op.
  `handle` owns the arrows, page keys, home/end and the vertical wheel, and
  answers `True` only on a real move. `bar=True` reserves the last column:
  a press on the thumb starts a drag through `ScrollState.scroll_to`, a
  press on the track pages by a viewport, and the wheel scrolls the view;
  `bar=False` renders and routes exactly as before. `offset`,
  `total_rows` and `scroll_state` are read-only views of the last render.
  A visible cell maps to child row `offset + row`; bar cells return `None`
  from `child_at`.

## Actions

### Button

- **Purpose:** the smallest interactive unit: one row of action.
- **Signature:** `Button(label, *, disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> bool | None` (`True` after a successful activation)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** any cell of the row is the control. Disabled refuses both doors
  and paints its quiet band. The base/hover/focus/disabled bands come from
  `controls.base` / `surfaces.hover` / `controls.focus` / `text.faint`
  (or `styles=`). Carries the tooltip's `hint`.

### Link

- **Purpose:** one row of clickable text in the theme's link style.
- **Signature:** `Link(text, *, disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> bool | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** same activation contract as `Button`, rendered in the link band
  (`content.link`, hover/focus from `surfaces.hover` / `controls.focus`).
  Carries the tooltip's `hint`.

### MenuBar

- **Purpose:** a one-row horizontal menu with one active label.
- **Signature:** `MenuBar(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False, theme=None, styles=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> str | None` (the active label)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** movement clamps and steps over disabled labels. Separators are
  `glyphs.vertical_rule` with one space on each side (the component owns the
  padding); the divider style is `chrome.divider`. `click` and `hover_at`
  resolve cells against the last render's span table, so padding, dividers
  and a truncating ellipsis carry no label. The active label is the
  selection, not a focus band.

### ContextMenu

- **Purpose:** the `Select` preset for a desktop context menu.
- **Signature:** `ContextMenu(options=(), *, title="", max_rows=8, glyphs=GLYPHS, **kwargs)`
- **Verbs:** inherited `Select` verbs (`click`, `hover_at`, `move`,
  `select`, `home`, `end`, `activate`)
- **Result:** `take_result() -> object | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** `commit=False`, `wrap=True`, `window=False`; the cursor is
  `glyphs.cursor`. It neither opens nor positions itself: mount it with
  `App.open_modal(menu, anchor=(y, x))` (or `Modal(tui, menu, anchor=...)`
  in a custom loop) at the click cell and route the pointer through the
  modal. `activatable` options settle on `activate()`.

### ShortcutBar

- **Purpose:** one row of key/label hints.
- **Signature:** `ShortcutBar(items, *, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** display-only chrome; no interaction and no result. Entries are
  joined by `glyphs.separator` (` · ` by default); keys use
  `content.accent`, labels `text.faint`. An over-wide bar truncates with an
  ellipsis.

### StatusLine

- **Purpose:** a dim two-sided status row.
- **Signature:** `StatusLine(*, left=(), right=(), theme=None, styles=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** left text at column 0, right text at the far edge, a computed
  gutter between. `left` and `right` accept `str` or `(str, Style)` entries
  and are copied at construction; the default style is `text.faint` (or a
  `styles=` override). Display-only.

## Overlays

### Dialog

- **Purpose:** a resolved box with a body and a button row: the modal's pure
  payload.
- **Signature:** `Dialog(title, body, buttons, *, danger=False, width=None, align="center", border=None, shade=True, frame=True, glyphs=GLYPHS, theme=None, styles=None)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`,
  `focus_at(row, col) -> bool`, `child_at(row, col)`
- **Result:** `take_result() -> object | None` (the taken button's value)
- **Protocols:** Component, Revisioned, Controller, Clickable, Container, Resultful
- **Notes:** `escape` cancels, `enter` takes the focused button's value, and
  tab/arrows walk the row clamped. `border` is a `Border` value (default
  `glyphs.box`); `danger=True` uses `borders.danger` and opens on the last
  non-dangerous button. Border and title colors resolve at render time from
  `borders` / `content.headings[1]` (or `styles=`). `frame=False` drops the
  box and title, keeps the body and button row, and uses `width - 2`.
  `focused_button` reads the button the keys act on (deliberately not named
  `focused`).

### ButtonSpec

- **Purpose:** one dialog button value.
- **Signature:** `ButtonSpec(label, value=None, styles=None, danger=False)`
- **Verbs:** none
- **Result:** none (the owning `Dialog` returns `value`)
- **Protocols:** plain value object
- **Notes:** `styles` overrides whole role groups on the rendered `Button`
  (`controls.base`, `surfaces.hover`, `controls.focus`); `danger=True`
  renders in the error band but stays enabled; the rule is "not the default
  focus", never "disabled".

### confirm_dialog

- **Purpose:** the classic Yes/No dialog builder.
- **Signature:** `confirm_dialog(message, *, danger=False, confirm_text="Yes", cancel_text="No", frame=True, glyphs=GLYPHS, theme=None) -> Dialog`
- **Verbs:** see `Dialog`
- **Result:** through the returned `Dialog`'s `take_result()`
- **Protocols:** factory function
- **Notes:** an untitled box with a `Text` body; the confirm button comes
  first.

### prompt_dialog

- **Purpose:** the one-line prompt builder.
- **Signature:** `prompt_dialog(title, *, placeholder="", mask="", confirm_text="OK", cancel_text="Cancel", styles=None, danger=False, frame=True, glyphs=GLYPHS, theme=None) -> Dialog`
- **Verbs:** see `Dialog`
- **Result:** through the returned `Dialog`'s `take_result()`; the field text
  is `dialog.body.text`
- **Protocols:** factory function
- **Notes:** the body is a single-line `Input`. The field binds no `enter`,
  so the return key falls through to the button row. `styles` is forwarded
  to the field as its group overrides; `mask` is forwarded verbatim.

### Modal

- **Purpose:** the blocking controller that paints any panel over a scrimmed
  frame.
- **Signature:** `Modal(tui, dialog, *, anchor=None, scrim=True, scrim_style=None, dismiss_on_click_outside=True, theme=None, focus=None)`
- **Verbs:** `open()`, `close(value=None)`, `handle(event) -> bool`,
  `take_result() -> object | None`, `detach()`, `set_theme(theme)`,
  `paint(frame)`
- **Result:** `take_result() -> object | None` (read once; `None` is a legal
  decision)
- **Protocols:** controller, not a Component
- **Notes:** lives in `motui.app.modal`. Constructing one registers it;
  `App.open_modal(panel)` constructs and opens it with the App theme and
  focus ring. `detach()` unregisters, closes, clears the result and pops a
  focus trap. While open it consumes everything: the panel's keys first, a
  panel `body` ahead of the panel's own `handle` (body-first), a press
  inside is the panel's click, a press outside dismisses. A host overriding
  `dispatch` for a quit gesture must run it **before** the modal. A closed
  modal paints nothing.

### CommandPalette

- **Purpose:** a self-contained command palette: query row over a filtered
  command list, in a modal.
- **Signature:** `CommandPalette(tui, commands, *, theme=None, max_rows=8, glyphs=GLYPHS, focus=None)`
- **Verbs:** `open()`, `close()`, `handle(event) -> bool`,
  `take_result() -> object | None`, `detach()`, `set_theme(theme)`,
  `render(width)`, `is_open`
- **Result:** `take_result() -> object | None`
- **Protocols:** controller and Component (it renders zero rows while closed)
- **Notes:** lives in `motui.app.command_palette` and on the package root as
  `motui.CommandPalette`. `App.open_palette(commands)` opens the App-owned
  instance. `up`/`down` move the list, `enter` leaves the highlighted
  command's value pending, `escape` closes with nothing. Every other event
  routes through the query `Input` and re-filters the list; the query prompt
  comes from `glyphs.prompt`. Opening resets the query and the list. This
  controller is not `ColorPalette`, the brand-color authoring value in
  `motui.core`.

## The row-band contract

Every vertical row widget (`List`, `Tree`, `Table`, `NavList`, `Select`,
`MultiSelect`, `Autocomplete`, `RadioGroup`, `CheckboxGroup`) resolves its
band through the widget's `rows` group (`styles.rows` when overridden, else
`theme.rows`); there is no separate band value to thread. Precedence:

```
disabled row      -> rows.disabled
hovered row       -> rows.hover      (whatever row it is on)
current row       -> rows.active     (focused)
                     rows.inactive   (unfocused)
selected row      -> rows.selected   (after the current-row branch)
marked row        -> rows.marked
every other row   -> rows.base
```

The active branch stops at the focus answer: a focused cursor row wears
`rows.active`, an unfocused one `rows.inactive`; the pointer's band still
wins over the cursor, and a disabled row wins over everything. Controls
(`Button`, `Checkbox`, `Collapsible`, `Slider`, ...) resolve through the
`controls` group with `disabled > active > focused > hovered > base`.

A row is its text-styled segments, then `fit(width).fill(fitted.width, band)`:
the band rests underneath the text and hugs the row's own cells. A `NONE`
band paints nothing. A full-surface band is the host's container's job:
wrap the widget in `Padding(styles=Styles(surfaces=...))` or
`Panel(frame=False, styles=Styles(surfaces=...))`.

```python
from dataclasses import replace

from motui import DEFAULT_THEME, List, Style, Styles

theme = replace(
    DEFAULT_THEME,
    rows=replace(
        DEFAULT_THEME.rows,
        active=Style(bg="#264f78"),
        inactive=Style(bg="#161b22"),
        hover=Style(bg="#30363d"),
    ),
)

List(items, theme=theme)                  # rows follow the theme
List(items, styles=Styles(rows=replace(   # one widget differs
    DEFAULT_THEME.rows, base=Style(bg="#0d1117")
)))
```

`Tabs` stays out: its active tab is a label idiom (accent plus underline),
not a row band.

## Disabled and read-only

Two different states, with two different mechanisms:

- **Disabled** is an attribute (`disabled: bool`) on interactive controls,
  plus optional `disabled_items` for individual rows. A disabled control
  refuses `click`, `activate`, `move`, `select` and `toggle`; a disabled row
  is skipped by movement and paints `rows.disabled` (which defaults to
  `NONE`, or `text.faint` for a control). The widget still renders. Override
  the group with `styles=Styles(rows=..., text=...)`; there is no
  `disabled_style=`.
- **Read-only** is an attribute on text fields (`Input.read_only`,
  `Editor.read_only`). A read-only field ignores every routed event without
  touching the buffer; programmatic edits and assigning `text` remain the
  host's.

`CheckboxGroup` follows `MultiSelect`'s rule: a disabled row cannot be
marked. `Tree` supports a disabled control and disabled nodes, but no marks.

## Containers and child_at

`Container.child_at(row, col)` is one method, and it reads the container's
**last render**:

```python
class Stack:
    def __init__(self, children):
        self.children = list(children)
        self._spans = []

    def render(self, width):
        self._spans = []
        rows = []
        for child in self.children:
            child_rows = child.render(width)
            self._spans.append((child, len(rows), len(child_rows)))
            rows.extend(child_rows)
        return rows

    def child_at(self, row, col):
        for child, first, height in reversed(self._spans):
            if first <= row < first + height:
                return child, row - first, col
        return None
```

Rules the built-in containers follow:

- geometry comes from the last render; a container that has never rendered
  declines every cell;
- coordinates are translated into the child's own cell;
- nothing else is proxied. `handle`, `move`, `activate` and `focused` stay
  the leaf's, so a `Padding(Editor)` needs the editor in the focus manager
  for keys while its clicks still descend.

`Pointer` and `FocusManager.click` run `descend` first, so a click through a
wrapper lands on the leaf. `Hit.leaf` / `hit_leaf` expose the same walk.

## Focus, pointer and selection

`App` mounts the three tiers by default. They are still ordinary objects in
`motui.app`: construct one against `app.tui` when you want a second ring, or
drive `TUI` directly and mount them yourself.

### FocusManager

```python
FocusManager(targets=(), *, wrap=True, on_change=None)
focus(target) -> bool
focus_next(delta=1) -> bool
focus_previous() -> bool
add(target) / remove(target) -> bool
handle(event) -> bool
click(hit) -> bool
push_trap(targets) / pop_trap()
focused -> Component | None
targets -> tuple[Component, ...]
```

- The constructor focuses nothing and writes no target's flag.
- A target need not be `Focusable`: a `Dialog` is a legal route target,
  focused by identity.
- `handle` dispatches to the focused target first; unconsumed arrows map to
  `move(-1)` / `move(1)` (or `move_up`/`move_left`/`move_down`/`move_right`
  for text fields), and `enter` maps to `activate()`.
- `click` descends to the leaf, dispatches `click`, focuses a registered
  target on the first click and activates it on the second.
- `push_trap` / `pop_trap` save and restore the target set; traps nest.

`App.add` registers interactive widgets automatically; `App.focus`,
`App.focus_next`, `App.focus_previous` and `App.set_focus_targets` are the
App surface. `App` also handles `tab`/`s-tab`. A custom `TUI` host must mount
the manager and route the cycle key itself. Widget focus and pane focus are
separate.

### Pointer

```python
Pointer(tui, *, ring=None, hover=True)
handle(event) -> bool
clear()
detach()
position -> tuple[int, int] | None
hovered -> Component | None
```

`Pointer` writes `hover` and optional `hover_at` on the leaf under the
pointer. A press is remembered, a drag drops it (the gesture's reports), and
a release on the same cell dispatches a stationary click. With a mounted
ring the click runs the ring's policy; without one it dispatches the deepest
`Clickable` leaf itself. Its `True` is a repaint cue, never a consumption
claim. Hover requires `hover=True` on the screen (DECSET 1003); `App` passes
it by default.

### SelectionGesture

```python
SelectionGesture(tui, *, on_end=copy_on_select, scroll_rows=2,
                 scroll_tick=0.05, double_click_seconds=0.35)
handle(event) -> bool
detach()
```

The left button anchors and extends a document-space range; release
finalizes and calls `on_end`. Repeated presses select the word, then the
visible line. A drag at an edge row arms an auto-scroll ticker on
`tui.every`. A click clears the selection and never fires `on_end`.
`copy_on_select` extracts the range at `tui.screen.width` and calls
`tui.copy_to_clipboard`. `App(on_selection=...)` replaces the default
`on_end` and mounts the gesture.

### Find

```python
Find(tui, *, theme=None, glyphs=GLYPHS)
open(); close(); detach()
handle(event) -> bool
is_open; query; matches; index
set_theme(theme)
```

A query `Input` row plus matches in the focused pane's document. Opening
starts from an empty query; the prompt is `find ❯ ` built from
`glyphs.prompt`. Typing or stepping reveals the current match; `enter`/`down`
and `up` wrap. The overlay marks every match with `theme.text.selection` and
the current one with `theme.surfaces.hover`; the query row's band is
`theme.overlays.toast` and its counter `theme.text.faint`. `App.find()` opens
the App-owned instance ahead of the gestures and host keys.

### Scrollbar

```python
Scrollbar(tui, *, pane=None, size=1, min_thumb=1, style=None,
          thumb_style=None, glyphs=GLYPHS, track=None, thumb=None,
          theme=None, scroll_tick=0.05)
handle(event) -> bool
set_theme(theme)
detach()
```

A pane-chrome controller in `motui.app`. Constructing one registers
right-edge chrome on a pane (one budgeted column); `detach()` unregisters
it. `track=None` and `thumb=None` mean `glyphs.bar_empty` /
`glyphs.bar_full`; explicit strings still override the cells (an empty
string paints the column's budget empty). The thumb reads the pane's
`ScrollState` (`offset` over `total_rows`) through the one shared
`ScrollState.thumb` formula. A left press in the strip is consumed for
grab-and-drag or paging; every other event passes through. A wheel over the
pane is routed by `App` to the nearest `Scrollable` first, so the pane bar
sees presses and drags, not wheel reports.

### Toasts

```python
Toasts(tui, *, ttl=4.0, max_shown=3, corner="top-right", style=None, theme=None)
show(content, *, style=None, ttl=None)
handle(event) -> bool
set_theme(theme)
detach()
```

`show` takes a string or any component. Past `max_shown`, the oldest toast
is evicted. Expiry rides `tui.every` and `tui.clock()`. The band is
`theme.overlays.toast`. A press inside a toast's rectangle dismisses it;
`detach()` unregisters and cancels the ticker. `App.toast(text)` uses the
mounted stack.

### Tooltip

```python
Tooltip(tui, pointer, *, theme=None)
set_theme(theme)
detach()
```

The narrowest overlay: no input and no ticker. It paints the hovered leaf's
`hint` as one `theme.overlays.tooltip` band beside the pointer, clamped into
the frame. A leaf without a hint, or a pointer that never moved, hands the
layout back unchanged.

### Stats

```python
Stats(tui, *, pointer=None, theme=None)
handle(event) -> bool
events; last; fps
set_theme(theme); detach()
```

A developer readout in the top-right corner: `painter.frames`, the frame
rate over a window of at least a second off `tui.clock()`, the event count
and last name, and the hovered leaf. The band is `theme.overlays.tooltip`.
`handle` consumes nothing; its `True` is a repaint cue. A host mounts it
with `App.mount(stats, dispatch=False)` and feeds it events itself, or routes
it beside the other tiers, never in a consume chain.

## Composition

### Command and CommandRegistry

```python
Command(name, description="", handler=None, keys=(), enabled=True)
CommandRegistry(commands=())

registry.add(command)              # duplicate names raise ValueError
registry.remove(name); registry.get(name)   # KeyError when missing
registry.match(query, *, include_disabled=False) -> list[Command]
registry.by_key(key) -> Command | None
registry.invoke(name, *args, **kwargs) -> object | None
registry.options() -> list[Option]         # the palette bridge
```

The registry keeps insertion order everywhere. `match` is a
case-insensitive substring search over name and description. `invoke`
returns `None` for a disabled or handler-less command. The registry is not
on the package root; it lives in `motui.app`.

### Clipboard

```python
Clipboard            # protocol: copy(text) -> bool
ScreenClipboard(screen)
MemoryClipboard()
```

`ScreenClipboard` delegates to the screen's OSC 52 write and its flush.
`MemoryClipboard` records the last text in `.text` and is the headless
backend. `True` is best-effort: a terminal may refuse application clipboard
writes. The real hook is `SelectionGesture(on_end=...)`. Both live in
`motui.core`.

## Theme, ColorPalette, glyphs and keymaps

`Theme` is ten frozen role groups; every field is a `Style`:

| Group | Fields | Used for |
|---|---|---|
| `text` | `base`, `muted`, `faint`, `inverse`, `disabled`, `caret`, `selection` | plain, quiet, inverse, caret and selected text |
| `surfaces` | `base`, `raised`, `hover`, `active`, `selected` | region and band backgrounds |
| `borders` | `base`, `grid`, `focus`, `danger` | panels, rules, table grids, emphasis |
| `controls` | `base`, `hover`, `focus`, `active`, `disabled` | button-like control bands |
| `rows` | `base`, `hover`, `active`, `inactive`, `selected`, `marked`, `disabled` | every vertical row widget |
| `status` | `success`, `warning`, `danger`, `info` | outcomes, `Notice`, `Diff` |
| `content` | `accent`, `link`, `code`, `inline_code`, `headings`, `marker`, `quote`, `strong`, `emphasis`, `strike` | Markdown, links, prompts |
| `chrome` | `divider`, `scrollbar`, `scrollbar_thumb` | dividers and scroll chrome |
| `overlays` | `scrim`, `toast`, `tooltip` | modal, toast and tooltip bands |
| `syntax` | `comment`, `keyword`, `string`, `number`, `builtin` | the syntax highlighter |

`Theme()` is the Ink & Signal dark theme and equals `DEFAULT_THEME` and
`Theme.dark()`. The other constructors are pure: `Theme.light()`,
`Theme.flat()`, `Theme.auto(env=None)` and
`Theme.from_palette(palette)`. `flat` keeps the dark palette but sets every
`surfaces.*` token to `NONE` and reads position through `rows.active`
(reverse), `rows.inactive` (dim), `rows.hover` (underline) and
`rows.selected` (reverse). `auto` reads `TERM_BACKGROUND`, then
`COLORFGBG`, and falls back to dark.

`RowStyles.band(...)` and `ControlStyles.band(...)` are the state
resolvers:

```python
theme.rows.band(active=True, hovered=False, focused=True, selected=False,
                marked=False, disabled=False)
# disabled > hovered > (active ? (focused ? active : inactive))
#          > selected > marked > base

theme.controls.band(hovered=False, focused=False, active=False, disabled=False)
# disabled > active > focused > hovered > base
```

Build a variant with `dataclasses.replace` at the group level, or override
one group for one widget with `Styles`:

```python
from dataclasses import replace

from motui import DEFAULT_THEME, List, Style, Styles

theme = replace(
    DEFAULT_THEME,
    content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff8800")),
    rows=replace(DEFAULT_THEME.rows, active=Style(bg="#264f78")),
)

List(items, theme=theme)
List(items, styles=Styles(rows=replace(DEFAULT_THEME.rows, base=Style(bg="#0d1117"))))
```

`Styles` has one optional field per group (`text`, `surfaces`, `borders`,
`controls`, `rows`, `status`, `content`, `chrome`, `overlays`, `syntax`); a
non-`None` field replaces the whole group and a `None` field inherits.
Widgets read it at render time, so `App.theme = theme` repaints mounted
widgets whose `theme is None`.

`ColorPalette` is the brand-colour authoring layer consumed by
`Theme.from_palette`. Its 18 fields are `ink`, `muted`, `faint`, `line`,
`surface`, `surface_raised`, `surface_hover`, `surface_active`,
`surface_inactive`, `accent`, `success`, `warning`, `danger`, `code`,
`heading`, `link`, `inline_code` and `marker`. `DARK_PALETTE` and
`LIGHT_PALETTE` are the shipped values; `ColorPalette()` equals
`DARK_PALETTE`.

```python
from motui import Style
from motui.core import ColorPalette, Theme
from motui.core.style import Color

brand = ColorPalette(
    accent=Style(fg=Color("#ff8800", ansi="yellow")),
    heading=Style(fg=Color("#ff8800", ansi="yellow")),
)
theme = Theme.from_palette(brand)
```

A `Color` is a `#rrggbb` string or `(r, g, b)` tuple plus an optional
`ansi` name from `FG_CODES`; the anchor is what a 16-color terminal paints
instead of quantizing the truecolor value. `None` means "quantize it".

**Glyphs** (`GLYPHS = Glyphs()`) are content, not style. Every
glyph-carrying component takes one `glyphs=` value:

| Field | Default | Used by |
|---|---|---|
| `prompt` | `❯` | `Input`, `Find`, `CommandPalette`, `ComboBox` |
| `cursor` | `→` | `List`, `Select`, `MultiSelect`, `Autocomplete`, `ContextMenu` |
| `rail` | `▌` | `NavList` |
| `fold_open` / `fold_closed` | `▾` / `▸` | `Tree`, `Collapsible` |
| `radio_off` / `radio_on` | `( )` / `(•)` | `RadioGroup` |
| `check_off` / `check_on` | `[ ]` / `[x]` | `Checkbox`, `CheckboxGroup`, `MultiSelect`, `List`, `Table`, `Markdown` |
| `check_indeterminate` | `[-]` | vocabulary only; no built-in consumer yet |
| `more_up` / `more_down` | `↑` / `↓` | `List` counter |
| `bar_full` / `bar_empty` | `█` / `░` | `ProgressBar`, `ScrollView`, `Scrollbar` |
| `slider_track` / `slider_thumb` | `━` / `●` | `Slider` |
| `horizontal_rule` | `─` | `Divider` |
| `vertical_rule` | `│` | `Tabs`, `MenuBar` separators |
| `quote` | `│` | `Markdown` block quotes |
| `separator` | ` · ` | `ShortcutBar` |
| `bullets` | `("•", "◦", "▪")` | `Markdown` lists |
| `notice_info` / `notice_success` / `notice_warn` / `notice_error` | `i` / `✓` / `!` / `×` | `Notice` |
| `diff_add` / `diff_remove` / `diff_context` | `+` / `-` / ` ` | `Diff` |
| `spinner` | ten braille frames | `Spinner` |
| `box` / `grid` | `Border.square()` | `Panel`, `Dialog` / `Table` |

Markdown's list nesting is capped at depth two, so `bullets[2]` is
vocabulary-only in the built-in rules.

`Border` is the 14-mark box style: `top_left`, `top`, `top_tee`,
`top_right`, `left`, `middle`, `cross`, `right`, `middle_left`,
`middle_right`, `bottom_left`, `bottom`, `bottom_tee`, `bottom_right`.
`Border.square()`, `rounded()`, `heavy()`, `double()`, `ascii()` and
`none()` are the shipped styles; `none()` paints spaces and keeps the
reserved geometry. `Panel`, `Dialog` and `Table` accept one explicitly.

`seat(glyph)` is glyph plus one space; `seat_width(glyph)` measures it;
`pair_seat(glyph, other)` pads a state pair to the wider member. `""` turns
a mark off and collapses its seat. Instance content overrides remain:
`Divider(char=)`, `Input(prompt=)`, `Scrollbar(track=/thumb=)`.

Keymaps are plain dicts from key name to editing method:

```python
from motui import Input
from motui.core import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, EDITOR_SUBMIT_KEYMAP

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]      # the host gets the event back
```

The derivation chain is `DEFAULT_INPUT_KEYMAP` -> `DEFAULT_EDITOR_KEYMAP`
(adds `enter` as `newline`) -> `EDITOR_SUBMIT_KEYMAP` (removes `enter`, binds
`c-j` as `newline`).

## Build your own

### A render-only component

```python
from motui import DEFAULT_THEME, Line, Segment
from motui.core.glyphs import GLYPHS


class Meter:
    """A labelled bar: one component, one render method."""

    def __init__(self, fraction: float, label: str = "", *, theme=None):
        self.fraction = min(1.0, max(0.0, fraction))
        self.label = label
        self.theme = theme or DEFAULT_THEME

    def render(self, width: int) -> list[Line]:
        lead = f"{self.label} " if self.label else ""
        track = max(0, width - Line.from_text(lead).width - 2)
        done = min(track, round(track * self.fraction)) if track else 0
        row = Line((
            Segment(lead),
            Segment("["),
            Segment(GLYPHS.bar_full * done, self.theme.status.success),
            Segment(GLYPHS.bar_empty * (track - done), self.theme.text.faint),
            Segment("]"),
        ))
        return [row.fit(width)]
```

Measure with `Line.width` / `visible_width`, never `len()`. Fit every row.
Read roles from the stored `theme`, never from a module-level style. Implement
`revision()` when the component holds mutable state.

### A clickable-through container

Implement `render` and `child_at` as in
[Containers and child_at](#containers-and-child_at). Record geometry during
render; translate the cell; proxy nothing else.

### A clickable inline span

```python
from motui import Line, Segment, Style
from motui.core import action_at


class Chips:
    """One row of clickable chips."""

    def __init__(self, chips):
        self.chips = list(chips)          # (label, action) pairs
        self.hover = False
        self._pending = None
        self._rows = []
        self._span = None

    def render(self, width):
        parts = []
        for label, action in self.chips:
            if parts:
                parts.append(Segment(" · "))
            parts.append(Segment(label, Style(underline=True), action=action))
        rows = [Line(parts).fit(width)]
        self._rows = rows
        if self._span is not None:
            row, start, end = self._span
            rows[row] = rows[row].merge_span(start, end, Style(reverse=True))
        return rows

    def hover_at(self, row, col):
        hit = action_at(self._rows[row], col) if 0 <= row < len(self._rows) else None
        span = None if hit is None else (row, hit[1], hit[2])
        changed = span != self._span
        self._span = span
        return changed

    def click(self, row, col):
        hit = action_at(self._rows[row], col) if 0 <= row < len(self._rows) else None
        if hit is None:
            return False
        self._pending = hit[0]
        return True

    def take_result(self):
        value, self._pending = self._pending, None
        return value
```

The hit test reads the last render's row table; `action_at` answers display
columns, left-closed and right-open. Merge the hover band into a copy so
clearing it restores the un-hovered bytes. A miss declines.

### A chrome

```python
from motui import Line
from motui.core.frame import Chrome


class Gutter:
    """A two-column line-number rail."""

    def __init__(self, style):
        self.style = style

    def chrome(self):
        return Chrome("left", 2, self._paint)

    def _paint(self, layout, length):
        first = layout.offset + 1
        rows = []
        for index in range(length):
            number = first + index
            if number > layout.total_rows:
                rows.append(Line.filled(2))
            else:
                rows.append(Line.from_text(f"{number:>2}"[-2:], self.style))
        return rows


tui.frame.pane("primary").add_chrome(Gutter(theme.text.faint).chrome())
```

A chrome is a pure function of the pane's last layout and the strip length.
`add_chrome` registers it; `remove_chrome` unregisters by identity; the
budget is negotiated at the next composition.

### An overlay

An overlay is any object with `paint(frame) -> ScreenLayout`. Register it
with `tui.frame.add_overlay(overlay, layer="overlay")` and unregister by
identity. Test membership before removing to keep `detach()` idempotent. The
driver's selection highlight and the shipped `Toasts`/`Tooltip`/`Stats` are
the reference shapes: read the composed layout, rewrite rows, hand the
layout back unchanged when there is nothing to paint.

## Testing

```python
from motui import KeyEvent, TUI
from motui.testing import ScriptedEvents, headless_tui, snapshot

tui = headless_tui(80, 24, script=[KeyEvent("a", "a"), KeyEvent("c-c")])
# ...drive the session...
assert "hello" in "\n".join(row.text for row in tui.rows)
print(tui.screen.output)      # every byte the session would have written
print(snapshot(tui))          # one stanza per block
```

- `HeadlessScreen` is live by construction and records every byte in
  `output`; it interprets no escapes.
- `ScriptedEvents` replays a fixed event list, then reports EOF forever. A
  `None` item is a one-shot EOF.
- `headless_tui(width, height, *, script=None, keys=None)` wires a real
  `TUI`: recording screen, scripted source, `interactive=False`. For the
  high-level App, pass the same pieces to its constructor:
  `App(screen=HeadlessScreen(...), keys=ScriptedEvents(...), interactive=False)`.
- `snapshot(tui)` renders the document as structured plain text, one stanza
  per block with its id and pin (`[id]`, `[id | top]`, `[id | bottom]`).
- Nothing sleeps. Time enters through `tui.clock()`; a test overrides it or
  calls `tui.tick(now)`.

Golden frames pin what a user sees: `tests/golden/topics/*.txt`, one frame
per demo topic, checked and re-recorded by `tools/golden.py`.
