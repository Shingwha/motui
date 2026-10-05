"""The frame: rects, the split algebra, and the multi-pane compositor.

Everything that claims screen space partitions one screen through this
module.  A :class:`Rect` is a rectangle of that screen; :func:`split_rect`
divides one into a tiling with the fixed/flex vocabulary the widgets'
:class:`~mocode_tui.widgets.layout.Row` and
:class:`~mocode_tui.widgets.layout.Column` divide space with; and a
:class:`Frame` composes its :class:`Pane` values -- each a rectangle with a
viewport laid out inside it and the chrome bands it carries -- into one
painting target plus the ownership table that routes a screen cell back to
its pane and its document address.

The kernel owns the mechanics only: where the panes sit, which cells each
claims, which document address a claimed cell holds.  How many panes there
are and at what ratios is policy and lives one level up (in ``app.py`` and
its assembly peers); chrome budgets and the overlay pipeline compose on top
of what the frame built, in the waves that follow this one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .lines import Line, cut_line
from .viewport import ScreenLayout, Viewport

__all__ = ["Frame", "FrameSpan", "FrameTable", "Pane", "Rect", "split_rect"]

#: What a split divides: ``"vertical"`` tiles the width into side-by-side
#: panes (a vertical divider between them), ``"horizontal"`` tiles the
#: height into stacked ones (a horizontal divider).
_ORIENTATIONS = ("vertical", "horizontal")


@dataclass(frozen=True)
class Rect:
    """One rectangle of the screen: a 0-based origin and a size in cells.

    Width and height are non-negative -- an empty rectangle is legal, a
    negative one is not -- and the origin may sit anywhere.  Rectangles are
    values: a split hands back new ones instead of editing what it divided.
    """

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(
                f"rect size must be non-negative, got {self.width}x{self.height}"
            )

    @property
    def right(self) -> int:
        """The first column past the rectangle (``x + width``)."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """The first row past the rectangle (``y + height``)."""
        return self.y + self.height


def _spans(span: int, sizes: Sequence[int | None]) -> list[int]:
    """The widgets' division, lifted: fixed cells first, flex share the rest.

    :meth:`~mocode_tui.widgets.layout.Row.render`'s arithmetic, without the
    inter-column gap (a frame leaves inter-pane space to the chrome wave):
    a fixed size is honoured first, the flexible ones share what remains
    (``remaining // count``, the remainder discarded, never redistributed),
    and a remainder the fixed sizes already exhausted leaves the flexible
    panes nothing.  A non-positive fixed size takes no cells and eats none
    of the remainder.
    """
    fixed_total = sum(w for w in sizes if w is not None and w > 0)
    flex = sum(1 for w in sizes if w is None)
    remaining = span - fixed_total
    share = remaining // flex if flex and remaining > 0 else 0
    return [w if w is not None else share for w in sizes]


def split_rect(
    rect: Rect, orientation: str, sizes: Sequence[int | None]
) -> list[Rect]:
    """Divide ``rect`` into one rectangle per entry of ``sizes``, in order.

    ``orientation`` names the divider: ``"vertical"`` tiles the width into
    side-by-side panes, ``"horizontal"`` tiles the height into stacked ones.
    ``sizes`` are cell counts, ``None`` meaning flexible, divided with the
    fixed/flex vocabulary of the widgets' containers -- so a frame split and
    a widget row read alike.  The sizes tile the span: a fixed size that
    overruns what remains is clipped to it (a tiling never overlaps), each
    pane's origin follows the panes before it, and the axis that was not
    divided is inherited from ``rect`` unchanged.
    """
    if orientation not in _ORIENTATIONS:
        raise ValueError(
            f"orientation must be 'vertical' or 'horizontal', got {orientation!r}"
        )
    if not sizes:
        return []
    span = rect.width if orientation == "vertical" else rect.height
    rects: list[Rect] = []
    at = 0
    for size in _spans(span, sizes):
        taken = max(0, min(size, span - at))
        if orientation == "vertical":
            rects.append(Rect(rect.x + at, rect.y, taken, rect.height))
        else:
            rects.append(Rect(rect.x, rect.y + at, rect.width, taken))
        at += taken
    return rects


@dataclass(frozen=True)
class Pane:
    """One pane of a frame: its rectangle and the viewport laid out inside it.

    ``chrome`` is the pane's edge budget -- the edge columns or rows
    reserved for scrollbars and rails, negotiated against the pane's inner
    rect.  The frame wave composes with it empty; the chrome wave fills it.
    """

    id: str
    rect: Rect
    viewport: Viewport
    chrome: tuple = ()


def _splice(base: Line, line: Line, x: int, width: int, frame_width: int) -> Line:
    """Place one pane row into the frame row beneath it.

    A pane whose rectangle spans the full frame width hands its row through
    unchanged -- the compositor never slices, truncates or pads a row it
    does not have to move, which is what makes a single-pane frame compose
    to its pane's own layout instead of a re-derivation of it.  A pane
    beside another one is cut to its own columns through the kernel's
    column cut (so styles survive exactly as they do under an overlay), the
    columns its neighbours hold or the edges leave blank kept around it.
    """
    if x == 0 and width == frame_width:
        return line
    left = cut_line(base, 0, x).pad_to(x)
    middle = cut_line(line, 0, width)
    right = cut_line(base, x + width, frame_width).pad_to(frame_width - x - width)
    return left + middle + right


@dataclass(frozen=True)
class FrameSpan:
    """One pane's claim on the columns ``[start, end)`` of one screen row.

    ``block_id`` / ``row_in_block`` are that row's document address inside
    the pane; ``block_id`` is ``None`` for the pane's blank fill (the pane
    owns those cells, no block owns the row) and ``row_in_block`` carries
    nothing there.
    """

    pane_id: str
    block_id: str | None
    row_in_block: int
    start: int
    end: int


@dataclass(frozen=True)
class FrameTable:
    """The frame's ownership: per screen row, the column spans panes claim.

    One entry per screen row in painting order.  A row of a split frame
    carries one span per pane touching it, leftmost first; a pane claims its
    whole rectangle, the rows below its content included, so a hit test can
    tell "inside a pane, over blank fill" apart from "outside every pane".
    """

    rows: tuple[tuple[FrameSpan, ...], ...]

    def resolve(self, row: int, col: int) -> FrameSpan | None:
        """The span owning cell ``(col, row)``, or ``None``.

        A column outside every span of an owned row clamps into the nearest
        span at that row's end -- the hit test's 0-based clamp, lifted into
        the table -- and a row past the last composition resolves to
        nothing.
        """
        if not 0 <= row < len(self.rows):
            return None
        spans = self.rows[row]
        if not spans:
            return None
        for span in spans:
            if span.start <= col < span.end:
                return span
        return spans[0] if col < spans[0].start else spans[-1]


class Frame:
    """A tiling of panes over one screen, composed into a painting target.

    The frame holds its panes and, after a :meth:`compose`, what that
    composition produced: the :class:`~mocode_tui.core.viewport.ScreenLayout`
    to paint, the per-pane layouts an overlay composes over, and the
    ownership table a hit test routes through.  It owns no scroll state (the
    panes' viewports do), no focus policy and no clock.
    """

    def __init__(self, panes: Iterable[Pane] = ()) -> None:
        self._panes: tuple[Pane, ...] = tuple(panes)
        self._layout: ScreenLayout | None = None
        self._pane_layouts: tuple[ScreenLayout, ...] = ()
        self._table: FrameTable | None = None

    # -- the tiling ------------------------------------------------------------

    @property
    def panes(self) -> tuple[Pane, ...]:
        """The panes, in the order the tiling was built."""
        return self._panes

    @property
    def rect(self) -> Rect | None:
        """The bounding rectangle of the tiling, or ``None`` when empty.

        Panes partition a frame, so this is the frame they tile -- which is
        how an owner tells a retiled frame from a stale one.
        """
        if not self._panes:
            return None
        left = min(pane.rect.x for pane in self._panes)
        top = min(pane.rect.y for pane in self._panes)
        right = max(pane.rect.right for pane in self._panes)
        bottom = max(pane.rect.bottom for pane in self._panes)
        return Rect(left, top, right - left, bottom - top)

    def pane(self, pane_id: str) -> Pane | None:
        """The pane with ``pane_id``, or ``None`` when the frame holds none."""
        for pane in self._panes:
            if pane.id == pane_id:
                return pane
        return None

    @property
    def focused_pane(self) -> Pane | None:
        """The pane input routes to: the first, until a focus policy moves it."""
        return self._panes[0] if self._panes else None

    # -- composition -------------------------------------------------------------

    def compose(self, width: int, height: int) -> ScreenLayout:
        """Lay every pane out inside its rectangle and splice one screen.

        Each pane's viewport is laid out at the pane's inner rect (its rect
        minus the chrome budgets it carries -- none yet), and the returned
        rows are spliced into the frame rows at the pane's columns and rows,
        clipped at the frame edge.  The ownership table records, per screen
        row, which pane claims which columns and the document address inside
        it.  A lone pane whose rectangle is the whole frame composes to its
        pane's own layout -- the very object its viewport returned -- so the
        single-pane stream is today's stream by pass-through, not by
        re-derivation.

        The result also travels back on the frame (:attr:`layout`,
        :attr:`pane_layouts`, :attr:`table`) for the overlay pipeline and
        the hit test to read.
        """
        rows: list[Line] = [Line() for _ in range(height)]
        table: list[list[FrameSpan]] = [[] for _ in range(height)]
        layouts: list[ScreenLayout] = []
        for pane in self._panes:
            rect = pane.rect
            layout = pane.viewport.layout(rect.width, rect.height)
            layouts.append(layout)
            for index, line in enumerate(layout.rows):
                row = rect.y + index
                if 0 <= row < height:
                    rows[row] = _splice(rows[row], line, rect.x, rect.width, width)
            for index, owner in enumerate(layout.row_blocks):
                row = rect.y + index
                if not 0 <= row < height:
                    continue
                block_id, row_in_block = owner if owner is not None else (None, 0)
                table[row].append(
                    FrameSpan(pane.id, block_id, row_in_block, rect.x, rect.right)
                )
        ordered = tuple(tuple(sorted(row, key=lambda span: span.start)) for row in table)
        if len(layouts) == 1 and self._panes[0].rect == Rect(0, 0, width, height):
            composed = layouts[0]  # pass-through: the frame is the pane's layout
        else:
            # No single document owns the frame: its ownership lives in the
            # frame table, and this layout is painted as it was spliced.
            composed = ScreenLayout(rows=rows, viewport_rows=[])
        self._layout = composed
        self._pane_layouts = tuple(layouts)
        self._table = FrameTable(rows=ordered)
        return composed

    @property
    def layout(self) -> ScreenLayout | None:
        """The layout the last :meth:`compose` produced, or ``None``."""
        return self._layout

    @property
    def pane_layouts(self) -> tuple[ScreenLayout, ...]:
        """The per-pane layouts of the last composition, in pane order.

        What an overlay composes over: the rows of one pane's layout
        spliced back into the frame rows it came from.
        """
        return self._pane_layouts

    @property
    def table(self) -> FrameTable | None:
        """The ownership table of the last composition, or ``None``."""
        return self._table

    def __repr__(self) -> str:
        return f"Frame({len(self._panes)} panes)"
