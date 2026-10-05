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
"""

from __future__ import annotations

from ..core.block import Component
from ..core.lines import Line

__all__ = ["Column", "Row"]


class Row:
    """Children laid out side by side in aligned columns.

    ``widths[i]`` fixes a column's width (``None`` = flexible).  Flexible
    columns share what remains after the fixed columns and the inter-column
    gaps: the remainder is discarded (``remaining // count``), never
    redistributed, so the grid stays predictable.  Every cell is padded to
    its column width, the row count is the tallest child, and a ``fit(width)``
    at the end keeps rows inside ``width`` even when fixed widths overflow.
    """

    __slots__ = ("children", "gap", "widths")

    def __init__(self, children, *, widths: list[int | None] | None = None, gap: int = 1) -> None:
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
            usable = max(0, col_width)
            cells.append([row.fit(usable).pad_to(usable) for row in child.render(usable)])
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
