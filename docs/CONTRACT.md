# The motui contract

This page is the short normative layer. It states the rules the
implementation and the tests are written against; it is not a tutorial.
[`docs/DESIGN.md`](DESIGN.md) explains the mechanisms and
[`docs/COMPONENTS.md`](COMPONENTS.md) explains how to build with them. Where
this page and the shipped code disagree, the code is wrong and the change
that touches it must make the code match.

## 1. Events

Every input is an `Event`. There is no catch-all "key" type.

```python
class Event: ...

@dataclass(frozen=True, slots=True)
class KeyEvent(Event):
    key: str
    char: str = ""
    modifiers: frozenset[str] = frozenset()
    kind: str = "press"          # press | repeat | release

@dataclass(frozen=True, slots=True)
class MouseEvent(Event):
    button: str = "none"         # left | middle | right | none |
                                 # wheel_up | wheel_down | wheel_left | wheel_right
    x: int = 0                   # 0-based column
    y: int = 0                   # 0-based row
    kind: str = "press"          # press | release | motion | wheel
    modifiers: frozenset[str] = frozenset()

@dataclass(frozen=True, slots=True)
class PasteEvent(Event):
    text: str

@dataclass(frozen=True, slots=True)
class ResizeEvent(Event):
    width: int
    height: int

@dataclass(frozen=True, slots=True)
class FocusEvent(Event):
    focused: bool
```

- A mouse report is never a key. `isinstance(event, KeyEvent)` matches the
  keyboard only.
- `PasteEvent.text` is literal; it is never re-interpreted as keys.
- Events are frozen, value-equal and hashable. They carry no timestamps.
- `KeyEvent.key` is the routing identity. Printable keys use the character
  itself (`"a"`, `"中"`, `"!"`); space is `"space"` with `char=" "`; special
  keys are `enter`, `escape`, `tab`, `backspace`, `insert`, `delete`,
  `home`, `end`, `page_up`, `page_down`, `up`, `down`, `left`, `right`,
  `f1`..`f24`.
- Chords use `c-` (Ctrl), `a-` (Alt), `s-` (Shift) in that order:
  `c-s-left`, `a-s-up`, `c-a-s-tab`. Ctrl-J is `c-j`; carriage return is
  `enter`.
- `modifiers` is the structured form of the same fact. Plain UTF-8 text
  does not infer Shift; only an escape sequence carrying a modifier
  parameter fills it.
- `TUI.read_event()` returns the next `Event`, or `None` at EOF and on a
  non-live screen.
- `EventSource.read()` returns `None` at EOF and keeps returning `None`.
  `PasteEvent` is one event even across feed boundaries.

## 2. Coordinates and hit testing

- Every cell index is 0-based. The decoder subtracts 1 from the terminal's
  1-based mouse fields; the painter adds 1 only when it emits a
  cursor-position escape.
- `tui.hit(x, y)` resolves a screen cell to a `Hit`. `tui.hit_leaf(x, y)`
  walks containers down to the deepest component. `tui.pane_at(x, y)`
  resolves the pane.
- Out-of-bounds coordinates return `None`. They are never clamped.
- `Hit.row` / `Hit.col` are block-internal 0-based coordinates. `Hit.col` is
  measured against the pane's **inner rect** (chrome subtracted).
- `Hit` carries `pane`, `block`, `row`, `col`, `leaf`, `leaf_row`,
  `leaf_col`; `pane_id` is a read-only convenience property.
- `Container.child_at(row, col)` answers from the container's **last
  render**. It may decline (`None`), and it proxies no controller verb.
- Block ids are unique across the whole frame, not only within one
  document.

## 3. Driver lifecycle

```python
await tui.run_session(body)     # scripted session; the caller owns the loop
tui.run()                       # sync entry; owns the loop
await tui.run_async()           # async entry; owns the loop
tui.exit()                      # end the session now
tui.refresh()                   # mark dirty; the pump paints
await tui.read_event()          # next event, or None at EOF
```

- `exit()` unblocks a pending `read_event()`, cancels the pump and lets
  teardown run. It is safe from any task.
