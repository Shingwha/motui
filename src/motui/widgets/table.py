"""Table component: a box-drawing grid of styled cells.

:class:`Table` renders a full box frame around the grid: a top rule
``┌─┬─┐``, the header row, the separator rule ``├─┼─┤`` and a bottom rule
``└─┴─┘``, with the data rows in between and one ``├─┼─┤`` rule between
every two rows -- a full grid (an empty body leaves the frame alone).  A
column's natural width is the widest cell in it (header included) plus one
padding cell per side.

Two width policies share that frame.  ``cell_wrap`` (``WrapMode.WORD`` by
default) selects how an over-long cell responds to its budget.  ``WORD`` and
``CHAR`` cap the natural widths at ``max_col_width``, floor them at
``min_col_width`` and, when the capped total still exceeds ``width``, shrink
the budgets proportionally above the floor; every cell then wraps inside its
budget (``Line.reflow`` keeps each ``Segment``, its ``link`` and its
``action``) -- a record as tall as its tallest cell, a rule only under its
last visual line, and the mark prefix on its first visual line alone.
``ELLIPSIS`` and ``CLIP`` keep the old one-row policy byte for byte: no cap,
no floor beyond one column, and over-long cells are ellipsized or hard-cut.
``OVERFLOW`` keeps the grid's natural width -- every column takes its widest
cell (capped by an explicit ``max_col_width``) no matter how narrow the
constraints are -- and the frame, its rules and its header are all generated
at that width, so the answer is a surface wider than ``Constraints.width``
for a scroll container to window.  Below ``width`` the grid keeps its
natural size: the right edge is never stretched.

Cells are ``str``, ``(str, Style)`` or ``Sequence[Segment]``.  ``str`` and
tuple cells normalize to a single segment (a tuple's style replaces the
cell's default, padding spaces included); a ``Segment`` list keeps its
styles -- an attribute-only segment (fg and bg both unset) is merged onto
the cell's base style, a colored segment stays absolute, the same rule
the Markdown inline engine applies.  The base style is ``text.muted`` on
the header row and ``text.base`` on data rows' first column
(``NONE`` elsewhere).  ``aligns`` gives each column's alignment
(``left`` / ``center`` / ``right``; anything else, and any column past
the list, reads as left) and is applied with pad segments inside the
column budget.  All rows of one table share exactly one width (frame
consistency); each is still clipped to ``width`` as a final guard.

The grid lines use ``borders.grid`` (uncolored by default, which reads
cleanest on any background); a ``styles=`` override can tint them.

**The row-band contract.**  Every row resolves its band through the theme's
:class:`~motui.kernel.theme.RowStyles`: ``base`` is the resting surface,
``active`` -- the band the cursor row's cells carry -- ``rows.active``,
``hover`` the pointer's row hover token (``rows.hover``) and ``disabled``
the ``text.faint`` token.  The selected row's
cells carry the band *underneath* their own styles (the W1 primitive, the
Rich ``Padding(style=...)`` rule); the resting rows -- the header and the
grid rules included, which are chrome rather than row bands and never take
the engaged band -- rest on the ground.  Every row's band merges under that
row's own cells -- a pill behind the grid, never a ribbon across the pane;
a full-surface band is the host's container's job
(``Padding(fill_style=...)`` / ``Panel(frame=False, style=...)``, which
fill every row to the width they are handed).  The fill is skipped while
the band is ``NONE`` (the default theme's ground and both its engaged
bands), so a resting row is then exactly the row it always was, byte for
byte, while any themed ground -- or a themed engaged band -- covers the
row's own cells.

The table can also carry a **row cursor**: ``index`` names a data row
(``None`` -- the default -- highlights nothing, so an unset table renders
byte-for-byte what a plain grid always did), the cursor row renders every
one of its data cells over the ``rows.active`` band (the reverse-video
band reads better on a data grid than an accent),
and ``move`` / ``click`` / ``activate`` are the interactive surface a host
routes keys and hits to.  ``move`` clamps at the ends (a data view, not a
menu cycle -- D10), ``click`` maps a block row onto a data row through the
very layout ``render`` emits, and ``activate`` leaves the cursor row's index
pending for :meth:`take_result` (read once, self-clearing).

The pointer tier adds a second, weaker highlight: ``hover_at(row, col)``
marks the data row a cell resolves to -- through the same layout, without
moving the cursor -- and that row's cells take the row hover band
(``rows.hover``), whatever row it is on (D3: the hover wins even over the
cursor's).
The marking starts ``None``, so an un-hovered table renders exactly the
bytes it always did.

**Marks are a third, sticky kind of emphasis.**  ``marked`` is the public
:class:`~motui.widgets.mark.MarkSet` of data-row indices and ``toggle()``
flips the cursor row's mark (the host routes the key it chooses -- the
library binds no gesture itself).  While the set is non-empty every data
row leads with its ``glyphs.check_on``/``check_off`` seat inside its first cell -- one pair-wide column,
padded through :func:`~motui.kernel.glyphs.pair_seat` -- so a custom pair
of unequal widths still lines up, and two empty strings collapse the column
to zero.  The grid's frame, its rules and its row count are untouched,
column 0's natural width grows by the pair, and an **empty** mark set
renders exactly the bytes the table always did.  The marks are row inputs
(they are part of :meth:`Table.revision`), and a ``sort_by`` re-order
re-points them at the record they were on exactly as it re-points the
cursor, the pending result and the pointer's mark.

The host also owns the two *data* gestures the grid itself never makes:
``sort_by(col, reverse=...)`` reorders the records by a column's rendered
text (stable, and the cursor, a pending result and the pointer's mark follow
the record they were on -- never the row number), and ``set_widths(...)`` pins
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
from typing import NamedTuple

from ..widgets.cursor import Cursor
from ..kernel.glyphs import GLYPHS, Border, Glyphs, pair_seat, seat_width
from ..kernel.cell import Line, Segment, Surface, fuse, overlay, rest
from ..kernel.layout import Constraints
from ..widgets.mark import MarkSet
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode, visible_width
from ..kernel.theme import Styles, Theme
from ..widgets.base import Widget

__all__ = ["Table"]

#: Accepted per-column alignment names; anything else reads as left.
_ALIGNS = ("left", "center", "right")


class _Slot(NamedTuple):
    """One rendered visual row: its kind, its data row, its visual line.

    ``kind`` is a data-row index for a body row or a frame token (``"top"``,
    ``"header"``, ``"header_rule"``, ``"row_rule"``, ``"bottom"``,
    ``"empty"``); ``data_row`` is the :attr:`Table.rows` index a body row
    carries (``None`` for frame rows), and ``visual_line`` is the row's
    0-based visual line -- 0 for every frame row and for an unwrapped body.
    """

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
    """The wrapped table's per-column content budgets at ``width``.

    The natural widths are capped at ``max_col_width`` (``None`` -- no cap)
    and floored at ``min_col_width``.  When the floored total does not fit
    the content columns left by the frame and the per-cell padding, the
    budget shrinks proportionally to the capped widths, never below the
    floor; a width too narrow even for the floors degenerates to an equal
    share of at least one column per column.
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


