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
"""

from __future__ import annotations

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.theme import Theme, Themed

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
    (:class:`~mocode_tui.core.block.Focusable`): while it is ``True`` the
    cursor row renders in ``cursor_style``; while it is ``False`` that
    style is merged with the theme's ``dim`` -- the cursor stays legible
    but loses weight, and every other row renders unchanged.
    """

    __slots__ = (
        "_cursor",
        "_cursor_style",
        "_dim",
        "_guide_style",
        "_label_style",
        "focused",
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
        self._cursor = 0
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._guide_style = self._pick(guide_style, "dim")
        self._label_style = label_style if label_style is not None else NONE
        self._cursor_style = self._pick(cursor_style, "selection")
        self._dim = self._pick(None, "dim")

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

        The tree's :class:`~mocode_tui.core.block.Activable` verb: with the
        cursor on a node, expanding or collapsing *is* the main operation.
        A leaf has nothing to expand, so activating one is a no-op and
        answers False.  Collapsing can shrink the visible rows, so the
        cursor is clamped back into range afterwards.
        """
        node = self.selected
        if node is None or not node.children:
            return False
        node.expanded = not node.expanded
        self._cursor = min(self._cursor, max(0, len(self._visible()) - 1))
        return True

    def render(self, width: int) -> list[Line]:
        visible = self._visible()
        cursor = self._cursor_index(visible)
        # The focus rule, once per render: an unfocused cursor row merges the
        # dim style over the cursor band (every other row is unchanged).
        cursor_style = self._cursor_style
        if not self.focused:
            cursor_style = cursor_style.merge(self._dim)
        out: list[Line] = []
        for i, (node, depth) in enumerate(visible):
            out.append(
                self._node_row(
                    node,
                    depth,
                    i == cursor,
                    self._guide_style,
                    self._label_style,
                    cursor_style,
                ).fit(width)
            )
        return out

    def _visible(self) -> list[tuple[TreeNode, int]]:
        """The visible nodes as ``(node, depth)`` pairs, in draw order."""
        out: list[tuple[TreeNode, int]] = []
        self._walk(self.root_nodes, 0, out)
        return out

    def _walk(self, nodes, depth: int, out: list[tuple[TreeNode, int]]) -> None:
        for node in nodes:
            out.append((node, depth))
            if node.expanded:
                self._walk(node.children, depth + 1, out)

    def _cursor_index(self, visible: list[tuple[TreeNode, int]]) -> int:
        """The cursor clamped into the visible rows (hosts may mutate roots)."""
        return min(self._cursor, len(visible) - 1)

    def _node_row(
        self,
        node: TreeNode,
        depth: int,
        current: bool,
        guide_style: Style,
        label_style: Style,
        cursor_style: Style,
    ) -> Line:
        guide = " " * (self.indent * depth)
        indicator = ""
        if node.children:
            indicator = "\u25be" if node.expanded else "\u25b8"
        else:  # a leaf keeps the indicator column blank so labels align
            indicator = " "
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
