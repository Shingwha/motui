# mocode-tui

A **layered, full-screen TUI toolkit**. It takes over the terminal on the
alternate screen, renders a document of addressable blocks one diffed row at
a time, owns its own scrollback, and keeps **pinned bands** (fixed top/bottom
regions, the frame's footer band) that never scroll away. Four layers compose
it, with the driver and the headless helpers sitting above the kernel:

- **`core`** — the kernel: `Style`/`Theme`, the `Key`/`Paste`/`MouseEvent`
  event model, the document model, the `Text` component, the measuring
  helpers, the render core (screen / viewport / painter), the frame model
  (`Pane`, `Rect`, the split algebra, the compositor), the interaction
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
- **`app`** / `gesture` / `pointer` / `focus` / **`chrome`** / **`testing`** —
  the `TUI` driver (the composition root), the mouse-selection policy tier
  (`SelectionGesture`, `copy_on_select`), the pointer tier (`Pointer` — hover
  tracking and stationary clicks beside the gesture), the focus tier
  (`FocusRing` — the peer of `gesture`: registered targets, the cycle, the
  routing table and the click policy), the frame-chrome and overlay assembly
  tier (`Scrollbar`, `Toasts` — one level above the kernel), and
  `headless_tui` / `snapshot`.

Any Python program can build its own components and screens on it; it is not
tied to a host. Runtime dependency: **`wcwidth` only**. The package root
exports a curated **66 names** — one import line for a host — and every
deeper seam stays public at its own module path.

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
- **syntax highlighting** — a zero-dependency `mocode_tui.widgets.syntax.Highlighter` seam, wired into Markdown fences and injectable.
- **testable without a terminal** — `headless_tui` + `snapshot`.

## Quickstart

A minimal interactive app: a `Button` and a `Checkbox` (the minimal action
primitives), a `FocusRing` for the keyboard and a `Pointer` for the mouse —
no chat layer, no pinned input box. Run it on a real terminal, or drive it
headless: the same body replays scripted events.

```python
import asyncio

from mocode_tui import Button, Checkbox, FocusRing, Key, MouseEvent, Pointer, Text, TUI


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

## The demo

`examples/demo.py` is the library's living front page: a **gallery** of thirteen
pages — one theme per page — whose shell (pinned header, pinned status row,
scrollbar, toasts, modal palette) is built from the same library. It answers
**locally** — no network, no model.

```bash
uv run python examples/demo.py              # a real terminal: the full screen
uv run python examples/demo.py < /dev/null  # piped: replays headless, dumps the final screen
uv run python examples/demo.py --pages      # every page as plain text, no terminal needed
```

**There is no input box anywhere in the gallery.** Its two text inputs are
query rows the shell's own tiers carry. The `/` palette is the modal one
(`widgets.Palette`, registered on the frame as an overlay only while open)
with its own query row, drawn over the page's bottom rows on the theme's
`toast` band: `/` opens it, typing filters the commands, `↑↓` walk the list,
`enter` takes the command and closes the panel, and `escape` closes it with
nothing taken; closed, it contributes no rows, no registry entry and no keys.
**`c-f` opens the search tier** (`Find`), the other self-contained query row:
type and every match on the page is marked on its own band, `enter`/`↓` walk
to the next match and `↑` to the previous one (the current one centered into
view), `escape` closes — while it is open it owns the keyboard, so typing `q`
searches for a `q`. **`c-g` mounts the dev stats overlay** (`Stats`) in the
frame's top-right corner — frames and the window frame rate, the events this
round has counted, the hovered leaf — and the next `c-g` retires it. The
pinned status row reads
`<page> · focus=<target>` on the left and the frame rate on the right.

**Three roads lead to a page.** The header's pinned `Tabs` strip carries one
short label per page — a click on a label opens it (the host follows
`Tabs.active` once per round, the same road a click on a widget takes) —
`c-n` and `c-p` step to the next and the previous page (the ends wrap), and
the `/` palette takes a page by name. Every page answers the same three
questions with the same helpers: a header (title, blurb, rule), a `TRY ▸`
line saying what to do here, an `API ·` note naming the real API behind the
exhibit, and labelled rules between the parts. The thirteen pages:

- `/overview` — what the gallery is, and a live index: click a row, or `↑↓` + `enter`, to open that page
- `/content` — `Text` and `Markdown`; the paragraph re-wraps at whatever width the pane has, and the sample's link is a clickable span (a toast plus the page's echo line answer) and a real OSC 8 hyperlink the terminal itself can open
- `/data` — `Table`: a row cursor, a pick, and hover on the row under the pointer
- `/structure` — `Panel`, `Row`/`Column`, `Padding`, `Spacer`, `Divider` — the geometry, read-only
- `/input` — `Input` and `Editor`: click any cell and the block cursor lands there; hover bands the whole field
- `/choice` — `Select` (a windowed 20-row menu), `Confirm`, `Autocomplete` — activate one; the toast and the `last pick:` line report it
- `/navigation` — `Tabs` and `Tree`: click, `tab`, and the label or row under the pointer in hover
- `/action` — **`Button`, `Checkbox`, `Link`**: the minimal action primitives, one block each — hover a row and click it, or `tab` + `enter`
- `/feedback` — `ProgressBar` (one live), `Spinner` (one live), `Notice` — and a level selector that raises a real toast
- `/styles` — a theme picker plus the three themes color by color, style attributes, color forms — activate a row and the whole shell re-skins
- `/streaming` — the 346-line rendering fixture streamed **block by block**; a control bar (`play / pause / step / replay / speed`) drives the document, and opening the page replays it
- `/features` — panes, scrollback, selection, hover — with a right pane the page mounts on entry and closes on the way out
- `/devtools` — the developer toolbox: `Stats` (`c-g`), the golden frames, the recorded-replay pair, and a live hit-test probe resolved by `TUI.hit_component`

A page that can be played with mounts a `FocusRing`: `tab` cycles its widgets,
`↑↓` drive the focused widget's cursor and `enter` activates it (`/data`
steers the table, `/choice` walks four menus, `/navigation` the strip and the
tree, `/feedback` the level selector, `/styles` the theme picker,
`/streaming` the control bar, `/action` the button and the checkbox). A
**click focuses**: the first click on a ring target focuses it, the second
activates it, and every widget that answers `click(row, col)` is dispatched
its cell either way. **Hover is the pointer tier's** — the gallery opens
`TUI(hover=True)` (DECSET 1003), and the leaf under the pointer takes the
`hover` band; `/action` is the plainest place to see it, three primitives with
three hovers. Nothing an activation produces goes unseen: the host reads each
page component's `chosen` once per event round and reports it — a toast, plus
the page's own echo line (`/data`, `/choice`, `/action`, `/feedback` and
`/styles` each keep their last pick in one) — and a pick whose value names a
page opens that page (`/overview`'s index is the registry) while one that
names a theme variant re-skins the shell (`/styles`). The pages stay live: the
focus, hover, click and pick paths are the real component APIs, not
screenshots.

The one layout page, `/features`, opens a **right pane** of its own: its
`enter` hook runs the one `tui.split("vertical", ratios=(2, 1))` and its
`leave` hook closes the pane on the way out, so `/split` — the live preview
pane every other page can toggle from the palette — toasts there instead of
stacking a third pane, and `c-o` moves the pane focus between the columns.

Both no-terminal paths are **dump-safe**, and the streaming page is where that
shows: no beat and no pump clock run there, so the page is built complete —
`--pages` prints the whole fixture (its progress line reads
`streaming: 98/98 blocks · paragraph · done · 1x`), and the replay builds it
whole on its way through, never a partial
document. The piped run replays a scripted session — every page through the
`/` palette, the rings driven by key, the hover and the click on `/action`'s
button, a drag and its copy, the preview pane's wheel, the toasts dismissed —
and ends on `/action`, whose two echo rows (`last pick: True`, `[x] Trace`)
are the last frame the run paints.

The gallery is a demo, not a shell to copy — the library ships no app shell.
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
src/mocode_tui/
  __init__.py                       # the curated public API: 66 names, one import line
  app.py  gesture.py  pointer.py    # the TUI driver + the selection and pointer policies
  search.py                         # the search tier: Find (query row, matches, reveal)
  focus.py  chrome.py               # the focus tier + the frame-chrome and overlay assembly
  testing.py                        # headless test helpers
  core/                             # the kernel
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
```

`from mocode_tui import …` is the one face a host needs. `app.py`,
`gesture.py`, `pointer.py`, `search.py`, `focus.py`, `chrome.py` and
`testing.py` sit above the kernel because they compose it with the `keys`
layer; each facade (`mocode_tui.core`, `.keys`, `.widgets`, `.app`,
`.chrome`, `.gesture`, `.focus`, `.pointer`, `.search`, `.testing`) is
complete for its own layer, and `tests/test_api_root.py` pins every one —
the root and every layer facade.

## What lives where

The root is curated; everything a host rarely needs stays public at the
module path it lives in.

| Import from | What lives there |
|---|---|
| `mocode_tui` | the curated surface: `TUI`, the frame tier (`Pane`, `Scrollbar`, `Toasts`, `Tooltip`, `Stats`), the widgets (`Button`/`Checkbox`/`Link`, `Palette`, `StatusLine`, …), `Style`/`Theme`/`DEFAULT_THEME`, the semantic constants (`ACCENT`, `MUTED`, …), the selection kernel (`Selection`, `highlight`, `extract`), `SelectionGesture` / `copy_on_select`, `Pointer`, `Find`, `FocusRing`, `visible_width` / `wrap_text`, `headless_tui` / `snapshot` |
| `mocode_tui.core` | the kernel facade: `Painter`, `Viewport`, `ScreenLayout`, `Document`, `BlockState`, the interaction protocols (`Clickable`, `Activable`, `Focusable`, `Hoverable`, `Container`, `descend`), the inline-action lookup (`action_at`), `MORE_BELOW`, `Text`, `ellipsize_tail`, `wrap_line`, the selection kernel (`Selection`, `highlight`, `extract`), the capability switches (the screens' `focus_events` / `color_mode`, `Painter(sync=...)`), the `core.ansi` escape helpers |
| `mocode_tui.core.frame` | the frame model below the driver's face: `Rect`, `Split`, `Chrome`, `Frame`, `FrameTable`, `Overlay`, `splice_row` |
| `mocode_tui.core.lines` | `wrap_line` (also on the kernel facade) and `styled_with`, the uncached row rendering for a downgraded color mode |
| `mocode_tui.gesture` | the selection policy tier: `SelectionGesture` (press/drag/release/edge auto-scroll/click count: word, then line) and `copy_on_select`, the shipped `on_end` default |
| `mocode_tui.pointer` | the pointer tier: `Pointer` (hover tracking — a button-named motion is a drag and stays the gesture's, the button-free one moves the hover — row-level `hover_at` dispatch, stationary clicks through the ring or to the deepest clickable leaf), on the root as `Pointer` |
| `mocode_tui.search` | the search tier: `Find` (the query row it owns, the `matches` a query addresses as `(bid, row, start, end)`, the wrapping cursor, the reveal of the current match, and the overlay that marks them), on the root as `Find` |
| `mocode_tui.focus` | the focus tier: `FocusRing` (registered targets, `focus`/`focus_next` cycling, the `handle` routing table, the click policy), on the root as `FocusRing` |
| `mocode_tui.chrome` | the frame-chrome assembly tier: `Scrollbar` (chrome + gesture), `Toasts` (overlay + controller), `Tooltip` (the hovered leaf's `hint`, painted beside the pointer) and `Stats` (the dev readout: frames and rate, counted events, the hover), all root-public |
| `mocode_tui.core.style` | `Style`, the named-16 `FG_CODES`, the palette constants not on the root (`BORDER`, `CODE`, `CURSOR`, `SELECTION`, `HEADING`, `LINK`, `INLINE_CODE`, `LIST_MARKER`, `NONE`), and the color-capability functions (`ColorMode`, `detect_color_mode`, `sgr_prefix`, `quantize`) |
| `mocode_tui.keys` | `KeyDecoder`, `RawTerminalKeys`, `RecordingKeys` / `ReplayKeys` (the JSONL pair: record a session's events, replay them back as a regression), `Keymap` and the three default tables (`DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP`, `EDITOR_SUBMIT_KEYMAP`) — the event *model* itself (`Key`, `Paste`, `MouseEvent`, `KeySource`, `ScriptedKeys`) lives in `core.events` and its value types are on the root |
| `mocode_tui.widgets.markdown` | `BlockRule` / `InlineRule` / `RenderContext`, `BLOCK_RULES` / `INLINE_RULES`, `default_block_rules`, `default_inline_rules`, every built-in rule class |
| `mocode_tui.widgets.syntax` | `Highlighter`, `RegexHighlighter`, `default_highlighter`, `highlight` |

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
field > `DEFAULT_THEME`. All of them import straight from `mocode_tui`.

### widgets — the generic library

| Component | Sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. Hoverable + clickable over its rows: an inline action segment (`Segment(..., action=...)`) answers `hover_at` and lands in `chosen` on a click — the plain rows carry no payloads, and a subclass can render its own. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, gap=1, divider_max_width=80)` | Rule-registry engine: headings, fenced code (syntax-highlighted), lists, quotes, GFM tables, thematic breaks, inline code/bold/strike/italic/links; every prefix renders. A `[label](url)` is a clickable span and an **OSC 8 link** (the terminal's own cmd+click works); a click lands the url in `chosen`, the pointer's span takes the hover band. Extend it with your own `BlockRule` / `InlineRule`. |
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, prompt_style=None, cursor_style=None, focused=True, theme=None, keymap=None)` | Single-line cursor-editable field; keys enter `handle(event)` and route through its keymap — the driver feeds keys, the field reads none. `.text` and `.cursor -> (row, col)` read the buffer; `click(row, col)` places the caret at that rendered cell. An empty focused field shows its placeholder dim, with no cursor cell (the block appears with the first typed character). A multi-line `Paste` is folded into the single line — every newline run becomes one space, so a paste never adds a row (an explicit `insert("\n")` still does). |
| `Editor` | `Editor(*, text="", placeholder="", style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `.text` and `.cursor -> (row, col)` read the buffer; `click(row, col)` places the caret (the `max_rows` window's first rendered row is restored first); `handle(event)` answers `True` when it consumed the event (a multi-line `Paste` keeps its newlines verbatim); `enter` is the host's submit gesture (`DEFAULT_EDITOR_KEYMAP` binds it to `newline`). The placeholder rule matches `Input`'s. |
| `Select` | `Select(options, *, title="", max_rows=8, wrap=True, marker="→", focused=True, label_style=None, selected_style=None, description_style=None, title_style=None, theme=None)` | The menu: vertical `Option(label, value, description)` rows, the cursor row led by `marker` in the theme's `accent`, every description in one aligned column (measured over the whole list). `move(delta)` wraps the ends (`wrap=False` clamps) and clears a pending pick, `activate()` takes the cursor's option into `chosen` (read once by the host), `max_rows` windows the rows with an `(i/n)` counter while it scrolls, `click(row, col)` (the column is ignored — a row owns the width) / `selected` / `index` complete the controller surface; `focused=False` renders the cursor row in `selected_style.merge(theme.dim)`. |
| `Confirm` | `Confirm(message, *, danger=False, theme=None)` | Yes/No `Select`; `danger` styles the message in `ERROR`. `move(delta)` / `click(row, col)` / `focused` as its `Select`; `activate()` lands `Option("Yes", True)` / `Option("No", False)` in `chosen`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, selected_style=None, aligns=None, focused=True, theme=None)` | Full box-frame grid; `str` or `(str, Style)` cells; natural widths, proportional shrink + ellipsis, never stretched. An optional row cursor: `index` (`None` by default, clamped on assignment) / `selected`; the cursor row bands every data cell in `selected_style` (the theme's `selection`), `move(delta)` clamps at the ends, `click(row, col)` maps a rendered row onto a data row (the column is ignored), `activate()` lands the row's index in `chosen`; `focused=False` dims the band. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│", focused=True, theme=None)` | One row of tab labels; `select(index)` selects (clamped), `move(delta)` steps, `click(row, col)` resolves the cell against the strip's own render, `active` reads; `focused=False` dims the active label. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, focused=True, theme=None)` + `TreeNode(label, children=(), *, expanded=False)` | Indented tree; `move(delta)` / `click(row, col)` steer (the column is ignored), `activate()` expands/collapses in place (`False` on a leaf), `selected` reads; `focused=False` dims the cursor row. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)` | Determinate bar: filled / shaded runs. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, wrap=True, label_style=None, selected_style=None, description_style=None, theme=None)` | The filter layer of the menu family: a `Select` subclass whose rows are the matches of `set_query(text)` (prefix matches first, then substrings; an empty query matches all), with the same window, counter, description column, wrapping cursor and `activate()`/`chosen`. The engine `Palette` is built on. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None, theme=None, max_width=None)` | Full-width rule; `label` embeds `── label ───`; `label` / `label_style` / `max_width` are mutable attributes. |
| `Notice` | `Notice(text, *, level="info", theme=None)` | One message row; `warn`/`error` prepend a styled label. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None, theme=None)` | A child inside a single-line box; titled top border when it fits. |
| `Row` / `Column` | `Row(children, *, widths=None, gap=1)` / `Column(children, *, gap=0)` | Layout containers: side-by-side (fixed/flex widths) / stacked with gap rows. |
| `Spacer` / `Padding` | `Spacer(rows=1)` / `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)` | Blank rows / a child inset, optionally filled into a solid band. |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-column row: left text at column 0, right text ending one column short of the width, a computed gutter between (at least one column wide). `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place; an over-wide row keeps the left part and ellipsizes the right tail. |
| `Palette` | `Palette(commands, *, theme=None, max_rows=8)` | The self-contained command palette: its own query `Input` row over an `Autocomplete` filtered by that row's text. `open()` resets the query and the list; `handle(event) -> bool` consumes up/down/enter/escape (enter lands the highlighted command's `value` in `.chosen`, read once by the host) and routes everything else through the query row; zero rows while closed. |

### widgets — the action primitives

| Component | Sketch | Capabilities |
|---|---|---|
| `Button` | `Button(label, *, style=None, hover_style=None, focus_style=None, theme=None, focused=False)` | One clickable row, `" label "` in the theme's `accent`; `hover` / `focused` merge the theme's `hover` / `cursor` bands on top. `click(row, col)` and `activate()` are the same landing — `True` in `chosen`, read once by the host and reset. Carries the tooltip's `hint` (default `""` = none). |
| `Checkbox` | `Checkbox(label, *, checked=False, theme=None, focused=False)` | One toggling row, `[x] label` / `[ ] label`; `click` / `activate` flip `checked` and mirror the new value into `chosen`. The hover/focus bands match `Button`'s. Carries the tooltip's `hint`. |
| `Link` | `Link(text, *, style=None, hover_style=None, theme=None)` | One clickable row in the theme's `link` band, deliberately mouse-only (not `Activable`); a click lands `True` in `chosen`. Carries the tooltip's `hint`. |

## Styling: Theme

`Style` is frozen and hashable (`fg`/`bg` accept named-16, `#rrggbb` or
`(r, g, b)` truecolor); `Theme` is the frozen dataclass that carries every
semantic default. Build a variant with `dataclasses.replace` and hand it to
the components you construct — nothing global is mutated:

```python
from dataclasses import replace

from mocode_tui import ACCENT, DEFAULT_THEME, Markdown, StatusLine, Style, Text

theme = replace(DEFAULT_THEME, accent=Style(fg="#ff8800"), heading=Style(fg="#ff8800"))
Text("hello", theme=theme)            # theme field wins over DEFAULT_THEME
Markdown("# H", theme=theme).render(80)
StatusLine(left=("ready",), theme=theme)  # the two-column row follows the theme
Text("still the default", style=ACCENT)  # an explicit style always wins
```

| Theme field | Default | Used for |
|---|---|---|
| `dim` `muted` `accent` `success` `error` `warning` `border` `code` `cursor` `selection` | the matching `mocode_tui.core.style` constant | the shared semantic styles |
| `heading` `link` `inline_code` `list_marker` | the matching `mocode_tui.core.style` constant (`#e3b341` gold, `#58a6ff` underlined, `#f778ba` pink, `#bc8cff` purple) | the Markdown heading ladder, link labels, inline `` `code` ``, list markers |
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
from mocode_tui import DEFAULT_INPUT_KEYMAP, Input

field = Input(keymap={**DEFAULT_INPUT_KEYMAP, "c-j": "clear"})
del field.keymap["up"]   # unbound: the host sees the event again
```

`DEFAULT_INPUT_KEYMAP` binds arrows/home/end/backspace/delete/`c-a`/`c-e`/
`c-u` (and up/down for wrapped rows) but leaves `enter` unbound — the return
key is the host's submit gesture. `DEFAULT_EDITOR_KEYMAP` adds `enter` as
`newline`, and `EDITOR_SUBMIT_KEYMAP` (the editor table minus `enter`, `c-j`
as `newline`) is what an editor whose host owns the submit gesture resolves.
All three tables live together in `keys/keymap.py` with the derivation chain
visible, and each is re-exported from `mocode_tui.keys`. A component consumes
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

from mocode_tui import EDITOR_SUBMIT_KEYMAP, Editor, Key, StatusLine, Text, TUI
from mocode_tui.core import Document, Viewport


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
both stay public at `mocode_tui.core` — the root's curated face is listed in
[What lives where](#what-lives-where).)

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
`uv run python examples/demo.py < /dev/null` visits every page, dumps the
final screen as plain text and exits 0 — the piped dump is the whole
assertion, and `--pages` dumps the pages one by one. The no-color path is a
run of its own: `NO_COLOR=1 uv run python examples/demo.py --pages` exits 0
too (`HeadlessScreen` pins its `color_mode` to `"truecolor"`, so a test's
bytes never depend on the machine, and the probe is what a live
`TerminalScreen` reads).

**Record a session, run it as a regression.** `RecordingKeys` wraps any key
source and appends every event it serves to a JSONL file — one line per
event, `{"ms": 125, "event": {"kind": "key", "name": "c-f", "char": ""}}` —
and `ReplayKeys` serves that file back as a source, waiting the recorded
milliseconds between events scaled by `speed`:

```python
from mocode_tui.keys import RawTerminalKeys, RecordingKeys, ReplayKeys

# 1. record a real session: wrap the live source before the driver sees it
source = RawTerminalKeys(hover=True)          # the live terminal
source.start()
asyncio.run(TUI(keys=RecordingKeys(source, "session.jsonl")).run(host_loop))
source.close()                                # the file is the session, verbatim

# 2. the recording is JSONL you can read, diff and review -- the model's own
#    fields, one event per line ("kind" is key | paste | mouse; a mouse
#    report's own class rides as "report"), an EOF stopping the file
#    {"ms": 0, "event": {"kind": "key", "name": "/", "char": "/"}}

# 3. replay it anywhere -- a pytest, CI, a bug report -- with no terminal,
#    and no wait: speed=0 hands the events out back to back (the lib
#    never sleeps)
tui = TUI(screen=HeadlessScreen(100, 30), keys=ReplayKeys("session.jsonl", speed=0))
```

A malformed line raises `ValueError` naming its line number, so a
hand-edited recording fails where it broke.

**Golden frames.** Every gallery page is also pinned byte for byte:
`tests/golden/pages/<page>.txt` holds one `--pages` dump per page, and
`uv run python tools/golden.py --check` — the same assertion as
`tests/test_golden_frames.py` — diffs them by name. `--update` re-records
the whole set, for a wave that *means* to change what a user sees.

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — the four layers and the focus tier, the 0-based coordinate charter, screen model, viewport, painter, driver, keys, keymaps, highlighting, the selection rationale (D1–D8) and mode table, the pointer tier and the hover rationale (1002 vs 1003, the wire's button-free motion), the non-TTY contract, and the frame model (the three space claims, the compositor, budget negotiation, focus and wheel routing, the pinned footer band, and the un-split).
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the `render(width)` protocol, the component catalogue, the Theme fields, the frame tier (`Pane` / `split` / `close` / `Scrollbar` / `Toasts`) with the dispatch-order contract, the `SelectionGesture` state machine and selection cookbook, the focus tier (`FocusRing`'s routing table and click policy), the footer-band recipe for assembling an app, the "build your own" walkthroughs (a custom 2-column chrome rail; a custom overlay; a clickable-through container), a custom `Markdown` rule walkthrough on `RenderContext`, and a custom-component walkthrough.

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
