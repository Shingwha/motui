"""Layout containers: :class:`Row`, :class:`Column`, :class:`Stack`, :class:`Align`.

They arrange child components rather than drawing: Row/Column tile rows,
Stack overlays layers, Align anchors one child.  ``Spacer`` and ``Padding``
add whitespace.  Only the kernel is imported; composition memories key on
child-row identity.
"""

from __future__ import annotations

from ..kernel.cell import Line, Segment, Surface
from ..kernel.document import Component
from ..kernel.geom import Size
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode
from ..kernel.theme import Styles, Theme
from ..widgets.base import Container, Widget

__all__ = ["Align", "Column", "Padding", "Row", "Spacer", "Stack"]



def _answer(rows: list[Line], c: Constraints) -> Surface:
    """The composed rows as a clipped surface, honouring ``max_height``.

    The memo keeps the untruncated rows, so a larger later budget can
    still answer from it.
    """
    if c.max_height is not None:
        rows = rows[: c.max_height]
    return Surface.clipped(rows, c.width)


class Row(Container):
    """Children laid out side by side in aligned columns.

    ``widths[i]`` fixes a column; flexible columns share ``remaining //
    count`` (remainder discarded), so the grid stays predictable.  Cells
    pad to their column, the height is the tallest child.  ``child_at``
    maps a rendered cell to its child; gap columns and filler rows belong
    to the Row.  Assembly is memoized on child-row identity.
    """

    __slots__ = ("_cell_rows", "_cells", "_memo", "gap", "widths")

    def __init__(
        self,
        children,
        *,
        widths: list[int | None] | None = None,
        gap: int = 1,
    ) -> None:
        super().__init__()
        # The base owns ``children`` (declared by ``Container``'s parent):
        # assigning the list also points every widget child's ``parent``
        # back at this row.
        self.children = list(children)
        self.widths = None if widths is None else list(widths)
        self.gap = gap
        # No cached geometry before the first render: `child_at` declines
        # every cell until `render` stores the layout it painted.
        self._cells: list[tuple[int, int]] = []  # (x_start, width) per child
        self._cell_rows: list[int] = []  # rendered rows per child
        #: The assembly memo: ``(child-row identity tuples, col widths, gap,
        #: width)`` -> ``(composed rows, the child rows that key it)``.  The
        #: child rows are kept so their identities stay pinned.
        self._memo: tuple[tuple, list[Line], list[list[Line]]] | None = None

    def render(self, c: Constraints) -> Surface:
        """Lay the children out side by side and return the clipped surface."""
        width = c.width
        count = len(self.children)
        if count == 0:
            return _answer([], c)
        columns = [
            self.widths[i] if self.widths is not None and i < len(self.widths) else None
            for i in range(count)
        ]
        gap_total = self.gap * (count - 1) if self.gap > 0 else 0
        fixed_total = sum(w for w in columns if w is not None and w > 0)
        flex = sum(1 for w in columns if w is None)
        remaining = width - gap_total - fixed_total
        share = remaining // flex if flex and remaining > 0 else 0
        col_widths = [w if w is not None else share for w in columns]

        raw_cells: list[list[Line]] = []
        x = 0
        geometry: list[tuple[int, int]] = []
        cell_rows: list[int] = []
        for child, col_width in zip(self.children, col_widths, strict=False):
            inner = max(0, col_width)
            raw = list(child.render(Constraints(width=inner)))
            raw_cells.append(raw)
            geometry.append((x, inner))
            cell_rows.append(len(raw))
            x += inner + (self.gap if self.gap > 0 else 0)
        self._cells = geometry
        self._cell_rows = cell_rows
        key = (
            tuple(tuple(map(id, rows)) for rows in raw_cells),
            tuple(col_widths),
            self.gap,
            width,
        )
        memo = self._memo
        if memo is not None and memo[0] == key:
            return _answer(list(memo[1]), c)

        cells = [
            [row.clip(WrapMode.ELLIPSIS, inner).fill(inner) for row in raw]
            for raw, (_, inner) in zip(raw_cells, geometry, strict=False)
        ]
        height = max(len(rows) for rows in cells)
        separator = Line.from_text(" " * self.gap) if self.gap > 0 else Line()
        out: list[Line] = []
        for r in range(height):
            line = Line()
            for i in range(count):
                if i:
                    line = line + separator
                rows = cells[i]
                if r < len(rows):
                    line = line + rows[r]
                else:
                    line = line + Line.from_text(" " * max(0, col_widths[i]))
            out.append(line.clip(WrapMode.ELLIPSIS, width))
        self._memo = (key, out, raw_cells)
        return _answer(out, c)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning a cell of the last render, in the child's coords.

        Gap columns, filler rows under shorter children and pre-render
        cells answer ``None``.
        """
        if row < 0 or col < 0:
            return None
        for i in range(min(len(self._cells), len(self.children))):
            x_start, cell_width = self._cells[i]
            if x_start <= col < x_start + cell_width:
                if row >= self._cell_rows[i]:
                    return None  # a blank filler row: the Row itself owns it
                return self.children[i], row, col - x_start
        return None

    def __repr__(self) -> str:
        return f"Row({self.children!r}, widths={self.widths!r}, gap={self.gap})"


class Column(Container):
    """Children stacked vertically, ``gap`` blank rows between them.

    ``child_at`` maps a row inside a child; gap rows belong to the Column.
    The stack is memoized on child-row identity.
    """

    __slots__ = ("_memo", "_offsets", "gap")

    def __init__(self, children, *, gap: int = 0) -> None:
        super().__init__()
        # The base owns ``children``; the assignment adopts each widget
        # child (``parent``) and leaves pure components alone.
        self.children = list(children)
        self.gap = gap
        # No cached geometry before the first render: `child_at` declines
        # every cell until `render` stores the layout it painted.
        self._offsets: list[tuple[int, int]] = []  # (y_start, rows) per child
        #: The stack memo: ``(child-row identity tuples, gap, width)`` ->
        #: ``(composed rows, the child rows that key it)``.
        self._memo: tuple[tuple, list[Line], list[list[Line]]] | None = None

    def render(self, c: Constraints) -> Surface:
        """Stack the children and return the clipped surface."""
        width = c.width
        raw_cells: list[list[Line]] = []
        offsets: list[tuple[int, int]] = []
        y = 0
        for i, child in enumerate(self.children):
            if i and self.gap > 0:
                y += self.gap
            raw = list(child.render(Constraints(width=width)))
            raw_cells.append(raw)
            offsets.append((y, len(raw)))
            y += len(raw)
        self._offsets = offsets
        key = (tuple(tuple(map(id, rows)) for rows in raw_cells), self.gap, width)
        memo = self._memo
        if memo is not None and memo[0] == key:
            return _answer(list(memo[1]), c)

        out: list[Line] = []
        for i, raw in enumerate(raw_cells):
            if i and self.gap > 0:
                out.extend(Line() for _ in range(self.gap))
            out.extend(
                row if row.width <= width else row.clip(WrapMode.ELLIPSIS, width)
                for row in raw
            )
        self._memo = (key, out, raw_cells)
        return _answer(out, c)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning a row of the last render; ``col`` passes through."""
        if row < 0 or col < 0:
            return None
        for i in range(min(len(self._offsets), len(self.children))):
            y_start, rows = self._offsets[i]
            if y_start <= row < y_start + rows:
                return self.children[i], row - y_start, col
        return None

    def __repr__(self) -> str:
        return f"Column({self.children!r}, gap={self.gap})"


