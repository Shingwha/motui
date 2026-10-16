"""The input page: ``Input`` and ``Editor`` -- placement, not typing.

The landing exhibit for a click's *placement* half: the two ``Editor`` blocks
at the bottom take a click anywhere inside them and dock the block cursor on
the very cell the hit test resolved (``field.click(row, col) ->
TextBuffer.place``), because a field is written into rather than activated.
The pointer's other door shows here too: the whole rendered row of a field
takes the hover band while the pointer is over it, block-level and plain.

The gallery keeps no text input of its own, and this page is where that is
visible: the fields are real and the cursor moves with a click, but the only
place to *type* in the gallery is the ``/`` panel's query row.
"""

from __future__ import annotations

from mocode_tui import Editor, FocusRing, Input, Text

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """The two fields in their states, with the click-to-place story."""
    theme = gallery.theme
    hint_only = Input(placeholder="an empty focused Input: the hint and the cursor block", theme=theme)
    plain = Input(prompt="$ ", theme=theme, focused=False)
    plain.insert("focused=False renders the text plainly, without a cursor")
    editor = Editor(
        text="the Editor\ncarries a block cursor\nand wraps long lines at the pane edge",
        theme=theme,
    )
    windowed = Editor(text="\n".join(f"row {i:02d}" for i in range(1, 13)), max_rows=5, theme=theme)

    return PageBody([
        *header("input",
                "Input and Editor -- the text fields, and what a click does to them.", theme),
        try_line("click any cell in the two Editor blocks below: the block cursor lands there; "
                 "hover a field and the whole row takes the hover band", theme),
        section("Input -- an empty focused one, and a plain one", theme),
        hint_only,
        plain,
        api_note("Input(placeholder=\u2026) / Input(prompt=\u2026, focused=False)", theme),
        section("Editor -- \u2191\u2193 move the block cursor, a click places it", theme),
        editor,
        api_note("TextBuffer.place(row, col) -- a click docks the cursor on the cell it hit", theme),
        section("Editor -- a max_rows window over a twelve-row buffer, click any row", theme),
        windowed,
        api_note("field.click(row, col) / field.hover -- the cell of its own render, window rows included",
                 theme),
        Text("The only typing in the gallery happens in the / panel's query row: these fields "
             "render, wrap, scroll and take a click, and a keystroke outside the palette never "
             "reaches them -- the shell routes print keys nowhere. A multi-line paste is one "
             "event and never submits.",
             style=theme.dim),
    ], focus=FocusRing([editor, windowed]), hint="editor, window")
