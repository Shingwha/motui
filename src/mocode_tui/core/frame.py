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
claims, which document address a claimed cell holds, which edge cells its
chrome reserves, and the order overlays paint in.  How many panes there
are and at what ratios is policy and lives one level up (in ``app.py`` and
its assembly peers); what a scrollbar looks like, how long a toast lives,
and which selection a highlight covers are policy too, and live in the
overlays and chrome renderers registered on the frame.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from .lines import Line, cut_line
from .viewport import ScreenLayout, Viewport

__all__ = [
    "Chrome",
    "Frame",
    "FrameSpan",
    "FrameTable",
    "Overlay",
    "Pane",
    "Rect",
    "split_rect",
]

#: What a split divides: ``"vertical"`` tiles the width into side-by-side
#: panes (a vertical divider between them), ``"horizontal"`` tiles the
#: height into stacked ones (a horizontal divider).
_ORIENTATIONS = ("vertical", "horizontal")

#: The pane edges a chrome band may sit on.
_EDGES = ("left", "right", "top", "bottom")


@dataclass(frozen=True)
class Chrome:
    """One edge band inside a pane's rectangle, acquired by budget negotiation.

    ``edge`` names the pane edge the band sits on; ``size`` the cells it
    wants across that edge -- a ``"left"``/``"right"`` chrome is ``size``
    columns wide and the pane's height tall, a ``"top"``/``"bottom"`` one
    ``size`` rows tall and the pane's width long.  ``paint`` renders the
    band: it takes the pane's own layout -- the scroll state among it,
    :attr:`~mocode_tui.core.viewport.ScreenLayout.offset` and
    ``total_rows`` -- and the strip's length along the pane's other axis
    (its height for a left/right band, its width for a top/bottom one), and
    hands back one row per cell of the strip, each exactly the band's width.
    Painters are pure functions: no state, no clock, no input.

    ``size: 0`` is legal and means a no-op seam -- nothing is budgeted and
    nothing is painted, the shape a custom renderer grows from.  A band
    that would shrink the pane's viewport below one cell is clipped to what
    remains (see :meth:`Frame.compose`).
    """

    edge: str
    size: int
    paint: Callable[[ScreenLayout, int], list[Line]]

    def __post_init__(self) -> None:
        if self.edge not in _EDGES:
            raise ValueError(f"chrome edge must be one of {_EDGES}, got {self.edge!r}")


