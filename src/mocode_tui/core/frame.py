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

A **split** is a :class:`Split` value a pane holds: orientation, ratios,
``min_size`` and whether a separator cell divides the panes.  The tiling is
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
module docstring of :mod:`mocode_tui.chrome` spells out.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from .block import Document
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
    "Split",
    "split_rect",
]

#: What a split divides: ``"vertical"`` tiles the width into side-by-side
#: panes (a vertical divider between them), ``"horizontal"`` tiles the
#: height into stacked ones (a horizontal divider).
_ORIENTATIONS = ("vertical", "horizontal")

#: The pane edges a chrome band may sit on.
_EDGES = ("left", "right", "top", "bottom")

#: The :attr:`Chrome.name` a divider registers under, so a close can strip
#: it by registration knowledge rather than by guessing at its size or edge
#: -- a scrollbar column is a 1-cell right-edge chrome too.  The kernel's
#: neutral divider (:func:`_plain_divider`) and the driver's themed
#: :class:`~mocode_tui.app._Separator` both register under it, and
#: :meth:`Pane.close` tears down whichever it finds on the edge the closed
#: pane sat beyond.
SEPARATOR_CHROME_NAME = "separator"


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

    ``name`` is an optional mark for *teardown*, not for lookup: a close
    (:meth:`Pane.close`) strips a divider by it -- the two known dividers,
    the kernel's neutral one and the driver's themed one, register under
    :data:`SEPARATOR_CHROME_NAME` -- so the band that divides two panes dies
    with the adjacency it divides instead of being guessed at by its size or
    edge.  It defaults to the empty string, an unnamed band, which no close
    ever touches.

    ``size: 0`` is legal and means a no-op seam -- nothing is budgeted and
    nothing is painted, the shape a custom renderer grows from.  A band
    that would shrink the pane's viewport below one cell is clipped to what
    remains (see :meth:`Frame.compose`).
    """

    edge: str
    size: int
    paint: Callable[[ScreenLayout, int], list[Line]]
    name: str = ""

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


def _ratio_sizes(span: int, ratios: Sequence[float], min_size: int) -> list[int]:
    """The cells each ratio takes of ``span``: proportional, then exact.

    A ratio's share is its weight over the sum (floor division, so a half
    cell is never invented), and the last ratio takes whatever the floors
    left -- unlike the widgets' flex division, which discards its
    remainder, because a frame's panes *partition* the screen and an
    untilted column would be a hole at its edge.  ``min_size`` then raises
    any share below it; a span that cannot host every pane at that floor
    clips the later ones away (the same overrun clip :func:`split_rect`
    applies to a fixed size).
    """
    total = sum(ratios)
    sizes = [span * ratio // total for ratio in ratios]
    remainder = span - sum(sizes)
    if remainder:
        sizes[-1] += remainder
    if min_size:
        sizes = [max(size, min_size) for size in sizes]
    return sizes


def _plain_divider(layout: ScreenLayout, length: int) -> list[Line]:
    """The kernel's neutral separator: blank cells, no styling opinion.

    The default a bare :meth:`Pane.split` installs -- one row per strip
    cell, each exactly the band's one column, filled with the band
    primitive.  A driver that themes its divider (the focused pane's side
    in the theme accent) registers its own chrome instead.
    """
    return [Line.filled(1) for _ in range(length)]


def _strip_divider(pane: Pane, edge: str) -> None:
    """Unregister the divider ``pane`` carries on ``edge``, if it has one.

    The hygiene half of :meth:`Pane.close`, by name *and* edge and never
    by size: a scrollbar column is a 1-cell right-edge chrome too, and a
    teardown that guessed would strip the wrong band.  A pane holding no
    divider on that edge keeps its chrome exactly as it stands -- a last
    child holds none, its abutting neighbour's having died with the pane
    that registered it.
    """
    kept = tuple(
        chrome
        for chrome in pane.chrome
        if not (chrome.name == SEPARATOR_CHROME_NAME and chrome.edge == edge)
    )
    if len(kept) != len(pane.chrome):
        object.__setattr__(pane, "chrome", kept)


def _split_holding(pane: Pane, tree: Sequence[Pane]) -> tuple[Pane, int, Split] | None:
    """The split that holds ``pane``, its position in it and its division.

    A pane carries no parent pointer -- it is a value and the tree is
    structure -- so the search walks ``tree`` (the frame's top-level panes)
    down to the pane, the one depth-first descent a close pays.  ``None``
    means no split holds it: a root, or a pane that already left the tiling.
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
    raised to, and ``separator`` says whether a 1-cell divider divides
    neighbouring children.

    The divider cell is *not* a gap: it is the last cell of the pane before
    it, budgeted as that pane's chrome (the W2 mechanism), so a split with
    ``separator=True`` and one without differ by one cell of the first
    pane's width and nothing else -- the panes never leave an unclaimed
    column between them.  The kernel paints its divider blank
    (:func:`_plain_divider`); theming it is the driver's, one level up.
    """

    orientation: str
    ratios: tuple[float, ...]
    min_size: int = 1
    separator: bool = True

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
        child's origin follows the children before it (its divider cell
        included, when ``separator``), and a size that overruns what
        remains is clipped -- a tiling never overlaps and never leaves a
        hole.
        """
        span = rect.width if self.orientation == "vertical" else rect.height
        gaps = len(self.ratios) - 1 if self.separator else 0
        sizes = _ratio_sizes(max(0, span - gaps), self.ratios, self.min_size)
        rects: list[Rect] = []
        at = 0
        for index, size in enumerate(sizes):
            divider = 1 if self.separator and index < len(sizes) - 1 else 0
            taken = max(0, min(size + divider, span - at))
            if self.orientation == "vertical":
                rects.append(Rect(rect.x + at, rect.y, taken, rect.height))
            else:
                rects.append(Rect(rect.x, rect.y + at, rect.width, taken))
            at += taken
        return tuple(rects)


@dataclass(frozen=True)
class Pane:
    """One pane of a frame: its rectangle and the viewport laid out inside it.

    ``chrome`` is the pane's edge budget -- the edge columns or rows
    reserved for scrollbars and rails, negotiated against the pane's inner
    rect by :meth:`Frame.compose`.  Chromes stack in registration order and
    their budgets add per edge, so a rail beside a gutter is two chromes.

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
    """

    id: str
    rect: Rect
    viewport: Viewport
    chrome: tuple = ()
    division: Split | None = None
    children: tuple["Pane", ...] = ()
    _frame: "Frame | None" = field(default=None, compare=False, repr=False)

    @property
    def document(self) -> Document:
        """The document this pane is a window over."""
        return self.viewport.document

    def add_chrome(self, chrome: Chrome) -> None:
        """Register ``chrome`` on the pane (it paints after the ones before it).

        The one way chrome joins a pane after construction: a pane is a
        value, and this is its registration-time mutation -- the same append
        the ``chrome=(...)`` constructor argument performs.  A retile
        rewrites the pane's rectangle in place (:meth:`Pane._place`) rather
        than rebuilding the pane, so the registration rides a resize with
        nothing to carry.
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

    # -- the split ---------------------------------------------------------------

    def split(
        self,
        orientation: str,
        *,
        ratios: tuple[float, ...] = (1, 1),
        min_size: int = 1,
        separator: bool = True,
    ) -> tuple["Pane", ...]:
        """Divide this pane into one child per ratio; return the children.

        The same code path :meth:`~mocode_tui.app.TUI.split` calls: the
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
        the live screen by that paint's retile.

        ``separator=True`` registers the kernel's neutral 1-cell divider
        (:func:`_plain_divider`) as chrome on every child but the last --
        the divider cell belongs to the pane before it, never a gap between
        two; a driver theming its divider (the focused pane's side in the
        theme accent) registers its own chrome instead, which is why
        :meth:`~mocode_tui.app.TUI.split` passes ``False`` and installs its
        own.  Both dividers register under
        :data:`SEPARATOR_CHROME_NAME`, the mark :meth:`close` tears a
        divider down by when the adjacency it divides goes.  Splitting an
        already-split pane raises ``RuntimeError``.
        """
        if self.division is not None:
            raise RuntimeError(f"pane {self.id!r} is already split")
        division = Split(orientation, ratios, min_size, separator)
        children = tuple(
            replace(self, rect=rect, division=None, children=())
            if index == 0
            else Pane(f"{self.id}-{index}", rect, Viewport(Document()))
            for index, rect in enumerate(division.rects(self.rect))
        )
        object.__setattr__(self, "division", division)
        object.__setattr__(self, "children", children)
        if separator:
            edge = "right" if orientation == "vertical" else "bottom"
            for child in children[:-1]:
                child.add_chrome(
                    Chrome(edge, 1, _plain_divider, name=SEPARATOR_CHROME_NAME)
                )
        if self._frame is not None:
            # The children join the frame that holds this pane the moment
            # they exist -- a split after the first paint adopts them here,
            # because the driver's retile no-ops on an unchanged tiling
            # and would otherwise never run the frame's adoption walk.
            self._frame._adopt()
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
        division trimmed rather than the tree rebuilt) and the tree is
        re-adopted, so the frame object is never replaced and the next
        composition paints the new tiling: a collapsed pane takes the whole
        rectangle the split held, and the single-pane pass-through composes
        to its own layout again -- the transcript | preview split is gone
        the moment the preview closes.

        **The id rule.**  A pane's id is its identity in the frame -- what a
        host registers chrome on, what ``frame.focus`` keys, what
        ``frame.pane`` answers -- and a collapse keeps the *parent's*: a
        split's first child shared it already, so collapsing onto the first
        child is invisible to every id a host holds (the scrollbar on
        ``"primary"`` and the ``"primary"`` focus key both ride on), while a
        survivor that was a later child carries an id -- ``"primary-1"`` --
        that dies with the split, the parent's own surviving in its place
        (``frame.pane("primary-1")`` answers ``None`` from then on, and a
        focus keyed on it falls to the pane that took its rectangle).  A
        re-divide changes no id at all: the survivors keep the ones they
        were given at split time, so a trimmed set's numbering may start
        above zero.  Nothing is ever renumbered -- an id a host holds must
        not move under it.

        **The separator.**  The divider cell is chrome of the pane before
        the gap, so it dies with the adjacency it divides: the close strips,
        from the pane before the gap, the chrome the split's orientation
        names on that edge, identified by :attr:`Chrome.name`
        (:data:`SEPARATOR_CHROME_NAME` -- the kernel's neutral divider and
        the driver's themed one both register under it) rather than by size
        or edge, which a scrollbar column shares.  The closed pane's own
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
        close: a frame without panes has no composition (``RuntimeError``;
        the driver may allow an empty frame one day, not this wave).
        Closing a **container** (an already-split pane) raises the same
        way, as does closing twice: a close is a claim about a leaf the
        tiling still holds.
        """
        frame = self._frame
        if frame is None:
            raise RuntimeError(f"pane {self.id!r} is held by no frame")
        if self.children:
            raise RuntimeError(
                f"pane {self.id!r} is a split: close a leaf, not a container"
            )
        if any(top is self for top in frame._panes):
            raise RuntimeError(
                f"pane {self.id!r} is the frame's root: a frame without panes "
                "has no composition"
            )
        home = _split_holding(self, frame._panes)
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
            object.__setattr__(parent, "division", trimmed)
            object.__setattr__(parent, "children", survivors)
            for child, rect in zip(survivors, trimmed.rects(parent.rect)):
                child._place(rect)
            fallback = survivors[min(index, len(survivors) - 1)]
        else:
            # one survivor (or none, from a one-child split): the parent
            # collapses back to a leaf, its own id and rectangle kept and
            # the survivor's window taken.  The survivor is either the pane
            # before the gap, whose divider was just stripped, or a last
            # child, which never registered one.
            survivor = survivors[0] if survivors else None
            object.__setattr__(parent, "division", None)
            object.__setattr__(parent, "children", ())
            if survivor is not None:
                object.__setattr__(parent, "viewport", survivor.viewport)
                object.__setattr__(parent, "chrome", survivor.chrome)
            fallback = parent
        if frame._focused_id is not None and frame.pane(frame._focused_id) is None:
            # The focused id died -- with the closed pane, or with a
            # collapsed child's -- so focus falls to the pane that now
            # occupies that rectangle.
            frame.focus(fallback)
        frame._adopt()

    # -- the tiling walk ----------------------------------------------------------

    def _place(self, rect: Rect) -> None:
        """Take ``rect`` as this pane's rectangle and re-derive any children.

        The one mutation a frozen pane accepts besides its chrome
        registry: the tiling is structure, so a resize rewrites the
        rectangles and leaves every pane -- id, viewport, chrome, focus
        target -- exactly as it was.
        """
        object.__setattr__(self, "rect", rect)
        division = self.division
        if division is not None:
            for child, child_rect in zip(self.children, division.rects(rect)):
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
    scroll state (the panes' viewports do), no clock, and no focus policy
    beyond which pane :meth:`focus` names.

    One **band** (:meth:`set_band`) reserves the rows beneath the pane
    area: a pane-like rectangle holding its own viewport, which paints
    last of the regions and joins the ownership table -- so a footer is
    hit-testable and selectable exactly as a pane's rows are -- but which
    takes neither focus (:attr:`focused_pane` never returns it, and
    :meth:`focus` refuses it) nor splits.
    """

    def __init__(self, panes: Iterable[Pane] = (), *, band: Pane | None = None) -> None:
        self._panes: tuple[Pane, ...] = tuple(panes)
        self._band: Pane | None = band
        self._layout: ScreenLayout | None = None
        self._pane_layouts: tuple[ScreenLayout, ...] = ()
        self._region_order: tuple[Pane, ...] = ()
        self._table: FrameTable | None = None
        # pane id -> the rect its rows were laid out at (chrome subtracted):
        # where a pane-relative overlay splices its rewrite back.
        self._placements: dict[str, Rect] = {}
        self._size: tuple[int, int] | None = None
        self._overlays: list[Overlay] = []
        self._focused_id: str | None = None
        self._adopt()

    # -- the tiling ------------------------------------------------------------

    def _adopt(self) -> None:
        """Point every pane the frame holds -- content and band alike -- at it.

        A pane carries the frame back-reference :meth:`Pane.focus` routes
        through, so a pane built for this frame (a split's children, a band
        handed over) becomes focusable the moment it joins.  Idempotent.
        """

        def walk(pane: Pane) -> None:
            object.__setattr__(pane, "_frame", self)
            for child in pane.children:
                walk(child)

        for pane in self._panes:
            walk(pane)
        if self._band is not None:
            walk(self._band)

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
    def band(self) -> Pane | None:
        """The frame's bottom band, or ``None`` when it holds none."""
        return self._band

    def set_band(self, band: Pane | None) -> None:
        """Reserve the frame's bottom band as ``band`` (``None`` releases it).

        The band's rectangle is the driver's to set (:meth:`retile`), its
        rows its own viewport's, and its cells join the ownership table --
        a footer block under the pointer resolves through
        :meth:`~mocode_tui.app.TUI.hit_test` exactly as a pane's does.
        """
        self._band = band
        self._adopt()

    @property
    def rect(self) -> Rect | None:
        """The bounding rectangle of the tiling, or ``None`` when empty.

        Every region belongs to the frame -- the content panes and the band
        alike -- so this is the screen they cover, which is how an owner
        tells a retiled frame from a stale one and where a corner-anchored
        overlay paints.
        """
        regions = (*self._leaves(), *((self._band,) if self._band is not None else ()))
        if not regions:
            return None
        left = min(pane.rect.x for pane in regions)
        top = min(pane.rect.y for pane in regions)
        right = max(pane.rect.right for pane in regions)
        bottom = max(pane.rect.bottom for pane in regions)
        return Rect(left, top, right - left, bottom - top)

    def pane(self, pane_id: str) -> Pane | None:
        """The pane with ``pane_id``, or ``None`` when the frame holds none.

        Content panes and the band are both addressable; a pane a split
        replaced keeps its id only through the child that inherited it.
        """
        for pane in (*self._leaves(), *((self._band,) if self._band is not None else ())):
            if pane.id == pane_id:
                return pane
        return None

    @property
    def focused_pane(self) -> Pane | None:
        """The pane input routes to: the first, until :meth:`focus` moves it.

        The band never holds focus -- it is a footer, not a document window
        -- so this is always a content pane.
        """
        if self._focused_id is not None:
            found = self.pane(self._focused_id)
            if found is not None and found is not self._band:
                return found
        panes = self._leaves()
        return panes[0] if panes else None

    def focus(self, pane: Pane | str) -> None:
        """Make ``pane`` (or the pane with that id) the frame's focused pane.

        The kernel half of focus: the record keys, scroll and the selection
        overlay read.  A pane the frame does not hold, and the band, both
        raise ``ValueError`` -- a focus that silently landed nowhere would
        send the next key to the wrong document.
        """
        pane_id = pane if isinstance(pane, str) else pane.id
        found = self.pane(pane_id)
        if found is None:
            raise ValueError(
                f"unknown pane {pane_id!r}: the frame holds {[p.id for p in self._leaves()]}"
            )
        if found is self._band:
            raise ValueError(
                f"the band {pane_id!r} takes no focus: it is a footer, not a window"
            )
        self._focused_id = pane_id

    def retile(self, rect: Rect, *, band: Rect | None = None) -> None:
        """Re-derive every pane's rectangle for a frame of ``rect``'s size.

        The tiling is structure: each top-level pane (the driver holds
        exactly one, every split nesting beneath it) takes ``rect`` and
        re-divides it down its recorded tree, and ``band`` is the rectangle
        the frame's bottom band takes -- the rows beneath the pane area,
        which ``None`` leaves where it stands.  Panes are objects rather
        than values rebuilt per frame, so a pane keeps its id, its viewport,
        its chrome registry and its focus target across the change: the
        owner retiles the tree in place and carries nothing across a
        rebuild.
        """
        for pane in self._panes:
            pane._place(rect)
        if band is not None and self._band is not None:
            self._band._place(band)
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
        regions = self._regions()
        for pane in regions:
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
            len(regions) == 1
            and regions[0].rect == Rect(0, 0, width, height)
            and not banded
        ):
            composed = layouts[0]  # pass-through: the frame is the pane's layout
        else:
            # No single document owns the frame: its ownership lives in the
            # frame table, and this layout is painted as it was spliced.
            composed = ScreenLayout(rows=rows, viewport_rows=[])
        self._layout = composed
        self._pane_layouts = tuple(layouts)
        self._region_order = regions
        self._table = FrameTable(rows=ordered)
        self._placements = placements
        self._size = (width, height)
        return composed

    def _regions(self) -> tuple[Pane, ...]:
        """What composes: the content leaves, the band last of all."""
        panes = self._leaves()
        if self._band is not None:
            return (*panes, self._band)
        return panes

    @property
    def layout(self) -> ScreenLayout | None:
        """The layout the last :meth:`compose` produced, or ``None``."""
        return self._layout

    @property
    def pane_layouts(self) -> tuple[ScreenLayout, ...]:
        """The per-pane layouts of the last composition, in pane order.

        What an overlay composes over: the rows of one pane's layout
        spliced back into the frame rows it came from.  The band's layout
        travels last, when the frame holds one.
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
        a toast -- attaches itself here and paints from then on.  The
        registry lives on the frame for the frame's whole life: a retile
        rewrites the pane rectangles in place rather than rebuilding the
        frame, so nothing carries across.
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
        :attr:`pane_layouts`, which holds them all in region order.
        """
        for pane, layout in zip(self._region_order, self._pane_layouts):
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
        band = ", band" if self._band is not None else ""
        return f"Frame({len(self._leaves())} panes{band})"
