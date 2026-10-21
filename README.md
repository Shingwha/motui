# motui

[![ci](https://github.com/Shingwha/motui/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Shingwha/motui/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/motui)](https://pypi.org/project/motui/)
[![python](https://img.shields.io/pypi/pyversions/motui)](https://pypi.org/project/motui/)
[![license](https://img.shields.io/pypi/l/motui)](LICENSE)

A layered, full-screen TUI toolkit. You describe a **document of addressable
blocks**; motui lays them out, scrolls them, and paints only the rows that
changed on the terminal's alternate screen. It ships parts, not an
application: a component library, a set of interaction tiers, and a driver
you compose.

- **A document, not a widget tree.** Content is blocks of rows. Nothing is
  hidden in a parent/child hierarchy, so layout, hit testing and scrolling
  are explicit operations you can inspect.
- **Every input is an event.** The decoder turns terminal bytes into frozen
  `KeyEvent`, `MouseEvent`, `PasteEvent`, `ResizeEvent` and `FocusEvent`
  values. Your loop decides what they mean.
- **No global state.** Themes are values, styles are frozen, and every
  component resolves its look once at construction. Two apps in one process
  cannot restyle each other.

Runtime dependency: **`wcwidth` only**. Python **3.12+**.

## Install

```bash
pip install motui      # or: uv add motui
```

The wheel carries its own demo, so `python -m motui` works right away.

## Quickstart

A small interactive app: a field, a button, keyboard focus and the mouse.

```python
import asyncio

from motui import Button, FocusManager, Input, KeyEvent, MouseEvent, Pointer, Text, TUI


async def session(tui):
    name = Input(placeholder="your name")
    tui.add(name, id="name")                      # one line of editable text
    greet = Button("Greet")
    tui.add(greet, id="greet")                    # one line of action

    focus = FocusManager([name, greet])           # tab order: field, then button
    focus.focus_next()                            # focus is explicit, never assumed
    pointer = Pointer(tui, ring=focus)            # hover + stationary clicks

    while True:
        event = await tui.read_event()
        if event is None or (isinstance(event, KeyEvent) and event.key == "c-c"):
            break                                 # EOF, or the host's quit gesture

        if isinstance(event, MouseEvent):
            if pointer.handle(event):             # the hover moved, or a click landed
                tui.refresh()
        elif isinstance(event, KeyEvent) and event.key == "tab":
            focus.focus_next()                    # the host owns the cycle key
        elif not focus.handle(event):
            if isinstance(event, KeyEvent) and event.key == "enter":
                greet.activate()                  # the field leaves enter to the host

        if greet.take_result() is not None:       # read once; the read clears it
            tui.add(Text(f"hello, {name.text or 'world'}"))

    tui.exit()


asyncio.run(TUI(hover=True).run_session(session))  # 1003: free motion reaches us
```

What each piece did:

| Piece | Job |
|---|---|
| `tui.add(component, id=...)` | append a block to the focused pane's document |
| `render(width) -> list[Line]` | every component's only rendering obligation |
| `FocusManager` | hold the tab order, flag the focused component, route `enter`/arrows |
| `Pointer` | write `hover`, and turn a press + release on one cell into a click |
| `run_session` | enter the alt screen, run the pump, call your body, tear down |
| `take_result()` | read a one-shot widget result and clear it |

## The 60-second mental model

```
terminal bytes ──KeyDecoder──▶ Event ──your loop──▶ FocusManager / Pointer / widgets
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
| **Event** | a frozen input value; `None` means EOF | `motui.kernel.events` |
| **Component** | anything with `render(width) -> list[Line]`; a `Line` is a tuple of `Segment`s | `motui.kernel.block.Component` |
| **Block** | an id, a component, a pin, and the one row cache | `motui.kernel.block` |
| **Document** | an ordered, id-addressable collection of blocks | `motui.kernel.block.Document` |
| **Viewport** | the scroll window over one document | `motui.kernel.viewport` |
| **Pane** | a rectangle owning a viewport and chrome | `motui.kernel.frame` |
| **Frame** | the split tree, docks, overlays and focused pane | `motui.kernel.frame.Frame` |
| **Host** | the narrow driver surface the interaction tiers see | `motui.kernel.host.Host` |
| **TUI** | the driver: document facade, pump, screen, split/dock | `motui.app.TUI` |

The host owns the loop. motui never calls `asyncio.run`, never sleeps, and
never writes to stdout behind the painter's back. If you want the long
version, read [`docs/DESIGN.md`](docs/DESIGN.md).

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
- `FocusManager` for widget focus (including nested modal traps),
  `Pointer` for hover and stationary clicks, `SelectionGesture` for
  document-space drag selection and copy.
- `Find`, `Scrollbar`, `Modal`, `Palette`, `Toasts`, `Tooltip` and `Stats`
  as mounted controllers, not hidden framework behavior.

**Content and styling**

- Markdown with a rule registry (GFM tables, fenced code, per-document
  limits) and an injectable syntax highlighter.
- Unified `Diff`, wrapped `Text`, `Table`, `Tree`, `List` and the choice
  family.
- One frozen `Theme` of ten role groups, derived from a `Palette`; `Color`
  pairs a truecolor value with an ANSI anchor. Named 16-color, `#rrggbb`
  and `(r, g, b)` still work everywhere a color does.
- `Theme.dark()` is the Ink & Signal default; `Theme.light()`, `Theme.flat()`
  and `Theme.auto()` are pure alternatives.
- Structural `Glyphs` and `Border` values are content, not style: pass one
  vocabulary per component, not one keyword per mark.

**Testing**

- `HeadlessScreen`, `ScriptedEvents`, `headless_tui` and `snapshot` run a
  real session without a terminal. The library never sleeps; time enters
  through `tui.clock()`.

## Components

The root is a curated 37-name import line. Everything else is public at its
layer: the complete component library is `motui.widgets` (43 names), the
primitives are `motui.kernel`, and the mounted controllers are
`motui.interaction`.

```python
from motui import TUI, Input, Markdown              # the curated root
from motui.widgets import Panel, Row, Diff          # the complete library
from motui.kernel import Style, Line, Selection     # the kernel seam
from motui.keys import DEFAULT_INPUT_KEYMAP         # decoder and keymaps
from motui.interaction import Find, Tooltip         # the strategy tier
```

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
| `CheckboxGroup` | multiple choice over a mark set |
| `Select` | the cursor/window base: options, descriptions, marks, commit |
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
| `Table` | a box grid with header, cursor, marks and host-side sorting |
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
| `ScrollView` | a fixed-height window over any component, optional scrollbar |
| `Delegate` | a one-child identity wrapper that forwards the protocols |

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

`Modal` and `Palette` are controllers in `motui.interaction`, not
components: they paint any component that speaks `render` / `click` /
`handle` / `take_result`.

## Interactions

Each tier is explicit and mountable. A host builds the ones it needs:

| Tier | Import | What it owns |
|---|---|---|
| `FocusManager` | `motui` | tab order, `focused` flags, `enter`/arrow routing, nested traps |
| `Pointer` | `motui` | hover flags, `hover_at` rows, stationary clicks |
| `SelectionGesture` | `motui` | drag selection in document space, copy on release |
| `Scrollbar` | `motui` | one budgeted column of pane chrome and its drag |
| `Toasts` / `Tooltip` / `Stats` | `motui.interaction` | overlay controllers |
| `Find` | `motui.interaction` | a query row plus match highlighting and reveal |
| `Modal` | `motui.interaction` | scrim, placement, keyboard capture, click-outside |
| `Palette` | `motui.interaction` | a query row over a filtered command list |

```python
from motui import Dialog, FocusManager, Input, Option, Pointer, Select
from motui import SelectionGesture, Text, TUI
from motui.commands import Command, CommandRegistry
from motui.interaction import Find, Modal, Palette, Scrollbar, Toasts, Tooltip

tui = TUI()                                      # a real terminal screen
field = Input()
menu = Select([Option("One"), Option("Two")])
focus = FocusManager([field, menu])               # the widget focus tier
pointer = Pointer(tui, ring=focus)                # hover + stationary clicks
gesture = SelectionGesture(tui)                   # drag to select and copy
bar = Scrollbar(tui)                              # pane chrome
toasts = Toasts(tui)                              # transient overlay bands
tooltip = Tooltip(tui, pointer)                   # the hovered leaf's hint
registry = CommandRegistry([Command("help", "show help")])
palette = Palette(tui, registry.options())        # a modal command palette
modal = Modal(tui, Dialog("Confirm", Text("Continue?"), ["Yes", "No"]))
find = Find(tui)                                  # search the focused pane
```

**Dispatch order.** Route every event through the chrome first, then the
overlays, the open modal, `Find` while it is open, the content gestures, the
focused widget, and finally your own keys:

```
chrome -> overlays -> modal -> find -> gestures -> focused widget -> host keys
```

Two details make the order work. An open modal consumes **everything**, so
handle your own quit gesture before it. And `read_event()` absorbs the
`scroll_keys` table (`page_up`/`page_down` and the wheel by default); rebind
or delete entries in `tui.scroll_keys` to get an event back.

### Build your own shell

The library ships no application shell. A host assembles one from a body
document, a footer document and `tui.dock`, which parks the footer outside
every split:

```python
import asyncio

from motui import Editor, KeyEvent, StatusLine, Text, TUI
from motui.kernel import Document, Viewport
from motui.keys import EDITOR_SUBMIT_KEYMAP


async def session(tui):
    footer = Document()                           # the shell's own document
    editor = Editor(keymap=EDITOR_SUBMIT_KEYMAP)  # enter stays the host's gesture
    footer.add(editor, id="input")                # the pinned input row
    footer.add(StatusLine(left=("ready",)), id="status")
    tui.dock(Viewport(footer))                    # full-width, below every pane

    while True:
        event = await tui.read_event()
        if event is None or (isinstance(event, KeyEvent) and event.key == "c-c"):
            break
        if isinstance(event, KeyEvent) and event.key == "enter":
            tui.add(Text(f"you: {editor.text}"))   # the host owns submission
            editor.clear()
            continue
        editor.handle(event)                       # editing keys and pastes

    tui.exit()


asyncio.run(TUI().run_session(session))
```

The same shape grows one line per tier: add `FocusManager`, `Pointer`,
`SelectionGesture`, `Scrollbar`, `Toasts`, `Find` or `Palette` beside the
loop. [`docs/COMPONENTS.md`](docs/COMPONENTS.md) has the wiring, the
per-component verbs and the build-your-own recipes.

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

from motui import DEFAULT_THEME, Markdown, StatusLine, Style, Text

theme = replace(
    DEFAULT_THEME,
    content=replace(DEFAULT_THEME.content, accent=Style(fg="#ff8800")),
    rows=replace(DEFAULT_THEME.rows, active=Style(bg="#264f78")),
)

Text("hello", theme=theme)                 # the theme field wins over the default
Markdown("# H", theme=theme).render(80)    # the heading ladder follows
StatusLine(left=("ready",), theme=theme)   # the two-column row follows
```

A brand theme derives every role from one authoring `Palette`:

```python
from motui import Style
from motui.kernel import Palette, Theme
from motui.kernel.style import Color

brand = Palette(
    accent=Style(fg=Color("#ff8800", ansi="yellow")),
    heading=Style(fg=Color("#ff8800", ansi="yellow")),
)
theme = Theme.from_palette(brand)   # every group derived
theme = Theme.light()               # the shipped light palette
theme = Theme.flat()                # no background surfaces
theme = Theme.auto()                # TERM_BACKGROUND / COLORFGBG, dark fallback
```

Resolution is **explicit `style=` > the component's `theme=` > `DEFAULT_THEME`**,
decided once at construction. Every vertical row widget resolves its band
through `theme.rows.band(...)` (`disabled > hovered > active/inactive >
selected > marked > base`), and every control through
`theme.controls.band(...)` (`disabled > active > focused > hovered > base`);
changing the group restyles `List`, `Table`, `Tree`, `NavList`, `Select` and
the form groups at once.

Structural marks are separate values: `Glyphs` (`GLYPHS`) holds the cursor,
prompt, folds, checks, bars, notice marks and box/grid borders, and `Border`
holds one box style. Every carrying component takes `glyphs=Glyphs(...)`;
`Panel`, `Dialog` and `Table` also take a `Border`. Glyphs are content, not
style: changing the theme never changes geometry, and `""` turns a mark off
and collapses its seat. See the glyph table in
[`docs/COMPONENTS.md`](docs/COMPONENTS.md#theme-palette-glyphs-and-keymaps).

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
from motui.keys import DEFAULT_INPUT_KEYMAP

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]      # unbound: the host sees the event again
```

`DEFAULT_INPUT_KEYMAP` binds movement, home/end, backspace/delete, undo/redo
and the selection chords, but leaves `enter` unbound: submission belongs to
the host. `DEFAULT_EDITOR_KEYMAP` adds `enter` as `newline`;
`EDITOR_SUBMIT_KEYMAP` hands the return key back and binds `c-j` to
`newline` instead. All three tables live in `motui.keys`.

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

There are 58 topics. The components section covers all 38 public-component
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
  component in one fixed template, the controller protocols, the row-band
  contract, dispatch order, build-your-own recipes and testing helpers.
- [`docs/CONTRACT.md`](docs/CONTRACT.md) — the short normative rules the
  implementation and tests are written against.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — the dependency graph, the gates,
  how to add a component or a demo topic, and the versioning policy.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed between releases.

**Source**: [`Shingwha/motui`](https://github.com/Shingwha/motui). Issues
and pull requests go to [the tracker](https://github.com/Shingwha/motui/issues).

## License

MIT — see [`LICENSE`](LICENSE).
