"""The interaction exhibit: the focus ring, the click, the pick, the cell.

The interaction model does not get a page *about* itself but the model
itself: one :class:`~mocode_tui.focus.FocusRing` over three widgets -- a
menu, a tree and an editor, each its own block -- so ``tab`` moves the
focus in front of you and the widget left behind dims its cursor row (the
focus tier's visible half), the arrows drive whichever widget holds the
focus, and ``enter`` runs its activation verb: the menu takes the option
under its cursor into ``chosen`` (the host reads it once and reports the
option), while the tree folds the node under its cursor and carries
nothing into ``chosen`` at all.

The click policy is the same three components' other half.  A hit resolves
to one of the three blocks, so the first click on a widget focuses it and
the second activates it -- and a click inside the editor's text docks the
block cursor on the very cell the hit test resolved (``field.click(row,
col)`` -> ``TextBuffer.place``), because a field is written into rather
than activated.

The last-action rows at the bottom are the session's
:attr:`~showcase.session.Showcase.log`: the host's one report outlet writes
the last three reports -- a pick, a fold, a focus move, a page opening --
and this page draws them with the newest in the accent and the older ones
dimmed.  A fold is the interesting one: the tree carries no ``chosen`` at
all, so the host reports the act (``activate \u2192 tree``) rather than a
value, and no activation ever reads as a silence or a bare ``None``.
The rows are fed the same way the page's widgets are driven: the host's
``note`` hook redraws them the moment an activation is reported (the pick
or fold you just caused), and the page's own beat redraws them from the log
a moment later for the reports that are log-only -- a ``tab``'s focus move,
a page opening -- so nothing the ring did goes unrecorded on screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mocode_tui import Editor, FocusRing, Option, Select, Text, Tree, TreeNode

from .page import PageBody, api_note, header, section, try_line

if TYPE_CHECKING:
    from .session import Showcase

__all__ = ["page"]

#: The editor's three lines before anyone plays with it: the field's half of
#: the story -- the cursor, the arrows, and the enter it keeps for itself.
EDITOR_TEXT = (
    "a click anywhere in this text docks the block cursor\n"
    "the caret is the cursor: this widget owns the arrows\n"
    "this field consumes enter -- a line break, not an activation"
)

#: The rows the last-action panel draws.  The session's log keeps this many
#: reports (``session.LOG_ROWS``) and the panel always draws that many rows
#: -- an empty slot stays blank -- so the page below the panel never jumps.
TAIL_ROWS = 3

#: What the panel shows before the first report of the session arrives.
TAIL_EMPTY = "--"

#: The menu's five rows as ``(label, description)``.  The label is also the
#: option's payload -- ``Option(label, value=label, ...)``, the same shape the
#: lists exhibit uses -- so the host's report reads ``chosen: 'row 03'`` and
#: the toast stays one line, while the description keeps the teaching text in
#: the column beside the rows.
MENU_ROWS = (
    ("row 01", "the cursor row: bright while the menu is focused"),
    ("row 02", "\u2191\u2193 move the cursor over the rows"),
    ("row 03", "enter activates the option under the cursor"),
    ("row 04", "the pick lands in chosen -- read exactly once"),
    ("row 05", "a click on a row moves the cursor there"),
)


def page(session: Showcase) -> PageBody:
    """The three ring targets, their notes, and the session's log tail.

    The exhibits mount in the ring's own order -- menu, tree, editor -- and
    the one ring is what makes them play together: ``tab`` steps the focus
    through all three, and each widget's dim caption says what it is while
    its ``API`` note says which line of the library it runs on.  The tail
    panel is fed from ``session.log`` through both page hooks: ``note`` --
    the host hands over one activation's outcome -- redraws it at once, and
    ``tick``, the page's beat, catches the log-only reports up.
    """
    theme = session.theme
    menu = Select(
        [Option(label, value=label, description=text) for label, text in MENU_ROWS],
        theme=theme,
    )
    tree = Tree(
        [TreeNode("the interaction model", [
            TreeNode("focus: the ring owns who is bright"),
            TreeNode("click: the first focuses, the second activates"),
            TreeNode("placement: a click docks the cursor on its cell"),
        ], expanded=True)],
        theme=theme,
    )
    editor = Editor(text=EDITOR_TEXT, theme=theme)
    tail = [
        Text(TAIL_EMPTY, style=theme.accent),
        Text("", style=theme.dim),
        Text("", style=theme.dim),
    ]

    def draw() -> None:
        """Draw the session's log, newest first, onto the panel's rows.

        One row per report -- the leading one in the accent the page opened
        with -- and a blank row for a slot the log has not filled yet, so
        the panel is always :data:`TAIL_ROWS` rows tall and the page below
        it never jumps.  Both hooks call it: the log is a plain list, so
        drawing is idempotent and the two can never disagree.
        """
        entries = list(session.log) + [""] * TAIL_ROWS
        for row, entry in zip(tail, entries):
            row.text = entry

    def note(_text: str) -> None:
        """One activation was reported (the host's loud half): redraw now."""
        draw()

    return PageBody([
        *header("interaction",
                "Focus, click, activation, placement -- the interaction model itself, "
                "one ring over three widgets.", theme),
        try_line("tab moves the focus (the cursor row left behind dims) \u00b7 \u2191\u2193 move "
                 "\u00b7 enter activates \u00b7 click once to focus, again to activate \u00b7 "
                 "click a cell in the Editor to dock the cursor", theme),
        section("one ring, three widgets", theme),
        api_note("ring.handle(event) -> bool -- the arrows and enter go to the focused widget",
                 theme),
        api_note("ring.click(hit) -> bool -- dispatch the cell, focus it, activate on the "
                 "second click", theme),
        Text("the menu -- the row under the cursor is bright while the menu holds the focus",
             style=theme.dim),
        menu,
        api_note("component.chosen -- the host reads it once, then resets it to None", theme),
        Text("the tree -- \u2191\u2193 walk the visible rows; folding is the tree's activation",
             style=theme.dim),
        tree,
        api_note("Tree.activate() -> bool -- a fold has no pick; the log reads "
                 "`activate \u2192 tree`", theme),
        Text("the editor -- a field is not activated: a click writes the cursor into it",
             style=theme.dim),
        editor,
        api_note("field.click(row, col) -- the cell of its own render, then TextBuffer.place",
                 theme),
        section("last actions", theme),
        Text("the host's log, newest first -- a pick, a fold, a focus move, a page opening",
             style=theme.dim),
        *tail,
        api_note("Showcase.log -- the host writes every report; this page draws it", theme),
    ], focus=FocusRing([menu, tree, editor]), hint="menu, tree, editor", note=note, tick=draw)