- A `TUI` can run more than once. Each run resets timers, selection and the
  painter's diff base; an owned key source is closed at teardown and
  reattached on the next run.
- The driver owns the screen, the frame and the pump. `TUI.screen`,
  `TUI.frame`, `TUI.document`, `TUI.viewport` and `TUI.painter` are
  read-only views.
- `TUI.refresh()` is the public dirty signal. `TUI.paint()` is the low-level
  immediate paint.
- `TUI.screen.copy_to_clipboard(text)` is the clipboard primitive and
  flushes.
- `read_event()` absorbs the `scroll_keys` table (`page_up`/`page_down` and
  the wheel by default) and runs the focus policy on a mouse press.

## 4. Panes, documents and docks

- A `Pane` is a mutable runtime object with a stable, monotonically
  allocated id that is never reused. It owns one `Viewport`, therefore one
  `Document`.
- Document operations are pane-scoped: `tui.pane(id).add/get/remove(...)`,
  or `tui.add(..., pane=...)`. With no explicit pane the focused pane is the
  target (the primary pane when there is no split).
- `tui.dock(viewport, edge="top"|"bottom", size=None)` pins a frame-level
  region outside the split area. `size=None` derives the height from
  content. `tui.undock(edge)` removes it. An empty dock paints nothing and
  keeps no ghost rows. One dock per edge.
- A dock takes neither focus nor splits. A wheel over a dock scrolls the
  focused pane.
- Structural frame changes (split, close, chrome, dock, overlay) make the
  driver dirty; a host does not need an extra `refresh()`.
- `TUI.visible_range(pane=None)` returns the visible body row range as
  screen rows, including the pane's top-pin offset, or `None` before the
  first composition.

## 5. Styles, ColorPalette and theme

`Style` is the frozen terminal style value; colors come from `Color`, a
`FG_CODES` name, `#rrggbb`, or an `(r, g, b)` tuple.

```python
@dataclass(frozen=True, slots=True)
class Color:
    value: str | tuple[int, int, int]   # "#rrggbb" or (r, g, b)
    ansi: str | None = None             # an FG_CODES name

@dataclass(frozen=True, slots=True)
class Style:
    fg: Color | str | tuple[int, int, int] | None = None
    bg: Color | str | tuple[int, int, int] | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False
    strike: bool = False
```

- `Color.value` is the authoring color. `Color.ansi` is the 16-color
  fallback and must be an `FG_CODES` key or `None`; anything else raises
  `ValueError` at construction.
- `truecolor` and `256` paint the authoring value (256 quantized); `16`
  prefers `Color.ansi` and quantizes only when it is `None`; `none` drops
  color and keeps attributes.
- A bare `Style(fg="#rrggbb")` or tuple color keeps its historical
  meaning. `Color` only adds the ANSI anchor beside it.

`ColorPalette` is the brand-color authoring layer. It is frozen, has 18
fields, and is consumed only by `Theme.from_palette`:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ColorPalette:
    ink: Style = NONE
    muted: Style = ...
    faint: Style = ...
    line: Style = ...
    surface: Style = NONE
    surface_raised: Style = ...
    surface_hover: Style = ...
    surface_active: Style = ...
    surface_inactive: Style = ...
    accent: Style = ...
    success: Style = ...
    warning: Style = ...
    danger: Style = ...
    code: Style = NONE
    heading: Style = ...
    link: Style = ...
    inline_code: Style = ...
    marker: Style = ...
