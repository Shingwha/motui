# mocode-tui

A **layered, full-screen TUI toolkit**. It takes over the terminal on the
alternate screen, renders a document of addressable blocks one diffed row at
a time, owns its own scrollback, and keeps a **pinned footer** (input box,
status bar) that never scrolls away. Four layers compose it:

- **`core`** — the kernel: `Style`/`Theme`, the document model, the render
  core (screen / viewport / painter) and the `TUI` driver.
- **`keys`** — the event model, the byte decoder, the key sources, and the
  keymap tables `Input`/`Editor` consume.
- **`widgets`** — the generic component library (`Text`, `Input`, `Markdown`,
  `Table`, `Tree`, …).
- **`chat`** — the pi-style coding-agent layer (`Composer`, `Transcript`,
  `Message`, `ToolBlock`, …).

Any Python program can build its own components and screens on it; it is not
tied to a host. Runtime dependency: **`wcwidth` only**.

- **alt screen** — standard vim/htop-style full screen; the shell is restored on exit.
- **viewport scrollback** — the whole document stays resident in memory; the screen is a window, `PageUp`/`PageDown` scroll back.
- **mouse** — the wheel scrolls (SGR 1006); button presses decode into `MouseEvent`s and `tui.hit_test(x, y)` resolves one to the block under it — the host dispatches clicks, never the driver.
- **pinned tail** — a scrolling region on top, fixed blocks (input / status) at the bottom.
- **pluggable keyboard** — one decoder feeding scripted or raw terminal sources; editing keys route through configurable keymaps.
- **themeable** — one frozen `Theme` carries every semantic style; `dataclasses.replace` restyles the whole toolkit at once.
- **syntax highlighting** — a zero-dependency `Highlighter` seam, wired into Markdown fences and injectable.
- **testable without a terminal** — `headless_tui` + `snapshot`.

## Quickstart

Fifteen lines to a full-screen app with an input box. Run it on a terminal, or
pipe anything in: the same body replays headless and dumps the final screen as
plain text (a tiny smoke test).

```python
import asyncio
from mocode_tui import Composer, Key, Message, TUI, Transcript

async def chat(tui):
    composer = Composer().attach(tui)   # the pinned footer: rules + editor + status line
    transcript = Transcript(tui)        # the scrolling body
    while True:
        key = await tui.read_key()      # PageUp/PageDown and the wheel already scroll
        if key is None or (isinstance(key, Key) and key.name == "c-c"):
            break
        if isinstance(key, Key) and key.name == "enter":   # the composer leaves enter unbound
            transcript.append(Message("user", composer.editor.value))
            composer.editor.clear()
        composer.editor.handle_key(key)   # every other editing key
    tui.stop()

asyncio.run(TUI().run(chat))
```

`tests/test_readme_examples.py` runs exactly this snippet — and the mocode
integration sample below — headless, so the docs cannot rot.

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
  __init__.py                       # the curated public API: one import line
  app.py  testing.py                # the TUI driver + headless test helpers
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
    markdown.py  table.py  spinner.py  chrome.py
    input.py  editor.py  choice.py  status.py  syntax.py
    autocomplete.py  progress.py  tabs.py  tree.py  layout.py
  chat/                             # the pi-style coding-agent layer
    __init__.py                     # chat facade
    message.py  tools.py            # Message / ToolBlock / EditBlock
    statusline.py  slash.py         # StatusLine / SlashPalette
    composer.py  transcript.py      # the footer + body controllers
