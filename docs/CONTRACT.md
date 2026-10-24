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
- `TUI.read_event()` is a **pure read**: it returns the next `Event`, or
  `None` at EOF and on a non-live screen. It performs no scroll or focus
  policy. The default wheel/page/focus routing lives in `App`.
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
- `Hit` carries `pane`, `block`, `row`, `col` and `chain`, where `chain` is
  the ancestor walk `descend_chain` resolved: one
  `(component, row, col)` per level, outermost first. `leaf`, `leaf_row`
  and `leaf_col` are derived properties over the chain's tail; `pane_id` is
  a read-only convenience property.
- `Container.child_at(row, col)` answers from the container's **last
  render**. It may decline (`None`), and it proxies no controller verb.
- Block ids are unique across the whole frame, not only within one
  document.

## 3. Driver lifecycle

`App` is the high-level entry; `TUI` is the low-level driver beneath it.

```python
app.run()                        # sync entry; owns the loop
await app.run_async()            # async entry; owns the loop
await app.run_session(body)      # run a coroutine, then tear down
app.quit()                       # end the session now
app.on_start(); app.on_stop()    # once before / after the loop
```

- `App` mounts focus, pointer, gesture, toasts, tooltip, find/palette and
  owns the dispatch order. `auto=False` mounts none of them.
- `App.add`, `get`, `remove`, `split`, `dock`, `undock`, `focus`,
  `focus_next`, `focus_previous`, `set_focus_targets`, `bind`, `toast`,
  `open_modal`, `open_palette` and `find` are the policy surface. `app.tui`
  is the driver.
- `TUI` keeps the same run entry points for a host that wants its own
  loop: `run`, `run_async`, `run_session`, `exit`, `refresh`,
  `read_event`.
- `exit()`/`quit()` unblocks a pending `read_event()`, cancels the pump and
  lets teardown run. It is safe from any task.
- A driver can run more than once. Each run resets timers, selection and the
  painter's diff base; an owned key source is closed at teardown and
  reattached on the next run.
- `TUI.screen`, `TUI.frame`, `TUI.document`, `TUI.viewport` and `TUI.painter`
  are read-only views. `TUI.refresh()` is the public dirty signal;
  `TUI.paint()` is the low-level immediate paint.
- `TUI.screen.copy_to_clipboard(text)` is the clipboard primitive and
  flushes.
- `TUI.add` returns the block id; `TUI.get` and `TUI.remove` return the
  component.

## 4. Panes, documents and docks

- A `Pane` is a mutable runtime object with a stable, monotonically
  allocated id that is never reused. It owns one `Viewport`, therefore one
  `Document`.
- Chrome is an edge band a pane grants by budget negotiation: `size` cells
  come off the pane's edge and the document re-wraps at the reduced width.
  A band also names the region of the pane it decorates, `Chrome.scope`:
  `"pane"` (the default) spans the pane's rectangle -- a divider, a border;
  `"body"` spans the pane's scrolling window, the rows between its fixed
  regions -- a scrollbar. A body band is a `left`/`right` band only: a
  `top`/`bottom` band owns its rows, so it cannot share the window's.
- `Pane.inner_rect` is the rectangle the viewport used; `Pane.band(chrome)`
  is the rectangle that chrome was granted -- the whole edge for a `pane`
  band, the window's rows for a `body` band, and `None` before the pane has
  been composed (or when the window has no rows). The compositor paints the
  very same rectangle, so a band's hit test and its pixels cannot disagree.
- Document operations are pane-scoped: `tui.pane(id).add/get/remove(...)`,
  or `tui.add(..., pane=...)`. With no explicit pane the **primary** pane
  (or the first content pane in paint order) is the target; focus routes
  input, not content ownership, so a click never changes where a producer's
  blocks land.
- `tui.dock(component, edge="top"|"bottom", size=None)` pins a frame-level
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
  background slot, and falls back to dark.
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

