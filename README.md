# motui

A **layered, full-screen TUI toolkit**. It takes over the terminal on the
alternate screen, renders a document of addressable blocks one diffed row at
a time, owns its own scrollback, and keeps **pinned bands** (fixed top/bottom
regions, the frame's footer band) that never scroll away. Any Python program
can build its own components and screens on it: the library ships parts, not
an application. Runtime dependency: **`wcwidth` only**. Python **3.12+**.

- [Install](#install)
- [Quickstart](#quickstart)
- [The import contract](#the-import-contract)
- [Features](#features)
- [The demo](#the-demo)
- [Building your own shell](#building-your-own-shell)
- [Chrome, panes, overlays](#chrome-panes-overlays)
- [Styling: Theme](#styling-theme)
- [Keys and keymaps](#keys-and-keymaps)
- [The driver at a glance](#the-driver-at-a-glance)
- [Package layout](#package-layout)
- [Components](#components)
- [Testing without a terminal](#testing-without-a-terminal)
- [Docs](#docs)
- [License](#license)

## Install

```bash
pip install motui      # or: uv add motui
```

The wheel carries its own demo, so `python -m motui` is one command away.

## Quickstart

A minimal interactive app: a `Button` and a `Checkbox` (the minimal action
primitives), a `FocusRing` for the keyboard and a `Pointer` for the mouse —
no chat layer, no pinned input box. Run it on a real terminal, or drive it
headless: the same body replays scripted events.

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

`tests/test_readme_examples.py` runs exactly this snippet headless — the
scripted source activates, clicks and hovers — so the docs cannot rot.

Selection is one dispatch line, and it composes the way a bracketed `Paste`
does: reports and pastes both arrive through `read_key()`, both belong to the
host's dispatch, and neither is interpreted by the driver — the terminal
brackets the paste, the gesture owns the drag. While a drag is in flight the
left button is the gesture's; a drag to the viewport's edge row auto-scrolls
across pages (the pinned footer never scrolls), release copies the extracted
range through OSC 52, and a plain click clears without touching the
clipboard. The knobs, the state machine and the four replacement points (its
own `set_selection` loop, its own `on_end`, the sub-gesture knobs, the
highlight style) are in [`docs/COMPONENTS.md`](docs/COMPONENTS.md); the
rationale is in [`docs/DESIGN.md`](docs/DESIGN.md).

## The import contract

The root is the curated face: **31 names** in one import line. Every other
name stays public — one name, one home — at its own layer namespace:

```python
from motui import TUI, Input, Markdown            # the root: 31 names, one line
from motui.widgets import Row, Panel, Diff        # the widget library, complete
from motui.kernel import Style, Line, Selection   # the kernel seam
from motui.keys import DEFAULT_INPUT_KEYMAP
from motui.interaction import FocusRing, Pointer, SelectionGesture, Find
from motui.chrome import Scrollbar, Toasts
```

The layers:

- **`kernel`** — the kernel and the root of the dependency graph: the
  `Line`/`Segment` row primitive, `Style`/`Theme`, the event model, the
  document model, the render core (screen / viewport / painter), the frame
  model (`Pane`, `Rect`, the split algebra, the compositor), the interaction
  protocols (`Clickable`, `Activable`, `Focusable`, `Hoverable`, `Container`,
  `descend`) and the selection kernel (`Selection`, `highlight`, `extract`).
- **`keys`** — the byte decoder, the key sources, and the three keymap
  tables (`DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP`,
  `EDITOR_SUBMIT_KEYMAP`) `Input`/`Editor` consume.
- **`widgets`** — the generic component library (`Text`, `Input`, `Markdown`,
  `Table`, `Tree`, …), the minimal action primitives (`Button`, `Checkbox`,
  `Link`), the two-column `StatusLine` and the self-contained `Palette`, plus
  the `widgets.markdown` rule registries and the `widgets.syntax`
  highlighting seam.
- **`interaction`** — the four strategy tiers a host mounts on the driver:
  the mouse-selection policy tier (`SelectionGesture`, `copy_on_select`), the
  pointer tier (`Pointer` — hover tracking and stationary clicks beside the
  gesture), the focus tier (`FocusRing` — registered targets, the cycle, the
  routing table and the click policy) and the search tier (`Find` — the query
  row it owns, the matches and the reveal).
- **`app`** — the `TUI` driver, the composition root: blocks, panes, the
  frame, the pump and the repaint throttle.
- **`chrome`** — the frame-chrome and overlay assembly tier (`Scrollbar`,
  `Toasts`, `Tooltip`, `Stats`), one level above the kernel.
- **`testing`** — `headless_tui` and `snapshot`.

The root's 31 names are the driver (`TUI`), the styling trio (`Theme`,
`DEFAULT_THEME`, `Style`), the row primitive (`Line`, `Segment`) plus `Text`,
the event trio (`Key`, `MouseEvent`, `Paste`), the content, editing, data,
selection and action components an application reaches for first, the wiring
entry points of the interaction and chrome tiers, and the two headless
helpers. Everything else is one import deeper:

| Import from | What lives there |
|---|---|
| `motui` | the curated surface, 31 names: `TUI`, `Scrollbar` / `Toasts`, the components a host starts with (`Button` / `Checkbox` / `Link`, `Input` / `Editor`, `Palette` / `StatusLine`, `Table` / `Tabs` / `Tree` / `List` / `Markdown` / `Option` / `Select`), the styling trio (`Theme` / `DEFAULT_THEME` / `Style`), the row primitive (`Line` / `Segment` / `Text`), the event trio (`Key` / `MouseEvent` / `Paste`), the interaction entry points (`SelectionGesture` / `Pointer` / `FocusRing`) and the headless pair (`headless_tui` / `snapshot`) |
| `motui.kernel` | the kernel facade: `Painter`, `Viewport`, `ScreenLayout`, `Document`, `BlockState`, the interaction protocols (`Clickable`, `Activable`, `Focusable`, `Hoverable`, `Container`, `descend`), the inline-action lookup (`action_at`), `MORE_BELOW`, `Text`, `ellipsize_tail`, `wrap_line`, the selection kernel (`Selection`, `highlight`, `extract`), the capability switches (the screens' `focus_events` / `color_mode`, `Painter(sync=...)`), the `kernel.ansi` escape helpers |
| `motui.widgets` | the component library's own facade: the full catalogue including the names the root leaves off (`Diff`, `Panel`, `Row`, `ProgressBar`, `Radio`, `Spinner`, …), each defined in its own module (`widgets.table`, `widgets.list`, `widgets.editor`, …) |
| `motui.kernel.frame` | the frame model below the driver's face: `Rect`, `Split`, `Chrome`, `Frame`, `FrameTable`, `Overlay`, `splice_row` |
| `motui.kernel.lines` | `wrap_line` (also on the kernel facade) and `styled_with`, the uncached row rendering for a downgraded color mode |
| `motui.interaction` | the four strategy tiers: the selection policy (`SelectionGesture` — press/drag/release/edge auto-scroll/click count: word, then line — and `copy_on_select`, the shipped `on_end` default), the pointer tier (`Pointer` — hover tracking, a button-named motion is a drag and stays the gesture's, the button-free one moves the hover, row-level `hover_at` dispatch, stationary clicks through the ring or to the deepest clickable leaf), the search tier (`Find` — the query row it owns, the `matches` a query addresses as `(bid, row, start, end)`, the wrapping cursor, the reveal of the current match and the overlay that marks them) and the focus tier (`FocusRing` — registered targets, `focus`/`focus_next` cycling, the `handle` routing table, the click policy) |
| `motui.chrome` | the frame-chrome assembly tier: `Scrollbar` (chrome + gesture), `Toasts` (overlay + controller), `Tooltip` (the hovered leaf's `hint`, painted beside the pointer) and `Stats` (the dev readout: frames and rate, counted events, the hover) — `Scrollbar` and `Toasts` also sit on the root, `Tooltip` and `Stats` do not |
| `motui.app` | the driver's own module face: `TUI`, `Hit` (the block-internal cell a click resolves to) and `EveryHandle` (a cancellable `tui.every` callback) |
| `motui.kernel.style` | `Style`, the named-16 `FG_CODES`, the palette constants not on the root (`BORDER`, `CODE`, `CURSOR`, `SELECTION`, `HEADING`, `LINK`, `INLINE_CODE`, `LIST_MARKER`, `NONE`), and the color-capability functions (`ColorMode`, `detect_color_mode`, `sgr_prefix`, `quantize`) |
| `motui.keys` | `KeyDecoder`, `RawTerminalKeys`, `Keymap` and the three default tables (`DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP`, `EDITOR_SUBMIT_KEYMAP`) — the event *model* itself (`Key`, `Paste`, `MouseEvent`, `KeySource`, `ScriptedKeys`) lives in `kernel.events` and its value types are on the root |
| `motui.widgets.markdown` | `BlockRule` / `InlineRule` / `RenderContext`, `BLOCK_RULES` / `INLINE_RULES`, `default_block_rules`, `default_inline_rules`, every built-in rule class |
| `motui.widgets.syntax` | `Highlighter`, `RegexHighlighter`, `default_highlighter`, `highlight` |

## Features

- **alt screen** — standard vim/htop-style full screen; the shell is restored on exit.
- **viewport scrollback** — the whole document stays resident in memory; the screen is a window, the page keys (`page_up`/`page_down`) scroll back.
- **mouse** — the wheel scrolls (SGR 1006); presses, releases and motion reports decode into 0-based `MouseEvent`s (each carrying `kind`) and `tui.hit_test(x, y)` resolves one to the block under it — the host dispatches clicks, never the driver.
- **mouse selection & copy** — one `SelectionGesture(tui)` line: drag selects (document-space addresses, so the highlight follows its text through scrolls and the copied range reaches rows scrolled out of view), a hold on the viewport's edge row auto-scrolls across pages, release copies through OSC 52 (best-effort; the `on_end` hook is the real contract). Repeated presses at one cell count: the second selects the word under the pointer, the third its whole visible line, the fourth starts over. Enabling mouse reporting takes the terminal's native selection away — the same bargain bracketed paste made: the terminal hands over the bytes, the application owns the gesture.
- **hover** — `Pointer(tui)` watches the same reports: the leaf under the pointer takes its `hover` flag (and row-level `hover_at` where a component has rows), a press and release on one cell is a stationary click, and a drag's motion stays the gesture's — a motion that names a button is a drag, only the button-free one moves the hover. Hover needs DECSET 1003, so it is opt-in — `TUI(hover=True)` — and the default mode stays 1000+1002+1006.
- **frame chrome** — one `Scrollbar(tui)` line budgets a column at the pane's edge and maps the scroll onto it (press to page, drag the thumb); the bar is the reference chrome, and a custom rail is one `Chrome` protocol away.
- **split panes** — `tui.split("vertical")` tiles the frame (transcript | preview): the first child keeps the document, a 1-cell tmux-convention divider between them, focus by press or `c-o`, and the wheel routed by pointer position.
- **toasts** — `Toasts(tui)` floats transient bands over the composed frame (a corner stack, TTL-bounded, click-to-dismiss), the reference overlay.
- **tooltip** — `Tooltip(tui, pointer)` paints the hovered leaf's own `hint` as a one-line theme-`toast` band beside the pointer, clamped into the frame; `Button` / `Checkbox` / `Link` declare the attribute, and a leaf without one shows nothing (zero bytes).
- **pinned tail** — a scrolling region on top, fixed blocks (input / status) at the bottom. A pinned footer lives in the frame's bottom **band**: its own viewport, below the pane area, so a split never cuts it in half.
- **pluggable keyboard** — one decoder feeding scripted or raw terminal sources; editing keys route through configurable keymaps and enter `handle(event)`.
- **themeable** — one frozen `Theme` carries every semantic style; components resolve it once at construction and `dataclasses.replace` restyles the whole toolkit at once.
- **markdown** — a streaming-safe rule-registry engine in `widgets/markdown`: GFM tables, fenced code, an inline/bold/strike/italic/link registry you extend with your own rules.
- **syntax highlighting** — a zero-dependency `motui.widgets.syntax.Highlighter` seam, wired into Markdown fences and injectable.
- **testable without a terminal** — `headless_tui` + `snapshot`.

## The demo

`python -m motui` runs the library's own front page: a demo that ships in the
wheel — **11 pages under a left rail**, the page content on the right, the
shell built from the same library it shows off. It answers **locally**: no
network, no model.

```bash
python -m motui              # a real terminal: the full screen
python -m motui < /dev/null  # piped: replays headless, dumps the final screen
python -m motui --pages      # every page as plain text, no terminal needed
```

The frame is a split: the left pane's document carries a **vertical `Tabs`**
— one row per page — and the right pane carries the page's own document, so
the rail never scrolls with the content and both halves are ordinary panes
(own viewport, own scroll state, own hit domain). A click on a label opens
that page, `c-n` / `c-p` step to the next and the previous one (the ends
wrap), and `q` / `c-c` quit. The header band holds the window title per page
and the cursor shape; the pinned footer reads the shell's own key hints
(`c-n/c-p pages · tab focus · c-o pane · c-f find · c-g stats · q`, a
`ShortcutBar`) above a `StatusLine` that reads `<page> · focus=<target>` on
the left and the frame rate on the right.

**There is no input box anywhere in the demo, and the shell has no `/`
command palette.** Navigation is the rail's — one screen, visible and
clickable — and everything the palette used to carry has a direct key
(`c-o` pane focus, `c-f` find, `c-g` stats, `q` quit); a modal panel beside
the rail would be a second navigator that owns keys without owning a job.
The `Palette` component still ships and is still on a page: the `chrome` page
holds it as an **exhibit** — open it there and its own query row, its
filtering and its pick answer for themselves. **`c-f` opens the search tier**
(`Find`), the other self-contained query row: type and every match on the
page is marked on its own band, `enter`/`↓` walk to the next match and `↑` to
the previous one (the current one centered into view), `escape` closes —
while it is open it owns the keyboard, so typing `q` searches for a `q`.
**`c-g` mounts the dev stats overlay** (`Stats`) in the frame's top-right
corner — frames and the window frame rate, the events this round has counted,
the hovered leaf — and the next `c-g` retires it.

**Two roads lead to a page**, plus the `overview` page's own index: a click
on a rail label (the host follows `Tabs.active` once per round, the same road
a click on a widget takes) and `c-n`/`c-p`. Every page answers the same three
questions with the same helpers: a header (title, blurb, rule), a `TRY ▸`
line saying what to do here, an `API ·` note naming the real API behind the
exhibit, and labelled rules between the parts. The eleven pages:

- `overview` — what the demo is, how it is organised, and a clickable index of the rest
- `content` — `Text`, `Markdown` (GFM tables, fenced code, inline rules) and `Diff`
- `data` — `Table`, `List` and `Tree`: a row cursor, a pick, the row under the pointer
- `input` — `Input`, `Editor` and `Autocomplete`: click any cell and the block cursor lands there
- `choice` — `Select`, `Confirm`, `Radio` and `Checkbox`: activate one and the page echoes it
- `action` — `Button`, `Link` and `Slider`
- `layout` — `Panel`, `Row`, `Column`, `Padding`, `Spacer`, `Divider`, a `Collapsible` that folds on `enter`, and `Notice`
- `feedback` — `ProgressBar`, `Spinner`, `StatusLine`, `Toasts` and `Tooltip`
- `chrome` — split panes, `Scrollbar`, `Stats`, the selection copy, a live hit-test probe, and the `Palette` exhibit
- `styles` — a theme picker plus the themes color by color, style attributes and color forms: activate a row and the whole shell re-skins
- `streaming` — a fixture streamed **block by block**; a control bar (`play / pause / step / replay / speed`) drives the document

A page that can be played with mounts a `FocusRing`: `tab` cycles its
widgets, `↑↓` drive the focused widget's cursor and `enter` activates it. A
**click focuses**: the first click on a ring target focuses it, the second
activates it, and every widget that answers `click(row, col)` is dispatched
its cell either way. **Hover is the pointer tier's** — the demo opens
`TUI(hover=True)` (DECSET 1003), and the leaf under the pointer takes the
`hover` band; the `action` page is the plainest place to see it, three
primitives with three hovers. Nothing an activation produces goes unseen: the
host reads each page component's `chosen` once per event round and reports it
— a toast, plus the page's own echo line (`data`, `choice`, `action`,
`feedback` and `styles` each keep their last pick in one) — and a pick whose
value names a page opens that page (`overview`'s index is the registry) while
one that names a theme variant re-skins the shell (`styles`). The pages stay
live: the focus, hover, click and pick paths are the real component APIs, not
screenshots.

The `chrome` page mounts a preview pane of its own: its `enter` hook opens
one more `tui.split`, its `leave` hook closes it on the way out, and `c-o`
moves the pane focus between the columns — panes, the pane focus and the
un-split, on the same frame the rail already divides.

Both no-terminal paths are **dump-safe**, and the streaming page is where
that shows: no beat and no pump clock run there, so the page is built
complete — `--pages` prints the whole fixture, and the replay builds it whole
on its way through, never a partial document. The piped run replays a
scripted session — every page through the rail, the rings driven by key, a
hover and a click, a drag and its copy, the wheel — and dumps the last frame
as plain text.

The demo is a demo, not a shell to copy — the library ships no app shell.
The recipe for building your own (a footer `Document` with an `Editor` and a
`StatusLine`, parked in the frame's bottom band) is the runnable snippet in
[Building your own shell](#building-your-own-shell) and the longer walkthrough
in [`docs/COMPONENTS.md`](docs/COMPONENTS.md).

## Chrome, panes, overlays

Everything that draws outside the document flow is exactly one of three
claims on screen space — a **pane** (an exclusive rectangle owning its own
viewport), **chrome** (a budgeted band inside a pane's rectangle, re-wrapping
its content) or an **overlay** (a pure paint over the composed frame) — and
picking which one a feature *is* is the design step. `Scrollbar` is the
reference chrome, `Toasts` the reference overlay and `Tooltip` the minimal
one (the hovered leaf's `hint`, one band beside the pointer), `Stats` the
developer's readout (frames and rate, the counted events, the hover), `Find`
the search tier (its own query row, the matches, the reveal), and `tui.split`
the pane tier:

```python
scrollbar = Scrollbar(tui)                  # chrome: budgets a column, maps the scroll
toasts = Toasts(tui)                        # overlay: corner-anchored transient bands
pointer = Pointer(tui)                      # hover + stationary clicks (TUI(hover=True))
tooltip = Tooltip(tui, pointer)             # overlay: the hovered leaf's hint, no input
stats = Stats(tui, pointer=pointer)         # overlay: frames, frame rate, events, hover
left, right = tui.split("vertical", ratios=(2, 1))   # panes: the first keeps the document
right.document.add(Markdown(text))          # ...the second opens over a fresh one
```

**The dispatch order** is one rule everywhere — chrome, then overlays, then
the panes' content gestures, then the host's own dispatch — and it is
geometric at every step: the bar's strip and a toast's band are derived from
the frame's rectangles, so both route *before* a hit test runs (a press that
reached a hit test first would anchor a selection on the text beneath them):

```python
if not scrollbar.handle(event):        # 1. chrome, first
    if not toasts.handle(event):       # 2. overlays, next
        if not gesture.handle(event):  # 3. content gestures
            ...                        # 4. the host's own dispatch
```

The wheel is nobody's chrome — `read_key` intercepts `scroll_keys` and routes
a wheel report to the pane *under the pointer*. The sketches, the two
"build your own" walkthroughs (a custom 2-column rail reading
`offset/total_rows`; a custom overlay on the registry protocol) and the full
dispatch contract are in
[`docs/COMPONENTS.md`](docs/COMPONENTS.md); the three-space-claims
constitution, the compositor, budget negotiation and the retile are in
[`docs/DESIGN.md`](docs/DESIGN.md).

## Package layout

```
src/motui/
  __init__.py                       # the curated public API: 31 names, one import line
  app.py                            # the TUI driver (the composition root)
  chrome.py  testing.py             # the frame-chrome assembly + the headless helpers
  interaction/                      # the four strategy tiers, one module each
    focus.py  pointer.py            # the focus ring + the pointer tier (hover, stationary clicks)
    gesture.py  search.py           # the selection policy tier + the search tier (Find)
  kernel/                           # the kernel
    __init__.py                     # kernel facade
    frame.py                        # Rect + Split: the split algebra + the compositor
    style.py  theme.py              # Style + Theme (+ DEFAULT_THEME) and the Themed base
    text.py  lines.py  ansi.py      # measuring + Text, rows, escape bytes
    events.py                       # Key/Paste/MouseEvent + the source protocol
    block.py                        # Component / Block / Document (+ the interaction protocols)
    screen.py  viewport.py  painter.py   # the render core
    selection.py                    # the document-space selection kernel
  keys/                             # input
    __init__.py                     # keys facade
    decoder.py                      # the Key/Paste/MouseEvent byte decoder
    keymap.py                       # Keymap + the three default tables
    sources.py  console.py          # the raw source, Windows plumbing
  widgets/                          # the generic component library
    __init__.py                     # widgets facade
    markdown/                       # the Markdown rule-registry engine
      inline.py  blocks.py          # the inline rules + the block rules & loop
      nested.py  tables.py          # quote/list rules, the GFM table
      context.py  component.py      # RenderContext + the Markdown component
    table.py  spinner.py  decor.py  textbuf.py
    field.py  input.py  editor.py   # the shared text-field shell + the two public fields
    button.py  checkbox.py  link.py # the action primitives
    choice.py  syntax.py            # Select/Confirm/Option, the highlighter seam
    statusline.py  palette.py       # the two-column status row + the command palette
    autocomplete.py  progress.py  tabs.py  tree.py  layout.py
  demo/                             # the shipped demo behind `python -m motui`
    __main__.py                     # the module entry point
    shell.py  session.py            # the shell (rail, header, footer) + the host loop
    registry.py  script.py          # the page table + the headless replay
    pages/  fixture.md              # one page builder per file + the streaming source
```

`from motui import …` is the one face an application needs. `app.py`,
`chrome.py`, `testing.py` and the `interaction/` tiers sit above the kernel
because they compose it with the `keys` layer; each facade (`motui.kernel`,
`.keys`, `.widgets`, `.interaction`, `.app`, `.chrome`, `.testing`) is
complete for its own layer, and `tests/test_api_root.py` pins every one — the
root and every layer facade.

## Components

Every component renders through the frozen `render(width) -> list[Line]`
protocol, and the interactive ones carry controller methods beside it:
`handle(event) -> bool` (`Input` / `Editor` / `Palette`),
`click(row, col) -> bool` (the text fields, the lists and the tab strip),
`move(delta)` /
`activate()` / `select(index)` — the menus wrap their ends, the tab strip
and tree clamp, and a menu's activation lands the picked option in
`chosen`. The focusable ones carry one more flag: `focused: bool` (the
text fields draw their block cursor by it; the lists, the tree and the tab
strip render an unfocused cursor row in their cursor style merged with the
theme's `dim`) — `FocusRing` sets it as the focus moves, and the component
never learns a manager exists. The pointer-driven ones carry `hover: bool`
and, where a component has rows, `hover_at(row, col) -> bool` (`row < 0`
means the pointer left) — `Pointer` writes both, the component only renders
by them — while the wrapping containers translate a cell for their children
through `child_at(row, col) -> (component, row, col) | None`: a click
through a `Row` / `Padding` / `Panel` reaches the leaf
(`tui.hit_component(x, y)` resolves it), and a container never proxies the
leaf's own methods.
Styles resolve **once, at construction**, as explicit `style=` > `theme=`
field > `DEFAULT_THEME`. The 31 most used import straight from `motui`; the
rest are one import away from `motui.widgets` — the catalogue, the
capability tables and the build-your-own walkthroughs are in
[`docs/COMPONENTS.md`](docs/COMPONENTS.md).

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

| Theme field | Default | Used for |
|---|---|---|
| `dim` `muted` `accent` `success` `error` `warning` `border` `code` `cursor` `selection` | the matching `motui.kernel.style` constant | the shared semantic styles |
| `heading` `link` `inline_code` `list_marker` | the matching `motui.kernel.style` constant (`#e3b341` gold, `#58a6ff` underlined, `#f778ba` pink, `#bc8cff` purple) | the Markdown heading ladder, link labels, inline `` `code` ``, list markers |
| `hover` | reverse video | the pointer tier's hover band |
| `table_border` | none (uncolored) | `Table` grid lines |
| `first_column` | none (plain) | `Table` first data column |
| `headings` `notice_levels` | derived from the colors above | read-only structural tables (`Theme()` rebuilds them) |

Bold is reserved for the `**…**` syntax itself and strike for `~~…~~`: no
default style above is bold or struck (syntax highlighting's keyword=accent
aside) — Markdown signals structure with color (gold headings, underlined
blue links, pink inline code, purple list markers, italic quotes) instead of
weight.

## Keys and keymaps

`KeyDecoder` is a pure `bytes -> events` machine (UTF-8, control names, CSI
navigation, bracketed paste — the screen opens DECSET 2004 on entry, so a
paste arrives wrapped in `\x1b[200~`/`\x1b[201~` and decodes to one event —
and SGR mouse). Editing keys route through a
**keymap** — key event name to the editing method it triggers — which
`Input`/`Editor` resolve at construction:

```python
from motui import Input
from motui.keys import DEFAULT_INPUT_KEYMAP

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]   # unbound: the host sees the event again
```

`DEFAULT_INPUT_KEYMAP` binds arrows/home/end/backspace/delete/`c-a`/`c-e`/
`c-u` (and up/down for wrapped rows), `c-z`/`c-y` for the buffer's bounded
undo/redo, and the `s-left`/`s-right`/`s-up`/`s-down`/`s-home`/`s-end` shift
chords for the text-internal selection (`c-a` selects the whole field; the
line start is the plain `home`), but leaves `enter` unbound — the return
key is the host's submit gesture. `DEFAULT_EDITOR_KEYMAP` adds `enter` as
`newline`, and `EDITOR_SUBMIT_KEYMAP` (the editor table minus `enter`, `c-j`
as `newline`) is what an editor whose host owns the submit gesture resolves.
All three tables live together in `keys/keymap.py` with the derivation chain
visible, and each is re-exported from `motui.keys`. A component consumes
one event at a time through
`handle(event) -> bool`, so the wrap geometry `move_up`/`move_down` follow
still comes from the component's last render — the event never carries it.

## The driver at a glance

In call order (not a runnable script — every call is on the driver):

```python
tui.add(comp, id="x", pin=None)        # append a block (auto id "b0"…); pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.system("system line")             # muted system block (no raw stdout writes)
tui.invalidate(); tui.paint()         # mark dirty / paint one frame now
tui.rows                              # the current frame: exactly screen.height rows
tui.every(0.1, fn)                    # periodic callback, returns a cancellable handle
tui.clock()                           # the pump's monotonic clock (the one time seam)
tui.tick(now)                         # advance the pump: due callbacks, then one frame
event = await tui.read_key()          # next key; page keys and the wheel scroll and are absorbed
tui.scroll_up(2); tui.scroll_to_bottom()
tui.reveal("b3", 12)                  # bring a document address on screen (centered, clamped)
tui.viewport.scroll_to(offset)        # the pane's window: an absolute jump, clamped
tui.viewport_rows()                   # the focused pane's window as (first, last), or None
tui.split("vertical", ratios=(2, 1))  # tile the focused pane: first child keeps the document
tui.add_band(viewport)                # park a footer viewport in the frame's bottom band
tui.set_title("my app")               # OSC 2 window title (control bytes scrubbed)
tui.set_cursor_shape("beam")          # DECSCUSR: block/beam/underline/default
tui.hit_test(x, y)                    # a 0-based cell -> the block under it (or None)
tui.hit_component(x, y)               # ...or the deepest leaf: child_at descends every container
tui.selection; tui.set_selection(sel) # the document-space selection overlay; None clears
tui.stop()                            # ask run() to finish
```

`TUI().run(body)` brackets `enter`/`leave`, runs a throttle/repaint pump, and —
on a non-live screen (pipe/file) — stays silent during the run and dumps the
final screen as plain text on exit. `TUI(theme=...)` sets the theme the
driver's own chrome reads (the split's separator; widgets take their own
`theme=`), and `TUI(hover=True)` opens DECSET 1003 — any-event motion — for a
`Pointer`; the default mouse mode stays 1000+1002+1006. `read_key` intercepts
the `scroll_keys` table (`tui.scroll_keys`, rebind or `del` entries to hand
an event back) and returns `None` on a non-live screen even with a source
attached.

Every non-empty frame is bracketed by DECSET 2026 (synchronized output) by
default — `TUI(sync=False)` drops the pair — and the rows are rendered for
the screen's color capability: `TUI(color_mode="truecolor"|"256"|"16"|"none")`
overrides the environment probe (`NO_COLOR`, `TERM`, `COLORTERM`) the default
screen's `"auto"` runs. `TUI(focus_events=True)` opens DECSET 1004, so the
decoder hands the host `focus_in` / `focus_out` events. A mouse click
resolves through the driver — the host dispatches (inside the async body,
where an `await` is legal):

```python
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)             # 0-based coords; None when no block owns the cell
    if hit is not None:
        hit.block.component.click(hit.row, hit.col)  # e.g. a Select: it ignores the column
```

## Building your own shell

The library ships no app shell — no chat layer, no pinned input box, no
demo mode to copy: the components plus the tiers are the whole toolkit, and
a host assembles its own. The shape is three pieces: the body document the
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

(`Document` and `Viewport` are the two deeper seams this recipe reaches for;
both stay public at `motui.kernel` — the root's curated face is listed in
[The import contract](#the-import-contract).)

`tests/test_readme_examples.py` runs this recipe headless: a scripted
session types, submits and quits, and the footer's own blocks are asserted
in place below the pane area.

Every other tier mounts with one line beside the loop: a `Palette` in the
footer document opens on a freshly typed `/` and owns the keys while open,
`SelectionGesture` adds drag selection (a drag's motion keeps its clicks),
`Pointer` adds hover and stationary clicks, `FocusRing` routes the keys a
focused widget owns, and `Scrollbar` / `Toasts` bring chrome and overlays —
[Chrome, panes, overlays](#chrome-panes-overlays) spells out the dispatch
order they route in. The complete shell recipe lands in
[`docs/COMPONENTS.md`](docs/COMPONENTS.md).

## Testing without a terminal

`headless_tui(...)` builds a driven `TUI` on a `HeadlessScreen` with a
`ScriptedKeys` source; `snapshot(tui)` renders the document to rows for
assertions. The [demo](#the-demo) doubles as a smoke test in piped mode:
`python -m motui < /dev/null` visits every page, dumps the
final screen as plain text and exits 0 — the piped dump is the whole
assertion, and `--pages` dumps the pages one by one. The no-color path is a
run of its own: `NO_COLOR=1 python -m motui --pages` exits 0
too (`HeadlessScreen` pins its `color_mode` to `"truecolor"`, so a test's
bytes never depend on the machine, and the probe is what a live
`TerminalScreen` reads).

**Golden frames.** Every demo page is also pinned byte for byte:
`tests/golden/pages/<page>.txt` holds one `--pages` dump per page, and
`uv run python tools/golden.py --check` — the same assertion as
`tests/test_golden_frames.py` — diffs them by name. `--update` re-records
the whole set, for a wave that *means* to change what a user sees.

The same gates run on every push and pull request:
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) syncs the lock with
`uv`, then runs `pytest -q`, framebench (the exit code and the presence of
the hash line, not the hash's value), the golden check, the piped replay and
the page dump — on Ubuntu and on Windows alike.

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — the layers and the focus tier, the 0-based coordinate charter, screen model, viewport, painter, driver, keys, keymaps, highlighting, the selection rationale (D1–D8) and mode table, the pointer tier and the hover rationale (1002 vs 1003, the wire's button-free motion), the non-TTY contract, and the frame model (the three space claims, the compositor, budget negotiation, focus and wheel routing, the pinned footer band, and the un-split).
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the `render(width)` protocol, the component catalogue, the Theme fields, the frame tier (`Pane` / `split` / `close` / `Scrollbar` / `Toasts`) with the dispatch-order contract, the `SelectionGesture` state machine and selection cookbook, the focus tier (`FocusRing`'s routing table and click policy), the footer-band recipe for assembling an app, the "build your own" walkthroughs (a custom 2-column chrome rail; a custom overlay; a clickable-through container), a custom `Markdown` rule walkthrough on `RenderContext`, and a custom-component walkthrough.
- [`docs/API.md`](docs/API.md) — generated, not hand-written: every facade's curated names, each with its signature, the first paragraph of its docstring and the module that defines it (`tools/apidoc.py`; `--check` is the drift gate `tests/test_api_doc.py` runs).

**Releases** are tag-driven: pushing a `v*` tag runs
[`.github/workflows/release.yml`](.github/workflows/release.yml) — `uv build`
on both platforms, then a trusted-publishing upload to PyPI; the file's
comments spell out the one-time PyPI-side configuration (the trusted
publisher's environment name — no secret lives in the repository).

Not on purpose (see `docs/DESIGN.md`): document-size caps / history trimming
(the document stays resident in full), runtime color negotiation (the palette
is 24-bit truecolor; a VT probe only gates streams that cannot render escapes
at all), drag-to-resize dividers and cross-pane selection (drag selection and
scrollbar dragging both ship — `SelectionGesture` consumes the press, motion
and release reports mode 1002 delivers, and the bar consumes its own strip —
but the divider's ratio is fixed at split time, selection stays
single-document, and multi-range selection stays at one range, while the
decoder still drops the horizontal wheel and unknown button codes), math
rendering in Markdown (the rule registries are the documented extension
point), and any sleep in the library or its tests.

## License

MIT — see [`LICENSE`](LICENSE).
