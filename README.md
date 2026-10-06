# mocode-tui

A **layered, full-screen TUI toolkit**. It takes over the terminal on the
alternate screen, renders a document of addressable blocks one diffed row at
a time, owns its own scrollback, and keeps a **pinned footer** (input box,
status bar) that never scrolls away. Four layers compose it, with the driver
and the headless helpers sitting above the kernel:

- **`core`** — the kernel: `Style`/`Theme`, the `Key`/`Paste`/`MouseEvent`
  event model, the document model, the `Text` component, the measuring
  helpers, the render core (screen / viewport / painter), the frame model
  (`Pane`, `Rect`, the split algebra, the compositor), and the selection
  kernel (`Selection`, `highlight`, `extract`).
- **`keys`** — the byte decoder, the key sources, and the three keymap
  tables (`DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP`,
  `COMPOSER_KEYMAP`) `Input`/`Editor`/the composer consume.
- **`widgets`** — the generic component library (`Text`, `Input`, `Markdown`,
  `Table`, `Tree`, …), plus the `widgets.markdown` rule registries and the
  `widgets.syntax` highlighting seam.
- **`chat`** — the coding-agent layer (`Composer`, `Transcript`,
  `Message`, `ToolBlock`, …).
- **`app`** / `gesture` / `focus` / **`chrome`** / **`testing`** — the `TUI`
  driver (the composition root), the mouse-selection policy tier
  (`SelectionGesture`, `copy_on_select`), the focus tier (`FocusRing` — the
  peer of `gesture`: registered targets, the cycle, the routing table and
  the click policy), the frame-chrome and overlay assembly tier (`Scrollbar`,
  `Toasts` — one level above the kernel), and `headless_tui` / `snapshot`.

Any Python program can build its own components and screens on it; it is not
tied to a host. Runtime dependency: **`wcwidth` only**. The package root
exports a curated **65 names** — one import line for a host — and every
deeper seam stays public at its own module path.

- **alt screen** — standard vim/htop-style full screen; the shell is restored on exit.
- **viewport scrollback** — the whole document stays resident in memory; the screen is a window, `PageUp`/`PageDown` scroll back.
- **mouse** — the wheel scrolls (SGR 1006); presses, releases and motion reports decode into 0-based `MouseEvent`s (each carrying `kind`) and `tui.hit_test(x, y)` resolves one to the block under it — the host dispatches clicks, never the driver.
- **mouse selection & copy** — one `SelectionGesture(tui)` line: drag selects (document-space addresses, so the highlight follows its text through scrolls and the copied range reaches rows scrolled out of view), a hold on the viewport's edge row auto-scrolls across pages, release copies through OSC 52 (best-effort; the `on_end` hook is the real contract). Enabling mouse reporting takes the terminal's native selection away — the same bargain bracketed paste made: the terminal hands over the bytes, the application owns the gesture.
- **frame chrome** — one `Scrollbar(tui)` line budgets a column at the pane's edge and maps the scroll onto it (press to page, drag the thumb); the bar is the reference chrome, and a custom rail is one `Chrome` protocol away.
- **split panes** — `tui.split("vertical")` tiles the frame (transcript | preview): the first child keeps the document, a 1-cell tmux-convention divider between them, focus by press or `c-o`, and the wheel routed by pointer position.
- **toasts** — `Toasts(tui)` floats transient bands over the composed frame (a corner stack, TTL-bounded, click-to-dismiss), the reference overlay.
- **pinned tail** — a scrolling region on top, fixed blocks (input / status) at the bottom. The `Composer` footer lives in the frame's bottom **band**: its own viewport, below the pane area, so a split never cuts it in half.
- **pluggable keyboard** — one decoder feeding scripted or raw terminal sources; editing keys route through configurable keymaps and enter `handle(event)`.
- **themeable** — one frozen `Theme` carries every semantic style; components resolve it once at construction and `dataclasses.replace` restyles the whole toolkit at once.
- **markdown** — a streaming-safe rule-registry engine in `widgets/markdown`: GFM tables, fenced code, an inline/bold/strike/italic/link registry you extend with your own rules.
- **syntax highlighting** — a zero-dependency `mocode_tui.widgets.syntax.Highlighter` seam, wired into Markdown fences and injectable.
- **testable without a terminal** — `headless_tui` + `snapshot`.

## Quickstart