```

`DARK_PALETTE` and `LIGHT_PALETTE` are the two shipped palettes.

`Theme` is ten frozen role groups; every field is a `Style`.

| Group | Fields |
|---|---|
| `text` | `base`, `muted`, `faint`, `inverse`, `disabled`, `caret`, `selection` |
| `surfaces` | `base`, `raised`, `hover`, `active`, `selected` |
| `borders` | `base`, `grid`, `focus`, `danger` |
| `controls` | `base`, `hover`, `focus`, `active`, `disabled` |
| `rows` | `base`, `hover`, `active`, `inactive`, `selected`, `marked`, `disabled` |
| `status` | `success`, `warning`, `danger`, `info` |
| `content` | `accent`, `link`, `code`, `inline_code`, `headings`, `marker`, `quote`, `strong`, `emphasis`, `strike` |
| `chrome` | `divider`, `scrollbar`, `scrollbar_thumb` |
| `overlays` | `scrim`, `toast`, `tooltip` |
| `syntax` | `comment`, `keyword`, `string`, `number`, `builtin` |

- `Theme()` and `DEFAULT_THEME` are the Ink & Signal dark theme:
  `Theme.dark() == Theme() == DEFAULT_THEME`.
- `Theme.light()`, `Theme.flat()`, `Theme.auto(env=None)` and
  `Theme.from_palette(palette)` are pure constructors. None writes global
  state; `auto` only reads the supplied mapping (default `os.environ`).
- `auto` reads `TERM_BACKGROUND` first, then a numeric `COLORFGBG`
  background slot (`COLORBGBG` is accepted as the 1.x alias), and falls
  back to dark.
- `flat` is the dark theme with `surfaces.*` flattened to `NONE`;
  position reads through `rows.active=reverse`, `rows.inactive=dim`,
  `rows.hover=underline`, `rows.selected=reverse` and reversed overlay
  bands.
- The 1.x flat fields (`accent`, `muted`, `dim`, `hover`, `ground`, ...)
  and the `kernel.style` semantic constants are **gone**. Read the group
  field instead. Build an override with
  `replace(theme, content=replace(theme.content, accent=...))`.
- `RowStyles.band()` and `ControlStyles.band()` are the default state
  resolvers. They have no side effects.

`Glyphs` and `Border` are content values, never theme tokens.

```python
@dataclass(frozen=True, slots=True)
class Border:
    top_left: str = "┌"; top: str = "─"; top_tee: str = "┬"; top_right: str = "┐"
    left: str = "│"; middle: str = "─"; cross: str = "┼"; right: str = "│"
    middle_left: str = "├"; middle_right: str = "┤"
    bottom_left: str = "└"; bottom: str = "─"; bottom_tee: str = "┴"; bottom_right: str = "┘"

@dataclass(frozen=True, slots=True, kw_only=True)
class Glyphs:
    prompt: str = "❯"; cursor: str = "→"; rail: str = "▌"
    fold_open: str = "▾"; fold_closed: str = "▸"
    radio_off: str = "( )"; radio_on: str = "(•)"
    check_off: str = "[ ]"; check_on: str = "[x]"; check_indeterminate: str = "[-]"
    more_up: str = "↑"; more_down: str = "↓"
    bar_full: str = "█"; bar_empty: str = "░"
    slider_track: str = "━"; slider_thumb: str = "●"
    horizontal_rule: str = "─"; vertical_rule: str = "│"; quote: str = "│"
    separator: str = " · "; bullets: tuple[str, ...] = ("•", "◦", "▪")
    notice_info: str = "i"; notice_success: str = "✓"
    notice_warn: str = "!"; notice_error: str = "×"
    diff_add: str = "+"; diff_remove: str = "-"; diff_context: str = " "
    spinner: tuple[str, ...] = (...)
    box: Border = Border.square()
    grid: Border = Border.square()
```

- `Border` has `square()`, `rounded()`, `heavy()`, `double()`, `ascii()`
  and `none()` constructors. `none()` keeps the geometry with spaces.
- `GLYPHS = Glyphs()` is the shipped vocabulary. `seat(glyph)` returns the
  glyph plus one space (`""` seats nothing); `seat_width(glyph)` measures
  the seat; `pair_seat(glyph, other)` pads a state pair to one width.
- A glyph-carrying component takes `glyphs: Glyphs = GLYPHS`.
  `Panel`, `Dialog` and `Table` also take an optional `Border`
  (`Panel.border`, `Dialog.border`, `Table.grid`).
- Instance content overrides that remain: `Divider(char=)`,
  `Input(prompt=)`, `Scrollbar(track=/thumb=)`. `None` means "use the
  glyph vocabulary"; `""` turns a mark off and collapses its seat.

## 6. Components

The rendering protocol is one method:

```python
def render(self, width: int) -> list[Line]: ...
```

- `render` is a pure function of the component, `width`, and documented
  caches. A cache never changes the answer at one width.
- `Revisioned.revision()` returns a value snapshot of **every** mutable input
  `render(width)` reads. Equal snapshots at one width mean equal rows. A
  snapshot costs far less than the render it guards. `None` disables caching
  for open blocks.
- Interaction protocols:

```python
class Clickable(Protocol):
    def click(self, row: int, col: int) -> bool: ...

