"""Canvas: a mutable cell grid that answers immutable surfaces.

A :class:`Canvas` is the toolkit's one drawing surface below the row model:
a rectangular grid of :class:`~motui.kernel.cell.Cell` values written with
``put``/``text``/``hline``/``vline``/``box``/``blit`` and read back as a
:class:`~motui.kernel.cell.Surface`.  It is deliberately the only component
that owns mutable render state: the surface it produces is frozen like every
other render result, and no byte ever leaves this module -- a Canvas paints
cells, and the painter above it turns those cells into terminal bytes.

Rows are cached by identity.  Every write marks its row dirty; :meth:`surface`
rebuilds only the dirty rows and reuses the previous ``Line`` objects for the
rest, so a game that moves one sprite or a plot that appends a point pays for
the rows that changed rather than for the canvas.  Adjacent cells sharing a
style fuse into one segment (:func:`~motui.kernel.cell.fuse`), which keeps an
80x24 monochrome canvas at one segment per row.

Two marker vocabularies refine the grid for plots:

* ``"cell"`` -- one cell per point, the full block glyph;
* ``"half"`` -- two sub-rows per cell (``▀``, ``▄`` or ``█``);
* ``"braille"`` -- two sub-columns by four sub-rows per cell, encoded as
  ``U+2800 + bitset`` with the standard dot numbering (dot 1 at the cell's
  top left, dot 7 at its bottom left).

The marker is the *plot* resolution: ``put``/``text`` write whole cells
whatever the marker, while :meth:`plot` projects value-space ``(x, y)``
points onto the marker's grid.  Plotting into a cell combines with a half or
braille mark already there; writing text into the cell replaces it.

The canvas owns its width and height.  Assigning either one resizes the
grid, preserving the cells in the overlapping rectangle (a wide character
whose continuation column is cut becomes a space).
"""

from __future__ import annotations

from ..kernel.cell import Cell, Line, Segment, Surface
from ..kernel.glyphs import GLYPHS, Border, Glyphs
from ..kernel.layout import Constraints
from ..kernel.style import NONE, Style
from ..kernel.text import visible_width
from .drawing import Drawing

__all__ = ["Canvas", "Sparkline"]

#: The accepted marker names, in increasing sub-cell resolution.
_MARKERS = ("cell", "half", "braille")

_HALF_TOP = "\u2580"  # ▀
_HALF_BOTTOM = "\u2584"  # ▄
_HALF_FULL = "\u2588"  # █
_BRAILLE_BASE = 0x2800
#: Braille dot bits by ``(sub-column, sub-row)``: the standard numbering puts
#: dots 1/2/3/7 in the left column and 4/5/6/8 in the right one.
_BRAILLE_BITS = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))

#: The segment every untouched blank cell shares: immutable, so one value is
#: safe to hand to the whole grid and a write replaces the slot.
_BLANK_SEGMENT = Segment(" ")
_BLANK_CELL = Cell()

#: The sparkline's default style: an immutable value safe as a default.
_DEFAULT_STYLE = Style()


