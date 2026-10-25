# Migration: 1.x to 2.0

2.0 is a breaking release. There are no shims or forwarding modules: a
removed name is gone, and this page is the one place that maps the old
vocabulary to the new one. The current API is described by
[CONTRACT](CONTRACT.md), [WIDGETS](WIDGETS.md) and [ARCHITECTURE](ARCHITECTURE.md).

## 1. One-page name table

| 1.x | 2.0 | Notes |
|---|---|---|
| `render(width: int) -> list[Line]` | `render(c: Constraints) -> Surface` | `Constraints` carries `width` and an optional `max_height` |
| `Block` | `Section` | `Section.widget` (also `.component`), `.placement`, `.sizing` |
| `pin="top"` / `pin="bottom"` | `placement=Placement.TOP` / `Placement.BOTTOM` | `pin=` still folds into `placement` at the document doors |
| `TUI` | `Runtime` + `Workspace` + `Terminal` | `App.runtime`, `App.workspace`, `App.terminal` |
| `App.tui` | `App.runtime` (or `.workspace`, `.terminal`) | |
| `Revisioned.revision()` | automatic `Widget.touch()`; an optional `revision()` snapshot | the section row cache consumes the snapshot |
| `Themed` | `Widget` + `theme` / `styles`, resolved through `Widget.group(name)` | there is no `style()` accessor |
| `take_result()` | `take()` | reading clears; `None` means nothing pending |
| `Resultful` | `HasResult` (`motui.widgets.base`) | runtime-checkable protocol |
| `handle(event)` | `on_key` / `on_mouse` / `on_paste` / `on_resize` / `on_focus` | typed hooks |
| `Clickable` / `Activable` / ... | `clickable` / `activatable` / `focusable` / `hoverable` | capability attributes |
| `Clickable.click(row, col)` | `on_click(pos: Pos)` | |
| `ScrollView` | `ScrollPanel(axis="y" \| "x" \| "both")` | `ScrollView` is no longer shipped |
| `ScrollState` | `Scroll` / `ScrollAxis` | `ScrollPanel.scroll_state` still exposes `ScrollState` |
| `split("vertical")` | `split(Axis.X)` | `"vertical"` remains an accepted compatibility string |
| `split("horizontal")` | `split(Axis.Y)` | `"horizontal"` remains accepted |
| `ratios=` | `weights=` | `ratios` remains accepted as a fallback |
| `dock(edge="bottom")` | `dock(placement=Placement.BOTTOM)` | `edge` remains accepted |
| `EveryHandle` | `Timer` | returned by `Runtime.every` / `App.every` |
| `RowRange` | planned `RowSpan` did not land; the value remains `RowRange` | visible body rows |
| `fit` / `fill` / `fuse` / `overlay` / `rest` free functions | `Line.clip` / `reflow` / `pad` / `fill` / `merge_span` | internal `rest` remains in `motui.kernel.cell` |
| `cut_line` / `slice_line` / `wrap_line` | `Line.clip` / `reflow` | the functions remain at the kernel seam |
| `action_at` | `action_at` (kernel) or `Text.take()` | inline payload lookup |
| `highlight` / `extract` | `highlight` / `extract` in `motui.kernel.selection` | functions over a `Selection` |
| `descend` / `descend_chain` | the same functions in `motui.kernel.document` | |
| `mark_prefix` | `MarkSet` + the glyph seat helpers | `mark_prefix` is no longer facade-exported |
| `visible_width` | `text.width` | `visible_width` remains a kernel alias |
| `Command(name, description, ...)` | `Command(name=..., group=..., description=..., keys=..., handler=...)` | keyword-only; `group` is first-class |
| `open_palette(list[object])` | `open_palette(registry)` | a plain option list still works |
| `Table(wrap=True/False)` | `Table(cell_wrap=WrapMode.WORD)` or `WrapMode.OVERFLOW` | `OVERFLOW` for a horizontal `ScrollPanel` |
| `App(mouse=, hover=, color_mode=, focus_events=, sync=, keys=, screen=)` | `App(terminal=TerminalOptions(...))` | the old arguments are folded into `TerminalOptions` |

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
`screen` are fields of the same value.

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
the whole `Component` protocol.

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
widget reads a group at render time through `self.group(name)`, so a theme
assignment repaints an already mounted UI. Build variants with
`dataclasses.replace` or `Theme.from_palette(ColorPalette(...))`.

