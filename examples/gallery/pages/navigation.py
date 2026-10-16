"""The navigation page: ``Tabs`` and ``Tree`` -- strips, rows, a cursor.

Two ways to walk a structure: a one-row tab strip whose labels are cells, and
an indented tree whose rows fold.  Both are ring targets -- ``tab`` cycles
between them, the arrows drive the one holding the focus and ``enter`` runs
its activation verb (a tab selects, a tree node folds) -- and both implement
``hover_at``, so the pointer marks the label or the row under it without
touching the cursor.  A tree node that folds carries no pick: ``activate``
is the whole report there, and nothing turns it into a ``chosen``.
"""

from __future__ import annotations

from mocode_tui import FocusRing, Tabs, Text, Tree, TreeNode

from ..page import PageBody, api_note, header, section, try_line


def page(gallery) -> PageBody:
    """The strip, the tree, and what each does under the focus."""
    theme = gallery.theme
    tabs = Tabs(["overview", "content", "data", "action"], active=1, theme=theme)
    tree = Tree(
        [TreeNode("mocode_tui", [
            TreeNode("core", [TreeNode("lines"), TreeNode("painter"), TreeNode("frame")],
                     expanded=True),
            TreeNode("widgets", [TreeNode("choice"), TreeNode("tree"), TreeNode("layout")]),
            TreeNode("app", [TreeNode("session"), TreeNode("chrome")]),
        ], expanded=True)],
        theme=theme,
    )

    return PageBody([
        *header("navigation",
                "Tabs and Tree -- a strip of labels and an indented list, both steered by "
                "one ring.", theme),
        try_line("click any tab in the strip, or any row in the tree; tab moves the focus on "
                 "-- the widget left behind dims its cursor; enter folds a node", theme),
        section("Tabs -- click a label; the cursor follows the focus", theme),
        tabs,
        api_note("Tabs.click(row, col) / Tabs.move(delta) -- the strip resolves the cell itself", theme),
        Text("when the focus moves on, the active label keeps its hue and loses weight: an "
             "unfocused strip renders selection merged with theme.dim. The label under the "
             "pointer takes the hover band instead.",
             style=theme.dim),
        section("Tree -- \u2191\u2193 walk the visible rows, enter or a click folds", theme),
        tree,
        api_note("Tree.activate() -- a fold has no pick; Tree.hover_at(row, col) marks the row", theme),
    ], focus=FocusRing([tabs, tree]), hint="tabs, tree")
