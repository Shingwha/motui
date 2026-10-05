"""Layout containers: :class:`Row` and :class:`Column`.

Both are ordinary components of the component library
(``render(width) -> list[Line]``) that arrange child components instead of
drawing: a ``Row`` places children side by side in columns of fixed or
shared width, a ``Column`` stacks them vertically with optional blank
rows between.  They nest one level deep (a ``Row`` child may be a
``Column``); beyond that, prefer building blocks and padding by hand.
Only the kernel is imported: :class:`~mocode_tui.core.block.Component` for the
protocol, :class:`~mocode_tui.core.lines.Line` for assembly.

They used to live at ``mocode_tui.layout``; that module path is gone by
design -- import the containers from :mod:`mocode_tui.widgets.layout`
or from :mod:`mocode_tui.widgets` / the package root.

:class:`Spacer` and :class:`Padding` complete the set: blank rows, and
whitespace around a child (optionally filled into a solid band).  Import
them from :mod:`mocode_tui.widgets.layout` -- the package-facade
re-export of the new classes is curated by the restructure's final wave.
"""

from __future__ import annotations

from ..core.block import Component
from ..core.lines import Line, Segment
from ..core.style import Style

__all__ = ["Column", "Padding", "Row", "Spacer"]


class Row:
    """Children laid out side by side in aligned columns.

    ``widths[i]`` fixes a column's width (``None`` = flexible).  Flexible
    columns share what remains after the fixed columns and the inter-column
    gaps: the remainder is discarded (``remaining // count``), never
    redistributed, so the grid stays predictable.  Every cell is padded to
    its column width, the row count is the tallest child, and a ``fit(width)``
    at the end keeps rows inside ``width`` even when fixed widths overflow.
    Containers lay children out, they never restyle them.
    """

    __slots__ = ("children", "gap", "widths")

    def __init__(
        self,
        children,
        *,
        widths: list[int | None] | None = None,
        gap: int = 1,
    ) -> None:
        self.children = list(children)
        self.widths = None if widths is None else list(widths)
        self.gap = gap

    def render(self, width: int) -> list[Line]:
        count = len(self.children)
        if count == 0:
            return []
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

        cells: list[list[Line]] = []
        for child, col_width in zip(self.children, col_widths):
            inner = max(0, col_width)
            cells.append([row.fit(inner).pad_to(inner) for row in child.render(inner)])
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
            out.append(line.fit(width))
        return out

    def __repr__(self) -> str:
        return f"Row({self.children!r}, widths={self.widths!r}, gap={self.gap})"


class Column:
    """Children stacked vertically, ``gap`` blank rows between them."""

    __slots__ = ("children", "gap")

    def __init__(self, children, *, gap: int = 0) -> None:
        self.children = list(children)
        self.gap = gap

    def render(self, width: int) -> list[Line]:
        out: list[Line] = []
        for i, child in enumerate(self.children):
            if i and self.gap > 0:
                out.extend(Line() for _ in range(self.gap))
            out.extend(row.fit(width) for row in child.render(width))
        return out

    def __repr__(self) -> str:
        return f"Column({self.children!r}, gap={self.gap})"


class Spacer:
    """``rows`` blank rows: vertical whitespace as a first-class component.

    Replaces the ``Text("")`` rows hosts used to stack for breathing room
    between blocks.  ``rows <= 0`` renders nothing.  A spacer has no styles
    and no theme -- it is whitespace, nothing else.
    """

    __slots__ = ("rows",)

    def __init__(self, rows: int = 1) -> None:
        self.rows = rows

    def render(self, width: int) -> list[Line]:
        return [Line() for _ in range(max(0, self.rows))]

    def __repr__(self) -> str:
        return f"Spacer(rows={self.rows})"


class Padding:
    """Whitespace around a child component.

    ``left``/``right``/``top``/``bottom`` are blank columns/rows around the
    child's own rows; the child renders at ``width - left - right`` and every
    emitted row is ``fit`` back to ``width``.  With ``fill_style=None`` the
    padding is plain (invisible) spaces.  With ``fill_style`` set, the blank
    areas are painted in that style and it merges *under* the child's own
    segment styles -- the child's colors win, the fill shows through
    wherever the child has none -- so the whole block reads as one
    continuous band, the pattern :class:`~mocode_tui.chat.message.Message`
    uses for its user turns.  The fill is never themed.
    """

    __slots__ = ("bottom", "child", "fill_style", "left", "right", "top")

    def __init__(
        self,
        child,
        *,
        left: int = 0,
        right: int = 0,
        top: int = 0,
        bottom: int = 0,
        fill_style: Style | None = None,
    ) -> None:
        self.child = child
        self.left = left
        self.right = right
        self.top = top
        self.bottom = bottom
        self.fill_style = fill_style

    def render(self, width: int) -> list[Line]:
        inner = max(0, width - max(0, self.left) - max(0, self.right))
        fill = self.fill_style
        left_pad = Line.from_text(" " * max(0, self.left), fill)
        out: list[Line] = []
        for _ in range(max(0, self.top)):
            out.append(Line.filled(width, fill) if fill is not None else Line())
        for row in self.child.render(inner):
            out.append((left_pad + self._content_row(row, inner, fill)).fit(width))
        for _ in range(max(0, self.bottom)):
            out.append(Line.filled(width, fill) if fill is not None else Line())
        return out

    def _content_row(self, row: Line, inner: int, fill: Style | None) -> Line:
        """One child row plus the blank columns to its right.

        Without a fill the row keeps its natural width followed by the
        ``right`` pad.  With a fill the blank columns up to
        ``inner + right`` are painted in it and it merges under the child's
        segment styles, so the band stays continuous.
        """
        if fill is None:
            return row + Line.from_text(" " * max(0, self.right))
        segments = [
            Segment(seg.text, fill.merge(seg.style)) for seg in row.segments
        ]
        gap = inner - Line(segments).width + max(0, self.right)
        if gap > 0:
            segments.append(Segment(" " * gap, fill))
        return Line(segments)

    def __repr__(self) -> str:
        return (
            f"Padding({self.child!r}, left={self.left}, right={self.right}, "
            f"top={self.top}, bottom={self.bottom})"
        )
