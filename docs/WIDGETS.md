# Widgets

The component library lives in `motui.widgets` (46 exported names) and is
re-exported selectively from `motui`. Every component renders through

```python
def render(self, c: Constraints) -> Surface: ...
```

and may add typed hooks. This page is the catalogue: constructor essentials,
capabilities, hooks and the `take()` result. The normative rules are in
[CONTRACT](CONTRACT.md).

## Conventions

- Every themed widget takes `theme: Theme | None = None` and
  `styles: Styles | None = None`. A `styles` field replaces that whole role
  group; `None` inherits the theme.
- Glyph-carrying widgets take `glyphs: Glyphs = GLYPHS`; `Panel`, `Dialog`
  and `Table` also take a `Border`. Glyphs are content, not style; `""`
  turns a mark off and collapses its seat.
- Capability flags are class attributes: `focusable`, `clickable`,
  `hoverable`, `activatable`. `focus_scope = True` keeps focus routing
  inside a container's subtree.
- A hook returns `True` only when it consumed the input.
- `take()` reads a one-shot result and clears it. `None` means "nothing
  pending"; `False`, `0` and `""` are real results. State attributes stay
  readable.
- The class `keymap` is the default; an instance `keymap` merges over it.
- `disabled` refuses activation and movement; `read_only` is the text-field
  equivalent.

| Capability set | Components |
|---|---|
| focus + click + hover + activate | `Button`, `Checkbox`, `Link`, `List`, `Table`, `Tree`, `Select`, `MultiSelect`, `RadioGroup`, `CheckboxGroup`, `Autocomplete`, `ContextMenu`, `MenuBar`, `Slider`, `Collapsible` |
| focus + click + hover (no activate) | `Tabs`, `NavList`, `Input`, `Editor` |
| click + hover (no focus) | `Text`, `Markdown` |
| focus + click (bar drag) | `ScrollPanel` |
| focus + scope | `Form`, `Dialog`, `ComboBox` |
| pure display | `Diff`, `Divider`, `Panel`, `Padding`, `Row`, `Column`, `Spacer`, `Notice`, `StatusLine`, `ShortcutBar`, `ProgressBar`, `Spinner` |

## Text and content

| Component | Constructor essentials | Hooks / result |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)`; wraps `WORD` | clickable/hoverable; `take() -> str \| None` (an inline action payload) |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, highlighter=None, glyphs=GLYPHS, gap=1, divider_max_width=80, max_width=None, code_wrap=WORD)` | clickable/hoverable; `take() -> str \| None` (a link); `.text` is assignable for streaming; `fences()` lists code blocks |
| `Diff` | `Diff(before, after, *, context=3, numbers=False, glyphs=GLYPHS, wrap=ELLIPSIS)` | display only; the LCS runs once at construction |
| `Notice` | `Notice(text, *, level="info", glyphs=GLYPHS)` | display only; levels `info`, `success`, `warn`, `error` |

`Text` renders each logical line verbatim and wraps it; a subclass can
render inline spans and inherit hit testing, hover and `take()`. `Markdown`
is a rule-registry engine: block and inline rules are ordered, every prefix
is safe to render, and `highlighter` accepts any object with
`highlight(code, lang) -> list[Line]`.

## Input and editing

| Component | Constructor essentials | Hooks / result |
|---|---|---|
| `Input` | `Input(text="", *, prompt=None, placeholder="", mask="", glyphs=GLYPHS, keymap=None, read_only=False, wrap=OVERFLOW)` | focusable/clickable/hoverable; `on_key`, `on_mouse`, `on_paste`, `on_action`, `on_click`; state `.text`; no `take()` |
| `Editor` | `Editor(text="", *, placeholder="", mask="", keymap=None, max_rows=None, read_only=False, wrap=WORD)` | same hooks; multi-line buffer; no `take()` |

Both expose `cursor`, `selection_range()`, `selected_text()`, `select_all()`,
`clear()` and the movement/selection methods (`move_left`, `move_up`,
`select_home`, ...). `DEFAULT_INPUT_KEYMAP` binds editing keys but leaves
`enter` unbound; `DEFAULT_EDITOR_KEYMAP` adds `enter` as newline;
`EDITOR_SUBMIT_KEYMAP` binds `c-j` instead. An unbound key is declined and
returns to the host.

