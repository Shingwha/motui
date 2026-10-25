"""The workspace: the document, frame, panes, hit test, selection and docks.

:class:`Workspace` owns *what is on screen*: the primary
:class:`~motui.kernel.document.Document` and its
:class:`~motui.kernel.layout.Viewport`, the
:class:`~motui.kernel.frame.Frame` tiling, every panes' document, the
document-space selection, the hit test, the docks and the frame-level rows.
:class:`~motui.app.runtime.Runtime` owns the session around it -- the
terminal, the painter, the timers and the pump -- and hands the workspace
the two moments it needs: ``refresh()`` (mark dirty) and paint (compose the
frame this workspace holds).

The workspace is also the host the interaction tiers mounted by
:class:`~motui.app.application.App` drive: a controller needs the frame and
the hit test from here and the clock/timers/repaint seam from the runtime,
so the six runtime seams a controller reads (``clock``/``every``/
``refresh``/``screen``/``painter``/``copy_to_clipboard``) are exposed here.
They delegate; the state stays on the runtime.

Every mutation invalidates the frame: ``add``/``fill``/``remove``/``split``/
``dock``/``set_selection`` and the scroll facades call :meth:`refresh`.
Components are addressed as :class:`~motui.kernel.document.Section` values,
never bare ids.

**The dispatch order**, one rule everywhere: a composition paints each
pane's chrome budget first, then that pane's content rows, then the granted
chrome strips over them, then the docks, then the overlay registry over
everything (:mod:`motui.kernel.frame`); a host routes an event the same way
-- chrome, then overlays, then the panes' content, then its own dispatch
(:mod:`motui.app.overlays`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..kernel.cell import Line
from ..kernel.document import (
    Component,
    Document,
    Placement,
    Section,
    Sizing,
    descend_chain,
)
from ..kernel.frame import Frame, Pane, Rect, Separator
from ..kernel.geom import Axis
from ..kernel.hit import Hit
from ..kernel.layout import Constraints, RowSpan, ScreenLayout, Viewport
from ..kernel.selection import Selection, highlight
from ..kernel.theme import Theme
from ..widgets.text import Text

if TYPE_CHECKING:
    from ..terminal.paint import Painter
    from ..terminal.screen import Screen
    from .runtime import Runtime, Timer

__all__ = ["Workspace"]


def _dock_edge(placement: Placement) -> str:
    """The frame edge a dock placement names; ``FLOW`` is not a dock.

    ``Placement.TOP``/``BOTTOM`` are the two fixed bands; anything else --
    a flow section or a non-enum value -- raises ``ValueError``.
    """
    if not isinstance(placement, Placement):
        raise ValueError(f"dock placement must be a Placement, got {placement!r}")
    if placement is Placement.FLOW:
        raise ValueError("a dock cannot use Placement.FLOW")
    return placement.value


def _body_address(viewport: Viewport, block: Section, row: int, width: int) -> int:
    """The body-row index of ``(block, row)`` in the viewport's document.

    The document order walks the blocks and sums what the flow blocks
    occupy before ``block`` -- each measured at ``width``, the width the
    pane was last laid out at, exactly as the viewport counts its own body
    (fixed-region rows are not body rows) -- and ``row`` lands on that
    prefix, clamped into the block's own rendered rows (an empty block
    answers its first row).  The counts come from each block's count gate
    (:meth:`~motui.kernel.document.Section.row_count`): the layout just filled
    the same cache, so the walk reads counts instead of re-wrapping rows,
    and a block whose content was touched carries a moved generation, so no
    count is stale.  The half of :meth:`Workspace.reveal` that is pure
    arithmetic over the document; the caller has already resolved the block
    out of the document, so the walk is total.
    """
    address = 0
    for held in viewport.document.blocks():
        if held is block:
            break
        if held.placement is Placement.FLOW:
            address += held.row_count(Constraints(width=width))
    count = block.row_count(Constraints(width=width))
    row = max(0, min(row, count - 1)) if count else 0
    return address + row


class _SelectionOverlay:
    """The driver's selection screen: overlay #1 of the frame's registry.

    Wraps the kernel's :func:`~motui.kernel.selection.highlight` in the
    overlay protocol -- the frame hands it the composed rows, it marks the
    layout of the pane the selection lives in and the marked rows are spliced
    back where that pane's came from.  The stored selection is read off the
    workspace at paint time, so :meth:`Workspace.set_selection` stays the one
    write on that surface and a ``None`` paints the rows exactly as they were
    composed.

    The pane matters more than it looks: block ids are numbered per document,
    so a split's second child holds a ``b0`` exactly as the first does, and an
    overlay that guessed a pane from the focus would mark a *neighbour's* rows
    at those colliding addresses.  :meth:`Workspace.set_selection` therefore
    records the pane alongside the range, and a pane the frame no longer
    holds paints nothing -- its document went with it (D8's vanished
    addresses).
    """

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def paint(self, frame: Frame) -> ScreenLayout:
        selection = self._workspace._selection
        if selection is None:
            return frame.layout
        pane_id = self._workspace._selection_pane_id
        if pane_id is None or frame.pane(pane_id) is None:
            return frame.layout
        marked = highlight(
            frame.pane_layout(pane_id),
            selection,
            style=self._workspace.theme.text.selection,
        )
        return frame.with_pane_rows(pane_id, marked.rows)


class Workspace:
    """The state owner: document, viewport, frame, panes, selection and docks.

    ``runtime`` is the session the workspace belongs to: it supplies the
    screen size a retile reads, the repaint seam and the painter whose rows
    :attr:`rows` answers.  ``theme`` is the workspace's own theme (the chrome
    the workspace composes -- the split's divider -- and the selection
    highlight); widgets are never themed from here, they each take
    ``theme=`` themselves.

    Every frame composes through :attr:`frame` (a single-pane frame composes
    to its pane's own layout), :meth:`hit` routes through its ownership
    table, the scroll facades move its focused pane's viewport, and the
    selection highlight is the frame's first overlay.  :meth:`split` divides
    a pane of that tiling in place -- the frame keeps its identity, its
    overlays and its focus across the division, and every pane keeps its
    viewport, its chrome and its scroll state -- so a split adds panes
    without any new plumbing, and a resize re-divides the same tree instead
    of rebuilding panes.
    """

    def __init__(self, runtime: Runtime, *, theme: Theme) -> None:
        self._runtime = runtime
        #: The theme the workspace's own chrome reads (the split's divider
        #: and the selection highlight); widgets take their own ``theme=``.
        self.theme = theme
        self._document = Document()
        self._viewport = Viewport(self._document)
        # The initial tiling: one pane, the primary, its whole rectangle the
        # screen -- held by the frame every composition routes through.  The
        # rectangle is a placeholder until the first paint retiles it to the
        # live screen; the selection highlight rides the frame as overlay #1.
        self._frame = Frame(
            [Pane("primary", Rect(x=0, y=0, width=0, height=0), self._viewport)]
        )
        self._frame.add_overlay(_SelectionOverlay(self), layer="selection")
        # Structural frame changes (split/close/chrome/dock/overlay) mark the
        # runtime dirty by themselves: a host never follows them with refresh().
        self._frame.on_change = runtime.refresh
        self._selection: Selection | None = None
        #: The pane the stored selection's addresses live in (its id), the
        #: document half of the range's identity: ``None`` with no selection,
        #: and a pane that leaves the frame takes the selection's meaning with
        #: it (the overlay then paints nothing).  Written only through
        #: :meth:`_set_selection`, alongside :attr:`_selection`.
        self._selection_pane_id: str | None = None
        self._layout_width: int | None = None
        #: The explicit dock heights, per edge; ``None`` means content-derived.
        self._dock_sizes: dict[str, int | None] = {"top": None, "bottom": None}
        #: The rectangles the last retile laid out (pane area, top dock,
        #: bottom dock) and the frame revision it ran at, so a same-size paint
        #: with an unchanged tree retiles nothing.
        self._tiling: tuple[Rect, Rect | None, Rect | None] | None = None
        self._tiling_revision: int | None = None

    # -- the runtime seams controllers read --------------------------------------

    @property
    def screen(self) -> Screen:
        """The runtime's screen (a read-only view of it)."""
        return self._runtime.screen

    @property
    def painter(self) -> Painter:
        """The runtime's painter (the diff base the rows come from)."""
        return self._runtime.painter

    def clock(self) -> float:
        """The runtime's monotonic clock (see :meth:`Runtime.clock`)."""
        return self._runtime.clock()

    def every(
        self,
        period: float,
        fn: Callable[[], object],
        *,
        catch_up: str = "skip",
    ) -> Timer:
        """Schedule ``fn`` on the runtime's pump (see :meth:`Runtime.every`)."""
        return self._runtime.every(period, fn, catch_up=catch_up)

    def refresh(self) -> None:
        """Mark the frame dirty on the runtime's pump."""
        self._runtime.refresh()

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard through the runtime."""
        return self._runtime.copy_to_clipboard(text)

    # -- read-only views ---------------------------------------------------------

    @property
    def document(self) -> Document:
        """The primary pane's document (a read-only view of it)."""
        return self._document

    @property
    def viewport(self) -> Viewport:
        """The primary pane's viewport (a read-only view of it)."""
        return self._viewport

    @property
    def frame(self) -> Frame:
        """The workspace's frame: its tiling, its docks, its overlays, its focus.

        The public seam the assembly tier reads -- a scrollbar resolves its
        pane's rectangle and layout through it, a toast its corner, and the
        gesture tier the pane a drag lives in.
        """
        return self._frame

    @property
    def panes(self) -> tuple[Pane, ...]:
        """Every content pane in paint order (docks excluded)."""
        return self._frame.panes

    @property
    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows."""
        return self._runtime.painter.rows

    @property
    def selection(self) -> Selection | None:
        """The document-space selection overlay, ``None`` when there is none.

        The read half of the selection surface (D3): the value is the
        kernel's :class:`~motui.kernel.selection.Selection`, written here
        whole by :meth:`set_selection` -- the workspace stores it and owns no
        anchor or head arithmetic of its own (that is gesture policy).
        """
        return self._selection

    @property
    def selection_pane(self) -> Pane | None:
        """The pane the stored selection lives in, or ``None``.

        The other half of a selection's identity: block ids are numbered per
        document, so a range's addresses only mean something inside one
        document, and this is it.  A gesture names the pane it anchored in
        when it writes the range (:meth:`set_selection`'s ``pane``); the
        highlight paints it, and a host's ``on_end`` extracts its text at the
        width its rows were laid out at.  ``None`` with no selection, and also
        after the pane it named left the frame -- a close takes its document
        with it.
        """
        if self._selection is None or self._selection_pane_id is None:
            return None
        return self._frame.pane(self._selection_pane_id)

    # -- document facade ---------------------------------------------------------

    def pane(self, pane_id: str) -> Pane:
        """The pane with ``pane_id`` (content pane or dock); unknown raises ``KeyError``."""
        found = self._frame.pane(pane_id)
        if found is None:
            raise KeyError(f"no pane with id {pane_id!r}")
        return found

    def _document_panes(self) -> tuple[tuple[Pane, Document], ...]:
        """Every pane and the document it shows, in paint order (docks last)."""
        held = [(pane, pane.viewport.document) for pane in self._frame.panes]
        held.extend(
            (pane, pane.viewport.document) for pane in self._frame.docks.values()
        )
        return tuple(held)

    def _content_pane(self, pane: Pane | str | None) -> Pane:
        """Resolve a content target: an explicit pane, or the main one.

        The main pane is ``primary`` when the frame holds it, else the first
        content pane in paint order.  Focus is deliberately not consulted:
        focus routes input, while a block's document is structural ownership
        and must not move when the user clicks another pane.
        """
        if pane is not None:
            return self.pane(pane if isinstance(pane, str) else pane.id)
        main = self._frame.pane("primary")
        if main is not None:
            return main
        panes = self._frame.panes
        if not panes:
            raise ValueError("the frame holds no content pane")
        return panes[0]

    def _focus_pane(self, pane: Pane | str | None) -> Pane:
        """Resolve a structural target: an explicit pane, or the focused one."""
        if pane is not None:
            return self.pane(pane if isinstance(pane, str) else pane.id)
        focused = self._frame.focused_pane
        if focused is not None:
            return focused
        return self.pane("primary")

    def _next_block_id(self) -> str:
        """The first ``bN`` id no document in the frame holds."""
        used = {
            block.id
            for _, document in self._document_panes()
            for block in document.blocks()
        }
        index = 0
        while f"b{index}" in used:
            index += 1
        return f"b{index}"

    def _panes_holding(self, id: str) -> tuple[Pane, ...]:
        """Every pane whose document holds a block with ``id``."""
        return tuple(
            pane
            for pane, document in self._document_panes()
            if any(block.id == id for block in document.blocks())
        )

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        placement: Placement = Placement.FLOW,
        sizing: Sizing = Sizing.NATURAL,
        pane: Pane | str | None = None,
    ) -> Section:
        """Append a block to a pane's document; answer its section.

        ``pane`` scopes the operation: an explicit pane (or pane id) wins,
        and with none named the **main** pane (``primary``, else the first
        content pane in paint order) is the target.  Focus routes input, not
        content ownership, so a click on another pane never changes where a
        producer's blocks land; pass ``pane=workspace.frame.focused_pane``
        when a focused-pane write is really what is meant.
        ``placement``/``sizing`` forward to
        :meth:`~motui.kernel.document.Document.add` (which owns the fill
        rules).  Section ids are unique across the whole frame: an automatic
        id is the first free ``bN`` over every pane's document, and an
        explicit id another pane already holds raises ``ValueError``.  The
        section is the handle a host keeps: :meth:`get` and :meth:`remove`
        speak sections, so the block value itself never has to cross the
        facade.
        """
        target = self._content_pane(pane)
        if id is None:
            id = self._next_block_id()
        elif self._panes_holding(id):
            raise ValueError(f"duplicate block id: {id!r}")
        section = target.viewport.document.add(
            component, id=id, placement=placement, sizing=sizing
        )
        self.refresh()
        return section

    def fill(self, component: Component, *, pane: Pane | str | None = None) -> Section:
        """Make ``component`` the fill of a pane (main pane by default).

        The pane's document is replaced by the fill; ``refresh`` marks the
        frame dirty so the next paint shows it.  The returned section is the
        new ``FILL`` block -- the handle a host can later ``document.get``.
        """
        target = self._content_pane(pane)
        section = target.fill(component)
        self.refresh()
        return section

    def _holder(self, id: str) -> Pane:
        """The one pane whose document holds ``id``.

        Frame-wide uniqueness is the contract: no holder raises ``KeyError``,
        and two holders raise ``ValueError`` naming the panes instead of
        silently picking the first.
        """
        holders = self._panes_holding(id)
        if not holders:
            raise KeyError(f"no block with id {id!r}")
        if len(holders) > 1:
            raise ValueError(
                f"block id {id!r} is held by multiple panes: "
                f"{[pane.id for pane in holders]}"
            )
        return holders[0]

    def get(self, id: str) -> Section:
        """The section with ``id`` from any pane's document (``KeyError`` when missing).

        The search spans every content pane and dock.  An id two panes hold
        is not silently resolved to the first: it raises ``ValueError`` and
        names the panes, because frame-wide uniqueness is the contract.
        """
        return self._holder(id).viewport.document.get(id)

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` and answer its section.

        The same frame-wide resolution :meth:`get` performs; an ambiguous id
        raises ``ValueError`` listing the panes instead of picking one.
        """
        section = self._holder(id).viewport.document.remove(id)
        self.refresh()
        return section

    def system(self, text: str, *, pane: Pane | str | None = None) -> Section:
        """Append a system block to a pane's document; default the main pane.

        The text is added as a muted :class:`~motui.kernel.text.Text`
        block, so a full-screen application never writes to stdout behind the
        painter's back.  ``pane`` follows :meth:`add`'s rule: explicit wins,
        and with none named the main document is the target -- system output
        is content, not input, so focus never chooses where it lands.
        Answer is the new section (:meth:`add`'s contract).
        """
        return self.add(Text(text, style=self.theme.text.muted), pane=pane)

    # -- scroll facade --------------------------------------------------------

    def _focused_viewport(self) -> Viewport:
        """The viewport the scroll facades move: the focused pane's window.

        A single-pane frame's focused pane is the primary one, so this is
        the resident viewport -- the very object :attr:`viewport` hands
        out -- and the facade keeps its shape when a split frame lands.
        """
        pane = self._frame.focused_pane
        return self.viewport if pane is None else pane.viewport

    def scroll_up(self, n: int = 1) -> None:
        """Scroll the viewport ``n`` rows toward the top."""
        self._focused_viewport().scroll_up(n)
        self.refresh()

    def scroll_down(self, n: int = 1) -> None:
        """Scroll the viewport ``n`` rows toward the bottom."""
        self._focused_viewport().scroll_down(n)
        self.refresh()

    def scroll_to_bottom(self) -> None:
        """Re-attach the viewport to the bottom of the document."""
        self._focused_viewport().scroll_to_bottom()
        self.refresh()

    def reveal(self, bid: str, row: int) -> bool:
        """Bring the document address ``bid``/``row`` on screen; ``False`` when unknown.

        The generic "scroll this block row into view" ability -- what a
        search tier reveals a match with, and what any host jumps with.  The
        pane moved is the one that **holds** ``bid`` -- the same frame-wide
        id resolution :meth:`get` and :meth:`remove` perform -- never the
        focused pane: a block belongs to a document, and revealing it
        follows that ownership even after the user clicks elsewhere.  A
        target **already visible** moves nothing.  A target outside the
        window scrolls it in, **centered** when the document's edges allow
        it: the window is put ``row`` rows above the middle, and the
        viewport's own clamp takes over near either end -- a limit that
        still shows the target, since a clamp only pulls the target toward
        the window's nearer edge.

        ``row`` is a 0-based row within the block's own ``render`` at the
        pane's laid-out width -- the address a hit test, a selection or a
        match names -- and is clamped into the block's rows (an empty block
        answers its first row).  A block in a fixed region never scrolls
        away, so it answers ``True`` without moving.  ``False`` for an
        unknown ``bid``, and for a pane with no window to show the target in
        -- before the first composition, or when the fixed regions fill the
        screen.  The frame is invalidated when the window moved.

        The "already visible" test runs **first**, against the layout's own
        row-ownership table: the screen has just told us which
        ``(block, row)`` addresses it is showing, so a target among them
        returns with no address arithmetic at all -- and the prefix walk
        (:func:`_body_address`) that would touch every block before the
        target only runs when a scroll is actually needed.  The table is
        only trusted while the viewport still sits at the offset the layout
        recorded (``layout.offset``): a scroll since the last paint has
        moved the window the next layout will show, so the table no longer
        answers "would the target be on screen".  The arithmetic check is
        kept after the walk too, because a layout built by hand carries no
        ownership to read.
        """
        try:
            pane = self._holder(bid)
        except KeyError:
            return False  # an unknown address reveals nothing
        viewport = pane.viewport
        block = viewport.document.get(bid)
        if block.placement is not Placement.FLOW:
            return True  # a fixed-region block is always on screen
        layout = self._frame.pane_layout(pane.id)
        placement = self._frame.region(pane.id)
        if layout is None or placement is None or not layout.body_rows:
            return False  # no composition has run, or no window to show it in
        count = block.row_count(Constraints(width=placement.width))
        row = max(0, min(row, count - 1)) if count else 0
        if layout.offset == viewport.offset and (bid, row) in layout.row_blocks:
            return True  # the layout already shows exactly this row
        address = _body_address(viewport, block, row, placement.width)
        window = len(layout.body_rows)
        offset = viewport.offset
        if offset <= address < offset + window:
            return True  # already on screen: nothing moves
        viewport.scroll_to(address - window // 2)
        self.refresh()
        return True

    # -- the split and focus surface ----------------------------------------------

    def split(
        self,
        axis: Axis,
        *,
        weights: tuple[float, ...] = (1, 1),
        min_size: int = 1,
        separator: bool = True,
        pane: Pane | str | None = None,
    ) -> tuple[Pane, ...]:
        """Split a pane; return the panes it became, in paint order.

        ``axis`` is the 2.0 spelling: :attr:`~motui.kernel.geom.Axis.X`
        divides the width (panes side by side) and
        :attr:`~motui.kernel.geom.Axis.Y` the height (panes stacked).
        ``weights`` are the children's shares -- ``(2, 1)`` gives the first
        twice the cells of the second -- and ``(1, 1)`` is the default.
        ``min_size`` is the floor each child is raised to.

        ``pane`` names the target: an explicit pane (or id) wins, and with
        none named the focused pane splits.  Two weights give the
        ``(left, right)`` or ``(top, bottom)`` pair; more give one pane per
        weight.  The same code path :meth:`~motui.kernel.frame.Pane.split`
        runs, so a pane splits itself identically.

        The first child keeps the split pane's document, so the transcript
        stays put; every child after it opens over a fresh, empty document
        -- ``right.document.add(markdown)`` is the preview side of a
        transcript | preview split.  A split leaves focus where it was (the
        first child) and re-divides the tiling immediately, so the returned
        panes already hold their rectangles.

        ``separator=True`` divides the panes with a 1-cell inter-pane
        divider (:class:`~motui.kernel.frame.Separator`): the tmux
        convention, drawn in the workspace's :attr:`theme` -- ``accent``
        beside the focused pane and ``border`` otherwise -- and registered
        as chrome on the pane before each gap so it is budgeted rather than
        overlapping content.  ``False`` leaves the panes abutting, no
        divider and no cell spent on one.
        """
        if not isinstance(axis, Axis):
            raise ValueError(f"split axis must be an Axis, got {axis!r}")
        target = self._focus_pane(pane)
        children = target.split(axis, weights=weights, min_size=min_size)
        if separator:
            edge = "right" if axis is Axis.X else "bottom"
            for before, after in zip(children, children[1:]):
                before.add_chrome(Separator(self, before.id, after.id, edge).chrome)
        self._retile()
        self.refresh()
        return children

    def pane_at(self, x: int, y: int) -> Pane | None:
        """The pane a 0-based screen cell falls in, or ``None``.

        Strict in both directions: a cell outside the screen, outside every
        pane's span, or past the composition's rows answers ``None`` -- no
        clamping to the nearest pane.  The cell routes through the frame's
        ownership table, so chrome columns and dock rows resolve to the pane
        that claims them.
        """
        if not (0 <= x < self.screen.width and 0 <= y < self.screen.height):
            return None
        table = self._frame.table
        if table is None:
            return None  # no composition has run yet
        span = table.resolve(y, x)
        return None if span is None else self._frame.pane(span.pane_id)

    def visible_range(self, pane: Pane | str | None = None) -> RowSpan | None:
        """A pane's visible body rows as screen rows (the focused pane by default).

        ``first``/``last`` are *screen* rows and include the pane's top
        chrome offset (``ScreenLayout.viewport_start``): the range a drag-to-edge
        gesture must not scroll past, and what a host drawing over the
        window needs.  Read off the last composition's pane layout and
        placement -- never a fresh layout.  ``None`` before the first
        composition, for a pane the frame does not hold, and for a body with
        no rows (a zero-height pane, or fixed regions filling it).
        """
        if pane is None:
            target = self._frame.focused_pane
        elif isinstance(pane, str):
            target = self._frame.pane(pane)
        else:
            target = self._frame.pane(pane.id)
        if target is None:
            return None
        placement = self._frame.region(target.id)
        layout = self._frame.pane_layout(target.id)
        if placement is None or layout is None or not layout.body_rows:
            return None
        first = placement.y + layout.viewport_start
        return RowSpan(first, first + len(layout.body_rows) - 1)

    # -- the docks -----------------------------------------------------------------

    def dock(
        self,
        component: Component,
        *,
        placement: Placement = Placement.BOTTOM,
        size: int | None = None,
    ) -> Pane:
        """Dock ``component`` at ``placement``; return its pane.

        ``placement`` is :attr:`~motui.kernel.document.Placement.BOTTOM`
        (the default) or ``TOP``; ``FLOW`` raises ``ValueError`` (a dock is
        never part of the scrolling body).

        A dock is a frame-level region outside the pane area, holding its
        own viewport built around the component handed over: the component
        joins a fresh document under a frame-wide unique block id and the
        viewport lays it out.  Its rows span the full frame width, join the
        ownership table (a footer block under the pointer resolves through
        :meth:`hit` exactly as a pane's rows do), but it takes neither
        focus nor splits, and a wheel over it scrolls the focused pane
        instead.  ``size=None`` derives the height from the content
        (:meth:`~motui.kernel.layout.Viewport.natural_height`); an
        explicit size is used as given, clamped to the screen.  An empty
        dock claims no rows and paints nothing.  One dock per edge; a
        second :meth:`dock` on the same edge raises ``RuntimeError``.
        """
        edge = _dock_edge(placement)
        if self._frame.dock(edge) is not None:
            raise RuntimeError(f"the frame already holds a {edge} dock")
        document = Document()
        document.add(component, id=self._next_block_id())
        dock = Pane(
            self._frame.next_pane_id(),
            Rect(x=0, y=0, width=0, height=0),
            Viewport(document),
        )
        self._dock_sizes[edge] = size
        self._frame.set_dock(edge, dock)
        self._retile()
        self.refresh()
        return dock

    def undock(
        self,
        placement: Placement = Placement.BOTTOM,
    ) -> Pane | None:
        """Release the dock named by ``placement``; ``None`` when that edge is empty.

        ``Placement.BOTTOM`` (the default) or ``TOP`` select the band;
        anything else raises ``ValueError``.
        """
        edge = _dock_edge(placement)
        pane = self._frame.dock(edge)
        if pane is None:
            return None
        self._frame.set_dock(edge, None)
        self._dock_sizes[edge] = None
        self._retile()
        self.refresh()
        return pane

    def dock_region(self, placement: Placement = Placement.BOTTOM) -> Rect | None:
        """The rectangle the last composition laid the dock on ``placement`` in."""
        pane = self._frame.dock(_dock_edge(placement))
        return None if pane is None else self._frame.region(pane.id)

    def _dock_height(self, edge: str, width: int, height: int) -> int:
        """The dock height on ``edge`` at ``width``: explicit size or natural content."""
        pane = self._frame.dock(edge)
        if pane is None:
            return 0
        size = self._dock_sizes.get(edge)
        wanted = pane.viewport.natural_height(width) if size is None else size
        return max(0, min(wanted, height))

    def _retile(self) -> None:
        """Lay the tiling out for the screen as it stands right now.

        The pane area is the whole screen minus the top and bottom docks; the
        top dock takes its rows at the top, the bottom dock at the bottom
        (clamped so the two never overlap), and the content leaves get what
        remains.  A same-size retile is a no-op, so the tree is re-divided
        only when something it lays out actually moved: the frame's
        structure changed since the last retile
        (:attr:`~motui.kernel.frame.Frame.revision` -- a split, a close,
        a chrome or overlay registration, a dock), or the computed tiling
        differs from the recorded one, which a dock's own content can move
        without any frame mutation (its height is
        :meth:`~motui.kernel.layout.Viewport.natural_height`, read off the
        document it shows).  A zero-height dock is released (an empty
        rectangle), so it paints nothing and owns no row: no ghost line.
        """
        width, height = self.screen.width, self.screen.height
        top_h = self._dock_height("top", width, height)
        bottom_h = min(
            self._dock_height("bottom", width, height), max(0, height - top_h)
        )
        top = Rect(x=0, y=0, width=width, height=top_h) if top_h > 0 else None
        bottom = (
            Rect(x=0, y=height - bottom_h, width=width, height=bottom_h)
            if bottom_h > 0
            else None
        )
        pane_rect = Rect(
            x=0, y=top_h, width=width, height=max(0, height - top_h - bottom_h)
        )
        tiling = (pane_rect, top, bottom)
        if self._tiling == tiling and self._tiling_revision == self._frame.revision:
            return
        self._tiling = tiling
        self._tiling_revision = self._frame.revision
        self._frame.retile(pane_rect, docks={"top": top, "bottom": bottom})

    def _reset(self) -> None:
        """Reset the per-run workspace state (selection and the retile memo)."""
        self._selection = None
        self._selection_pane_id = None
        self._tiling = None
        self._tiling_revision = None

    # -- selection --------------------------------------------------------------

    def set_selection(
        self, selection: Selection | None, *, pane: Pane | str | None = None
    ) -> None:
        """Replace the selection and repaint; ``None`` clears it.

        The one write on that surface: the stored overlay is applied by
        :func:`~motui.kernel.selection.highlight` between layout and
        paint (D2), so the next frame -- and everything that reads the
        presented frame, from ``workspace.rows`` to headless assertions on the
        painted rows -- shows the marked rows.  Because the selection lives
        in document space (D1), scrolling moves the text under a stationary
        range and leaves the highlight exactly where it was set; a width
        change (reflow) clears it instead, since the columns of one width
        address different glyphs at another (D8).

        ``pane`` names the document the range's addresses live in -- the pane
        a gesture anchored its drag in, which is the only thing that tells one
        document's ``b0`` from another's.  ``None`` (the default) resolves it
        to the focused pane; a pane the frame does not hold raises
        ``ValueError``, the same answer :meth:`~motui.kernel.frame.Frame.focus`
        gives an unknown id.  A ``selection`` of ``None`` clears both.
        """
        if selection is None:
            self._set_selection(None, None)
            return
        pane_id = self._pane_id(pane) if pane is not None else self._focused_id()
        self._set_selection(selection, pane_id)

    def _set_selection(
        self, selection: Selection | None, pane_id: str | None
    ) -> None:
        """The one write on the workspace's selection surface.

        Both halves of a selection's identity change together -- the stored
        range and the pane its addresses live in -- and the frame is marked
        dirty, so every writer lands here: :meth:`set_selection` and the
        reflow clear :meth:`Runtime._paint_at` runs.
        """
        self._selection = selection
        self._selection_pane_id = pane_id
        self.refresh()

    def _focused_id(self) -> str | None:
        """The focused pane's id, ``None`` on a frame that holds none."""
        pane = self._frame.focused_pane
        return None if pane is None else pane.id

    def _pane_id(self, pane: Pane | str) -> str:
        """The id of ``pane``, which the frame must hold (``ValueError``)."""
        pane_id = pane if isinstance(pane, str) else pane.id
        if self._frame.pane(pane_id) is None:
            raise ValueError(
                f"unknown pane {pane_id!r}: the frame holds "
                f"{[held.id for held in self._frame.panes]}"
            )
        return pane_id

    # -- mouse hit test ------------------------------------------------------------

    def hit(self, x: int, y: int) -> Hit | None:
        """Resolve a 0-based terminal cell to a pane, a block and a cell in it.

        ``x``/``y`` are 0-based, exactly as a
        :class:`~motui.kernel.events.MouseEvent` reports them (the decoder
        subtracts 1 from the terminal's 1-based report fields), so an event's
        own ``x``/``y`` go straight in.  Out-of-bounds coordinates -- either
        axis below zero or at/past the screen -- answer ``None``; they are
        never clamped.  The cell routes through the frame's ownership table
        -- which pane claims it, and the document address inside that pane --
        and ``Hit.col`` is measured against that pane's **inner rect**
        (chrome subtracted), so a left chrome column is not column zero of
        the block.  A cell in chrome, a row no block owns (the blank fill
        below short content), a cell no span claims, and a block removed
        since the last layout all resolve to ``None``.

        The result carries the pane, the block, the block-internal
        coordinates and the ancestor chain the cell descends to
        (:func:`~motui.kernel.document.descend_chain`).  The workspace never
        dispatches clicks itself: the host reads the
        :class:`~motui.kernel.events.MouseEvent` from ``read_event``,
        resolves it here, and calls the leaf itself::

            event = await runtime.read_event()
            if isinstance(event, MouseEvent):
                hit = workspace.hit(event.x, event.y)
                if hit is not None and hit.leaf is not None:
                    hit.leaf.on_click(Pos(y=hit.leaf_row, x=hit.leaf_col))

        :meth:`hit_leaf` is the convenience entry when the pane and the
        block address are not needed.
        """
        if not (0 <= x < self.screen.width and 0 <= y < self.screen.height):
            return None  # never clamp an out-of-bounds report
        frame = self._frame
        table = frame.table
        if table is None:
            return None  # no composition has run yet
        span = table.resolve(y, x)
        if span is None or span.block_id is None:
            return None  # outside every pane, or the pane's blank fill
        pane = frame.pane(span.pane_id)
        if pane is None:
            return None
        placement = frame.region(pane.id)
        if placement is None:
            return None  # the pane was never laid out
        if not (
            placement.x <= x < placement.right
            and placement.y <= y < placement.bottom
        ):
            return None  # a chrome cell owns no block coordinate
        try:
            block = pane.viewport.document.get(span.block_id)
        except KeyError:
            return None  # removed since the last layout
        row = span.row_in_block
        col = x - placement.x
        chain = descend_chain(block.widget, row, col)
        return Hit(pane, block, row, col, chain)

    def hit_leaf(self, x: int, y: int) -> tuple[Component, int, int] | None:
        """The deepest component owning a cell, with its own coordinates.

        :meth:`hit` resolves the pane and the block; this hands back just the
        leaf walk's result -- the component a host dispatches a click to and
        the cell in its own ``render`` output.  ``None`` exactly where
        :meth:`hit` answers ``None``.  The containers answer from their last
        render, so a component that has not painted yet declines every cell
        and the walk stops at the outermost component.
        """
        hit = self.hit(x, y)
        if hit is None or hit.leaf is None:
            return None
        return hit.leaf, hit.leaf_row, hit.leaf_col
