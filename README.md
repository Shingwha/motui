# motui

[![ci](https://github.com/Shingwha/motui/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Shingwha/motui/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/motui)](https://pypi.org/project/motui/)
[![python](https://img.shields.io/pypi/pyversions/motui)](https://pypi.org/project/motui/)
[![license](https://img.shields.io/pypi/l/motui)](LICENSE)

A layered, full-screen TUI toolkit. You describe a **document of addressable
blocks**; motui lays them out, scrolls them, and paints only the rows that
changed on the terminal's alternate screen. It ships parts, not an
application: a component library, a default interaction policy, and the
driver beneath them.

- **A document, not a widget tree.** Content is blocks of rows. Nothing is
  hidden in a parent/child hierarchy, so layout, hit testing and scrolling
  are explicit operations you can inspect.
- **Every input is an event.** The decoder turns terminal bytes into frozen
  `KeyEvent`, `MouseEvent`, `PasteEvent`, `ResizeEvent` and `FocusEvent`
  values. `App` owns the default dispatch; `TUI` hands you the raw loop.
- **No global state.** Themes are values and styles are frozen. A widget
  resolves its role groups at render time, so assigning `App.theme` repaints
  a mounted UI without rebuilding it. Two apps in one process cannot restyle
  each other.

Runtime dependency: **`wcwidth` only**. Python **3.12+**.

## Install

```bash
pip install motui      # or: uv add motui
```

The wheel carries its own demo, so `python -m motui` works right away.

## Quickstart

A small interactive app: a field, keyboard focus and a bound key.

```python
from motui import App, Input, Text


class Greeting(App):
    def on_start(self):
        self.name = Input(placeholder="your name")   # one line of editable text
        self.add(self.name, id="name")
        self.focus(self.name)                        # tab still cycles the ring
        self.bind("enter", self.greet)               # one key -> one callback
        self.bind("c-c", self.quit)

    def greet(self):
        self.add(Text(f"hello, {self.name.text or 'world'}"))


Greeting().run()
```

What each piece did:

| Piece | Job |
|---|---|
| `App` | the driver plus the default interaction policy: `run()` owns the loop |
| `on_start` | called once before the first frame; where a host builds its UI |
| `app.add(component, id=...)` | append a block to the focused pane's document and answer its id |
| `app.focus(target)` | focus a block id or a component; `tab` cycles the interactive ring |
| `app.bind(key, callback)` | run a callback after the focused control declines the key |
| `render(width) -> list[Line]` | every component's only rendering obligation |
| `take_result()` | read a one-shot widget result; the read clears it |

## The 60-second mental model

```
terminal bytes ──KeyDecoder──▶ Event ──App.dispatch──▶ overlays / controllers / widgets
                                                          │
                                            Document = Block + Component + rows
                                                          │
                                              Viewport.layout(width, height)
                                                          │
                                            ScreenLayout (rows + ownership)
                                                          │
                                     Frame.compose (panes, chrome, docks, overlays)
                                                          │
                                     Painter.paint (per-row diff, one flush)
                                                          ▼
                                                       Screen
```

| Concept | What it is | Where it lives |
|---|---|---|
| **Event** | a frozen input value; `None` means EOF | `motui.core.events` |
| **Component** | anything with `render(width) -> list[Line]`; a `Line` is a tuple of `Segment`s | `motui.core.block.Component` |
| **Widget** | the shared themed base: `theme`, `styles`, `focused`, `hover` and no-op interaction verbs | `motui.core.widget.Widget` |
| **Block** | an id, a component, a pin, and the one row cache | `motui.core.block` |
| **Document** | an ordered, id-addressable collection of blocks | `motui.core.block.Document` |
| **Viewport** | the scroll window over one document | `motui.core.viewport` |
| **ScrollState** | offset/content/viewport geometry, clamping, reveal and the shared thumb formula | `motui.core.scroll` |
| **Pane** | a rectangle owning a viewport and chrome | `motui.core.frame` |
| **Frame** | the split tree, docks, overlays and focused pane | `motui.core.frame.Frame` |
| **App** | the driver plus the default dispatch: focus, pointer, gesture, overlays, find, palette, wheel/page | `motui.app.application.App` |
| **TUI** | the low-level driver: document facade, pump, screen, split/dock; `read_event()` is a pure read | `motui.app.driver.TUI` |

`App` owns the default loop and the documented dispatch order. `TUI` is the
layer below it: it reads one event at a time and runs no scroll or focus
policy, so a host that wants its own dispatch can drive it directly. Neither
one ever calls `asyncio.run`, sleeps, or writes to stdout behind the
painter's back. If you want the long version, read
[`docs/DESIGN.md`](docs/DESIGN.md).

## Features

**Rendering and layout**

- Full-screen alternate-screen output with a per-row diff: an unchanged
  frame writes zero bytes.
- One document per pane, scrolled by a viewport; panes tile with fixed
  ratios and 1-cell separators.
- Pinned docks above and below the pane area, outside every split, for
  headers, footers, inputs and status rows.
- Explicit overlay layers (`background`, `content`, `selection`, `chrome`,
  `overlay`, `modal`, `tooltip`, `toast`) so a toast never paints under a
  dialog by accident.

**Input and interaction**

- Incremental UTF-8 decoding, CSI/SS3 keys, kitty and modifyOtherKeys,
  bracketed paste, SGR/X10/urxvt mouse reports, focus reports and resizes.
- Rebindable editing keymaps per text field; unbound keys go back to your
  dispatch.
- `App` mounts `FocusManager`, `Pointer`, `SelectionGesture`, `Toasts` and
  `Tooltip`, opens `Find`/`CommandPalette` on demand, and owns the documented
  dispatch order. `TUI.read_event()` stays a pure read for hosts that build
  their own loop.
- `Find`, `Scrollbar`, `Modal`, `CommandPalette`, `Toasts`, `Tooltip` and
  `Stats` as mountable controllers, not hidden framework behavior.

**Content and styling**

- Markdown with a rule registry (GFM tables, fenced code, per-document
  limits) and an injectable syntax highlighter.
- Unified `Diff`, wrapped `Text`, `Markdown` tables and `Table` that wrap
  long cells by default, `Tree`, `List` and the choice family.
- One frozen `Theme` of ten role groups, derived from a `ColorPalette`;
  `Color` pairs a truecolor value with an ANSI anchor. Named 16-color,
  `#rrggbb` and `(r, g, b)` still work everywhere a color does.
- Every themed widget takes `theme=` and one `styles: Styles` override.
  Widgets resolve their role groups when they render, so assigning
  `App.theme` repaints a mounted UI without rebuilding it.
- `Theme.dark()` is the Ink & Signal default; `Theme.light()`, `Theme.flat()`
  and `Theme.auto()` are pure alternatives.
- Structural `Glyphs` and `Border` values are content, not style: pass one
  vocabulary per component, not one keyword per mark.
- `ScrollView(bar=True)` gives a component its own draggable scrollbar;
  `ScrollState` is the one scroll geometry behind it, the viewport and the
  pane chrome.

**Testing**

- `HeadlessScreen`, `ScriptedEvents`, `headless_tui` and `snapshot` run a
  real session without a terminal. `snapshot` prints one stanza per block
  with its id and pin. The library never sleeps; time enters through
  `tui.clock()`.

## Components

The root is a curated 41-name import line (including `App`, `TUI`,
`CommandPalette`, `ColorPalette`, `Glyphs`, `Border`, `ScrollView`, `Row`,
`Column` and `Panel`). Everything else is
public at its layer: the complete component library is `motui.widgets`
(42 names), the primitives are `motui.core`, and the controllers are
`motui.app`.

```python
from motui import App, TUI, Input, Markdown        # the curated root
from motui.widgets import Panel, Row, Diff         # the complete library
from motui.core import Style, Line, Selection      # the core seam
from motui.core import DEFAULT_INPUT_KEYMAP        # decoder and keymaps
from motui.app import Find, Tooltip                # the controller tier
```

Every themed widget below takes `theme=` and `styles: Styles`; there are no
per-token `*_style` arguments and no `focused=` constructor flag. `Text` is
the core's plain renderer (`motui.core`, also on the root), not a member of
`motui.widgets`; it takes one explicit `style=` instead of a `Styles`
override.

### Text

| Component | What it does |
|---|---|
| `Text` | verbatim, wrapped text; action spans are clickable |
| `Markdown` | streaming-safe Markdown with links, tasks, tables and fences |
| `Diff` | line-level unified diff computed once at construction |
| `Notice` | one message row with an `i` / `✓` / `!` / `×` level glyph |

### Forms

| Component | What it does |
|---|---|
| `Input` | one-line editable field with prompt, placeholder and mask |
| `Editor` | multi-line buffer with masked display and a row window |
| `Checkbox` | one-row `[x]` / `[ ]` toggle |
| `RadioGroup` | single choice, `(•)` / `( )` markers |
| `CheckboxGroup` | multiple choice over a mark set, built on `MultiSelect` |
| `Select` | the single-choice cursor/window list: options, descriptions, commit |
| `MultiSelect` | the marked variant of `Select`: `marked` and `toggle()` |
| `Option` | a label, an optional value and a description |
| `ComboBox` | an input over a filtered dropdown |
| `Autocomplete` | a `Select` whose rows are the current matches |
| `Slider` | one-row stepped integer control |
| `Form` | labelled fields, focus, validation and one-shot submission |
| `Field` | a form entry: component, label, validator and value extractor |

### Data

| Component | What it does |
|---|---|
| `List` | a windowed cursor over a long sequence |
| `Table` | a box grid with header, cursor, marks and host-side sorting; long cells wrap |
| `Tree` | indented nodes with expand/collapse, filter and type-ahead |
| `TreeNode` | one tree node's label, children and expanded flag |
| `Tabs` | one-row horizontal content strip (clamped, not wrapping) |
| `NavList` | a vertical navigation rail with an indicator bar |
| `ProgressBar` | determinate bar with a label and a re-clamping fraction |
| `Spinner` | frame-cycling activity indicator; the host advances it |

### Layout

| Component | What it does |
|---|---|
| `Row` | side-by-side children with fixed or flexible widths |
| `Column` | vertical children with an optional gap |
| `Padding` | inset a child on four sides; optional painted fill |
| `Panel` | a child in a single-line box, or a borderless filled panel |
| `Divider` | a repeated-character rule with an optional label |
| `Spacer` | blank rows as a first-class component |
| `Collapsible` | a titled section that folds its body away |
| `ScrollView` | a fixed-height window over any component; `bar=True` adds an interactive scrollbar |

### Actions

| Component | What it does |
|---|---|
| `Button` | one-row action; click or `enter` lands `True` |
| `Link` | one-row clickable text in the theme's link style |
| `MenuBar` | one-row horizontal menu with one active label |
| `ContextMenu` | the `Select` preset for a desktop context menu |
| `ShortcutBar` | one row of key/label hints (display only) |
| `StatusLine` | a dim two-sided status row (display only) |

### Overlays and builders

| Component | What it does |
|---|---|
| `Dialog` | a box with a body and a button row; the modal's payload |
| `ButtonSpec` | one dialog button: label, value, styles, danger flag |
| `confirm_dialog` | the Yes/No builder over `Dialog` |
| `prompt_dialog` | the one-line prompt builder over `Dialog` |

`Modal` and `CommandPalette` are controllers in `motui.app`, not
components: they paint any component that speaks `render` / `click` /
`handle` / `take_result`.

## Interactions

`App` mounts the default tiers and owns the order. They remain ordinary
objects: a host can reach them, replace them, or mount one more.

| Tier | Import | What it owns |
|---|---|---|
| `App` | `motui` | the dispatch order and the default mounts |
| `FocusManager` | `motui.app` | tab order, `focused` flags, `enter`/arrow routing, nested traps |
| `Pointer` | `motui.app` | hover flags, `hover_at` rows, stationary clicks |
| `SelectionGesture` | `motui.app` | drag selection in document space, copy on release |
| `Scrollbar` | `motui.app` | one budgeted column of pane chrome and its drag |
| `Toasts` / `Tooltip` / `Stats` | `motui.app` | overlay controllers |
| `Find` | `motui.app` | a query row plus match highlighting and reveal |
| `Modal` | `motui.app` | scrim, placement, keyboard capture, click-outside |
| `CommandPalette` | `motui` / `motui.app` | a query row over a filtered command list |

`CommandPalette` lives in `motui.app.command_palette` and is re-exported as
`motui.CommandPalette`. `App` exposes its default mounts as `focus_manager`,
`pointer`, `gesture`, `toasts`, `tooltip`, `palette` and `find_bar`; a
controller added by the host goes through `mount` so the App dispatches it
in order:

```python
from motui import App, Dialog, Text
from motui.app import Scrollbar


class Shell(App):
    def on_start(self):
        self.mount(Scrollbar(self.tui))        # pane chrome, in the App order
        self.bind("c-k", self.ask)

    def ask(self):
        self.open_modal(Dialog("Confirm", Text("Continue?"), ["Yes", "No"]))


Shell().run()
```

**Dispatch order.** The first claim wins:

```
palette -> modal -> find -> toasts -> mounted controllers
        -> wheel -> mouse (drag, gesture, pointer, pane focus)
        -> focused widget -> page keys -> bind -> tab -> hooks
```

An open modal consumes **everything**, so a host that overrides `dispatch`
or `on_key` for a quit gesture must run it before the modal tier. And
`read_event()` is a **pure read**: it no longer absorbs wheel/page or runs a
focus policy. That policy lives in `App`; a host driving `TUI` directly
routes those events itself.

### Build your own shell

The library ships no application shell. A host assembles one with `App`,
`add` and `dock`; a dock is a frame-level region outside every split and
takes a component:

```python
from motui import App, Editor, Text
from motui.core import EDITOR_SUBMIT_KEYMAP
from motui.widgets import StatusLine


class Shell(App):
    def on_start(self):
        self.editor = Editor(keymap=EDITOR_SUBMIT_KEYMAP)  # enter stays the host's
        self.dock(StatusLine(left=("ready",)), edge="top")
        self.dock(self.editor, edge="bottom")
        self.focus(self.editor)
        self.bind("c-c", self.quit)

    def on_key(self, event):
        if event.key == "enter":
            self.add(Text(f"you: {self.editor.text}"))   # the host owns submission
            self.editor.clear()
            return True
        return super().on_key(event)


Shell().run()
```

`app.undock(edge)` releases a dock. [`docs/COMPONENTS.md`](docs/COMPONENTS.md)
has the per-component verbs and the build-your-own recipes.

## Styling

`Style` is frozen and hashable; `fg`/`bg` accept a named 16-color, a
`#rrggbb` string, an `(r, g, b)` tuple, or a `Color` that pairs the
truecolor value with an ANSI anchor. `Theme` is ten frozen role groups
(`text`, `surfaces`, `borders`, `controls`, `rows`, `status`, `content`,
`chrome`, `overlays`, `syntax`). `DEFAULT_THEME` is the Ink & Signal dark
theme and equals `Theme()` and `Theme.dark()`. Build a variant with
`dataclasses.replace`; nothing global is mutated.

```python
from dataclasses import replace

from motui import App, DEFAULT_THEME, List, Markdown, Style, Text
from motui.widgets import StatusLine

theme = replace(
    DEFAULT_THEME,
    content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff8800")),
    rows=replace(DEFAULT_THEME.rows, active=Style(bg="#264f78")),
)

app = App()
app.add(List(["one", "two"]))              # no theme=: it follows app.theme
app.theme = theme                          # repaints the mounted list, no rebuild

Markdown("# H", theme=theme).render(80)    # an explicit theme stays local
StatusLine(left=("ready",), theme=theme)   # the two-column row follows
Text("hello", theme=theme)                 # the core renderer takes theme=
```

A brand theme derives every role from one authoring `ColorPalette`:

```python
from motui import Style
from motui.core import ColorPalette, Theme
from motui.core.style import Color

brand = ColorPalette(
    accent=Style(fg=Color("#ff8800", ansi="yellow")),
    heading=Style(fg=Color("#ff8800", ansi="yellow")),
)
theme = Theme.from_palette(brand)   # every group derived
theme = Theme.light()               # the shipped light palette
theme = Theme.flat()                # no background surfaces
theme = Theme.auto()                # TERM_BACKGROUND / COLORFGBG, dark fallback
```

A widget resolves its look **when it renders**: a non-`None` `styles` group
first, then its own explicit `theme=`, then the App theme, then
`DEFAULT_THEME`. `Styles(rows=...)` replaces that whole role group for one
widget; every `None` group keeps following the theme:

```python
from motui import Styles

hot = replace(DEFAULT_THEME.rows, active=Style(bg="#264f78"))
List(items, styles=Styles(rows=hot))       # one widget overrides one group
```

`App.theme` walks the mounted components and assigns the new value to every
`Widget` whose `theme is None`; an explicit `theme=` stays a local override.
Every vertical row widget resolves its band through `theme.rows.band(...)`
(`disabled > hovered > active/inactive > selected > marked > base`), and
every control through `theme.controls.band(...)`
(`disabled > active > focused > hovered > base`); changing the group
restyles `List`, `Table`, `Tree`, `NavList`, `Select`, `MultiSelect` and the
form groups at once. `Text` is the exception: a core renderer, not a
`Widget`, whose one explicit `style=` wins over `theme.text.base`.

Structural marks are separate values: `Glyphs` (`GLYPHS`) holds the cursor,
prompt, folds, checks, bars, notice marks and box/grid borders, and `Border`
holds one box style. Every carrying component takes `glyphs=Glyphs(...)`;
`Panel`, `Dialog` and `Table` also take a `Border`. Glyphs are content, not
style: changing the theme never changes geometry, and `""` turns a mark off
and collapses its seat. See the glyph table in
[`docs/COMPONENTS.md`](docs/COMPONENTS.md#theme-colorpalette-glyphs-and-keymaps).

## Markdown and syntax

`Markdown` is a rule-registry engine, not a regex pile. Two ordered
registries do the work: block rules classify and consume lines, inline rules
recognize constructs at a position. Add a rule by prepending it to the
registry. Every prefix renders, so streaming into `.text` one chunk at a
time is safe.

```python
from motui import Markdown

md = Markdown("# Live\n\nA paragraph arrives ")
md.text += "in pieces, with **bold** and a [link](https://example.com)."
rows = md.render(80)                         # headings, emphasis and links resolve
assert "".join(row.text for row in rows).count("Live") == 1
```

`Markdown(..., highlighter=...)` accepts any object with
`highlight(code, lang) -> list[Line]`. The built-in `RegexHighlighter`
covers 16 languages with five weight-free token classes. The rule registries
and the `Highlighter` protocol are documented in
[`docs/COMPONENTS.md`](docs/COMPONENTS.md#markdown).

## Keys and keymaps

`KeyDecoder` is a pure `bytes -> events` machine: UTF-8, control names, CSI
navigation, bracketed paste, mouse reports, focus and resize. Editing keys
in `Input` and `Editor` route through a **keymap**: a plain dict from a key
name to the editing method it triggers.

```python
from motui import Input
from motui.core import DEFAULT_INPUT_KEYMAP

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]      # unbound: the host sees the event again
```

`DEFAULT_INPUT_KEYMAP` binds movement, home/end, backspace/delete, undo/redo
and the selection chords, but leaves `enter` unbound: submission belongs to
the host. `DEFAULT_EDITOR_KEYMAP` adds `enter` as `newline`;
`EDITOR_SUBMIT_KEYMAP` hands the return key back and binds `c-j` to
`newline` instead. All three tables live in `motui.core`.

## The demo

`python -m motui` starts the library's own component browser. It ships in
the wheel and answers locally: no network, no model.

```bash
python -m motui              # a real terminal: the full screen
python -m motui < /dev/null  # piped: replay headless, dump the final screen
python -m motui --pages      # every topic as plain text, no terminal needed
```

It is a master-detail explorer, not a gallery:

- a header `MenuBar` switches six sections: `overview`, `components`,
  `interactions`, `styling`, `patterns`, `reference`;
- the left catalog lists the current section's topics in groups;
- the right stage shows one topic: title, summary, live preview, optional
  variants, a `Try:` line and an `API:` line.

There are 57 topics. The components section covers all 37 public-component
topics in six groups (Text, Forms, Data, Layout, Actions, Overlays); the
other sections cover the interaction tiers, the theme and glyph vocabulary,
four composition recipes and the static reference tables.

Controls: `c-1`..`c-6` switch sections, `c-n`/`c-p` step topics, `[`/`]`
step sections, `/` or `c-k` opens the command palette, `c-f` opens `Find`,
`tab` cycles focus, arrows and `enter` drive the focused component, `space`
marks a row, `c-t` cycles themes, `c-g` toggles the stats overlay, `esc`
closes a panel or returns focus to the catalog, a drag selects and copies,
and `q` quits (a focused text field keeps `q` for itself).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — the problem, the mechanism and the
  trade-off behind each layer: coordinates, events, lifecycle, caching,
  viewport, frame, painter, focus and selection.
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the task catalogue: every
  component in one fixed template, the widget verbs, the row-band contract,
  dispatch order, build-your-own recipes and testing helpers.
- [`docs/CONTRACT.md`](docs/CONTRACT.md) — the short normative rules the
  implementation and tests are written against.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — the dependency graph, the gates,
  how to add a component or a demo topic, and the versioning policy.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed between releases.

**Source**: [`Shingwha/motui`](https://github.com/Shingwha/motui). Issues
and pull requests go to [the tracker](https://github.com/Shingwha/motui/issues).

## License

MIT — see [`LICENSE`](LICENSE).