Every themed widget inherits `Widget` and takes `theme: Theme | None` plus
one `styles: Styles | None`; there are no per-token `*_style` parameters and
no `focused=` constructor flag.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Styles:
    text: TextStyles | None = None
    surfaces: SurfaceStyles | None = None
    borders: BorderStyles | None = None
    controls: ControlStyles | None = None
    rows: RowStyles | None = None
    status: StatusStyles | None = None
    content: ContentStyles | None = None
    chrome: ChromeStyles | None = None
    overlays: OverlayStyles | None = None
    syntax: SyntaxStyles | None = None
```

- A non-`None` `Styles` field replaces that whole role group for the widget;
  a `None` field inherits the theme's group.
- Styles resolve at **render time**: `self.group(name)` returns the
  override or the theme's group, and `theme`/`styles` must be part of
  `revision()` so the row cache sees a change.
- `App.theme` propagates to mounted `Widget`s whose `theme is None`; an
  explicit `theme=` stays a local override. `Text` is the core exception:
  a render-only component with `style=` and `theme=`, not a `Widget`.

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
- `Component` is the only mandatory public protocol. The capability
  protocols (`Clickable`, `Activable`, `Focusable`, `Hoverable`,
  `Container`, `Controller`, `Resultful`, `Revisioned`) are implementation
  vocabulary; they are not re-exported from `motui.core`, `motui.widgets`
  or the root.
- `Widget` supplies the interaction verbs as no-ops; a subclass overrides
  only the ones it takes:

```python
class Widget:
    theme: Theme | None
    styles: Styles | None
    focused: bool
    hover: bool

    def group(self, name: str) -> object: ...   # styles override, else theme
    def handle(self, event: Event) -> bool: ...    # True = consumed
    def click(self, row: int, col: int) -> bool: ...
    def drag(self, row: int, col: int, kind: str) -> bool: ...
    def hover_at(self, row: int, col: int) -> bool: ...
    def activate(self) -> bool: ...
    def take_result(self) -> object | None: ...    # read once; clears
    def revision(self) -> object | None: ...       # None disables caching
```

- `Revisioned.revision()` returns a value snapshot of **every** mutable input
  `render(width)` reads. Equal snapshots at one width mean equal rows. A
  snapshot costs far less than the render it guards. `None` disables caching.
  A `Widget` subclass returns `theme` and `styles` in that snapshot.
- `handle` means **consumed**, everywhere. A tier that only needs a repaint
  calls `tui.refresh()` itself; it does not overload the return value.
- Cursor widgets share one vocabulary: `index: int`, `select(index) -> bool`,
  `move(delta) -> bool`, `home()`, `end()`, `activate() -> bool`;
  `MultiSelect` adds `toggle() -> bool`.
- `Select` is single-choice. `MultiSelect` is the marked variant with
  `marked` and `toggle()`; `CheckboxGroup` is a `MultiSelect` preset.
- `selected` reads the current value. A one-shot result is read with
  `take_result() -> T | None`, which clears it.
- Wrappers that hold a child expose it through `child_at` (`Row`, `Column`,
  `Padding`, `Panel`, `Dialog`, `Collapsible`, `ComboBox`, `ScrollView`,
  `Form`).
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
- `CommandRegistry` lives in `motui.app`, not `motui.widgets`; its
  `options()` method is the `CommandPalette` bridge. The clipboard capability
  is the runtime-checkable `Clipboard` protocol
  (`ScreenClipboard` / `MemoryClipboard`) in `motui.core`.
- Interactive widgets carry `disabled`; text fields carry `read_only`. A
  disabled widget renders its disabled band and refuses activation. A
  read-only field ignores routed events without touching its buffer.
- `Input(text=...)` and `Editor(text=...)` seed their buffer; `text` is
  readable and writable. Caret, prompt, selection and hover styles come from
  the `text`, `content` and `surfaces` role groups (or a `styles=` group
  override); there is no `caret_style=` or `active_style=` argument.
- `Modal` and `CommandPalette` are controllers in `motui.app`, not
  components. They accept any panel with `render`, `click`, `handle` and
  `take_result`.
- `Spinner` implements `render(width)`; the host decides when to advance it.
- `ScrollView(bar=True)` reserves its last column for a draggable thumb,
  track paging and wheel scrolling. The pane-level `Scrollbar` remains the
  chrome controller; both read `ScrollState` and use its one thumb formula.
  `Scrollbar` is a `body`-scoped chrome: its strip, thumb, drag mapping and
  press region are the pane's scrolling window, so rows a pane pins above
  or below that window keep the column empty and route no press.
- `Table(..., wrap=True, max_col_width=40, min_col_width=3)` wraps long
  cells; `wrap=False` keeps the old ellipsis behavior.

## 7. Focus, selection and overlays

- `App` mounts one `FocusManager` by default and owns the dispatch order:
  palette, modal, find, toasts, mounted controllers, wheel, mouse (drag,
  gesture, pointer, pane focus), focused widget, page keys, `bind`, `tab`,
  then the host hooks.
- `FocusManager` owns widget focus: `add`, `remove`, `focus`,
  `focus_next`, `focus_previous`, `focused`, `handle`, `click`, and
  `push_trap` / `pop_trap` for nested modals. Its constructor focuses nothing
  and writes no target's flag. `App.focus`, `App.focus_next`,
  `App.focus_previous` and `App.set_focus_targets` are the App-level
  surface; a `TUI` host mounts the manager itself.
- Pane focus and widget focus are separate: the frame owns the focused
  pane, the focus manager owns the widget. The App's mouse tier focuses the
  pane on a press.
- A focus owner is a widget the App registers as a target. A compound owner
  (`owns_focus = True`, e.g. `Form`, `ComboBox`) keeps its descendants out
  of the ring and routes their keys itself. A click runs the leaf's
  `click` and every ancestor's `focus_at`; the focus manager focuses the
  nearest registered ancestor, and only a non-container leaf activates on a
  repeat click.
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
core  ->  widgets  ->  app
testing (above app and core)
```

