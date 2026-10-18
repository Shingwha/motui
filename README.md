# motui

[![ci](https://github.com/Shingwha/motui/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Shingwha/motui/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/motui)](https://pypi.org/project/motui/)
[![python](https://img.shields.io/pypi/pyversions/motui)](https://pypi.org/project/motui/)
[![license](https://img.shields.io/pypi/l/motui)](LICENSE)

A **layered, full-screen TUI toolkit**. It takes over the terminal on the
alternate screen, renders a document of addressable blocks one diffed row at
a time, owns its own scrollback, and keeps **pinned bands** (fixed top/bottom
regions, the frame's footer band) that never scroll away. Any Python program
can build its own components and screens on it: the library ships parts, not
an application.

Runtime dependency: **`wcwidth` only** — Python **3.12+**.

## Install

```bash
pip install motui      # or: uv add motui
```

The wheel carries its own demo, so `python -m motui` is one command away.

## Quickstart

A minimal interactive app: a `Button` and a `Checkbox` (the minimal action
primitives), a `FocusRing` for the keyboard and a `Pointer` for the mouse.
Run it on a real terminal, or drive it with scripted events.

```python
import asyncio

from motui import Button, Checkbox, FocusRing, Key, MouseEvent, Pointer, Text, TUI


async def session(tui):
    ship = Button("Ship")
    tui.add(ship, id="ship")                       # a one-row action
    trace = Checkbox("Trace")
    tui.add(trace, id="trace")                     # a one-row toggle
    ring = FocusRing([ship, trace])                # tab cycles, enter activates
    pointer = Pointer(tui, ring=ring)              # hover + stationary clicks
    while True:
        event = await tui.read_key()
        if event is None or (isinstance(event, Key) and event.name == "c-c"):
            break                                  # EOF, or the quit gesture
        if isinstance(event, MouseEvent):
            if pointer.handle(event):              # the hover moved, or a click landed
                tui.invalidate()
        elif isinstance(event, Key) and event.name == "tab":
            ring.focus_next()                      # the host owns the cycle key
        elif not ring.handle(event):
            ...                                    # the host's own dispatch
        for widget in (ship, trace):
            if widget.chosen is not None:          # read each chosen once
                tui.add(Text(f"{widget.label}: {widget.chosen}"))
                widget.chosen = None
    tui.stop()

asyncio.run(TUI(hover=True).run(session))          # 1003: motion reaches the pointer
```

## The demo

`python -m motui` runs the library's own front page: a demo that **ships in
the wheel** — eleven pages under a left rail grouped into foundations,
components and shell, the page content on the right, the shell built from the
same library it shows off. It answers locally: no network, no model.

```bash
python -m motui              # a real terminal: the full screen
python -m motui < /dev/null  # piped: replays headless, dumps the final screen
python -m motui --pages      # every page as plain text, no terminal needed
```

Click a rail label to open that page, or `c-n` / `c-p` to step (the ends
wrap). `tab` cycles the page's focus ring, the arrows and `enter` drive what
it focuses, `space` marks the focused view's cursor row, `c-o` moves the pane
focus, `c-f` opens the search tier, `c-g` mounts the dev stats overlay, a drag
selects and release copies, `q` quits.
Each page follows one template — a title, one factual line, then its
exhibits, each a live component under its own rule with at most one caption
line — and the eleven pages — `overview`, `text`, `layout`, `actions`,
`forms`, `views`, `modals`, `shell`, `themes`, `streaming`, `notes` — carry
one exhibit per component family, so every widget in the library is on one of
them. The `notes` page is the manual: how to play, the tour, the signature
quick reference and the interaction model.

## The API

The root is the curated face — **34 names** in one import line. Every other
name stays public, one name one home, at its layer namespace:

```python
from motui import TUI, Input, Markdown            # the root: 34 names, one line
from motui.widgets import Row, Panel, Diff        # the component library, complete
from motui.kernel import Style, Line, Selection   # the kernel seam
from motui.keys import DEFAULT_INPUT_KEYMAP
from motui.interaction import FocusRing, Pointer, SelectionGesture, Find, Scrollbar, Toasts
```

`motui.kernel` holds the primitives — rows, styles, events, the document
model, screen / viewport / painter, the frame model, selection — and imports
nothing above itself. `motui.keys` decodes bytes into events and carries the
keymaps; `motui.widgets` is the component library; `motui.interaction` is the
policy tier a host mounts on the driver; `motui.app`
and `motui.testing` are the driver and the headless helpers. The full map,
deeper seams included, is the table in [`docs/DESIGN.md`](docs/DESIGN.md).

Everything hangs off the driver and the components it mounts:

```python
tui.add(Button("Ship"), id="ship")     # append a block; address it by id later
tui.remove("ship"); tui.get("ship")    # detach it / fetch it
tui.invalidate()                       # mark the frame dirty; a paint follows
await tui.read_key()                   # the host's loop: keys, pastes, mouse reports
tui.scroll_up(2); tui.reveal("b3", 12) # scroll, or bring an address on screen
tui.split("vertical", ratios=(2, 1))   # tile the focused pane
tui.add_band(Viewport(footer))         # pin a footer band outside every split
tui.hit_test(x, y)                     # a 0-based cell -> the block under it
tui.set_title("my app"); tui.stop()    # OSC 2 title; ask run() to finish
```

Components render through one frozen protocol — `render(width) -> list[Line]`
— and the interactive ones carry controller verbs beside it: `handle(event)`,
`click(row, col)`, `move(delta)`, `activate()`, `select(index)`, plus the
`focused` and `hover` flags the tiers write. The library ships `Text`,
`Markdown`, `Diff`, `Input`, `Editor`, `ComboBox`, `Autocomplete`, `Table`,
`List`, `Tree`, `Tabs`, `NavList`, `Select`, `Option`, `Radio`, `CheckGroup`,
`Checkbox`, `Button`, `Link`, `Slider`, `ProgressBar`, `Spinner`, `Panel`,
`Notice`, `Divider`, `Row`, `Column`, `Padding`, `Spacer`, `Collapsible`,
`Dialog`, `Palette`, `StatusLine` and `ShortcutBar`; the modal layer adds
`Modal` (the controller) beside them.

## Features

- **alt screen + scrollback** — full screen; the whole document stays
  resident and the page keys scroll the window back through it.
- **mouse** — the wheel, presses, releases and motion decode into 0-based
  `MouseEvent`s; `tui.hit_test` resolves a cell to a block, and the host
  dispatches.
- **selection & copy** — `SelectionGesture(tui)`: drag to select in document
  space, release copies through OSC 52, repeated presses take the word, then
  the line.
- **hover** — `Pointer(tui)`: the leaf under the pointer takes its `hover`
  flag; a press and release on one cell is a stationary click.
- **panes, chrome, overlays** — `tui.split`; `Scrollbar`; `Toasts`;
  `Tooltip`; the `Stats` dev readout.
- **modal dialogs** — `Modal(tui, dialog)` (or a `Palette`, or a `ComboBox`
  dropdown): a scrimmed panel centered or anchored, the keyboard routed into
  the body first, a click outside dismissing; `confirm_dialog` /
  `prompt_dialog` are the two builders.
- **pinned bands** — fixed top/bottom blocks in the frame's own band, outside
  every split.
- **themeable** — one frozen `Theme`; restyle everything with
  `dataclasses.replace`, nothing global is mutated.
- **markdown + syntax** — a streaming-safe rule-registry engine (GFM tables,
  fenced code, your own rules) with an injectable highlighter.
- **keymaps** — the text fields' editing keys are tables you can rebind, or
  unbind to hand the event back.

## Building your own shell

The library ships no app shell — no ready-made application, no pinned
input box: the components plus the tiers are the whole toolkit, and a host
assembles its own. The shape is three pieces: the body document the
panes render, a footer `Document` holding the input and status rows, and
`tui.add_band(viewport)`, which parks that footer's viewport in the frame's
bottom band — full width, beneath every pane, outside every split, so a
pane division never cuts it in half.

```python
import asyncio

from motui import Editor, Key, StatusLine, Text, TUI
from motui.kernel import Document, Viewport
from motui.keys import EDITOR_SUBMIT_KEYMAP


async def session(tui):
    footer = Document()                           # the shell's own footer document
    editor = Editor(keymap=EDITOR_SUBMIT_KEYMAP)  # enter stays the host's submit gesture
    footer.add(editor, id="input")                # the pinned input row
    footer.add(StatusLine(left=("ready",)), id="status")
    tui.add_band(Viewport(footer))                # park the footer under the pane area
    while True:
        key = await tui.read_key()
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break                                     # EOF, or the quit gesture
        if isinstance(key, Key) and key.name == "enter":
            tui.add(Text(f"you: {editor.text}"))      # the submit gesture is the host's
            editor.clear()
            continue
        editor.handle(key)                            # every editing key, and a Paste
    tui.stop()

asyncio.run(TUI().run(session))
```

Every other tier mounts with one more line beside the loop — `Pointer`,
`FocusRing`, `SelectionGesture`, `Scrollbar`, `Toasts`, `Find`, `Palette` —
and [`docs/COMPONENTS.md`](docs/COMPONENTS.md) has the dispatch order they
route in plus the build-your-own walkthroughs (a custom chrome rail, a custom
overlay, a clickable-through container, a custom Markdown rule).

## Styling: Theme

`Style` is frozen and hashable (`fg`/`bg` accept named-16, `#rrggbb` or
`(r, g, b)` truecolor); `Theme` is the frozen dataclass that carries every
semantic default. Build a variant with `dataclasses.replace` and hand it to
the components you construct — nothing global is mutated:

```python
from dataclasses import replace

from motui import DEFAULT_THEME, Markdown, StatusLine, Style, Text
from motui.kernel import ACCENT

theme = replace(DEFAULT_THEME, accent=Style(fg="#ff8800"), heading=Style(fg="#ff8800"))
Text("hello", theme=theme)            # theme field wins over DEFAULT_THEME
Markdown("# H", theme=theme).render(80)
StatusLine(left=("ready",), theme=theme)  # the two-column row follows the theme
Text("still the default", style=ACCENT)  # an explicit style always wins
```

Styles resolve once, at construction: explicit `style=` > the component's
`theme=` field > `DEFAULT_THEME`. The fields and their defaults are the table
in [`docs/COMPONENTS.md`](docs/COMPONENTS.md).

## Keys and keymaps

`KeyDecoder` is a pure `bytes -> events` machine (UTF-8, control names, CSI
navigation, bracketed paste, SGR mouse). Editing keys route through a
**keymap** — key event name to the editing method it triggers — which
`Input`/`Editor` resolve at construction:

```python
from motui import Input
from motui.keys import DEFAULT_INPUT_KEYMAP

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]   # unbound: the host sees the event again
```

`DEFAULT_INPUT_KEYMAP` binds the arrows, home/end, backspace/delete,
`c-a`/`c-e`/`c-u`, the bounded undo/redo pair and the shift chords for the
text-internal selection, but leaves `enter` unbound — the return key is the
host's submit gesture. `DEFAULT_EDITOR_KEYMAP` adds `enter` as `newline`, and
`EDITOR_SUBMIT_KEYMAP` is the editor table with the submit key handed back.
The three tables live together in `keys/keymap.py`; the full semantics are in
[`docs/DESIGN.md`](docs/DESIGN.md).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — how it works and why: the layers and
  the import table, the coordinate charter, the screen model, the viewport,
  the painter, the frame model, the driver, selection, keys, and what is
  deliberately out of scope.
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — how to build with it: the
  render protocol and the controller verbs, the driver in call order, the
  component catalogue, the Theme fields, the dispatch order and the
  build-your-own walkthroughs.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed between releases.
- [`docs/releases/`](docs/releases/) — the release notes as published on
  GitHub, one page per release.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how the code is changed and how
  releases are cut: the gates, the invariants, the versioning policy.

**Source**: [`Shingwha/motui`](https://github.com/Shingwha/motui) — issues and
pull requests go to [the tracker](https://github.com/Shingwha/motui/issues).

## License

MIT — see [`LICENSE`](LICENSE).
