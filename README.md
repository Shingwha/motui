# mocode-tui

A **layered, full-screen TUI toolkit**. It takes over the terminal on the
alternate screen, renders a document of addressable blocks one diffed row at
a time, owns its own scrollback, and keeps a **pinned footer** (input box,
status bar) that never scrolls away. Four layers compose it, with the driver
and the headless helpers sitting above the kernel:

- **`core`** — the kernel: `Style`/`Theme`, the `Key`/`Paste`/`MouseEvent`
  event model, the document model, the `Text` component, the measuring
  helpers, and the render core (screen / viewport / painter).
- **`keys`** — the byte decoder, the key sources, and the keymap tables
  `Input`/`Editor` consume.
- **`widgets`** — the generic component library (`Text`, `Input`, `Markdown`,
  `Table`, `Tree`, …), plus the `widgets.markdown` rule registries and the
  `widgets.syntax` highlighting seam.
- **`chat`** — the pi-style coding-agent layer (`Composer`, `Transcript`,
  `Message`, `ToolBlock`, …).
- **`app`** / **`testing`** — the `TUI` driver (the composition root) and
  `headless_tui` / `snapshot`, the one level that may import both `core` and
  `keys`.

Any Python program can build its own components and screens on it; it is not
tied to a host. Runtime dependency: **`wcwidth` only**. The package root
exports a curated **65 names** — one import line for a host — and every
deeper seam stays public at its own module path.

- **alt screen** — standard vim/htop-style full screen; the shell is restored on exit.
- **viewport scrollback** — the whole document stays resident in memory; the screen is a window, `PageUp`/`PageDown` scroll back.
- **mouse** — the wheel scrolls (SGR 1006); presses, releases and motion reports decode into 0-based `MouseEvent`s (each carrying `kind`) and `tui.hit_test(x, y)` resolves one to the block under it — the host dispatches clicks, never the driver.
- **mouse selection & copy** — one `SelectionGesture(tui)` line: drag selects (document-space addresses, so the highlight follows its text through scrolls and the copied range reaches rows scrolled out of view), a hold on the viewport's edge row auto-scrolls across pages, release copies through OSC 52 (best-effort; the `on_end` hook is the real contract). Enabling mouse reporting takes the terminal's native selection away — the same bargain bracketed paste made: the terminal hands over the bytes, the application owns the gesture.
- **pinned tail** — a scrolling region on top, fixed blocks (input / status) at the bottom.
- **pluggable keyboard** — one decoder feeding scripted or raw terminal sources; editing keys route through configurable keymaps and enter `handle_key(event)`.
- **themeable** — one frozen `Theme` carries every semantic style; components resolve it once at construction and `dataclasses.replace` restyles the whole toolkit at once.
- **markdown** — a streaming-safe rule-registry engine in `widgets/markdown`: GFM tables, fenced code, an inline/bold/strike/italic/link registry you extend with your own rules.
- **syntax highlighting** — a zero-dependency `mocode_tui.widgets.syntax.Highlighter` seam, wired into Markdown fences and injectable.
- **testable without a terminal** — `headless_tui` + `snapshot`.

## Quickstart

Nineteen lines to a full-screen app with an input box and mouse selection.
Run it on a terminal, or pipe anything in: the same body replays headless and
dumps the final screen as plain text (a tiny smoke test).