Twenty-one lines to a full-screen app with an input box, mouse selection, and
a scrollbar. Run it on a terminal, or pipe anything in: the same body replays
headless and dumps the final screen as plain text (a tiny smoke test).

```python
import asyncio
from mocode_tui import Composer, Key, Message, Scrollbar, SelectionGesture, TUI, Transcript

async def chat(tui):
    composer = Composer(tui)   # the pinned footer: rules + editor + status line
    transcript = Transcript(tui)        # the scrolling body
    scrollbar = Scrollbar(tui)          # chrome: one budgeted column, press/drag/pages it
    gesture = SelectionGesture(tui)     # mouse selection: copy_on_select is the default on_end
    while True:
        key = await tui.read_key()      # PageUp/PageDown and the wheel already scroll
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break
        if not scrollbar.handle(key) and not gesture.handle(key):
            # the mouse is the chrome's, then the gesture's; everything else is yours
            if isinstance(key, Key) and key.name == "enter":   # the composer leaves enter unbound
                transcript.append(Message("user", composer.editor.text))
                composer.editor.clear()
            composer.editor.handle(key)   # every other editing key
    tui.stop()

asyncio.run(TUI().run(chat))
```

`tests/test_readme_examples.py` runs exactly this snippet — and the mocode
integration sample below — headless, so the docs cannot rot.

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

`examples/demo.py` is the library's living front page: a **showcase** — every
component, every style and every feature, one page per category, with the
shell around them built from the same library. It answers **locally** — no
network, no model.

```bash
uv run python examples/demo.py              # a real terminal: the full screen
uv run python examples/demo.py < /dev/null  # piped: replays headless, dumps the final screen
uv run python examples/demo.py --pages      # every page as plain text, no terminal needed
```

A leading `/` opens the page menu — the same `Select` kernel the component
pages show off, so the menu itself is a demo: `↑` at the top wraps to the
bottom, and a menu longer than its `max_rows` window carries an `(i/n)`
counter. Then the pages:

- `/overview` — what this is, and the page list
- `/data` — Text, Markdown, Table, Divider
- `/structure` — Panel, Row/Column, Padding, Tabs, Tree
- `/lists` — Select (20 rows, 6 visible, a counter), Confirm, Autocomplete
- `/fields` — Input and Editor, in their states
- `/feedback` — ProgressBar (one live), Spinner (one live), Notice
- `/styles` — the three themes color by color, style attributes, color forms
- `/features` — panes, scrollback, selection, the three keymaps
- `/markdown` — the rendering fixture, every construct in one page
- `/chat` — Message, ToolBlock, EditBlock, StatusLine
- `/split` — toggle a live second pane; `/theme` cycles the themes; `/fps`
  toggles the frame-rate readout; `/quit` leaves

On a page that can be played with, the page mounts a `FocusRing`: `tab`
cycles the widget focus (`/structure` starts on the tab strip, `tab` moves to
the tree; `/lists` walks the menu, the two confirms and the filter;
`/fields` the editor and its window), `↑↓` drive the focused widget's cursor
and `enter` activates it (the tree folds, a menu takes its pick into
`chosen`), and a **click focuses**: the first click on a ring target focuses
it, the second activates it — every widget that answers `click(row, col)` is
dispatched its cell either way. The pages stay live, so the focus and click
paths are the real component APIs, not screenshots.

Enter sends, c-j breaks a line, a leading `/` opens the menu, tab cycles the
page's focus ring and c-o switches pane focus (after `/split`), drag selects
and release copies through OSC 52, Ctrl-C quits. A multi-line paste is one
event, never a line-by-line submit:
the box fills and only enter sends (an old console or a pipe that cannot
bracket degrades to line-by-line — the reason and the paths are in
`docs/DESIGN.md`). The composer is a real `Editor`: type a question and the
chat page streams a canned Markdown answer. Everything the demo "says" is
canned: the interactive stream paces itself with short sleeps, the headless
replay never sleeps, and the piped run doubles as a smoke test — it visits
every page.

## Chrome, panes, overlays

Everything that draws outside the document flow is exactly one of three
claims on screen space — a **pane** (an exclusive rectangle owning its own
viewport), **chrome** (a budgeted band inside a pane's rectangle, re-wrapping
its content) or an **overlay** (a pure paint over the composed frame) — and
picking which one a feature is *is* the design step. `Scrollbar` is the
reference chrome, `Toasts` the reference overlay, and `tui.split` the pane
tier:

```python
scrollbar = Scrollbar(tui)                  # chrome: budgets a column, maps the scroll
toasts = Toasts(tui)                        # overlay: corner-anchored transient bands
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
  __init__.py                       # the curated public API: 65 names, one import line
  app.py  gesture.py  focus.py      # the TUI driver + the selection and focus policies
  chrome.py                         # the frame-chrome and overlay assembly
  testing.py                        # headless test helpers
  core/                             # the kernel
    __init__.py                     # kernel facade
    frame.py                        # Rect + Split: the split algebra + the compositor
    style.py  theme.py              # Style + Theme (+ DEFAULT_THEME) and the Themed base
    text.py  lines.py  ansi.py      # measuring + Text, rows, escape bytes
    events.py                       # Key/Paste/MouseEvent + the source protocol
    block.py                        # Component / Block / Document (+ Clickable, Activable)
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
    choice.py  syntax.py            # Select/Confirm/Option, the highlighter seam
    autocomplete.py  progress.py  tabs.py  tree.py  layout.py
  chat/                             # the coding-agent layer
    __init__.py                     # chat facade
    message.py  tools.py            # Message / ToolBlock / EditBlock
    statusline.py  slash.py         # StatusLine / SlashPalette
    composer.py  transcript.py      # the footer + body controllers
```

`from mocode_tui import …` is the one face a host needs. `app.py`,
`gesture.py`, `chrome.py` and `testing.py` sit above the kernel because
they compose it with the `keys` layer; each package facade (`mocode_tui.core`,
`.keys`, `.widgets`, `.chat`, `.app`, `.chrome`, `.gesture`, `.testing`) is
complete for its own layer, and `tests/test_api_root.py` pins all nine — the
root and every layer facade.

## What lives where

The root is curated; everything a host rarely needs stays public at the
module path it lives in.

| Import from | What lives there |
|---|---|
| `mocode_tui` | the curated surface: `TUI`, the frame tier (`Pane`, `Scrollbar`, `Toasts`), the widgets, the chat layer, `Style`/`Theme`/`DEFAULT_THEME`, the semantic constants (`ACCENT`, `MUTED`, …), the selection kernel (`Selection`, `highlight`, `extract`), `SelectionGesture` / `copy_on_select`, `visible_width` / `wrap_text`, `headless_tui` / `snapshot` |
| `mocode_tui.core` | the kernel facade: `Painter`, `Viewport`, `ScreenLayout`, `Document`, `BlockState`, the component protocols (`Clickable`, `Activable`, `Focusable`), `MORE_BELOW`, `Text`, `ellipsize_tail`, `wrap_line`, the selection kernel (`Selection`, `highlight`, `extract`), the `core.ansi` escape helpers |
| `mocode_tui.core.frame` | the frame model below the driver's face: `Rect`, `Split`, `Chrome`, `Frame`, `FrameTable`, `Overlay`, `splice_row` |
| `mocode_tui.gesture` | the selection policy tier: `SelectionGesture` (press/drag/release/edge auto-scroll/double-click) and `copy_on_select`, the shipped `on_end` default |
| `mocode_tui.focus` | the focus tier: `FocusRing` (registered targets, `focus`/`focus_next` cycling, the `handle` routing table, the click policy), on the root as `FocusRing` |
| `mocode_tui.chrome` | the frame-chrome assembly tier: `Scrollbar` (chrome + gesture) and `Toasts` (overlay + controller), both root-public |
| `mocode_tui.core.style` | `Style`, the named-16 `FG_CODES`, and the palette constants not on the root (`BORDER`, `CODE`, `CURSOR`, `SELECTION`, `HEADING`, `LINK`, `INLINE_CODE`, `LIST_MARKER`, `NONE`) |
| `mocode_tui.keys` | `KeyDecoder`, `RawTerminalKeys`, `Keymap` and the three default tables (`DEFAULT_INPUT_KEYMAP`, `DEFAULT_EDITOR_KEYMAP`, `COMPOSER_KEYMAP`) — the event *model* itself (`Key`, `Paste`, `MouseEvent`, `KeySource`, `ScriptedKeys`) lives in `core.events` and its value types are on the root |
| `mocode_tui.widgets.markdown` | `BlockRule` / `InlineRule` / `RenderContext`, `BLOCK_RULES` / `INLINE_RULES`, `default_block_rules`, `default_inline_rules`, every built-in rule class |
| `mocode_tui.widgets.syntax` | `Highlighter`, `RegexHighlighter`, `default_highlighter`, `highlight` |
| `mocode_tui.chat` | the chat facade (`Composer`, `Transcript`, the message blocks); `COMPOSER_KEYMAP` re-exports here from `mocode_tui.keys` |

