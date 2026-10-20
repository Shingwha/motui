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

**The row-band contract.**  Every row resolves its bands once, at
construction: ``_ground = _pick(ground_style, "ground")`` is the resting
surface and ``selected_style`` -- the band the cursor row's cells carry --
picks ``"ground_active"``, the engaged surface the hovered row's cells
wear as well (D2).  The selected row's cells carry the band *underneath*
their own styles (the W1 primitive, the Rich ``Padding(style=...)`` rule);
the resting rows -- the header and the grid rules included, which are
chrome rather than row bands and never take the engaged band -- rest on
the ground.  Every row grows to the full painting width, the surface a
grounded grid wears: the fill is skipped while the band is ``NONE`` (the
default theme's ground), so a resting row is then exactly the row it
always was, byte for byte, while the engaged row's band -- and any themed
ground -- spans the width, the registered default change.

The table can also carry a **row cursor**: ``index`` names a data row
(``None`` -- the default -- highlights nothing, so an unset table renders
byte-for-byte what a plain grid always did), the cursor row renders every
one of its data cells over the ``ground_active`` band (the reverse-video
band reads better on a data grid than an accent),
and ``move`` / ``click`` / ``activate`` are the interactive surface a host
routes keys and hits to.  ``move`` clamps at the ends (a data view, not a
menu cycle -- D10), ``click`` maps a block row onto a data row through the
very layout ``render`` emits, and ``activate`` lands the cursor row's index
in ``chosen`` for the host to read once.

The pointer tier adds a second, weaker highlight: ``hover_at(row, col)``
marks the data row a cell resolves to -- through the same layout, without
moving the cursor -- and that row's cells take the theme's
``ground_active``.  The marking starts ``None``, so an un-hovered table
renders exactly the bytes it always did.

**Marks are a third, sticky kind of emphasis.**  ``marked`` is the public
:class:`~motui.kernel.mark.MarkSet` of data-row indices and ``toggle()``
flips the cursor row's mark (the host routes the key it chooses -- the
library binds no gesture itself).  While the set is non-empty every data
row leads with the three-column ``[x] ``/``[ ] `` prefix
(:func:`~motui.kernel.mark.mark_prefix`) inside its first cell: the grid's
frame, its rules and its row count are untouched, column 0's natural width
grows by the prefix, and an **empty** mark set renders exactly the bytes
the table always did.  The marks are row inputs (they are part of
:meth:`Table.revision`), and a ``sort_by`` re-order re-points them at the
record they were on exactly as it re-points the cursor, ``chosen`` and the
pointer's mark.

The host also owns the two *data* gestures the grid itself never makes:
``sort_by(col, reverse=...)`` reorders the records by a column's rendered
text (stable, and the cursor, ``chosen`` and the pointer's mark follow the
record they were on -- never the row number), and ``set_widths(...)`` pins
per-column budgets (``None`` goes back to the measured widths; the render
clamps whatever does not fit).  ``header_line(width)`` is the third,
styling-free half: the header row *alone*, byte-identical to the grid's own,
for a host that pins it as a sticky row (the recipe is in the method's
docstring -- the widget knows nothing of viewports).

Only the kernel is imported; ``render`` is a pure function of the table and
``width``.  That is what makes the memory safe: while :meth:`Table.revision`
-- the value snapshot of every row input -- and the width hold still, the
remembered rows are exactly what a fresh render would answer, so
:meth:`Table.render` hands them back as a list copy instead of rebuilding
the grid.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ..kernel.lines import Line, Segment, fuse, overlay
from ..kernel.mark import MarkSet, mark_prefix
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from ..kernel.theme import Theme, Themed

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