```python
import asyncio
from mocode_tui import Composer, Key, Message, SelectionGesture, TUI, Transcript

async def chat(tui):
    composer = Composer().attach(tui)   # the pinned footer: rules + editor + status line
    transcript = Transcript(tui)        # the scrolling body
    gesture = SelectionGesture(tui)     # mouse selection: copy_on_select is the default on_end
    while True:
        key = await tui.read_key()      # PageUp/PageDown and the wheel already scroll
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break
        if not gesture.handle(key):     # the mouse is the gesture's; everything else is yours
            if isinstance(key, Key) and key.name == "enter":   # the composer leaves enter unbound
                transcript.append(Message("user", composer.editor.value))
                composer.editor.clear()
            composer.editor.handle_key(key)   # every other editing key
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

## The demos

- [`examples/pi_demo.py`](examples/pi_demo.py) — a full coding-assistant face
  on the `chat` layer: banner + update notice, a role-banded transcript, a
  streamed Markdown reply, `ToolBlock` / `Table` / `EditBlock` turns, the slash
  palette, the two-sided status line, and the working spinner. The `/md`
  palette command renders
  [`examples/Markdown-Rendering-Test.md`](examples/Markdown-Rendering-Test.md)
  (the Markdown engine's acceptance fixture) into the transcript as one
  sealed block. Interactive on a terminal
  (`uv run python examples/pi_demo.py`), or piped: a scripted session
  replays headless and prints the final screen.

```sh
python examples/pi_demo.py < /dev/null; echo exit=$?       # exit=0, prints the screen
```

## Package layout

```
src/mocode_tui/
  __init__.py                       # the curated public API: 65 names, one import line
  app.py  selection.py              # the TUI driver + the selection policy tier
  testing.py                        # headless test helpers
  core/                             # the kernel
    __init__.py                     # kernel facade
    style.py  theme.py              # Style + Theme (+ DEFAULT_THEME)
    text.py  lines.py  ansi.py      # measuring + Text, rows, escape bytes
    events.py                       # Key/Paste/MouseEvent + the source protocol
    block.py                        # Component / Block / Document
    screen.py  viewport.py  painter.py   # the render core
  keys/                             # input
    __init__.py                     # keys facade
    decoder.py                      # the Key/Paste/MouseEvent byte decoder
    keymap.py                       # Keymap + the two default tables
    sources.py  console.py          # the raw source, Windows plumbing
  widgets/                          # the generic component library
    __init__.py                     # widgets facade
    markdown/                       # the Markdown rule-registry engine
      inline.py  blocks.py          # the inline rules + the block rules & loop
      nested.py  tables.py          # quote/list rules, the GFM table
      context.py  component.py      # RenderContext + the Markdown component
    table.py  spinner.py  chrome.py  textbuf.py
    input.py  editor.py  choice.py  status.py  syntax.py
    autocomplete.py  progress.py  tabs.py  tree.py  layout.py
  chat/                             # the pi-style coding-agent layer
    __init__.py                     # chat facade
    message.py  tools.py            # Message / ToolBlock / EditBlock
    statusline.py  slash.py         # StatusLine / SlashPalette
    composer.py  transcript.py      # the footer + body controllers