## Choice, forms and actions

| Component | Constructor essentials | Result |
|---|---|---|
| `Option` | `Option(label, value=None, description="")` | a value, not a widget |
| `Select` | `Select(options=(), *, title="", max_rows=8, wrap=True, commit=False, window=False, disabled=False, disabled_items=(), glyphs=GLYPHS)` | `take() -> object \| None`, the chosen option's value (label if no value); `commit=True` leaves a pick on every move/click |
| `MultiSelect` | `MultiSelect(options=(), *, title="", max_rows=8, wrap=True, marked=(), disabled=False, ...)` | `take() -> list[object] \| None`, the marked values in row order; `toggle()` flips the cursor row |
| `RadioGroup` | `RadioGroup(labels, *, index=0, disabled=False, disabled_items=(), glyphs=GLYPHS)` | `selected -> str \| None`; `take()` returns the selected value; clamped, never wraps |
| `CheckboxGroup` | `CheckboxGroup(labels, *, marked=(), index=0, disabled=False, ...)` | `take() -> list[object] \| None`; a click moves the cursor and flips the mark |
| `Autocomplete` | `Autocomplete(options=(), *, max_rows=8, wrap=True, glyphs=GLYPHS)` | `set_query(text)` filters; `take()` returns the chosen value |
| `ComboBox` | `ComboBox(options=(), *, text="", max_rows=8, max_drop_rows=6, glyphs=GLYPHS)` | `.input`/`.list`/`is_open`, `open()`/`close()`; `take()` returns the picked value |
| `Button` | `Button(label, *, disabled=False)` | `take() -> bool \| None` (activation), `on_action("activate")` |
| `Checkbox` | `Checkbox(label, *, checked=False, glyphs=GLYPHS, disabled=False)` | `take() -> bool \| None`, the new checked value |
| `Link` | `Link(text, *, disabled=False)` | `take() -> bool \| None`, a follow request |
| `Form` | `Form(fields, *, gap=0, index=0, on_submit=None)` | `focus_scope`; `take() -> dict[str, object] \| None` after validation |
| `Field` | `Field(name, component, label="", validate=None, value=None, error=None)` | a form entry, not a widget |
| `Slider` | `Slider(value=0, *, minimum=0, maximum=10, step=1, disabled=False, glyphs=GLYPHS)` | `take() -> int \| None`, a confirmation; `.value` is a state property |
| `Collapsible` | `Collapsible(title, body, *, open=True, disabled=False, glyphs=GLYPHS)` | `take() -> bool \| None`, the new `open` state |

`Select`/`MultiSelect` rows support `move(delta)`, `select(index)`,
`home()`/`end()`, `on_click`, `on_hover` and `on_action("prev"|"next"|
"first"|"last"|"activate")`. `List` is the simpler windowed cursor; see
below. `Option.description` is rendered in the choice family; the form
groups reject descriptions.

## Data views

