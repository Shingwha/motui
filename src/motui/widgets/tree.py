"""Tree: an indented, collapsible list of :class:`TreeNode` values.

``Tree`` walks its root nodes depth-first, descending into expanded nodes
only, and renders one row per visible node: ``indent`` spaces per depth, a
``\\u25be``/``\\u25b8`` indicator (``\\u25be`` expanded, ``\\u25b8`` collapsed) for
a node with children -- two blank columns for a leaf, so every label starts
at the same offset -- and the label itself.  Guides are deliberately
minimal: plain space indentation, **no ``\\u2502`` connectors**.

The row under the cursor forms one continuous ``cursor_style`` band like a
``Select`` row; the other rows carry the guide in ``guide_style`` and the
label in ``label_style``.  ``move`` clamps the cursor inside the visible
rows without wrapping, and ``activate`` expands/collapses the node under
it (a no-op on a leaf), re-clamping the cursor when rows disappear.  Styles
resolve once, at construction, as explicit > theme > ``DEFAULT_THEME``.

Two host gestures narrow and steer the rows without the tree ever changing
its own data: ``filter(query)`` prunes the tree to the labels holding the
query (case-insensitive substring), keeps the ancestors of every hit and
renders those chains open -- the user's ``expanded`` flags are never
rewritten, so clearing the filter restores the tree the user built -- and
``jump(char)`` is type-ahead: the cursor hops to the next *visible* node
whose label starts with that character, case-insensitively, wrapping around
the rows.
"""

from __future__ import annotations

from ..kernel.lines import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.theme import Theme, Themed

__all__ = ["Tree", "TreeNode"]


class TreeNode:
    """One tree node: a label, child nodes, and an ``expanded`` flag.

    A plain mutable class on purpose: :meth:`Tree.activate` flips
    ``expanded`` in place instead of rebuilding the path back to the root,
    which is what a frozen dataclass would force.  ``children`` is copied
    into a list; a node without children is a leaf and never expands.
    """

    __slots__ = ("children", "expanded", "label")

    def __init__(self, label: str, children=(), *, expanded: bool = False) -> None:
        self.label = label
        self.children = list(children)
        self.expanded = expanded

    def __repr__(self) -> str:
        return (
            f"TreeNode({self.label!r}, children={self.children!r}, "
            f"expanded={self.expanded})"
        )


