"""Table: a box-drawing grid of styled cells with cursor, marks and sorting.

Depends only on ``motui.kernel``; ``render`` is a pure function of the table
and the width.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import NamedTuple

from ..kernel.cell import Line, Segment, Surface, fuse, overlay, rest
from ..kernel.geom import Pos
from ..kernel.glyphs import GLYPHS, Border, Glyphs, pair_seat, seat_width
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode, visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import CURSOR_KEYMAP, CursorWidget
from ..widgets.mark import MarkSet
from .strip import Keymap

__all__ = ["Table"]

#: Accepted per-column alignment names; anything else reads as left.
_ALIGNS = ("left", "center", "right")


class _Slot(NamedTuple):
    """One visual row: kind (data-row index or frame token), data row, visual line."""

    kind: str | int
    data_row: int | None
    visual_line: int


def _wrap_budgets(
    natural: list[int],
    width: int,
    ncols: int,
    max_col_width: int | None,
    min_col_width: int,
) -> list[int]:
    """Per-column content budgets for the wrapped policies.

    Caps at ``max_col_width``, floors at ``min_col_width`` and shrinks
    proportionally when over budget, never below the floor; a width too
    narrow for the floors gives every column an equal share.
    """
    floor = max(1, min_col_width)
    if max_col_width is None:
        preferred = [max(floor, w) for w in natural]
    else:
        cap = max(1, max_col_width)
        preferred = [max(floor, min(w, cap)) for w in natural]
    # The frame takes ncols + 1 columns; every cell takes two padding cells.
    avail = width - (ncols + 1) - 2 * ncols
    if ncols * floor > avail:
        share = max(1, avail // ncols)
        return [share] * ncols
    total = sum(preferred)
    if total <= avail:
        return preferred
    budgets = [max(floor, w * avail // total) for w in preferred]
    # The floors can overshoot the proportional split; trim the widest
    # columns (never below the floor) until the whole grid fits.
    excess = sum(budgets) - avail
    while excess > 0:
        widest = max(range(ncols), key=budgets.__getitem__)
        if budgets[widest] <= floor:
            break
        budgets[widest] -= 1
        excess -= 1
    return budgets


def _shrink(natural: list[int], inner_total: int) -> list[int]:
    """Natural widths scaled into ``inner_total``, floored at one per column.

    ``inner_total`` is clamped up to one column per column, so budgets never
    go negative.
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

    A tuple or lone ``Segment`` also replaces the cell base so padding keeps
    its style; a segment list is kept run by run, attribute-only runs merged
    onto ``base`` and colored runs left absolute.
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


def _cell_text(cell: str | tuple[str, Style] | Sequence[Segment] | Segment) -> str:
    """One cell's plain text, styles dropped -- the key :meth:`Table.sort_by` reads."""
    if isinstance(cell, Segment):
        return cell.text
    if isinstance(cell, tuple) and len(cell) == 2:
        return cell[0]
    if isinstance(cell, str):
        return cell
    return "".join(seg.text for seg in cell)


