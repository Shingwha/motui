# Migration: 1.x to 2.0

2.0 is a breaking release. There are no shims or forwarding modules: a
removed name is gone, and this page is the one place that maps the old
vocabulary to the new one. The current API is described by
[CONTRACT](CONTRACT.md), [WIDGETS](WIDGETS.md) and [ARCHITECTURE](ARCHITECTURE.md).

## 1. One-page name table

| 1.x | 2.0 | Notes |
|---|---|---|
| `render(width: int) -> list[Line]` | `render(c: Constraints) -> Surface` | `Constraints` carries `width` and an optional `max_height` |
| `Block` | `Section` | `Section.id` and `Section.widget`; there is no `.component` alias |
| `pin="top"` / `pin="bottom"` | `placement=Placement.TOP` / `Placement.BOTTOM` | `pin=` is removed; a non-`Placement` raises `ValueError` |
| `TUI` | `Runtime` + `Workspace` + `Terminal` | `App.runtime`, `App.workspace`, `App.terminal` |
| `App.tui` | `App.runtime` (session) or `App.workspace` (content) | |
| `Revisioned.revision()` | automatic `Widget.touch()` / `widget.generation` | the section row cache reads `generation`; no snapshot method |
| `Themed` | `Widget` + `theme` / `styles`, resolved through `Theme.group(name)` | there is no `Themed` base or `style()` accessor |
| `take_result()` | `take()` | reading clears; `None` means nothing pending |
| `Resultful` | `HasResult` (`motui.widgets.base`) | runtime-checkable protocol |
| `handle(event)` | `on_key` / `on_mouse` / `on_paste` / `on_resize` / `on_focus` | typed hooks |
| `Clickable` / `Activable` / ... | `clickable` / `activatable` / `focusable` / `hoverable` | capability attributes |
| `Clickable.click(row, col)` | `on_click(pos: Pos)` | |
| `ScrollView` | `ScrollPanel(axis="y" \| "x" \| "both")` | `ScrollView` is no longer shipped |
| `ScrollState` | `Scroll` / `ScrollAxis` | `ScrollPanel.scroll` and `Viewport.scroll` answer `Scroll` |
| `RowRange` | `RowSpan(first, last)` (`motui.kernel.layout`) | inclusive screen-row range |
| `split("vertical")` | `split(Axis.X)` | strings are rejected with `ValueError` |
| `split("horizontal")` | `split(Axis.Y)` | strings are rejected with `ValueError` |
| `ratios=` | `weights=` | `ratios` is removed |
| `dock(edge="bottom")` | `dock(placement=Placement.BOTTOM)` | `edge` is removed |
| `EveryHandle` | `Timer` | returned by `Runtime.every` / `App.every` |
| `fit` / `fill` / `fuse` / `overlay` / `rest` free functions | `Line.clip` / `reflow` / `pad` / `fill` / `merge_span` | the old application-level functions are gone; `fuse`/`overlay`/`rest` remain kernel-private helpers |
| `cut_line` / `slice_line` / `wrap_line` | `Line.clip` / `reflow` | the module functions remain at the kernel seam |
| `action_at` | `action_at` (kernel) or `Text.take()` | inline payload lookup |
| `highlight` / `extract` | `highlight` / `extract` in `motui.kernel.selection` | functions over a `Selection` |
| `descend` / `descend_chain` | the same functions in `motui.kernel.document` | |
| `mark_prefix` | `MarkSet` + the glyph seat helpers | `mark_prefix` is no longer facade-exported |
| `visible_width` | `text.width` | `visible_width` remains a kernel alias |
| `Command(name, description, ...)` | `Command(name=..., group=..., description=..., keys=..., handler=...)` | keyword-only; `group` is first-class |
| `open_palette(list[object])` | `open_palette(registry: CommandRegistry)` | any other type raises `TypeError` |
| `Table(wrap=True/False)` | `Table(cell_wrap=WrapMode.WORD)` or `WrapMode.OVERFLOW` | `OVERFLOW` for a horizontal `ScrollPanel` |
| `App(mouse=, hover=, color_mode=, focus_events=, sync=, keys=, screen=)` | `App(terminal=TerminalOptions(...))` | the old arguments are removed, not folded |
| `App.remove(id)` | `App.remove(section)` | takes the `Section` value `add` answered |
| `set_focus_targets(...)` | `focusable = True` on widgets | the ring is derived from the tree |
| `ClampedCursor` | the per-view index attributes (`index`, `selected`) | no shared cursor value |
| `handle`-style demo topics / `Topic` registry | the five-scene showcase (`demo/`) | the topic tour is gone |

