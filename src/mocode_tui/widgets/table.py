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
style to tint them.

The table can also carry a **row cursor**: ``index`` names a data row
(``None`` -- the default -- highlights nothing, so an unset table renders
byte-for-byte what a plain grid always did), the cursor row renders every
one of its data cells in ``selected_style`` (the theme's ``selection`` by
default: a reverse-video band reads better on a data grid than an accent),
and ``move`` / ``click`` / ``activate`` are the interactive surface a host
routes keys and hits to.  ``move`` clamps at the ends (a data view, not a
menu cycle -- D10), ``click`` maps a block row onto a data row through the
very layout ``render`` emits, and ``activate`` lands the cursor row's index
in ``chosen`` for the host to read once.

Only the kernel is imported; ``render`` is a pure function of the table and
``width``.
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

    The optional row cursor is the table's interactive face: ``index`` is
    the data row under it (``None`` -- the default, and the empty table's
    only value -- highlights nothing), ``selected`` reads that row's raw
    cells, and the cursor row renders every data cell in ``selected_style``
    (default the theme's ``selection``) while the header and the grid rules
    stay untouched; the row count and the column budgets are exactly the
    same whether a row is under the cursor or not.  ``move(delta)`` steps
    it and clamps at the ends, ``click(row, col)`` maps a rendered row onto
    a data row (``col`` is ignored: a data row owns its whole width), and
    ``activate()`` takes it into ``chosen`` -- the row index a host reads
    once, cleared by the next ``move`` or by a click that lands.
    ``focused`` is the focus flag the focus tier sets
    (:class:`~mocode_tui.core.block.Focusable`): while it is ``False`` the
    cursor band renders in ``selected_style.merge(theme.dim)`` -- the band
    stays legible but loses weight, and every other row renders unchanged.
    """

    __slots__ = (
        "_border_style",
        "_dim",
        "_first_column_style",
        "_header_style",
        "_index",
        "_selected_style",
        "aligns",
        "chosen",
        "focused",
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
        selected_style: Style | None = None,
        aligns: Sequence[str] | None = None,
        focused: bool = True,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self.theme = theme
        self.headers = list(headers)
        self.rows = [list(row) for row in rows]
        self.aligns = list(aligns) if aligns is not None else None
        self.focused = focused
        # No cursor until a host (or a key) puts one there: a table without a
        # cursor renders exactly the bytes it always did.
        self._index: int | None = None
        # The pending activation: written by ``activate``, read once by the
        # host, cleared by ``move`` and by a click that lands.
        self.chosen: int | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._header_style = (
            header_style if header_style is not None else DEFAULT_HEADER_STYLE
        )
        self._first_column_style = self._pick(first_column_style, "first_column")
        self._border_style = self._pick(border_style, "table_border")
        self._selected_style = self._pick(selected_style, "selection")
        self._dim = self._pick(None, "dim")

    # -- the cursor -------------------------------------------------------------

    @property
    def index(self) -> int | None:
        """The data row under the cursor; ``None`` while no row is selected.

        The index counts **data rows only** -- the header and the grid rules
        are not rows the cursor can sit on.  ``None`` is both the initial
        value and the empty table's only value.
        """
        return self._index

    @index.setter
    def index(self, value: int | None) -> None:
        if value is None or not self.rows:
            self._index = None
        else:
            self._index = min(max(value, 0), len(self.rows) - 1)

    @property
    def selected(self) -> list | None:
        """The raw data row under the cursor; ``None`` without one.

        The row is returned as stored -- the caller's own cells, not a copy
        and not a re-normalized row.  An index the current ``rows`` no
        longer answer (a host swapped them out) reads as no cursor.
        """
        index = self._index
        if index is None or not 0 <= index < len(self.rows):
            return None
        return self.rows[index]

    def move(self, delta: int) -> bool:
        """Move the cursor ``delta`` data rows, clamped at the ends; True on a move.

        The clamp is deliberate, and the opposite of the menu family's
        default: a menu is an *option list* -- its ends meet, so a step off
        one row lands on the other -- while a table is a *data view*: the
        first and the last data row are real edges, and a step past one
        stops there (D10).  With no cursor yet, a step lands on the edge it
        walks away from: ``down`` puts it on the first data row, ``up`` on
        the last.  ``False`` (and still no cursor) without rows, and
        ``False`` for a step that goes nowhere -- which still clears a
        pending :attr:`chosen`, so a stale pick never survives the next
        keystroke.
        """
        self.chosen = None
        count = len(self.rows)
        if count == 0 or delta == 0:
            return False
        if self._index is None:
            self._index = 0 if delta > 0 else count - 1
            return True
        target = min(max(self._index + delta, 0), count - 1)
        moved = target != self._index
        self._index = target
        return moved

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the data row rendered at block row ``row``; True on a hit.

        ``row`` is a 0-based row of this component's own ``render`` output --
        exactly what :meth:`~mocode_tui.app.TUI.hit_test` reports -- and the
        mapping back onto a data row comes from the table's own row layout
        (:meth:`_layout`: the top rule, the header and every ``├─┼─┤`` rule
        carry no data), never from a pinned row offset, so the mapping
        follows the rendered structure wherever it goes -- a shrunk or
        ellipsized cell, a header that takes more room than the body: the
        layout is read off the same shape ``render`` emits.  A row that
        carries no data -- the frame rows, and every row past the last
        rendered one -- answers ``False`` and changes nothing.  ``col`` is
        ignored, and deliberately so: every column of a data row belongs to
        that row, so no column narrows the hit.  A hit moves the cursor
        there (even when it already was) and clears a pending
        :attr:`chosen`.
        """
        layout = self._layout()
        if not 0 <= row < len(layout):
            return False
        entry = layout[row]
        if not isinstance(entry, int):  # a frame row: no data row to land on
            return False
        self._index = entry
        self.chosen = None
        return True

    def activate(self) -> bool:
        """Take the data row under the cursor into :attr:`chosen`.

        The table's :class:`~mocode_tui.core.block.Activable` verb: a host
        routes the return key here, reads ``chosen`` once -- the data row's
        index -- and resets it to ``None``.  Answers whether there was a row
        to take: ``False``, with ``chosen`` ``None``, for an empty table or
        a cursor no current row answers.
        """
        self.chosen = self.index if self.selected is not None else None
        return self.chosen is not None

    def render(self, width: int) -> list[Line]:
        aligns = [a if a in _ALIGNS else "left" for a in (self.aligns or ())]
        ncols = len(self.headers)
        if ncols == 0:
            # No columns, no data rows: one blank line -- the single-entry
            # shape ``_layout`` reports for a headerless table.
            return [Line()]
        natural = [
            sum(visible_width(seg.text) for seg in segs)
            for segs, _ in (_cell_segments(h, self._header_style) for h in self.headers)
        ]
        header = [_cell_segments(h, self._header_style) for h in self.headers]
        # The focus rule, once per render: an unfocused table dims its cursor
        # band, every other row keeps its own style untouched.
        selection = self._selected_style
        if not self.focused:
            selection = selection.merge(self._dim)
        cursor = self._index
        data: list[list[tuple[list[Segment], Style]]] = []
        for r, raw in enumerate(self.rows):
            cells: list[tuple[list[Segment], Style]] = []
            for i in range(ncols):
                cell = raw[i] if i < len(raw) else ""
                base = self._first_column_style if i == 0 else NONE
                segments, cell_base = _cell_segments(cell, base)
                if r == cursor:
                    # The cursor row is one band: the style every data cell
                    # already carries takes the selection on top (a cell's own
                    # color is kept, the band is added), and the padding rides
                    # it.  The header and the grid rules never merge it.
                    segments = [
                        Segment(seg.text, seg.style.merge(selection))
                        for seg in segments
                    ]
                    cell_base = cell_base.merge(selection)
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
        # The row structure comes from ``_layout`` -- the one list ``click``
        # reads too -- so the two can never disagree about which row is what.
        out: list[Line] = []
        for entry in self._layout():
            if isinstance(entry, int):  # a data row, carrying its own index
                out.append(self._row(data[entry], budgets, self._border_style, aligns))
            elif entry == "top":
                out.append(self._rule(budgets, _TOP_RULE, self._border_style))
            elif entry == "header":
                out.append(self._row(header, budgets, self._border_style, aligns))
            elif entry == "bottom":
                out.append(self._rule(budgets, _BOTTOM_RULE, self._border_style))
            else:  # "header_rule" / "row_rule": the same rule, twice over
                out.append(self._rule(budgets, _HEADER_RULE, self._border_style))
        return [line.fit(width) for line in out]

    def _layout(self) -> list[str | int]:
        """What each rendered row carries: a data-row index, or a frame token.

        :meth:`render` emits one line per entry and the hit mapping reads the
        same list back, so the table's row arithmetic lives in exactly one
        place.  An ``int`` entry is the index of the :attr:`rows` entry that
        row carries; a string names a frame row that carries no data:
        ``"top"`` / ``"header"`` / ``"header_rule"`` above the body,
        ``"row_rule"`` for the rule under a data row (the last one is the
        frame's bottom), ``"bottom"``, and ``"empty"`` -- the single blank
        row of a headerless table.  The shape is derived from the row list,
        never from pinned row numbers, so a data row's position follows
        whatever the table renders.
        """
        if not self.headers:
            return ["empty"]
        layout: list[str | int] = ["top", "header", "header_rule"]
        for index in range(len(self.rows)):
            layout.extend((index, "row_rule"))
        if self.rows:
            layout[-1] = "bottom"
        else:
            layout.append("bottom")
        return layout

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
