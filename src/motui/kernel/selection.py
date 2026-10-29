"""Document-space selection: the value, the overlay and the text extraction.

Addresses are ``(block, row, column)`` in document space, never screen
space, so a scroll moves the highlight with its text. Order is normalized
at use against a known block walk, and a removed endpoint resolves to
nothing rather than guessing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from .cell import Line, cut_line
from .document import Document
from .layout import Constraints, ScreenLayout
from .style import Style

__all__ = ["Selection", "SelectionAnchor", "extract", "highlight"]
#: One cell address: the block id, the row within that block, the column.
SelectionAnchor = tuple[str, int, int]


class Selection:
    """A range of document addresses, carried as the ``(anchor, head)`` pair.

    Stored exactly as given; direction is normalized at use against a walk of
    block ids, so a backwards drag covers the same range as a forwards one."""

    __slots__ = ("_anchor", "_head")

    def __init__(self, anchor: SelectionAnchor, head: SelectionAnchor) -> None:
        object.__setattr__(self, "_anchor", anchor)
        object.__setattr__(self, "_head", head)

    @classmethod
    def between(cls, anchor: SelectionAnchor, head: SelectionAnchor) -> Selection:
        """The range from ``anchor`` to ``head`` (direction normalized at use)."""
        return cls(anchor, head)

    @property
    def anchors(self) -> tuple[SelectionAnchor, SelectionAnchor]:
        """The ``(anchor, head)`` pair, as passed to :meth:`between`; round-trips."""
        return (self._anchor, self._head)

    def _ordered(
        self, positions: dict[str, int]
    ) -> tuple[SelectionAnchor, SelectionAnchor]:
        """Order the pair by block position, then by ``(row, col)`` within one block."""
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
    """A selection ordered against one walk of block ids, ready to apply;
    ``order`` is the layout's or the document's."""

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
    ) -> _ResolvedRange | None:
        """The selection resolved against ``order``, or ``None`` when an endpoint's
        block is gone -- a range never widens to swallow the document."""
        positions = {block_id: index for index, block_id in enumerate(order)}
        start, end = selection._ordered(positions)
        if start[0] not in positions or end[0] not in positions:
            return None
        return cls(start, end, positions)

    def _position(self, block_id: str) -> int | None:
        """The block's walk position when inside the range, else ``None``."""
        position = self._positions.get(block_id)
        if position is None or not self._start_at <= position <= self._end_at:
            return None
        return position

    def holds(self, block_id: str) -> bool:
        """Whether any row of ``block_id`` can be in the range."""
        return self._position(block_id) is not None

    def row_range(self, block_id: str, row: int) -> tuple[int, int | None] | None:
        """The columns ``(block_id, row)`` contributes, or ``None``; an end column
        of ``None`` means to the end of the row."""
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


def highlight(
    layout: ScreenLayout,
    selection: Selection | None,
    *,
    style: Style = Style(reverse=True),
) -> ScreenLayout:
    """The selection overlay: one pure pass over a laid-out frame.

    Rows in range are cut at the column boundaries and ``style`` is merged
    onto the pieces; ``None`` or an unresolvable range returns the layout
    unchanged."""
    if selection is None:
        return layout
    order = layout.block_order
    if not order or not layout.row_blocks:
        return layout  # no ownership: nothing can be in range
    resolved = _ResolvedRange.over(selection, order)
    if resolved is None:
        return layout
    rows: list[Line] | None = None
    for index, (row, owner) in enumerate(
        zip(layout.rows, layout.row_blocks, strict=False)
    ):
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
                    seg.with_style(seg.style.merge(style))
                    for seg in marked.segments
                ),
                *cut_line(row, end, row.width).segments,
            ]
        )
    if rows is None:
        return layout
    return replace(layout, rows=rows)


def extract(document: Document, selection: Selection | None, *, width: int) -> str:
    """The plain text of ``selection`` over ``document``, rows joined by
    newlines.

    Blocks are read from the document, not a viewport window, so scrolled-past
    content extracts too. ``width`` must be the width the addresses were laid
    out against, because row numbers index wrapped rows."""
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
        for row_index, row in enumerate(block.rows_view(Constraints(width=width))):
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