### 2.7 Tests

```python
# 1.x
tui = headless_tui(80, 24)
tui.paint()

# 2.0
from motui import Text, headless_tui
from motui.testing import Emulator

tui = headless_tui(80, 24)     # a real Runtime over a recording screen
tui.add(Text("hello"))
tui.paint()

assert "hello" in "\n".join(row.text for row in tui.rows)

screen = Emulator(80, 24)
screen.feed(tui.screen.output)
assert screen.cell(0, 0).char == "h"
```

`Runtime.advance(dt)` replays time without sleeping. `ScriptedEvents`
replays a fixed event sequence. `snapshot(tui)` renders the document as
structured plain text.

## 3. Removed names

These are gone from the public surface; no alias is provided.

`TUI`, `App.tui`, `take_result`, `Resultful`, `set_focus_targets`, `Themed`
(as a public base), `Revisioned` (as a public protocol), `EveryHandle`,
`ClampedCursor`, `mark_prefix` (facade export), `ScrollView`, `Block`, the
`core/` package, public `ansi.*` exports, the free `fit` / `fill` / `fuse` /
`overlay` / `rest` functions as an application API, and
`Table(wrap=bool)`.

Implementation names that still exist at their module for internal use
(`Revisioned` in `motui.kernel.document`, `Themed` in
`motui.kernel.theme`) are not facade exports and are not part of the
application contract.

## 4. Compatibility entries still present

The release keeps a small number of aliases and string entries so existing
calls do not break mid-migration. They are documented, not recommended:

| Entry | Status |
|---|---|
| `pin="top"` / `pin="bottom"` | accepted by the document doors; prefer `placement=` |
| `split("vertical" \| "horizontal")` | accepted; prefer `Axis.X` / `Axis.Y` |
| `split(ratios=...)` | fallback when `weights` is absent |
| `dock(edge=...)` / `undock(edge)` | accepted; prefer `placement=` |
| `App(mouse=..., hover=..., keys=..., screen=...)` | folded into `TerminalOptions`; prefer `terminal=` |
| `open_palette(list)` | accepted; prefer a `CommandRegistry` |
| `RowRange` | still exported; the planned `RowSpan` rename did not land |
| `ScrollPanel.scroll_state` | still returns the mutable `ScrollState` |
| `visible_width`, `wrap_text`, `ellipsize_tail`, `cut_line`, `slice_line`, `action_at`, `wrap_line` | kernel module functions kept beside the value methods |

`Command`'s positional-argument compatibility shim and `App.remove`'s
string-or-section argument are scheduled for removal in the release wave;
new code should always use keywords and pass a `Section`.

## 5. Migration checklist

1. Replace `TUI` references with `App`/`Runtime`/`Workspace`/`Terminal`.
2. Pass `TerminalOptions` to `App`; map `mouse`/`hover` to `MouseMode`.
3. Change `render(width)` to `render(Constraints)` and return a `Surface`.
4. Replace `Block`/`pin` with `Section`/`Placement`; consume the `Section`
   returned by `add`.
5. Replace `take_result()` with `take()` and `Resultful` with `HasResult`.
6. Replace `handle(event)` with the typed hooks and capability flags.
7. Replace `ScrollView` with `ScrollPanel`; choose `axis=`.
8. Replace `split`/`dock` strings with `Axis`/`Placement` (the strings are
   temporary compatibility entries).
9. Replace `Table(wrap=...)` with `cell_wrap=...`.
10. Update tests to `headless_tui` + `Runtime.advance` + `Emulator`.