class Activable(Protocol):
    def activate(self) -> bool: ...

class Focusable(Protocol):
    focused: bool

class Hoverable(Protocol):
    hover: bool
    # optional: hover_at(row, col) -> bool

class Container(Protocol):
    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None: ...

class Controller(Protocol):
    def handle(self, event: Event) -> bool: ...   # True = consumed

class Resultful(Protocol):
    def take_result(self) -> object | None: ...   # read once; clears

class Revisioned(Protocol):
    def revision(self) -> object: ...
```

- `handle` means **consumed**, everywhere. A tier that only needs a repaint
  calls `tui.refresh()` itself; it does not overload the return value.
- Cursor widgets share one vocabulary: `index: int`, `select(index) -> bool`,
  `move(delta) -> bool`, `home()`, `end()`, `activate() -> bool`;
  multi-select adds `toggle() -> bool`.
- `selected` reads the current value. A one-shot result is read with
  `take_result() -> T | None`, which clears it.
- Wrappers that hold a child expose it through `child_at` (`Row`, `Column`,
  `Padding`, `Panel`, `Delegate`, `Dialog`, `Collapsible`, `ComboBox`,
  `ScrollView`, `Form`).
- Every vertical row widget resolves its band through
  `theme.rows.band(active=..., hovered=..., focused=..., selected=...,
  marked=..., disabled=...)`. Precedence is `disabled > hovered >
  (active ? (focused ? active : inactive)) > selected > marked > base`.
  A control resolves through `theme.controls.band(...)`
  (`disabled > active > focused > hovered > base`).
- Glyph-carrying widgets take `glyphs: Glyphs`; a mark is content, so a
  host can change it without changing styles. `""` turns a mark off and
  collapses its seat.
- `MenuBar` is a clamped horizontal strip; `ContextMenu` is a `Select`
  preset for a modal-mounted menu. Both settle their result through
  `take_result()`.
- `CommandRegistry` lives in `motui.commands`, not `motui.widgets`; its
  `options()` method is the `CommandPalette` bridge. The clipboard capability is
  the runtime-checkable `Clipboard` protocol
  (`ScreenClipboard` / `MemoryClipboard`).
- Interactive widgets carry `disabled`; text fields carry `read_only`. A
  disabled widget renders its disabled band and refuses activation. A
  read-only field ignores routed events without touching its buffer.
- `Input(text=...)` and `Editor(text=...)` seed their buffer; `text` is
  readable and writable. The text caret's style is `caret_style`; a row's
  engaged band is `active_style`.
- `Modal` and `CommandPalette` are controllers, not components. They accept any
  panel with `render`, `click`, `handle` and `take_result`.
- `Spinner` implements `render(width)`; the host decides when to advance it.

## 7. Focus, selection and overlays

- One `FocusManager` owns widget focus: `add`, `remove`, `focus`,
  `focus_next`, `focus_previous`, `focused`, `handle`, `click`, and
  `push_trap` / `pop_trap` for nested modals. Its constructor focuses nothing
  and writes no target's flag.
- Pane focus and widget focus are separate: the frame owns the focused
  pane, the focus manager owns the widget.
- A modal traps focus and restores it on close. Two modals stack; closing
  the top one returns focus to the one below.
- Document selection is a pair of document-space anchors
  (`Selection.between`). It is painted as an overlay with `theme.text.selection`,
  and `Find` uses the same token. A width change clears it.
- Selection stays inside one pane; `tui.selection_pane` names its document.
- Overlays have explicit layers:
  `background < content < selection < chrome < overlay < modal < tooltip
  < toast`.
  Same-layer overlays paint in registration order. An unknown layer raises
  `ValueError`. A pane-relative overlay never writes outside its pane.
- The shipped controllers register at construction and unregister through an
  idempotent `detach()`.

## 8. Layering

```
kernel  ->  keys  ->  widgets  ->  commands
                               ->  interaction  ->  app
