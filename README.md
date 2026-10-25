# motui

[![ci](https://github.com/Shingwha/motui/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Shingwha/motui/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/motui)](https://pypi.org/project/motui/)
[![python](https://img.shields.io/pypi/pyversions/motui)](https://pypi.org/project/motui/)
[![license](https://img.shields.io/pypi/l/motui)](LICENSE)

A layered, full-screen terminal UI toolkit with pure values at the bottom and a
component tree on top. You describe a document of addressable sections;
motui lays them out, scrolls them, and paints only the rows that changed on
the terminal's alternate screen. It ships parts, not an application: a
component library, a default interaction policy, and the runtime beneath
them.

- **Values first.** Geometry, rows, surfaces, styles, scroll values and
  selection are frozen values in `motui.kernel`, with no terminal I/O.
- **One render method.** Every component answers
  `render(Constraints) -> Surface`; nothing else is promised, so a pure
  renderer never has to inherit a base class.
- **Explicit interaction.** Widgets declare capabilities
  (`focusable`, `clickable`, `hoverable`, `activatable`) and override typed
  hooks (`on_key`, `on_click`, `on_action`, ...). There is no untyped
  `handle` fallback.
- **Explicit tree.** `Widget.parent`, `Widget.children`, `walk()` and
  `touch()` replace attribute sniffing and manual invalidation.

Runtime dependency: **`wcwidth` only**. Python **3.12+**.

## Install

```bash
pip install motui      # or: uv add motui
```

The wheel carries its own demo, so `python -m motui` works right away.

## Quickstart

The smallest app: a `Text` row and an `Input`, painted once headless. The
runnable copy is `examples/quickstart.py`.

```python
from motui import App, Input, Text
from motui.terminal import HeadlessScreen, TerminalOptions

app = App(terminal=TerminalOptions(screen=HeadlessScreen(60, 6)), auto=False)
app.add(Text("Hello, motui."))
app.add(Input("type here"))
app.paint_now()
for row in app.workspace.rows[:3]:
    print(row.text)
```

What each piece did:

| Piece | Job |
|---|---|
| `App` | composes the runtime, the workspace and the terminal; `run()` owns the loop |
| `TerminalOptions` | the one terminal configuration: stream, input, mouse mode, paste, focus events, color mode, sync and the headless `screen` |
| `app.add(component)` | append a section and answer the `Section` the caller keeps |
| `app.workspace.rows` | the painted rows; `app.workspace` owns the frame and its content |
| `app.focus(target)` | focus a section id or a mounted component; `tab` cycles the tree-derived ring |
| `app.bind(key, callback)` | run a callback after the focused control and the default tiers decline the key |
| `render(Constraints) -> Surface` | a component's only rendering obligation |
| `take()` | read a one-shot widget result; the read clears it |

## Capability matrix

| Goal | What ships | Where it runs |
|---|---|---|
| Playable game | `Canvas` cell grid, `Sizing.FILL`, `app.every`, `app.bind` | `python -m motui --scene breakout` |
| Live dashboard | `Sparkline`, `ProgressBar`, `Table`, `App.every`/`invalidate` | `python -m motui --scene dashboard` |
| Wide table | `Table(cell_wrap=WrapMode.OVERFLOW)` inside `ScrollPanel(axis="x")` | `examples/wide_table.py` |
| Two-axis code view | `WrapMode.OVERFLOW` inside `ScrollPanel(axis="both")` | `examples/code.py` |
| Streaming document | `Markdown.text += chunk`, section generation cache, `ScrollPanel` | below |
| Split IDE | `split(Axis.X)`, `dock(placement=Placement.BOTTOM)`, `Panel`, `StatusLine` | [ARCHITECTURE](docs/ARCHITECTURE.md) |
| Forms and dialogs | `Form`/`Field`, `Input`/`Editor`, `Dialog` through `App.open_modal` | [WIDGETS](docs/WIDGETS.md) |

The three shipped examples are `quickstart`, `code` and `wide_table`. The
interactive demo is one page with five scenes: splash, menu, Breakout,
Dashboard and a component Gallery.

Wide content is the one horizontal-scroll case: `ScrollPanel(axis="x"` or
`"both")` windows a component that may render wider than its constraints
(`WrapMode.OVERFLOW`). Document-flow horizontal scrolling is a 2.x goal.

## The five concepts

**1. Kernel values.** `Rect`, `Size`, `Pos` and `Axis` are geometry.
`Cell`, `Segment`, `Line` and `Surface` are the row model. `Constraints`,
`Scroll`, `ScrollAxis` and `ScreenLayout` are layout. `Section`, `Document`,
`Placement` and `Sizing` are the document model. `Style`, `Theme`, `Styles`,
`Glyphs` and `Border` are styling. The data values are frozen; `Section`
and `Document` manage identity and order. All live in `motui.kernel`; the
package imports no `os`, `sys`, `io`, `ctypes`, `termios`, `tty`, `select`
or `asyncio`.

```python
from motui.kernel import Constraints, Line, Surface, WrapMode

row = Line.from_text("hello").clip(WrapMode.ELLIPSIS, 4)  # "hel..."
surface = Surface.of([row], width=4)                       # clipped, then padded
```

**2. Constraints and Surface.** A component is asked for a width and an
optional height budget, and answers rows at one content width.

```python
from motui.kernel import Constraints, Line, Surface


class Banner:
    def render(self, c: Constraints) -> Surface:
        rows = [Line.from_text("motui").clip("ellipsis", c.width)]
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)
```

`Surface.of` guarantees every row is at most `width` columns and pads short
rows; `Surface.clipped` keeps short rows short (the byte-stable builder).
`OVERFLOW` is the one wrap mode that may return a row wider than the limit;
a container clips it at its edge.

**3. Widgets and hooks.** `Widget` adds the explicit tree, automatic
invalidation and no-op interaction hooks. A subclass overrides only what it
takes and returns `True` when it consumed the input.

```python
from motui.kernel import Constraints, Line, Surface
from motui.widgets import Widget


class Counter(Widget):
    focusable = True
    activatable = True
    keymap = {"enter": "activate", "space": "activate"}

    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def on_action(self, name: str) -> bool:
        if name != "activate":
            return False
        self.count += 1          # the setter calls touch()
        return True

    def render(self, c: Constraints) -> Surface:
        return Surface.of([Line.from_text(f"count: {self.count}")], c.width)
```

Assigning any public attribute calls `touch()`, which bumps this widget's
`generation` and every ancestor's. Mutating a list in place cannot be seen;
call `touch()` yourself in that case.

**4. Sections.** `Document` holds `Section` values: a stable id, a widget,
a `Placement` (`FLOW`, `TOP`, `BOTTOM`) and a `Sizing` (`NATURAL`, `FILL`).
`app.add(...)` and `workspace.add(...)` answer the section.

```python
from motui import App, Text
from motui.kernel.document import Placement, Sizing

app = App()
header = app.add(Text("header"), placement=Placement.TOP)
canvas = app.add(game, sizing=Sizing.FILL)   # or: app.fill(game)
```

At most one `FILL` section is allowed, it must be in the flow, and no flow
section may follow it. In this release `Fill` is the document form
(`sizing=Sizing.FILL`), not a separate pane-content union.

**5. Terminal options.** `App(terminal=TerminalOptions(...))` is the one
terminal configuration. `MouseMode` is `OFF`, `BUTTON`, `DRAG` or `MOVE`;
`color_mode="auto"` probes the environment once; `screen=` is the
testing/headless escape hatch.

```python
from motui import App
from motui.terminal import MouseMode, TerminalOptions

app = App(terminal=TerminalOptions(mouse=MouseMode.DRAG, paste=True))
```

There are no separate `mouse=`, `hover=`, `screen=` or `keys=` arguments on
`App`; every switch lives in `TerminalOptions`.

## The 60-second pipeline

```
terminal bytes --KeyDecoder--> Event --Router (DEFAULT_HANDLERS)--> palette /
                                                      modal / find / toasts /
                                                      controllers / wheel /
                                                      drag / mouse / focus /
                                                      page keys / bindings /
                                                      host hooks
                                                            |
                         Component.render(Constraints) -> Surface
                                                            |
                              Section.rows (generation cache) -> Viewport.layout
                                                            |
                                               ScreenLayout (rows + ownership)
                                                            |
                                  Frame.compose (panes, docks, chrome, overlays)
                                                            |
                                  Painter.paint (per-row diff, one flush)
                                                            v
                                                          Screen
```

An unchanged frame writes zero bytes. A non-live `Screen` keeps the logical
rows and stays silent, which is how piped runs and tests work.

## Components

The root is a curated 40-name import line. Everything else is public at its
own layer:

```python
from motui import App, Input, Markdown, Table          # the curated root
from motui.widgets import Canvas, Panel, ScrollPanel   # the complete library
from motui.kernel import Style, Line, Selection        # the kernel seam
from motui.kernel import DEFAULT_INPUT_KEYMAP          # decoder and keymaps
from motui.app import Runtime, Workspace, Scrollbar    # runtime and controllers
from motui.terminal import TerminalOptions, Screen     # terminal seam
from motui.testing import Emulator, headless_tui       # test helpers
```

The component families are text (`Text`, `Markdown`, `Diff`, `Notice`),
forms (`Input`, `Editor`, `Checkbox`, `RadioGroup`, `CheckboxGroup`,
`Select`, `MultiSelect`, `ComboBox`, `Autocomplete`, `Slider`, `Form`,
`Field`, `Option`), data (`List`, `Table`, `Tree`, `Tabs`, `NavList`,
`ProgressBar`, `Spinner`), layout (`Row`, `Column`, `Padding`, `Panel`,
`Divider`, `Spacer`, `Collapsible`, `ScrollPanel`), actions (`Button`,
`Link`, `MenuBar`, `ContextMenu`, `ShortcutBar`, `StatusLine`), overlays
(`Dialog`, `ButtonSpec`, `confirm_dialog`, `prompt_dialog`) and drawing
(`Canvas`, `Sparkline`).

Every themed widget takes `theme=`; components that resolve role groups take
one `styles: Styles` override, while `Text` takes one explicit `style=`.
Widgets resolve their role groups when they render, so assigning
`app.theme` repaints a mounted UI without rebuilding it. See
[WIDGETS](docs/WIDGETS.md) for the per-component catalogue.

## Runtime and controllers

`App` composes `Runtime`, `Workspace` and `Terminal` and owns the default
interaction policy. `Runtime` owns the session: terminal, pump, timers,
painter and run lifecycle. `Workspace` owns what is on screen: document,
frame, panes, docks, hit testing and selection. With `auto=False`, `App`
mounts no controllers and the caller drives the runtime directly.

The dispatch order is public and first-claim-wins; `App.handlers` is
`DEFAULT_HANDLERS` (in `motui/app/router.py`) unless the host passes its own
tuple:

```
palette -> modal -> find -> toasts -> mounted controllers
        -> wheel -> drag -> mouse (gesture, pointer, pane focus)
        -> focused widget -> page keys -> bindings -> host hooks
```

Controllers are ordinary objects: `FocusManager`, `Pointer`,
`SelectionGesture`, `Scrollbar`, `Toasts`, `Tooltip`, `Stats`, `Find`,
`Modal` and `CommandPalette`. A controller is hosted on the workspace (it
owns the frame and the hit test); a host controller joins through
`app.mount(controller)`.

```python
from motui import App, Dialog, Text
from motui.app import Scrollbar


class Shell(App):
    def on_start(self) -> None:
        self.mount(Scrollbar(self.workspace))
        self.bind("c-k", self.ask)

    def ask(self) -> None:
        self.open_modal(Dialog("Confirm", Text("Continue?"), ["Yes", "No"]))


Shell().run()
```

Commands are values plus a registry that binds their keys:

```python
from motui.app import Command, CommandRegistry

registry = CommandRegistry()
registry.add(Command(
    name="theme.next",
    group="Appearance",
    description="Switch theme",
    keys=("c-t",),
    handler=self.next_theme,
))
registry.bind(app)              # keys -> invoke(name)
app.open_palette(registry)      # the palette renders the registry
```

## Layout patterns

Split and dock use enums, not direction strings:

```python
from motui import App, Editor, Text
from motui.kernel import Axis
from motui.kernel.document import Placement
from motui.widgets import StatusLine


class EditorApp(App):
    def on_start(self) -> None:
        left, right = self.split(Axis.X, weights=(1, 2))
        self.add(Text("# notes"), pane=left)
        self.dock(StatusLine(left=("ready",)), placement=Placement.BOTTOM)
        self.add(Editor("hello"), pane=right)
```

Streaming Markdown is a plain attribute assignment; the assignment calls
`touch()`, the section cache sees the new `generation`, and only the changed
rows repaint:

```python
from motui import Markdown

md = Markdown("# Live\n\nA paragraph arrives ")
md.text += "in pieces, with **bold** and a [link](https://example.com)."
app.add(md)
```

A wide table is a non-wrapping table in a horizontal panel:

```python
from motui import ScrollPanel, Table
from motui.kernel.text import WrapMode

table = Table(headers, rows, cell_wrap=WrapMode.OVERFLOW)
view = ScrollPanel(table, axis="x", height=8, bar=True)
app.add(view)
```

## Styling

`Style` is frozen and hashable; `fg`/`bg` accept a named 16-color, a
`#rrggbb` string, an `(r, g, b)` tuple, or a `Color` that pairs truecolor
with an ANSI anchor. `Theme` is ten frozen role groups (`text`, `surfaces`,
`borders`, `controls`, `rows`, `status`, `content`, `chrome`, `overlays`,
`syntax`). `DEFAULT_THEME` is the Ink & Signal dark theme and equals
`Theme()` and `Theme.dark()`.

```python
from dataclasses import replace

from motui import DEFAULT_THEME, List, Style

theme = replace(
    DEFAULT_THEME,
    content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff8800")),
    rows=replace(DEFAULT_THEME.rows, active=Style(bg="#264f78")),
)

app.add(List(["one", "two"]))
app.theme = theme       # repaints mounted widgets whose theme is still None
```

A brand theme derives every role from one `ColorPalette`; `Theme.light()`,
`Theme.flat()` and `Theme.auto(env)` are the shipped alternatives.
`terminal.auto_theme()` is the convenience that reads `os.environ` and
returns a theme.

Structural marks are separate values: `Glyphs` (`GLYPHS`) holds cursors,
prompts, folds, checks, bars and notice marks; `Border` holds one box style.
Every carrying component takes `glyphs=...`; `Panel`, `Dialog` and `Table`
also take a `Border`. Glyphs are content, not style: a theme change never
moves geometry.

## Keys

`KeyDecoder` is a pure `bytes -> events` machine. Editing keys route through
a plain dict keymap:

```python
from motui import Input
from motui.kernel import DEFAULT_INPUT_KEYMAP

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]      # an unbound key goes back to the host
```

`DEFAULT_INPUT_KEYMAP` leaves `enter` unbound, so submission stays the
host's. `DEFAULT_EDITOR_KEYMAP` adds `enter` as newline;
`EDITOR_SUBMIT_KEYMAP` hands return back and binds `c-j` to newline.

## Results and the tree

State attributes (`selected`, `checked`, `text`, `open`) can be read at any
time. `take()` is the one-shot door: it returns the pending result and
clears it, so `None` means "nothing pending" and `False` is a real result.
Collect results with `walk()`:

```python
from motui.widgets.base import HasResult

for widget in app.walk():
    if isinstance(widget, HasResult):
        value = widget.take()
        if value is not None:
            handle(value)
```

There is no per-widget result callback; see ADR-023.

## Testing

`headless_tui` returns a `Harness`: one flat test driver over a real
`Runtime` (recording screen, scripted event source) and its `Workspace`.
Content members resolve to the workspace, session members to the runtime;
`tui.runtime` and `tui.workspace` reach the two objects directly. `snapshot`
renders the document as structured plain text. `Emulator` rebuilds the cell
grid the painter wrote, so assertions can be on what a terminal would show
rather than on escape spelling.

```python
from motui import Text, headless_tui
from motui.testing import Emulator

tui = headless_tui(40, 10)          # a Harness
tui.add(Text("hello"))              # workspace.add
tui.paint()                         # runtime.paint

assert "hello" in "\n".join(row.text for row in tui.rows)

screen = Emulator(40, 10)
screen.feed(tui.screen.output)
assert screen.cell(0, 0).char == "h"
```

The library never sleeps. Time enters through `Runtime.clock()` and
`Runtime.advance(dt)`; `App.every` and `App.animation` schedule against
deadlines rather than accumulating drift.

## The demo

`python -m motui` starts the five-scene showcase that ships in the wheel:
splash, menu, Breakout, Dashboard and Component Gallery. No network, no
model, no assets beyond the package.

```bash
python -m motui                          # a real terminal: the splash and menu
python -m motui --scene gallery          # start on one scene
python -m motui --headless --frames 60   # deterministic text frame, no TTY
python -m motui < /dev/null              # piped: print the menu frame, exit 0
python -m motui --pages                  # all five scenes as plain text
```

In the live menu, arrows and `enter` (or a click) pick Breakout, Dashboard,
Gallery or Quit; `esc` returns to the splash. Breakout plays with the left
and right arrows, `space` launches/pauses, `q` or `esc` returns to the menu.
The Gallery keeps a real `Tree`, `Table`, `ProgressBar`, `Slider` and
`Input` side by side; `tab` cycles their focus.

## Docs

- [ARCHITECTURE](docs/ARCHITECTURE.md) - layers, dependency rules, object
  model, lifecycle, dispatch order and extension points.
- [CONTRACT](docs/CONTRACT.md) - the normative values, protocols and
  invariants the implementation and tests are written against.
- [WIDGETS](docs/WIDGETS.md) - every component: construction, capabilities,
  hooks and `take()`.
- [MIGRATION](docs/MIGRATION.md) - the 1.x to 2.0 name table, recipes and the
  removal list.
- [ADRs](docs/adr/README.md) - the 23 accepted architecture decisions.
- [CONTRIBUTING](CONTRIBUTING.md) - the gates, the commit style and the
  release process.
- [CHANGELOG](CHANGELOG.md) - what changed between releases.

**Source**: [`Shingwha/motui`](https://github.com/Shingwha/motui). Issues
and pull requests go to [the tracker](https://github.com/Shingwha/motui/issues).

## License

MIT - see [`LICENSE`](LICENSE).