def _interactive_at(component: Component, row: int, col: int) -> bool:
    """Whether ``component`` has an interactive target at ``(row, col)``.

    Capability flags count over the component's extent; ``child_at`` is
    followed to an interactive descendant.  Pure geometry (never renders),
    depth-guarded so a malformed container cannot hang a hit test.
    """
    for _ in range(64):
        if (
            getattr(component, "clickable", False)
            or getattr(component, "focusable", False)
            or getattr(component, "hoverable", False)
        ):
            return True
        child_at = getattr(component, "child_at", None)
        if child_at is None:
            return False
        hit = child_at(row, col)
        if hit is None:
            return False
        component, row, col = hit
    return False


class Stack(Container):
    """Children painted on top of one another, ``children[0]`` at the bottom.

    Every layer renders with the same constraints and layers overlay bottom
    to top; a transparent cell shows through.  Hit testing prefers
    interaction over z-order: the first top-down layer with an interactive
    component at the cell wins, else the topmost layer containing it.
    Geometry comes from the last render.
    """

    __slots__ = ("_geometry",)

    def __init__(
        self,
        children,
        *,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        # Bottom -> top; the assignment adopts widget children's ``parent``.
        self.children = list(children)
        #: Last render's per-layer ``(height, width)`` in its own frame.
        self._geometry: list[tuple[int, int]] = []

    def render(self, c: Constraints) -> Surface:
        """Overlay the children bottom to top and clip the composed frame."""
        if not self.children:
            return Surface.blank(Size(width=c.width, height=c.max_height or 0))
        layers = [
            child.render(Constraints(width=c.width, max_height=c.max_height))
            for child in self.children
        ]
        self._geometry = [(layer.height, layer.width) for layer in layers]
        composed = layers[0]
        for layer in layers[1:]:
            composed = layer.overlay(composed)
        rows = composed.rows
        if c.max_height is not None:
            rows = rows[: c.max_height]
        return Surface.clipped(rows, c.width)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The layer owning a cell: interactive top-down, else topmost."""
        if row < 0 or col < 0 or not self._geometry:
            return None
        topmost: tuple[Component, int, int] | None = None
        for index in range(len(self.children) - 1, -1, -1):
            height, width = self._geometry[index]
            if row >= height or col >= width:
                continue
            child = self.children[index]
            if topmost is None:
                topmost = (child, row, col)
            if _interactive_at(child, row, col):
                return child, row, col
        return topmost

    def __repr__(self) -> str:
        return f"Stack({self.children!r})"


class Align(Widget):
    """One child placed at a two-dimensional anchor in the frame.

    ``horizontal`` is left/center/right, ``vertical`` top/middle/bottom;
    invalid values raise ``ValueError``.  The child renders once with the
    full constraints; its extent is its row count by its widest row, and
    overflow is clipped, never wrapped.  ``child_at`` maps only the child's
    painted rectangle.
    """

    __slots__ = (
        "_child_height",
        "_child_width",
        "_left",
        "_top",
        "child",
        "horizontal",
        "vertical",
    )

    HORIZONTAL = ("left", "center", "right")
    VERTICAL = ("top", "middle", "bottom")

    def __init__(
        self,
        child,
        *,
        horizontal: str = "center",
        vertical: str = "middle",
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        if horizontal not in self.HORIZONTAL:
            raise ValueError(
                f"horizontal must be one of {self.HORIZONTAL}, got {horizontal!r}"
            )
        if vertical not in self.VERTICAL:
            raise ValueError(
                f"vertical must be one of {self.VERTICAL}, got {vertical!r}"
            )
        self.child = child
        # The explicit tree: the aligned child is this widget's one child.
        self.children = [child]
        self.horizontal = horizontal
        self.vertical = vertical
        # Geometry of the last render: the anchor offset and the part of the
        # child that fits inside the frame.
        self._top = 0
        self._left = 0
        self._child_height = 0
        self._child_width = 0

    def render(self, c: Constraints) -> Surface:
        surface = self.child.render(c)
        rows = surface.rows
        child_height = len(rows)
        child_width = max((row.width for row in rows), default=0)
        frame_width = c.width
        frame_height = child_height if c.max_height is None else c.max_height
        if self.horizontal == "left":
            left = 0
        elif self.horizontal == "center":
            left = max(0, (frame_width - child_width) // 2)
        else:
            left = max(0, frame_width - child_width)
        if self.vertical == "top":
            top = 0
        elif self.vertical == "middle":
            top = max(0, (frame_height - child_height) // 2)
        else:
            top = max(0, frame_height - child_height)
        self._top = top
        self._left = left
        self._child_height = min(child_height, frame_height - top)
        self._child_width = min(child_width, frame_width - left)
        out: list[Line] = []
        # A child already at the left edge needs no prefix row: ``Line() +
        # row`` is the same value, so the row can be normalized in place.
        prefix = Line.from_text(" " * left) if left else None
        # The frame padding is the same immutable value on every blank row.
        blank = Line.filled(frame_width)
        for r in range(frame_height):
            if top <= r < top + child_height:
                row = rows[r - top]
                if prefix is not None:
                    row = prefix + row
                if row.width > frame_width:
                    row = row.clip(WrapMode.CLIP, frame_width)
                if row.width < frame_width:
                    row = row.fill(frame_width)
                out.append(row)
            else:
                out.append(blank)
        return Surface.clipped(out, frame_width)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child's cell at ``(row, col)``, or ``None`` outside its rect."""
        if (
            row < self._top
            or row >= self._top + self._child_height
            or col < self._left
            or col >= self._left + self._child_width
        ):
            return None
        return self.child, row - self._top, col - self._left

    def __repr__(self) -> str:
        return (
            f"Align({self.child!r}, horizontal={self.horizontal!r}, "
            f"vertical={self.vertical!r})"
        )


class Spacer(Widget):
    """``rows`` blank rows: vertical whitespace as a component.

    ``rows <= 0`` renders nothing.  It reads no styles and has no children,
    so it is not a ``Container``.
    """

    __slots__ = ("rows",)

    def __init__(self, rows: int = 1) -> None:
        super().__init__()
        self.rows = rows

    def render(self, c: Constraints) -> Surface:
        """``rows`` blank rows as a clipped surface (the budget may shorten it)."""
        count = max(0, self.rows)
        if c.max_height is not None:
            count = min(count, c.max_height)
        return Surface.clipped([Line() for _ in range(count)], c.width)

    def __repr__(self) -> str:
        return f"Spacer(rows={self.rows})"


class Padding(Widget):
    """Whitespace around a child component.

    The child renders at ``width - left - right`` and rows are fitted back
    to ``width``.  The fill is ``surfaces.base`` (``NONE`` by default),
    merged under the child's styles.  ``child_at`` maps only the child's
    cells.  Padded rows are memoized on child-row identity.
    """

    __slots__ = (
        "_child_rows",
        "_inner",
        "_left",
        "_memo",
        "_top",
        "bottom",
        "child",
        "left",
        "right",
        "top",
    )

    def __init__(
        self,
        child,
        *,
        left: int = 0,
        right: int = 0,
        top: int = 0,
        bottom: int = 0,
        theme: Theme | None = None,
        styles: Styles | None = None,
    ) -> None:
        super().__init__(theme, styles)
        self.child = child
        # The explicit tree: the padded child is this widget's child; a
        # widget child gets its ``parent`` pointed back here.
        self.children = [child]
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
        # No cached geometry before the first render: `child_at` declines
        # every cell until `render` stores the layout it painted.
        self._child_rows = 0
        self._inner = 0
        self._left = 0
        self._top = 0
        #: The padding memo: ``(child-row identity tuple, clipped insets,
        #: fill, width)`` -> ``(padded rows, the child rows that key it)``.
        self._memo: tuple[tuple, list[Line], list[Line]] | None = None

    def render(self, c: Constraints) -> Surface:
        """Pad the child and return the clipped surface."""
        width = c.width
        left = max(0, self.left)
        top = max(0, self.top)
        right = max(0, self.right)
        bottom = max(0, self.bottom)
        inner = max(0, width - left - right)
        fill = self.group("surfaces").base
        child_rows = list(self.child.render(Constraints(width=inner)))
        self._child_rows = len(child_rows)
        self._inner = inner
        self._left = left
        self._top = top
        key = (tuple(map(id, child_rows)), left, right, top, bottom, fill, width)
        memo = self._memo
        if memo is not None and memo[0] == key:
            return _answer(list(memo[1]), c)

        left_pad = Line.from_text(" " * left, fill)
        out: list[Line] = []
        for _ in range(top):
            out.append(Line.filled(width, fill) if fill != NONE else Line())
        for row in child_rows:
            out.append(
                (left_pad + self._content_row(row, inner, fill)).clip(
                    WrapMode.ELLIPSIS, width
                )
            )
        for _ in range(bottom):
            out.append(Line.filled(width, fill) if fill != NONE else Line())
        self._memo = (key, out, child_rows)
        return _answer(out, c)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning a cell of the last render; padding cells answer ``None``."""
        if row < 0 or col < 0:
            return None
        if row < self._top or row >= self._top + self._child_rows:
            return None
        if col < self._left or col >= self._left + self._inner:
            return None
        return self.child, row - self._top, col - self._left

    def _content_row(self, row: Line, inner: int, fill: Style) -> Line:
        """One child row plus the right padding; a fill merges under the child's styles."""
        if fill == NONE:
            return row + Line.from_text(" " * max(0, self.right))
        segments = [seg.with_style(fill.merge(seg.style)) for seg in row.segments]
        gap = inner - Line(segments).width + max(0, self.right)
        if gap > 0:
            segments.append(Segment(" " * gap, fill))
        return Line(segments)

    def __repr__(self) -> str:
        return (
            f"Padding({self.child!r}, left={self.left}, right={self.right}, "
            f"top={self.top}, bottom={self.bottom})"
        )
