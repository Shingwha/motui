"""Tree: an indented, collapsible list of :class:`TreeNode` values.

``Tree`` walks root nodes depth-first through open nodes only and renders one
row per visible node: indentation, a fold indicator (blank for leaves) and
the label.  ``filter`` prunes to matching chains without rewriting flags;
``jump`` is type-ahead.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..kernel.cell import Line, Segment, Surface, rest
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Glyphs, pair_seat, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from .strip import Keymap

__all__ = ["Tree", "TreeNode"]


class TreeNode:
    """One tree node: label, children, ``open`` and ``disabled``.

    Mutable on purpose: activation flips ``open`` in place.  A node without
    children is a leaf; a disabled node renders faint and cursor gestures
    skip it.
    """

    __slots__ = ("children", "disabled", "label", "open")

    def __init__(
        self,
        label: str,
        children=(),
        *,
        open: bool = False,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.children = list(children)
        self.open = open
        self.disabled = disabled

    def __repr__(self) -> str:
        return (
            f"TreeNode({self.label!r}, children={self.children!r}, "
            f"open={self.open}, disabled {self.disabled})"
        )


class Tree(CursorWidget):
    """An indented node list with a cursor and per-node expand/collapse.

    ``selected`` is the visible node under the cursor.  The cursor row rides
    ``rows.active`` (``rows.inactive`` unfocused), hover wins over it (D3),
    and disabled rows paint faint.  ``indent`` sets per-depth spacing; the
    fold pair shares one seated column so labels align.  Movement clamps;
    activation expands/collapses and emits the node.  ``filter``/``jump``
    narrow and steer rows without writing ``open`` flags.
    """

    __slots__ = (
        "_filter",
        "_hover_index",
        "disabled",
        "glyphs",
        "indent",
        "nodes",
    )

    #: The tree owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The cursor family's arrows plus the fold keys: left closes, right opens.
    keymap = Keymap(
        {
            **{k: v for k, v in CURSOR_KEYMAP.items() if k not in ("left", "right")},
            "left": "close",
            "right": "open",
        }
    )

    def __init__(
        self,
        nodes: Iterable[TreeNode] = (),
        *,
        indent: int = 2,
        glyphs: Glyphs = GLYPHS,
        disabled: bool = False,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.nodes = list(nodes)
        self.indent = indent
        self.glyphs = glyphs
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_index`` (:meth:`on_hover`).
        self.hover = False
        #: The whole tree refuses every cursor gesture when disabled.
        self.disabled = disabled
        # The active filter query (case-insensitive substring) or ``None``;
        # written by ``filter``, read by ``_visible``.  ``None`` -- the
        # default -- renders exactly the walk the tree always did.
        self._filter: str | None = None
        # The visible node row the pointer is on, or ``None``; written by
        # ``on_hover``, read by ``render``.  ``None`` renders byte-for-byte
        # what the tree always did.
        self._hover_index: int | None = None

    def _band(self, current: bool, hovered: bool, disabled: bool = False) -> Style:
        return self.group("rows").band(
            active=current, hovered=hovered, focused=self.focused, disabled=disabled
        )

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self._visible())

    def _entry_at(self, index: int) -> object | None:
        return self._visible()[index][0]

    def _cursor_disabled(self) -> Iterable[int]:
        return {i for i, (node, _, _) in enumerate(self._visible()) if node.disabled}

    def _cursor_wraps(self) -> bool:
        """The tree clamps at its visible ends; it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        return not self.disabled

    # -- the verbs ---------------------------------------------------------------

    def activate(self) -> bool:
        """Toggle the node under the cursor; ``True`` when it folded.

        Emits the node.  Leaves, disabled nodes and a disabled tree refuse.
        """
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        if not self._fold(not node.open):
            return False
        self._emit(node)
        return True

    def toggle(self) -> bool:
        """Flip the cursor node's open state without emitting a result."""
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        return self._fold(not node.open)

    def on_action(self, name: str) -> bool:
        """``open``/``close`` fold explicitly; every other name is the shared cursor's."""
        if name == "open":
            return self._fold(True)
        if name == "close":
            return self._fold(False)
        return super().on_action(name)

    def on_click(self, pos: Pos) -> bool:
        """Place the cursor on the visible node at ``pos.y``; ``True`` on a hit.

        ``pos.x`` is ignored; disabled nodes and trees refuse.
        """
        if self.disabled:
            return False
        visible = self._visible()
        if not 0 <= pos.y < len(visible):
            return False
        if visible[pos.y][0].disabled:
            return False
        self.select(pos.y)
        return True

    def _fold(self, opened: bool) -> bool:
        """Set the cursor node's ``open`` to ``opened``; ``True`` on a change.

        Leaves, disabled nodes and an already-matching state answer
        ``False``; a real flip re-clamps the cursor.
        """
        if self.disabled:
            return False
        node = self.selected
        if node is None or node.disabled or not node.children:
            return False
        if node.open == opened:
            return False
        node.open = opened
        self._sync_cursor()
        self.touch()
        return True

    def filter(self, query: str | None) -> bool:
        """Prune visible rows to labels holding ``query``; True when the rows moved.

        Case-insensitive substring; ancestors of hits are kept and their
        chains render open.  ``""`` matches everything, ``None`` clears.
        Auto-expansion is derived, never written to ``open``.  A changed
        query resets the cursor to the top; the answer says whether the rows
        changed.
        """
        query = None if query is None else str(query)
        if query == self._filter:
            return False  # the same list: the cursor stays where the host left it
        before = self._visible()
        self._filter = query
        # The P0: the row numbering the pointer named no longer exists (the
        # Autocomplete rule); a stale mark could otherwise band the wrong row.
        self._hover_index = None
        self._cursor.index = 0
        self.touch()
        return self._visible() != before

    def jump(self, char: str) -> bool:
        """Type-ahead: move the cursor to the next visible label starting with ``char``.

        Case-insensitive, wraps around and skips disabled rows; ``True``
        when the cursor landed elsewhere.  Non-printable or multi-character
        input, an empty tree and no match decline.
        """
        if len(char) != 1 or not char.isprintable():
            return False
        visible = self._visible()
        count = len(visible)
        if count == 0:
            return False
        needle = char.lower()
        current = self.index
        for step in range(1, count + 1):
            row = (current + step) % count
            node = visible[row][0]
            if not node.disabled and node.label.lower().startswith(needle):
                moved = row != current
                if moved:
                    self.select(row)
                return moved
        return False  # no enabled visible label starts with the character

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the visible node row under the pointer; True when the marking changed.

        Resolved like :meth:`on_click` without moving the cursor; ``None``
        clears it.
        """
        if pos is None:
            target = None
        else:
            visible = self._visible()
            target = pos.y if 0 <= pos.y < len(visible) else None
        changed = target != self._hover_index
        if changed:
            self._hover_index = target
            self.touch()
        return changed

    def render(self, c: Constraints) -> Surface:
        """One banded row per visible node; ``max_height`` truncates leading rows."""
        self._sync_cursor()
        visible = self._visible()
        cursor = self._cursor.index
        out: list[Line] = []
        for i, (node, depth, opened) in enumerate(visible):
            node_disabled = self.disabled or node.disabled
            out.append(
                rest(
                    self._node_row(node, depth, opened, i == cursor, node_disabled),
                    c.width,
                    self._band(i == cursor, i == self._hover_index, node_disabled),
                )
            )
        if c.max_height is not None:
            out = out[: c.max_height]
        return Surface.clipped(out, c.width)

    def _visible(self) -> list[tuple[TreeNode, int, bool]]:
        """The visible nodes as ``(node, depth, open)`` in draw order.

        ``open`` is what the indicator draws: the node's flag normally, or
        "has a kept child" under a filter (derived, never written back).
        """
        out: list[tuple[TreeNode, int, bool]] = []
        if self._filter is None:
            self._visit(self.nodes, 0, out)
        else:
            self._visit_filtered(self.nodes, 0, out, self._filter.lower())
        return out

    def _visit(
        self, nodes, depth: int, out: list[tuple[TreeNode, int, bool]]
    ) -> None:
        for node in nodes:
            out.append((node, depth, node.open))
            if node.open:
                self._visit(node.children, depth + 1, out)

    def _visit_filtered(
        self,
        nodes,
        depth: int,
        out: list[tuple[TreeNode, int, bool]],
        needle: str,
    ) -> None:
        """The filtered walk: keep a node when it matches or holds a match below.

        Emits the ancestor chain with ``open=True`` where a kept child
        follows; ``open`` flags are never consulted, so clearing restores
        the user's tree.
        """
        for node in nodes:
            below: list[tuple[TreeNode, int, bool]] = []
            self._visit_filtered(node.children, depth + 1, below, needle)
            if below or needle in node.label.lower():
                out.append((node, depth, bool(below)))
                out.extend(below)

    def _node_row(
        self,
        node: TreeNode,
        depth: int,
        opened: bool,
        current: bool,
        disabled: bool = False,
    ) -> Line:
        """One node's row: indentation and indicator, then the label.

        The cursor row is one unstyled run (its band comes from the caller);
        other rows paint the guide faint and the label base.  A leaf keeps
        the pair's wider seat blank so labels align.
        """
        guide = " " * (self.indent * depth)
        pair_width = max(
            seat_width(self.glyphs.fold_open), seat_width(self.glyphs.fold_closed)
        )
        if node.children:
            glyph, other = (
                (self.glyphs.fold_open, self.glyphs.fold_closed)
                if opened
                else (self.glyphs.fold_closed, self.glyphs.fold_open)
            )
            indicator = pair_seat(glyph, other)
        else:  # a leaf keeps the indicator column blank so labels align
            indicator = " " * pair_width
        if disabled:
            return Line((Segment(guide + indicator + node.label, self.group("text").faint),))
        if current:
            return Line((Segment(guide + indicator + node.label),))
        text = self.group("text")
        return Line(
            (
                Segment(guide + indicator, text.faint),
                Segment(node.label, text.base),
            )
        )

    def __repr__(self) -> str:
        return f"Tree({self.nodes!r}, index={self.index})"