class Canvas(Drawing):
    """A mutable cell grid; :meth:`surface` answers its immutable image.

    Coordinates are 0-based cells with the origin at the top left.  Writes
    outside the canvas are ignored (``put``/``text`` clip at the edges rather
    than raising), and a write that would split a double-width character is
    dropped instead of half-written: an over-wide cell would corrupt every
    row after it.  A wide character occupies its lead cell plus a
    continuation cell whose ``char`` is empty, so a row's display width is
    still one column per cell.

    Sizing is the :class:`~motui.widgets.drawing.Drawing` lifecycle: the grid
    is resized explicitly (``width``/``height`` assignment, :meth:`resize` or
    :meth:`fit`) and ``render`` only clips the cached image.  The ``plot``
    marker is ``plot_marker``; it affects :meth:`plot` alone, while
    ``put``/``text`` always write whole cells.
    """

    __slots__ = (
        "_cells",
        "_dirty",
        "_lines",
        "_row_counts",
        "_row_rep",
        "_segments",
        "_spares",
        "glyphs",
        "plot_marker",
    )

    def __init__(
        self,
        *,
        width: int = 0,
        height: int = 0,
        plot_marker: str = "cell",
        glyphs: Glyphs = GLYPHS,
        theme=None,
    ) -> None:
        if plot_marker not in _MARKERS:
            raise ValueError(
                f"marker must be one of {_MARKERS}, got {plot_marker!r}"
            )
        super().__init__(width=width, height=height, theme=theme)
        self.plot_marker = plot_marker
        self.glyphs = glyphs
        self._cells: list[list[Cell]] = []
        #: The cell's immutable segment form, built at write time.  ``Surface``
        #: materialization then coalesces these runs instead of constructing a
        #: segment per cell, and a cell nobody rewrote keeps its segment object
        #: across rebuilds.  ``None`` is a continuation cell (a wide glyph's
        #: second column).  Blank cells share one segment: the value is
        #: immutable and a write replaces the slot rather than the segment.
        self._segments: list[list[Segment | None]] = []
        #: Per row, how many cells carry each segment object, and the one
        #: object a uniform row carries (``None`` for a mixed row).  The
        #: counts let ``surface`` answer a whole uniform row with one cached
        #: line instead of walking its cells; writes maintain them in O(1).
        self._row_counts: list[dict[int, int]] = []
        self._row_rep: list[Segment | None] = []
        #: Canonical segment/cell values per ``(char, id(style))``, so every
        #: cell drawn with one character and one style object shares one
        #: immutable value (which is what makes a packed row one run).  The
        #: cache is capped: a game that mints a new Style per cell must not
        #: grow it without bound.
        self._spares: dict[tuple[str, int], tuple[Cell, Segment]] = {}
        #: Dirty rows and their cached lines: ``None`` means "never built",
        #: and every write adds its row here (and drops the surface cache).
        self._dirty: set[int] = set()
        self._lines: list[Line | None] = []
        self._resize_storage(self._width, self._height)

    # -- geometry ----------------------------------------------------------

    def _resize_storage(self, width: int, height: int) -> None:
        """Rebuild the grid for the base's new size, keeping the overlap."""
        cells: list[list[Cell]] = []
        segments: list[list[Segment | None]] = []
        for y in range(height):
            if y < len(self._cells):
                old = self._cells[y]
                old_segments = self._segments[y]
                row = list(old[:width])
                row_segments: list[Segment | None] = list(old_segments[:width])
                if len(row) < width:
                    row.extend(_BLANK_CELL for _ in range(width - len(row)))
                    row_segments.extend(_BLANK_SEGMENT for _ in range(width - len(row_segments)))
            else:
                row = [_BLANK_CELL for _ in range(width)]
                row_segments = [_BLANK_SEGMENT] * width
            # A wide character whose continuation column was cut would make
            # the row wider than its cells; blank the orphaned lead.
            if row and visible_width(row[-1].char) > 1:
                row[-1] = Cell()
                row_segments[-1] = _BLANK_SEGMENT
            cells.append(row)
            segments.append(row_segments)
        self._cells = cells
        self._segments = segments
        self._row_counts = []
        self._row_rep = []
        for row_segments in segments:
            counts: dict[int, int] = {}
            representative: Segment | None = None
            for segment in row_segments:
                if segment is None:
                    continue
                identifier = id(segment)
                counts[identifier] = counts.get(identifier, 0) + 1
                representative = segment
            self._row_counts.append(counts)
            self._row_rep.append(representative if len(counts) == 1 else None)
        self._lines = [None] * height
        self._dirty = set(range(height))

    def _ensure_grid(self) -> None:
        if len(self._cells) != self._height or (
            self._cells and len(self._cells[0]) != self._width
        ):
            self._resize_storage(self._width, self._height)

    # -- writing -----------------------------------------------------------

    def clear(self) -> None:
        """Blank every cell; every row is dirty again."""
        self._cells = [[_BLANK_CELL for _ in range(self._width)] for _ in range(self._height)]
        self._segments = [[_BLANK_SEGMENT] * self._width for _ in range(self._height)]
        self._row_counts = [
            {id(_BLANK_SEGMENT): self._width} if self._width else {}
            for _ in range(self._height)
        ]
        self._row_rep = [
            _BLANK_SEGMENT if self._width else None for _ in range(self._height)
        ]
        self._dirty = set(range(self._height))
        self._invalidate()

    def put(self, x: int, y: int, char: str, style: Style = NONE) -> None:
        """Write one character (or cluster) at ``(x, y)``.

        A double-width character occupies two columns (its continuation cell
        carries the empty string); a write whose character would cross the
        right edge is ignored.  Negative or out-of-range coordinates write
        nothing.  The empty string is a no-op.
        """
        self._ensure_grid()
        if not char or y < 0 or y >= self._height or x < 0:
            return
        width = visible_width(char)
        if width <= 0:
            return
        if x + width > self._width:
            return
        self._write(x, y, char, width, style)

    def text(self, x: int, y: int, text: str, style: Style = NONE) -> None:
        """Write ``text`` left to right from ``(x, y)``, clipping at the edge.

        Characters are written one codepoint at a time; a zero-width
        continuation (a combining mark) attaches to the previous cell.  Text
        running past the right edge is clipped, not wrapped.
        """
        self._ensure_grid()
        if y < 0 or y >= self._height:
            return
        col = x
        for char in text:
            width = visible_width(char)
            if width == 0:
                if 0 <= col - 1 < self._width:
                    previous = self._cells[y][col - 1]
                    cell, segment = self._spare(previous.char + char, previous.style)
                    self._put_cell(y, col - 1, cell, segment)
                    self._touch(y)
                continue
            if col >= self._width:
                break
            if col + width <= self._width:
                self._write(col, y, char, width, style)
            col += width

    def hline(
        self, x: int, y: int, length: int, char: str = "\u2500", style: Style = NONE
    ) -> None:
        """Draw ``length`` cells of ``char`` to the right from ``(x, y)``."""
        for offset in range(max(0, length)):
            self.put(x + offset, y, char, style)

    def vline(
        self, x: int, y: int, length: int, char: str = "\u2502", style: Style = NONE
    ) -> None:
        """Draw ``length`` cells of ``char`` downward from ``(x, y)``."""
        for offset in range(max(0, length)):
            self.put(x, y + offset, char, style)

    def box(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        border: Border | None = None,
        style: Style = NONE,
    ) -> None:
        """Draw a box outline; ``border`` defaults to the glyph vocabulary.

        A one-row box is drawn as a top edge; a one-column box as a left edge.
        Every mark is written through :meth:`put`, so a box that leaves the
        canvas is clipped exactly like its cells.
        """
        if width <= 0 or height <= 0:
            return
        marks = self.glyphs.box if border is None else border
        if height == 1:
            for column in range(width):
                self.put(x + column, y, marks.top, style)
            return
        for column in range(width):
            if column == 0:
                top, bottom = marks.top_left, marks.bottom_left
            elif column == width - 1:
                top, bottom = marks.top_right, marks.bottom_right
            else:
                top, bottom = marks.top, marks.bottom
            self.put(x + column, y, top, style)
            self.put(x + column, y + height - 1, bottom, style)
        for row in range(1, height - 1):
            self.put(x, y + row, marks.left, style)
            if width > 1:
                self.put(x + width - 1, y + row, marks.right, style)

    def blit(self, other: Canvas, x: int, y: int) -> None:
        """Copy ``other``'s cells onto this canvas with its top left at ``(x, y)``.

        Only whole cells cross: the source's continuation cells are rebuilt
        by :meth:`put` from their lead character, so a wide glyph blitted at
        an edge is dropped rather than split.  The copy lands clipped to this
        canvas.
        """
        for source_y in range(other.height):
            for source_x in range(other.width):
                cell = other._cells[source_y][source_x]
                if not cell.char:
                    continue
                self.put(x + source_x, y + source_y, cell.char, cell.style)

    def plot(
        self,
        points,
        *,
        marker: str | None = None,
        style: Style = NONE,
    ) -> None:
        """Plot value-space ``(x, y)`` points onto the marker's grid.

        The points are normalized independently on both axes to the marker
        resolution (one cell, 1x2 half-cells or 2x4 braille dots per cell),
        with the larger ``y`` value at the top -- the usual math orientation
        for charts.  A degenerate range (every point on one line) lands on the
        first column and the bottom row.  Plotting combines with half/braille
        marks already in a cell; with the ``"cell"`` marker a point overwrites
        the cell with a full block.  An empty sequence is a no-op.
        """
        self._ensure_grid()
        mode = self.plot_marker if marker is None else marker
        if mode not in _MARKERS:
            raise ValueError(f"marker must be one of {_MARKERS}, got {mode!r}")
        projected = [(float(px), float(py)) for px, py in points]
        if not projected or self._width <= 0 or self._height <= 0:
            return
        columns = self._width * (2 if mode == "braille" else 1)
        rows = self._height * {"cell": 1, "half": 2, "braille": 4}[mode]
        xs = [point[0] for point in projected]
        ys = [point[1] for point in projected]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        for value_x, value_y in projected:
            column = (
                0
                if max_x == min_x
                else round((value_x - min_x) * (columns - 1) / (max_x - min_x))
            )
            row = (
                rows - 1
                if max_y == min_y
                else round((max_y - value_y) * (rows - 1) / (max_y - min_y))
            )
            if mode == "cell":
                self.put(column, row, self.glyphs.bar_full, style)
            elif mode == "half":
                self._mark_half(column, row // 2, row % 2 == 0, style)
            else:
                self._mark_braille(column // 2, row // 4, column % 2, row % 4, style)

    # -- the row image -----------------------------------------------------

    def _build_surface(self) -> Surface:
        """Assemble the full-size surface; only dirty rows are rebuilt.

        A rebuild reuses the ``Line`` object of every row that was not
        written since the last one -- the row cache is identity, not
        equality, so a caller can see which rows changed.  The base caches
        the returned surface until the next :meth:`_invalidate`.
        """
        self._ensure_grid()
        lines = self._lines
        uniform: dict[int, Line] = {}
        for row in sorted(self._dirty):
            counts = self._row_counts[row]
            if len(counts) == 1:
                segment = self._row_rep[row]
                if segment is None:  # a continuation-only row: build normally
                    lines[row] = _row_line(self._segments[row])
                    continue
                identifier = id(segment)
                line = uniform.get(identifier)
                if line is None:
                    # One run, repeated once per non-continuation cell: the
                    # row of a packed canvas (all spaces, or one ink colour).
                    line = Line(
                        (Segment(segment.text * counts[identifier], segment.style),)
                    )
                    uniform[identifier] = line
                lines[row] = line
            else:
                lines[row] = _row_line(self._segments[row])
        self._dirty.clear()
        return Surface(width=self._width, rows=tuple(lines))

    # -- internals ---------------------------------------------------------

    def _write(self, x: int, y: int, char: str, width: int, style: Style) -> None:
        cells = self._cells[y]
        old_char = cells[x].char
        # A wide glyph's cells are a unit: writing into either half blanks the
        # old cluster first, and a continuation left beyond the new span is
        # repaired below.  Ordinary single-width cells take the fast path.
        if old_char == "" and x > 0:
            lead = x - 1
            while lead >= 0 and cells[lead].char == "":
                lead -= 1
            if lead >= 0:
                self._blank_cells(y, lead, lead + visible_width(cells[lead].char))
        elif old_char and visible_width(old_char) > 1:
            self._blank_cells(y, x, x + visible_width(old_char))
        cell, segment = self._spare(char, style)
        self._put_cell(y, x, cell, segment)
        for offset in range(1, width):
            self._put_cell(y, x + offset, Cell("", style), None)
        after = x + width
        if after < self._width and cells[after].char == "":
            self._blank_cells(y, after, after + 1)
        self._touch(y)

    def _spare(self, char: str, style: Style) -> tuple[Cell, Segment]:
        """The canonical ``(cell, segment)`` pair for ``char`` in ``style``."""
        key = (char, id(style))
        cached = self._spares.get(key)
        if cached is not None and cached[1].style is style:
            return cached
        if len(self._spares) >= 4096:
            self._spares.clear()
        value = (Cell(char, style), Segment(char, style))
        self._spares[key] = value
        return value

    def _put_cell(self, y: int, index: int, cell: Cell, segment: Segment | None) -> None:
        """Replace one cell and keep the row's segment census true."""
        segments = self._segments[y]
        counts = self._row_counts[y]
        old = segments[index]
        if old is not None:
            identifier = id(old)
            remaining = counts[identifier] - 1
            if remaining:
                counts[identifier] = remaining
            else:
                del counts[identifier]
        self._cells[y][index] = cell
        segments[index] = segment
        if segment is not None:
            identifier = id(segment)
            counts[identifier] = counts.get(identifier, 0) + 1
        if len(counts) == 1:
            self._row_rep[y] = segment if segment is not None else self._row_rep[y]
        else:
            self._row_rep[y] = None

    def _blank_cells(self, y: int, start: int, stop: int) -> None:
        """Blank the cells ``[start, stop)``, repairing their wide clusters."""
        for index in range(max(0, start), min(self._width, stop)):
            self._put_cell(y, index, _BLANK_CELL, _BLANK_SEGMENT)

    def _touch(self, row: int) -> None:
        self._dirty.add(row)
        self._invalidate()

    def _mark_half(self, x: int, y: int, top: bool, style: Style) -> None:
        if not 0 <= x < self._width or not 0 <= y < self._height:
            return
        previous = self._cells[y][x].char
        if previous == "":
            return  # a wide glyph's continuation cell: do not split it
        if top:
            char = _HALF_FULL if previous in (_HALF_BOTTOM, _HALF_FULL) else _HALF_TOP
        else:
            char = _HALF_FULL if previous in (_HALF_TOP, _HALF_FULL) else _HALF_BOTTOM
        self._write(x, y, char, 1, style)

    def _mark_braille(
        self, x: int, y: int, column: int, row: int, style: Style
    ) -> None:
        if not 0 <= x < self._width or not 0 <= y < self._height:
            return
        previous = self._cells[y][x].char
        bits = ord(previous) - _BRAILLE_BASE if len(previous) == 1 else -1
        if not 0 <= bits <= 0xFF:
            bits = 0
        char = chr(_BRAILLE_BASE + (bits | _BRAILLE_BITS[column][row]))
        self._write(x, y, char, 1, style)

    def __repr__(self) -> str:
        return (
            f"Canvas({self._width}x{self._height}, plot_marker={self.plot_marker!r}, "
            f"dirty={len(self._dirty)})"
        )


def _row_line(segments: list[Segment | None]) -> Line:
    """One row's cached segments as a line, coalescing adjacent equal runs.

    The row is built in one pass instead of through :func:`fuse`: a run that
    is one cell reuses that cell's segment object, and a longer run builds
    one segment from the joined text.  ``fuse`` would rebuild the growing
    run on every merge (quadratic bytes per row); a full-colour canvas has
    one segment per cell already, so coalescing must stay linear there.

    Canvas cells carry no ``link``/``action`` payloads (the write API has no
    slot for them), so style is the whole run key.
    """
    runs: list[Segment] = []
    current: Segment | None = None
    current_style: Style | None = None
    texts: list[str] | None = None
    for segment in segments:
        # ``None`` is a wide glyph's continuation cell (it paints nothing);
        # a present segment always carries text.
        if segment is None:
            continue
        style = segment.style
        # Identity first: a canvas written with one style object (the common
        # whole-grid case) compares by pointer, not field by field.
        if current is not None and (
            style is current_style or style == current_style
        ):
            if texts is None:
                texts = [current.text]
            texts.append(segment.text)
            continue
        if current is not None:
            runs.append(
                current if texts is None else Segment("".join(texts), current_style)
            )
        current = segment
        current_style = style
        texts = None
    if current is not None:
        runs.append(current if texts is None else Segment("".join(texts), current_style))
    return Line(runs)


class Sparkline:
    """A one-row plot of ``values``: the thinnest wrapper over :class:`Canvas`.

    Each value is plotted at its index with the configured marker, so the
    natural height is one cell row (two half-cells or four braille rows).
    A ``max_height`` budget makes the sparkline fill that many rows, which is
    what a dashboard slot does with it.
    """

    __slots__ = ("glyphs", "marker", "style", "values")

    def __init__(
        self,
        values=(),
        *,
        marker: str = "half",
        style: Style = _DEFAULT_STYLE,
        glyphs: Glyphs = GLYPHS,
    ) -> None:
        if marker not in _MARKERS:
            raise ValueError(f"marker must be one of {_MARKERS}, got {marker!r}")
        self.values = list(values)
        self.marker = marker
        self.style = style
        self.glyphs = glyphs

    def render(self, c: Constraints) -> Surface:
        """Plot the values into a canvas at the constraint's size."""
        height = 1 if c.max_height is None else c.max_height
        if c.width <= 0 or height <= 0:
            return Surface(width=c.width, rows=())
        canvas = Canvas(
            width=c.width,
            height=height,
            plot_marker=self.marker,
            glyphs=self.glyphs,
        )
        canvas.plot(
            [(index, value) for index, value in enumerate(self.values)],
            style=self.style,
        )
        return canvas.render(Constraints(width=c.width, max_height=height))

    def __repr__(self) -> str:
        return f"Sparkline({len(self.values)} values, marker={self.marker!r})"