| Component | Constructor essentials | Hooks / result |
|---|---|---|
| `List` | `List(items=(), *, window=8, prefix_jump=True, disabled=False, disabled_items=(), glyphs=GLYPHS)` | focus + click + hover + activate; `take() -> str \| None`; `.index`, `.items`, `.marked`; `toggle()` flips a mark; clamped steps |
| `Table` | `Table(headers, rows, *, aligns=None, grid=None, disabled=False, disabled_items=(), cell_wrap=WORD, max_col_width=40, min_col_width=3)` | focus + click + hover + activate; `take() -> int \| None` (data-row index); `.selected`, `.marked`, `toggle()`, `sort_by(col, reverse=False)`, `set_widths(widths)`, `header_line(width)`; `OVERFLOW` disables the column cap |
| `Tree` | `Tree(root_nodes, *, indent=2, glyphs=GLYPHS, disabled=False)` | focus + click + hover + activate; `.selected -> TreeNode \| None`; `on_action("prev"|"next"|"expand"|"collapse"|"activate")`, `filter(query)`, `jump(char)`; no `take()` |
| `TreeNode` | `TreeNode(label, children=(), *, expanded=False, disabled=False)` | a tree value, not a widget |
| `Tabs` | `Tabs(tabs, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False)` | focus + click + hover; `.index`, `.select(i)`, `.move(delta)`; no `take()` |
| `NavList` | `NavList(items, *, groups=(), index=0, disabled_items=(), disabled=False, bar_space=None, glyphs=GLYPHS)` | focus + click + hover; `.index`, `.select(i)`, `.move(delta)`; no `take()` |
| `MenuBar` | `MenuBar(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False)` | `take() -> str \| None`; clamped horizontal strip |
| `ContextMenu` | `ContextMenu(options=(), *, title="", max_rows=8, glyphs=GLYPHS, **kwargs)` | a `Select` preset; mount it through a `Modal` |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, glyphs=GLYPHS)` | display only; `.fraction` clamps to `0..1` |
| `Spinner` | `Spinner(text="", *, frames=None, glyphs=GLYPHS)` | display only; the host calls `.advance()` |

`List` clamps at the ends; the menu family wraps by default (pass
`wrap=False` for a form group). `Table` is a data view and always clamps.
`Table(cell_wrap=WrapMode.OVERFLOW)` keeps the natural grid width for a
horizontal `ScrollPanel`; `WrapMode.WORD` is the default and wraps long
cells. The table binds no key for marks: route `space` (or any key) to
`toggle()` yourself.

## Layout and decoration

| Component | Constructor essentials | Notes |
|---|---|---|
| `Row` | `Row(children, *, widths=None, gap=1)` | side-by-side; `widths[i]` fixes a column, `None` is flexible; implements `child_at` |
| `Column` | `Column(children, *, gap=0)` | vertical stack; implements `child_at` |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0)` | insets; the fill comes from `surfaces.base`; implements `child_at` |
| `Spacer` | `Spacer(rows=1)` | blank rows as a component |
| `Panel` | `Panel(child, *, title="", frame=True, border=None, glyphs=GLYPHS)` | one-line box or a borderless padded panel; implements `child_at` |
| `Divider` | `Divider(*, char=None, label="", max_width=None, glyphs=GLYPHS)` | repeated rule with an optional label |
| `Collapsible` | `Collapsible(title, body, *, open=True, disabled=False, glyphs=GLYPHS)` | folds the body under a title row; implements `child_at` |
| `ScrollPanel` | `ScrollPanel(child, *, height=None, offset=0, bar=False, axis="y", glyphs=GLYPHS)` | a window over any component; see below |
| `StatusLine` | `StatusLine(*, left=(), right=(), glyphs=GLYPHS)` | dim two-sided row |
| `ShortcutBar` | `ShortcutBar(items, *, glyphs=GLYPHS)` | key/label hints |

Containers never restyle their children. `Row` and `Column` remember their
last child rows and implement `Container.child_at`; a cell owned by a gap,
a border or padding belongs to the container, not a child.

## ScrollPanel

`ScrollPanel` is the composition-layer answer to content taller or wider
than its slot:

```python
from motui import ScrollPanel, Table
from motui.kernel.text import WrapMode

table = Table(headers, rows, cell_wrap=WrapMode.OVERFLOW)
view = ScrollPanel(table, axis="x", height=8, bar=True)
app.add(view)
```

- `axis="y"` (default) moves rows only; `"x"` moves columns only and shows
  every child row; `"both"` moves the axes independently. Any other value
  raises `ValueError`.
- `height=None` shows every child row; a fixed height pads short content so
  the slot never jumps.
- `bar=True` reserves the rightmost column (and the bottom row for a
  horizontal bar) and paints a draggable proportional thumb. No thumb is
  painted when the content fits.
- Horizontal overflow is legal: an `OVERFLOW` child may render wider than
  the panel. The panel hard-cuts columns (no ellipsis) because the removed
  columns are scrollable.
- State: `.offset`, `.x_offset`, `.total_rows`, `.total_columns`;
  methods `scroll_to`, `scroll_up/down`, `scroll_by`, `scroll_to_x`,
  `scroll_x`, `scroll_x_to_end`, `scroll_x_by`.
- The default keymap binds arrows, page keys and home/end; wheel
  `wheel_left`/`wheel_right` move one column. The panel is focusable and
  clickable (bar drag), not hoverable or activatable.
- `scroll_state` still exposes the mutable `ScrollState` geometry used by
  the pane chrome; the immutable `Scroll`/`ScrollAxis` values are the 2.0
  model.

