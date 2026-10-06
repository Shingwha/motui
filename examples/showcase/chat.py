"""The chat page: the coding-agent layer's components, plus a live turn.

Message, ToolBlock, EditBlock and a standalone StatusLine, all canned -- and
the same page is where a typed question lands: the session switches here and
streams one of the reply documents in :mod:`showcase.content`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import DIM, EditBlock, Message, StatusLine, Text, ToolBlock

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["page"]


def page(session: Showcase) -> PageBody:
    """The chat-layer samples, plus the note about the live turn."""
    theme = session.theme
    status = StatusLine(theme=theme)
    status.left = ("mocode_tui \u00b7 a local session",)
    status.right = ("no network",)
    return PageBody([
        *header("the chat layer",
                "Message, ToolBlock, EditBlock and StatusLine -- and a live turn: "
                "type anything in the composer and press enter.", theme),
        try_line("type a sentence in the composer below and press enter: this page answers "
                 "with a streamed reply", theme),
        section("Message -- the three roles", theme),
        Message("user", "What does each role look like?", theme=theme),
        Message("thinking", "Considering the shape of the answer\u2026", theme=theme),
        Message("assistant", "A plain assistant turn: one role band, wrapped to the pane.", theme=theme),
        api_note("Message(role, text) -- role picks the band: user / thinking / assistant", theme),
        section("ToolBlock -- a tool call, with its own band", theme),
        ToolBlock("$ echo hello", ["hello from a tool call"], tone="tool", footer="Took 0.1s",
                  theme=theme),
        api_note("ToolBlock(title, lines, tone=..., footer=...)", theme),
        section("EditBlock -- a diff, numbered from one", theme),
        EditBlock(
            "examples/showcase/session.py",
            context=["from mocode_tui import TUI"],
            removed=["footer = Editor()"],
            added=["footer = Composer(tui)"],
            theme=theme,
        ),
        api_note("EditBlock(path, context=[...], removed=[...], added=[...])", theme),
        section("StatusLine -- the footer's own, shown standalone", theme),
        status,
        api_note("StatusLine -- left / right tuples of strings, one row, two-sided", theme),
        Text("Typing here streams a canned Markdown answer -- no model is called. "
             "Every turn is local, and the transcript keeps the turns until you open another page.",
             style=DIM),
    ])