## 2. Recipes

### 2.1 App and terminal options

```python
# 1.x
app = App(theme=Theme.dark(), mouse=True, hover=True, throttle=0.03)

# 2.0
from motui import App, Theme
from motui.terminal import MouseMode, TerminalOptions

app = App(
    theme=Theme.dark(),
    terminal=TerminalOptions(mouse=MouseMode.MOVE),
    throttle=0.03,
)
```

`MouseMode.OFF` replaces `mouse=False`; `MouseMode.MOVE` replaces
`mouse=True, hover=True`; `MouseMode.DRAG` replaces `mouse=True,
hover=False`. `focus_events`, `sync`, `color_mode`, `stream`, `input` and
`screen` are fields of the same value. `App` accepts no other terminal
arguments.

### 2.2 Document, sections and panes

```python
# 1.x
block_id = app.add(Text("hello"))
component = app.get(block_id)
app.tui.split("vertical", ratios=(1, 2))
app.tui.dock(StatusLine(left=("ready",)), edge="bottom")

# 2.0
from motui.kernel import Axis
from motui.kernel.document import Placement

section = app.add(Text("hello"))
assert section.widget is app.get(section.id).widget
left, right = app.split(Axis.X, weights=(1, 2))
app.dock(StatusLine(left=("ready",)), placement=Placement.BOTTOM)
```

A fill is a sizing, not a separate document type:

```python
from motui.kernel.document import Sizing

app.add(game, sizing=Sizing.FILL)   # or: app.fill(game)
```

The content doors are `App`, `Workspace` and `Pane`; `Runtime` has no
`add`, `get`, `split`, `dock`, `fill` or `rows` of its own.

### 2.3 A custom component

```python
# 1.x
class Counter(Widget):
    def render(self, width):
        return [Line.from_text(f"count: {self.count}")]
    def handle(self, event):
        if event.key == "enter":
            self.count += 1
            return True
        return False

# 2.0
from motui.kernel import Constraints, Line, Surface
from motui.widgets import Widget

class Counter(Widget):
    focusable = True
    activatable = True
    keymap = {"enter": "activate"}

    def on_action(self, name: str) -> bool:
        if name != "activate":
            return False
        self.count += 1            # the setter calls touch()
        return True

    def render(self, c: Constraints) -> Surface:
        return Surface.clipped([Line.from_text(f"count: {self.count}")], c.width)
```

A pure renderer does not need `Widget`; one `render(c) -> Surface` method is
the whole `Component` protocol. A pure component is not cached; subclass
`Widget` when you want `touch()`/`generation` invalidation.

### 2.4 One-shot results and tree collection

```python
# 1.x
if (picked := select.take_result()) is not None:
    handle(picked)

# 2.0
if (picked := select.take()) is not None:
    handle(picked)

from motui.widgets.base import HasResult

for widget in app.walk():
    if isinstance(widget, HasResult) and (value := widget.take()) is not None:
        handle(value)
```

`None` means "no pending result"; `False`, `0` and `""` are real results.
State attributes (`selected`, `checked`, `text`, `open`) are not cleared by
`take()`.

### 2.5 A custom screen

