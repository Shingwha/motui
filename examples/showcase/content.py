"""The showcase's canned copy: the theme variants and the chat page's answers.

Everything here is local and fixed -- no network, no model.  Page copy lives
beside the page that shows it; this module holds what the chat page streams
and the theme variants ``/theme`` cycles.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from mocode_tui import DEFAULT_THEME, Style

#: The composer's empty-state hint (the cursor block appears once you type).
PLACEHOLDER = "type / for the pages -- or ask about this toolkit"

#: Three themes, two built with ``dataclasses.replace`` (nothing global is mutated).
THEMES = (
    ("default", DEFAULT_THEME),
    ("amber", replace(
        DEFAULT_THEME, accent=Style(fg="#e8a020"), heading=Style(fg="#e8a020"),
        selection=Style(bg="#3a2d12"), user_bg=Style(bg="#3a2d12"),
    )),
    ("violet", replace(
        DEFAULT_THEME, accent=Style(fg="#9d7cd8"), heading=Style(fg="#9d7cd8"),
        selection=Style(bg="#2a2140"), user_bg=Style(bg="#2a2140"),
    )),
)

THINKING = "Reading this toolkit top to bottom before answering\u2026"

#: The first answer: the library in one Markdown turn.
REPLY_LONG = """\
# A full-screen toolkit in one process

This screen is a **block document**: every row is a `Block` inside one
addressable `Document`, the visible part is a `Viewport` window, and the
footer is a `Composer` parked in the frame's bottom band.

- `core` -- rows, styles, events, the document, the painter, the frame
- `keys` -- raw bytes to events, and the three keymap tables
- `widgets` -- the component library (`Table`, `Tree`, `Tabs`, ...)
- `chat` -- `Composer`, `Transcript`, `Message`, `ToolBlock`

```python
from mocode_tui import Composer, Key, Message, Transcript, TUI

async def chat(tui: TUI) -> None:
    body = Transcript(tui)          # the scrolling stream
    footer = Composer(tui)          # mounted at construction
    while (key := await tui.read_key()) is not None:
        footer.editor.handle(key)   # editing keys; enter is unbound
        if isinstance(key, Key) and key.name == "enter":
            body.append(Message("user", footer.editor.text))
            footer.editor.clear()

asyncio.run(TUI().run(chat))
```

| layer   | owns                                        |
|:--------|:--------------------------------------------|
| core    | the row primitive, the frame, the selection |
| chat    | the coding-agent pieces                     |

> Everything the showcase "says" is canned -- no model is called, and
> nothing you type leaves this process.
"""

#: Every later answer: the short shape, so no two turns read alike.
REPLY_SHORT = """\
Everything on screen is a `Block` in one `Document`: the pages, the samples,
this reply, and the pinned header -- the footer is a `Composer` in the
frame's bottom band.

Open the page menu with `/` and try `styles`, `features` or `chat`.

> Still local, still canned -- no model involved.
"""

#: The Markdown rendering fixture, one level up beside the entry point.
FIXTURE = Path(__file__).resolve().parent.parent / "Markdown-Rendering-Test.md"
