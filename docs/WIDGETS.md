# Widgets

The component library lives in `motui.widgets` (51 exported names) and is
re-exported selectively from `motui`. Every component renders through

```python
def render(self, c: Constraints) -> Surface: ...
```

and may add typed hooks. This page is the catalogue: constructor essentials,
capabilities, hooks and the `take()` result. The normative rules are in
[CONTRACT](CONTRACT.md).

## Conventions

- The main content is the single positional parameter; every other
  parameter is keyword-only. The tail order is `glyphs`, `theme`, `styles`,
  `keymap`. Exceptions are listed in [CONTRACT §9.1](CONTRACT.md#91-construction).
- Every themed widget accepts `theme: Theme | None = None`. Components that
  resolve role groups also accept `styles: Styles | None = None`. A `styles`
  field replaces that whole role group; `None` inherits the theme, resolved
  through `Theme.group(name)`. `Text` is the exception: it takes one
  explicit `style=` instead of `styles`.
- Glyph-carrying widgets take `glyphs: Glyphs = GLYPHS`; `Panel`, `Dialog`
  and `Table` also take a `Border`. Glyphs are content, not style; `""`
  turns a mark off and collapses its seat.
- Capability flags are class attributes: `focusable`, `clickable`,
  `hoverable`, `activatable`. `focus_scope = True` keeps focus routing
  inside a container's subtree.
- `keymap` is a `Keymap` descriptor: the class attribute is the family
  default, the instance attribute is that widget's own copy. Assigning a
  mapping or one entry touches only that instance.
- A hook returns `True` only when it consumed the input.
- `take()` reads a one-shot result and clears it. `None` means "nothing
  pending"; `False`, `0` and `""` are real results. State attributes stay
  readable. Only `activate()` and `toggle()` write a result; moving the
  cursor clears one.
- `index` is assignable (it delegates to `select()`); `selected` is
  read-only.
- `disabled` refuses activation and movement; `read_only` is the text-field
  equivalent.

| Capability set | Components |
|---|---|
| focus + click + hover + activate | `Button`, `Checkbox`, `Link`, `List`, `Table`, `Tree`, `Tabs`, `MenuBar`, `NavList`, `Select`, `MultiSelect`, `RadioGroup`, `CheckboxGroup`, `Autocomplete`, `ContextMenu`, `Slider`, `Collapsible` |
| focus + click + hover (no activate) | `Input`, `Editor` |
| click + hover (no focus) | `Text`, `Markdown` |
| focus + click (bar drag) | `ScrollPanel` |
| focus scope (internal routing) | `Form`, `Dialog`, `ComboBox` |
| display or container (no flags of its own) | `Diff`, `Divider`, `Panel`, `Padding`, `Row`, `Column`, `Stack`, `Align`, `Spacer`, `Notice`, `StatusLine`, `ShortcutBar`, `ProgressBar`, `Spinner`, `Canvas`, `PixelCanvas` |

## Styles and buttons

The theme is shared role groups, not a per-component recipe. The tokens a
widget writer reaches for are `surfaces.control` (field and neutral-button
floor), `surfaces.accent`/`surfaces.danger` (primary/danger floors) and the
state overlay:

```python
from motui import DEFAULT_THEME

band = DEFAULT_THEME.controls.overlay(
    hovered=True, focused=True, pressed=False, disabled=False
)
# disabled > pressed > focused > hovered; merge the answer over the base
```

`ButtonKind` is the one action-family role enum:

```python
from motui.widgets import Button, ButtonKind, Row

actions = Row([
    Button("Save", kind=ButtonKind.PRIMARY),
    Button("Cancel"),
    Button("Delete", kind=ButtonKind.DANGER),
])
```

`NEUTRAL` rides `surfaces.control` with `text.base`, `PRIMARY` rides
`surfaces.accent` with `text.inverse`, `GHOST` has no floor and uses
`content.accent`, and `DANGER` rides `surfaces.danger` with `text.inverse`.
See [CONTRACT §9.5](CONTRACT.md#95-style-resolution).

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
`select_home`, ...). Every row sits on `surfaces.control`; hover underlines
the row, focus is the caret, and `disabled`/`read_only` dims. `keymap`
replaces the whole table: `DEFAULT_INPUT_KEYMAP` leaves `enter` unbound;
`DEFAULT_EDITOR_KEYMAP` adds `enter` as newline; `EDITOR_SUBMIT_KEYMAP` binds
`c-j` instead. An unbound key is declined and returns to the host.

## Choice, forms and actions

| Component | Constructor essentials | Result |
|---|---|---|
| `Option` | `Option(label, value=None, description="")` | a value, not a widget |
| `Select` | `Select(options=(), *, title="", max_rows=8, wrap=True, window=False, disabled=False, disabled_items=(), glyphs=GLYPHS)` | `take() -> object \| None`, the chosen option's value (label if no value); moving or clicking clears the pending pick |
| `MultiSelect` | `MultiSelect(options=(), *, title="", max_rows=8, wrap=True, marked=(), disabled=False, disabled_items=(), glyphs=GLYPHS)` | `take() -> list[object] \| None`, the marked values in row order; `toggle()` flips the cursor row |
| `RadioGroup` | `RadioGroup(options, *, index=0, disabled=False, disabled_items=(), glyphs=GLYPHS)` | `selected -> Option \| None`; `take()` returns the selected value; clamped, never wraps |
| `CheckboxGroup` | `CheckboxGroup(options, *, marked=(), index=0, disabled=False, disabled_items=(), glyphs=GLYPHS)` | `take() -> list[object] \| None`; a click moves the cursor and flips the mark |
| `Autocomplete` | `Autocomplete(options=(), *, max_rows=8, wrap=True, glyphs=GLYPHS)` | `set_query(text)` filters; `take()` returns the chosen value |
| `ComboBox` | `ComboBox(options=(), *, text="", max_rows=8, max_drop_rows=6, glyphs=GLYPHS)` | `.input`/`.list`/`.open` (read-write bool); `toggle()` or assign `open`; `take()` returns the picked value |
| `Button` | `Button(label, *, kind=ButtonKind.NEUTRAL, disabled=False)` | `take() -> bool \| None` (activation), `on_action("activate")` |
| `Checkbox` | `Checkbox(label, *, checked=False, glyphs=GLYPHS, disabled=False)` | `take() -> bool \| None`, the new checked value |
| `Link` | `Link(text, *, disabled=False)` | `take() -> bool \| None`, a follow request |
| `Form` | `Form(fields, *, gap=0, index=0, on_submit=None)` | `focus_scope`; `take() -> dict[str, object] \| None` after validation |
| `Field` | `Field(name, component, label="", validate=None, value=None, error=None)` | a form entry, not a widget |
| `Slider` | `Slider(value=0, *, minimum=0, maximum=10, step=1, disabled=False, glyphs=GLYPHS)` | `.value` is the state; `move(delta)` steps it; no `take()` |
| `Collapsible` | `Collapsible(body, *, title="", open=True, disabled=False, glyphs=GLYPHS)` | `take() -> bool \| None`, the new `open` state |

`Select`/`MultiSelect` rows support `move(delta)`, `select(index)`,
`home()`/`end()`, `on_click`, `on_hover` and `on_action("prev"|"next"|
"first"|"last"|"activate"|"toggle")`. `List` is the simpler windowed cursor;
see below. `Option.description` is rendered in the choice family; the form
groups reject descriptions. `Select` has no `commit` switch: a move or a
click never writes a result, so a form reads `selected`, not `take()`.

```python
from motui.widgets import Option, Select

picker = Select([Option("Small", 1), Option("Large", 2)], title="Size")
picker.move(1)
size = picker.take()      # 2, or None when nothing was picked
```

`RadioGroup` and `CheckboxGroup` take labels or `Option` values and answer
`Option` objects from `.selected`:

```python
from motui.widgets import CheckboxGroup, RadioGroup

mode = RadioGroup(["Fast", "Accurate"])
features = CheckboxGroup(["Cache", "Compress"], marked=[0])

mode.selected             # Option(label='Fast', value=None, description='')
features.marked           # MarkSet({0})
features.take()           # ["Cache"]: the marked values, in row order
```

## Data views

| Component | Constructor essentials | Hooks / result |
|---|---|---|
| `List` | `List(items=(), *, window=8, prefix_jump=True, disabled=False, disabled_items=(), glyphs=GLYPHS)` | focus + click + hover + activate; `take() -> str \| None`; `.index`, `.items`, `.marked`; `toggle()` flips a mark; clamped steps |
| `Table` | `Table(rows, *, headers=(), aligns=None, glyphs=GLYPHS, grid=None, disabled=False, disabled_items=(), cell_wrap=WORD, max_col_width=40, min_col_width=3)` | focus + click + hover + activate; `take() -> object \| None` (the activated row); `.index` is an `int` (0 when empty), `.selected` is the row object; `.marked`, `toggle()`, `sort_by(col, reverse=False)`, `set_widths(widths)`, `header_lines(width)`/`header_line(width)`; `OVERFLOW` disables the column cap |
| `Tree` | `Tree(nodes=(), *, indent=2, glyphs=GLYPHS, disabled=False)` | focus + click + hover + activate; `.index` is the visible-row index, `.selected -> TreeNode \| None`; `take() -> TreeNode \| None` when a fold lands; `on_action("prev"|"next"|"open"|"close"|"activate")`, `filter(query)`, `jump(char)` |
| `TreeNode` | `TreeNode(label, children=(), *, open=False, disabled=False)` | a tree value, not a widget |
| `Tabs` | `Tabs(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False)` | focus + click + hover + activate; `.index`, `.select(i)`, `.move(delta)`; `take() -> str \| None`, the activated label |
| `NavList` | `NavList(items, *, groups=(), index=0, disabled_items=(), disabled=False, glyphs=GLYPHS, bar_space=None)` | focus + click + hover + activate; `.index`, `.select(i)`, `.move(delta)`; `take() -> str \| None`, the activated item |
| `MenuBar` | `MenuBar(items, *, index=0, glyphs=GLYPHS, disabled_items=(), disabled=False)` | focus + click + hover + activate; `take() -> str \| None`, the active label; clamped horizontal strip |
| `ContextMenu` | `ContextMenu(options=(), *, title="", max_rows=8, glyphs=GLYPHS)` | a `Select` preset; mount it through a `Modal` |
| `ProgressBar` | `ProgressBar(value=0.0, *, maximum=1.0, label="", width_chars=None, glyphs=GLYPHS)` | display only; `.value` clamps into `0..maximum`; `.fraction` is the read-only `value / maximum` |
| `Spinner` | `Spinner(text="", *, frames=None, glyphs=GLYPHS)` | display only; the host calls `.advance()`; `.frame` is the current cell |

`List`, `Table`, `Tabs`, `MenuBar` and `NavList` clamp at the ends;
`Select`/`MultiSelect`/`Autocomplete` wrap by default (`wrap=False` clamps),
and the form groups always clamp. `Table` is a data view and always clamps.
`Table(cell_wrap=WrapMode.OVERFLOW)` keeps the natural grid width for a
horizontal `ScrollPanel`; `WrapMode.WORD` is the default and wraps long
cells. The table binds `space` to `toggle`; a fresh table has no armed
cursor, so the first activation needs a move or a click.

```python
from motui.widgets import Table, Tree, TreeNode

table = Table(
    [("alpha", "ok"), ("beta", "warn")],
    headers=["name", "status"],
)
tree = Tree([
    TreeNode("src", [TreeNode("motui", open=True)]),
    TreeNode("tests"),
])
```

`Tabs`, `NavList` and `MenuBar` are activatable strips; activation writes
the label once:

```python
from motui.widgets import NavList, Tabs

tabs = Tabs(["Overview", "Logs"], index=1)
tabs.activate()
tabs.take()               # "Logs"

rail = NavList(["Home", "Settings"], groups=((1, "Account"),))
rail.activate()
rail.take()               # "Home"
```

## Layout and decoration

| Component | Constructor essentials | Notes |
|---|---|---|
| `Row` | `Row(children, *, widths=None, gap=1)` | side-by-side; `widths[i]` fixes a column, `None` is flexible; implements `child_at` |
| `Column` | `Column(children, *, gap=0)` | vertical stack; implements `child_at` |
| `Stack` | `Stack(children, *, theme=None, styles=None)` | layers bottom to top, same constraints, overlaid with `Surface.overlay`; implements `child_at` |
| `Align` | `Align(child, *, horizontal="center", vertical="middle", theme=None, styles=None)` | anchors one child (`left`/`center`/`right`, `top`/`middle`/`bottom`); implements `child_at` |
| `Padding` | `Padding(child, *, left=0, right=0, top=0, bottom=0)` | insets; the fill comes from `surfaces.base`; implements `child_at` |
| `Spacer` | `Spacer(rows=1)` | blank rows as a component |
| `Panel` | `Panel(child, *, title="", frame=True, border=None, glyphs=GLYPHS)` | one-line box or a borderless padded panel; implements `child_at` |
| `Divider` | `Divider(*, char=None, label="", max_width=None, glyphs=GLYPHS)` | repeated rule with an optional label |
| `Collapsible` | `Collapsible(body, *, title="", open=True, disabled=False, glyphs=GLYPHS)` | folds the body under a title row; implements `child_at` |
| `ScrollPanel` | `ScrollPanel(child, *, height=None, offset=0, bar=False, axis="y", glyphs=GLYPHS)` | a window over any component; see below |
| `StatusLine` | `StatusLine(*, left=(), right=())` | dim two-sided row |
| `ShortcutBar` | `ShortcutBar(items, *, glyphs=GLYPHS)` | key/label hints |

Containers never restyle their children. `Row` and `Column` remember their
last child rows and implement `Container.child_at`; a cell owned by a gap,
a border or padding belongs to the container, not a child.

`Stack` paints `children[0]` at the bottom; every layer renders with the
same constraints, and a transparent cell lets the layer below show through.
Hit testing prefers interaction: `child_at` walks top-down and returns the
first layer with a clickable/focusable/hoverable node at the cell, then
falls back to the topmost geometric layer. `Align` renders its child once
with the full constraints and measures the painted block (`len(rows)` by
the widest row); the anchor is applied to that size and overflow is
clipped. A child that fills the width shows no horizontal alignment: there
is no second measure.

```python
from motui.kernel import Constraints
from motui.widgets import Align, Canvas, Stack, Text

backdrop = Canvas(width=40, height=6)
backdrop.text(2, 1, "scanning sector 7")
badge = Align(Text("READY"), horizontal="center", vertical="middle")

view = Stack([backdrop, badge])
surface = view.render(Constraints(width=40, max_height=6))
```

## ScrollPanel

`ScrollPanel` is the composition-layer answer to content taller or wider
than its slot:

```python
from motui import ScrollPanel, Table
from motui.kernel.text import WrapMode

rows = [("alpha", "ok"), ("beta", "warn")]
table = Table(rows, headers=["name", "status"], cell_wrap=WrapMode.OVERFLOW)
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
- State: `.offset`, `.x_offset`, `.total_rows`, `.total_columns`; the
  immutable `.scroll -> Scroll` value behind them; methods `scroll_to`,
  `scroll_up/down`, `scroll_by`, `scroll_to_x`, `scroll_x`,
  `scroll_x_to_end`, `scroll_x_by`.
- The default keymap binds arrows, page keys and home/end; wheel
  `wheel_left`/`wheel_right` move one column. The panel is focusable and
  clickable (bar drag), not hoverable or activatable.

## Canvas and plots

```python
class Canvas(Drawing):
    def __init__(self, *, width=0, height=0, plot_marker="cell",
                 glyphs=GLYPHS, theme=None): ...
    def put(self, x, y, char, style=Style()) -> None: ...
    def text(self, x, y, text, style=Style()) -> None: ...
    def hline(self, x, y, length, char="─", style=Style()) -> None: ...
    def vline(self, x, y, length, char="│", style=Style()) -> None: ...
    def box(self, x, y, width, height, *, border=None, style=Style()) -> None: ...
    def blit(self, other, x, y) -> None: ...
    def plot(self, points, *, marker=None, style=Style()) -> None: ...
    def clear(self) -> None: ...
    def resize(self, width, height) -> None: ...
    def fit(self, c: Constraints) -> None: ...
    def surface(self) -> Surface: ...
    def render(self, c: Constraints) -> Surface: ...
```

`plot_marker` is `"cell"`, `"half"` (`▀▄█`) or `"braille"` (2x4) and affects
`plot` only. Writes outside the canvas are ignored; a wide character that
would split at the edge is dropped. `Canvas` is mutable and produces a
`Surface`; it never writes terminal bytes. `Sparkline(values=(), *,
marker="half", style=Style(), glyphs=GLYPHS)` is a plain renderer (not a
`Widget`) over the same canvas; its natural height is one row, and a
`max_height` budget fills that many.

### The Drawing lifecycle

`Canvas` and `PixelCanvas` share the internal `Drawing` base:

- Assigning `width` or `height` calls `resize(width, height)`.
- `resize` clamps at zero and is a no-op when the size is unchanged, so a
  redraw loop does not drop ink between equal constraints.
- `fit(c)` adopts `c.width` and `c.max_height` (a natural-height constraint
  keeps the current height).
- `surface()` answers the full-size cached `Surface`.
- `render(c)` clips that cached image to the constraints and **never
  resizes**. A host that follows a changing slot calls `resize` or `fit`
  before painting.

```python
from motui.kernel import Constraints
from motui.widgets import Canvas

canvas = Canvas(width=20, height=6, plot_marker="braille")
canvas.text(0, 0, "spectrum")
canvas.fit(Constraints(width=20, max_height=6))
rows = canvas.surface()          # the full image
painted = canvas.render(Constraints(width=12, max_height=4))  # clipped only
```

## PixelCanvas: sub-cell art

`PixelCanvas` is the sub-cell sibling of `Canvas`. It is new in 2.1 and
provisional: the engine (`motui.pixel`) and this widget may change in a
minor until they are frozen.

```python
class PixelCanvas(Drawing):
    def __init__(self, *, width=0, height=0, marker=Marker.BRAILLE,
                 palette=None, theme=None): ...
    def plot(self, x, y, slot=1, *, heat=255, layer=LayerName.ART) -> None: ...
    def erase(self, x, y, *, layer=LayerName.ART) -> None: ...
    def stamp(self, points, slot=1, *, heat=255, layer=LayerName.ART) -> None: ...
    def line(self, x0, y0, x1, y1, slot=1, *, heat=255, layer=LayerName.ART) -> None: ...
    def rect(self, x0, y0, x1, y1, *, fill=False, slot=1, heat=255, layer=LayerName.ART) -> None: ...
    def disc(self, cx, cy, r, slot=1, *, heat=255, layer=LayerName.ART) -> None: ...
    def ring(self, cx, cy, r, thickness=1, slot=1, *, heat=255, layer=LayerName.ART) -> None: ...
    def clear(self, *, layer=None) -> None: ...
    def decay(self, amount, *, layer=LayerName.ART) -> None: ...
    def resize(self, width, height) -> None: ...
    def fit(self, c: Constraints) -> None: ...
    def surface(self) -> Surface: ...
    def render(self, c: Constraints) -> Surface: ...
```

Every cell is a 2x4 sub-cell grid and every drawing coordinate is a
sub-cell. The widget owns two private `motui.pixel.Raster` layers:

- **art** (`LayerName.ART`) — lines, sprites and rings at `marker`
  resolution;
- **fill** (`LayerName.FILL`) — half-block fills behind the art.

`marker` is `Marker.BRAILLE` (eight dots) or `Marker.HALF` (top/bottom
blocks); it is validated on assignment. `palette=None` derives
`PixelPalette.from_theme(theme)`; an explicit `PixelPalette` always wins.
`PixelPalette` maps each slot id to a `(main, cool)` color pair; fresh ink
(`heat >= 192`) uses *main*, cooled ink uses *cool*, and `bg` optionally
paints the unlit half of a fill cell. `heat` is `0..255`; `decay` cools a
layer in place, which is the trail primitive. A cell belongs to the first
layer with ink in it, so art wins a cell both layers claim.

```python
from motui.kernel import Constraints
from motui.pixel import PixelPalette
from motui.widgets import LayerName, PixelCanvas

palette = PixelPalette(slots={1: ((255, 99, 132), (122, 46, 64))})
canvas = PixelCanvas(width=20, height=8, palette=palette)
canvas.disc(20, 16, 5, 1, layer=LayerName.FILL)
canvas.ring(20, 16, 12, 2, 1)
canvas.decay(40)
canvas.fit(Constraints(width=20, max_height=8))
surface = canvas.render(Constraints(width=20, max_height=8))
```

`render` never resizes: it clips the cached image, so rendering at a probe
width cannot drop the ink. A real `resize` (or a changed `width`/`height`)
rebuilds both rasters empty, which a pixel scene refills on its next tick.
`pixel_width`/`pixel_height` answer the sub-cell geometry. The splash and
motion scenes are the reference uses: the wordmark stamps the fill layer,
the sweep and stars ride the art layer, and the rings stamp their fade at
an explicit heat.

## Dialogs and modal panels

| Component | Constructor essentials | Result |
|---|---|---|
| `Dialog` | `Dialog(body, *, title="", buttons=(), danger=False, width=None, align="center", border=None, shade=True, frame=True, glyphs=GLYPHS)` | `take() -> object \| None`, the pressed `ButtonSpec.value`; `escape` leaves a taken cancel (`None`); `on_key`, `on_click`; `focus_scope` |
| `ButtonSpec` | `ButtonSpec(label, value=None, styles=None, kind=ButtonKind.NEUTRAL)` | a dialog button value; `kind=ButtonKind.DANGER` is the destructive role |
| `confirm_dialog` | `confirm_dialog(message, *, danger=False, confirm_text="Yes", cancel_text="No", frame=True)` | a `Dialog` |
| `prompt_dialog` | `prompt_dialog(title, *, placeholder="", mask="", confirm_text="OK", cancel_text="Cancel", danger=False, frame=True)` | a `Dialog` |

`Dialog` draws its own box; `width=None` means three fifths of the paint
width, clamped to 24..72 and never wider than the pane. Its interior cells
sit on `surfaces.raised`, and a `danger` dialog keeps the destructive
button's `surfaces.danger` floor. `frame=False` drops the box and keeps the
body/buttons. The dialog is mounted by a controller: `App.open_modal(dialog)`
wraps it in a `Modal` (scrim, blocking keys and click-outside), and
`Modal.take()`/its callbacks carry the result to the host.

```python
from motui import Dialog, Text
from motui.widgets import ButtonKind, ButtonSpec

confirm = Dialog(Text("Continue?"), title="Confirm", buttons=["Yes", "No"])
delete = Dialog(
    Text("Delete the project?"),
    title="Delete",
    buttons=[ButtonSpec("Delete", True, kind=ButtonKind.DANGER), "Cancel"],
)
```

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

An interactive component subclasses `Widget` and declares a `Keymap`:

```python
from motui.kernel import Constraints, Line, Surface
from motui.widgets import Widget
from motui.widgets.base import Keymap


class Toggle(Widget):
    focusable = True
    activatable = True
    keymap = Keymap({"enter": "activate", "space": "activate"})

    def __init__(self) -> None:
        super().__init__()
        self.on = False
        self._pending: bool | None = None

    def on_action(self, name: str) -> bool:
        if name != "activate":
            return False
        self.on = not self.on      # the setter calls touch()
        self._pending = self.on
        return True

    def take(self) -> bool | None:
        pending, self._pending = self._pending, None
        return pending

    def render(self, c: Constraints) -> Surface:
        return Surface.clipped(
            [Line.from_text(f"[{'x' if self.on else ' '}]")], c.width
        )
```

Rules of thumb:

1. Render into `Surface.clipped(rows, c.width)` and honor `max_height`.
2. Declare only the capabilities you implement.
3. Read styles at render time through `self.group(name)`; the section cache
   keys on `generation`, so an attribute assignment (automatic `touch()`)
   or an explicit `touch()` after in-place mutation is the invalidation.
4. Return `False` for declined input and let routing continue.
5. Collect one-shot results with `take()`, not callbacks; add the widget to
   `children` if it owns another widget.
6. Write a result only from `activate()`/`toggle()`; clear it from every
   state-changing verb.

## Collecting results

```python
from motui.widgets.base import HasResult

for widget in app.walk():
    if isinstance(widget, HasResult):
        value = widget.take()
        if value is not None:
            handle(value)
```

`HasResult` is a runtime-checkable protocol with one `take()` method; every
`ResultWidget` implements it. Use `is not None` for boolean and integer
results: `False` and `0` are real answers. A legal `None` payload (a
cancelled dialog) is recognized by the fact that `take()` was called at all.