## Components

Every component renders through the frozen `render(width) -> list[Line]`
protocol, and the interactive ones carry controller methods beside it:
`handle(event) -> bool` (`Input` / `Editor` / `SlashPalette`),
`click(row, col) -> bool` (the lists and the tab strip), `move(delta)` /
`activate()` / `select(index)` — the menus wrap their ends, the tab strip
and tree clamp, and a menu's activation lands the picked option in
`chosen`. The focusable ones carry one more flag: `focused: bool` (the
text fields draw their block cursor by it; the lists, the tree and the tab
strip render an unfocused cursor row in their cursor style merged with the
theme's `dim`) — `FocusRing` sets it as the focus moves, and the component
never learns a manager exists.
Styles resolve **once, at construction**, as explicit `style=` > `theme=`
field > `DEFAULT_THEME`. All of them import straight from `mocode_tui`.

### widgets — the generic library

| Component | Sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, gap=1, divider_max_width=80)` | Rule-registry engine: headings, fenced code (syntax-highlighted), lists, quotes, GFM tables, thematic breaks, inline code/bold/strike/italic/links; every prefix renders. Extend it with your own `BlockRule` / `InlineRule`. |
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, prompt_style=None, cursor_style=None, focused=True, theme=None, keymap=None)` | Single-line cursor-editable field; keys enter `handle(event)` and route through its keymap — the driver feeds keys, the field reads none. `.text` and `.cursor -> (row, col)` read the buffer. An empty focused field shows its placeholder dim, with no cursor cell (the block appears with the first typed character). A multi-line `Paste` is folded into the single line — every newline run becomes one space, so a paste never adds a row (an explicit `insert("\n")` still does). |
| `Editor` | `Editor(*, text="", placeholder="", style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `.text` and `.cursor -> (row, col)` read the buffer; `handle(event)` answers `True` when it consumed the event (a multi-line `Paste` keeps its newlines verbatim); `enter` is the host's submit gesture (`DEFAULT_EDITOR_KEYMAP` binds it to `newline`). The placeholder rule matches `Input`'s. |
| `Select` | `Select(options, *, title="", max_rows=8, wrap=True, marker="→", focused=True, label_style=None, selected_style=None, description_style=None, title_style=None, theme=None)` | The menu: vertical `Option(label, value, description)` rows, the cursor row led by `marker` in the theme's `accent`, every description in one aligned column (measured over the whole list). `move(delta)` wraps the ends (`wrap=False` clamps) and clears a pending pick, `activate()` takes the cursor's option into `chosen` (read once by the host), `max_rows` windows the rows with an `(i/n)` counter while it scrolls, `click(row, col)` (the column is ignored — a row owns the width) / `selected` / `index` complete the controller surface; `focused=False` renders the cursor row in `selected_style.merge(theme.dim)`. |
| `Confirm` | `Confirm(message, *, danger=False, theme=None)` | Yes/No `Select`; `danger` styles the message in `ERROR`. `move(delta)` / `click(row, col)` / `focused` as its `Select`; `activate()` lands `Option("Yes", True)` / `Option("No", False)` in `chosen`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, aligns=None, theme=None)` | Full box-frame grid; `str` or `(str, Style)` cells; natural widths, proportional shrink + ellipsis, never stretched. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│", focused=True, theme=None)` | One row of tab labels; `select(index)` selects (clamped), `move(delta)` steps, `click(row, col)` resolves the cell against the strip's own render, `active` reads; `focused=False` dims the active label. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, focused=True, theme=None)` + `TreeNode(label, children=(), *, expanded=False)` | Indented tree; `move(delta)` / `click(row, col)` steer (the column is ignored), `activate()` expands/collapses in place (`False` on a leaf), `selected` reads; `focused=False` dims the cursor row. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)` | Determinate bar: filled / shaded runs. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, wrap=True, label_style=None, selected_style=None, description_style=None, theme=None)` | The filter layer of the menu family: a `Select` subclass whose rows are the matches of `set_query(text)` (prefix matches first, then substrings; an empty query matches all), with the same window, counter, description column, wrapping cursor and `activate()`/`chosen`. The engine `SlashPalette` is built on. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None, theme=None, max_width=None)` | Full-width rule; `label` embeds `── label ───`; `label` / `label_style` / `max_width` are mutable attributes. |
| `Notice` | `Notice(text, *, level="info", theme=None)` | One message row; `warn`/`error` prepend a styled label. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None, theme=None)` | A child inside a single-line box; titled top border when it fits. |
| `Row` / `Column` | `Row(children, *, widths=None, gap=1)` / `Column(children, *, gap=0)` | Layout containers: side-by-side (fixed/flex widths) / stacked with gap rows. |
| `Spacer` / `Padding` | `Spacer(rows=1)` / `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)` | Blank rows / a child inset, optionally filled into a solid band. |

### chat — the coding-agent pieces

| Component | Sketch | Capabilities |
|---|---|---|
| `Composer` | `Composer(tui, *, theme=None, placeholder="", commands=())` | The pinned input box as a *controller*: construction mounts it — the five-piece footer (top rule / editor / bottom rule / palette slot / status line) parked in the frame's bottom band; `.editor` / `.palette` / `.statusline` are its pieces; `set_working(on)` drives the spinner label; `anchor_cursor()` pins the IME cursor; `detach()` unmounts. |
| `Transcript` | `Transcript(tui, *, theme=None, spacer=True)` | The body message stream: `append(component)`, `stream(role) -> StreamHandle`, `clear()`; the one-blank-row rhythm between blocks is built in. |
| `Message` | `Message(role, text="", *, style=None, theme=None)` | Role-banded chat row: `user` (full-width band with in-band padding rows), `assistant` (plain), `thinking` (muted italic); unknown roles degrade to `assistant`. |
| `ToolBlock` | `ToolBlock(title, body=(), *, tone="tool", footer="", theme=None)` | Tool-call band: bold title, output rows, italic footer; `tone` picks the band (`tool` deep green / `code` near-black / `plain`). |
| `EditBlock` | `EditBlock(path, context=(), removed=(), added=(), *, theme=None)` | A diff: accent path, numbered context / `-` / `+` rows, green `(edited)` badge. |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-sided row; `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. |
| `SlashPalette` | `SlashPalette(commands, *, theme=None, max_rows=8)` | The leading-slash command palette: `open()` / `close()` / `set_query(text)`, and `handle(event) -> bool` consuming only up/down/enter/escape. `enter` consumes and lands the highlighted command's `value` in `.chosen` (`None` while nothing is picked); a host reads `chosen` after a consuming `handle` and resets it. |

