"""The frame: rects, the split algebra, and the multi-pane compositor.

Everything that claims screen space partitions one screen through this
module.  A :class:`Rect` is a rectangle of that screen; :meth:`Split.rects`
divides one into a tiling -- proportional to the split's ratios, with a
``min_size`` floor -- and a :class:`Frame` composes its :class:`Pane`
values -- each a rectangle with a viewport laid out inside it and the
chrome bands it carries -- into one painting target plus the ownership
table that routes a screen cell back to its pane and its document address.

A **split** is a :class:`Split` value a pane holds: orientation, ratios and
``min_size``.  The tiling is
therefore structure, not geometry -- :meth:`Frame.retile` re-divides the
same tree onto a new frame rectangle, and each pane keeps its id, its
viewport, its chrome registry and its focus target across the change, so
an owner retiles without rebuilding anything.  A **band** is the one
pane-like rectangle the frame reserves beneath the pane area: it holds its
own viewport (the assembly tier's footer), paints last of the regions, and
joins the ownership table, but it takes neither focus nor splits.

The kernel owns the mechanics only: where the panes sit, which cells each
claims, which document address a claimed cell holds, which edge cells its
chrome reserves, and the order overlays paint in.  How many panes there
are and at what ratios is policy and lives one level up (in ``app.py`` and
its assembly peers); what a scrollbar looks like, how long a toast lives,
and which selection a highlight covers are policy too, and live in the
overlays and chrome renderers registered on the frame.

**The paint order.**  One composition runs, per region, chrome budgets
first (``Pane.add_chrome`` negotiation), then the pane's own content rows,
then the granted bands spliced back over them; the band's rows land last of
the regions; and the overlay registry (:meth:`Frame.add_overlay`) paints
over the composed frame after all of it.  A host routing input follows the
same order -- chrome, then overlays, then the panes' content -- as the
module docstring of :mod:`motui.app.scrollbar` spells out.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from .cell import Line, cut_line, slice_line
from .document import Document, Section
from .geom import Rect
from .layout import ScreenLayout, Viewport
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

#: What a split divides: ``"vertical"`` tiles the width into side-by-side
#: panes (a vertical divider between them), ``"horizontal"`` tiles the
#: height into stacked ones (a horizontal divider).
_ORIENTATIONS = ("vertical", "horizontal")

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

    ``edge`` names the pane edge the band sits on; ``size`` the cells it
    wants across that edge -- a ``"left"``/``"right"`` chrome is ``size``
    columns wide, a ``"top"``/``"bottom"`` one ``size`` rows tall.  ``scope``
    names the rectangle of the pane the band decorates, and with it the
    band's extent along its own edge: ``"pane"`` (the default) is the pane's
    whole rectangle, the band a divider or a border wants; ``"body"`` is the
    pane's scrolling window -- the rows the viewport laid out for the
    unpinned blocks -- which is the band a scrollbar wants, because the
    scroll state a bar maps *is* that window.  A body band is legal on a
    ``"left"``/``"right"`` edge only: a top/bottom band owns rows instead of
    sharing them, so it cannot sit on the window.

    ``paint`` renders the band: it takes the pane's own layout -- the scroll
    state among it, :attr:`~motui.kernel.viewport.ScreenLayout.offset` and
    ``total_rows`` -- and the strip's length along the band's other axis (the
    pane's height for a pane-scoped left/right band, the window's height for
    a body-scoped one; the pane's width for a top/bottom band), and hands
    back one row per cell of the strip, each exactly the band's width.  A
    painter therefore only ever paints cells the band holds: it never pads,
    and it never paints less than it is granted.  Painters are pure
    functions: no state, no clock, no input.

    The budget is the pane's rectangle for either scope: the band's ``size``
    cells are subtracted from the pane's edge, so the document re-wraps at
    the reduced width whichever region the band decorates.  The rows a body
    band does not span -- the pane's fixed regions -- therefore carry the
    band's column empty rather than at full width.

    ``name`` is an optional mark for *teardown* and for *stacking*, not for
    lookup: a close (:meth:`Pane.close`) strips a divider by it -- the one
    divider implementation, the kernel's themed
    :class:`~motui.kernel.chrome.Separator`, registers under
    :data:`SEPARATOR_CHROME_NAME` -- so the band that divides
    two panes dies with the adjacency it divides instead of being guessed at
    by its size or edge, and the same mark puts it first in negotiation
    (:func:`_negotiate`), so the divider stacks outermost on its edge
    whatever else the pane registered and whenever.  Every other band keeps
    registration order.  It defaults to the empty string, an unnamed band,
    which no close ever touches.

    ``size: 0`` is legal and means a no-op seam -- nothing is budgeted and
    nothing is painted, the shape a custom renderer grows from.  A band
    that would shrink the pane's viewport below one cell is clipped to what
    remains (see :meth:`Frame.compose`).
    """

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