## Canvas and plots

```python
class Canvas(Widget):
    def __init__(self, width=0, height=0, *, marker="cell", glyphs=GLYPHS): ...
    def put(self, x, y, char, style=Style()) -> None: ...
    def text(self, x, y, text, style=Style()) -> None: ...
    def hline(self, ...): ...
    def vline(self, ...): ...
    def box(self, ...): ...
    def blit(self, other, x, y) -> None: ...
    def plot(self, points, *, style=Style()) -> None: ...
    def surface(self) -> Surface: ...
    def render(self, c: Constraints) -> Surface: ...
```

`marker` is `"cell"`, `"half"` (`▀▄█`) or `"braille"` (2x4). Writes outside
the canvas are ignored; a wide character that would split at the edge is
dropped. `Canvas` is mutable and produces a `Surface`; it never writes
terminal bytes. `Sparkline(values=(), *, marker="half", style=Style(),
glyphs=GLYPHS)` is a plain renderer (not a `Widget`) over the same canvas;
its natural height is one row, and a `max_height` budget fills that many.

## Dialogs and modal panels

| Component | Constructor essentials | Result |
|---|---|---|
| `Dialog` | `Dialog(title, body, buttons, *, danger=False, width=None, align="center", border=None, shade=True, frame=True, glyphs=GLYPHS)` | `take() -> object \| None`, the pressed `ButtonSpec.value`; `escape` leaves a taken cancel (`None`); `on_key`, `on_click`; `focus_scope` |
| `ButtonSpec` | `ButtonSpec(label, value=None, styles=None, danger=False)` | a dialog button value |
| `confirm_dialog` | `confirm_dialog(message, *, danger=False, confirm_text="Yes", cancel_text="No", frame=True)` | a `Dialog` |
| `prompt_dialog` | `prompt_dialog(title, *, placeholder="", mask="", confirm_text="OK", cancel_text="Cancel", danger=False, frame=True)` | a `Dialog` |

`Dialog` draws its own box; `width=None` means three fifths of the paint
width, clamped to 24..72 and never wider than the pane. `frame=False`
drops the box and keeps the body/buttons. The dialog is mounted by a
controller: `App.open_modal(dialog)` wraps it in a `Modal` (scrim, blocking
keys and click-outside), and `Modal.take()`/its callbacks carry the result
to the host.

`Modal` and `CommandPalette` are `motui.app` controllers, not components.
They accept any panel that renders and handles events. `App.open_palette`
accepts a `CommandRegistry` and renders its `options()`.

## Writing a component

A pure renderer needs no base class:

```python
from motui.kernel import Constraints, Line, Surface


class Rule:
    def render(self, c: Constraints) -> Surface:
        return Surface.clipped([Line.from_text("-" * c.width)], c.width)
```

An interactive component subclasses `Widget`:

```python
from motui.kernel import Constraints, KeyEvent, Line, Surface
from motui.widgets import Widget


class Toggle(Widget):
    focusable = True
    activatable = True
    keymap = {"enter": "activate", "space": "activate"}

    def __init__(self) -> None:
        super().__init__()
        self.on = False

    def on_action(self, name: str) -> bool:
        if name != "activate":
            return False
        self.on = not self.on      # the setter calls touch()
        return True

    def take(self) -> bool | None:
        pending, self._pending = getattr(self, "_pending", None), None
        return pending

    def render(self, c: Constraints) -> Surface:
        return Surface.clipped([Line.from_text(f"[{'x' if self.on else ' '}]")], c.width)
```

Rules of thumb:

1. Render into `Surface.clipped(rows, c.width)` and honor `max_height`.
2. Declare only the capabilities you implement.
3. Read styles at render time through `self.group(name)`; put `theme` and
   `styles` in your `revision()` snapshot when you answer one.
4. Return `False` for declined input and let routing continue.
5. Collect one-shot results with `take()`, not callbacks; add the widget to
   `children` if it owns another widget.

## Collecting results

```python
from motui.widgets import HasResult

for widget in app.walk():
    if isinstance(widget, HasResult):
        value = widget.take()
        if value is not None:
            handle(value)
```

`HasResult` is a runtime-checkable protocol with one `take()` method. Use
`is not None` for boolean and integer results: `False` and `0` are real
answers.