def _cell_text(cell: str | tuple[str, Style] | Sequence[Segment] | Segment) -> str:
    """One cell's plain text -- styles dropped, the string the sort reads.

    The same four cell shapes :func:`_cell_segments` normalizes, measured
    for their text alone: ``str`` is itself, a ``(text, style)`` tuple (or a
    lone :class:`Segment`) yields its text and a ``Segment`` sequence its
    concatenation.  Used by :meth:`Table.sort_by`, which orders on the text
    a reader sees, never on the styles.
    """
    if isinstance(cell, Segment):
        return cell.text
    if isinstance(cell, tuple) and len(cell) == 2:
        return cell[0]
    if isinstance(cell, str):
        return cell
    return "".join(seg.text for seg in cell)


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
    cells, and the cursor row's data cells carry the ``ground_active``
    band underneath their own styles (default: the theme's
    ``ground_active``) while the header and the grid rules stay untouched;
    the row count and the column budgets are exactly the same whether a
    row is under the cursor or not.  ``move(delta)`` steps
    it and clamps at the ends, ``click(row, col)`` maps a rendered row onto
    a data row (``col`` is ignored: a data row owns its whole width), and
    ``activate()`` takes it into ``chosen`` -- the row index a host reads
    once, cleared by the next ``move`` or by a click that lands.
    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.block.Focusable`): while it is ``False`` the
    cursor band merges the theme's ``dim`` under it -- the band
    stays legible but loses weight, and every other row renders unchanged.

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.block.Hoverable`); :meth:`hover_at` marks the
    data row under the pointer -- resolved through the same row layout
    (:meth:`_layout`) :meth:`click` reads, without moving the cursor -- and
    that row's cells take the theme's ``ground_active`` under the band they
    already carry (the cursor's included: D2 shares the one token).  The
    marking starts ``None``, so an un-hovered table renders byte-for-byte
    what it always did.

    **Marking** is the third, sticky emphasis: :attr:`marked` is the public
    :class:`~motui.kernel.mark.MarkSet` of data-row indices and
    :meth:`toggle` flips the cursor row's mark (the host routes the key --
    the table binds none).  While the set is non-empty every data row leads
    with the ``[x] ``/``[ ] `` prefix inside its first cell; an empty set
    renders exactly the bytes the table always did, the frame and the row
    structure never change, and a :meth:`sort_by` re-order re-points the
    marks at their records like the cursor.

    Three host-facing extras ride beside that interactive face.
    :meth:`sort_by` reorders the data rows by one column's rendered text --
    stable, and the cursor, a pending ``chosen`` and the pointer's mark
    follow the *record* into its new position, never the row number -- while
    :meth:`set_widths` pins explicit per-column budgets (``None`` restores
    the measured ones) and :meth:`header_line` hands the header row out on
    its own, byte-identical to the grid's, for a host that pins it as a
    sticky row.  None of the three changes a default render: a table that
    is neither sorted, pinned nor header-stripped paints what it always did.

    **The memory.**  A grid render normalizes, bands, measures, pads and
    fuses every cell of every row -- 24 ms for a 240-row table -- and a host
    repaints the same table frame after frame (every mouse move repaints),
    so :meth:`render` remembers its last answer: while :meth:`revision` and
    the width are unchanged, the remembered rows come back as a list copy
    and the natural-width measurement they were built from rides in the
    same slot instead of being re-measured.  The snapshot copies the row
    and header **lists** (``tuple(map(tuple, self.rows))``): :attr:`rows`
    is the host's own list, and an in-place edit -- ``rows[i][j] = ...``,
    ``rows.append(...)``, ``headers[:] = ...`` -- must move the snapshot,
    where a snapshot holding the live list would compare equal to itself
    forever and the memory would freeze a table the host is editing.  A
    cell's own ``Segment`` list is the one level the copy does not reach
    (the block protocol names this shape as the canonical snapshot): a cell
    is a value in every documented use, and a host that mutates a segment
    list under a rendered table must assign the cell, which the snapshot
    sees.

    :meth:`revision` is the :class:`~motui.kernel.block.Revisioned` door:
    the block keys its own row cache on the same value, so a sealed
    table's hover finally reaches the screen (D4).
    """

    __slots__ = (
        "_border_style",
        "_dim",
        "_first_column_style",
        "_ground",
        "_header_style",
        "_hover_row",
        "_hover_style",
        "_index",
        "_memo_natural",
        "_memo_natural_revision",
        "_memo_revision",
        "_memo_rows",
        "_memo_width",
        "_selected_style",
        "_widths",
        "aligns",
        "chosen",
        "focused",
        "headers",
        "hover",
        "marked",
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
        ground_style: Style | None = None,
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
        #: The pointer tier's flag; the row-level emphasis lives in
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        #: The marked data rows (:class:`~motui.kernel.mark.MarkSet`, raw
        #: row indices): :meth:`toggle` flips the cursor row's mark, and
        #: while the set is non-empty every data row leads with its
        #: ``[x] ``/``[ ] `` prefix.  The set is the host's to read, clear
        #: and fill; a sort re-points its indices at the records they were
        #: on (see :meth:`sort_by`).
        self.marked = MarkSet()
        # No cursor until a host (or a key) puts one there: a table without a
        # cursor renders exactly the bytes it always did.
        self._index: int | None = None
        # The data row the pointer is on, or ``None``; written by
        # ``hover_at``, read by ``render``.  ``None`` renders byte-for-byte
        # what the table always did.
        self._hover_row: int | None = None
        # The pending activation: written by ``activate``, read once by the
        # host, cleared by ``move`` and by a click that lands.
        self.chosen: int | None = None
        # Explicit column budgets (``set_widths``), or ``None`` for the
        # measured widths; read by ``_budgets`` on every render.
        self._widths: list[int] | None = None
        # Styles resolve once, at construction: explicit > theme field > DEFAULT_THEME.
        self._header_style = (
            header_style if header_style is not None else DEFAULT_HEADER_STYLE
        )
        self._first_column_style = self._pick(first_column_style, "first_column")
        self._border_style = self._pick(border_style, "table_border")
        self._ground = self._pick(ground_style, "ground")
        self._selected_style = self._pick(selected_style, "ground_active")
        self._dim = self._pick(None, "dim")
        self._hover_style = self._pick(None, "hover")
        # The memory: the rows of the last grid while ``_memo_revision`` and
        # ``_memo_width`` still describe the table, and the natural widths
        # that grid was built from (their own slot, because ``header_line``
        # asks for the widths without rendering the grid).  ``None`` rows
        # mean "nothing remembered"; the revision never answers ``None``
        # (this component always has a snapshot), so the initial ``None``
        # keys are crossed by the row check, not by a snapshot value.
        self._memo_rows: list[Line] | None = None
        self._memo_width: int | None = None
        self._memo_revision: object = None
        self._memo_natural: list[int] | None = None
        self._memo_natural_revision: object = None

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
        exactly what :meth:`~motui.app.TUI.hit_test` reports -- and the
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

        The table's :class:`~motui.kernel.block.Activable` verb: a host
        routes the return key here, reads ``chosen`` once -- the data row's
        index -- and resets it to ``None``.  Answers whether there was a row
        to take: ``False``, with ``chosen`` ``None``, for an empty table or
        a cursor no current row answers.
        """
        self.chosen = self.index if self.selected is not None else None
        return self.chosen is not None

    def toggle(self) -> bool:
        """Flip the cursor row's mark; ``True`` when there was one to flip.

        The marking gesture beside the cursor's own -- the library binds no
        key to it, so the host routes ``space`` (or whatever it chooses)
        here.  The cursor row's mark flips in :attr:`marked` and nothing
        else moves: ``index``, ``chosen`` and the pointer's hover are the
        cursor's own state.  ``False`` -- and no mark written -- without a
        cursor (an empty table, or one no row has taken yet), exactly the
        ``Select.toggle`` rule.
        """
        if self.selected is None or self._index is None:
            return False
        self.marked.toggle(self._index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the data row under a rendered row; True when the marking changed.

        The pointer tier's row-level half (D3), and :meth:`click`'s mapping
        without its cursor move: ``row`` is a 0-based row of this
        component's own ``render`` output, resolved through the same row
        layout (:meth:`_layout`) -- a frame row (a rule, the header) carries
        no data and clears the marking, exactly as a row past the last
        rendered one does.  ``col`` is ignored like ``click``'s, and a
        negative ``row`` clears the marking (the pointer left).  The answer
        is whether the marked data row changed, so a motion inside one row
        answers ``False``; :meth:`render` rests that row's cells on the
        theme's ``ground_active`` band (the cursor row's included: D2
        shares the one token).
        """
        target: int | None = None
        if row >= 0:
            layout = self._layout()
            if 0 <= row < len(layout):
                entry = layout[row]
                if isinstance(entry, int):
                    target = entry
        changed = target != self._hover_row
        self._hover_row = target
        return changed

    # -- the host's data gestures -------------------------------------------------

    def sort_by(self, col: int, *, reverse: bool = False) -> bool:
        """Reorder the data rows by column ``col``'s rendered text; True on a change.

        The key is the column's **rendered text** (the plain string a reader
        sees: a cell's styles, its inline markup and its ellipsis play no
        part): the header row names the columns, so ``col`` is a data column
        index, and anything outside them -- a negative index, a column past
        the headers, a cell a short row leaves out -- reads as the empty
        string, which sorts first.  The sort is **stable** (the built-in
        ``list.sort`` rule): rows with equal keys keep their relative order,
        with ``reverse=True`` reversing the keys, not the ties.

        Row identity survives the reorder: the cursor (:attr:`index`), a
        pending :attr:`chosen`, the pointer's mark and the entries of
        :attr:`marked` are positions *into* the row list, and each is
        re-pointed at the record it was on -- the cursor stays on the same
        record wherever the record lands, the host's pending pick names the
        same row it always did, and a marked record stays marked.  A
        position no current row answers (a host swapped the rows out) is
        left untouched, exactly as it reads elsewhere.

        The table never sorts on its own -- there is no header-click magic,
        no cursor side effect, and a click on the header row still maps onto
        no data row.  A host calls this (from a header hit it resolved
        itself, from a sort control of its own) and the next :meth:`render`
        paints the new order; ``True`` says the order actually moved, so a
        no-op sort (every key equal) answers ``False``.
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
        if self._index is not None:
            self._index = position.get(self._index, self._index)
        if self._hover_row is not None:
            self._hover_row = position.get(self._hover_row, self._hover_row)
        if self.chosen is not None:
            self.chosen = position.get(self.chosen, self.chosen)
        if len(self.marked):
            remapped = sorted({position.get(i, i) for i in self.marked})
            self.marked.clear()
            for index in remapped:  # the same MarkSet object, re-pointed in place
                self.marked.toggle(index)
        return True

    def set_widths(self, widths: Sequence[int] | None) -> None:
        """Pin explicit per-column cell budgets; ``None`` restores the measured widths.

        ``widths`` is one budget per data column, in header order (a cell's
        columns of padding come on top of it, exactly as they do for a
        measured width).  The two rules that always held still hold: a
        column past the list keeps its measured width, and the render
        **clamps** -- a budget below one reads as one, and budgets whose
        total does not fit the painting width shrink proportionally, the
        same fallback an over-wide natural table takes.  So explicit widths
        are a *preference*, never an overflow: no row ever exceeds ``width``
        and the frame stays one width.

        The list is copied, so a caller's own list stays its own;
        ``set_widths(None)`` is the way back to the auto widths (the
        constructor state).
        """
        self._widths = None if widths is None else [int(w) for w in widths]

    def header_line(self, width: int) -> Line | None:
        """The header row alone, byte-identical to the grid's own; ``None`` without headers.

        The line :meth:`render` emits between its top rule and the header
        rule, at the same budgets: the natural widths are measured over the
        headers **and** the data rows (remembered between calls -- see
        :meth:`_natural_widths` -- which never changes the answer),
        :meth:`set_widths`' pinned budgets apply, and the fits/shrink clamp
        runs -- so the pinned line and the scrolled grid's header agree byte
        for byte, alignment pads and ellipsis included, at any width each is
        handed.  A table with no columns answers ``None``: its render is one
        blank row and there is no header to pin.

        Recipe -- a **sticky header**.  The table scrolls inside a pane; the
        host pins the header above it as its own one-row component::

            class StickyHeader:
                \"\"\"One row: the table's header, rendered at the pane's width.\"\"\"

                def __init__(self, table):
                    self.table = table

                def render(self, width):
                    line = self.table.header_line(width)
                    return [] if line is None else [line]

            tui.add(StickyHeader(table), pin="top")
            tui.add(table)                      # the grid scrolls under the pin

        The pinned row lines up with the grid because both read the same
        budgets.  There is deliberately **no viewport magic** in the widget:
        the host decides what to pin and when (the line is a value, taken
        fresh on every render).
        """
        if not self.headers:
            return None
        header = [_cell_segments(h, self._header_style) for h in self.headers]
        budgets = self._budgets(self._natural_widths(), width)
        return self._rest(
            self._row(header, budgets, self._border_style, self._aligns()),
            width,
            self._ground,
        )

    # -- the render ---------------------------------------------------------------

    def _revision(self) -> object:
        """The value snapshot of everything the grid's rows are made of.

        :attr:`rows` and :attr:`headers` go in as **copies** -- a tuple over
        a tuple of each row -- because they are the host's own mutable
        lists: the copy is what makes an in-place edit (a rewritten cell, an
        appended record, a swapped header list) move the snapshot, where
        comparing the live lists would compare the table to itself.  The
        pinned budgets, the alignments, the cursor, the pointer's mark, the
        focus flag and the seven resolved styles are row inputs and go in
        unchanged; they are values (or construction-time constants), so
        holding them is holding a copy.  The marks go in as
        ``tuple(self.marked)`` -- the set's ascending snapshot -- because
        the first cell's prefix is a row input like any other.  ``chosen``
        is deliberately **not** here: it never reaches a row, and the
        protocol's promise is about rows -- a snapshot moves when what the
        grid paints moves.

        The one level the copy does not reach is a cell that is itself a
        mutable ``Segment`` list: every documented cell shape is a value
        (``str``, ``(str, Style)``, a lone ``Segment``) and the copy the
        block protocol prescribes stops at the same depth.
        """
        widths = self._widths
        aligns = self.aligns
        return (
            tuple(map(tuple, self.rows)),
            tuple(self.headers),
            None if widths is None else tuple(widths),
            None if aligns is None else tuple(aligns),
            self._index,
            self._hover_row,
            tuple(self.marked),
            self.focused,
            self._header_style,
            self._first_column_style,
            self._border_style,
            self._ground,
            self._selected_style,
            self._dim,
            self._hover_style,
            self.theme,
        )

    def revision(self) -> object:
        """The :class:`~motui.kernel.block.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this
        component keys its own row cache on the same value, so a sealed
        table's hover -- or an in-place row edit -- invalidates the block's
        copy and this component's memory in one move.
        """
        return self._revision()

    def render(self, width: int) -> list[Line]:
        """The grid at ``width``, remembered while the snapshot holds.

        While the width and :meth:`_revision` are unchanged, the remembered
        rows of the last grid come back as a list copy -- no cell
        normalization, banding, measuring, padding or fusing (the
        component's memory, see the class docstring).  A miss builds the
        grid, remembers it together with its natural widths and moves the
        key; the returned list is always the caller's own.
        """
        revision = self._revision()
        rows = self._memo_rows
        if (
            rows is None
            or self._memo_width != width
            or self._memo_revision != revision
        ):
            rows = self._grid(width)
            self._memo_revision = revision
            self._memo_width = width
            self._memo_rows = rows
        return list(rows)

    def _grid(self, width: int) -> list[Line]:
        """The freshly built grid at ``width``: :meth:`render`'s miss path.

        The one place the row structure is assembled; :meth:`render` calls
        it only when the snapshot moved or the width changed, and never
        hands the list out itself (the memory keeps it).
        """
        aligns = self._aligns()
        ncols = len(self.headers)
        if ncols == 0:
            # No columns, no data rows: one blank line -- the single-entry
            # shape ``_layout`` reports for a headerless table.
            return [Line()]
        header = [_cell_segments(h, self._header_style) for h in self.headers]
        # The focus rule, once per render: an unfocused table dims its cursor
        # band, every other row keeps its own style untouched.
        selection = self._selected_style
        if not self.focused:
            selection = selection.merge(self._dim)
        cursor = self._index
        hover = self._hover_row
        # The mark column rides inside the first cell while anything is
        # marked; an empty set leaves every cell exactly as it was.
        marking = len(self.marked) > 0
        data: list[list[tuple[list[Segment], Style]]] = []
        for r, raw in enumerate(self.rows):
            cells: list[tuple[list[Segment], Style]] = []
            for i in range(ncols):
                cell = raw[i] if i < len(raw) else ""
                base = self._first_column_style if i == 0 else NONE
                segments, cell_base = _cell_segments(cell, base)
                if marking and i == 0:
                    # The prefix takes the cell's own base, so the band the
                    # row pipeline lays underneath merges under it like under
                    # any cell run.
                    segments = [Segment(mark_prefix(r in self.marked), cell_base), *segments]
                cells.append((segments, cell_base))
            data.append(cells)
        budgets = self._budgets(self._natural_widths(), width)
        # The row structure comes from ``_layout`` -- the one list ``click``
        # reads too -- so the two can never disagree about which row is what.
        out: list[Line] = []
        for entry in self._layout():
            if isinstance(entry, int):  # a data row, carrying its own index
                line = self._row(data[entry], budgets, self._border_style, aligns)
                band = self._row_band(entry, selection, cursor, hover)
            elif entry == "top":
                line, band = self._rule(budgets, _TOP_RULE, self._border_style), self._ground
            elif entry == "header":
                line = self._row(header, budgets, self._border_style, aligns)
                band = self._ground
            elif entry == "bottom":
                line, band = self._rule(budgets, _BOTTOM_RULE, self._border_style), self._ground
            else:  # "header_rule" / "row_rule": the same rule, twice over
                line, band = self._rule(budgets, _HEADER_RULE, self._border_style), self._ground
            out.append(self._rest(line, width, band))
        return out

    def _row_band(
        self, r: int, selection: Style, cursor: int | None, hover: int | None
    ) -> Style:
        """The surface one data row rests on: the ground, or the engaged band.

        The cursor row carries ``selection`` (``ground_active``, the theme's
        ``dim`` merged onto it while unfocused), the pointer's row
        ``_hover_style`` (the same token -- D2: the keyboard cursor and the
        hover share it), stacked where the two meet; every other data row
        rests on the ground.  The header and the grid rules are chrome:
        they rest on the ground and never take the engaged band.
        """
        if r != cursor and r != hover:
            return self._ground
        band = selection if r == cursor else self._hover_style
        if r == hover and r == cursor:
            band = band.merge(self._hover_style)
        return band

    def _rest(self, line: Line, width: int, band: Style) -> Line:
        """One grid row on its band: ``fit``, then the band under, full width.

        The row-band contract's rendering half, the Table reading: ``fit``
        trims to ``width``, then the band -- the ground on a resting row
        (the header and the rules included, so a grounded grid has no
        holes), the engaged band on the cursor's or the pointer's -- rests
        *underneath* every segment through the W1 primitive: the band the
        base, the row's own styles (the borders' ``table_border``, the
        cells' ``first_column``) riding on top with their colors winning.
        The row grows to the full painting width, the surface a grounded
        grid wears.  The fill is skipped when the band is ``NONE`` (the
        default theme's ground): a resting row is then exactly the row it
        always was, byte for byte, while the engaged row's band -- and any
        themed ground -- spans the width (the registered default change).
        ``header_line`` runs the very same row through it, which is what
        keeps the pinned header byte-identical to the grid's.
        """
        fitted = line.fit(width)
        return fitted if band == NONE else fitted.fill(width, band)

    def _aligns(self) -> list[str]:
        """The per-column alignments: a name outside ``_ALIGNS`` reads as left."""
        return [a if a in _ALIGNS else "left" for a in (self.aligns or ())]

    def _natural_widths(self) -> list[int]:
        """The widest cell of every column, headers and data rows alike, by text.

        The measuring rule of the constructor's docstring, in one place:
        ``_cell_segments`` normalizes each cell exactly as :meth:`render`
        will (the band merges never change a cell's text, so the widths are
        the same), and an empty cell a short row leaves out contributes
        zero.  :meth:`render` and :meth:`header_line` read it, which is what
        keeps their budgets -- and their header bytes -- in step.

        The answer is **remembered** while the table's :meth:`_revision`
        holds: the walk normalizes every cell of every row, and both
        callers ask for the very same widths frame after frame (a pinned
        header asks without rendering the grid at all), so a hit answers
        the remembered list without measuring.  Every input the walk reads
        -- the rows, the headers, the header style and the marks (the
        first column's cell carries the mark prefix) -- is part of the
        snapshot, so a hit is always the value a fresh walk would answer;
        the returned list is the memory's own, and every caller only reads
        it (``_budgets`` copies what it changes).
        """
        revision = self._revision()
        widths = self._memo_natural
        if widths is None or self._memo_natural_revision != revision:
            widths = self._measure_widths()
            self._memo_natural_revision = revision
            self._memo_natural = widths
        return widths

    def _measure_widths(self) -> list[int]:
        """The fresh measurement behind :meth:`_natural_widths`."""
        ncols = len(self.headers)
        natural = [
            sum(visible_width(seg.text) for seg in segs)
            for segs, _ in (_cell_segments(h, self._header_style) for h in self.headers)
        ]
        for raw in self.rows:
            for i in range(ncols):
                cell = raw[i] if i < len(raw) else ""
                natural[i] = max(
                    natural[i],
                    sum(visible_width(seg.text) for seg in _cell_segments(cell, NONE)[0]),
                )
        if natural and len(self.marked):
            # The first cell leads with the mark prefix while anything is
            # marked: the column's budget grows by it, the grid's frame
            # stays one width (the rules follow the budgets).
            natural[0] += visible_width(mark_prefix(False))
        return natural

    def _budgets(self, natural: list[int], width: int) -> list[int]:
        """The per-column cell budgets at ``width``: explicit widths, then the clamp.

        ``set_widths``' pinned budgets replace the measured ones column by
        column (a column past the pinned list keeps its measured width, a
        pinned value below one reads as one); the fits/shrink rule of the
        module docstring then runs exactly as it does for measured widths --
        a total that fits keeps the budgets (never stretched), a total that
        does not shrinks proportionally, floored at one column each.
        """
        ncols = len(self.headers)
        pins = self._widths
        if pins is not None:
            natural = [
                max(1, pins[i]) if i < len(pins) else natural[i] for i in range(ncols)
            ]
        # The rules take one column each (ncols + 1 of them), each column
        # another two for its padding.
        inner = width - (ncols + 1)
        if sum(w + 2 for w in natural) <= inner:
            return natural  # fits: keep the budgets, no stretch
        return _shrink(natural, inner - 2 * ncols)

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