## Styling: Theme

`Style` is frozen and hashable (`fg`/`bg` accept named-16, `#rrggbb` or
`(r, g, b)` truecolor); `Theme` is the frozen dataclass that carries every
semantic default. Build a variant with `dataclasses.replace` and hand it to
the components you construct — nothing global is mutated:

```python
from dataclasses import replace

from mocode_tui import ACCENT, DEFAULT_THEME, Markdown, Message, Style, Text

theme = replace(DEFAULT_THEME, accent=Style(fg="#ff8800"), heading=Style(fg="#ff8800"))
Text("hello", theme=theme)            # theme field wins over DEFAULT_THEME
Markdown("# H", theme=theme).render(80)
Message("user", "hi", theme=theme)    # the user band follows theme.user_bg
Text("still the default", style=ACCENT)  # an explicit style always wins
```

| Theme field | Default | Used for |
|---|---|---|
| `dim` `muted` `accent` `success` `error` `warning` `border` `code` `cursor` `selection` | the matching `mocode_tui.core.style` constant | the shared semantic styles |
| `heading` `link` `inline_code` `list_marker` | the matching `mocode_tui.core.style` constant (`#e3b341` gold, `#58a6ff` underlined, `#f778ba` pink, `#bc8cff` purple) | the Markdown heading ladder, link labels, inline `` `code` ``, list markers |
| `user_bg` | `#1c2b3a` slate blue | the `user` band |
| `tool_bg` | `#16281c` deep green | the `"tool"` tone band |
| `code_bg` | `#12181f` near-black blue | the `"code"` tone / `EditBlock` band |
| `table_border` | none (uncolored) | `Table` grid lines |
| `first_column` | none (plain) | `Table` first data column |
| `headings` `tones` `title_tones` `notice_levels` | derived from the colors above | read-only structural tables (`Theme()` rebuilds them) |

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
`newline`, and `COMPOSER_KEYMAP` (the editor table minus `enter`, `c-j` as
`newline`) is what the composer's editor resolves. All three tables live
together in `keys/keymap.py` with the derivation chain visible, and each is
re-exported from `mocode_tui.keys` (the composer's also from
`mocode_tui.chat`). A component consumes one event at a time through
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
tui.viewport_rows()                   # the focused pane's window as (first, last), or None
tui.split("vertical", ratios=(2, 1))  # tile the focused pane: first child keeps the document
tui.selection; tui.set_selection(sel) # the document-space selection overlay; None clears
tui.stop()                            # ask run() to finish
```

`TUI().run(body)` brackets `enter`/`leave`, runs a throttle/repaint pump, and —
on a non-live screen (pipe/file) — stays silent during the run and dumps the
final screen as plain text on exit. `TUI(theme=...)` sets the theme the
driver's own chrome reads (the split's separator; widgets take their own
`theme=`). `read_key` intercepts the `scroll_keys`
table (`tui.scroll_keys`, rebind or `del` entries to hand an event back) and
returns `None` on a non-live screen even with a source attached. A mouse click
resolves through the driver — the host dispatches (inside the async body,
where an `await` is legal):

```python
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)             # 0-based coords; None when no block owns the cell
    if hit is not None:
        hit.block.component.click(hit.row, hit.col)  # e.g. a Select: it ignores the column
