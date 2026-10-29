"""The workspace: the document, frame, panes, hit test, selection and docks.

The state owner behind :class:`~motui.app.runtime.Runtime`; every mutation
calls :meth:`refresh`. Dispatch order everywhere: chrome, then overlays,
then pane content, then host dispatch."""

from __future__ import annotations

import itertools
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
    """The frame edge a dock placement names; ``FLOW`` is not a dock."""
    if not isinstance(placement, Placement):
        raise ValueError(f"dock placement must be a Placement, got {placement!r}")
    if placement is Placement.FLOW:
        raise ValueError("a dock cannot use Placement.FLOW")
    return placement.value


def _body_address(viewport: Viewport, block: Section, row: int, width: int) -> int:
    """The body-row index of ``(block, row)``; counts come from the blocks'
    row caches, never from re-wrapping rows."""
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
    """The selection screen, overlay #1 of the frame's registry.

    It marks the layout of the pane the selection was anchored in -- block
    ids repeat per document, so guessing the pane from focus would mark a
    neighbour's rows."""

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

    ``theme`` styles only the workspace's own chrome. A split mutates the
    tiling in place, so the frame keeps its overlays and focus and every pane
    keeps its viewport, chrome and scroll state."""

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
        """The workspace's frame: its tiling, docks, overlays and focus."""
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
        """The document-space selection, ``None`` when there is none; written
        whole through :meth:`set_selection`."""
        return self._selection

    @property
    def selection_pane(self) -> Pane | None:
        """The pane the stored selection's addresses live in, or ``None``; block
        ids are per document, and a closed pane takes them with it."""
        if self._selection is None or self._selection_pane_id is None:
            return None
        return self._frame.pane(self._selection_pane_id)

    # -- document facade ---------------------------------------------------------

    def pane(self, pane_id: str) -> Pane:
        """The pane with ``pane_id`` (content pane or dock); unknown raises
        ``KeyError``."""
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
        """Resolve a content target: an explicit pane, else ``primary``, else the
        first content pane. Focus is not consulted -- ownership must not move
        when the user clicks another pane."""
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
        """Append a block to a pane's document; return its section.

        With no ``pane`` the main pane (``primary`` first) is targeted, never the
        focused one: focus routes input, not ownership. Section ids are unique
        across the whole frame."""
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
        """Make ``component`` the fill of a pane (the main pane by default) and
        repaint."""
        target = self._content_pane(pane)
        section = target.fill(component)
        self.refresh()
        return section

    def _holder(self, id: str) -> Pane:
        """The one pane whose document holds ``id``; no holder raises ``KeyError``,
        several raise ``ValueError`` naming them."""
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
        """The section with ``id`` from any pane's document; an ambiguous id raises
        ``ValueError``."""
        return self._holder(id).viewport.document.get(id)

    def remove(self, id: str) -> Section:
        """Detach the block with ``id`` and answer its section, by the same
        frame-wide resolution :meth:`get` performs."""
        section = self._holder(id).viewport.document.remove(id)
        self.refresh()
        return section

    def system(self, text: str, *, pane: Pane | str | None = None) -> Section:
        """Append ``text`` as a muted system block; the target follows :meth:`add`."""
        return self.add(Text(text, style=self.theme.text.muted), pane=pane)

    # -- scroll facade --------------------------------------------------------

    def _focused_viewport(self) -> Viewport:
        """The viewport the scroll facades move: the focused pane's window."""
        pane = self._frame.focused_pane
        return self.viewport if pane is None else pane.viewport

    def scroll_up(self, n: int = 1) -> None:
        """Scroll the focused viewport ``n`` rows toward the top and repaint."""
        self._focused_viewport().scroll_up(n)
        self.refresh()

    def scroll_down(self, n: int = 1) -> None:
        """Scroll the focused viewport ``n`` rows toward the bottom and repaint."""
        self._focused_viewport().scroll_down(n)
        self.refresh()

    def scroll_to_bottom(self) -> None:
        """Re-attach the focused viewport to the bottom and repaint."""
        self._focused_viewport().scroll_to_bottom()
        self.refresh()

    def reveal(self, bid: str, row: int) -> bool:
        """Bring the document address ``bid``/``row`` on screen; ``False`` when
        unknown.

        The pane moved is the one that **holds** the block, never the focused
        pane. An already-visible target moves nothing; otherwise it is centered
        where the viewport's clamp allows."""
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

        The first child keeps the document and focus; later children open empty
        documents. ``separator=True`` registers a themed 1-cell divider as chrome
        on the pane before each gap."""
        if not isinstance(axis, Axis):
            raise ValueError(f"split axis must be an Axis, got {axis!r}")
        target = self._focus_pane(pane)
        children = target.split(axis, weights=weights, min_size=min_size)
        if separator:
            edge = "right" if axis is Axis.X else "bottom"
            for before, after in itertools.pairwise(children):
                before.add_chrome(Separator(self, before.id, after.id, edge).chrome)
        self._retile()
        self.refresh()
        return children

    def pane_at(self, x: int, y: int) -> Pane | None:
        """The pane a 0-based screen cell falls in, or ``None``; never clamped to
        the nearest pane."""
        if not (0 <= x < self.screen.width and 0 <= y < self.screen.height):
            return None
        table = self._frame.table
        if table is None:
            return None  # no composition has run yet
        span = table.resolve(y, x)
        return None if span is None else self._frame.pane(span.pane_id)

    def visible_range(self, pane: Pane | str | None = None) -> RowSpan | None:
        """A pane's visible body rows as screen rows (the focused pane by default);
        ``None`` before composition or when the body has no rows."""
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
        """Dock ``component`` at ``TOP``/``BOTTOM``; return its pane.

        The dock is a frame-level region with its own viewport; it joins hit
        testing but takes neither focus nor splits. ``size=None`` derives the
        height from the content."""
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
        """Release the dock at ``placement``; ``None`` when that edge is empty."""
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
        """The dock height: explicit size or content-derived, clamped to the screen."""
        pane = self._frame.dock(edge)
        if pane is None:
            return 0
        size = self._dock_sizes.get(edge)
        wanted = pane.viewport.natural_height(width) if size is None else size
        return max(0, min(wanted, height))

    def _retile(self) -> None:
        """Lay the tiling out for the current screen; a same-size retile with an
        unchanged frame revision is a no-op."""
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

        ``pane`` names the document the addresses live in (default: focused).
        The selection is document-space, so scrolling keeps it; a reflow clears
        it because columns address different glyphs at another width."""
        if selection is None:
            self._set_selection(None, None)
            return
        pane_id = self._pane_id(pane) if pane is not None else self._focused_id()
        self._set_selection(selection, pane_id)

    def _set_selection(
        self, selection: Selection | None, pane_id: str | None
    ) -> None:
        """The one write on the selection surface: range and pane change together
        and the frame is marked dirty."""
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
        """Resolve a 0-based cell to a pane, a block and block coordinates, or
        ``None``.

        Out-of-bounds and unowned cells are never clamped; ``col`` is measured
        against the pane's inner rect (chrome subtracted) and the result carries
        the ancestor chain."""
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
        """The deepest component owning a cell, with its own coordinates; ``None``
        exactly where :meth:`hit` answers ``None``."""
        hit = self.hit(x, y)
        if hit is None or hit.leaf is None:
            return None
        return hit.leaf, hit.leaf_row, hit.leaf_col
