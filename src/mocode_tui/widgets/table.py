"""Table component: a box-drawing grid of styled cells.

:class:`Table` renders a full box frame around the grid: a top rule
``┌─┬─┐``, the header row, the separator rule ``├─┼─┤`` and a bottom rule
``└─┴─┘``, with the data rows in between and one ``├─┼─┤`` rule between
every two rows -- a full grid (an empty body leaves the frame alone).  A
column's natural width is the widest cell in it (header included) plus one
padding cell per side; when the natural total exceeds ``width`` the cell
budgets shrink proportionally -- floored, never below one column -- and
over-long cells are ellipsized.  Below ``width`` the grid keeps its
natural size: the right edge is never stretched.

Cells are ``str``, ``(str, Style)`` or ``Sequence[Segment]``.  ``str`` and
tuple cells normalize to a single segment (a tuple's style replaces the
cell's default, padding spaces included); a ``Segment`` list keeps its
styles -- an attribute-only segment (fg and bg both unset) is merged onto
the cell's base style, a colored segment stays absolute, the same rule
the Markdown inline engine applies.  The base style is ``header_style``
on the header row and ``first_column_style`` on data rows' first column
(``NONE`` elsewhere).  ``aligns`` gives each column's alignment
(``left`` / ``center`` / ``right``; anything else, and any column past
the list, reads as left) and is applied with pad segments inside the
column budget.  All rows of one table share exactly one width (frame
consistency); each is still ``fit`` to ``width`` as a final guard.

The grid lines use ``border_style`` (the theme's ``table_border`` by
default -- uncolored, which reads cleanest on any background); pass a
style to tint them.  Only the kernel is imported; ``render`` is a pure
function of the table and ``width``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..core.lines import Line, Segment, fuse, overlay
from ..core.style import NONE, Style
from ..core.text import visible_width
from ..core.theme import Theme, Themed

__all__ = ["Table"]

#: Header style when the caller passes none: none at all -- the header rule
#: already separates it from the body, and bold stays reserved for the
#: **...** syntax in Markdown cells.
DEFAULT_HEADER_STYLE = NONE

#: Accepted per-column alignment names; anything else reads as left.
_ALIGNS = ("left", "center", "right")

#: Horizontal rules as ``(left, cross, right)`` characters: the top rule
#: closes the frame above the header, the header rule separates it from the
#: body (and every data row from the next), the bottom rule closes the frame
#: after the last row.  Every rule is one ``─`` run of ``(column + 2)``
#: per column, so all lines -- and each data row -- share exactly one
#: width; adding rules therefore leaves the column budget untouched.
_TOP_RULE = ("\u250c", "\u252c", "\u2510")  # ┌──┬──┐
_HEADER_RULE = ("\u251c", "\u253c", "\u2524")  # ├──┼──┤
_BOTTOM_RULE = ("\u2514", "\u2534", "\u2518")  # └──┴──┘


def _shrink(natural: list[int], inner_total: int) -> list[int]:
    """Cell budgets proportional to the natural widths, floored, each >= 1.

    ``inner_total`` is clamped up to one column per column, so an
    over-narrow ``width`` still yields a (possibly ellipsized) grid rather
    than negative budgets.
    """
    n = len(natural)
    total = max(inner_total, n)
    nat_total = sum(natural)
    if nat_total <= 0:
        return [1] * n
    return [max(1, w * total // nat_total) for w in natural]


def _cell_segments(
    cell: str | tuple[str, Style] | Sequence[Segment] | Segment, base: Style
) -> tuple[list[Segment], Style]:
    """Normalize one cell to ``(segments, base)``.

    ``str`` becomes a single segment in ``base``; ``(str, Style)`` and a
    lone :class:`Segment` become a single segment whose style also becomes
    the cell base, so the padding spaces keep it (byte-identical to the
    single-segment row).  A ``Segment`` sequence is kept run by run: an
    attribute-only segment (fg and bg both unset) is merged onto
    ``base``, a colored segment stays absolute.
    """
    if isinstance(cell, Segment):
        return [cell], cell.style
    if isinstance(cell, tuple) and len(cell) == 2:
        text, style = cell
        return [Segment(text, style)], style
    if isinstance(cell, str):
        return [Segment(cell, base)], base
    segments = overlay(base, cell)
    return segments, base


class Table(Themed):
    """A box-line table of string, styled, or multi-segment cells.

    ``headers`` names the columns; ``rows`` holds the records (a short row
    is padded with empty cells, a long row is truncated at the last
    header).  Column widths follow the natural/shrink rules above; the
    header row always uses ``header_style`` (default ``NONE``), and
    ``first_column_style`` (default the theme's plain ``first_column``)
    only touches data rows' first column.  ``aligns`` aligns each column
    (``left`` / ``center`` / ``right``, default left).  Grid lines use
    ``border_style`` (default the theme's uncolored ``table_border``), and
    one ``├─┼─┤`` rule separates every two data rows.  Each style resolves
    once, at construction, as explicit > theme field > ``DEFAULT_THEME``.
    """

    __slots__ = (
        "_border_style",
        "_first_column_style",
        "_header_style",
        "aligns",
        "headers",
        "rows",
        "theme",
    )

    def __init__(
        self,
        headers: Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment],
        rows: Iterable[
            Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment]
        ],
        *,
        header_style: Style | None = None,
        first_column_style: Style | None = None,
        border_style: Style | None = None,
        aligns: Sequence[str] | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.headers = list(headers)
        self.rows = [list(row) for row in rows]
        self.aligns = list(aligns) if aligns is not None else None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._header_style = (
            header_style if header_style is not None else DEFAULT_HEADER_STYLE
        )
        self._first_column_style = self._pick(first_column_style, "first_column")
        self._border_style = self._pick(border_style, "table_border")

    def render(self, width: int) -> list[Line]:
        aligns = [a if a in _ALIGNS else "left" for a in (self.aligns or ())]
        ncols = len(self.headers)
        if ncols == 0:
            return [Line()]
        natural = [
            sum(visible_width(seg.text) for seg in segs)
            for segs, _ in (_cell_segments(h, self._header_style) for h in self.headers)
        ]
        header = [_cell_segments(h, self._header_style) for h in self.headers]
        data: list[list[tuple[list[Segment], Style]]] = []
        for row in self.rows:
            cells: list[tuple[list[Segment], Style]] = []
            for i in range(ncols):
                cell = row[i] if i < len(row) else ""
                base = self._first_column_style if i == 0 else NONE
                segments, cell_base = _cell_segments(cell, base)
                cells.append((segments, cell_base))
                natural[i] = max(natural[i], sum(visible_width(s.text) for s in segments))
            data.append(cells)
        # The rules take one column each (ncols + 1 of them), each column
        # another two for its padding.
        inner = width - (ncols + 1)
        if sum(w + 2 for w in natural) <= inner:
            budgets = natural  # fits: keep the natural widths, no stretch
        else:
            budgets = _shrink(natural, inner - 2 * ncols)
        out = [
            self._rule(budgets, _TOP_RULE, self._border_style),
            self._row(header, budgets, self._border_style, aligns),
            self._rule(budgets, _HEADER_RULE, self._border_style),
        ]
        for cells in data:
            out.append(self._row(cells, budgets, self._border_style, aligns))
            out.append(self._rule(budgets, _HEADER_RULE, self._border_style))
        if data:
            out[-1] = self._rule(budgets, _BOTTOM_RULE, self._border_style)
        else:
            out.append(self._rule(budgets, _BOTTOM_RULE, self._border_style))
        return [row.fit(width) for row in out]

    def _row(
        self,
        cells: list[tuple[list[Segment], Style]],
        budgets: list[int],
        border_style: Style,
        aligns: list[str],
    ) -> Line:
        """One ``│ cell │ cell │`` row, every cell keeping its own segments.

        A cell is truncated to its column budget through ``Line.fit``
        (the marker is one column, like the ellipsis of any other
        truncation); the alignment pad fills the remaining budget as a
        ``Segment`` in the cell's base style.  ``str`` and tuple cells
        have one style throughout, so the fused row is byte-identical to
        the single-segment rendering.  Columns past ``aligns`` read as
        left.
        """
        segments: list[Segment] = [Segment("\u2502", border_style)]
        for i, (cell_segments, base) in enumerate(cells):
            segments.extend(self._cell_parts(cell_segments, base, budgets[i], aligns, i))
            segments.append(Segment("\u2502", border_style))
        return Line(segments)

    @staticmethod
    def _cell_parts(
        cell: list[Segment],
        base: Style,
        inner: int,
        aligns: list[str],
        column: int,
    ) -> list[Segment]:
        """The padded, truncated, space-wrapped interior of one cell."""
        line = Line(cell)
        fitted = line if line.width <= inner else line.fit(inner)
        gap = max(inner - fitted.width, 0)
        align = aligns[column] if column < len(aligns) else "left"
        parts = list(fitted.segments)
        if align == "right":
            if gap:
                parts.insert(0, Segment(" " * gap, base))
        elif align == "center":
            if gap:
                lead = gap // 2
                parts.insert(0, Segment(" " * lead, base))
                parts.append(Segment(" " * (gap - lead), base))
        elif gap:  # left: the tail pad plus the trailing space
            parts.append(Segment(" " * gap, base))
        # Fuse adjacent runs that share a style; ``fuse`` keeps zero-width
        # runs, which paint nothing, so they are dropped here at the call.
        return [seg for seg in fuse([Segment(" ", base), *parts, Segment(" ", base)]) if seg.text]

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
