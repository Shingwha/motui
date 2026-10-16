"""The data page: ``Table`` and ``Slider`` -- a cursor, a pick, and a value.

The table keeps its row cursor and the page's ring holds two targets:
``tab`` steps from the table onto the slider -- ``\u2191\u2193`` move the
table's cursor, ``\u2190\u2192`` step the slider's value, and ``enter``
activates the focused one.  A table activation lands the row's index in
``chosen``; a slider activation lands its value.  The host reads the pick
once and this page echoes it.  ``col`` is ignored by ``Table.click`` --
every column of a data row belongs to that row -- so a click anywhere on a
row moves the cursor there; a click on the slider's track lands its value
on the nearest grid point.  Hover is the pointer's weaker highlight: the
row -- or the slider's own single row -- under the pointer marks itself
without moving anything.
"""

from __future__ import annotations

from mocode_tui import ACCENT, FocusRing, SUCCESS, Slider, Table, Text, WARNING

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """The table, the slider, the readout, and the pick echo."""
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
    slider = Slider(4, minimum=0, maximum=10, theme=theme)
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """One activation was reported: echo the value the host read.

        Two widgets land picks here -- the table's row index and the
        slider's value -- and the host reports ``chosen: <value>`` for
        either; the echo keeps the value half verbatim, so the line never
        guesses which widget produced it.
        """
        echo.text = f"last pick: {text.removeprefix('chosen: ')}"

    return PageBody([
        *header("data",
                "Table -- a grid that shrinks to fit and never stretches, with a cursor "
                "you can steer.", theme),
        try_line("click any table row to move the cursor there; \u2191\u2193 move; enter "
                 "takes the row -- then tab onto the slider and step it with \u2190\u2192",
                 theme),
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
        section("Slider -- a stepped value; \u2190\u2192 step it, a cell of the track sets it", theme),
        slider,
        api_note("Slider(value, minimum=0, maximum=10, step=1) -- activate confirms it into chosen",
                 theme),
    ], focus=FocusRing([table, slider]), hint="table, slider", note=note)