```

- `kernel` imports the standard library and `wcwidth` only. It never imports
  `keys`, `widgets`, `interaction` or `app`.
- `keys` imports `kernel`.
- `widgets` imports `kernel` and `keys.keymap`.
- `commands` imports `widgets.choice` only.
- `interaction` imports `kernel` and the `Host` protocol. It does not import
  `app` or `widgets`.
- `app` may import anything; `testing` imports `app` and `kernel`.
- `Host` is the narrow driver surface the interaction tiers see:

```python
class Host(Protocol):
    screen: Screen
    frame: Frame
    document: Document
    selection: Selection | None
    selection_pane: Pane | None
    scroll_keys: dict[str, int]
    painter: Painter

    def refresh(self) -> None: ...
    async def read_event(self) -> Event | None: ...
    def clock(self) -> float: ...
    def every(self, seconds: float, fn: Callable[[], object]) -> EveryHandle: ...
    def hit(self, x: int, y: int) -> Hit | None: ...
    def reveal(self, bid: str, row: int) -> bool: ...
    def set_selection(self, selection: Selection | None, *, pane=None) -> None: ...
    def visible_range(self, pane=None) -> RowRange | None: ...
    def copy_to_clipboard(self, text: str) -> bool: ...
    def make_input(self, **kwargs: object) -> QueryInput: ...
    def make_autocomplete(self, options: Sequence[object], **kwargs: object) -> FilterList: ...
```

- `interaction` builds its query rows through `Host.make_input` and
  `Host.make_autocomplete` rather than importing `widgets`. The two return
  types are the narrow protocols `QueryInput` / `FilterList`, and
  `FilterList.take_result` answers an `OptionLike`; all three live in
  `motui.kernel.host`.

## 9. Caching

- `Block.rows(width)` is the one cached read of a block's rows.
- A sealed block caches by width. An open block caches only when its
  component is `Revisioned` and `revision()` is not `None`.
- Component-internal caches are render accelerators, not a second source of
  truth; their key must be covered by `revision()` or they must be bypassed
  when the block cache cannot see the change.
- `Painter.rows` is exactly `screen.height` rows after a paint.

## 10. Naming charter

| Concept | Name |
|---|---|
| Read one input | `TUI.read_event()` |
| End the session | `TUI.exit()` |
| Mark dirty | `TUI.refresh()` |
| Hit a cell | `TUI.hit(x, y)` |
| Deepest component | `TUI.hit_leaf(x, y)` |
| Pane at a cell | `TUI.pane_at(x, y)` |
| Pin a frame region | `TUI.dock(viewport, edge=..., size=...)` |
| Visible body rows | `TUI.visible_range()` |
| One-shot result | `take_result()` |
| Cursor position | `index` (not `active`) |
| Current value | `selected` |
| Text caret style | `caret_style` |
| Row engaged band | `active_style` |
| Window budget | `max_rows` |
| Event source | `EventSource` |
| Mouse button | `button: str` |
| Key identity | `KeyEvent.key` |
| Widget focus | `FocusManager` |

## 11. Non-goals

- A Textual-style retained widget tree, message bus or CSS-like layout.
- Charts, date/colour pickers, a grid layout engine, draggable split
  dividers, cross-pane selection, horizontal wheel scrolling.
- Full UAX #29 grapheme segmentation; runtime colour query/response.
- A document memory cap.
- Backward-compatibility shims. A removed name is deleted with its last
  consumer.

## 12. Gates

A change lands only when:

1. `uv run pytest -q -p no:cacheprovider` is green.
2. `uv run python tools/golden.py --check` reports every topic frame
   matching.
3. `uv run python tools/framebench.py` exits 0 and the render hash is
   reported.
4. Both piped demo entries exit 0:
   `python -m motui < /dev/null` and `python -m motui --pages`.
5. The public facade pin (`tests/test_api_root.py`) matches the intended
   surface.
6. The import graph still matches §8.
