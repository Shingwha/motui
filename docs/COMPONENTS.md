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

Blocks add a lifecycle and a row cache on top. `Block.rows(width)` is the
one cached read; `Block.render(width)` is the uncached door. A sealed block
caches by width; an open block caches only when its component implements
`Revisioned` and returns a non-`None` snapshot. See
[documents and caching](DESIGN.md#documents-blocks-and-caching).

## Controller protocols

Interaction is a set of small protocols, not a base class:

| Protocol | Method / attribute | Contract |
|---|---|---|
| `Controller` | `handle(event) -> bool` | `True` means **consumed**; `False` hands the event back |
| `Resultful` | `take_result() -> object \| None` | read once and clear; `None` when nothing is pending |
| `Clickable` | `click(row, col) -> bool` | `row`/`col` are in the component's own last render |
| `Activable` | `activate() -> bool` | the `enter` gesture |
| `Focusable` | `focused: bool` | the one flag the focus tier writes |
| `Hoverable` | `hover: bool`, optional `hover_at(row, col) -> bool` | the pointer tier writes it; `hover_at` marks a row and answers whether the render changed |
| `Container` | `child_at(row, col) -> (Component, row, col) \| None` | route a cell to a child, from the last render |
| `Revisioned` | `revision() -> object` | a value snapshot of every mutable row input |

A component never learns that a manager exists. A container routes
coordinates and nothing else: it does not proxy `handle`, `move`,
`activate` or `focused`.

## The driver in call order

```python
tui.add(component, id="x", pin=None, pane=None)  # append a block
tui.get("x"); tui.remove("x")                    # address by id
tui.system("line")                               # a muted system block
tui.pane("primary").document                     # explicit pane scope
tui.split("vertical", ratios=(2, 1))             # divide the focused pane
tui.dock(Viewport(footer), edge="bottom")        # frame-level footer
tui.reveal("b3", 12)                             # bring an address on screen
tui.visible_range()                              # screen rows of the body
tui.refresh(); tui.paint()                       # mark dirty / paint now
event = await tui.read_event()                   # next event; scroll keys absorbed
tui.hit(x, y); tui.hit_leaf(x, y)                # cell -> block / deepest leaf
tui.exit()                                       # end the run
```

`add` targets the focused pane unless `pane=` is given. Block ids are unique
across the whole frame. `read_event` intercepts `tui.scroll_keys`
(`page_up`/`page_down`/`wheel_up`/`wheel_down` by default); rebind or delete
an entry to receive the event yourself.

## Text

### Text

- **Purpose:** plain, wrapped text; action spans are clickable and hoverable.
- **Signature:** `Text(text="", *, style=None, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`
- **Result:** `take_result() -> str | None` (the `action` payload under a click)
- **Protocols:** Component, Revisioned, Clickable, Hoverable
- **Notes:** `text` is mutable for streaming. Each logical line is
  word-wrapped; `hover_at` marks the span under the pointer. A subclass can
  return its own `Line` values and inherit the hit testing unchanged.

### Markdown

- **Purpose:** a streaming-safe Markdown document rendered through rule
  registries.
- **Signature:** `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, glyphs=GLYPHS, gap=1, divider_max_width=80, max_width=None)`
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
  `text` after reading it.

### Diff

- **Purpose:** a line-level unified diff of two texts.
- **Signature:** `Diff(before, after, *, context=3, numbers=False, glyphs=GLYPHS, theme=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** the walk and hunks are computed once at construction; assigning
  `before`, `after`, `context`, `numbers`, `glyphs` or `theme` rebuilds them.
  Rows are `@@` headers, `glyphs.diff_add` / `diff_remove` /
  `diff_context` lines and `… N lines` elisions. Display only.

### Notice

- **Purpose:** one message row with a level glyph.
- **Signature:** `Notice(text, *, level="info", glyphs=GLYPHS, theme=None)`
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
- **Signature:** `Input(text="", *, prompt=None, placeholder="", mask="", style=None, prompt_style=None, caret_style=None, glyphs=GLYPHS, focused=True, theme=None, keymap=None, read_only=False)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`, `home()`, `end()`, `undo()`, `redo()`, `cursor_position(width)`
- **Result:** none (`take_result` is not a field concept)
- **Protocols:** Component, Revisioned, Controller, Clickable, Focusable
- **Notes:** editing keys come from the keymap; `enter` is unbound by
  default. A paste is folded into one line (newline runs become spaces).
  `prompt=None` means `seat(glyphs.prompt)` (`❯ `); `prompt=""` removes the
  prompt and its seat. `read_only=True` refuses every routed event without
  touching the buffer. `mask` is display-only; `.text` stays plain.

### Editor

- **Purpose:** a multi-line editable buffer with a block cursor.
- **Signature:** `Editor(text="", *, placeholder="", mask="", style=None, caret_style=None, theme=None, keymap=None, focused=True, max_rows=None, read_only=False)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`, `home()`, `end()`, `undo()`, `redo()`, `cursor_position(width)`
- **Result:** none
- **Protocols:** Component, Revisioned, Controller, Clickable, Focusable
- **Notes:** a paste keeps its newlines. `max_rows` slides a window over the
  cursor. `EDITOR_SUBMIT_KEYMAP` leaves `enter` to the host and binds `c-j`
  to `newline` instead. `read_only` behaves as on `Input`.

### Checkbox

- **Purpose:** one-row checked/unchecked toggle.
- **Signature:** `Checkbox(label, *, checked=False, style=None, hover_style=None, focus_style=None, disabled_style=None, glyphs=GLYPHS, disabled=False, theme=None, focused=False)`
- **Verbs:** `click(row, col) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> bool | None` (the new `checked` value)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** the mark is `glyphs.check_on` / `glyphs.check_off`, drawn in
  `content.accent`; the label uses `text.base`. The empty seat collapses when
  a mark is `""`. Carries the tooltip's `hint` protocol.

### RadioGroup

- **Purpose:** a single-choice group with `(•)` / `( )` markers.
- **Signature:** `RadioGroup(labels, *, index=0, glyphs=GLYPHS, label_style=None, active_style=None, hover_style=None, ground_style=None, disabled=False, disabled_items=(), disabled_style=None, theme=None, focused=False)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `home()`, `end()`,
  `activate() -> bool`, `toggle() -> bool`
- **Result:** `take_result() -> object | None` (the selected label or payload)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** rows take plain labels or `Option` values; a non-empty
  description raises at construction. `glyphs.radio_on` / `glyphs.radio_off`
  draw the mark in `content.accent`; labels use `text.base`; rows resolve
  through `theme.rows.band(...)`. The cursor steps clamped. A step, a click
  and `activate` all leave the new pick pending.

### CheckboxGroup

- **Purpose:** a multiple-choice group over a mark set.
- **Signature:** `CheckboxGroup(labels, *, marked=(), index=0, glyphs=GLYPHS, label_style=None, active_style=None, hover_style=None, ground_style=None, disabled=False, disabled_items=(), disabled_style=None, theme=None, focused=False)`
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

- **Purpose:** the vertical option list every menu and choice preset builds
  on.
- **Signature:** `Select(options=(), *, title="", max_rows=8, wrap=True, glyphs=GLYPHS, commit=False, multi=False, marked=(), window=False, focused=True, label_style=None, cursor_text_style=None, description_style=None, title_style=None, ground_style=None, disabled=False, disabled_items=(), disabled_style=None, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `home()`, `end()`,
  `activate() -> bool`, `toggle() -> bool`
- **Result:** `take_result() -> object | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** five knobs cover the family: `wrap` (cycle or clamp), `window`
  (top-stick or centered), `commit` (the cursor is the choice) and `multi`
  (the marks are the selection). `glyphs.cursor` marks the cursor and
  `glyphs.check_on/off` the multi-selection; descriptions use `text.muted`.
  A description column is measured over the whole option universe. A list
  longer than `max_rows` gets a window and an `(i/n)` counter.

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
- **Signature:** `ComboBox(options=(), *, text="", max_rows=8, theme=None, max_drop_rows=6, glyphs=GLYPHS)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`, `open()`,
  `close()`, `child_at(row, col)`
- **Result:** `take_result() -> object | None` (the picked option's value)
- **Protocols:** Component, Revisioned, Controller, Clickable, Container, Resultful
- **Notes:** while open, `down`/`up` move the list, `enter` takes the
  highlighted value and writes its label back into the field, `escape`
  closes with nothing. Every other event goes to the field. A paste is
  never read as a key. The dropdown is painted by a host-mounted `Modal`;
  route `combo.handle` before `modal.handle` and keep both open states in
  step.

### Autocomplete

- **Purpose:** a `Select` whose rows are the matches of a query.
- **Signature:** `Autocomplete(options=(), *, max_rows=8, wrap=True, glyphs=GLYPHS, label_style=None, cursor_text_style=None, description_style=None, theme=None)`
- **Verbs:** `set_query(text)`, plus the inherited cursor and activation verbs
- **Result:** `take_result() -> object | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** prefix matches come first, then substring matches,
  case-insensitive; an empty query matches all. The description column is
  measured over the whole universe so it never jumps while filtering.

### Slider

- **Purpose:** a one-row stepped integer control.
- **Signature:** `Slider(value=0, *, minimum=0, maximum=10, step=1, filled_style=None, empty_style=None, hover_style=None, focus_style=None, disabled_style=None, glyphs=GLYPHS, disabled=False, theme=None, focused=False)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> int | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** the value snaps to the `step` grid; assigning `minimum`,
  `maximum` or `step` re-clamps and re-snaps. The track repeats
  `glyphs.slider_track`, the thumb is `glyphs.slider_thumb` and the value
  text uses `text.muted`. A click maps the rendered track column to the
  nearest grid point; `activate` confirms the value.

### Form

- **Purpose:** labelled fields with focus, navigation, validation and a
  one-shot submission.
- **Signature:** `Form(fields, *, gap=0, index=0, on_submit=None, theme=None)`
- **Verbs:** `handle(event) -> bool`, `move(delta) -> bool`, `focus(target) -> bool`, `activate() -> bool`, `child_at(row, col)`
- **Result:** `take_result() -> dict[str, object] | None`
- **Protocols:** Component, Revisioned, Controller, Container, Activable
- **Notes:** the focused field's `handle` runs first, then `tab`/`down` and
  `s-tab`/`up` step, then `enter` validates every field. Errors land back in
  each `Field.error`. A clean submit leaves `{name: value}` pending and
  calls `on_submit` once. Values come from `Field.value()` or the
  component's first `value` / `text` / `checked` / `selected` / `marked`;
  `take_result` never consumes a field's own result.

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
- **Signature:** `List(items=(), *, window=8, ground_style=None, focused=False, prefix_jump=True, glyphs=GLYPHS, disabled=False, disabled_items=(), disabled_style=None, theme=None)`
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
- **Signature:** `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, active_style=None, ground_style=None, glyphs=GLYPHS, grid=None, aligns=None, focused=True, disabled=False, disabled_items=(), disabled_style=None, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `activate() -> bool`, `toggle() -> bool`,
  `sort_by(col, *, reverse=False) -> bool`, `set_widths(widths)`,
  `header_line(width) -> Line | None`
- **Result:** `take_result() -> int | None` (the activated data-row index)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** there is no cursor until a host sets `index`. `grid` is a
  `Border` (default `glyphs.grid`) and its lines use `borders.grid`; the
  header uses `text.muted` and marks use `glyphs.check_on/off`. `sort_by` is
  the host's reorder by a column's rendered text (stable); the cursor, marks
  and pending result follow the record. `set_widths` pins per-column
  budgets; `header_line` returns the header row alone for a host that pins
  it.

### Tree

- **Purpose:** an indented, collapsible node list.
- **Signature:** `Tree(root_nodes, *, indent=2, glyphs=GLYPHS, guide_style=None, label_style=None, active_style=None, ground_style=None, focused=True, disabled=False, disabled_style=None, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `activate() -> bool`, `filter(query) -> bool`,
  `jump(char) -> bool`
- **Result:** none (`selected` reads the node)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** only expanded nodes render; leaves keep a blank indicator
  column. The fold marks are `glyphs.fold_open` / `glyphs.fold_closed`.
  `filter` prunes to matching labels plus ancestors and draws those
  chains open without rewriting the user's `expanded` flags. `jump` is
  wrapping type-ahead over visible rows.

### TreeNode

- **Purpose:** one tree node: label, children and state.
- **Signature:** `TreeNode(label, children=(), *, expanded=False, disabled=False)`
- **Verbs:** none
- **Result:** none
- **Protocols:** plain value object
- **Notes:** `expanded` is a mutable attribute; `activate` flips it.

### Tabs

- **Purpose:** a horizontal content strip with one underlined active label.
- **Signature:** `Tabs(tabs, *, index=0, active_style=None, inactive_style=None, hover_style=None, disabled_style=None, glyphs=GLYPHS, divider_style=None, indicator_style=None, disabled_items=(), disabled=False, focused=True, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`
- **Result:** none (`index` reads the selection)
- **Protocols:** Component, Revisioned, Clickable, Hoverable, Focusable
- **Notes:** the strip is one row. Movement clamps and steps over disabled
  indices. The separator is `glyphs.vertical_rule` with one space on each
  side. An unfocused strip drops the indicator's hue from accent to muted;
  the underline remains.

### NavList

- **Purpose:** a vertical navigation rail with a bar indicator.
- **Signature:** `NavList(items, *, groups=(), group_style=None, index=0, disabled_items=(), disabled=False, glyphs=GLYPHS, bar_space=None, active_style=None, inactive_style=None, hover_style=None, disabled_style=None, bar_style=None, bar_active_style=None, ground_style=None, focused=True, theme=None)`
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
- **Signature:** `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, glyphs=GLYPHS, theme=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** `fraction` re-clamps to `[0, 1]` on assignment. The filled
  cells are `glyphs.bar_full` and the rest `glyphs.bar_empty`. The track
  length follows `render(width)` unless `width_chars` pins it.

### Spinner

- **Purpose:** a frame-cycling activity indicator.
- **Signature:** `Spinner(text="", *, frames=None, style=None, glyphs=GLYPHS, theme=None)`
- **Verbs:** `advance()`
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** the driver decides when to call `advance()`; `revision()` covers
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
- **Signature:** `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)`
- **Verbs:** `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Container
- **Notes:** `fill_style` paints the blank areas and merges underneath the
  child's own segments. The fill is never themed. Insets are clipped to the
  painting width.

### Panel

- **Purpose:** a child inside a single-line box, or a borderless filled panel.
- **Signature:** `Panel(child, *, title="", style=None, frame=True, border=None, glyphs=GLYPHS, theme=None)`
- **Verbs:** `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Container
- **Notes:** with `frame=False` there is no border or title, the child gets
  `width - 2`, and an explicit `style` becomes the panel's ground. `border`
  is a `Border` value (default `glyphs.box`): `Border.square()`,
  `rounded()`, `heavy()`, `double()`, `ascii()` or `none()`. A titled box
  embeds the title in its top edge when it fits.

### Divider

- **Purpose:** a horizontal rule built from one repeated character.
- **Signature:** `Divider(*, char=None, style=None, label="", label_style=None, glyphs=GLYPHS, theme=None, max_width=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** `char=None` means `glyphs.horizontal_rule`; an explicit `char`
  overrides the glyph for this instance. `label` renders as
  `── label ────` across the width; an over-wide label is ellipsized.
  `style` falls back to `borders.base`, `label_style` to `text.muted`.
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
- **Signature:** `Collapsible(title, body, *, open=True, title_style=None, hover_style=None, focus_style=None, disabled_style=None, glyphs=GLYPHS, disabled=False, theme=None, focused=False)`
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
- **Signature:** `ScrollView(child, *, height=None, offset=0, scrollbar=False, glyphs=GLYPHS, theme=None)`
- **Verbs:** `handle(event) -> bool`, `scroll_up(n)`, `scroll_down(n)`,
  `scroll_to(offset)`, `reveal(row)`, `child_at(row, col)`
- **Result:** none
- **Protocols:** Component, Revisioned, Controller, Container
- **Notes:** `height=None` shows every row and makes scrolling a no-op.
  `handle` owns the arrows, page keys, home/end and the vertical wheel, and
  answers `True` only on a real move. `scrollbar=True` reserves the last
  column and paints a proportional thumb with `glyphs.bar_empty` /
  `glyphs.bar_full`. A visible cell maps to child row `offset + row`.

### Delegate

- **Purpose:** a one-child identity wrapper that answers every protocol
  surface.
- **Signature:** `Delegate(child)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `child_at(row, col)`, `revision()`
- **Result:** none
- **Protocols:** Component, Revisioned, Clickable, Hoverable, Container
- **Notes:** `render` returns the child's rows verbatim. A child without
  `revision` answers `None`; a child without `click`/`hover_at` answers
  `False`. It never proxies `handle`, `move`, `activate` or `focused`; reach
  `delegate.child` for those.

## Actions

### Button

- **Purpose:** the smallest interactive unit: one row of action.
- **Signature:** `Button(label, *, style=None, hover_style=None, focus_style=None, disabled_style=None, disabled=False, theme=None, focused=False)`
- **Verbs:** `click(row, col) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> bool | None` (`True` after a successful activation)
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** any cell of the row is the control. Disabled refuses both doors
  and paints its quiet band. Carries the tooltip's `hint`.

### Link

- **Purpose:** one row of clickable text in the theme's link style.
- **Signature:** `Link(text, *, style=None, hover_style=None, focus_style=None, disabled_style=None, disabled=False, theme=None, focused=False)`
- **Verbs:** `click(row, col) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> bool | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Focusable, Hoverable
- **Notes:** same activation contract as `Button`, rendered in the link band.
  Carries the tooltip's `hint`.

### MenuBar

- **Purpose:** a one-row horizontal menu with one active label.
- **Signature:** `MenuBar(items, *, index=0, active_style=None, inactive_style=None, hover_style=None, disabled_style=None, glyphs=GLYPHS, divider_style=None, disabled_items=(), disabled=False, focused=True, theme=None)`
- **Verbs:** `click(row, col) -> bool`, `hover_at(row, col) -> bool`,
  `move(delta) -> bool`, `select(index) -> bool`, `activate() -> bool`
- **Result:** `take_result() -> str | None` (the active label)
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** movement clamps and steps over disabled labels. Separators are
  `glyphs.vertical_rule` with one space on each side (the component owns the
  padding); the divider style falls back to `chrome.divider`. `click` and
  `hover_at` resolve cells against the last render's span table, so padding,
  dividers and a truncating ellipsis carry no label. The active label is the
  selection, not a focus band.

### ContextMenu

- **Purpose:** the `Select` preset for a desktop context menu.
- **Signature:** `ContextMenu(options=(), *, title="", max_rows=8, glyphs=GLYPHS, **kwargs)`
- **Verbs:** inherited `Select` verbs (`click`, `hover_at`, `move`,
  `select`, `home`, `end`, `activate`, `toggle`)
- **Result:** `take_result() -> object | None`
- **Protocols:** Component, Revisioned, Clickable, Activable, Hoverable, Focusable
- **Notes:** `commit=False`, `wrap=True`, `window=False`; the cursor is
  `glyphs.cursor`. It neither opens nor positions itself: mount it with
  `Modal(tui, menu, anchor=(y, x))` at the click cell and route the pointer
  through the modal. `activatable` options settle on `activate()`.

### ShortcutBar

- **Purpose:** one row of key/label hints.
- **Signature:** `ShortcutBar(items, *, glyphs=GLYPHS, key_style=None, label_style=None, theme=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** display-only chrome; no interaction and no result. Entries are
  joined by `glyphs.separator` (` · ` by default). An over-wide bar truncates
  with an ellipsis.

### StatusLine

- **Purpose:** a dim two-sided status row.
- **Signature:** `StatusLine(*, left=(), right=(), theme=None, gap_style=None)`
- **Verbs:** none
- **Result:** none
- **Protocols:** Component, Revisioned
- **Notes:** left text at column 0, right text at the far edge, a computed
  gutter between. `left` and `right` accept `str` or `(str, Style)` entries
  and are copied at construction. Display-only.

## Overlays

### Dialog

- **Purpose:** a resolved box with a body and a button row: the modal's pure
  payload.
- **Signature:** `Dialog(title, body, buttons, *, danger=False, width=None, align="center", border=None, border_style=None, title_style=None, shade=True, frame=True, glyphs=GLYPHS, theme=None)`
- **Verbs:** `handle(event) -> bool`, `click(row, col) -> bool`,
  `child_at(row, col)`
- **Result:** `take_result() -> object | None` (the taken button's value)
- **Protocols:** Component, Revisioned, Controller, Clickable, Container, Resultful
- **Notes:** `escape` cancels, `enter` takes the focused button's value, and
  tab/arrows walk the row clamped. `border` is a `Border` value (default
  `glyphs.box`); `danger=True` uses `borders.danger` and opens on the last
  non-dangerous button. `frame=False` drops the box and title, keeps the
  body and button row, and uses `width - 2`. `focused_button` reads the
  button the keys act on (deliberately not named `focused`).

### ButtonSpec

- **Purpose:** one dialog button value.
- **Signature:** `ButtonSpec(label, value=None, style=None, hover_style=None, focus_style=None, danger=False)`
- **Verbs:** none
- **Result:** none (the owning `Dialog` returns `value`)
- **Protocols:** plain value object
- **Notes:** `danger=True` renders in the error band but stays enabled; the
  rule is "not the default focus", never "disabled".

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
- **Signature:** `prompt_dialog(title, *, placeholder="", mask="", confirm_text="OK", cancel_text="Cancel", style=None, danger=False, frame=True, glyphs=GLYPHS, theme=None) -> Dialog`
- **Verbs:** see `Dialog`
- **Result:** through the returned `Dialog`'s `take_result()`; the field text
  is `dialog.body.text`
- **Protocols:** factory function
- **Notes:** the body is a single-line `Input`. The field binds no `enter`,
  so the return key falls through to the button row. `style` is the field's
  band; `mask` is forwarded verbatim.

### Modal

- **Purpose:** the blocking controller that paints any panel over a scrimmed
  frame.
- **Signature:** `Modal(tui, dialog, *, anchor=None, scrim=True, scrim_style=None, dismiss_on_click_outside=True, theme=None, focus=None)`
- **Verbs:** `open()`, `close(value=None)`, `handle(event) -> bool`,
  `take_result() -> object | None`, `detach()`, `paint(frame)`
- **Result:** `take_result() -> object | None` (read once; `None` is a legal
  decision)
- **Protocols:** controller, not a Component
- **Notes:** constructed mounted; `detach()` unregisters, closes, clears the
  result and pops a focus trap. While open it consumes everything: the
  panel's keys first, a panel `body` ahead of the panel's own `handle`
  (body-first), a press inside is the panel's click, a press outside
  dismisses. `handle` for the host's quit gesture must run **before** the
  modal. A closed modal paints nothing.

### Palette

- **Purpose:** a self-contained command palette: query row over a filtered
  command list, in a modal.
- **Signature:** `Palette(tui, commands, *, theme=None, max_rows=8, glyphs=GLYPHS, focus=None)`
- **Verbs:** `open()`, `close()`, `handle(event) -> bool`,
  `take_result() -> object | None`, `detach()`, `render(width)`, `is_open`
- **Result:** `take_result() -> object | None`
- **Protocols:** controller and Component (it renders zero rows while closed)
- **Notes:** `up`/`down` move the list, `enter` leaves the highlighted
  command's value pending, `escape` closes with nothing. Every other event
  routes through the query `Input` and re-filters the list; the query prompt
  comes from `glyphs.prompt`. Opening resets the query and the list. This
  controller is not the brand-color `Palette` from `motui.kernel`.

## The row-band contract

Every vertical row widget (`List`, `Tree`, `Table`, `NavList`, `Select`,
`Autocomplete`, `RadioGroup`, `CheckboxGroup`) resolves its band through
`theme.rows.band(...)`; there is no separate band value to thread.
Precedence:

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
(`Button`, `Checkbox`, `Collapsible`, `Slider`, ...) resolve through
`theme.controls.band(...)` with `disabled > active > focused > hovered >
base`.

A row is its text-styled segments, then `fit(width).fill(fitted.width, band)`:
the band rests underneath the text and hugs the row's own cells. A `NONE`
band paints nothing. A full-surface band is the host's container's job:
wrap the widget in `Padding(fill_style=...)` or
`Panel(frame=False, style=...)`.

```python
from dataclasses import replace

from motui import DEFAULT_THEME, List, Style

theme = replace(
    DEFAULT_THEME,
    rows=replace(
        DEFAULT_THEME.rows,
        active=Style(bg="#264f78"),
        inactive=Style(bg="#161b22"),
        hover=Style(bg="#30363d"),
    ),
)

List(items, theme=theme)                              # rows follow the theme
List(items, ground_style=Style(bg="#0d1117"), theme=theme)  # one widget differs
```

`Tabs` stays out: its active tab is a label idiom (accent plus underline),
not a row band.

## Disabled and read-only

Two different states, with two different mechanisms:

- **Disabled** is an attribute (`disabled: bool`) on interactive controls,
  plus optional `disabled_items` for individual rows. A disabled control
  refuses `click`, `activate`, `move`, `select` and `toggle`; a disabled row
  is skipped by movement and paints `disabled_style` (`rows.disabled`, which
  defaults to `NONE`, or `text.faint` for a control). The widget still
  renders.
- **Read-only** is an attribute on text fields (`Input.read_only`,
  `Editor.read_only`). A read-only field ignores every routed event without
  touching the buffer; programmatic edits and assigning `text` remain the
  host's.

`CheckboxGroup` follows `Select`'s multi rule: a disabled row cannot be
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

The host owns the cycle key (`tab` -> `focus_next`) and pane focus
(`tui.focus_policy`). Widget focus and pane focus are separate.

### Pointer

```python
Pointer(tui, *, ring=None, hover=True)
handle(event) -> bool
clear()
position -> tuple[int, int] | None
hovered -> Component | None
```

`Pointer` writes `hover` and optional `hover_at` on the leaf under the
pointer. A press is remembered, a drag drops it (the gesture's reports), and
a release on the same cell dispatches a stationary click. With a mounted
ring the click runs the ring's policy; without one it dispatches the deepest
`Clickable` leaf itself. Its `True` is a repaint cue, never a consumption
claim. Hover requires `TUI(hover=True)` (DECSET 1003).

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
`tui.copy_to_clipboard`.

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
`theme.overlays.toast` and its counter `theme.text.faint`. Route the open
tier before the gestures and the host's keys.

### Scrollbar

```python
Scrollbar(tui, *, pane=None, size=1, min_thumb=1, style=None,
          thumb_style=None, glyphs=GLYPHS, track=None, thumb=None,
          theme=None, scroll_tick=0.05)
handle(event) -> bool
detach()
```

Constructing one registers right-edge chrome on a pane (one budgeted
column); `detach()` unregisters it. `track=None` and `thumb=None` mean
`glyphs.bar_empty` / `glyphs.bar_full`; explicit strings still override the
cells (an empty string paints the column's budget empty). The thumb maps the
pane's laid-out `offset` over `total_rows`. A left press in the strip is
consumed for grab-and-drag or paging; every other event passes through. The
bar never sees a wheel report because `read_event` absorbs the wheel first.

### Toasts

```python
Toasts(tui, *, ttl=4.0, max_shown=3, corner="top-right", style=None, theme=None)
show(content, *, style=None, ttl=None)
handle(event) -> bool
detach()
```

`show` takes a string or any component. Past `max_shown`, the oldest toast
is evicted. Expiry rides `tui.every` and `tui.clock()`. The band is
`theme.overlays.toast`. A press inside a toast's rectangle dismisses it;
`detach()` unregisters and cancels the ticker.

### Tooltip

```python
Tooltip(tui, pointer, *, theme=None)
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
`handle` consumes nothing; its `True` is a repaint cue, so route it beside
the other tiers, never in a consume chain.

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
on the package root; it lives in `motui.commands`.

### Clipboard

```python
Clipboard            # protocol: copy(text) -> bool
ScreenClipboard(screen)
MemoryClipboard()
```

`ScreenClipboard` delegates to the screen's OSC 52 write and its flush.
`MemoryClipboard` records the last text in `.text` and is the headless
backend. `True` is best-effort: a terminal may refuse application clipboard
writes. The real hook is `SelectionGesture(on_end=...)`.

## Theme, Palette, glyphs and keymaps

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

Build a variant with `dataclasses.replace` at the group level:

```python
from dataclasses import replace

from motui import DEFAULT_THEME, Style

theme = replace(
    DEFAULT_THEME,
    content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff8800")),
    rows=replace(DEFAULT_THEME.rows, active=Style(bg="#264f78")),
)
```

`Palette` is the brand-colour authoring layer consumed by
`Theme.from_palette`. Its 18 fields are `ink`, `muted`, `faint`, `line`,
`surface`, `surface_raised`, `surface_hover`, `surface_active`,
`surface_inactive`, `accent`, `success`, `warning`, `danger`, `code`,
`heading`, `link`, `inline_code` and `marker`. `DARK_PALETTE` and
`LIGHT_PALETTE` are the shipped values; `Palette()` equals `DARK_PALETTE`.

```python
from motui.kernel import Palette, Theme
from motui.kernel.style import Color

brand = Palette(
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
| `prompt` | `❯` | `Input`, `Find`, `Palette`, `ComboBox` |
| `cursor` | `→` | `List`, `Select`, `Autocomplete`, `ContextMenu` |
| `rail` | `▌` | `NavList` |
| `fold_open` / `fold_closed` | `▾` / `▸` | `Tree`, `Collapsible` |
| `radio_off` / `radio_on` | `( )` / `(•)` | `RadioGroup` |
| `check_off` / `check_on` | `[ ]` / `[x]` | `Checkbox`, `CheckboxGroup`, `Select`, `List`, `Table`, `Markdown` |
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
from motui.keys import DEFAULT_EDITOR_KEYMAP, DEFAULT_INPUT_KEYMAP, EDITOR_SUBMIT_KEYMAP

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
from motui.kernel.glyphs import GLYPHS


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
from motui.kernel import action_at


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
from motui.kernel.frame import Chrome


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
  driver: recording screen, scripted source, `interactive=False`.
- `snapshot(tui)` renders the document as structured plain text, one stanza
  per block with its id, state and pin.
- Nothing sleeps. Time enters through `tui.clock()`; a test overrides it or
  calls `tui.tick(now)`.

Golden frames pin what a user sees: `tests/golden/topics/*.txt`, one frame
per demo topic, checked and re-recorded by `tools/golden.py`.