- `core` imports the standard library and `wcwidth` only. It never imports
  `widgets` or `app`.
- `widgets` imports `core`.
- `app` may import `core` and `widgets`; `testing` imports `app` and
  `core`.
- There is no `motui.kernel`, `motui.keys`, `motui.interaction` or
  `motui.commands` namespace, and no `Host` protocol. `App` composes `TUI`
  and the controllers directly.
- `motui.core`, `motui.widgets`, `motui.app` and `motui.testing` are the
  four public facades; the root is a curated 41-name subset of them.

## 9. Caching

- `Block.rows(width)` is the one cached read of a block's rows. It caches
  only when the component implements `Revisioned` and `revision()` is not
  `None`, keyed by `(width, revision)`.
- A component without a snapshot re-renders on every read; there is no
  sealed state and no `BlockState`.
- Component-internal caches are render accelerators, not a second source of
  truth; their key must be covered by `revision()` or they must be bypassed
  when the block cache cannot see the change.
- `Painter.rows` is exactly `screen.height` rows after a paint.

## 10. Naming charter

| Concept | Name |
|---|---|
| Read one input | `TUI.read_event()` (pure) |
| End the session | `App.quit()` / `TUI.exit()` |
| Mark dirty | `TUI.refresh()` |
| Hit a cell | `TUI.hit(x, y)` |
| Deepest component | `Hit.leaf`, `TUI.hit_leaf(x, y)` |
| Pane at a cell | `TUI.pane_at(x, y)` |
| Focus a widget | `App.focus(target)` |
| Bind a key | `App.bind(key, callback)` |
| Pin a frame region | `App.dock(component, edge=..., size=...)` |
| Visible body rows | `TUI.visible_range()` |
| One-shot result | `take_result()` |
| Widget style override | `styles=Styles(...)` |
| Cursor position | `index` (not `active`) |
| Current value | `selected` |
| Window budget | `max_rows` |
| Event source | `EventSource` |
| Mouse button | `button: str` |
| Key identity | `KeyEvent.key` |
| Widget focus | `FocusManager` (mounted by `App`) |

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
5. The public facade pin (`tests/test_api.py`) matches the intended
   surface.
6. The import graph still matches §8.