class Table(Widget):
    """A box-line table of string, styled, or multi-segment cells.

    ``headers`` names the columns; ``rows`` holds the records (a short row
    is padded with empty cells, a long row is truncated at the last
    header).  Column widths follow the width policy above: ``cell_wrap``
    (``WrapMode.WORD`` by default) caps at ``max_col_width``, floors at
    ``min_col_width`` and wraps over-long cells, while ``ELLIPSIS`` /
    ``CLIP`` keep the old natural/shrink/truncate behavior byte for byte
    (``OVERFLOW`` keeps the natural grid width for a horizontal scroll
    container).  The
    header row always uses ``text.muted``, and ``text.base`` only touches
    data rows' first column.  ``aligns`` aligns
    each column (``left`` / ``center`` / ``right``, default left).  Grid
    lines use ``borders.grid`` (uncolored by default), and one ``├─┼─┤``
    rule separates every two data rows.
    Styles resolve at render time from the theme (or a ``styles=`` group
    override): ``text``, ``borders`` and ``rows`` are read through
    :meth:`~motui.widgets.base.Widget.group`, and ``theme``/``styles`` are
    part of :meth:`revision`, so a theme switch repaints a mounted table.

    The optional row cursor is the table's interactive face: ``index`` is
    the data row under it (``None`` -- the default, and the empty table's
    only value -- highlights nothing), ``selected`` reads that row's raw
    cells, and the cursor row's data cells carry the ``rows.active``
    band underneath their own styles
    while the header and the grid rules stay untouched;
    the row count and the column budgets are exactly the same whether a
    row is under the cursor or not.  ``move(delta)`` steps
    it and clamps at the ends, ``click(row, col)`` maps a rendered row onto
    a data row (``col`` is ignored: a data row owns its whole width), and
    ``activate()`` leaves it pending for :meth:`take_result` -- the row
    index a host reads once, cleared by the next ``move`` or by a click
    that lands.
    ``focused`` is the focus flag the focus tier sets
    (:class:`~motui.kernel.document.Focusable`): while it is ``False`` the
    cursor row wears ``rows.inactive`` instead -- the band stays legible
    but loses weight, and every other row renders unchanged.  It starts
    ``True``, the old constructor default.

    ``hover`` is the pointer tier's flag
    (:class:`~motui.kernel.document.Hoverable`); :meth:`hover_at` marks the
    data row under the pointer -- resolved through the same row layout
    (:meth:`_layout`) :meth:`click` reads, without moving the cursor -- and
    that row's cells take the row hover band under the band they
    already carry (the cursor's included: D3's precedence makes the hover
    win outright, so a hovered cursor row wears the hover band alone).  The
    marking starts ``None``, so an un-hovered table renders byte-for-byte
    what it always did.

    **Marking** is the third, sticky emphasis: :attr:`marked` is the public
    :class:`~motui.widgets.mark.MarkSet` of data-row indices and
    :meth:`toggle` flips the cursor row's mark (the host routes the key --
    the table binds none).  While the set is non-empty every data row leads
    with its ``glyphs.check_on``/``check_off`` seat inside its first cell; the column is the pair's wider
    seat, so a custom pair lines up, and an empty pair (two ``""``)
    collapses it to zero columns.  An empty set renders exactly the bytes
    the table always did, the frame and the row
    structure never change, and a :meth:`sort_by` re-order re-points the
    marks at their records like the cursor.

    Three host-facing extras ride beside that interactive face.
    :meth:`sort_by` reorders the data rows by one column's rendered text --
    stable, and the cursor, a pending result and the pointer's mark
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

    :meth:`revision` is the :class:`~motui.kernel.document.Revisioned` door:
    the block keys its own row cache on the same value, so a sealed
    table's hover finally reaches the screen (D4).
    """

    __slots__ = (
        "_glyphs",
        "_border",
        "_hover_row",
        "_index",
        "_last_layout",
        "_memo_layout",
        "_memo_natural",
        "_memo_natural_revision",
        "_memo_revision",
        "_memo_rows",
        "_memo_width",
        "_pending",
        "_widths",
        "aligns",
        "disabled",
        "disabled_items",
        "headers",
        "marked",
        "max_col_width",
        "min_col_width",
        "rows",
        "cell_wrap",
    )

    def __init__(
        self,
        headers: Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment],
        rows: Iterable[
            Iterable[str | tuple[str, Style] | Sequence[Segment] | Segment]
        ],
        *,
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
        #: ``_hover_row`` (:meth:`hover_at`).
        self.hover = False
        #: The marked data rows (:class:`~motui.widgets.mark.MarkSet`, raw
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
        #: The whole table refuses every cursor gesture when disabled.
        self.disabled = disabled
        #: The data rows that cannot be landed on (a frozen set: assign a
        #: new iterable to replace it).
        self.disabled_items = frozenset(disabled_items)
        # The pending activation: written by ``activate``, read once by
        # ``take_result``, cleared by ``move`` and by a click that lands.
        self._pending: int | None = None
        # Explicit column budgets (``set_widths``), or ``None`` for the
        # measured widths; read by ``_budgets`` on every render.
        self._widths: list[int] | None = None
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
        # The visual-row structure of the remembered grid (the memo's
        # companion) and the structure of the most recent render -- what
        # ``click``/``hover_at`` map a block row through.  ``None`` until a
        # render; the hit then reads the unwrapped one-line-per-record shape.
        self._memo_layout: list[_Slot] | None = None
        self._last_layout: list[_Slot] | None = None

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
            self._index = Cursor(len(self.rows)).clamp(value)

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
        """Move the cursor ``delta`` enabled data rows, clamped at the ends.

        The clamp is deliberate, and the opposite of the menu family's
        default: a menu is an *option list* -- its ends meet, so a step off
        one row lands on the other -- while a table is a *data view*: the
        first and the last data row are real edges, and a step past one
        stops there (D10).  ``disabled_items`` are stepped over, and a
        disabled table moves nowhere.  With no cursor yet, a step lands on
        the edge it walks away from: ``down`` puts it on the first enabled
        data row, ``up`` on the last.  ``False`` (and still no cursor)
        without rows or an enabled landing, and ``False`` for a step that
        goes nowhere -- which still clears a pending result, so a stale pick
        never survives the next keystroke.
        """
        self._pending = None
        if self.disabled or delta == 0:
            return False
        count = len(self.rows)
        if count == 0:
            return False
        step = 1 if delta > 0 else -1
        if self._index is None:
            # No cursor yet: the step lands on the edge it walks away from,
            # skipping disabled rows.  A sentinel index one past the edge
            # makes the edge jump report whether any enabled row exists.
            cursor = Cursor(
                count,
                index=-1 if step > 0 else count,
                disabled=self.disabled_items,
            )
            landed = cursor.home() if step > 0 else cursor.end()
            if not landed:
                return False  # every row is disabled
            self._index = cursor.index
            return True
        cursor = Cursor(
            count,
            index=self._index,
            disabled=self.disabled_items,
        )
        moved = cursor.move(delta)
        self._index = cursor.index
        return moved

    def _is_disabled(self, index: int) -> bool:
        """Whether data row ``index`` is disabled (the table or per item)."""
        return self.disabled or index in self.disabled_items

    def click(self, row: int, col: int) -> bool:
        """Place the cursor on the data row rendered at block row ``row``; True on a hit.

        ``row`` is a 0-based row of this component's own ``render`` output --
        exactly what :meth:`~motui.app.TUI.hit` reports -- and the
        mapping back onto a data row comes from the **most recent render's**
        visual-row structure (:meth:`_layout`): the top rule, the header
        (every visual line of it) and every ``├─┼─┤`` rule carry no data,
        while every visual line of a wrapped record maps onto that record.
        The mapping follows the rendered structure wherever it goes -- a
        shrunk or wrapped cell, a header that takes more room than the body:
        the layout is read off the same shape ``render`` emits.  A row that
        carries no data -- the frame rows, and every row past the last
        rendered one -- answers ``False`` and changes nothing.  ``col`` is
        ignored, and deliberately so: every column of a data row belongs to
        that row, so no column narrows the hit.  A hit moves the cursor
        there (even when it already was) and clears a pending result; a
        disabled table or data row refuses the hit.
        """
        if self.disabled:
            return False
        layout = self._hit_layout()
        if not 0 <= row < len(layout):
            return False
        entry = layout[row]
        if entry.data_row is None:  # a frame row: no data row to land on
            return False
        if self._is_disabled(entry.data_row):
            return False
        self._index = entry.data_row
        self._pending = None
        return True

    def activate(self) -> bool:
        """Leave the data row under the cursor pending; True when there was one.

        The table's :class:`~motui.kernel.document.Activable` verb: a host
        routes the return key here and reads the result once through
        :meth:`take_result` -- the data row's index.  Answers whether there
        was a row to take: ``False``, with nothing pending, for an empty
        table, a disabled table or row, or a cursor no current row answers.
        """
        if self.disabled or self.selected is None or self._index is None:
            self._pending = None
            return False
        if self._is_disabled(self._index):
            self._pending = None
            return False
        self._pending = self._index
        return True

    def take_result(self) -> int | None:
        """Read the pending row index once and clear it (the ``Resultful`` door)."""
        value = self._pending
        self._pending = None
        return value

    def toggle(self) -> bool:
        """Flip the cursor row's mark; ``True`` when there was one to flip.

        The marking gesture beside the cursor's own -- the library binds no
        key to it, so the host routes ``space`` (or whatever it chooses)
        here.  The cursor row's mark flips in :attr:`marked` and nothing
        else moves: ``index``, the pending result and the pointer's hover
        are the cursor's own state.  ``False`` -- and no mark written --
        without a cursor (an empty table, or one no row has taken yet), on a
        disabled row or table, exactly the ``Select.toggle`` rule.
        """
        if self.selected is None or self._index is None:
            return False
        if self._is_disabled(self._index):
            return False
        self.marked.toggle(self._index)
        return True

    def hover_at(self, row: int, col: int) -> bool:
        """Mark the data row under a rendered row; True when the marking changed.

        The pointer tier's row-level half (D3), and :meth:`click`'s mapping
        without its cursor move: ``row`` is a 0-based row of this
        component's own ``render`` output, resolved through the same
        most-recent-render visual-row structure (:meth:`_layout`) -- a frame
        row (a rule, any header visual line) carries no data and clears the
        marking, exactly as a row past the last rendered one does.  Every
        visual line of a wrapped record maps onto that record.  ``col`` is
        ignored like ``click``'s, and a negative ``row`` clears the marking
        (the pointer left).  The answer is whether the marked data row
        changed, so a motion inside one record answers ``False``;
        :meth:`render` rests that row's cells -- every visual line of them
        -- on the row hover band (the cursor row's included: D3's
        precedence makes the hover win outright).
        """
        target: int | None = None
        if row >= 0:
            layout = self._hit_layout()
            if 0 <= row < len(layout):
                target = layout[row].data_row
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
        pending result, the pointer's mark and the entries of
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
        if self._pending is not None:
            self._pending = position.get(self._pending, self._pending)
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

    def header_lines(self, width: int) -> list[Line]:
        """Every header visual line, byte-identical to the grid's own header.

        The wrapped header can take several visual lines; each is built at
        the same budgets and alignment pads as :meth:`render` uses, so the
        list is the grid's header block exactly.  A table with no columns
        answers an empty list: its render is one blank row and there is no
        header to pin.  With a single-row ``cell_wrap`` this is the old
        header row.
        """
        if not self.headers:
            return []
        header = [_cell_segments(h, self.group("text").muted) for h in self.headers]
        budgets = self._budgets(self._natural_widths(), width)
        lines = self._row_lines(
            header, budgets, self.group("borders").grid, self._aligns()
        )
        band = self.group("rows").base
        return [rest(line, width, band) for line in lines]

    def header_line(self, width: int) -> Line | None:
        """The header row's first visual line, byte-identical to the grid's; ``None`` without headers.

        The single-line compatibility view of :meth:`header_lines`: the
        line :meth:`render` emits right after its top rule, at the same
        budgets and alignment pads.  A wrapped header hands back its first
        visual line; a host that pins the whole header asks for
        :meth:`header_lines`.  A table with no columns answers ``None``.

        Recipe -- a **sticky header**.  The table scrolls inside a pane; the
        host pins the header above it as its own component::

            class StickyHeader:
                \"\"\"The table's header, rendered at the pane's width.\"\"\"

                def __init__(self, table):
                    self.table = table

                def render(self, c):
                    return Surface.clipped(self.table.header_lines(c.width), c.width)

            tui.add(StickyHeader(table), pin="top")
            tui.add(table)                      # the grid scrolls under the pin

        The pinned rows line up with the grid because both read the same
        budgets.  There is deliberately **no viewport magic** in the widget:
        the host decides what to pin and when (the lines are values, taken
        fresh on every render).
        """
        lines = self.header_lines(width)
        return lines[0] if lines else None

    # -- the render ---------------------------------------------------------------

    def _revision(self) -> object:
        """The value snapshot of everything the grid's rows are made of.

        :attr:`rows` and :attr:`headers` go in as **copies** -- a tuple over
        a tuple of each row -- because they are the host's own mutable
        lists: the copy is what makes an in-place edit (a rewritten cell, an
        appended record, a swapped header list) move the snapshot, where
        comparing the live lists would compare the table to itself.  The
        pinned budgets, the alignments, the cursor, the pointer's mark, the
        focus and disabled flags, the disabled item set, the theme and the
        ``styles`` overrides (the roles resolve from them at render time)
        are row inputs and go in unchanged; they are values
        (or construction-time constants), so holding them is holding a
        copy.  The marks go in as
        ``tuple(self.marked)`` -- the set's ascending snapshot -- because
        the first cell's prefix is a row input like any other.  The glyph
        vocabulary the prefix is drawn from is a row input too, and so are
        the rest.  The pending result
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
            (self._glyphs.check_on, self._glyphs.check_off),
            self._border,
            self.focused,
            self.disabled,
            tuple(sorted(self.disabled_items)),
            self.cell_wrap,
            self.max_col_width,
            self.min_col_width,
            self.theme,
            self.styles,
        )

    def revision(self) -> object:
        """The :class:`~motui.kernel.document.Revisioned` snapshot.

        The protocol's door to :meth:`_revision`: a block holding this
        component keys its own row cache on the same value, so a sealed
        table's hover -- or an in-place row edit -- invalidates the block's
        copy and this component's memory in one move.
        """
        return self._revision()

    def render(self, c: Constraints) -> Surface:
        """The grid at the constraint width, remembered while the snapshot holds.

        With ``OVERFLOW`` the natural grid width -- the width the cells'
        own content asks for -- is the painting width whenever it exceeds
        ``c.width``, and the frame, the rules and every row are built at
        that width; the surface then carries it so a horizontal scroll
        container can window it.  The width memo keys on that build width,
        so a pane resize below the natural width re-uses the one grid.  A
        ``max_height`` budget
        truncates the leading grid rows, so a table inside a shorter pane
        never paints past its slot.  The budget is deliberately not part of
        the memory's key: the full grid at the width is remembered once and
        every budget slices the same rows, so alternating budgets cannot
        thrash the build.

        While the width and :meth:`_revision` are unchanged, the remembered
        rows of the last grid come back as a list copy -- no cell
        normalization, banding, measuring, wrapping, padding or fusing (the
        component's memory, see the class docstring).  A miss builds the
        grid, remembers it together with its natural widths and visual-row
        layout and moves the key; the returned rows are always the caller's
        own.  Either way the visual-row layout is recorded for
        :meth:`click` / :meth:`hover_at` -- the last render's full layout,
        which also describes the untruncated rows a host may have pinned.
        """
        width = c.width
        build_width = width
        if self.cell_wrap is WrapMode.OVERFLOW:
            build_width = max(width, self._grid_width(width))
        revision = self._revision()
        rows = self._memo_rows
        if (
            rows is None
            or self._memo_width != build_width
            or self._memo_revision != revision
        ):
            rows, layout = self._grid(build_width)
            self._memo_revision = revision
            self._memo_width = build_width
            self._memo_rows = rows
            self._memo_layout = layout
        else:
            layout = self._memo_layout
            if layout is None:  # a memo from before the layout slot existed
                layout = self._layout(build_width)
        self._last_layout = layout
        if c.max_height is not None:
            rows = rows[: c.max_height]
        else:
            rows = list(rows)
        if self.cell_wrap is WrapMode.OVERFLOW:
            return Surface.of(rows, build_width, pad=False)
        return Surface.clipped(rows, c.width)

    def _grid_width(self, width: int) -> int:
        """The full frame width at ``width`` under the current cell policy.

        The rules take one column each (``ncols + 1``) and every column two
        padding cells; the budgets are the policy's (for ``OVERFLOW`` the
        natural widths, whatever ``width`` is).  An empty table has no
        frame: one blank row is its whole render.
        """
        ncols = len(self.headers)
        if ncols == 0:
            return 0
        budgets = self._budgets(self._natural_widths(), width)
        return sum(b + 2 for b in budgets) + ncols + 1

    def _mark_width(self) -> int:
        """The mark column's width: the pair's wider seat in display columns."""
        marked_glyph, unmarked_glyph = self._mark_pair()
        return max(seat_width(marked_glyph), seat_width(unmarked_glyph))

    def _mark_pair(self) -> tuple[str, str]:
        """The ``(marked, unmarked)`` pair the first cell's marks are drawn from."""
        return self._glyphs.check_on, self._glyphs.check_off

    def _mark_seat(self, marked: bool) -> str:
        """One row's mark seat, padded to the pair's wider member."""
        marked_glyph, unmarked_glyph = self._mark_pair()
        glyph, other = (
            (marked_glyph, unmarked_glyph)
            if marked
            else (unmarked_glyph, marked_glyph)
        )
        return pair_seat(glyph, other)

    def _grid(self, width: int) -> tuple[list[Line], list[_Slot]]:
        """The freshly built grid at ``width``: :meth:`render`'s miss path.

        The one place the row structure is assembled; :meth:`render` calls
        it only when the snapshot moved or the width changed, and never
        hands the list out itself (the memory keeps it).  The visual-row
        layout comes back beside the lines so the memory -- and the hit
        mapping -- see the very structure this grid emitted.
        """
        layout, lines = self._plan(width)
        cursor = self._index
        hover = self._hover_row
        rows_style = self.group("rows")
        out: list[Line] = []
        for slot, line in zip(layout, lines):
            if slot.data_row is None:  # a frame row or the blank empty row
                band = rows_style.base
            else:
                band = self._row_band(slot.data_row, cursor, hover)
            out.append(rest(line, width, band))
        return out, layout

    def _plan(self, width: int) -> tuple[list[_Slot], list[Line]]:
        """The visual-row structure at ``width`` and its un-banded lines.

        One entry per visual line: the frame rows and every visual line of a
        (possibly wrapped) header record and data record.  A record's
        ``row_rule`` follows its **last** visual line; the final rule is the
        frame's bottom.  A single-row ``cell_wrap`` gives every record
        exactly one visual line, so the structure -- and every line's bytes
        -- is the old one.
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
        """Every data record's normalized cells, mark prefix included.

        ``text.base`` touches the first column, ``text.faint`` a disabled
        row and ``NONE`` every other cell; while anything is marked the
        first cell leads with its seat.  The prefix lives at the head of the
        cell's segments, which is what keeps it on the record's first visual
        line once the cell wraps.
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
                if row_disabled:
                    base = disabled_style
                else:
                    base = first_column_style if i == 0 else NONE
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
        """One record's visual lines: one row, or the wrapped block.

        ``WORD`` and ``CHAR`` take the wrapping policy; the single-row
        modes keep exactly one visual line per record.
        """
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
        """One record wrapped to ``budgets``: as many visual lines as its tallest cell.

        Every cell is wrapped through :meth:`~motui.kernel.cell.Line.reflow`
        under ``cell_wrap`` (``WORD`` or ``CHAR``; styles, links and actions
        survive), each visual line is padded to its column budget with the
        cell's base style, and every visual line carries its own left and
        right border.  A cell shorter than the record's tallest one pads
        blank on the lines past its end.
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

        The resolution is :meth:`~motui.kernel.theme.RowStyles.band`: the
        precedence rule (D3) lives in the theme.
        **The hovered row wears the hover band
        whatever row it is on** -- the pointer is the more immediate signal,
        and the band's own precedence puts it over the cursor.  The cursor
        row carries ``rows.active`` while focused and ``rows.inactive``
        while not; every other data row rests on ``rows.base``, and a
        disabled row wears ``rows.disabled``.  The header and the grid rules
        are chrome: they rest on ``rows.base`` and never take the engaged
        band.  The ``rows`` group comes from ``styles`` when overridden,
        else the theme.
        """
        return self.group("rows").band(
            active=r == cursor,
            hovered=r == hover,
            focused=self.focused,
            disabled=self._is_disabled(r),
        )

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
        """The per-column cell budgets at ``width``: explicit widths, then the policy.

        ``set_widths``' pinned budgets replace the measured ones column by
        column (a column past the pinned list keeps its measured width, a
        pinned value below one reads as one).  With a single-row
        ``cell_wrap`` the old fits/shrink rule then runs exactly as it
        always did: a total that fits keeps the budgets (never stretched),
        a total that does not shrinks proportionally, floored at one column
        each.  With ``WORD`` / ``CHAR`` the wrapped policy runs instead --
        cap, floor, proportional split -- see :func:`_wrap_budgets`.
        """
        ncols = len(self.headers)
        pins = self._widths
        if pins is not None:
            natural = [
                max(1, pins[i]) if i < len(pins) else natural[i] for i in range(ncols)
            ]
        if self.cell_wrap is WrapMode.OVERFLOW:
            # The natural width is the content's own: the viewport never
            # shrinks it, and ``max_col_width=None`` leaves it uncapped.  A
            # set cap still applies, because it is the host's explicit
            # preference rather than a width response.
            if self.max_col_width is None:
                return list(natural)
            cap = max(1, self.max_col_width)
            return [min(w, cap) for w in natural]
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
        """What each rendered visual row carries: its kind, data row and visual line.

        :meth:`render` emits one line per entry and :meth:`click` /
        :meth:`hover_at` read the same structure back (the last render's,
        through :meth:`_hit_layout`), so the table's row arithmetic lives in
        exactly one place.  An entry whose ``data_row`` is an ``int`` is a
        visual line of that :attr:`rows` entry; a frame entry carries
        ``None``: ``"top"`` / ``"header"`` / ``"header_rule"`` above the
        body, ``"row_rule"`` after a record's last visual line,
        ``"bottom"``, and ``"empty"`` -- the single blank row of a
        headerless table.  The shape is derived from the row list and the
        wrapped cell heights, never from pinned row numbers, so a data
        row's position follows whatever the table renders.

        ``width=None`` answers the unwrapped structure (one visual line per
        record): the hit mapping's fallback before the first render.
        """
        if not self.headers:
            return [_Slot("empty", None, 0)]
        if width is None or self.cell_wrap not in (WrapMode.WORD, WrapMode.CHAR):
            return self._unwrapped_layout()
        return self._plan(width)[0]

    def _unwrapped_layout(self) -> list[_Slot]:
        """The one-visual-line-per-record structure (single-row modes, no render yet)."""
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
        """The visual-row structure hit mapping reads: the last render's, or the fallback."""
        layout = self._last_layout
        return layout if layout is not None else self._unwrapped_layout()

    def _row(
        self,
        cells: list[tuple[list[Segment], Style]],
        budgets: list[int],
        border_style: Style,
        aligns: list[str],
    ) -> Line:
        """One ``│ cell │ cell │`` row, every cell keeping its own segments.

        A cell is truncated to its column budget through
        ``Line.clip(cell_wrap, inner)`` (the marker is one column in
        ``ELLIPSIS`` mode, absent in ``CLIP``); the alignment pad fills the
        remaining budget as a ``Segment`` in the cell's base style.  ``str``
        and tuple cells have one style throughout, so the fused row is
        byte-identical to the single-segment rendering.  Columns past
        ``aligns`` read as left.
        """
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
        """The padded, truncated, space-wrapped interior of one cell."""
        line = Line(cell)
        # OVERFLOW's budget is the cell's natural width, so only an explicit
        # ``max_col_width`` can make a cell over-wide: that cap is a hard
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
        """A horizontal rule: ``left``, one run per column joined by ``cross``,
        ``right`` (``┌──┬──┐`` and kin, from the grid's :class:`Border`)."""
        rule = left + cross.join(line * (b + 2) for b in budgets) + right
        return Line.from_text(rule, border_style)

    def __repr__(self) -> str:
        return f"Table({self.headers!r})"