```python
from motui.terminal import HeadlessScreen, Screen, TerminalOptions
from motui import App

class MyScreen(HeadlessScreen):
    def write(self, s: str) -> None:
        super().write(s)
        # forward, record or mirror the frame

app = App(terminal=TerminalOptions(screen=MyScreen(80, 24)))
```

Subclass `Screen` (directly or through `HeadlessScreen`). `enter`, `leave`,
`write`, `flush`, `refresh_size` and `close` are the lifecycle;
`copy_to_clipboard` has a declining default, so override it only if the
screen owns that write.

### 2.6 Theme and per-widget styles

```python
# 1.x
Widget(theme=...)

# 2.0
from dataclasses import replace
from motui import DEFAULT_THEME, List, Style, Styles

rows = replace(DEFAULT_THEME.rows, active=Style(bg="#264f78"))
listing = List(items, styles=Styles(rows=rows))
```

`Styles` replaces whole role groups; `theme` stays the inherited value. A
widget reads a group at render time through `self.group(name)`, which calls
`Theme.group`; a theme assignment repaints an already mounted UI. Build
variants with `dataclasses.replace` or `Theme.from_palette(ColorPalette(...))`.

### 2.7 Tests

```python
# 1.x
tui = headless_tui(80, 24)
tui.paint()

# 2.0
from motui import Text, headless_tui
from motui.testing import Emulator

tui = headless_tui(80, 24)     # a Harness: content -> workspace, session -> runtime
tui.add(Text("hello"))
tui.paint()

assert "hello" in "\n".join(row.text for row in tui.rows)

screen = Emulator(80, 24)
screen.feed(tui.screen.output)
assert screen.cell(0, 0).char == "h"
```

`tui.runtime` is the `Runtime`, `tui.workspace` the `Workspace`, and
`tui.rows` resolves to `workspace.rows`. `Runtime.advance(dt)` replays time
without sleeping. `ScriptedEvents` replays a fixed event sequence.
`snapshot(tui)` renders the document as structured plain text.

## 3. Removed names

These are gone from the public surface and from the source; no alias is
provided.

`TUI`, `App.tui`, `take_result`, `Resultful`, `set_focus_targets`,
`Themed`, `Revisioned`, `EveryHandle`, `ClampedCursor`, `mark_prefix` (as a
facade export), `ScrollView`, `ScrollState`, `RowRange`, `Block`, the
`core/` package, public `ansi.*` exports, the free `fit` / `fill` / `fuse` /
`overlay` / `rest` functions as an application API, `Table(wrap=bool)`,
`pin=`, `Section.component`, `split("vertical"|"horizontal")`, `ratios=`,
`dock(edge=...)`, `open_palette(list)`, and the 1.x `App` constructor
arguments.

`Frame.revision` remains, but it counts structural frame mutations (split,
close, chrome, overlay, band); it is not a row cache and has no relation to
the removed `Revisioned` protocol.

## 4. Migration checklist

1. Replace `TUI` references with `App`/`Runtime`/`Workspace`/`Terminal`.
2. Pass `TerminalOptions` to `App`; map `mouse`/`hover` to `MouseMode`.
3. Change `render(width)` to `render(Constraints)` and return a `Surface`.
4. Replace `Block`/`pin` with `Section`/`Placement`; consume the `Section`
   returned by `add`.
5. Replace `take_result()` with `take()` and `Resultful` with `HasResult`.
6. Replace `handle(event)` with the typed hooks and capability flags;
   replace `revision()` with automatic `touch()`/`generation`.
7. Replace `ScrollView` with `ScrollPanel`; choose `axis=`. Replace
   `ScrollState` reads with `Scroll`/`ScrollAxis`; `RowRange` with
   `RowSpan`.
8. Replace `split`/`dock` strings with `Axis`/`Placement`; there are no
   compatibility entries.
9. Replace `Table(wrap=...)` with `cell_wrap=...`; pass a registry to
   `open_palette`.
10. Update tests to `headless_tui` (a `Harness`) + `Runtime.advance` +
    `Emulator`; the shipped examples are quickstart, code and wide_table.