```

## Integrating with a host (mocode)

The session is two controllers plus your own model loop. The essence
(illustrative shape — `tui` and `model` are the host's own):

```python
transcript = Transcript(tui)                              # the message stream
composer = Composer(tui, commands=COMMANDS)        # the pinned footer
handle = transcript.stream("assistant")                   # a streaming message
handle.append(chunk)                                      # one model chunk at a time
handle.seal()                                             # freeze when the turn ends
```

In the key loop, the palette and the editor split the keyboard and `enter`
stays the host's submit gesture (the composer's keymap leaves it unbound).
A consuming `palette.handle` may have picked a command: the host reads
`palette.chosen` once and dispatches it itself (`None` after navigation or
dismissal, so a stale pick never fires):

```python
from mocode_tui import Composer, Key, Message, Transcript

async def chat(tui):
    transcript, composer = Transcript(tui), Composer(tui, commands=COMMANDS)
    while True:
        key = await tui.read_key()                          # page keys / wheel already scroll
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break                                           # EOF / the quit gesture
        if composer.palette.handle(key):
            chosen = composer.palette.chosen   # enter's pick; None on navigation
            composer.palette.chosen = None     # a host reads it exactly once
            if chosen is not None:             # ... and dispatches it itself
                composer.editor.clear()        # the pick replaces the query
            continue                           # palette navigation / dismissal
        composer.editor.handle(key)   # editing keys (a Paste inserts)
        composer.palette.set_query(composer.editor.text)
        if isinstance(key, Key) and key.name == "enter":    # the submit gesture
            prompt = composer.editor.text
            composer.editor.clear()
            transcript.append(Message("user", prompt))
            handle = transcript.stream("assistant")
            async for chunk in model.stream(prompt):        # your model loop
                handle.append(chunk)
            handle.seal()
```

`COMMANDS` and `model` are the host's own. `tests/test_readme_examples.py` runs
this shape headless against a fake model, so the documented shape cannot rot.

## Testing without a terminal

`headless_tui(...)` builds a driven `TUI` on a `HeadlessScreen` with a
`ScriptedKeys` source; `snapshot(tui)` renders the document to rows for
assertions. The [demo](#the-demo) doubles as a smoke test in piped mode:
`uv run python examples/demo.py < /dev/null` visits every page, dumps the
final screen as plain text and exits 0 — the piped dump is the whole
assertion, and `--pages` dumps the pages one by one.

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — the four layers and the focus tier, the 0-based coordinate charter, screen model, viewport, painter, driver, keys, keymaps, highlighting, the selection rationale (D1–D8) and mode table, the non-TTY contract, and the frame model (the three space claims, the compositor, budget negotiation, focus and wheel routing, the Composer band, and the un-split).
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the `render(width)` protocol, the component catalogue, the Theme fields, the frame tier (`Pane` / `split` / `close` / `Scrollbar` / `Toasts`) with the dispatch-order contract, the `SelectionGesture` state machine and selection cookbook, the focus tier (`FocusRing`'s routing table and click policy), the two "build your own" walkthroughs (a custom 2-column chrome rail; a custom overlay), a custom `Markdown` rule walkthrough on `RenderContext`, and a custom-component walkthrough.

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
