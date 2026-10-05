"""Table component: a box-drawing grid of styled cells.

:class:`Table` renders a full box frame around the grid: a top rule
``┌─┬─┐``, the header row, the separator rule ``├─┼─┤`` and a bottom rule
``└─┴─┘``, with data rows in between.  A column's natural
width is the widest cell in it (header included) plus one padding cell per
side; when the natural total exceeds ``width`` the cell budgets shrink
proportionally -- floored, never below one column -- and over-long cells
are ellipsized.  Below ``width`` the grid keeps its natural size: the right
edge is never stretched.

Cells are ``str`` or ``(str, Style)``; a styled cell replaces the default
style for that cell.  ``first_column_style`` colors data rows' first column
only -- the header keeps ``header_style`` throughout.  The grid lines use
``border_style`` (the theme's ``table_border`` by default -- uncolored, which
reads cleanest on any background); pass a style to tint them.  Only the
kernel is imported; ``render`` is a pure function of the table and ``width``,
and every row is ``fit`` to ``width`` as a final guard.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..core.lines import Line, Segment
from ..core.style import NONE, Style
from ..core.text import ellipsize_tail, visible_width
from ..core.theme import DEFAULT_THEME, Theme

__all__ = ["Table"]

#: Header emphasis when the caller passes none (attribute-only, no color).
DEFAULT_HEADER_STYLE = Style(bold=True)

#: Horizontal rules as ``(left, cross, right)`` characters: the top rule
#: closes the frame above the header, the header rule separates it from the
#: body, the bottom rule closes the frame after the last row.  Every rule
#: is one ``─`` run of ``(column + 2)`` per column, so all three lines --
#: and each data row -- share exactly one width; adding the top and bottom
#: rules therefore leaves the column budget untouched.
_TOP_RULE = ("\u250c", "\u252c", "\u2510")  # ┌──┬──┐
_HEADER_RULE = ("\u251c", "\u253c", "\u2524")  # ├──┼──┤
_BOTTOM_RULE = ("\u2514", "\u2534", "\u2518")  # └──┴──┘


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
    ``first_column_style`` (default the theme's soft-purple bold) only
    touches data rows' first column.  Grid lines use ``border_style``
    (default the theme's uncolored ``table_border``).  Each style resolves
    at render time as explicit > theme field > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "border_style",
        "first_column_style",
        "header_style",
        "headers",
        "rows",
        "theme",
    )

    def __init__(
        self,
        headers: Iterable[str],
        rows: Iterable[Iterable[str | tuple[str, Style]]],
        *,
        header_style: Style | None = None,
        first_column_style: Style | None = None,
        border_style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        self.headers = list(headers)
        self.rows = [list(row) for row in rows]
        self.header_style = header_style
        self.first_column_style = first_column_style
        self.border_style = border_style
        self.theme = theme

    def render(self, width: int) -> list[Line]:
        theme = self.theme or DEFAULT_THEME
        header_style = (
            self.header_style if self.header_style is not None else DEFAULT_HEADER_STYLE
        )
        first_column_style = (
            self.first_column_style
            if self.first_column_style is not None
            else theme.first_column
        )
        border_style = self.border_style if self.border_style is not None else theme.table_border
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
                    text, style = str(cell), (first_column_style if i == 0 else NONE)
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
            self._rule(budgets, _TOP_RULE, border_style),
            self._row([(h, header_style) for h in self.headers], budgets, border_style),
            self._rule(budgets, _HEADER_RULE, border_style),
        ]
        out.extend(self._row(cells, budgets, border_style) for cells in data)
        out.append(self._rule(budgets, _BOTTOM_RULE, border_style))
        return [row.fit(width) for row in out]

    def _row(
        self,
        cells: list[tuple[str, Style]],
        budgets: list[int],
        border_style: Style,
    ) -> Line:
        """One ``│ cell │ cell │`` row; each cell is a single styled segment."""
        segments = [Segment("\u2502", border_style)]
        for i, (text, style) in enumerate(cells):
            fitted = ellipsize_tail(text, budgets[i])
            pad = " " * max(budgets[i] - visible_width(fitted), 0)
            segments.append(Segment(f" {fitted}{pad} ", style))
            segments.append(Segment("\u2502", border_style))
        return Line(segments)

    def _rule(
        self,
        budgets: list[int],
        corners: tuple[str, str, str],
        border_style: Style,
    ) -> Line:
        """A horizontal rule: ``left`` corner, one ``─`` run per column joined
        by the ``cross`` character, ``right`` corner (``┌──┬──┐`` and kin)."""
        left, cross, right = corners
        rule = left + cross.join("\u2500" * (b + 2) for b in budgets) + right
        return Line.from_text(rule, border_style)

    def __repr__(self) -> str:
        return f"Table({self.headers!r})"
