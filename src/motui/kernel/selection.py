"""Document-space selection: the value, the overlay, and the text extraction.

A :class:`Selection` is a range of ``(block_id, row, column)`` addresses
(:data:`SelectionAnchor`) -- document space, never screen space (D1): a
scroll moves the highlight with its text, and :func:`extract` reaches
content the viewport has long scrolled past.  Nothing here owns state,
time, or policy: :func:`highlight` is a pure overlay a composition root
applies to an already laid-out frame (D2), and :func:`extract` is the
plain text that overlay covers.

Two ordering facts shape the model.  Block ids carry no document order --
``"b10"`` sorts before ``"b2"`` and user ids are arbitrary strings -- so
direction can only be normalized where the order is known, at use time:
both use sites order the pair against a walk of block ids (the document
for extraction, the layout's document order for the overlay).  And an
address whose block was removed resolves to nothing (D8), which makes a
range with a missing endpoint resolve to nothing rather than guess.

Column cutting is the kernel's, not a copy: :func:`motui.kernel.lines.cut_line`
cuts by display columns through the same per-segment slicer word wrapping
uses, and clamps lazily -- an anchor column past a short row reaches that
row's end.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from .block import Document
from .lines import Line, cut_line
from .style import SELECTION
from .viewport import ScreenLayout

__all__ = ["Selection", "SelectionAnchor", "extract", "highlight"]
#: One cell address: the block id, the row within that block, the column.
SelectionAnchor = tuple[str, int, int]


class Selection:
    """A range of document addresses, carried as the ``(anchor, head)`` pair.

    Built through :meth:`between` and frozen afterwards.  The pair is stored
    exactly as given -- dragging backwards from the anchor keeps the head
    below it -- because direction only means something against the document
    order the use sites know (see the module docstring); the overlay and the
    extraction order the pair the same way, so a backwards drag covers
    exactly the range a forwards drag covers.  Columns clamp lazily, when a
    row's width is known.

    Internals may grow spans; the v1 surface is this one range (D8).
    """

    __slots__ = ("_anchor", "_head")

    def __init__(self, anchor: SelectionAnchor, head: SelectionAnchor) -> None:
        object.__setattr__(self, "_anchor", anchor)
        object.__setattr__(self, "_head", head)

    @classmethod
    def between(cls, anchor: SelectionAnchor, head: SelectionAnchor) -> "Selection":
        """The range from ``anchor`` to ``head`` (direction normalized at use)."""
        return cls(anchor, head)

    @property
    def anchors(self) -> tuple[SelectionAnchor, SelectionAnchor]:
        """The ``(anchor, head)`` pair, as it was passed to :meth:`between`.

        Round-trips: ``Selection.between(*selection.anchors) == selection``.
        A gesture extending the head reads the pair back off and rebuilds.
        """
        return (self._anchor, self._head)

    def _ordered(
        self, positions: dict[str, int]
    ) -> tuple[SelectionAnchor, SelectionAnchor]:
        """The pair ordered by ``positions`` -- a walk of block ids as a map.

        Different blocks rank by first appearance in the walk; one block
        (or two blocks the walk never shows) by ``(row, col)``.
        """
        anchor, head = self._anchor, self._head
        left, right = positions.get(anchor[0], -1), positions.get(head[0], -1)
        if left != right:
            return (anchor, head) if left < right else (head, anchor)
        return (anchor, head) if anchor[1:] <= head[1:] else (head, anchor)

    # -- immutability ------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Selection):
            return NotImplemented
        return self.anchors == other.anchors

    def __hash__(self) -> int:
        return hash((self._anchor, self._head))

    def __repr__(self) -> str:
        return f"Selection(anchor={self._anchor!r}, head={self._head!r})"


class _ResolvedRange:
    """A selection ordered against one walk of block ids, ready to apply.

    ``order`` is the walk: the layout's
    :attr:`~motui.kernel.viewport.ScreenLayout.block_order` for
    :func:`highlight`, the document's block ids for :func:`extract` --
    both document order, which is what lets the overlay and the text
    agree on which address starts the range.
    """

    __slots__ = ("_end", "_end_at", "_positions", "_start", "_start_at")

    def __init__(
        self,
        start: SelectionAnchor,
        end: SelectionAnchor,
        positions: dict[str, int],
    ) -> None:
        # Only :meth:`over` constructs one, and it has already resolved both
        # endpoints against ``positions``: the lookups below are total.
        self._start = start
        self._end = end
        self._start_at = positions[start[0]]
        self._end_at = positions[end[0]]
        self._positions = positions

    @classmethod
    def over(
        cls, selection: Selection, order: Sequence[str]
    ) -> "_ResolvedRange | None":
        """The selection resolved against ``order``, or ``None``.

        ``None`` when an endpoint's block is not in the walk: a removed
        block's address resolves to nothing (D8), and a range missing an
        endpoint has nothing left to cover -- it never widens to swallow
        the document.
        """
        positions = {block_id: index for index, block_id in enumerate(order)}
        start, end = selection._ordered(positions)
        if start[0] not in positions or end[0] not in positions:
            return None
        return cls(start, end, positions)

    def _position(self, block_id: str) -> int | None:
        """``block_id``'s position in the walk when it is inside the range.

        The one containment judgment: a block outside the range -- before it,
        after it, or never in the walk at all -- answers ``None``.
        """
        position = self._positions.get(block_id)
        if position is None or not self._start_at <= position <= self._end_at:
            return None
        return position

    def holds(self, block_id: str) -> bool:
        """Whether any row of ``block_id`` can be in the range."""
        return self._position(block_id) is not None

    def row_range(self, block_id: str, row: int) -> tuple[int, int | None] | None:
        """The columns ``(block_id, row)`` contributes, or ``None``.

        ``None`` means the row is outside the range.  The end column is
        ``None`` for "to the end of the row" -- the caller knows the row's
        width, and that is where columns clamp (D8: addresses point at
        cells, not content).
        """
        position = self._position(block_id)
        if position is None:
            return None
        _, start_row, start_col = self._start
        _, end_row, end_col = self._end
        if position == self._start_at:
            if row < start_row:
                return None
            if position == self._end_at:
                # One block on both sides: the middle rows are whole.
                if row > end_row:
                    return None
                return (
                    start_col if row == start_row else 0,
                    end_col if row == end_row else None,
                )
            return (start_col if row == start_row else 0, None)
        if position == self._end_at:
            if row > end_row:
                return None
            return (0, end_col if row == end_row else None)
        return (0, None)


def highlight(layout: ScreenLayout, selection: Selection | None) -> ScreenLayout:
    """The selection overlay (D2): one pure pass over a laid-out frame.

    Every screen row whose ``(block_id, row_in_block)`` -- from the
    layout's :attr:`~motui.kernel.viewport.ScreenLayout.row_blocks` --
    is in range gets its segments cut at the range's column boundaries and
    :data:`~motui.kernel.style.SELECTION` merged onto the cut pieces
    (plain reverse, so a segment's own hue becomes the highlight's background
    and the terminal default becomes its text).  Rows no block owns are
    untouched, and so is everything outside the range.

    ``selection=None`` -- or a range that resolves to nothing (D8) --
    returns the layout unchanged: no allocation, no copy.  The sealed-row
    cache is never involved: the overlay builds new :class:`Line` values
    over the layout's rows and touches nothing the viewport, the blocks,
    or the components hold.  ``rows`` is the painting target and the only
    field rewritten; ``viewport_rows`` (the window slice) travels through
    as it was laid out.
    """
    if selection is None:
        return layout
    order = layout.block_order
    if not order or not layout.row_blocks:
        return layout  # no ownership: nothing can be in range
    resolved = _ResolvedRange.over(selection, order)
    if resolved is None:
        return layout
    rows: list[Line] | None = None
    for index, (row, owner) in enumerate(zip(layout.rows, layout.row_blocks)):
        if owner is None:
            continue
        span = resolved.row_range(owner[0], owner[1])
        if span is None:
            continue
        start_col, end_col = span
        end = row.width if end_col is None else end_col
        marked = cut_line(row, start_col, end)
        if not marked.segments:
            continue  # an empty range paints nothing
        if rows is None:
            rows = list(layout.rows)
        rows[index] = Line(
            [
                *cut_line(row, 0, start_col).segments,
                *(
                    seg.with_style(seg.style.merge(SELECTION))
                    for seg in marked.segments
                ),
                *cut_line(row, end, row.width).segments,
            ]
        )
    if rows is None:
        return layout
    return replace(layout, rows=rows)


def extract(document: Document, selection: Selection | None, *, width: int) -> str:
    """The plain text of ``selection`` over ``document``, rows joined by ``"\\n"``.

    Walks the blocks in document order and slices the range's first and
    last rows by their columns through the same cluster-aware cut the
    overlay uses; rows fully inside the range are joined whole.  The
    blocks are read straight from the document -- not through a viewport
    window -- so content the viewport has scrolled past extracts exactly
    like the visible rows, and an ``OPEN`` block yields what is there now
    (D8's grid semantics: addresses point at cells, not identity).

    ``width`` is the width the addresses were laid out against: row
    numbers index wrapped rows, so another width addresses different
    glyphs.  It is keyword-only because there is no honest default --
    picking one silently would extract the wrong text.

    ``selection=None`` -- or a range with a removed endpoint -- yields
    ``""`` (D8), and so does an empty range.
    """
    if selection is None:
        return ""
    blocks = document.blocks()
    resolved = _ResolvedRange.over(selection, tuple(block.id for block in blocks))
    if resolved is None:
        return ""
    lines: list[str] = []
    for block in blocks:
        if not resolved.holds(block.id):
            continue  # outside the range (or already removed): nothing to render
        for row_index, row in enumerate(block.render(width)):
            span = resolved.row_range(block.id, row_index)
            if span is None:
                continue
            start_col, end_col = span
            if start_col == 0 and end_col is None:
                lines.append(row.text)  # whole row: the plain-text view
            else:
                lines.append(
                    cut_line(
                        row, start_col, row.width if end_col is None else end_col
                    ).text
                )
    return "\n".join(lines)

