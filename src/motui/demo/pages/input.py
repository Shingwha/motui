"""The input page: ``Input``, ``Editor`` and ``Autocomplete`` -- placement, not typing.

A click inside an ``Editor`` docks the block cursor on the cell the hit
test resolved, because a field is written into rather than activated.  The
demo keeps no text input of its own: the only typing happens in the two
query rows the shell owns (``c-f``'s search and the chrome page's palette)."""

from __future__ import annotations

from motui import Editor, FocusRing, Input, Option, Text
from motui.widgets import Autocomplete

from ..page import PageBody, api_note, header, section, try_line


def page(session) -> PageBody:
    """The two fields in their states, and the narrowed menu."""
    theme = session.theme
    hint_only = Input(placeholder="an empty Input: the hint and the cursor block", theme=theme)
    plain = Input(prompt="$ ", theme=theme, focused=False)
    plain.insert("focused=False renders the text plainly, without a cursor")
    editor = Editor(
        text="the Editor\ncarries a block cursor\nand wraps long lines at the pane edge",
        theme=theme,
    )
    windowed = Editor(text="\n".join(f"row {i:02d}" for i in range(1, 13)), max_rows=5, theme=theme)
    filtered = Autocomplete(
        options=[Option("/help", value="/help", description="this command list"),
                 Option("/theme", value="/theme", description="the next theme variant"),
                 Option("/find", value="/find", description="the search row over the page"),
                 Option("/quit", value="/quit", description="leave the demo")],
        theme=theme,
    )
    filtered.set_query("/h")

    return PageBody([
        *header("input",
                "Input, Editor and Autocomplete -- the text fields, and what a click does to "
                "them.", theme),
        try_line("click any cell in the two Editor blocks below: the block cursor lands there; "
                 "hover a field and the whole row takes the hover band", theme),
        section("Input -- an empty focused one, and a plain one", theme),
        hint_only,
        plain,
        section("Editor -- \u2191\u2193 move the block cursor, a click places it", theme),
        editor,
        api_note("TextBuffer.place(row, col) -- a click docks the cursor on the cell it hit", theme),
        section("Editor -- a max_rows window over a twelve-row buffer, click any row", theme),
        windowed,
        section("Autocomplete -- a query narrows the rows; enter takes the match", theme),
        filtered,
        api_note("Autocomplete -- the host sets the query; enter lands the matching row in chosen",
                 theme),
        Text("The only typing in the demo happens in the shell's two query rows -- c-f's "
             "search and the chrome page's palette; a keystroke typed at the shell never "
             "reaches these fields.", style=theme.dim),
    ], focus=FocusRing([editor, windowed, filtered]))
