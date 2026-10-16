"""The data page: ``Table``, ``Slider`` and ``List`` -- cursors, a pick, a value.

The table keeps its row cursor and the page's ring holds four targets:
``tab`` steps from the table onto the slider, then the list, then the
sorter -- ``\u2191\u2193`` move the focused one's cursor, ``\u2190\u2192`` step the
slider's value, and ``enter`` activates the focused one.  A table
activation lands the row's index in ``chosen``; a slider activation lands
its value; a list activation lands the item under its cursor; the sorter's
activation lands the column it names.  The host reads the pick once and
this page echoes it.  ``col`` is ignored by ``Table.click`` -- every column
of a data row belongs to that row -- so a click anywhere on a row moves the
cursor there; a click on the slider's track lands its value on the nearest
grid point, a click on a list row lands that item (the counter rows carry
none), and a click on a sorter row is the menu's usual first-click-focus,
second-click-activate.  Hover is the pointer's weaker highlight: the row
-- or the slider's own single row -- under the pointer marks itself without
moving anything.

**The sorter is the wave's exhibit: the host's explicit ``sort_by``.**
The table never orders itself (no header click magic), so the page mounts a
one-line menu of the table's columns and its ``note`` runs the pick:
``sort:<col>`` calls :meth:`~mocode_tui.Table.sort_by`, which reorders the
records by the column's rendered text and lets the cursor, a pending
``chosen`` and the pointer's mark follow the *record* into its new position
-- tab back onto the table and the band sits on the same row it did, now
somewhere else -- while every render stays one width.  The sorter is the
ring's **last** target on purpose: the table, the slider and the list are
the wave-7 walk, and appending leaves ``tab`` twice to the list untouched.

The ``List`` is the windowed view: the page gives it the toolkit's own
component names and a window of six rows, so the counter rows
(``\u2191 N more`` / ``\u2193 N more``) and the sliding window are on
display without a screenful of rows.  Its prefix jump -- type ``p`` and the
cursor lands on the first ``P`` item -- is a widget contract the gallery
replay cannot reach (the shell routes no printable to a widget), so the
page demonstrates it only in the ``API`` line.
"""

from __future__ import annotations

from mocode_tui import ACCENT, FocusRing, SUCCESS, List, Option, Select, Slider, Table, Text, WARNING

from ..page import PageBody, api_note, header, section, try_line

#: The list's items: the library's own components, alphabetically -- long
#: enough for the window and the counter rows to mean something.
COMPONENTS = [
    "Autocomplete",
    "Button",
    "Checkbox",
    "Collapsible",
    "Column",
    "Confirm",
    "Diff",
    "Divider",
    "Editor",
    "Input",
    "Link",
    "List",
    "Markdown",
    "Notice",
    "Option",
    "Padding",
    "Palette",
    "Panel",
    "ProgressBar",
    "Radio",
    "Row",
    "Select",
    "Slider",
    "Spinner",
    "Table",
    "Tabs",
    "Text",
    "Tree",
]

#: The table's columns, in header order: the sorter's payloads are indices
#: into this list (``"sort:<i>"``), so a pick is unambiguous however the
#: labels read.
SORT_COLUMNS: tuple[str, ...] = ("component", "what it does", "state")


def page(gallery) -> PageBody:
    """The table, the slider, the list, the sorter, the readout, the echo."""
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
    listing = List(COMPONENTS, window=6, theme=theme)
    sorter = Select(
        [Option(name, value=f"sort:{index}") for index, name in enumerate(SORT_COLUMNS)],
        title="sort the table above by",
        theme=theme,
    )
    echo = Text("last pick: --", style=theme.dim)

    def note(text: str) -> None:
        """One activation was reported: run the pick, and echo it.

        Four widgets land picks here -- the table's row index, the slider's
        value, the list's item and the sorter's column -- and the host
        reports ``chosen: <value>`` for each; the echo keeps the value half
        verbatim, so the line never guesses which widget produced it.  The
        sorter's payload (``sort:<col>``) is the one pick the page *acts*
        on: it calls :meth:`~mocode_tui.Table.sort_by` -- the host's
        explicit call, the widget sorts nothing on its own -- and the next
        frame shows the new order.
        """
        pick = text.removeprefix("chosen: ")
        if pick.strip("'").startswith("sort:"):
            column = int(pick.strip("'").removeprefix("sort:"))
            table.sort_by(column)
        echo.text = f"last pick: {pick}"

    return PageBody([
        *header("data",
                "Table -- a grid that shrinks to fit and never stretches, with a cursor "
                "you can steer.", theme),
        try_line("click any table row to move the cursor there; \u2191\u2193 move; enter "
                 "takes the row -- then tab twice: onto the slider (\u2190\u2192 step it) "
                 "and onto the list (\u2191\u2193 walk it; enter picks), and once more onto "
                 "the sorter (enter re-orders the table by that column)", theme),
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
        section("List -- a windowed cursor over a long sequence", theme),
        listing,
        api_note("List(items, window=6) -- six rows and two counter rows whatever the length; "
                 "a printable jumps to the first item starting with it", theme),
        section("Sorter -- the host calls Table.sort_by on the pick", theme),
        sorter,
        api_note("Table.sort_by(col, reverse=False) -- stable, by the column's rendered text; "
                 "the cursor and a pending chosen follow the record", theme),
    ], focus=FocusRing([table, slider, listing, sorter]), hint="table, slider, list, sort",
       note=note)