```

`from mocode_tui import …` is the one face a host needs. `app.py` and
`testing.py` sit above the kernel because they compose it with the `keys`
layer; each package facade (`mocode_tui.core`, `.keys`, `.widgets`,
`.chat`, `.app`, `.testing`) is complete for its own layer, and
`tests/test_api_root.py` pins all seven.

## What lives where

The root is curated; everything a host rarely needs stays public at the
module path it lives in.

| Import from | What lives there |
|---|---|
| `mocode_tui` | the curated surface: `TUI`, `Painter`-adjacent driver names, the widgets, the chat layer, `Style`/`Theme`/`DEFAULT_THEME`, the semantic constants (`ACCENT`, `MUTED`, …), `visible_width` / `wrap_text`, `headless_tui` / `snapshot`, `SelectionGesture` / `copy_on_select` |
| `mocode_tui.core` | the kernel facade: `Painter`, `Viewport`, `ScreenLayout`, `Document`, `BlockState`, `MORE_BELOW`, `Text`, `ellipsize_tail`, `wrap_line`, the selection kernel (`Selection`, `highlight`, `extract`), the `core.ansi` escape helpers |
| `mocode_tui.selection` | the selection policy tier: `SelectionGesture` (press/drag/release/edge auto-scroll/double-click) and `copy_on_select`, the shipped `on_end` default |
| `mocode_tui.core.style` | `Style`, the named-16 `FG_CODES`, and the palette constants not on the root (`BORDER`, `CODE`, `CURSOR`, `SELECTION`, `HEADING`, `LINK`, `INLINE_CODE`, `LIST_MARKER`, `NONE`) |
| `mocode_tui.keys` | `KeyDecoder`, `RawTerminalKeys` — the event *model* itself (`Key`, `Paste`, `MouseEvent`, `KeySource`, `ScriptedKeys`) lives in `core.events` and is on the root |
| `mocode_tui.widgets.markdown` | `BlockRule` / `InlineRule` / `RenderContext`, `BLOCK_RULES` / `INLINE_RULES`, `default_block_rules`, every built-in rule class |
| `mocode_tui.widgets.syntax` | `Highlighter`, `RegexHighlighter`, `default_highlighter`, `highlight` |
| `mocode_tui.chat` | `COMPOSER_KEYMAP` and the rest of the chat facade |

## Components

Every component implements the frozen `render(width) -> list[Line]` protocol
and resolves styles **once, at construction**, as explicit `style=` >
`theme=` field > `DEFAULT_THEME`. All of them import straight from
`mocode_tui`.

### widgets — the generic library

| Component | Sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None, theme=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None, gap=1, divider_max_width=80)` | Rule-registry engine: headings, fenced code (syntax-highlighted), lists, quotes, GFM tables, thematic breaks, inline code/bold/strike/italic/links; every prefix renders. Extend it with your own `BlockRule` / `InlineRule`. |
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, prompt_style=None, cursor_style=None, focused=True, theme=None, keymap=None)` | Single-line cursor-editable field; keys enter `handle_key(event)` and route through its keymap — the driver feeds keys, the field reads none. |
| `Editor` | `Editor(*, text="", placeholder="", style=None, cursor_style=None, theme=None, keymap=None, focused=True, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `enter` is the host's submit gesture (`DEFAULT_EDITOR_KEYMAP` binds it to `newline`). |
| `Select` | `Select(options, *, title="", label_style=None, selected_style=None, hint_style=None, title_style=None, theme=None)` | Vertical `Option(label, value, hint)` list; `move(delta)` clamped cursor, `selected` getter, `click(row)` for a mouse hit. |
| `Confirm` | `Confirm(message, *, danger=False, theme=None)` | Yes/No `Select`; `danger` styles the message in `ERROR`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |
| `Table` | `Table(headers, rows, *, header_style=None, first_column_style=None, border_style=None, aligns=None, theme=None)` | Full box-frame grid; `str` or `(str, Style)` cells; natural widths, proportional shrink + ellipsis, never stretched. |
| `Tabs` | `Tabs(tabs, *, active=0, active_style=None, inactive_style=None, divider="│", theme=None)` | One row of tab labels with the active one emphasized. |
| `Tree` | `Tree(root_nodes, *, indent=2, guide_style=None, label_style=None, cursor_style=None, theme=None)` + `TreeNode(label, children=(), *, expanded=False)` | Indented tree; nodes expand/collapse in place. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", width_chars=None, done_style=None, todo_style=None, theme=None)` | Determinate bar: filled / shaded runs. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, label_style=None, hint_style=None, selected_style=None, theme=None)` | The filter kernel behind `SlashPalette`: prefix matching with a scrolling window. |
| `StatusBar` | `StatusBar(*, segments=())` + `StatusSegment(text, priority=0)` | Priority-ordered footer cells, dropping the lowest priority first. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None, theme=None, max_width=None)` | Full-width rule; `label` embeds `── label ───`; all three are mutable. |
| `Notice` | `Notice(text, *, level="info", theme=None)` | One message row; `warn`/`error` prepend a styled label. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None, theme=None)` | A child inside a single-line box; titled top border when it fits. |
| `Row` / `Column` | `Row(children, *, widths=None, gap=1)` / `Column(children, *, gap=0)` | Layout containers: side-by-side (fixed/flex widths) / stacked with gap rows. |
| `Spacer` / `Padding` | `Spacer(rows=1)` / `Padding(child, *, left=0, right=0, top=0, bottom=0, fill_style=None)` | Blank rows / a child inset, optionally filled into a solid band. |

### chat — the pi-style coding-agent pieces

| Component | Sketch | Capabilities |
|---|---|---|
| `Composer` | `Composer(theme=None, *, prompt="", placeholder="", commands=[])` | The pinned input box as a *controller*: `attach(tui)` pins rules + editor + palette slot + status line; `.editor` / `.palette` / `.statusline` are its pieces; `set_working(on)` drives the spinner label; `anchor_cursor(tui)` pins the IME cursor. |
| `Transcript` | `Transcript(tui, *, theme=None, spacer=True)` | The body message stream: `append(component)`, `stream(role) -> StreamHandle`, `clear()`; the pi rhythm (one blank row between blocks) is built in. |
| `Message` | `Message(role, text="", *, style=None, theme=None)` | Role-banded chat row: `user` (full-width band with in-band padding rows), `assistant` (plain), `thinking` (muted italic); unknown roles degrade to `assistant`. |
| `ToolBlock` | `ToolBlock(title, body=(), *, tone="tool", footer="", theme=None)` | Tool-call band: bold title, output rows, italic footer; `tone` picks the band (`tool` deep green / `code` near-black / `plain`). |
| `EditBlock` | `EditBlock(path, context=(), removed=(), added=(), *, theme=None)` | A diff: accent path, numbered context / `-` / `+` rows, green `(edited)` badge. |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None, gap_style=None)` | Exactly one dim two-sided row; `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. |
| `SlashPalette` | `SlashPalette(commands, *, theme=None, max_rows=8)` | The leading-slash command palette: `open()` / `close()` / `set_query(text)`, and `handle_key(key) -> str \| None \| False` (a selection's value / consumed / not the palette's key). |

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
navigation, bracketed paste, SGR mouse). Editing keys route through a
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
`newline`, and `chat.Composer` uses its own `COMPOSER_KEYMAP` (enter out,
`c-j` as `newline`). The wrap geometry `move_up`/`move_down` follow comes
from the component's last render; `handle_key(event)` therefore takes only
the event.