```

`from mocode_tui import …` is the one face a host needs. Each layer facade
(`mocode_tui.core`, `mocode_tui.keys`, `mocode_tui.widgets`, `mocode_tui.chat`)
is complete for its own layer, and `tests/test_api_root.py` pins all five
surfaces.

## Components

Every component implements the frozen `render(width) -> list[Line]` protocol
and resolves styles as **explicit `style=` > `theme=` field > `DEFAULT_THEME`**.
All of them import straight from `mocode_tui`.

### widgets — the generic library

| Component | Sketch | Capabilities |
|---|---|---|
| `Text` | `Text(text="", *, style=None)` | Verbatim text, one logical line per `\n`, word-wrapped. Mutable `.text` drives streaming. |
| `Markdown` | `Markdown(text="", *, block_rules=None, inline_rules=None, theme=None, highlighter=None)` | Rule-registry engine: headings, fenced code (syntax-highlighted), lists, quotes, GFM tables, thematic breaks, inline code/bold/italic/links; every prefix renders. |
| `Input` | `Input(*, prompt="❮ ", placeholder="", style=None, …, keymap=None)` | Single-line cursor-editable field; keys route through `handle_key(key, width)` and its keymap — the driver feeds keys, the field reads none. |
| `Editor` | `Editor(*, text="", placeholder="", …, keymap=None, max_rows=None)` | Multi-line buffer with a reverse-video block cursor; `enter` is the host's submit gesture (`DEFAULT_EDITOR_KEYMAP` binds it to `newline`). |
| `Select` | `Select(options, *, title="", …)` | Vertical `Option(label, value, hint)` list; `move(delta)` clamped cursor, `selected` getter. |
| `Confirm` | `Confirm(message, *, danger=False)` | Yes/No `Select`; `danger` styles the message in `ERROR`. |
| `Spinner` | `Spinner(text="", *, frames=None)` | Braille frame cycling; `advance()` steps, `frame` reads. The driver decides when. |
| `Table` | `Table(headers, rows, *, header_style=None, …)` | Full box-frame grid; `str` or `(str, Style)` cells; natural widths, proportional shrink + ellipsis, never stretched. |
| `Tabs` | `Tabs(tabs, *, active=0, …)` | One row of tab labels with the active one emphasized. |
| `Tree` | `Tree(root_nodes, *, indent=2, …)` + `TreeNode(label, children=(), *, expanded=False)` | Indented tree; nodes expand/collapse in place. |
| `ProgressBar` | `ProgressBar(fraction=0.0, *, label="", …)` | Determinate bar: filled / shaded runs. |
| `Autocomplete` | `Autocomplete(*, options=(), max_rows=8, …)` | The filter kernel behind `SlashPalette`: prefix matching with a scrolling window. |
| `StatusBar` | `StatusBar(*, segments=())` + `StatusSegment(text, priority=0)` | Priority-ordered footer cells, dropping the lowest priority first. |
| `Divider` | `Divider(*, char="─", style=None, label="", label_style=None)` | Full-width rule; `label` embeds `── label ───`; both attributes are mutable. |
| `Notice` | `Notice(text, *, level="info")` | One message row; `warn`/`error` prepend a styled label. Truncated, never wrapped. |
| `Panel` | `Panel(child, *, title="", style=None)` | A child inside a single-line box; titled top border when it fits. |
| `Row` / `Column` | `Row(children, *, widths=None, gap=1)` / `Column(children, *, gap=0)` | Layout containers: side-by-side (fixed/flex widths) / stacked with gap rows. |
| `Spacer` / `Padding` | `Spacer(rows=1)` / `Padding(child, *, left=0, right=0, top=0, bottom=0)` | Blank rows / a child inset with themed fill. |

### chat — the pi-style coding-agent pieces

| Component | Sketch | Capabilities |
|---|---|---|
| `Composer` | `Composer(theme=None, *, prompt="", placeholder="…", commands=[])` | The pinned input box as a *controller*: `attach(tui)` pins rules + editor + palette slot + status line; `.editor` / `.palette` / `.statusline` are its pieces; `set_working(on)` drives the spinner label; `anchor_cursor(tui)` pins the IME cursor. |
| `Transcript` | `Transcript(tui, *, theme=None, spacer=True)` | The body message stream: `append(component)`, `stream(role) -> StreamHandle`, `clear()`; the pi rhythm (one blank row between blocks) is built in. |
| `Message` | `Message(role, text="", *, style=None)` | Role-banded chat row: `user` (full-width band with in-band padding rows), `assistant` (plain), `thinking` (dim italic); unknown roles degrade to `assistant`. |
| `ToolBlock` | `ToolBlock(title, body=(), *, tone="tool", footer="")` | Tool-call band: bold title, output rows, italic footer; `tone` picks the band (`tool` deep green / `code` near-black / `plain`). |
| `EditBlock` | `EditBlock(path, context=(), removed=(), added=())` | A diff: accent path, numbered context / `-` / `+` rows, green `(edited)` badge. |
| `StatusLine` | `StatusLine(*, left=(), right=(), theme=None)` | Exactly one dim two-sided row; `left`/`right` are sequences of `str` or `(str, Style)` a host rewrites in place. |
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

Bold is reserved for the `**…**` syntax itself: no default style above is
bold (syntax highlighting's keyword=accent aside) — Markdown signals
structure with color (gold headings, underlined blue links, pink inline
code, purple list markers, italic quotes) instead of weight.

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
`c-j` as `newline`).

## The driver at a glance

```python
tui.add(comp, id="x", pin=None)        # append a block (auto id "b0"…); pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.print("system line")              # muted system block (no raw stdout writes)
tui.invalidate(); tui.paint()         # mark dirty / paint one frame now
tui.every(0.1, fn)                    # periodic callback, returns a cancellable handle
event = await tui.read_key()          # next key; page keys and the wheel scroll and are absorbed
tui.scroll_up(2); tui.scroll_to_bottom()
tui.stop()                            # ask run() to finish
```

`TUI().run(body)` brackets `enter`/`leave`, runs a throttle/repaint pump, and —
on a non-live screen (pipe/file) — stays silent during the run and dumps the
final screen as plain text on exit. `read_key` intercepts the `scroll_keys`
table (`tui.scroll_keys`, rebind or `del` entries to hand an event back) and
returns `None` on a non-live screen even with a source attached. A mouse click
resolves through the driver — the host dispatches:

```python
if isinstance(event, MouseEvent):
    hit = tui.hit_test(event.x, event.y)      # None when no block owns the row
    if hit is not None:
        hit.block.component.click(hit.row)    # e.g. a Select
```

## Integrating with a host (mocode)

The session is two controllers plus your own model loop. The essence:

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
[`specs/2026-10-05-markdown-polish/ref/after-pi-demo.txt`](specs/2026-10-05-markdown-polish/ref/after-pi-demo.txt).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — the four layers, screen model, viewport, painter, driver, keys, keymaps, highlighting, the non-TTY contract.
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the `render(width)` protocol, the component catalogue, the Theme fields, and a custom-component walkthrough.

Not on purpose (see `docs/DESIGN.md`): document-size caps / history trimming
(the document stays resident in full), runtime color negotiation (the palette
is 24-bit truecolor; a VT probe only gates streams that cannot render escapes
at all), mouse drag and scrollbar dragging (presses decode and `hit_test`
resolves them; releases, motion and the horizontal wheel stay dropped, and SGR
1002 motion tracking is never enabled), math rendering in Markdown (the rule
registries are the documented extension point), and any sleep in the library
or its tests.
