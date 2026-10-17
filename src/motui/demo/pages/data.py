"""The data page: ``Table``, ``List`` and ``Tree`` -- cursors, picks, a filter.

One ring over the three: ``tab`` walks them, the arrows move the focused
cursor and ``enter`` activates.  The sorter is the ``Table.sort_by``
exhibit and ``c-t`` is the ``Tree.filter`` one (the shell's key hands the
tree the next canned query and the page's echo line names it)."""

from __future__ import annotations

from motui import FocusRing, List, Option, Select, Table, Text, Tree
from motui.kernel import ACCENT, SUCCESS, WARNING
from motui.widgets import TreeNode

from ..page import PageBody, api_note, header, section, try_line

#: The list's items: the library's own components, alphabetically -- long
#: enough for the window and its counter rows to mean something.
COMPONENTS = (
    "Autocomplete", "Button", "Checkbox", "Collapsible", "Column", "Confirm",
    "Diff", "Divider", "Editor", "Input", "Link", "List", "Markdown",
    "Notice", "Option", "Padding", "Palette", "Panel", "ProgressBar", "Radio",
    "Row", "Select", "Slider", "Spinner", "Table", "Tabs", "Text", "Tree",
)

#: The table's columns; the sorter's payloads are indices into this list
#: (``"sort:<i>"``), so a pick is unambiguous however the labels read.
SORT_COLUMNS: tuple[str, ...] = ("component", "what it does", "state")


def page(session) -> PageBody:
    """The table, the list, the sorter, the tree, the echoes."""
    theme = session.theme
    table = Table(
        list(SORT_COLUMNS),
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
    listing = List(COMPONENTS, window=6, theme=theme)
    sorter = Select(
        [Option(name, value=f"sort:{index}") for index, name in enumerate(SORT_COLUMNS)],
        title="sort the table above by",
        theme=theme,
    )
    tree = Tree(
        [TreeNode("motui", [
            TreeNode("kernel", [TreeNode("lines"), TreeNode("painter"), TreeNode("frame")],
                     expanded=True),
            TreeNode("widgets", [TreeNode("choice"), TreeNode("tree"), TreeNode("layout")]),
            TreeNode("app", [TreeNode("session"), TreeNode("chrome")]),
        ], expanded=True)],
        theme=theme,
    )
    pick_echo = Text("last pick: --", style=theme.dim)
    filter_echo = Text("filter: --", style=theme.dim)

    def note(text: str) -> None:
        """One report was handed in: run a sorter pick, and echo it."""
        if text.startswith("filter:"):
            filter_echo.text = text
            return
        pick = text.removeprefix("chosen: ")
        if pick.strip("'").startswith("sort:"):
            table.sort_by(int(pick.strip("'").removeprefix("sort:")))
        pick_echo.text = f"last pick: {pick}"

    return PageBody([
        *header("data",
                "Table, List and Tree -- a grid that shrinks to fit, a windowed list and a "
                "tree, each with a cursor you can steer.", theme),
        try_line("click any table row to move the cursor there; \u2191\u2193 move and enter "
                 "takes the row -- then tab on: the list (\u2191\u2193 walks it), the sorter "
                 "(enter re-orders by that column) and the tree (enter folds; c-t cycles its "
                 "filter)", theme),
        pick_echo,
        table,
        api_note("Table.index / Table.chosen / Table.sort_by(col) -- the host reads the pick "
                 "once and the cursor follows its record", theme),
        section("List -- a windowed cursor over a long sequence", theme),
        listing,
        api_note("List(items, window=6) -- six rows and two counter rows whatever the length; "
                 "a printable jumps to the first item starting with it", theme),
        section("Sorter -- the host calls Table.sort_by on the pick", theme),
        sorter,
        section("Tree -- \u2191\u2193 walk the visible rows, enter folds; c-t filters", theme),
        tree,
        filter_echo,
    ], focus=FocusRing([table, listing, sorter, tree]), note=note)