## The driver at a glance

In call order (not a runnable script — every call is on the driver):

```python
tui.add(comp, id="x", pin=None)        # append a block (auto id "b0"…); pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.print("system line")              # muted system block (no raw stdout writes)
tui.invalidate(); tui.paint()         # mark dirty / paint one frame now
tui.rows                              # the current frame: exactly screen.height rows
tui.every(0.1, fn)                    # periodic callback, returns a cancellable handle
event = await tui.read_key()          # next key; page keys and the wheel scroll and are absorbed
tui.scroll_up(2); tui.scroll_to_bottom()
tui.selection; tui.set_selection(sel) # the document-space selection overlay; None clears
tui.stop()                            # ask run() to finish
```

`TUI().run(body)` brackets `enter`/`leave`, runs a throttle/repaint pump, and —
on a non-live screen (pipe/file) — stays silent during the run and dumps the
final screen as plain text on exit. `read_key` intercepts the `scroll_keys`
table (`tui.scroll_keys`, rebind or `del` entries to hand an event back) and
returns `None` on a non-live screen even with a source attached. A mouse click
resolves through the driver — the host dispatches (inside the async body,
where an `await` is legal):

```python
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)      # 0-based coords; None when no block owns the row
    if hit is not None:
        hit.block.component.click(hit.row)    # e.g. a Select
```

## Integrating with a host (mocode)

The session is two controllers plus your own model loop. The essence
(illustrative shape — `tui` and `model` are the host's own):

```python
transcript = Transcript(tui)                              # the message stream
composer = Composer(commands=COMMANDS).attach(tui)        # the pinned footer
handle = transcript.stream("assistant")                   # a streaming message
handle.append(chunk)                                      # one model chunk at a time
handle.seal()                                             # freeze when the turn ends
```

In the key loop, the palette and the editor split the keyboard and `enter`
stays the host's submit gesture (the composer's keymap leaves it unbound):

```python
from mocode_tui import Composer, Key, Message, Transcript

async def chat(tui):
    transcript, composer = Transcript(tui), Composer(commands=COMMANDS).attach(tui)
    while True:
        key = await tui.read_key()                          # page keys / wheel already scroll
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break                                           # EOF / the quit gesture
        if composer.palette.handle_key(key) is not False:
            continue                                        # palette navigation / selection
        composer.editor.handle_key(key)   # editing keys (a Paste inserts)
        composer.palette.set_query(composer.editor.value)
        if isinstance(key, Key) and key.name == "enter":    # the submit gesture
            prompt = composer.editor.value
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
assertions. The demo doubles as a smoke test in piped mode — the pi demo's
piped output is byte-baselined at
[`specs/2026-10-06-frame-chrome/ref/pi-demo-baseline.txt`](specs/2026-10-06-frame-chrome/ref/pi-demo-baseline.txt)
(the pre-frame-chrome dump is archived beside the wave that captured it, as
`pi-demo-baseline-pre-chrome.txt`).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — the four layers, the 0-based coordinate charter, screen model, viewport, painter, driver, keys, keymaps, highlighting, the selection rationale (D1–D8) and mode table, the non-TTY contract.
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the `render(width)` protocol, the component catalogue, the Theme fields, the `SelectionGesture` state machine and selection cookbook, a custom `Markdown` rule walkthrough on `RenderContext`, and a custom-component walkthrough.

Not on purpose (see `docs/DESIGN.md`): document-size caps / history trimming
(the document stays resident in full), runtime color negotiation (the palette
is 24-bit truecolor; a VT probe only gates streams that cannot render escapes
at all), and the horizontal wheel, multi-range selection and scrollbar
dragging (drag selection ships — `SelectionGesture` consumes the press,
motion and release reports mode 1002 delivers — but the decoder still drops
the horizontal wheel and unknown button codes), math rendering in Markdown
(the rule registries are the documented extension point), and any sleep in
the library or its tests.
