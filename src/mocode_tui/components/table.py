"""Table component: a box-drawing grid of styled cells.

:class:`Table` renders a header row, a separator rule and one row per
record inside box-line characters (``│`` / ``├─┼─┤``).  A column's natural
width is the widest cell in it (header included) plus one padding cell per
side; when the natural total exceeds ``width`` the cell budgets shrink
proportionally -- floored, never below one column -- and over-long cells
are ellipsized.  Below ``width`` the grid keeps its natural size: the right
edge is never stretched.

Cells are ``str`` or ``(str, Style)``; a styled cell replaces the default
style for that cell.  ``first_column_style`` colors data rows' first column
only -- the header keeps ``header_style`` throughout.  The grid lines use
:data:`TABLE_BORDER`, one step brighter than :data:`~mocode_tui.style.BORDER`
so the box stays legible on dark backgrounds (W12).  Only the kernel is
imported; ``render`` is a pure function of the table and ``width``, and
every row is ``fit`` to ``width`` as a final guard.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..lines import Line, Segment
from ..style import NONE, Style
from ..text import ellipsize_tail, visible_width

__all__ = ["TABLE_BORDER", "Table"]

#: Header emphasis when the caller passes none.
DEFAULT_HEADER_STYLE = Style(bold=True)

#: First-column emphasis for data rows when the caller passes none (the W11
#: palette's soft purple).
DEFAULT_FIRST_COLUMN_STYLE = Style(fg="#bc8cff", bold=True)

#: Grid line color: one step brighter than BORDER (#3d444d), which read as
#: too dim to trace on a dark background.  Shared with the Markdown table
#: rule so box grids look the same everywhere.
TABLE_BORDER = Style(fg="#9aa4b0")


def _shrink(natural: list[int], budget_total: int) -> list[int]:
    """Cell budgets proportional to the natural widths, floored, each >= 1.

    ``budget_total`` is clamped up to one column per column, so an
    over-narrow ``width`` still yields a (possibly ellipsized) grid rather
    than negative budgets.
    """
    n = len(natural)
    total = max(budget_total, n)
    nat_total = sum(natural)
    if nat_total <= 0:
        return [1] * n
    return [max(1, w * total // nat_total) for w in natural]


class Table:
    """A box-line table of string or styled cells.

    ``headers`` names the columns; ``rows`` holds the records (a short row
    is padded with empty cells, a long row is truncated at the last
    header).  Column widths follow the natural/shrink rules above; the
    header row always uses ``header_style`` (default bold), and
    ``first_column_style`` (default soft-purple bold) only touches data rows'
    first column.
    """

    __slots__ = ("first_column_style", "header_style", "headers", "rows")

    def __init__(
        self,
        headers: Iterable[str],
        rows: Iterable[Iterable[str | tuple[str, Style]]],
        *,
        header_style: Style | None = None,
        first_column_style: Style | None = None,
    ) -> None:
        self.headers = list(headers)
        self.rows = [list(row) for row in rows]
        self.header_style = header_style if header_style is not None else DEFAULT_HEADER_STYLE
        self.first_column_style = (
            first_column_style if first_column_style is not None else DEFAULT_FIRST_COLUMN_STYLE
        )

    def render(self, width: int) -> list[Line]:
        ncols = len(self.headers)
        if ncols == 0:
            return [Line()]
        natural = [visible_width(h) for h in self.headers]
        data: list[list[tuple[str, Style]]] = []
        for row in self.rows:
            cells: list[tuple[str, Style]] = []
            for i in range(ncols):
                cell = row[i] if i < len(row) else ""
                if isinstance(cell, tuple) and len(cell) == 2:
                    text, style = cell
                else:
                    text, style = str(cell), (self.first_column_style if i == 0 else NONE)
                natural[i] = max(natural[i], visible_width(text))
                cells.append((text, style))
            data.append(cells)
        # The rules take one column each (ncols + 1 of them), each column
        # another two for its padding.
        avail = width - (ncols + 1)
        if sum(w + 2 for w in natural) <= avail:
            budgets = natural  # fits: keep the natural widths, no stretch
        else:
            budgets = _shrink(natural, avail - 2 * ncols)
        out = [
            self._row([(h, self.header_style) for h in self.headers], budgets),
            self._rule(budgets),
        ]
        out.extend(self._row(cells, budgets) for cells in data)
        return [row.fit(width) for row in out]

    def _row(self, cells: list[tuple[str, Style]], budgets: list[int]) -> Line:
        """One ``│ cell │ cell │`` row; each cell is a single styled segment."""
        segments = [Segment("\u2502", TABLE_BORDER)]
        for i, (text, style) in enumerate(cells):
            fitted = ellipsize_tail(text, budgets[i])
            pad = " " * max(budgets[i] - visible_width(fitted), 0)
            segments.append(Segment(f" {fitted}{pad} ", style))
            segments.append(Segment("\u2502", TABLE_BORDER))
        return Line(segments)

    def _rule(self, budgets: list[int]) -> Line:
        """The header separator: ``├───┼───┤``, one run per column."""
        rule = "\u251c" + "\u253c".join("\u2500" * (b + 2) for b in budgets) + "\u2524"
        return Line.from_text(rule, TABLE_BORDER)

    def __repr__(self) -> str:
        return f"Table({self.headers!r})"
