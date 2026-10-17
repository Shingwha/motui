"""The views page: ``Table``, ``List`` and ``Tree`` -- cursors, marks, a filter.

One ring over the three: ``tab`` walks them, the arrows move the focused
cursor and ``enter`` activates.  ``space`` marks the focused view's cursor
row -- the marks are the view's own :class:`~motui.kernel.mark.MarkSet` and
the row's leading ``[x]`` is the whole rendering, so the session routes the
key (a view binds no mark key itself).  The sorter's rows carry the
``Table.sort_by`` call as kit ``Action``s -- a pick says what it does, so no
host string-matches ``"sort:<i>"`` any more -- and the shell's generic
``c-t`` hands the tree the next query from this page's own canned cycle:
the queries ride the tree's exhibit slot (``Slot.meta``), the session reads
them off the seat without knowing the page, and the page's one echo line
names the filter and every pick (the retired page kept a second line for
it)."""

from __future__ import annotations

from motui import List, Option, Select, Table, Tree
from motui.kernel import ACCENT, SUCCESS, WARNING
from motui.widgets import TreeNode

from ..kit import Action, Exhibit, Pick
from ..page import PageBody

#: The list's items: the library's own components, alphabetically -- long
#: enough for the window and its counter rows to mean something.
COMPONENTS = (
    "Autocomplete", "Button", "Checkbox", "CheckGroup", "Collapsible", "Column",
    "ComboBox", "Dialog", "Diff", "Divider", "Editor", "Input", "Link", "List",
    "Markdown", "Notice", "Option", "Padding", "Palette", "Panel", "ProgressBar",
    "Radio", "Row", "Select", "Slider", "Spinner", "Table", "Tabs", "Text", "Tree",
)

#: The table's columns; the sorter's rows are :class:`~motui.demo.kit.Action`
#: payloads carrying the column's index (``"sort:<i>"``), so a pick is
#: unambiguous however the labels read.
SORT_COLUMNS: tuple[str, ...] = ("component", "what it does", "state")

#: The canned queries ``c-t`` cycles on this page's tree, in order -- the
#: widget's contract is ``Tree.filter(query)``, and the cycle lives with the
#: page that owns the tree (``None`` clears it).
TREE_FILTERS: tuple[str | None, ...] = ("kernel", "lines", "widget", None)


def page(session) -> PageBody:
    """The table, the list, the sorter, the tree, the marks, the one echo."""
    theme = session.theme
    exhibit = Exhibit(
        session,
        title="views",
        blurb="Table, List and Tree -- a grid that shrinks to fit, a windowed list and a "
              "tree, each with a cursor you can steer and a row you can mark.",
        try_text="click any table row to move the cursor there; \u2191\u2193 move and enter "
                 "takes the row -- then tab on: the list (\u2191\u2193 walks it), the sorter "
                 "(enter re-orders by that column) and the tree (enter folds; c-t cycles its "
                 "filter). press space to mark the focused view's cursor row",
        echo_label="echo",
    )
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
    table.marked.toggle(3)  # and one mark, so the mark column is on the page
    listing = List(COMPONENTS, window=6, theme=theme)
    listing.index = 6
    listing.toggle()  # the cursor row's mark, the column's other exhibit
    sorter = Select(
        [Option(name, value=Action(f"sort:{index}", name,
                                   lambda s, column=index: table.sort_by(column)))
         for index, name in enumerate(SORT_COLUMNS)],
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

    def watch(pick: Pick) -> None:
        """One pick was resolved: a sorter row echoes itself.

        The sorter's actions run (the table re-orders, no toast for that);
        the watch is what still names the row on the page's line, exactly
        the old note's job for a ``sort:<i>`` payload.
        """
        if pick.action is not None:
            exhibit.echo.set(pick.action.id, "last pick")

    exhibit.watch(watch)
    # The page's one echo line: the table pick, the sorter's row and the
    # shell's ``c-t`` filter all land here (empty until one of them does).
    exhibit.show(exhibit.echo)
    exhibit.show(
        table,
        note="last pick",
        api="Table.index / Table.chosen / Table.sort_by(col) -- the host reads the pick "
            "once and the cursor follows its record",
    ).focus()
    exhibit.text("API \u00b7 Table.marked + Table.toggle() -- space marks the cursor row; "
                 "the [x] column rides the first cell")
    exhibit.section("List -- a windowed cursor over a long sequence")
    exhibit.show(
        listing,
        api="List(items, window=6) -- six rows and two counter rows whatever the length; "
            "a printable jumps to the first item starting with it",
    ).focus()
    exhibit.text("API \u00b7 List.marked + List.toggle() -- the mark follows the cursor's "
                 "marker seat")
    exhibit.section("Sorter -- the row's own action calls Table.sort_by")
    exhibit.show(sorter).focus()
    exhibit.section("Tree -- \u2191\u2193 walk the visible rows, enter folds; c-t filters")
    # The page's own ``c-t`` cycle: the queries ride the exhibit slot's
    # ``meta`` (the kit forwards the lookup), so the session's generic arm
    # applies them with no page name on its side.
    tree_slot = exhibit.show(tree).focus()
    tree_slot.meta = TREE_FILTERS
    return exhibit.build()
