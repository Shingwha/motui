"""Layout containers: :class:`Row`, :class:`Column` and :class:`Stack`.

All are ordinary components of the component library
(``render(Constraints) -> Surface``) that arrange child components instead
of drawing: a ``Row`` places children side by side in columns of fixed or
shared width, a ``Column`` stacks them vertically with optional blank rows
between, and a ``Stack`` paints them on top of one another.  They nest (a
``Row`` child may be a ``Column``); beyond that, prefer building blocks and
padding by hand.  Only the kernel is imported:
:class:`~motui.kernel.document.Component` for the protocol,
:class:`~motui.kernel.cell.Line` / ``Surface`` for assembly.  Import the
containers from :mod:`motui.widgets.layout` or from :mod:`motui.widgets` /
the package root.

Children still receive a bare width int while the library migrates (they may
be 1.x components); the composed rows are clipped into a Surface, and a
``max_height`` budget truncates them.

:class:`Spacer` and :class:`Padding` complete the set: blank rows, and
whitespace around a child (optionally filled into a solid band).
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

__all__ = ["Column", "Padding", "Row", "Spacer"]



def _answer(rows: list[Line], c: Constraints) -> Surface:
    """The composed rows as the 2.0 answer, honouring the height budget.

    ``Surface.clipped`` only truncates, so a container's rows -- already
    fitted to the width -- pass through byte-for-byte.  The height budget
    slices a copy; the container's own memo keeps the untruncated rows, so a
    later call with a larger budget can still answer from it.
    """
    if c.max_height is not None:
        rows = rows[: c.max_height]
    return Surface.clipped(rows, c.width)


class Row(Container):
    """Children laid out side by side in aligned columns.

    ``widths[i]`` fixes a column's width (``None`` = flexible).  Flexible
    columns share what remains after the fixed columns and the inter-column
    gaps: the remainder is discarded (``remaining // count``), never
    redistributed, so the grid stays predictable.  Every cell is padded to
    its column width, the row count is the tallest child, and a ``fit(width)``
    at the end keeps rows inside ``width`` even when fixed widths overflow.
    Containers lay children out, they never restyle them.  The container
    implements ``Container.child_at`` over the geometry of its last render:
    a cell inside a column maps to that child, an inter-column gap column
    and a blank filler row below a shorter child belong to the ``Row``
    itself.

    The assembly is remembered per **child-row identity** (each child's rows
    by object, plus the column widths, the gap and the width): a host that
    repaints the same children re-splices nothing -- the child rows read
    through their own memories and the composed rows come back by copy
    (render-cost W4).  The remembered rows are the very ``Line`` values of
    the previous answer, and the ``child_at`` geometry is refreshed on a hit
    exactly as on a miss.
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
        """Lay the children out side by side and answer a clipped surface.

        Children receive the constraint's inner widths and the composed
        rows are fitted to ``c.width`` as before.  ``max_height`` truncates
        the final rows.
        """
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

        Gap columns, the blank filler rows below a shorter child and every
        cell before the first render answer ``None``.
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

    The container implements ``Container.child_at`` over the geometry of its
    last render: a row inside a child's own rows maps to that child, a
    ``gap`` row belongs to the ``Column`` itself.

    Like :class:`Row`, the stack is remembered per **child-row identity**
    (each child's rows by object, plus the gap and the width): an unchanged
    stack hands back the same rows without re-fitting a child row, and the
    ``child_at`` offsets are rebuilt from the child row counts either way.
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
        """Stack the children and answer a clipped surface.

        Children render at their inner widths; ``max_height`` truncates the
        final rows.
        """
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
            out.extend(row.clip(WrapMode.ELLIPSIS, width) for row in raw)
        self._memo = (key, out, raw_cells)
        return _answer(out, c)

    def child_at(self, row: int, col: int) -> tuple[Component, int, int] | None:
        """The child owning a row of the last render, in the child's coords.

        ``col`` passes through unchanged: a stacked child renders at the
        full width.  ``gap`` rows and every cell before the first render
        answer ``None``.
        """
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

    The capability flags count anywhere in the component's own extent; a
    coordinate door (``child_at``) counts when the cell descends to a
    component that is interactive.  The walk is pure geometry -- it never
    calls ``render`` -- and depth-guarded like the kernel's ``descend``, so
    a malformed container cannot hang a hit test.
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

    Every layer renders with the **same** constraints -- the whole frame
    width and the same height budget -- and the surfaces are composed bottom
    to top with :meth:`motui.kernel.cell.Surface.overlay`: a transparent
    cell lets the layer below show through, any other cell wins and merges
    the underlying style.  The result is clipped to ``c.width`` and
    ``c.max_height``.  With no children the stack answers the empty frame
    :meth:`~motui.kernel.cell.Surface.blank` of that size.

    **Hit testing prefers interaction over z-order.**  ``child_at`` walks
    from the top layer down and answers the first layer that has an
    interactive component at the cell -- a ``clickable``/``focusable``/
    ``hoverable`` component, or a container whose own ``child_at`` descends
    to one.  A non-interactive layer such as a background ``Canvas`` is
    therefore not a click target even when it is on top.  When no layer has
    an interactive node there, the topmost layer containing the cell wins
    (so text selection and geometry-only hits keep their z semantics), and a
    cell outside every layer answers ``None``.  The geometry comes from the
    last render; before it, every cell answers ``None``.
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
        """The layer owning a cell: interactive top-down, else topmost.

        Every layer shares the stack's origin, so the cell needs no offset.
        """
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


class Spacer(Widget):
    """``rows`` blank rows: vertical whitespace as a first-class component.

    Replaces the ``Text("")`` rows hosts used to stack for breathing room
    between blocks.  ``rows <= 0`` renders nothing.  A spacer has no styles
    and no theme values it reads -- it is whitespace, nothing else -- and no
    children, so it implements no ``Container.child_at``:
    ``isinstance(Spacer, Container)`` is ``False``.  It still inherits
    :class:`~motui.widgets.base.Widget` so ``walk()``/``touch()`` and the
    capability defaults cover it like every other mounted node.
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

    ``left``/``right``/``top``/``bottom`` are blank columns/rows around the
    child's own rows; the child renders at ``width - left - right`` and every
    emitted row is ``fit`` back to ``width``.  The fill is
    ``surfaces.base`` -- resolved at render time from ``styles`` (when
    given) or the theme, and ``NONE`` by default, so the padding is plain
    (invisible) spaces.  A non-``NONE`` fill paints the blank
    areas and merges *under* the child's own
    segment styles -- the child's colors win, the fill shows through
    wherever the child has none -- so the whole block reads as one
    continuous band, the full-width role-band pattern.
    The container
    implements ``Container.child_at`` over the geometry of its last render:
    only the child's own cells -- inside the insets -- map to the child,
    every padding cell belongs to the ``Padding`` itself.

    The padded rows are remembered per **child-row identity** (the child's
    rows by object, plus the clipped insets, the resolved fill and the
    width): a host
    that repaints the same child re-processes no row -- the fill merge in
    particular is skipped wholesale -- and a hit refreshes the ``child_at``
    geometry exactly as a miss does (render-cost W4).
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
        """Pad the child and answer a clipped surface.

        The child renders at the inner width; ``max_height`` truncates the
        final rows (the memo keeps the untruncated ones).
        """
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
        """The child owning a cell of the last render, in the child's coords.

        Only the child's own cells -- below ``top`` and inside the
        ``left``/``right`` insets -- map to it; every padding cell and every
        cell before the first render answers ``None``.
        """
        if row < 0 or col < 0:
            return None
        if row < self._top or row >= self._top + self._child_rows:
            return None
        if col < self._left or col >= self._left + self._inner:
            return None
        return self.child, row - self._top, col - self._left

    def _content_row(self, row: Line, inner: int, fill: Style) -> Line:
        """One child row plus the blank columns to its right.

        A ``NONE`` fill keeps the row's natural width followed by the
        ``right`` pad.  A band fill paints the blank columns up to
        ``inner + right`` in it and merges it under the child's
        segment styles, so the band stays continuous.
        """
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