def _ratio_sizes(span: int, ratios: Sequence[float], min_size: int) -> list[int]:
    """The cells each ratio takes of ``span``: proportional, then exact.

    A ratio's share is its weight over the sum (floor division, so a half
    cell is never invented), and the last ratio takes whatever the floors
    left -- unlike the widgets' flex division, which discards its
    remainder, because a frame's panes *partition* the screen and an
    untilted column would be a hole at its edge.  ``min_size`` then raises
    any share below it; a span that cannot host every pane at that floor
    clips the later ones away (the same overrun clip
    :meth:`Split.rects` applies to a size that overruns what remains).
    """
    total = sum(ratios)
    sizes = [int(span * ratio // total) for ratio in ratios]
    remainder = span - sum(sizes)
    if remainder:
        sizes[-1] += remainder
    if min_size:
        sizes = [max(size, min_size) for size in sizes]
    return sizes


def _strip_divider(pane: Pane, edge: str) -> None:
    """Unregister the divider ``pane`` carries on ``edge``, if it has one.

    The hygiene half of :meth:`Pane.close`, by name *and* edge and never
    by size: a scrollbar column is a 1-cell right-edge chrome too, and a
    teardown that guessed would strip the wrong band.  A pane holding no
    divider on that edge keeps its chrome exactly as it stands -- a last
    child holds none, its abutting neighbour's having died with the pane
    that registered it, and a split that left its panes abutting (the
    driver's ``separator=False``) registered none.  A miss is therefore
    **silent**, unlike :meth:`Pane.remove_chrome`'s ``ValueError``: a close
    *may* find no divider -- the adjacency it tears down may never have
    had one -- while ``remove_chrome`` is an explicit claim about what the
    pane carries.
    """
    kept = tuple(
        chrome
        for chrome in pane.chrome
        if not (chrome.name == SEPARATOR_CHROME_NAME and chrome.edge == edge)
    )
    if len(kept) != len(pane.chrome):
        pane.chrome = kept


def _split_holding(pane: Pane, tree: Sequence[Pane]) -> tuple[Pane, int, Split] | None:
    """The split that holds ``pane``, its position in it and its division.

    A pane carries no parent pointer -- the tree is the structure and panes
    are the runtime objects it holds -- so the search walks ``tree`` (the
    frame's top-level panes) down to the pane, the one depth-first descent
    a close pays.  ``None`` means no split holds it: a root, or a pane that
    already left the tiling.
    """

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
    """How a pane's rectangle divides: one child pane per ratio.

    ``orientation`` is the divider's axis and ``ratios`` the children's
    weights -- ``(2, 1)`` gives the first pane twice the cells of the
    second, ``(1, 1)`` halves it.  ``min_size`` is the floor each child is
    raised to.

    The children **abut**: the rectangles partition the span, so no cell
    between two panes is left unclaimed.  A divider is *chrome*, not a gap
    -- the driver's themed separator registers on the pane before the gap
    (:data:`SEPARATOR_CHROME_NAME`) and is budgeted from that pane's own
    rectangle, so it takes the last cell of the pane it divides.
    """

    orientation: str
    ratios: tuple[float, ...]
    min_size: int = 1

    def __post_init__(self) -> None:
        if self.orientation not in _ORIENTATIONS:
            raise ValueError(
                f"orientation must be 'vertical' or 'horizontal', got {self.orientation!r}"
            )
        if not self.ratios:
            raise ValueError("a split needs at least one ratio")
        if any(ratio < 0 for ratio in self.ratios):
            raise ValueError(f"split ratios must not be negative, got {self.ratios!r}")
        if sum(self.ratios) <= 0:
            raise ValueError(f"split ratios must share some cells, got {self.ratios!r}")
        if self.min_size < 0:
            raise ValueError(f"min_size must not be negative, got {self.min_size!r}")

    def rects(self, rect: Rect) -> tuple[Rect, ...]:
        """Divide ``rect`` into one rectangle per ratio, in order.

        The span is the rectangle's width for ``"vertical"`` and its height
        for ``"horizontal"``; the cross axis is inherited unchanged, each
        child's origin follows the children before it, and a size that
        overruns what remains is clipped -- a tiling never overlaps and
        never leaves a hole.
        """
        span = rect.width if self.orientation == "vertical" else rect.height
        sizes = _ratio_sizes(span, self.ratios, self.min_size)
        rects: list[Rect] = []
        at = 0
        for size in sizes:
            taken = max(0, min(size, span - at))
            if self.orientation == "vertical":
                rects.append(Rect(x=rect.x + at, y=rect.y, width=taken, height=rect.height))
            else:
                rects.append(Rect(x=rect.x, y=rect.y + at, width=rect.width, height=taken))
            at += taken
        return tuple(rects)


@dataclass(eq=False)
class Pane:
    """One pane of a frame: its rectangle and the viewport laid out inside it.

    ``chrome`` is the pane's edge budget -- the edge columns or rows
    reserved for scrollbars and rails, negotiated against the pane's inner
    rect by :meth:`Frame.compose`.  The divider is outermost by definition
    (negotiation puts a band named :data:`SEPARATOR_CHROME_NAME` first on
    its edge) and every other band stacks inward in registration order, the
    budgets adding per edge, so a rail beside a gutter is two chromes.
    Each band also names what it decorates (:attr:`Chrome.scope`): the
    pane's rectangle (a divider, a border) or its scrolling window (a
    scrollbar), which is why a bar's strip and a divider beside it can end
    at different rows on the same edge.

    ``division`` / ``children`` hold the pane's **split**, once it has one:
    a leaf pane holds neither, and :meth:`split` fills both in.  A split
    pane keeps its own id, viewport and chrome -- its first child inherits
    all three, so the document a host added and any chrome registered on it
    survive the division -- while the children after it open over fresh,
    empty documents the caller fills.  A split pane is a container, not a
    window: it composes nothing and takes no focus, the frame reaching its
    children instead.  :meth:`close` is the division's symmetric: a leaf
    leaves its parent's tiling for good, and with one survivor left the
    parent collapses back to a leaf, its own id and rectangle kept and the
    survivor's window taken (the id rule lives in that docstring).

    ``_frame`` is the frame that holds the pane (set when it joins one), the
    back-reference :meth:`focus` routes through.

    A pane is a **runtime object**, not a value: the frame retiles and
    re-divides it in place, split and close rewrite its structure, and a
    host's handle must keep addressing the same pane across every change
    (identity ``==``, the default the dataclass keeps with ``eq=False``).
    """

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
    def scroll_state(self):
        """The pane's scroll geometry, delegated to its viewport."""
        return self.viewport.scroll_state

    def scroll_to(self, offset: int) -> bool:
        """Scroll the pane's viewport to ``offset``; whether it moved.

        The write half of :class:`~motui.kernel.scroll.Scrollable`, delegated
        to the viewport -- so a pane is a scroll target wherever a viewport
        is (the App's wheel fallback and the scrollbar's ``Scrollable``
        door).
        """
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
        pin: str | None = None,
    ) -> Section:
        """Append a block to this pane's document (``Document.add``'s arguments)."""
        return self.document.add(component, id=id, pin=pin)

    def get(self, id: str) -> Section:
        """The block with ``id`` in this pane's document (``KeyError`` when missing)."""
        return self.document.get(id)

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` from this pane's document."""
        return self.document.remove(id)

    def add_chrome(self, chrome: Chrome) -> None:
        """Register ``chrome`` on the pane (inside the ones before it -- the
        divider excepted, the one band negotiation moves outermost).

        The one way chrome joins a pane after construction: a pane is a
        runtime object, and this is its registration-time mutation -- the same
        append the ``chrome=(...)`` constructor argument performs.  A retile
        rewrites the pane's rectangle in place (:meth:`Pane._place`) rather
        than rebuilding the pane, so the registration rides a resize with
        nothing to carry, and the frame's
        :attr:`~motui.kernel.frame.Frame.revision` bumps so an owner
        caching its retile recomposes.
        """
        self.chrome = self.chrome + (chrome,)
        if self._frame is not None:
            self._frame._touch()

    def remove_chrome(self, chrome: Chrome) -> None:
        """Unregister ``chrome`` from the pane -- the symmetric of ``add_chrome``.

        The mirror of the registration append, by identity: the pane gives
        the band's cells back, so its viewport lays out at the full width
        again on the next composition.  A chrome the pane does not hold
        raises ``ValueError`` -- an unregister is a claim about what the
        pane carries, and a silent miss would hide a controller removing
        the wrong band (``Document.remove`` raises for a missing block the
        same way).  A controller that may detach twice tests membership
        first, keeping its own detach idempotent.  The frame's
        :attr:`~motui.kernel.frame.Frame.revision` bumps, so an owner
        caching its retile recomposes.
        """
        kept = tuple(c for c in self.chrome if c is not chrome)
        if len(kept) == len(self.chrome):
            raise ValueError(f"chrome is not registered on pane {self.id!r}: {chrome!r}")
        self.chrome = kept
        if self._frame is not None:
            self._frame._touch()

    def _negotiated(self) -> tuple[Rect, tuple[tuple[Chrome, int, int], ...]]:
        """The pane's inner rectangle and chrome grants, negotiated once.

        :func:`_negotiate` is a pure function of the pane's rectangle and
        its chrome registry, and both are replaced rather than mutated here
        (a retile and a registration each hand the pane a fresh one), so the
        result is memoized on exactly those two: :meth:`Frame.compose` and
        :meth:`band` read the one derivation, and a grant cannot outlive the
        rectangle or the registry it was negotiated from.
        """
        memo = self._negotiation
        if memo is not None and memo[0] == self.rect and memo[1] is self.chrome:
            return memo[2], memo[3]
        inner, granted = _negotiate(self.rect, self.chrome)
        granted = tuple(granted)
        self._negotiation = (self.rect, self.chrome, inner, granted)
        return inner, granted

    @property
    def inner_rect(self) -> Rect:
        """The rectangle the pane's viewport lays out in, chrome subtracted.

        The one read for the viewport's own rectangle: the remainder of the
        pane's rectangle once every registered chrome has taken its edge
        budget -- the same negotiation :meth:`Frame.compose` runs, memoized
        here through :meth:`_negotiated`.  :meth:`band` is its complement:
        the inner rect shares no cell with any granted band, and each axis
        partitions into the edge bands and this rect between them.
        """
        return self._negotiated()[0]

    def band(self, chrome: Chrome) -> Rect | None:
        """The rectangle this pane's negotiation granted ``chrome``.

        The one read for "which cells did the kernel reserve for this band":
        the same negotiation :meth:`Frame.compose` ran -- the pane memoizes
        it on its rectangle and its chrome registry -- so a band's geometry
        -- a scrollbar's press test, say -- is the very rectangle the
        compositor paints, one derivation whatever else the pane stacked on
        that edge.  ``None`` when the pane does not hold the chrome, or its
        grant was clipped to nothing (the band routes and paints nothing
        alike).

        A ``"pane"``-scoped band spans the pane's rectangle, as it always
        has.  A ``"body"``-scoped band spans the pane's scrolling window, so
        it is clipped against the last layout the frame composed for this
        pane (:func:`_body_band`) -- and answers ``None`` until there is
        one, or when the window has no rows: a band with no window to
        decorate holds nothing, and saying so is what keeps a press test and
        the painted strip the same rectangle.
        """
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
        orientation: str,
        *,
        ratios: tuple[float, ...] = (1, 1),
        min_size: int = 1,
    ) -> tuple[Pane, ...]:
        """Divide this pane into one child per ratio; return the children.

        The same code path :meth:`~motui.app.TUI.split` calls: the
        division is recorded on the pane (:attr:`division` /
        :attr:`children`) so a later :meth:`Frame.retile` re-divides a new
        rectangle the same way, and the children are returned in paint
        order.  Two ratios give the ``(left, right)`` pair of a vertical
        split or the ``(top, bottom)`` pair of a horizontal one; more give
        one pane per ratio.

        The first child inherits this pane's id, viewport and chrome --
        splitting keeps the document a host already filled and any chrome
        registered on the pane -- and every child after it opens over a
        fresh, empty document (``child.document.add(...)``).  The children
        take the rectangles :meth:`Split.rects` derives from this pane's
        current one, so a split before the first paint is re-divided onto
        the live screen by that paint's retile.  The children join this
        pane's frame (when it has one) from birth -- the frame's own
        adoption walk re-marks every pane it holds at the next retile -- and
        the split bumps the frame's
        :attr:`~motui.kernel.frame.Frame.revision`, so a driver caching
        its retile re-divides the tree on the next frame.

        The children **abut** -- no cell is left between them; a divider is
        chrome, not a gap, and the one implementation is the kernel's themed
        :class:`~motui.kernel.chrome.Separator`, which
        :meth:`~motui.app.TUI.split` registers on the pane before each
        gap under :data:`SEPARATOR_CHROME_NAME` when its caller asks for a
        separator.  Splitting an already-split pane raises ``RuntimeError``.
        """
        if self.division is not None:
            raise RuntimeError(f"pane {self.id!r} is already split")
        frame = self._frame
        if frame is not None and frame.is_dock(self):
            raise RuntimeError(f"pane {self.id!r} is a dock: docks do not split")
        division = Split(orientation, ratios, min_size)
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
        """Close this leaf pane: it leaves its parent's tiling for good.

        The symmetric of :meth:`split`, and the kernel's only structural
        removal: a **leaf** (a pane with no children) leaves the split that
        holds it.  With siblings remaining the parent **re-divides** its
        rectangle over the survivors -- its ``ratios`` trimmed to the
        surviving count, in order, so a trimmed pair keeps the survivors'
        relative weights -- and when exactly one survivor remains the parent
        **collapses** to it, keeping its own id and its own rectangle and
        taking the survivor's window (its ``viewport``, and the ``chrome``
        and ``document`` that come with it): the walk a split ran, in
        reverse.  A one-child split collapses the same way, the parent
        resuming the leaf it was.

        Rectangles are rewritten in place (``_place``-style, the parent's
        division trimmed rather than the tree rebuilt) and the frame's
        :attr:`~motui.kernel.frame.Frame.revision` bumps, so a driver
        caching its tiling re-runs its retile and the next composition
        paints the new tiling: a collapsed pane takes the whole
        rectangle the split held, and the single-pane pass-through composes
        to its own layout again -- the transcript | preview split is gone
        the moment the preview closes.

        **The id rule.**  A pane's id is its identity in the frame -- what a
        host registers chrome on, what ``frame.focus`` keys, what
        ``frame.pane`` answers -- and a collapse keeps the *parent's*: a
        split's first child shared it already, so collapsing onto the first
        child is invisible to every id a host holds (the scrollbar on
        ``"primary"`` and the ``"primary"`` focus key both ride on), while a
        survivor that was a later child carries an id -- ``"pane-N"`` --
        that dies with the split, the parent's own surviving in its place
        (``frame.pane("pane-N")`` answers ``None`` from then on, and a
        focus keyed on it falls to the pane that took its rectangle).  A
        re-divide changes no id at all: the survivors keep the ones they
        were given at split time, so a trimmed set's numbering may start
        above zero.  Nothing is ever renumbered -- an id a host holds must
        not move under it.

        **The separator.**  The divider cell is chrome of the pane before
        the gap, so it dies with the adjacency it divides: the close strips,
        from the pane before the gap, the chrome the split's orientation
        names on that edge, identified by :attr:`Chrome.name`
        (:data:`SEPARATOR_CHROME_NAME`, the mark the driver's themed divider
        registers under) rather than by size or edge, which a scrollbar
        column shares; a miss is silent, since a split that left its panes
        abutting registered no divider.  The closed pane's own
        chromes die with it, and no divider is invented between the
        survivors -- closing the middle of three leaves the two survivors
        abutting, the honest reading of "that divider belonged to that
        adjacency"; a host wanting one back registers its own chrome on the
        pane now before the new gap.

        **Focus.**  If the focused pane closed -- its id died with it -- the
        focus falls to the pane that now occupies its rectangle: the
        collapsed parent, or the survivor that takes the closed child's
        place (the one now at that index, or the last survivor when the
        closed child was the last).

        A **root** pane -- one no split holds, the frame's own -- does not
        close: a frame without panes has no composition (``RuntimeError``).
        Closing a **container** (an already-split pane) raises the same
        way, as does closing twice: a close is a claim about a leaf the
        tiling still holds.
        """
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
        edge = "right" if division.orientation == "vertical" else "bottom"
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
                ratios=division.ratios[:index] + division.ratios[index + 1 :],
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
        """Take ``rect`` as this pane's rectangle and re-derive any children.

        The one structural mutation a retile makes: the tiling is structure,
        so a resize rewrites the rectangles and leaves every pane -- id,
        viewport, chrome, focus target -- exactly as it was.
        """
        self.rect = rect
        division = self.division
        if division is not None:
            for child, child_rect in zip(
                self.children, division.rects(rect), strict=True
            ):
                child._place(child_rect)

    def focus(self) -> None:
        """Make this the frame's focused pane, the one input routes to.

        Routes through the frame that holds the pane (``_frame``); a pane
        no frame holds raises ``RuntimeError``.  Focusing is the driver's
        to invalidate, so the next frame paints the change -- a divider
        accent follows its focus.
        """
        frame = self._frame
        if frame is None:
            raise RuntimeError(f"pane {self.id!r} is held by no frame")
        frame.focus(self)

    def __repr__(self) -> str:
        children = len(self.children)
        return f"Pane({self.id!r}, {self.rect.width}x{self.rect.height}, {children} split)"


def splice_row(base: Line, line: Line, x: int, width: int, frame_width: int) -> Line:
    """Write ``line``'s cells into ``base``'s columns ``[x, x + width)``.

    The one operation every writer into a frame row runs through -- the
    compositor placing a pane's rows, a granted chrome strip, a pane-relative
    overlay's rewrite, a toast band -- and the reason it is one operation is
    that a frame row is a **grid**: exactly ``frame_width`` columns, every
    pane and band occupying the columns of its own rectangle and nothing
    else.  So the window's cells come from ``line`` (cut to ``width``, padded
    out to it when the row is short), every other cell of ``base`` is kept
    where it stands, and the result is exactly ``frame_width`` columns wide
    whatever either row measured.  A row the window spans completely is
    handed through as it stands -- the compositor never slices a row it does
    not have to move, which is what keeps a single-pane frame composing to its
    pane's own layout.

    Addressing, not concatenation: because the base survives outside the
    window and the window is padded to its own width, the writers compose in
    any order, over however short an earlier row was.  A write that only cut
    and padded *around* its row would leave the window short, and the next
    write into the row would then drag the cells past it -- another pane's
    content, a scrollbar's column -- leftwards against the window's own tail.

    The base row's three cut points -- the window's start, its end and the
    frame's end -- are resolved in **one** walk, and each piece is cut with
    :func:`slice_line` at the resolved indices: a cut *is* ``slice_line`` at
    resolved indices, so the pieces are the very ones
    :func:`motui.kernel.lines.cut_line` hands back, and the row's prefix
    is walked once instead of three times.

    Three shapes are handed through without a cut, which is what keeps a
    chrome column beside a fitting row from walking the row at all: a
    base that ends at or before the window leaves *both* pieces beside it
    plain padding (no cell of the base is inside the window's span, and
    :meth:`~motui.kernel.lines.Line.fill` grows it to the same cells a
    slice would), and a line that already fits the window is its own
    middle piece ``fill``-ed to the window -- ``slice_line`` over the
    whole row would hand back the same segments.  Either shortcut is taken
    only for a row :func:`_whole_cut` vouches for, whose whole text is
    exactly what a cut past its end hands back.
    """
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
    """Whether a cut past the row's end hands the very row back.

    The question :func:`splice_row`'s shortcuts ask before they keep a row
    whole -- ``fill``-ed beside a window instead of sliced against it --
    and the three things a cut can still change:

    * a segment whose text came out empty is **dropped**;
    * a tab is normalized to spaces (the rule
      :func:`~motui.kernel.lines.wrap_line` shares);
    * the cut's boundaries are answered in **cells**, so a character
      carrying no cell of its own -- a combining mark, a zero-width joiner,
      a control -- would pull the boundary back before the text's end and
      leave the tail of the row out.  ``len(text) <= width`` is exactly
      "every character owns at least one cell", the shape whose cell
      boundaries are the text's own, and the test a row failing it takes
      the walk for.

    ``Line.text`` and ``Line.width`` are the row's cached views, so the
    test costs one scan of the text per splice -- against the three-piece
    walk it stands in for.
    """
    text = line.text
    return (
        "\t" not in text
        and len(text) <= line.width
        and all(segment.text for segment in line.segments)
    )


def _negotiate(
    rect: Rect, chromes: Sequence[Chrome]
) -> tuple[Rect, list[tuple[Chrome, int, int]]]:
    """Subtract the pane's chrome budgets from ``rect``; the remainder is the
    viewport's.

    Every chrome asks for ``size`` cells across its edge; the pane's
    budgets add per edge, and opposite edges both subtract.  A band named
    :data:`SEPARATOR_CHROME_NAME` is negotiated **first** on its edge, so
    the divider stacks outermost on the edge it divides -- by name, whatever
    else the pane registered and whenever -- and every other band follows in
    registration order.  A budget that would leave the viewport under one
    cell in either axis is clipped to what remains of that axis --
    first come, first served, the clipping a tiling applies to a size
    that overruns what remains -- so chrome never eats a pane's whole
    viewport (or
    squeezes one out of a pane too small to host it).  Chromes on one edge
    stack outward from it: each takes its cells beside the ones before it.

    Returns the inner rectangle the pane's viewport lays out in and, per
    chrome in negotiation order, the cells granted it (0 for a zero-size
    chrome or one clipped away) and its offset from the pane edge.
    """
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
    """The rectangle one granted chrome band holds of its pane.

    The placement :func:`_plan_chrome` writes through and
    :meth:`Pane.band` hands back -- one derivation, so a band's painter and
    every reader of its geometry (a scrollbar's press test) agree by
    construction, whatever else the pane stacked on that edge.
    """
    if edge == "left":
        return Rect(x=rect.x + offset, y=rect.y, width=take, height=rect.height)
    if edge == "right":
        return Rect(x=rect.right - offset - take, y=rect.y, width=take, height=rect.height)
    if edge == "top":
        return Rect(x=rect.x, y=rect.y + offset, width=rect.width, height=take)
    return Rect(x=rect.x, y=rect.bottom - offset - take, width=rect.width, height=take)


def _body_band(band: Rect, layout: ScreenLayout) -> Rect | None:
    """``band`` clipped to the layout's scrolling window -- a body band's extent.

    The window is the middle region of a :class:`ScreenLayout`: the rows
    between the fixed regions, ``viewport_start`` rows down and
    ``len(body_rows)`` tall.  A body-scoped band decorates exactly those
    rows, which is why both the compositor (:func:`_plan_chrome`) and the
    geometry read (:meth:`Pane.band`) clip through this one function.
    ``None`` for a window with no rows: a pane whose fixed regions fill it
    has nothing for a body band to sit on, so it paints and routes nothing.
    """
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
    """Record the pane's granted chrome strips into the frame row ``plan``.

    The write half of the compositor's chrome step, split off from the
    splice it used to run so a row's whole write list is assembled before
    any of it is applied (:meth:`Frame.compose`).  A band holds the pane
    edge its chrome named, stacked outward from that edge (the divider sits
    outermost, the bands after it beside it in negotiation order): a
    left/right chrome the columns at that side, a top/bottom one the rows at
    that end over the pane's whole width.  How far a left/right band reaches
    along the pane's rows is the band's ``scope``: the pane's whole height
    for ``"pane"``, the scrolling window only for ``"body"`` (clipped
    through :func:`_body_band`, the same derivation :meth:`Pane.band`
    answers).  The strip lands over whatever the pane's viewport painted
    beside it -- a left/right band shares its rows with the document, a
    top/bottom one owns its own -- so the bands paint last and never hide
    content they were not budgeted across.  ``length`` is the band's own
    extent along the other axis, so a painter draws every cell it owns and
    none it does not.  The strip is clipped to the cells actually granted (a
    painter declaring its full size over a clipped budget paints only the
    part that fits); a zero grant paints nothing.
    """
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

        Strict on both axes: a column must fall in a span's
        ``[start, start + width)`` interval, and a row must be one this
        composition painted.  A column outside every span of an owned row --
        left of the first, right of the last, or in a gap no pane claims --
        answers ``None``; the table never snaps to the nearest pane.
        """
        if not 0 <= row < len(self.rows):
            return None
        for span in self.rows[row]:
            if span.start <= col < span.end:
                return span
        return None


class Frame:
    """A tiling of panes over one screen, composed into a painting target.

    The frame holds its panes and, after a :meth:`compose`, what that
    composition produced: the :class:`~motui.kernel.viewport.ScreenLayout`
    to paint, the per-pane layouts an overlay composes over, and the
    ownership table a hit test routes through.  An ordered overlay registry
    (:meth:`add_overlay`) paints over the composed frame last, through
    :meth:`apply_overlays` -- the registry is the kernel's mechanism, the
    overlays' controllers are policy and live one level up.  It owns no
    scroll state (the panes' viewports do), no clock, and no focus policy
    beyond which pane :meth:`focus` names.

    Docks (:meth:`set_dock`) reserve the rows above and below the pane
    area: pane-like rectangles holding their own viewports, which paint
    after the content and join the ownership table -- so a header or footer
    is hit-testable and selectable exactly as a pane's rows are -- but which
    take neither focus (:attr:`focused_pane` never returns one, and
    :meth:`focus` refuses one) nor splits.
    """

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

        Every mutation that can change what a composition paints -- a
        :meth:`Pane.split` or a :meth:`Pane.close` in the tree, a chrome
        registration (:meth:`Pane.add_chrome` / :meth:`Pane.remove_chrome`),
        an overlay registration or the band -- bumps it, so an owner that
        caches a retile (the driver) can tell "the tree changed under me"
        from "the same tiling again".  Geometry is not structure: a
        :meth:`retile` to new rectangles does not bump it, and neither does
        a pane's content.
        """
        return self._revision

    def _touch(self) -> None:
        """Record one structural mutation and notify the owner (see :attr:`revision`)."""
        self._revision += 1
        if self.on_change is not None:
            self.on_change()

    # -- the tiling ------------------------------------------------------------

    def _adopt(self) -> None:
        """Point every pane the frame holds -- content and band alike -- at it.

        A pane carries the frame back-reference :meth:`Pane.focus` routes
        through, so a pane built for this frame (a split's children, a band
        handed over) becomes focusable the moment it joins.  Idempotent.
        """

        def walk(pane: Pane) -> None:
            pane._frame = self
            for child in pane.children:
                walk(child)

        for pane in self._panes:
            walk(pane)
        for pane in self._docks.values():
            walk(pane)

    def _leaves(self) -> tuple[Pane, ...]:
        """The content panes that compose: the tiling's leaves, in paint order."""
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
        """The content panes, in the order the tiling paints them.

        The leaves of the split tree, so a split parent -- which composes
        nothing and holds no viewport of its own -- is not among them.  The
        band is not among them either: it is a region of the frame, not a
        content pane.
        """
        return self._leaves()

    @property
    def roots(self) -> tuple[Pane, ...]:
        """The frame's top-level panes: the split tree's roots, in tiling order.

        What a close walks to find the split holding a pane, and what tells
        a root pane -- one no split holds, the frame's own -- from a nested
        leaf.  The windows that compose are :attr:`panes`.
        """
        return self._panes

    @property
    def docks(self) -> dict[str, Pane]:
        """The frame's docks, keyed by edge (a copy: mutating it changes nothing)."""
        return dict(self._docks)

    def dock(self, edge: str) -> Pane | None:
        """The dock pinned against ``edge``, or ``None``."""
        return self._docks.get(edge)

    def set_dock(self, edge: str, pane: Pane | None) -> None:
        """Pin ``pane`` against ``edge`` (``None`` releases that edge).

        A dock's rectangle is the driver's to set (:meth:`retile`), its rows
        its own viewport's, and its cells join the ownership table -- a
        footer block under the pointer resolves through
        :meth:`~motui.app.TUI.hit` exactly as a pane's does.  A dock handed
        over joins the frame's adoption walk here, and the frame's
        :attr:`revision` bumps.  Docks take no focus and never split.
        """
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
        """The bounding rectangle of the tiling, or ``None`` when empty.

        Every region belongs to the frame -- the content panes and the docks
        alike -- so this is the screen they cover, which is how an owner
        tells a retiled frame from a stale one and where a corner-anchored
        overlay paints.  An empty dock claims no cell and is left out.
        """
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
        """The pane with ``pane_id``, or ``None`` when the frame holds none.

        Content panes and docks are both addressable; a pane a split
        replaced keeps its id only through the child that inherited it.
        """
        for pane in (*self._leaves(), *self._docks.values()):
            if pane.id == pane_id:
                return pane
        return None

    @property
    def focused_pane(self) -> Pane | None:
        """The pane input routes to: the first, until :meth:`focus` moves it.

        A dock never holds focus -- it is a footer, not a document window
        -- so this is always a content pane.
        """
        if self._focused_id is not None:
            found = self.pane(self._focused_id)
            if found is not None and not self.is_dock(found):
                return found
        panes = self._leaves()
        return panes[0] if panes else None

    @property
    def focused_id(self) -> str | None:
        """The id focus is keyed on, or ``None`` when none was recorded.

        The raw record: :attr:`focused_pane` resolves it to a live pane and
        falls back to the first leaf, so this is what tells a dropped focus
        key -- an id whose pane left the tiling -- from a live one.
        """
        return self._focused_id

    def focus(self, pane: Pane | str) -> None:
        """Make ``pane`` (or the pane with that id) the frame's focused pane.

        The kernel half of focus: the record keys, scroll and the selection
        overlay read.  A pane the frame does not hold, and a dock, both
        raise ``ValueError`` -- a focus that silently landed nowhere would
        send the next key to the wrong document.
        """
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
        """Re-derive every pane's rectangle for a frame of ``rect``'s size.

        The tiling is structure: each top-level pane (the driver holds
        exactly one, every split nesting beneath it) takes ``rect`` and
        re-divides it down its recorded tree.  ``docks`` maps an edge to the
        rectangle its dock takes; ``None`` releases every dock (each takes
        an empty rectangle and stops composing), and an edge mapped to
        ``None`` -- or omitted -- releases that dock alone.  Panes are
        objects rather than values rebuilt per frame, so a pane keeps its
        id, its viewport, its chrome registry and its focus target across
        the change: the owner retiles the tree in place and carries nothing
        across a rebuild.
        """
        for pane in self._panes:
            pane._place(rect)
        for edge, dock in self._docks.items():
            placement = None if docks is None else docks.get(edge)
            dock._place(placement if placement is not None else Rect(x=0, y=0, width=0, height=0))
        self._adopt()

    def region(self, pane_id: str) -> Rect | None:
        """The rectangle a pane's viewport was laid out in, chrome subtracted.

        Where the pane's rows sit in the frame -- the placement a
        pane-relative overlay splices its rewrite back through
        (:meth:`with_pane_rows`) and a chrome band is measured from.
        ``None`` before the first composition, or for a pane the frame does
        not hold.
        """
        return self._placements.get(pane_id)

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

        Every write into a frame row runs through :func:`splice_row`, so the
        row stays a grid: exactly ``width`` columns, each region occupying
        the columns of its own rectangle and nothing else, whatever the
        earlier rows measured -- which is what lets a chrome strip, an
        overlay's rewrite or a second region be written over a row already
        composed without dragging any cell of it leftwards.

        A lone pane whose rectangle is the whole frame and carries no
        budgeted chrome composes to its pane's own layout -- the very
        object its viewport returned -- so the single-pane stream is
        today's stream by pass-through, not by re-derivation.

        Every other composition assembles, per screen row, the ordered
        **plan** of writes the regions make into it -- the pane's own rows
        at its inner rectangle first, its granted strips over them, region
        by region: exactly the sequence the sequential splice ran in.
        :func:`splice_row` is a pure function of the row it starts from
        (blank), the writes and the frame width, so a plan equal to one the
        previous composition ran builds the same row: that row is handed
        back as it stands (``Line`` objects are immutable values) instead
        of being spliced again, and the memo holding the previous frame's
        plans is replaced whole each composition -- a plan no frame has
        wanted for two compositions dies with it.  This is what makes a
        frame that did not change a walk instead of a splice, and what
        hands the unchanged rows of a scrolled frame -- a shifted window
        shares most of its rows with the frame before, only at other screen
        rows -- their composed values back without rebuilding them.  A row
        whose plan is a single write covering the whole width skips even
        that: :func:`splice_row` hands such a row back as it stands (its
        own full-row early return), so the composed row **is** the written
        line -- no splice runs and no memo entry is made.

        The plan and table containers themselves are the frame's buffers
        between compositions: at an unchanged height every row is cleared
        in place and refilled -- the per-frame list-of-lists allocation is
        paid once, not per composition -- and at a new height they are
        rebuilt to it.  The containers live as long as the frame; the row
        contents are rebuilt every composition, exactly as with a fresh
        container.

        The result also travels back on the frame (:attr:`layout`,
        :attr:`table`, :meth:`pane_layout`) for the overlay pipeline and
        the hit test to read, and it carries the rectangle it was laid out
        in -- ``width``/``height`` -- as the pane layouts do.
        """
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
        """The layout the frame is painting, or ``None`` before composition.

        The last :meth:`compose`'s product, advanced by
        :meth:`apply_overlays` as each overlay hands back the rows the next
        one paints over -- so an overlay reads the rows one earlier already
        rewrote.
        """
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
        """Append ``overlay`` to the registry on ``layer``.

        ``layer`` is one of :data:`LAYERS`; an unknown name raises
        ``ValueError``.  The frame's half of the overlay surface; panes
        accept chrome the same way (:meth:`Pane.add_chrome`).  Both
        registrations are the assembly tier's front door: a controller --
        the driver's selection, a toast -- attaches itself here and paints
        from then on.  :attr:`overlays` keeps registration order while
        :meth:`apply_overlays` paints a stable sort by layer, so a
        later-registered lower layer still paints underneath an earlier
        higher one.  The registry lives on the frame for the frame's whole
        life: a retile rewrites the pane rectangles in place rather than
        rebuilding the frame, so nothing carries across.  The frame's
        :attr:`revision` bumps.
        """
        if layer not in LAYERS:
            raise ValueError(f"overlay layer must be one of {LAYERS}, got {layer!r}")
        self._overlays.append((LAYERS.index(layer), overlay))
        self._touch()

    def remove_overlay(self, overlay: Overlay) -> None:
        """Unregister ``overlay`` -- the symmetric of :meth:`add_overlay`.

        By identity, and a missing overlay raises ``ValueError`` for the
        same reason :meth:`Pane.remove_chrome` does: an unregister is a
        claim about what the registry carries, and a silent miss would
        hide a controller detaching the wrong overlay.  The frame's
        :attr:`revision` bumps.
        """
        kept = [
            (layer, held) for layer, held in self._overlays if held is not overlay
        ]
        if len(kept) == len(self._overlays):
            raise ValueError(f"overlay is not registered on the frame: {overlay!r}")
        self._overlays = kept
        self._touch()

    def apply_overlays(self, layout: ScreenLayout) -> ScreenLayout:
        """Run the overlay registry over ``layout``, back to front by layer.

        The composition root's last step: each overlay paints over the
        composed frame and hands back the layout to paint.  The mechanism
        lives in :func:`motui.kernel.overlay.apply_overlays`; the frame keeps
        the method as its registry's front door.
        """
        return apply_overlays(self, layout)

    def pane_layout(self, pane_id: str) -> ScreenLayout | None:
        """The layout :meth:`compose` laid out for the pane, or ``None``.

        The read half of a pane-relative overlay: the pane's own rows --
        laid out at its inner rect, chrome subtracted -- beside the frame's
        placement for it (:meth:`region`), which the rewrite splices back
        through.
        """
        for pane, layout in zip(
            self._region_order, self._pane_layouts, strict=True
        ):
            if pane.id == pane_id:
                return layout
        return None

    def with_pane_rows(self, pane_id: str, rows: Sequence[Line]) -> ScreenLayout | None:
        """The layout being painted, with one pane's rows replaced in place.

        The write half of a pane-relative overlay: ``rows`` -- an overlay's
        rewrite of the pane's own :meth:`pane_layout` -- are spliced back
        into the frame rows at the pane's rectangle, every other cell kept
        exactly as it stands.  Only the pane's first ``placement.height``
        rows are written, so a rewrite that grew rows never bleeds into the
        pane below; a placement with zero height returns the layout
        untouched.  An overlay that rewrites nothing hands the pane's own
        rows back; the layout then comes back as it stands -- the
        single-pane pass-through stays the pane's own layout -- while any
        other sequence is spliced cell by cell.
        """
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

    The tmux convention (D4): the divider cell belongs to the pane before
    it -- registered as that pane's right-edge (vertical split) or
    bottom-edge (horizontal) chrome, so it is budgeted, never a gap -- and
    it reads in the host's theme: ``content.accent`` while either pane it
    divides is the focused one, ``borders.base`` otherwise.  The style is
    read at paint time from the frame's focus and the host's theme, so one
    chrome object serves every focus change and follows a re-themed host,
    and it rides a retile without re-registration.  The chrome registers
    under
    :data:`~motui.kernel.frame.SEPARATOR_CHROME_NAME`, the mark a
    :meth:`~motui.kernel.frame.Pane.close` strips it by when the
    adjacency it divides goes.  ``TUI.split`` is the one registration path;
    a host wanting a different look registers its own chrome on the pane
    instead (``split(separator=False)``, then ``pane.add_chrome(...)``).
    """

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
        """Whether either pane this divider separates is the focused one."""
        focused = self._host.frame.focused_pane
        return focused is not None and focused.id in (self._before_id, self._after_id)

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip: one accent or border cell per cell of the pane's edge.

        Edge-aware the way the paint protocol needs: a left/right divider is
        the pane's height in one-column rows, a bottom one one row of the
        pane's width -- either way the strip fills its band's own cells, so a
        horizontal split's divider never paints a one-column row over the
        content it was budgeted beside.

        The strip is the resolved style repeated, and the style is read
        here, every paint -- focus and the host's theme are live -- so
        the memo is keyed on where it landed besides the edge and the
        length: a focus change or a re-skin resolves a different style and
        rebuilds, and the frame invalidation that follows focus needs no
        separate signal.  A fresh list comes back every call, as it always
        has.
        """
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