class Tree(Themed):
    """An indented node list with a cursor and per-node expand/collapse.

    ``root_nodes`` is any iterable of :class:`TreeNode`; ``indent`` is the
    per-depth space count.  ``selected`` is the visible node under the
    cursor (``None`` for an empty tree).  ``guide_style`` (default: the
    theme's ``dim``) paints the indent and indicators, ``label_style``
    (default: plain) the unselected labels, and ``cursor_style`` (default:
    the theme's ``selection``) the whole row under the cursor.

    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.block.Focusable`): while it is ``True`` the
    cursor row renders in ``cursor_style``; while it is ``False`` that
    style is merged with the theme's ``dim`` -- the cursor stays legible
    but loses weight, and every other row renders unchanged.

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`); :meth:`hover_at` marks the
    visible node row under the pointer and that row merges the theme's
    ``hover`` over the styles it already carries (the cursor row's
    ``cursor_style`` included).  The marking starts ``None``, so an
    un-hovered tree renders byte-for-byte what it always did.

    :meth:`filter` prunes the visible rows to the labels holding a query
    (case-insensitive substring) and keeps the chain to every hit, rendered
    open -- the row's own ``\u25be``/``\u25b8`` indicator included; :meth:`jump`
    is the printable-key type-ahead.  Both read the ``expanded`` flags,
    neither writes them: the auto-expansion a filter shows is derived from
    the match structure on every walk, so clearing the filter brings the
    user's own rows back untouched.
    """

    __slots__ = (
        "_cursor",
        "_cursor_style",
        "_dim",
        "_filter",
        "_guide_style",
        "_hover_index",
        "_hover_style",
        "_label_style",
        "focused",
        "hover",
        "indent",
        "root_nodes",
        "theme",
    )

    def __init__(
        self,
        root_nodes,
        *,
        indent: int = 2,
        guide_style: Style | None = None,
        label_style: Style | None = None,
        cursor_style: Style | None = None,
        focused: bool = True,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.root_nodes = list(root_nodes)
        self.indent = indent
        self.focused = focused
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`hover_at`).
        self.hover = False
        self._cursor = 0
        # The active filter query (case-insensitive substring) or ``None``;
        # written by ``filter``, read by ``_visible``.  ``None`` -- the
        # default -- renders exactly the walk the tree always did.
        self._filter: str | None = None
        # The visible node row the pointer is on, or ``None``; written by
        # ``hover_at``, read by ``render``.  ``None`` renders byte-for-byte
        # what the tree always did.
        self._hover_index: int | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._guide_style = self._pick(guide_style, "dim")
        self._label_style = label_style if label_style is not None else NONE
        self._cursor_style = self._pick(cursor_style, "selection")
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "hover")

    @property
    def selected(self) -> TreeNode | None:
        """The visible node under the cursor, or ``None`` for an empty tree."""
        visible = self._visible()
        if not visible:
            return None
        return visible[self._cursor_index(visible)][0]

    def move(self, delta: int) -> bool:
        """Move the cursor by ``delta`` visible rows, clamped; True when it moved."""
        visible = self._visible()
        if not visible:
            return False
        target = min(max(self._cursor_index(visible) + delta, 0), len(visible) - 1)
        moved = target != self._cursor
        self._cursor = target
        return moved

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the visible node at rendered row ``row``; True on a hit.

        ``row`` is a 0-based row of this component's own ``render`` -- the
        visible nodes, in draw order.  A row that is a node answers
        ``True`` and moves the cursor there (even when it already was);
        any row past the last node answers ``False`` and leaves the cursor
        alone.  ``col`` is ignored: a node row belongs to its node from the
        first indent column to the last label column -- no column narrows
        the hit.
        """
        if not 0 <= row < len(self._visible()):
            return False
        self._cursor = row
        return True

    def activate(self) -> bool:
        """Expand/collapse the node under the cursor; True when it changed.

        The tree's :class:`~motui.kernel.block.Activable` verb: with the
        cursor on a node, expanding or collapsing *is* the main operation.
        A leaf has nothing to expand, so activating one is a no-op and
        answers False.  Collapsing can shrink the visible rows, so the
        cursor is clamped back into range afterwards.  While a
        :meth:`filter` is up the flag still flips -- it is the user's own
        state -- but the rendered chains follow the matches, so the fold
        becomes visible once the filter clears.
        """
        node = self.selected
        if node is None or not node.children:
            return False
        node.expanded = not node.expanded
        self._cursor = min(self._cursor, max(0, len(self._visible()) - 1))
        return True

    def filter(self, query: str | None) -> bool:
        """Prune the visible rows to the labels holding ``query``; True when they moved.

        A node stays visible when its own label holds ``query`` as a
        **case-insensitive substring** *or* a node below it does -- the
        ancestors of every hit are kept, so the chain to each match is on
        screen and renders **open** (the walk descends any kept node with
        kept children, whatever that node's own ``expanded`` flag says).
        An empty string matches every label (the substring rule), so
        ``filter("")`` shows the whole tree with every chain open; ``None``
        clears the filter.

        The auto-expansion is **derived, never written back**: the user's
        expansion set is exactly the nodes' ``expanded`` flags and the
        filter's own is recomputed from the match structure on every walk,
        so the two cannot drift -- ``filter(None)`` restores the user's rows
        because nothing was ever rewritten, and the filter never interferes
        with :meth:`activate`, whose fold simply waits for the filter to
        clear.  The cursor returns to the top row whenever the query
        changes (a new query is a new list -- the ``Autocomplete`` rule),
        and the answer says whether the *rows* changed: ``True`` for a
        query that prunes or restores, ``False`` for a no-op call (the same
        query twice, clearing an unfiltered tree).
        """
        query = None if query is None else str(query)
        if query == self._filter:
            return False  # the same list: the cursor stays where the host left it
        before = self._visible()
        self._filter = query
        self._cursor = 0
        return self._visible() != before

    def jump(self, char: str) -> bool:
        """Type-ahead: cursor to the next visible node starting with ``char``.

        ``char`` is one printable character (anything else declines without
        moving); the scan walks the **visible** rows -- the filtered ones
        included -- starting at the row *after* the cursor and wrapping
        around, so repeated presses cycle the matches and a press on a node
        already under the cursor moves on to the next hit rather than
        staying put.  The match is case-insensitive on the label's first
        character.  ``True`` when the cursor landed on a different row;
        ``False`` -- and nothing moved -- for a non-printable or multi-
        character argument, an empty tree, or a character no visible label
        starts with.

        The gallery shell routes no printable to a widget, so a host that
        wants live type-ahead routes its character keys here itself::

            if isinstance(event, Key) and event.char:
                tree.jump(event.char)
        """
        if len(char) != 1 or not char.isprintable():
            return False
        visible = self._visible()
        count = len(visible)
        if count == 0:
            return False
        needle = char.lower()
        current = self._cursor_index(visible)
        for step in range(1, count + 1):
            row = (current + step) % count
            if visible[row][0].label.lower().startswith(needle):
                self._cursor = row
                return row != current
        return False  # no visible label starts with the character

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the visible node row under a cell; True when the marking changed.

        The pointer tier's row-level half (D3): ``row`` is a 0-based row of
        the visible nodes in draw order -- exactly what :meth:`click`
        consumes, minus the cursor move -- and ``col`` is ignored like
        ``click``'s (a node row owns the whole width).  A row past the last
        node answers "no node" and clears the marking; a negative ``row``
        clears it too (the pointer left).  The answer is whether the marked
        row changed, and :meth:`render` merges the theme's ``hover`` over
        that row's own styles -- the cursor row's ``cursor_style``
        included.
        """
        if row < 0:
            target = None
        else:
            visible = self._visible()
            target = row if 0 <= row < len(visible) else None
        changed = target != self._hover_index
        self._hover_index = target
        return changed

    def render(self, width: int) -> list[Line]:
        visible = self._visible()
        cursor = self._cursor_index(visible)
        # The focus rule, once per render: an unfocused cursor row merges the
        # dim style over the cursor band (every other row is unchanged).
        cursor_style = self._cursor_style
        if not self.focused:
            cursor_style = cursor_style.merge(self._dim)
        out: list[Line] = []
        for i, (node, depth, opened) in enumerate(visible):
            out.append(
                self._node_row(
                    node,
                    depth,
                    opened,
                    i == cursor,
                    self._guide_style,
                    self._label_style,
                    cursor_style,
                    i == self._hover_index,
                ).fit(width)
            )
        return out

    def _visible(self) -> list[tuple[TreeNode, int, bool]]:
        """The visible nodes as ``(node, depth, open)`` triples, in draw order.

        ``open`` is what the row's own indicator shows: the node's
        ``expanded`` flag on the unfiltered walk, and "this node holds a
        kept child" on the filtered one (:meth:`_walk_filtered`) -- so a
        drawn ``\\u25be`` never disagrees with the rows actually below it,
        and the filter's derived auto-expansion is visible in the indicator
        without the flag ever being written.
        """
        out: list[tuple[TreeNode, int, bool]] = []
        if self._filter is None:
            self._walk(self.root_nodes, 0, out)
        else:
            self._walk_filtered(self.root_nodes, 0, out, self._filter.lower())
        return out

    def _walk(
        self, nodes, depth: int, out: list[tuple[TreeNode, int, bool]]
    ) -> None:
        for node in nodes:
            out.append((node, depth, node.expanded))
            if node.expanded:
                self._walk(node.children, depth + 1, out)

    def _walk_filtered(
        self,
        nodes,
        depth: int,
        out: list[tuple[TreeNode, int, bool]],
        needle: str,
    ) -> None:
        """The filtered walk: keep a node when it matches or holds a match below.

        Every node is visited -- a match below a match is a match too -- and
        a node is emitted when its own label holds ``needle`` or the walk
        below it emitted anything, with that subtree following it: the
        ancestors of every hit are kept and the chains render open (the
        emitted ``open`` flag is "there is a kept child", the row the
        indicator draws).  The ``expanded`` flags are not read here, which
        is exactly what makes the auto-expansion derived state (and the
        user's rows restorable by simply clearing the filter).
        """
        for node in nodes:
            below: list[tuple[TreeNode, int, bool]] = []
            self._walk_filtered(node.children, depth + 1, below, needle)
            if below or needle in node.label.lower():
                out.append((node, depth, bool(below)))
                out.extend(below)

    def _cursor_index(self, visible: list[tuple[TreeNode, int, bool]]) -> int:
        """The cursor clamped into the visible rows (hosts may mutate roots)."""
        return min(self._cursor, len(visible) - 1)

    def _node_row(
        self,
        node: TreeNode,
        depth: int,
        opened: bool,
        current: bool,
        guide_style: Style,
        label_style: Style,
        cursor_style: Style,
        hovered: bool = False,
    ) -> Line:
        """One node's row; ``hovered`` merges the theme's ``hover`` over it.

        The cursor row is one ``cursor_style`` band; every other row carries
        the guide in ``guide_style`` and the label in ``label_style``.  A
        hovered row merges the hover band over whatever it already carries,
        so the pointer's emphasis sits on top of the cursor's.  ``opened``
        is what the indicator draws -- the node's own ``expanded`` flag, or
        the filter's derived chain state -- and a leaf keeps the indicator
        column blank so labels align.
        """
        guide = " " * (self.indent * depth)
        indicator = ""
        if node.children:
            indicator = "\u25be" if opened else "\u25b8"
        else:  # a leaf keeps the indicator column blank so labels align
            indicator = " "
        if hovered:
            guide_style = guide_style.merge(self._hover_style)
            label_style = label_style.merge(self._hover_style)
            cursor_style = cursor_style.merge(self._hover_style)
        if current:
            return Line((Segment(guide + indicator + " " + node.label, cursor_style),))
        return Line(
            (
                Segment(guide + indicator + " ", guide_style),
                Segment(node.label, label_style),
            )
        )

    def __repr__(self) -> str:
        return f"Tree({self.root_nodes!r}, cursor={self._cursor})"
