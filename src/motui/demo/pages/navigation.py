"""The navigation page: ``Tabs`` and ``Tree`` -- strips, rows, a cursor.

Two ways to walk a structure: a one-row tab strip whose labels are cells, and
an indented tree whose rows fold.  Both are ring targets -- ``tab`` cycles
between them, the arrows drive the one holding the focus and ``enter`` runs
its activation verb (a tab selects, a tree node folds) -- and both implement
``hover_at``, so the pointer marks the label or the row under it without
touching the cursor.  A tree node that folds carries no pick: ``activate``
is the whole report there, and nothing turns it into a ``chosen``.

The wave's own exhibit is ``Tree.filter``: the shell's ``c-t`` cycles the
canned queries of :data:`~motui.demo.session.TREE_FILTERS` against the tree --
each press prunes to the labels holding the query (the ancestors of a hit
are kept and their chains draw open) and the next clears it -- and the
page's echo line names the query the host reported.  The key is the
*host's*: it is handled by the session, because the shell routes no
printable to a widget, so a typed query would need an ``Input`` row wired
the same way.  ``Tree.jump(char)`` -- the printable type-ahead over the
visible rows -- is the widget's contract and the same door: the API line
names it; the key is the host's to route.  The ``\u2191\u2193``/``enter`` ring
still works while a filter is up, over the pruned rows.
"""

from __future__ import annotations

from motui import FocusRing, Tabs, Text, Tree
from motui.widgets import TreeNode

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """The strip, the tree, the filter echo, and what each does under the focus."""
    theme = gallery.theme
    tabs = Tabs(["overview", "content", "data", "action"], active=1, theme=theme)
    tree = Tree(
        [TreeNode("motui", [
            TreeNode("kernel", [TreeNode("lines"), TreeNode("painter"), TreeNode("frame")],
                     expanded=True),
            TreeNode("widgets", [TreeNode("choice"), TreeNode("tree"), TreeNode("layout")]),
            TreeNode("app", [TreeNode("session"), TreeNode("chrome")]),
        ], expanded=True)],
        theme=theme,
    )
    # The filter's read-out: a placeholder until the host reports a query,
    # so the line is on screen before the first c-t (the data page's rule).
    echo = Text("filter: --", style=theme.dim)

    def note(text: str) -> None:
        """One report was handed in: keep it on the page's echo line.

        The host reports ``filter: '<query>'`` for its own ``c-t`` gesture
        (and would report a widget pick the same way), so the echo line
        names the filter the tree is showing -- or ``filter: cleared``.
        """
        echo.text = text

    return PageBody([
        *header("navigation",
                "Tabs and Tree -- a strip of labels and an indented list, both steered by "
                "one ring.", theme),
        try_line("click any tab in the strip, or any row in the tree; tab moves the focus on "
                 "-- the widget left behind dims its cursor; enter folds a node, and c-t "
                 "cycles the tree's filter", theme),
        section("Tabs -- click a label; the cursor follows the focus", theme),
        tabs,
        api_note("Tabs.click(row, col) / Tabs.move(delta) -- the strip resolves the cell itself", theme),
        Text("when the focus moves on, the active label keeps its hue and loses weight: an "
             "unfocused strip renders selection merged with theme.dim. The label under the "
             "pointer takes the hover band instead.",
             style=theme.dim),
        section("Tree -- \u2191\u2193 walk the visible rows, enter or a click folds; c-t filters", theme),
        tree,
        api_note("Tree.filter(query) -- a case-insensitive substring prune that keeps every "
                 "hit's ancestors open; Tree.jump(char) is the printable type-ahead", theme),
        echo,
        api_note("Tree.activate() -- a fold has no pick; Tree.hover_at(row, col) marks the row", theme),
    ], focus=FocusRing([tabs, tree]), hint="tabs, tree, c-t filters", note=note)
