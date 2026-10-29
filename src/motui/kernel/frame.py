"""Rectangles, the split algebra, and the multi-pane compositor.
Splits are structure; a frame composes pane views and chrome into one row
grid, painting chrome budgets, content, granted strips, then overlays."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from .cell import Line, cut_line, slice_line
from .document import Document, Placement, Section, Sizing
from .geom import Axis, Rect
from .layout import ScreenLayout, Scroll, Viewport
from .overlay import LAYERS, Overlay, apply_overlays
from .style import Style
from .text import index_bounds_at_columns
from .theme import Theme

__all__ = [
    "LAYERS",
    "Chrome",
    "Frame",
    "FrameSpan",
    "FrameTable",
    "Overlay",
    "Pane",
    "Rect",
    "Separator",
    "Split",
    "splice_row",
]

#: The module-level fallback counter for a pane split outside any frame
#: (tests, a detached `Pane`): ids are monotonic and never reused, exactly
#: as a frame's own counter.
_fallback_pane_counter = 0


def _next_fallback_pane_id() -> str:
    """The next ``pane-N`` id for a split outside a frame."""
    global _fallback_pane_counter
    _fallback_pane_counter += 1
    return f"pane-{_fallback_pane_counter}"

#: The pane edges a chrome band may sit on.
_EDGES = ("left", "right", "top", "bottom")

#: The pane regions a chrome band may decorate: the pane's rectangle
#: ("pane") or its scrolling window ("body").
_SCOPES = ("pane", "body")

#: The frame edges a dock may pin against.
DOCK_EDGES = ("top", "bottom")

#: The :attr:`Chrome.name` a divider registers under -- one mark with two
#: jobs, rather than guessing at a size or an edge a scrollbar column
#: shares: :func:`_negotiate` puts it first on its edge, so the divider
#: stacks outermost whatever else the pane registered and whenever, and a
#: close strips it by name (:meth:`Pane.close`), so the band that divides
#: two panes dies with the adjacency it divides.  The kernel's themed
#: :class:`~motui.kernel.chrome.Separator` is the one divider implementation
#: and registers under this mark; the kernel owns the mark because
#: negotiation and teardown are the kernel's.
SEPARATOR_CHROME_NAME = "separator"


@dataclass(frozen=True)
class Chrome:
    """One edge band inside a pane's rectangle, acquired by budget negotiation.

    ``edge``/``size`` name the side and cells; ``scope`` is ``"pane"`` or the
    scrolling ``"body"``; ``paint`` renders the band's strip purely. ``name``
    lets a close strip a divider and stack it outermost."""

    edge: str
    size: int
    paint: Callable[[ScreenLayout, int], list[Line]]
    name: str = ""
    scope: str = "pane"

    def __post_init__(self) -> None:
        if self.edge not in _EDGES:
            raise ValueError(f"chrome edge must be one of {_EDGES}, got {self.edge!r}")
        if self.scope not in _SCOPES:
            raise ValueError(
                f"chrome scope must be one of {_SCOPES}, got {self.scope!r}"
            )
        if self.scope == "body" and self.edge not in ("left", "right"):
            raise ValueError(
                "a body-scoped chrome shares the window's rows; "
                f"edge {self.edge!r} owns its rows instead"
            )


def _ratio_sizes(span: int, weights: Sequence[float], min_size: int) -> list[int]:
    """The last weight takes the floor remainder: panes partition the screen, so a
    hole at the edge is never allowed."""
    total = sum(weights)
    sizes = [int(span * weight // total) for weight in weights]
    remainder = span - sum(sizes)
    if remainder:
        sizes[-1] += remainder
    if min_size:
        sizes = [max(size, min_size) for size in sizes]
    return sizes


def _strip_divider(pane: Pane, edge: str) -> None:
    """Strip by name and edge, never by size: a scrollbar is a 1-cell right-edge
    chrome too, and a miss is silent."""
    kept = tuple(
        chrome
        for chrome in pane.chrome
        if not (chrome.name == SEPARATOR_CHROME_NAME and chrome.edge == edge)
    )
    if len(kept) != len(pane.chrome):
        pane.chrome = kept


def _split_holding(pane: Pane, tree: Sequence[Pane]) -> tuple[Pane, int, Split] | None:
    """A pane carries no parent pointer, so the holding split is found by walking
    the roots depth-first."""

    def walk(parent: Pane) -> tuple[Pane, int, Split] | None:
        division = parent.division
        if division is None:
            return None
        for index, child in enumerate(parent.children):
            if child is pane:
                return parent, index, division
            found = walk(child)
            if found is not None:
                return found
        return None

    for held in tree:
        found = walk(held)
        if found is not None:
            return found
    return None


@dataclass(frozen=True)
class Split:
    """How a pane's rectangle divides: one child per weight.

    Weights are shares (``(2, 1)`` gives twice the cells), ``min_size`` floors
    each child, and children abut -- a divider is chrome, not a gap."""

    axis: Axis
    weights: tuple[float, ...]
    min_size: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.axis, Axis) or self.axis not in (Axis.X, Axis.Y):
            raise ValueError(f"split axis must be Axis.X or Axis.Y, got {self.axis!r}")
        if not self.weights:
            raise ValueError("a split needs at least one weight")
        if any(weight < 0 for weight in self.weights):
            raise ValueError(f"split weights must not be negative, got {self.weights!r}")
        if sum(self.weights) <= 0:
            raise ValueError(f"split weights must share some cells, got {self.weights!r}")
        if self.min_size < 0:
            raise ValueError(f"min_size must not be negative, got {self.min_size!r}")

    def rects(self, rect: Rect) -> tuple[Rect, ...]:
        """Divide ``rect`` into one rectangle per weight, in order; a tiling never
        overlaps or leaves a hole."""
        span = rect.width if self.axis is Axis.X else rect.height
        sizes = _ratio_sizes(span, self.weights, self.min_size)
        rects: list[Rect] = []
        at = 0
        for size in sizes:
            taken = max(0, min(size, span - at))
            if self.axis is Axis.X:
                rects.append(Rect(x=rect.x + at, y=rect.y, width=taken, height=rect.height))
            else:
                rects.append(Rect(x=rect.x, y=rect.y + at, width=rect.width, height=taken))
            at += taken
        return tuple(rects)


@dataclass(eq=False)
class Pane:
    """One pane of a frame: its rectangle and the viewport laid out inside it.

    A pane is a runtime object: retile, split and close mutate it in place, so a
    host's handle keeps its identity across every change."""

    id: str
    rect: Rect
    viewport: Viewport
    chrome: tuple = ()
    division: Split | None = None
    children: tuple[Pane, ...] = ()
    _frame: Frame | None = field(default=None, compare=False, repr=False)
    #: Derived cache: the pane's chrome negotiation over one ``(rect, chrome)``
    #: pair -- both immutable values of the pane, so a retile or a registration
    #: invalidates the memo by construction.  Invisible to eq/hash/repr.
    _negotiation: tuple[Rect, tuple, Rect, tuple] | None = field(
        default=None, compare=False, repr=False
    )

    @property
    def document(self) -> Document:
        """The document this pane is a window over."""
        return self.viewport.document

    @property
    def scroll(self) -> Scroll:
        """The pane's immutable scroll value, delegated to its viewport."""
        return self.viewport.scroll

    def scroll_to(self, offset: int) -> bool:
        """Scroll the pane's viewport to ``offset``; whether it moved."""
        return self.viewport.scroll_to(offset)

    def scroll_by(self, delta: int) -> bool:
        """Scroll the pane's viewport ``delta`` rows (signed); whether it moved."""
        return self.viewport.scroll_by(delta)

    # -- the document facade ------------------------------------------------------

    def add(
        self,
        component,
        *,
        id: str | None = None,
        placement: Placement = Placement.FLOW,
        sizing: Sizing = Sizing.NATURAL,
    ) -> Section:
        """Append a block to this pane's document; ``placement``/``sizing`` forward
        unchanged (``FLOW`` is the body, ``TOP``/``BOTTOM`` the fixed bands)."""
        return self.document.add(
            component, id=id, placement=placement, sizing=sizing
        )

    def fill(self, component) -> Section:
        """Make ``component`` this pane's fill, owning the remaining height.

        The document is cleared first: a fill is the pane's whole content, and a
        flow section after it is refused."""
        for block in self.document.blocks():
            self.document.remove(block.id)
        return self.document.add(component, sizing=Sizing.FILL)

    def get(self, id: str) -> Section:
        """The block with ``id`` in this pane's document (``KeyError`` when missing)."""
        return self.document.get(id)

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` from this pane's document."""
        return self.document.remove(id)

    def add_chrome(self, chrome: Chrome) -> None:
        """Register ``chrome`` on the pane, inside earlier bands; the divider is
        negotiated outermost. Registration bumps the frame revision."""
        self.chrome = self.chrome + (chrome,)
        if self._frame is not None:
            self._frame._touch()

    def remove_chrome(self, chrome: Chrome) -> None:
        """Unregister ``chrome`` by identity; a missing band raises ``ValueError``,
        because a silent miss would hide a wrong detach."""
        kept = tuple(c for c in self.chrome if c is not chrome)
        if len(kept) == len(self.chrome):
            raise ValueError(f"chrome is not registered on pane {self.id!r}: {chrome!r}")
        self.chrome = kept
        if self._frame is not None:
            self._frame._touch()

    def _negotiated(self) -> tuple[Rect, tuple[tuple[Chrome, int, int], ...]]:
        """Memoized on ``(rect, chrome)`` -- both immutable, so a retile or a
        registration invalidates by construction."""
        memo = self._negotiation
        if memo is not None and memo[0] == self.rect and memo[1] is self.chrome:
            return memo[2], memo[3]
        inner, granted = _negotiate(self.rect, self.chrome)
        granted = tuple(granted)
        self._negotiation = (self.rect, self.chrome, inner, granted)
        return inner, granted

    @property
    def inner_rect(self) -> Rect:
        """The rectangle the pane's viewport lays out in, chrome subtracted."""
        return self._negotiated()[0]

    def band(self, chrome: Chrome) -> Rect | None:
        """The rectangle this pane's negotiation granted ``chrome``, or ``None`` when
        not held or clipped away. Body-scoped bands clip to the last composed
        window, so a press test matches the painted strip."""
        for held, take, offset in self._negotiated()[1]:
            if held is not chrome:
                continue
            if take <= 0:
                return None
            band = _band_of(self.rect, chrome.edge, take, offset)
            if chrome.scope == "pane":
                return band
            frame = self._frame
            layout = None if frame is None else frame.pane_layout(self.id)
            return None if layout is None else _body_band(band, layout)
        return None

    # -- the split ---------------------------------------------------------------

    def split(
        self,
        axis: Axis,
        *,
        weights: tuple[float, ...] = (1, 1),
        min_size: int = 1,
    ) -> tuple[Pane, ...]:
        """Divide this pane into one child per weight; return the children.

        The first child inherits id, viewport and chrome; later children open empty
        documents. Bumps the frame revision; splitting twice raises ``RuntimeError``."""
        if self.division is not None:
            raise RuntimeError(f"pane {self.id!r} is already split")
        frame = self._frame
        if frame is not None and frame.is_dock(self):
            raise RuntimeError(f"pane {self.id!r} is a dock: docks do not split")
        division = Split(axis, weights, min_size)
        children = tuple(
            replace(self, rect=rect, division=None, children=())
            if index == 0
            else Pane(
                frame.next_pane_id() if frame is not None else _next_fallback_pane_id(),
                rect,
                Viewport(Document()),
                _frame=frame,
            )
            for index, rect in enumerate(division.rects(self.rect))
        )
        self.division = division
        self.children = children
        if frame is not None:
            frame._touch()
        return children

    # -- the un-split --------------------------------------------------------------

    def close(self) -> None:
        """Close this leaf: it leaves its parent's tiling for good.

        The parent re-divides over survivors and collapses to the survivor's window
        when one remains, keeping its own id so a host's id never moves. The
        divider of the gap dies with the adjacency, and focus falls to the pane now
        occupying the rectangle. A root, a container, or a repeat raises."""
        frame = self._frame
        if frame is None:
            raise RuntimeError(f"pane {self.id!r} is held by no frame")
        if frame.is_dock(self):
            raise RuntimeError(f"pane {self.id!r} is a dock: docks do not close")
        if self.children:
            raise RuntimeError(
                f"pane {self.id!r} is a split: close a leaf, not a container"
            )
        if any(top is self for top in frame.roots):
            raise RuntimeError(
                f"pane {self.id!r} is the frame's root: a frame without panes "
                "has no composition"
            )
        home = _split_holding(self, frame.roots)
        if home is None:
            raise RuntimeError(
                f"pane {self.id!r} is held by no split: it left the tiling "
                "already (a close is not repeatable)"
            )
        parent, index, division = home
        edge = "right" if division.axis is Axis.X else "bottom"
        siblings = parent.children
        # The divider of the gap the closed pane leaves dies with its
        # adjacency: the pane before the gap gives it back.  The closed
        # pane's own chromes -- the divider of the gap after it among them
        # -- die with the pane itself.
        if index > 0:
            _strip_divider(siblings[index - 1], edge)
        survivors = siblings[:index] + siblings[index + 1 :]
        if len(survivors) > 1:
            trimmed = replace(
                division,
                weights=division.weights[:index] + division.weights[index + 1 :],
            )
            parent.division = trimmed
            parent.children = survivors
            for child, rect in zip(
                survivors, trimmed.rects(parent.rect), strict=True
            ):
                child._place(rect)
            fallback = survivors[min(index, len(survivors) - 1)]
        else:
            # one survivor (or none, from a one-child split): the parent
            # collapses back to a leaf, its own id and rectangle kept and
            # the survivor's window taken.  The survivor is either the pane
            # before the gap, whose divider was just stripped, or a last
            # child, which never registered one.
            survivor = survivors[0] if survivors else None
            parent.division = None
            parent.children = ()
            if survivor is not None:
                parent.viewport = survivor.viewport
                parent.chrome = survivor.chrome
                if survivor.division is not None:
                    # The survivor is itself a split container: the parent
                    # adopts the whole subtree, not just its (unused) window.
                    # Re-divide it over the parent's own rectangle so no
                    # child keeps a rectangle from the swallowed subtree.
                    parent.division = survivor.division
                    parent.children = survivor.children
                    for child, rect in zip(
                        survivor.children,
                        survivor.division.rects(parent.rect),
                        strict=True,
                    ):
                        child._place(rect)
            fallback = parent
        focused_id = frame.focused_id
        if focused_id is not None and frame.pane(focused_id) is None:
            # The focused id died -- with the closed pane, or with a
            # collapsed child's -- so focus falls to the pane that now
            # occupies that rectangle.
            frame.focus(fallback)
        frame._touch()  # the tree changed: a cached retile re-runs on it

    # -- the tiling walk ----------------------------------------------------------

    def _place(self, rect: Rect) -> None:
        """Rewrite the rectangle in place and re-derive children; a retile changes
        geometry, never structure."""
        self.rect = rect
        division = self.division
        if division is not None:
            for child, child_rect in zip(
                self.children, division.rects(rect), strict=True
            ):
                child._place(child_rect)

    def focus(self) -> None:
        """Make this the frame's focused pane, the one input routes to; a pane no
        frame holds raises ``RuntimeError``."""
        frame = self._frame
        if frame is None:
            raise RuntimeError(f"pane {self.id!r} is held by no frame")
        frame.focus(self)

    def __repr__(self) -> str:
        children = len(self.children)
        return f"Pane({self.id!r}, {self.rect.width}x{self.rect.height}, {children} split)"


def splice_row(base: Line, line: Line, x: int, width: int, frame_width: int) -> Line:
    """Write ``line``'s cells into ``base``'s columns ``[x, x + width)``.

    Every writer into a frame row runs through here so a row stays an exactly
    ``frame_width``-column grid: the window is cut/padded, all other cells are
    kept, and writers therefore compose in any order. A whole-row window is
    handed through unsliced."""
    if x == 0 and width == frame_width:
        return line
    text = base.text
    if _whole_cut(base) and base.width <= x and base.width <= x + width:
        left = base.fill(x)  # the whole base sits left of the window
        right = Line.from_text(" " * (frame_width - x - width))
    else:
        start_at, end_at, frame_at = index_bounds_at_columns(
            text, x, x + width, frame_width
        )
        left = slice_line(base, 0, start_at).fill(x)
        right = slice_line(base, end_at, frame_at).fill(frame_width - x - width)
    if width > 0 and _whole_cut(line) and line.width <= width:
        middle = line.fill(width)  # the line fits the window: the cut is it
    else:
        middle = cut_line(line, 0, width).fill(width)
    return left + middle + right


def _whole_cut(line: Line) -> bool:
    """Whether a cut past the row's end returns the row unchanged: no tab, no
    zero-width character, no empty segment."""
    text = line.text
    return (
        "\t" not in text
        and len(text) <= line.width
        and all(segment.text for segment in line.segments)
    )


def _negotiate(
    rect: Rect, chromes: Sequence[Chrome]
) -> tuple[Rect, list[tuple[Chrome, int, int]]]:
    """Subtract chrome budgets from ``rect``; the remainder is the viewport's.

    A ``SEPARATOR_CHROME_NAME`` band is negotiated first so the divider stacks
    outermost; budgets never shrink the viewport below one cell per axis."""
    room_width = max(0, rect.width - 1)  # shared by the left and right edges
    room_height = max(0, rect.height - 1)  # shared by the top and bottom ones
    left = right = top = bottom = 0
    granted: list[tuple[Chrome, int, int]] = []
    # The divider stacks outermost on its edge -- by name, whatever else was
    # registered and whenever -- so it is negotiated first and the other
    # bands sit inside it.  ``sorted`` is stable, so a group's internal
    # order is preserved: registration order within each.
    stacked = sorted(chromes, key=lambda band: band.name != SEPARATOR_CHROME_NAME)
    for chrome in stacked:
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
    inner = Rect(x=rect.x + left, y=rect.y + top, width=rect.width - left - right, height=rect.height - top - bottom)
    return inner, granted


def _band_of(rect: Rect, edge: str, take: int, offset: int) -> Rect:
    """The rectangle a granted band holds; one derivation shared by the painter
    and every reader of the geometry."""
    if edge == "left":
        return Rect(x=rect.x + offset, y=rect.y, width=take, height=rect.height)
    if edge == "right":
        return Rect(x=rect.right - offset - take, y=rect.y, width=take, height=rect.height)
    if edge == "top":
        return Rect(x=rect.x, y=rect.y + offset, width=rect.width, height=take)
    return Rect(x=rect.x, y=rect.bottom - offset - take, width=rect.width, height=take)


def _body_band(band: Rect, layout: ScreenLayout) -> Rect | None:
    """Clip a body-scoped band to the layout's scrolling window; ``None`` when the
    window has no rows."""
    start = min(max(0, layout.viewport_start), band.height)
    height = max(0, min(len(layout.body_rows), band.height - start))
    if height == 0:
        return None
    return Rect(x=band.x, y=band.y + start, width=band.width, height=height)


def _plan_chrome(
    plan: list[list[tuple[int, int, Line]]],
    pane: Pane,
    granted: Sequence[tuple[Chrome, int, int]],
    layout: ScreenLayout,
) -> None:
    """Record the granted strips into the row plan, clipped to each grant; strips
    paint last over content they share rows with."""
    for chrome, take, offset in granted:
        if take <= 0:
            continue  # the no-op seam: a zero-size chrome is never painted
        band = _band_of(pane.rect, chrome.edge, take, offset)
        if chrome.scope == "body":
            band = _body_band(band, layout)
            if band is None:
                continue  # no window to decorate: nothing to paint
        length = band.height if chrome.edge in ("left", "right") else band.width
        strip = chrome.paint(layout, length)[: band.height]
        for index, line in enumerate(strip):
            row = band.y + index
            if 0 <= row < len(plan):
                plan[row].append((band.x, band.width, line))


@dataclass(frozen=True)
class FrameSpan:
    """One pane's claim on columns ``[start, end)`` of one screen row; ``block_id``
    is ``None`` for a row no block owns."""

    pane_id: str
    block_id: str | None
    row_in_block: int
    start: int
    end: int


@dataclass(frozen=True)
class FrameTable:
    """The frame's ownership: per screen row, the column spans panes claim."""

    rows: tuple[tuple[FrameSpan, ...], ...]

    def resolve(self, row: int, col: int) -> FrameSpan | None:
        """The span owning cell ``(col, row)``, or ``None``; strict on both axes, never
        snapping to the nearest pane."""
        if not 0 <= row < len(self.rows):
            return None
        for span in self.rows[row]:
            if span.start <= col < span.end:
                return span
        return None


class Frame:
    """A tiling of panes over one screen, composed into a painting target.

    Holds the pane tree plus the last composition's layouts and ownership
    table, and an overlay registry that paints last. Docks join the table but
    take neither focus nor splits."""

    def __init__(
        self,
        panes: Iterable[Pane] = (),
        *,
        docks: Mapping[str, Pane] | None = None,
    ) -> None:
        self._panes: tuple[Pane, ...] = tuple(panes)
        self._docks: dict[str, Pane] = dict(docks or {})
        for edge in self._docks:
            if edge not in DOCK_EDGES:
                raise ValueError(
                    f"dock edge must be one of {DOCK_EDGES}, got {edge!r}"
                )
        # The layout currently being painted: the last compose's product, the
        # running target while apply_overlays runs the registry (see the
        # layout property).
        self._painting: ScreenLayout | None = None
        self._pane_layouts: tuple[ScreenLayout, ...] = ()
        self._region_order: tuple[Pane, ...] = ()
        self._table: FrameTable | None = None
        # pane id -> the rect its rows were laid out at (chrome subtracted):
        # where a pane-relative overlay splices its rewrite back.
        self._placements: dict[str, Rect] = {}
        self._size: tuple[int, int] | None = None
        #: ``(layer index, overlay)`` pairs, in registration order; painting
        #: walks a stable sort by layer, so the z-order is explicit and ties
        #: keep the order they were registered in.
        self._overlays: list[tuple[int, Overlay]] = []
        self._focused_id: str | None = None
        #: The monotonic counter new split panes take their ids from: an id a
        #: pane ever held is never handed out again.
        self._pane_counter = 0
        #: Called after every structural mutation (split/close/chrome/dock/
        #: overlay).  The driver points this at its dirty signal, so a host
        #: never follows a frame mutation with a manual refresh().
        self.on_change: Callable[[], None] | None = None
        #: The per-row write plans the last composition ran, keyed by
        #: ``(width, steps)`` and holding the row each built -- the memo
        #: :meth:`compose` replaces whole each frame, so it never outlives
        #: one composition plus the reuse it feeds (see that docstring).
        self._row_memo: dict[tuple, Line] = {}
        #: The composition's per-row buffers -- the write plan and the
        #: ownership claims -- owned by the frame and reused between
        #: compositions: at an unchanged height every row is cleared in
        #: place and refilled, at a new height they are rebuilt to it.  The
        #: containers are the frame's for its whole life; the row contents
        #: are rebuilt every composition (see :meth:`compose`).
        self._plan_rows: list[list[tuple[int, int, Line]]] = []
        self._table_rows: list[list[FrameSpan]] = []
        #: How many structural mutations the frame has seen (:attr:`revision`).
        self._revision = 0
        self._adopt()

    @property
    def revision(self) -> int:
        """How many structural mutations the frame has seen.

        Split, close, chrome and overlay registration bump it so an owner caching a
        retile can tell the tree changed; retile and content changes do not."""
        return self._revision

    def _touch(self) -> None:
        """Record one structural mutation and notify the owner."""
        self._revision += 1
        if self.on_change is not None:
            self.on_change()

    # -- the tiling ------------------------------------------------------------

    def _adopt(self) -> None:
        """Point every held pane at this frame; idempotent."""

        def walk(pane: Pane) -> None:
            pane._frame = self
            for child in pane.children:
                walk(child)

        for pane in self._panes:
            walk(pane)
        for pane in self._docks.values():
            walk(pane)

    def _leaves(self) -> tuple[Pane, ...]:
        """The composing content panes: the tiling's leaves, in paint order."""
        out: list[Pane] = []

        def walk(pane: Pane) -> None:
            if pane.children:
                for child in pane.children:
                    walk(child)
            else:
                out.append(pane)

        for pane in self._panes:
            walk(pane)
        return tuple(out)

    @property
    def panes(self) -> tuple[Pane, ...]:
        """The content panes, in the order the tiling paints them."""
        return self._leaves()

    @property
    def roots(self) -> tuple[Pane, ...]:
        """The frame's top-level panes, in tiling order."""
        return self._panes

    @property
    def docks(self) -> dict[str, Pane]:
        """The frame's docks, keyed by edge (a copy: mutating it changes nothing)."""
        return dict(self._docks)

    def dock(self, edge: str) -> Pane | None:
        """The dock pinned against ``edge``, or ``None``."""
        return self._docks.get(edge)

    def set_dock(self, edge: str, pane: Pane | None) -> None:
        """Pin ``pane`` against ``edge`` (``None`` releases it); a dock joins the
        ownership table but takes no focus."""
        if edge not in DOCK_EDGES:
            raise ValueError(f"dock edge must be one of {DOCK_EDGES}, got {edge!r}")
        if pane is None:
            self._docks.pop(edge, None)
        else:
            self._docks[edge] = pane
        self._adopt()
        self._touch()

    @property
    def rect(self) -> Rect | None:
        """The bounding rectangle of the tiling, or ``None`` when empty."""
        regions = (*self._leaves(), *self._composing_docks())
        if not regions:
            return None
        left = min(pane.rect.x for pane in regions)
        top = min(pane.rect.y for pane in regions)
        right = max(pane.rect.right for pane in regions)
        bottom = max(pane.rect.bottom for pane in regions)
        return Rect(x=left, y=top, width=right - left, height=bottom - top)

    def next_pane_id(self) -> str:
        """Allocate the next ``pane-N`` id; ids are monotonic and never reused."""
        self._pane_counter += 1
        return f"pane-{self._pane_counter}"

    def is_dock(self, pane: Pane) -> bool:
        """Whether ``pane`` is one of the frame's docks (never a window)."""
        return any(held is pane for held in self._docks.values())

    def pane(self, pane_id: str) -> Pane | None:
        """The pane with ``pane_id``, or ``None``; content panes and docks are both
        addressable."""
        for pane in (*self._leaves(), *self._docks.values()):
            if pane.id == pane_id:
                return pane
        return None

    @property
    def focused_pane(self) -> Pane | None:
        """The pane input routes to: the first, until :meth:`focus` moves it; a dock
        never holds focus."""
        if self._focused_id is not None:
            found = self.pane(self._focused_id)
            if found is not None and not self.is_dock(found):
                return found
        panes = self._leaves()
        return panes[0] if panes else None

    @property
    def focused_id(self) -> str | None:
        """The id focus is keyed on, or ``None``; the raw record :attr:`focused_pane`
        resolves."""
        return self._focused_id

    def focus(self, pane: Pane | str) -> None:
        """Make ``pane`` (or the pane with that id) focused; an unknown pane or a dock
        raises ``ValueError``."""
        pane_id = pane if isinstance(pane, str) else pane.id
        found = self.pane(pane_id)
        if found is None:
            raise ValueError(
                f"unknown pane {pane_id!r}: the frame holds {[p.id for p in self._leaves()]}"
            )
        if self.is_dock(found):
            raise ValueError(
                f"the dock {pane_id!r} takes no focus: it is a footer, not a window"
            )
        self._focused_id = pane_id

    def retile(
        self,
        rect: Rect,
        *,
        docks: Mapping[str, Rect | None] | None = None,
    ) -> None:
        """Re-derive every pane's rectangle in place; ids, viewports, chrome and focus
        survive the retile."""
        for pane in self._panes:
            pane._place(rect)
        for edge, dock in self._docks.items():
            placement = None if docks is None else docks.get(edge)
            dock._place(placement if placement is not None else Rect(x=0, y=0, width=0, height=0))
        self._adopt()

    def region(self, pane_id: str) -> Rect | None:
        """The rectangle a pane's viewport was laid out in, chrome subtracted;
        ``None`` before the first composition."""
        return self._placements.get(pane_id)

    # -- composition -------------------------------------------------------------

    def compose(self, width: int, height: int) -> ScreenLayout:
        """Lay every pane out inside its rectangle and splice one screen.

        Per region: negotiate chrome, lay out the viewport in the remainder, splice
        content rows, then granted strips. Rows are memoized on ``(width, steps)``
        so an unchanged or shifted row is reused, and a single whole-width write
        passes through unspliced."""
        regions = self._regions()
        # The per-row write plan and the ownership claims, assembled in the
        # composition order the sequential splice ran in: region by region,
        # a pane's own rows first, its granted strips over them.  The two
        # containers are the frame's buffers between compositions: at an
        # unchanged height each row is cleared in place (the allocation the
        # refills would otherwise pay every frame is paid once), at a new
        # height they are rebuilt to it.  Only the row contents are per-frame.
        if len(self._plan_rows) == height:
            for plan_row in self._plan_rows:
                plan_row.clear()
            for table_row in self._table_rows:
                table_row.clear()
        else:
            self._plan_rows = [[] for _ in range(height)]
            self._table_rows = [[] for _ in range(height)]
        plan = self._plan_rows
        table = self._table_rows
        layouts: list[ScreenLayout] = []
        placements: dict[str, Rect] = {}
        banded = False  # whether any chrome strip took cells of the frame
        for pane in regions:
            rect = pane.rect
            inner, granted = pane._negotiated()
            layout = pane.viewport.layout(inner.width, inner.height)
            layouts.append(layout)
            placements[pane.id] = inner
            for index, line in enumerate(layout.rows):
                row = inner.y + index
                if 0 <= row < height:
                    plan[row].append((inner.x, inner.width, line))
            _plan_chrome(plan, pane, granted, layout)
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
        # The single-pane pass-through: one region covering the whole frame
        # with no budgeted chrome composes to that pane's own layout, the
        # very object its viewport returned.
        passthrough = (
            len(regions) == 1
            and regions[0].rect == Rect(x=0, y=0, width=width, height=height)
            and not banded
        )
        if passthrough:
            composed = layouts[0]
            # Nothing to reuse and no plan to feed one: drop the memo rather
            # than pin a frame's rows behind a composition that will never
            # ask for them (the keys could never be read wrong -- the memo is
            # a pure function's -- only held).
            self._row_memo = {}
        else:
            memo = self._row_memo
            fresh: dict[tuple, Line] = {}
            rows = [Line() for _ in range(height)]
            for index, steps in enumerate(plan):
                if not steps:
                    continue  # no region wrote this row: it stays the blank row
                if len(steps) == 1:
                    x, take, line = steps[0]
                    if x == 0 and take == width:
                        # The row's only write covers it whole: splice_row
                        # hands the very line back (its own full-row early
                        # return -- a row the window spans completely is never
                        # sliced), so both the splice and the memo round-trip
                        # would build nothing the line is not already.  The
                        # row is the line as it stands, the split frame's
                        # full-width content rows chief among them.
                        rows[index] = line
                        continue
                key = (width, tuple(steps))
                row = memo.get(key)
                if row is None:
                    row = Line()
                    for x, take, line in steps:
                        row = splice_row(row, line, x, take, width)
                fresh[key] = row  # a hit is carried on, a miss enters the memo
                rows[index] = row
            self._row_memo = fresh
            composed = ScreenLayout(
                rows=tuple(rows), body_rows=(), width=width, height=height
            )
        self._painting = composed
        self._pane_layouts = tuple(layouts)
        self._region_order = regions
        self._table = FrameTable(rows=ordered)
        self._placements = placements
        self._size = (width, height)
        return composed

    def _composing_docks(self) -> tuple[Pane, ...]:
        """The docks that claim cells: empty rectangles compose nothing."""
        return tuple(
            dock
            for edge in DOCK_EDGES
            if (dock := self._docks.get(edge)) is not None
            and dock.rect.width > 0
            and dock.rect.height > 0
        )

    def _regions(self) -> tuple[Pane, ...]:
        """What composes: the content leaves, then the docks (top, then bottom)."""
        return (*self._leaves(), *self._composing_docks())

    @property
    def layout(self) -> ScreenLayout | None:
        """The layout the frame is painting, or ``None`` before composition; overlays
        advance it as each hands back the rows the next one paints over."""
        return self._painting

    @property
    def table(self) -> FrameTable | None:
        """The ownership table of the last composition, or ``None``."""
        return self._table

    # -- overlays ------------------------------------------------------------------

    @property
    def overlays(self) -> tuple[Overlay, ...]:
        """The overlay registry, in registration order (not paint order)."""
        return tuple(overlay for _layer, overlay in self._overlays)

    def add_overlay(self, overlay: Overlay, *, layer: str = "overlay") -> None:
        """Append ``overlay`` on ``layer`` (one of ``LAYERS``); painting is a stable
        sort by layer, so ties keep registration order."""
        if layer not in LAYERS:
            raise ValueError(f"overlay layer must be one of {LAYERS}, got {layer!r}")
        self._overlays.append((LAYERS.index(layer), overlay))
        self._touch()

    def remove_overlay(self, overlay: Overlay) -> None:
        """Unregister ``overlay`` by identity; a missing overlay raises
        ``ValueError``."""
        kept = [
            (layer, held) for layer, held in self._overlays if held is not overlay
        ]
        if len(kept) == len(self._overlays):
            raise ValueError(f"overlay is not registered on the frame: {overlay!r}")
        self._overlays = kept
        self._touch()

    def apply_overlays(self, layout: ScreenLayout) -> ScreenLayout:
        """Run the overlay registry over ``layout``, back to front by layer."""
        return apply_overlays(self, layout)

    def pane_layout(self, pane_id: str) -> ScreenLayout | None:
        """The layout :meth:`compose` laid out for the pane, or ``None``."""
        for pane, layout in zip(
            self._region_order, self._pane_layouts, strict=True
        ):
            if pane.id == pane_id:
                return layout
        return None

    def with_pane_rows(self, pane_id: str, rows: Sequence[Line]) -> ScreenLayout | None:
        """The layout being painted, with one pane's rows spliced back at its
        placement. Only ``placement.height`` rows are written, so a rewrite never
        bleeds into the pane below."""
        layout = self._painting
        placement = self._placements.get(pane_id)
        if layout is None or placement is None or self._size is None:
            return layout
        if placement.height <= 0:
            return layout  # a pane with no rows hosts no rewrite
        pane_layout = self.pane_layout(pane_id)
        if pane_layout is not None and rows is pane_layout.rows:
            return layout  # nothing was rewritten: the pane's own rows stand
        width, _ = self._size
        spliced = list(layout.rows)
        for index, line in enumerate(rows[: placement.height]):
            row = placement.y + index
            if 0 <= row < len(spliced):
                spliced[row] = splice_row(
                    spliced[row], line, placement.x, placement.width, width
                )
        return replace(layout, rows=spliced)

    def __repr__(self) -> str:
        docks = f", docks={sorted(self._docks)}" if self._docks else ""
        return f"Frame({len(self._leaves())} panes{docks})"


class _ChromeHost(Protocol):
    """The two live values the separator reads (the driver satisfies this)."""

    @property
    def frame(self) -> Frame: ...

    @property
    def theme(self) -> Theme: ...


class Separator:
    """The 1-cell divider between two split panes: chrome, themed by focus.

    The cell belongs to the pane before the gap -- budgeted, never a gap -- and
    reads the host's live theme and focus at paint time."""

    __slots__ = ("_after_id", "_before_id", "_host", "_strip_cache", "chrome")

    def __init__(
        self, host: _ChromeHost, before_id: str, after_id: str, edge: str
    ) -> None:
        self._host = host
        self._before_id = before_id
        self._after_id = after_id
        self.chrome = Chrome(edge, 1, self._paint, name=SEPARATOR_CHROME_NAME)
        # The last strip painted and the state it was painted from: the memo
        # of :meth:`_paint`, keyed by the edge, the length and the style.
        self._strip_cache: tuple[tuple, tuple[Line, ...]] | None = None

    def _accent(self) -> bool:
        """Whether either divided pane holds focus."""
        focused = self._host.frame.focused_pane
        return focused is not None and focused.id in (self._before_id, self._after_id)

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip, resolved style repeated; memoized on ``(edge, length, style)``
        so a focus or theme change rebuilds and nothing else does."""
        style = self._resolve()
        key = (self.chrome.edge, length, style)
        cached = self._strip_cache
        if cached is not None and cached[0] == key:
            return list(cached[1])
        if self.chrome.edge in ("left", "right"):
            strip = tuple(Line.filled(1, style) for _ in range(length))
        else:
            strip = (Line.filled(length, style),)
        self._strip_cache = (key, strip)
        return list(strip)

    def _resolve(self) -> Style:
        """The cell's style: the host theme's accent beside focus, else its border."""
        theme = self._host.theme
        return theme.content.accent if self._accent() else theme.borders.base

    def __repr__(self) -> str:
        return f"Separator({self._before_id!r}|{self._after_id!r})"