class Table(CursorWidget):
    """A box-line table of string, styled or multi-segment cells.

    ``cell_wrap`` picks the width policy: ``WORD``/``CHAR`` wrap under
    ``max_col_width``/``min_col_width``, ``ELLIPSIS``/``CLIP`` keep one row,
    ``OVERFLOW`` keeps the natural grid width for a scroll container.  An
    optional cursor bands its row and activates to :meth:`take`; marks are
    sticky row indices; sorting and width pins follow row identity.
    ``render`` is memoized on ``generation`` and width -- call ``touch``
    after in-place edits.
    """

    __slots__ = (
        "_border",
        "_cursor_armed",
        "_glyphs",
        "_hover_row",
        "_last_layout",
        "_memo_generation",
        "_memo_layout",
        "_memo_natural",
        "_memo_natural_generation",
        "_memo_rows",
        "_memo_width",
        "_widths",
        "aligns",
        "cell_wrap",
        "disabled",
        "disabled_items",
        "headers",
        "marked",
        "max_col_width",
        "min_col_width",
        "rows",
    )

    #: The table owns the keyboard, clicks, the pointer's row and activation.
    focusable = True
    clickable = True
    hoverable = True
    activatable = True

    #: The family table plus the marking key.
    keymap = Keymap({**CURSOR_KEYMAP, "space": "toggle"})

    def __init__(
        self,
        rows: Iterable[
            Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment]
        ] = (),
        *,
        headers: Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment] = (),
        aligns: Sequence[str] | None = None,
        glyphs: Glyphs = GLYPHS,
        grid: Border | None = None,
        disabled: bool = False,
        disabled_items: Iterable[int] = (),
        theme: Theme | None = None,
        styles: Styles | None = None,
        cell_wrap: WrapMode = WrapMode.WORD,
        max_col_width: int | None = 40,
        min_col_width: int = 3,
    ) -> None:
        super().__init__(theme, styles)
        self.headers = list(headers)
        self.rows = [list(row) for row in rows]
        self.aligns = list(aligns) if aligns is not None else None
        #: How an over-long cell responds to its column budget: ``WORD`` /
        #: ``CHAR`` wrap the record, the single-row modes truncate it.
        self.cell_wrap = cell_wrap
        #: The wrapped policy's per-column cap (``None``: no cap) and floor.
        self.max_col_width = max_col_width
        self.min_col_width = min_col_width
        # The old constructor default; FocusManager/App may flip it later.
        self.focused = True
        self._glyphs = glyphs
        self._border = glyphs.grid if grid is None else grid
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`on_hover`).
        self.hover = False
        #: The marked data rows (:class:`~motui.widgets.mark.MarkSet`, raw
        #: row indices): :meth:`toggle` flips the cursor row's mark, and
        #: while the set is non-empty every data row leads with its
        #: ``[x] ``/``[ ] `` prefix.  The set is the host's to read, clear
        #: and fill; a sort re-points its indices at the records they were
        #: on (see :meth:`sort_by`).
        self.marked = MarkSet()
        # No cursor until a host (or a key) puts one there: a table without a
        # cursor renders exactly the bytes it always did.  ``index`` still
        # reads ``0`` (the empty table included) and ``selected`` the first
        # row; the render-only flag keeps the fresh grid unbanded.
        self._cursor_armed = False
        # The data row the pointer is on, or ``None``; written by
        # ``on_hover``, read by ``render``.  ``None`` renders byte-for-byte
        # what the table always did.
        self._hover_row: int | None = None
        #: The whole table refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The data rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)
        # Explicit column budgets (``set_widths``), or ``None`` for the
        # measured widths; read by ``_budgets`` on every render.
        self._widths: list[int] | None = None
        # The memory: the rows of the last grid while ``_memo_generation`` and
        # ``_memo_width`` still describe the table, and the natural widths
        # that grid was built from (their own slot, because ``header_line``
        # asks for the widths without rendering the grid).  ``None`` rows
        # mean "nothing remembered"; the generation is always an int here,
        # so the initial ``None`` keys are crossed by the row check.
        self._memo_rows: list[Line] | None = None
        self._memo_width: int | None = None
        self._memo_generation: object = None
        self._memo_natural: list[int] | None = None
        self._memo_natural_generation: object = None
        # The visual-row structure of the remembered grid (the memo's
        # companion) and the structure of the most recent render -- what
        # ``click``/``on_hover`` map a block row through.  ``None`` until a
        # render; the hit then reads the unwrapped one-line-per-record shape.
        self._memo_layout: list[_Slot] | None = None
        self._last_layout: list[_Slot] | None = None

    # -- the cursor hooks -------------------------------------------------------

    def _entry_count(self) -> int:
        return len(self.rows)

    def _entry_at(self, index: int) -> object | None:
        return self.rows[index]

    def _cursor_disabled(self) -> Iterable[int]:
        return self.disabled_items

    def _cursor_wraps(self) -> bool:
        """A data view clamps at its ends (D10); it never wraps."""
        return False

    def _cursor_enabled(self) -> bool:
        return not self.disabled

    # -- the cursor -------------------------------------------------------------

    def _arm(self) -> None:
        if not self._cursor_armed:
            self._cursor_armed = True
            self.touch()

    def select(self, index: int) -> bool:
        """Place the cursor and arm the render band (the host's door)."""
        self._arm()
        return super().select(index)

    def move(self, delta: int) -> bool:
        """Move the cursor and arm the render band (the keyboard's door)."""
        self._arm()
        return super().move(delta)

    def home(self) -> bool:
        """Jump to the first enabled row and arm the render band."""
        self._arm()
        return super().home()

    def end(self) -> bool:
        """Jump to the last enabled row and arm the render band."""
        self._arm()
        return super().end()

    def activate(self) -> bool:
        """Leave the cursor row pending; ``False`` without an armed cursor or on a disabled row."""
        if not self._cursor_armed:
            return False
        selected = self.selected
        if selected is None or not self.rows:
            return False
        index = self.index
        if self._is_disabled(index):
            return False
        self._emit(selected)
        return True

    def _is_disabled(self, index: int) -> bool:
        return self.disabled or index in self.disabled_items

    def on_click(self, pos: Pos) -> bool:
        """Place the cursor on the data row rendered at ``pos.y``; True on a hit.

        ``pos.x`` is ignored: a data row owns its whole width.  Frame rows
        and rows past the last rendered one answer ``False``.
        """
        if self.disabled:
            return False
        layout = self._hit_layout()
        if not 0 <= pos.y < len(layout):
            return False
        entry = layout[pos.y]
        if entry.data_row is None:  # a frame row: no data row to land on
            return False
        if self._is_disabled(entry.data_row):
            return False
        self.select(entry.data_row)
        return True

    def toggle(self) -> bool:
        """Flip the cursor row's mark; ``True`` when one flipped.

        Never emits; a disabled table or row refuses.
        """
        selected = self.selected
        if selected is None or not self.rows:
            return False
        index = self.index
        if self._is_disabled(index):
            return False
        self.marked.toggle(index)
        self.touch()
        return True

    def on_hover(self, pos: Pos | None) -> bool:
        """Mark the data row under the pointer; True when the marking changed.

        ``None`` clears it; frame rows carry no data.  ``pos.x`` is ignored.
        """
        target: int | None = None
        if pos is not None:
            layout = self._hit_layout()
            if 0 <= pos.y < len(layout):
                target = layout[pos.y].data_row
        changed = target != self._hover_row
        if changed:
            self._hover_row = target
            self.touch()
        return changed

    # -- the host's data gestures -------------------------------------------------

    def sort_by(self, col: int, *, reverse: bool = False) -> bool:
        """Reorder rows by column ``col``'s rendered text; True when the order moved.

        Stable; the cursor, pending result and marks follow their record,
        never the row number.  A bad column reads as the empty string.
        """
        if not self.rows:
            return False
        ncols = len(self.headers)
        keys = [
            _cell_text(row[col]) if 0 <= col < ncols and col < len(row) else ""
            for row in self.rows
        ]
        order = sorted(range(len(self.rows)), key=lambda i: keys[i], reverse=reverse)
        if order == list(range(len(self.rows))):
            return False
        # The permutation old-position -> new-position: the four positions
        # the table holds follow their record, and a position no row answers
        # (stale) stays where it is -- it keeps reading as "no row" either way.
        position = {old: new for new, old in enumerate(order)}
        self.rows[:] = [self.rows[i] for i in order]
        if self._cursor_armed:
            self._cursor.index = position.get(self._cursor.index, self._cursor.index)
        if self._hover_row is not None:
            self._hover_row = position.get(self._hover_row, self._hover_row)
        if len(self.marked):
            remapped = sorted({position.get(i, i) for i in self.marked})
            self.marked.clear()
            for index in remapped:  # the same MarkSet object, re-pointed in place
                self.marked.toggle(index)
        self.touch()
        return True

    def set_widths(self, widths: Sequence[int] | None) -> None:
        """Pin per-column cell budgets; ``None`` restores the measured widths.

        Budgets are clamped at render: at least one, shrunk proportionally
        when the total does not fit.
        """
        self._widths = None if widths is None else [int(w) for w in widths]
        self.touch()

    def header_lines(self, width: int) -> list[Line]:
        """Every header visual line, byte-identical to the grid's header at ``width``.

        An empty list without columns.
        """
        if not self.headers:
            return []
        header = [_cell_segments(h, self.group("text").muted) for h in self.headers]
        budgets = self._budgets(self._natural_widths(), width)
        lines = self._row_lines(
            header, budgets, self.group("borders").grid, self._aligns()
        )
        band = self.group("rows").base
        # OVERFLOW's header keeps the grid's natural width as well, so a
        # pinned header still lines up with the wider grid beneath it.
        line_width = width
        if self.cell_wrap is WrapMode.OVERFLOW:
            line_width = max(width, self._grid_width(width))
        return [rest(line, line_width, band) for line in lines]

    def header_line(self, width: int) -> Line | None:
        """The header row's first visual line, byte-identical to the grid's.

        ``None`` without headers.  A host pinning a wrapped header uses
        :meth:`header_lines`; the widget knows nothing of viewports.
        """
        lines = self.header_lines(width)
        return lines[0] if lines else None

    # -- the render ---------------------------------------------------------------

    def render(self, c: Constraints) -> Surface:
        """The grid at the constraint width, remembered while generation and width hold.

        A ``max_height`` budget truncates leading rows without invalidating
        the memo.  With ``OVERFLOW`` the surface is as wide as the natural
        grid for a scroll container.  The visual-row layout is recorded for
        hit mapping.
        """
        width = c.width
        build_width = width
        surface_width = width
        if self.cell_wrap is WrapMode.OVERFLOW:
            build_width = self._grid_width(width)
            surface_width = max(width, build_width)
        generation = self.generation
        rows = self._memo_rows
        if (
            rows is None
            or self._memo_width != build_width
            or self._memo_generation != generation
        ):
            rows, layout = self._grid(build_width)
            self._memo_generation = generation
            self._memo_width = build_width
            self._memo_rows = rows
            self._memo_layout = layout
        else:
            layout = self._memo_layout
            if layout is None:  # a memo from before the layout slot existed
                layout = self._layout(build_width)
        self._last_layout = layout
        rows = (
            rows[: c.max_height] if c.max_height is not None else list(rows)
        )
        if self.cell_wrap is WrapMode.OVERFLOW:
            return Surface.of(rows, surface_width, pad=False)
        return Surface.clipped(rows, c.width)

    def _grid_width(self, width: int) -> int:
        """The full frame width at ``width``; 0 for a headerless table (one blank row)."""
        ncols = len(self.headers)
        if ncols == 0:
            return 0
        budgets = self._budgets(self._natural_widths(), width)
        return sum(b + 2 for b in budgets) + ncols + 1

    def _mark_width(self) -> int:
        marked_glyph, unmarked_glyph = self._mark_pair()
        return max(seat_width(marked_glyph), seat_width(unmarked_glyph))

    def _mark_pair(self) -> tuple[str, str]:
        return self._glyphs.check_on, self._glyphs.check_off

    def _mark_seat(self, marked: bool) -> str:
        marked_glyph, unmarked_glyph = self._mark_pair()
        glyph, other = (
            (marked_glyph, unmarked_glyph)
            if marked
            else (unmarked_glyph, marked_glyph)
        )
        return pair_seat(glyph, other)

    def _grid(self, width: int) -> tuple[list[Line], list[_Slot]]:
        """Build the freshly banded grid at ``width``; the memo's miss path."""
        layout, lines = self._plan(width)
        cursor = self._cursor.index if self._cursor_armed else None
        hover = self._hover_row
        rows_style = self.group("rows")
        out: list[Line] = []
        for slot, line in zip(layout, lines, strict=True):
            if slot.data_row is None:  # a frame row or the blank empty row
                band = rows_style.base
            else:
                band = self._row_band(slot.data_row, cursor, hover)
            out.append(rest(line, width, band))
        return out, layout

    def _plan(self, width: int) -> tuple[list[_Slot], list[Line]]:
        """The visual-row structure at ``width`` and its un-banded lines.

        A record's ``row_rule`` follows its last visual line; the final rule
        is the frame's bottom.
        """
        ncols = len(self.headers)
        if ncols == 0:
            # No columns, no data rows: one blank line -- the single-entry
            # shape ``_layout`` reports for a headerless table.
            return [_Slot("empty", None, 0)], [Line()]
        aligns = self._aligns()
        border_style = self.group("borders").grid
        header = [_cell_segments(h, self.group("text").muted) for h in self.headers]
        data = self._data_cells(ncols)
        budgets = self._budgets(self._natural_widths(), width)
        layout: list[_Slot] = [_Slot("top", None, 0)]
        lines: list[Line] = [
            self._rule(
                budgets,
                self._border.top_left,
                self._border.top_tee,
                self._border.top_right,
                self._border.top,
                border_style,
            )
        ]
        for visual, line in enumerate(
            self._row_lines(header, budgets, border_style, aligns)
        ):
            layout.append(_Slot("header", None, visual))
            lines.append(line)
        layout.append(_Slot("header_rule", None, 0))
        lines.append(
            self._rule(
                budgets,
                self._border.middle_left,
                self._border.cross,
                self._border.middle_right,
                self._border.middle,
                border_style,
            )
        )
        for index in range(len(self.rows)):
            for visual, line in enumerate(
                self._row_lines(data[index], budgets, border_style, aligns)
            ):
                layout.append(_Slot(index, index, visual))
                lines.append(line)
            layout.append(_Slot("row_rule", None, 0))
            lines.append(
                self._rule(
                    budgets,
                    self._border.middle_left,
                    self._border.cross,
                    self._border.middle_right,
                    self._border.middle,
                    border_style,
                )
            )
        if self.rows:
            # The last row's rule is the frame's bottom.
            layout[-1] = _Slot("bottom", None, 0)
            lines[-1] = self._rule(
                budgets,
                self._border.bottom_left,
                self._border.bottom_tee,
                self._border.bottom_right,
                self._border.bottom,
                border_style,
            )
        else:
            layout.append(_Slot("bottom", None, 0))
            lines.append(
                self._rule(
                    budgets,
                    self._border.bottom_left,
                    self._border.bottom_tee,
                    self._border.bottom_right,
                    self._border.bottom,
                    border_style,
                )
            )
        return layout, lines

    def _data_cells(
        self, ncols: int
    ) -> list[list[tuple[list[Segment], Style]]]:
        """Every data record's normalized cells with the mark prefix on the first.

        The prefix sits at the head of the first cell so wrapping keeps it on
        the record's first visual line.
        """
        text = self.group("text")
        first_column_style = text.base
        disabled_style = text.faint
        marking = len(self.marked) > 0
        data: list[list[tuple[list[Segment], Style]]] = []
        for r, raw in enumerate(self.rows):
            row_disabled = self._is_disabled(r)
            cells: list[tuple[list[Segment], Style]] = []
            for i in range(ncols):
                cell = raw[i] if i < len(raw) else ""
                base = (
                    disabled_style
                    if row_disabled
                    else first_column_style if i == 0 else NONE
                )
                segments, cell_base = _cell_segments(cell, base)
                if marking and i == 0:
                    # The prefix takes the cell's own base, so the band the
                    # row pipeline lays underneath merges under it like under
                    # any cell run.  An empty pair seats nothing at all.
                    prefix = self._mark_seat(r in self.marked)
                    if prefix:
                        segments = [Segment(prefix, cell_base), *segments]
                cells.append((segments, cell_base))
            data.append(cells)
        return data

    def _row_lines(
        self,
        cells: list[tuple[list[Segment], Style]],
        budgets: list[int],
        border_style: Style,
        aligns: list[str],
    ) -> list[Line]:
        """One record's visual lines: one row, or a wrapped block under WORD/CHAR."""
        if self.cell_wrap not in (WrapMode.WORD, WrapMode.CHAR):
            return [self._row(cells, budgets, border_style, aligns)]
        return self._wrapped_row(cells, budgets, border_style, aligns)

    def _wrapped_row(
        self,
        cells: list[tuple[list[Segment], Style]],
        budgets: list[int],
        border_style: Style,
        aligns: list[str],
    ) -> list[Line]:
        """One record wrapped to ``budgets``: as many lines as its tallest cell.

        Every visual line keeps its own borders; shorter cells pad blank.
        """
        wrapped = [
            Line(segments).reflow(self.cell_wrap, budgets[i])
            for i, (segments, _) in enumerate(cells)
        ]
        height = max(len(lines) for lines in wrapped)
        out: list[Line] = []
        for visual in range(height):
            parts: list[Segment] = [Segment(self._border.left, border_style)]
            for i, (_, base) in enumerate(cells):
                line = wrapped[i][visual] if visual < len(wrapped[i]) else Line()
                parts.extend(
                    self._cell_parts(
                        list(line.segments), base, budgets[i], self.cell_wrap, aligns, i
                    )
                )
                parts.append(Segment(self._border.right, border_style))
            out.append(Line(parts))
        return out

    def _row_band(self, r: int, cursor: int | None, hover: int | None) -> Style:
        """The surface one data row rests on, resolved by the theme's row roles.

        Hover wins over cursor (D3); the header and grid rules never take the
        engaged band.
        """
        return self.group("rows").band(
            active=r == cursor,
            hovered=r == hover,
            focused=self.focused,
            disabled=self._is_disabled(r),
        )

    def _aligns(self) -> list[str]:
        return [a if a in _ALIGNS else "left" for a in (self.aligns or ())]

    def _natural_widths(self) -> list[int]:
        """Widest cell per column by text, remembered while ``generation`` holds.

        ``render`` and ``header_lines`` both read it, keeping their budgets
        and header bytes in step.
        """
        generation = self.generation
        widths = self._memo_natural
        if widths is None or self._memo_natural_generation != generation:
            widths = self._measure_widths()
            self._memo_natural_generation = generation
            self._memo_natural = widths
        return widths

    def _measure_widths(self) -> list[int]:
        ncols = len(self.headers)
        natural = [
            sum(visible_width(seg.text) for seg in segs)
            for segs, _ in (_cell_segments(h, self.group("text").muted) for h in self.headers)
        ]
        for raw in self.rows:
            for i in range(ncols):
                cell = raw[i] if i < len(raw) else ""
                natural[i] = max(
                    natural[i],
                    sum(visible_width(seg.text) for seg in _cell_segments(cell, NONE)[0]),
                )
        if natural and len(self.marked):
            # The first cell leads with the mark seat while anything is
            # marked: the column's budget grows by the pair's width, the
            # grid's frame stays one width (the rules follow the budgets).
            natural[0] += self._mark_width()
        return natural

    def _budgets(self, natural: list[int], width: int) -> list[int]:
        """Per-column cell budgets: pinned widths first, then the cell-wrap policy."""
        ncols = len(self.headers)
        pins = self._widths
        if pins is not None:
            natural = [
                max(1, pins[i]) if i < len(pins) else natural[i] for i in range(ncols)
            ]
        if self.cell_wrap is WrapMode.OVERFLOW:
            # OVERFLOW is uncapped by nature: the viewport and the wrapped
            # policy's max_col_width never shrink or cut a cell, so the
            # container can scroll to its real end.  Explicit ``set_widths``
            # pins (applied above) remain the host's own budgets.
            return list(natural)
        if self.cell_wrap in (WrapMode.WORD, WrapMode.CHAR):
            return _wrap_budgets(
                natural, width, ncols, self.max_col_width, self.min_col_width
            )
        # The rules take one column each (ncols + 1 of them), each column
        # another two for its padding.
        inner = width - (ncols + 1)
        if sum(w + 2 for w in natural) <= inner:
            return natural  # fits: keep the budgets, no stretch
        return _shrink(natural, inner - 2 * ncols)

    def _layout(self, width: int | None = None) -> list[_Slot]:
        """What each rendered visual row carries; ``width=None`` is the unwrapped shape."""
        if not self.headers:
            return [_Slot("empty", None, 0)]
        if width is None or self.cell_wrap not in (WrapMode.WORD, WrapMode.CHAR):
            return self._unwrapped_layout()
        return self._plan(width)[0]

    def _unwrapped_layout(self) -> list[_Slot]:
        layout: list[_Slot] = [
            _Slot("top", None, 0),
            _Slot("header", None, 0),
            _Slot("header_rule", None, 0),
        ]
        for index in range(len(self.rows)):
            layout.append(_Slot(index, index, 0))
            layout.append(_Slot("row_rule", None, 0))
        if self.rows:
            layout[-1] = _Slot("bottom", None, 0)
        else:
            layout.append(_Slot("bottom", None, 0))
        return layout

    def _hit_layout(self) -> list[_Slot]:
        layout = self._last_layout
        return layout if layout is not None else self._unwrapped_layout()

    def _row(
        self,
        cells: list[tuple[list[Segment], Style]],
        budgets: list[int],
        border_style: Style,
        aligns: list[str],
    ) -> Line:
        """One ``│ cell │ cell │`` row, every cell padded or clipped to its budget."""
        segments: list[Segment] = [Segment(self._border.left, border_style)]
        for i, (cell_segments, base) in enumerate(cells):
            segments.extend(
                self._cell_parts(
                    cell_segments, base, budgets[i], self.cell_wrap, aligns, i
                )
            )
            segments.append(Segment(self._border.right, border_style))
        return Line(segments)

    @staticmethod
    def _cell_parts(
        cell: list[Segment],
        base: Style,
        inner: int,
        mode: WrapMode,
        aligns: list[str],
        column: int,
    ) -> list[Segment]:
        line = Line(cell)
        # OVERFLOW's budget is the cell's natural width, so only an explicit
        # ``set_widths`` pin can make a cell over-wide: that pin is a hard
        # cut, never an ellipsis (the container owns the visible columns).
        if mode is WrapMode.OVERFLOW:
            fitted = line if line.width <= inner else line.clip(WrapMode.CLIP, inner)
        else:
            fitted = line if line.width <= inner else line.clip(mode, inner)
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
        left: str,
        cross: str,
        right: str,
        line: str,
        border_style: Style,
    ) -> Line:
        """A horizontal rule from the grid's ``Border``: ``┌──┬──┐`` and kin."""
        rule = left + cross.join(line * (b + 2) for b in budgets) + right
        return Line.from_text(rule, border_style)

    def __repr__(self) -> str:
        return f"Table({self.headers!r})"