class Overlay(Protocol):
    """One overlay of the frame's pipeline: a pure ``paint(frame) -> layout``.

    An overlay claims nothing -- it paints last, over the composed frame, so
    it needs no budget negotiation.  The frame hands it the composed value:
    :attr:`Frame.layout` is the rows as they stand (an earlier overlay's
    rows when the registry already ran one), :attr:`Frame.pane_layouts`
    each pane's own layout, :attr:`Frame.table` the ownership table, and
    :attr:`Frame.rect` the frame's bounds -- a toast paints a corner off the
    bounds, a highlight rewrites a pane's rows.  What comes back is the
    layout to paint: the frame's layout with its rows rewritten, a
    pane-relative edit spliced back through :meth:`Frame.with_pane_rows`.

    Overlays register with :meth:`Frame.add_overlay` and paint in
    registration order; their lifecycle and their input live in the
    controller that owns them, never in the kernel.  The registry runs
    after a composition (:meth:`Frame.apply_overlays`), where
    ``frame.layout`` is the layout being painted.
    """

    def paint(self, frame: Frame) -> ScreenLayout: ...


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
    rect by :meth:`Frame.compose`.  Chromes stack in registration order and
    their budgets add per edge, so a rail beside a gutter is two chromes.
    """

    id: str
    rect: Rect
    viewport: Viewport
    chrome: tuple = ()

    def add_chrome(self, chrome: Chrome) -> None:
        """Register ``chrome`` on the pane (it paints after the ones before it).

        The one way chrome joins a pane after construction: a pane is a
        value, and this is its registration-time mutation -- the same append
        the ``chrome=(...)`` constructor argument performs.  A pane rebuilt
        for a new rectangle (a resize) starts bare: an owner that retiles
        its panes carries each chrome list across itself, the way the
        frame's overlay registry rides a new frame.
        """
        object.__setattr__(self, "chrome", self.chrome + (chrome,))

    def remove_chrome(self, chrome: Chrome) -> None:
        """Unregister ``chrome`` from the pane -- the symmetric of ``add_chrome``.

        The mirror of the registration append, by identity: the pane gives
        the band's cells back, so its viewport lays out at the full width
        again on the next composition.  A chrome the pane does not hold
        raises ``ValueError`` -- an unregister is a claim about what the
        pane carries, and a silent miss would hide a controller removing
        the wrong band (``Document.remove`` raises for a missing block the
        same way).  A controller that may detach twice tests membership
        first, keeping its own detach idempotent.
        """
        kept = tuple(c for c in self.chrome if c is not chrome)
        if len(kept) == len(self.chrome):
            raise ValueError(f"chrome is not registered on pane {self.id!r}: {chrome!r}")
        object.__setattr__(self, "chrome", kept)


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


def _negotiate(
    rect: Rect, chromes: Sequence[Chrome]
) -> tuple[Rect, list[tuple[Chrome, int, int]]]:
    """Subtract the pane's chrome budgets from ``rect``; the remainder is the
    viewport's.

    Every chrome asks for ``size`` cells across its edge; the pane's
    budgets add per edge, and opposite edges both subtract.  Negotiation is
    in registration order and a budget that would leave the viewport less
    than one cell in either axis is clipped to what remains of that axis --
    first come, first served, the clipping :func:`split_rect` applies to
    fixed sizes -- so chrome never eats a pane's whole viewport (or
    squeezes one out of a pane too small to host it).  Chromes on one edge
    stack outward from it: each takes its cells beside the ones before it.

    Returns the inner rectangle the pane's viewport lays out in and, per
    chrome in registration order, the cells granted it (0 for a zero-size
    chrome or one clipped away) and its offset from the pane edge.
    """
    room_width = max(0, rect.width - 1)  # shared by the left and right edges
    room_height = max(0, rect.height - 1)  # shared by the top and bottom ones
    left = right = top = bottom = 0
    granted: list[tuple[Chrome, int, int]] = []
    for chrome in chromes:
        if chrome.edge in ("left", "right"):
            take = min(max(0, chrome.size), room_width)
            room_width -= take
        else:
            take = min(max(0, chrome.size), room_height)
            room_height -= take
        if chrome.edge == "left":
            offset, left = left, left + take
        elif chrome.edge == "right":
            offset, right = right, right + take
        elif chrome.edge == "top":
            offset, top = top, top + take
        else:  # "bottom"
            offset, bottom = bottom, bottom + take
        granted.append((chrome, take, offset))
    inner = Rect(
        rect.x + left,
        rect.y + top,
        rect.width - left - right,
        rect.height - top - bottom,
    )
    return inner, granted


def _splice_chrome(
    rows: list[Line],
    pane: Pane,
    granted: Sequence[tuple[Chrome, int, int]],
    layout: ScreenLayout,
    width: int,
) -> None:
    """Splice the pane's granted chrome strips into the frame ``rows``.

    A band holds the pane edge its chrome named, stacked outward from that
    edge (the first chrome on an edge sits outermost, the ones after it
    beside it): a left/right chrome the columns at that side over the
    pane's whole height, a top/bottom one the rows at that end over the
    pane's whole width.  The strip lands over whatever the pane's viewport
    painted beside it -- a left/right band shares its rows with the
    viewport, a top/bottom one owns its own -- so the bands paint last and
    never hide content they were not budgeted across.  The strip is clipped
    to the cells actually granted (a painter declaring its full size over a
    clipped budget paints only the part that fits); a zero grant paints
    nothing.
    """
    rect = pane.rect
    for chrome, take, offset in granted:
        if take <= 0:
            continue  # the no-op seam: a zero-size chrome is never painted
        if chrome.edge == "left":
            band = Rect(rect.x + offset, rect.y, take, rect.height)
        elif chrome.edge == "right":
            band = Rect(rect.right - offset - take, rect.y, take, rect.height)
        elif chrome.edge == "top":
            band = Rect(rect.x, rect.y + offset, rect.width, take)
        else:  # "bottom"
            band = Rect(rect.x, rect.bottom - offset - take, rect.width, take)
        length = band.height if chrome.edge in ("left", "right") else band.width
        strip = chrome.paint(layout, length)[: band.height]
        for index, line in enumerate(strip):
            row = band.y + index
            if 0 <= row < len(rows):
                rows[row] = _splice(rows[row], line, band.x, band.width, width)


@dataclass(frozen=True)
class FrameSpan:
    """One pane's claim on the columns ``[start, end)`` of one screen row.

    ``block_id`` / ``row_in_block`` are that row's document address inside
    the pane; ``block_id`` is ``None`` for a row no block owns -- the pane's
    blank fill below short content, or a row its chrome bands cover -- and
    ``row_in_block`` carries nothing there.
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
    ownership table a hit test routes through.  An ordered overlay registry
    (:meth:`add_overlay`) paints over the composed frame last, through
    :meth:`apply_overlays` -- the registry is the kernel's mechanism, the
    overlays' controllers are policy and live one level up.  It owns no
    scroll state (the panes' viewports do), no focus policy and no clock.
    """

    def __init__(self, panes: Iterable[Pane] = ()) -> None:
        self._panes: tuple[Pane, ...] = tuple(panes)
        self._layout: ScreenLayout | None = None
        self._pane_layouts: tuple[ScreenLayout, ...] = ()
        self._table: FrameTable | None = None
        # pane id -> the rect its rows were laid out at (chrome subtracted):
        # where a pane-relative overlay splices its rewrite back.
        self._placements: dict[str, Rect] = {}
        self._size: tuple[int, int] | None = None
        self._overlays: list[Overlay] = []

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

        Each pane negotiates its chrome first: the bands it carries
        subtract their edge cells from its rectangle -- the bands stack,
        their budgets add, opposite edges both subtract, and a budget that
        would leave the viewport under one cell is clipped -- and the
        viewport lays out in the remainder, so content re-wraps at the
        reduced width instead of hiding under chrome.  The granted strips
        are then spliced back into the pane's rectangle, over the rows the
        viewport laid out beside them.  The painted rows are spliced into
        the frame rows at the pane's columns and rows, clipped at the frame
        edge.  The ownership table records, per screen row, which pane
        claims which columns and the document address inside it -- a pane
        claims its whole rectangle, its chrome band rows included, and a
        band row carries no document address.

        A lone pane whose rectangle is the whole frame and carries no
        budgeted chrome composes to its pane's own layout -- the very
        object its viewport returned -- so the single-pane stream is
        today's stream by pass-through, not by re-derivation.

        The result also travels back on the frame (:attr:`layout`,
        :attr:`pane_layouts`, :attr:`table`) for the overlay pipeline and
        the hit test to read.
        """
        rows: list[Line] = [Line() for _ in range(height)]
        table: list[list[FrameSpan]] = [[] for _ in range(height)]
        layouts: list[ScreenLayout] = []
        placements: dict[str, Rect] = {}
        banded = False  # whether any chrome strip took cells of the frame
        for pane in self._panes:
            rect = pane.rect
            inner, granted = _negotiate(rect, pane.chrome)
            layout = pane.viewport.layout(inner.width, inner.height)
            layouts.append(layout)
            placements[pane.id] = inner
            for index, line in enumerate(layout.rows):
                row = inner.y + index
                if 0 <= row < height:
                    rows[row] = _splice(rows[row], line, inner.x, inner.width, width)
            _splice_chrome(rows, pane, granted, layout, width)
            banded = banded or any(take > 0 for _, take, _ in granted)
            for row in range(rect.y, rect.bottom):
                if not 0 <= row < height:
                    continue
                index = row - inner.y
                owner = (
                    layout.row_blocks[index]
                    if 0 <= index < len(layout.row_blocks)
                    else None
                )
                block_id, row_in_block = owner if owner is not None else (None, 0)
                table[row].append(
                    FrameSpan(pane.id, block_id, row_in_block, rect.x, rect.right)
                )
        ordered = tuple(tuple(sorted(row, key=lambda span: span.start)) for row in table)
        if (
            len(layouts) == 1
            and self._panes[0].rect == Rect(0, 0, width, height)
            and not banded
        ):
            composed = layouts[0]  # pass-through: the frame is the pane's layout
        else:
            # No single document owns the frame: its ownership lives in the
            # frame table, and this layout is painted as it was spliced.
            composed = ScreenLayout(rows=rows, viewport_rows=[])
        self._layout = composed
        self._pane_layouts = tuple(layouts)
        self._table = FrameTable(rows=ordered)
        self._placements = placements
        self._size = (width, height)
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

    # -- overlays ------------------------------------------------------------------

    @property
    def overlays(self) -> tuple[Overlay, ...]:
        """The overlay registry, in the order the overlays paint."""
        return tuple(self._overlays)

    def add_overlay(self, overlay: Overlay) -> None:
        """Append ``overlay`` to the registry (it paints after the ones before it).

        The frame's half of the overlay surface; panes accept chrome the
        same way (:meth:`Pane.add_chrome`).  Both registrations are the
        assembly tier's front door: a controller -- the driver's selection,
        a toast -- attaches itself here and paints from then on.  A frame
        built for a new tiling (a resize) starts empty, so the owner
        carries its overlays across.
        """
        self._overlays.append(overlay)

    def remove_overlay(self, overlay: Overlay) -> None:
        """Unregister ``overlay`` -- the symmetric of :meth:`add_overlay`.

        By identity, and a missing overlay raises ``ValueError`` for the
        same reason :meth:`Pane.remove_chrome` does: an unregister is a
        claim about what the registry carries, and a silent miss would
        hide a controller detaching the wrong overlay.
        """
        kept = [held for held in self._overlays if held is not overlay]
        if len(kept) == len(self._overlays):
            raise ValueError(f"overlay is not registered on the frame: {overlay!r}")
        self._overlays = kept

    def apply_overlays(self, layout: ScreenLayout) -> ScreenLayout:
        """Run the overlay registry over ``layout``, in registration order.

        The composition root's last step: each overlay paints over the
        composed frame -- the frame carries the rows as they stand, so a
        later overlay composes over the rows an earlier one painted -- and
        hands back the layout to paint.  An empty registry, like an overlay
        that rewrites nothing, hands ``layout`` through unchanged.
        """
        for overlay in self._overlays:
            self._layout = layout  # the running layout, for the overlay to read
            layout = overlay.paint(self)
        self._layout = layout
        return layout

    def pane_layout(self, pane_id: str) -> ScreenLayout | None:
        """The layout :meth:`compose` laid out for the pane, or ``None``.

        The read half of a pane-relative overlay: the pane's own rows --
        laid out at its inner rect, chrome subtracted -- beside
        :attr:`pane_layouts`, which holds them all in pane order.
        """
        for pane, layout in zip(self._panes, self._pane_layouts):
            if pane.id == pane_id:
                return layout
        return None

    def with_pane_rows(self, pane_id: str, rows: list[Line]) -> ScreenLayout:
        """The layout being painted, with one pane's rows replaced in place.

        The write half of a pane-relative overlay: ``rows`` -- an overlay's
        rewrite of the pane's own :meth:`pane_layout` -- are spliced back
        into the frame rows at the pane's rectangle, every other cell kept
        exactly as it stands.  A pane spanning the frame hands its rows
        through unchanged, so the single-pane stream stays the pane's own;
        when no row moved, the layout comes back as it was.
        """
        layout = self._layout
        placement = self._placements.get(pane_id)
        if layout is None or placement is None or self._size is None:
            return layout
        width, _ = self._size
        spliced = list(layout.rows)
        for index, line in enumerate(rows):
            row = placement.y + index
            if 0 <= row < len(spliced):
                spliced[row] = _splice(
                    spliced[row], line, placement.x, placement.width, width
                )
        if len(spliced) == len(layout.rows) and all(
            new is old for new, old in zip(spliced, layout.rows)
        ):
            return layout  # nothing moved: the pass-through stays the pane's own
        return replace(layout, rows=spliced)

    def __repr__(self) -> str:
        return f"Frame({len(self._panes)} panes)"
