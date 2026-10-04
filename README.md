# mocode-tui

A **full-screen block-document TUI toolkit**. It takes over the terminal on the
alternate screen (`\x1b[?1049h` / `\x1b[?1049l`), renders a document of
addressable blocks one diffed row at a time, owns its own scrollback, and keeps
a **pinned footer** (input box, status bar) that never scrolls away. Any Python
program can build its own components and screens on it; it is not tied to a
host. Runtime dependency: **`wcwidth` only**.

- **alt screen** — standard vim/htop-style full screen; the shell is restored on exit.
- **viewport scrollback** — the whole document stays resident in memory; the screen is a window, `PageUp`/`PageDown` scroll back.
- **pinned tail** — a scrolling region on top, fixed blocks (input / status) at the bottom.
- **pluggable keyboard** — one decoder feeding scripted or raw terminal sources.
- **testable without a terminal** — `headless_tui` + `snapshot`.

## Quickstart

```python
import asyncio
from mocode_tui import TUI, Text, Divider, Input, Message, DIM

async def body(tui):
    tui.add(Message("assistant", "hello, full-screen world"))
    tui.add(Divider())
    tui.add(Input(placeholder="type here…  (Ctrl-C to quit)"), id="input", pin="bottom")
    tui.add(Text("19.9k tokens · deepseek/… · medium", style=DIM), id="status", pin="bottom")
    while True:
        event = await tui.read_key()          # PageUp/PageDown already scroll
        if event is None or event.name == "c-c":
            break
    tui.stop()

asyncio.run(TUI().run(body))
```

Run it, or pipe anything in to get the exact same body replayed headless and
dumped as plain text — which makes the piped run a tiny smoke test.

## A pi-style demo

[`examples/pi_demo.py`](examples/pi_demo.py) is a full coding-assistant face:
startup header + `[Skills]` + update notice, a role-banded conversation
(`Message` user / thinking / assistant), a streamed reply, `ToolBlock` and
`Table` and `EditBlock` turns, and a pinned `Input` + status footer. Run it on a
terminal (`uv run python examples/pi_demo.py`), or pipe it:

```sh
python examples/pi_demo.py < /dev/null; echo exit=$?   # exit=0, prints the screen
```

## Components

| Component | Role |
|---|---|
| `Text` | verbatim text block, word-wrapped; mutable `.text` for streaming. |
| `Markdown` | light subset: paragraphs, `#`–`####` headings, fenced code, lists, inline code/bold/italic. |
| `Message` | role-banded chat row: `user` (color band with in-band padding rows), `assistant`, `thinking` (dim italic). |
| `Input` | line editor with a block cursor; up/down follow wrapped rows. |
| `Select` | vertical `Option` list with a moving cursor (menu / picker). |
| `Confirm` | Yes/No `Select` specialization (optional danger styling). |
| `Spinner` | braille frame cycling around a label; `advance()` steps it. |
| `Table` | full box-frame grid (`┌─┬─┐`/`├─┼─┤`/`└─┴─┘`); styled `(text, Style)` cells; proportional shrink + ellipsis. |
| `ToolBlock` | tool-call band (soft truecolor): title (bold), output rows, `tone` deep-green/code/plain, italic footer. |
| `EditBlock` | a diff: path (accent), numbered context/`-`/`+` rows, green `(edited)` badge. |
| `Notice` | one leveled message row (`info`/`warn`/`error`). |
| `Panel` | a child inside a single-line box, optional titled top border. |
| `Divider` | a full-width horizontal rule; `label` embeds `── label ───` (with `label_style`). |
| `StatusBar` | priority-ordered footer cells, dropping the lowest priority first. |
| `Row` / `Column` | layout containers (side-by-side / stacked, with gaps). |

## The driver at a glance

```python
tui.add(comp, id="x", pin=None)        # append a block (auto id "b0"…); invalidates; pin: "top"/"bottom"/None
tui.get("x"); tui.remove("x")         # address by id; invalidate
tui.print("system line")              # muted system block (no raw stdout writes)
tui.invalidate(); tui.flush()         # mark dirty / paint one frame now
tui.every(0.1, fn)                    # periodic callback, returns a cancellable handle
event = await tui.read_key()          # next key; page keys scroll and are absorbed
tui.scroll_up(2); tui.scroll_to_bottom()
tui.stop()                            # ask run() to finish
```

`TUI().run(body)` brackets `enter`/`leave`, runs a throttle/repaint pump, and —
on a non-live screen (pipe/file) — stays silent during the run and dumps the
final screen as plain text on exit.

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — screen model, document/blocks, viewport, painter, driver, keys, non-TTY contract.
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) — the `render(width)` protocol, the capability tables, and a custom-component walkthrough.

## Layout of the toolkit

```
src/mocode_tui/
  style.py  text.py  lines.py  ansi.py  block.py    # primitives  (W1)
  screen.py  viewport.py  painter.py                # render core (W2)
  components/  layout.py                            # component lib (W3 + W5)
  keys.py  app.py  testing.py                       # driver       (W4)
```

Not on purpose (see `docs/DESIGN.md`): mouse-wheel scrolling, document-size
caps / history trimming, and legacy terminal color negotiation (the palette
is 24-bit truecolor with a named-16 subset).
