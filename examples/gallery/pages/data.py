"""The data page: ``Table`` -- shrink-to-fit columns, a cursor, a pick.

The table keeps its row cursor and its one-target ring: ``\u2191\u2193`` move,
``enter`` (or the second click) activates, and ``chosen`` lands the row's
index, which the host reads once and this page echoes.  ``col`` is ignored
by ``Table.click`` -- every column of a data row belongs to that row -- so a
click anywhere on a row moves the cursor there.  Hover is the pointer's
weaker highlight: the row under the pointer marks itself without moving the
cursor.
"""

from __future__ import annotations

from mocode_tui import ACCENT, FocusRing, SUCCESS, Table, Text, WARNING

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """The table, its readout, and the pick echo."""
    theme = gallery.theme
    table = Table(
        ["component", "what it does", "state"],
        [
            ["Text", "verbatim rows, word-wrapped", ("streams", SUCCESS)],
            ["Markdown", "headings, lists, code, tables", ("live", SUCCESS)],
            ["Table", "shrinks to fit, never stretches", ("you are here", ACCENT)],
            ["Divider", "a full-width rule, labelled or not", ("below", WARNING)],
        ],
        aligns=["left", "left", "right"],
        theme=theme,
    )
    table.index = 0  # a visible cursor on arrival: the row the arrows steer from here
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """One activation was reported: keep the row it named on the echo line.

        The host reports ``chosen: <index>``; the table still holds the row
        the activation took (it is the host's own read that resets the
        component's pick), so the echo can name it in words.
        """
        row = table.selected
        index = text.removeprefix("chosen: ")
        echo.text = f"last pick: row {index} -- {row[0]}" if row else f"last pick: {text}"

    return PageBody([
        *header("data",
                "Table -- a grid that shrinks to fit and never stretches, with a cursor "
                "you can steer.", theme),
        try_line("click any table row to move the cursor there; \u2191\u2193 move; enter "
                 "takes the row -- watch the toast and the echo line", theme),
        echo,
        table,
        api_note("Table.index / Table.chosen / Table.activate() -- the host reads the pick once",
                 theme),
        Text("The table measures every column, shrinks the wide ones to the pane and keeps "
             "the first column as the anchor; a cell renders inline markup, so a "
             "(text, style) pair or a Segment lands in the grid unharmed. The row under the "
             "pointer takes the hover mark as you pass over it -- a highlight that moves no "
             "cursor.",
             style=theme.dim),
        section("alignment -- left, left, right", theme),
        Table(
            ["form", "written", "sample"],
            [["named 16-color", '"red" / "bright_blue"', ("named", theme.accent)],
             ["hex truecolor", '"#58a6ff"', ("hex", theme.accent)],
             ["rgb truecolor", "(88, 166, 255)", ("rgb", theme.accent)]],
            theme=theme,
        ),
        api_note("Segment(text, style) in a cell -- the table composes segments, never strings", theme),
    ], focus=FocusRing([table]), hint="table", note=note)
