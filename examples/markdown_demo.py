"""Render ``Markdown-Rendering-Test.md`` through the Markdown component.

Interactive:  ``uv run python examples/markdown_demo.py``
Piped (non-TTY): dumps the first screenful as plain text, exit 0.

Scroll: Up/Down, PageUp/PageDn, mouse wheel.  Quit: q, Escape, Ctrl-C.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mocode_tui import (
    ACCENT,
    BORDER,
    Divider,
    HeadlessScreen,
    Markdown,
    MUTED,
    ScriptedKeys,
    TUI,
)

SOURCE = Path(__file__).with_name("Markdown-Rendering-Test.md")


async def view_document(tui: TUI) -> None:
    tui.scroll_keys.update({"up": -1, "down": 1})
    tui.add(Divider(label=f" {SOURCE.name} ", label_style=ACCENT), id="title", pin="top")
    document = tui.add(Markdown(SOURCE.read_text(encoding="utf-8")), id="document")
    document.seal()  # static content: render once per width, then cached
    # A viewer opens at the top; the chat-style default sticks to the bottom.
    tui.scroll_up(10_000)
    tui.add(
        Divider(label=" up/down/page/wheel scroll · q quit ", style=BORDER, label_style=MUTED),
        id="hints",
        pin="bottom",
    )

    while True:
        key = await tui.read_key()
        if key is None or getattr(key, "name", "") in ("q", "escape", "c-c"):
            break


def main() -> None:
    if sys.stdin.isatty() and sys.stdout.isatty():
        asyncio.run(TUI().run(view_document))
        return
    # Non-TTY: render one headless screenful and dump it as plain text.
    tui = TUI(screen=HeadlessScreen(100, 60), keys=ScriptedKeys(()), interactive=False)
    asyncio.run(tui.run(view_document))
    print("\n".join(row.text for row in tui.rows()))


if __name__ == "__main__":
    main()
