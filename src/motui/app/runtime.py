"""The runtime: full-screen lifecycle, document facade, pump, and dump.

:class:`Runtime` ties the kernel together -- a
:class:`~motui.kernel.document.Document`, the
:class:`~motui.kernel.layout.Viewport` over it, a
:class:`~motui.terminal.paint.Painter` and a
:class:`~motui.terminal.screen.Screen` -- and adds the runtime behaviour a
full-screen application needs:

* a **document facade** (``add``/``get``/``remove``/``system``) where every
  mutation invalidates the frame, addressing components rather than blocks:
  ``add`` answers the block id, ``get``/``remove`` the component itself;
* **scroll facades** -- the directed moves in :meth:`Runtime.scroll_up` /
  :meth:`Runtime.scroll_down` / :meth:`Runtime.scroll_to_bottom`, and
  :meth:`Runtime.reveal`, which brings a document address on screen
  (centered, clamped at the edges) on the same focused-pane rule;
* a **mouse hit test** (:meth:`Runtime.hit`) that resolves a report's
  coordinates to the block and cell under them -- routed through the
  frame's ownership table, with the ancestor chain
  (:func:`~motui.kernel.document.descend_chain`) carried on the result -- and
  :meth:`Runtime.hit_leaf` for the deepest component alone.  The driver never
  dispatches a click: the host routes the event;
* one optional **document-space selection** (:attr:`Runtime.selection` /
  :meth:`Runtime.set_selection`) painted by the frame's first overlay between
  layout and paint, so the highlight follows its text through scrolls
  (D1-D2) -- the range carries the pane its addresses live in
  (:attr:`Runtime.selection_pane`), since block ids are numbered per document;
* the **split and focus surface** -- :meth:`Runtime.split` (one code path with
  :meth:`~motui.kernel.frame.Pane.split`) and the pane a press focuses
  (:attr:`Runtime.frame`'s own focus record; the default press policy now
  lives in :class:`~motui.app.application.App`);
* one optional **dock pair** (:meth:`Runtime.dock`) -- frame-level regions
  above and below the pane area, each holding its own viewport built
  around the component handed over, where the assembly tier parks a
  header and a footer (D6);
* a small **protocol surface** -- :meth:`Runtime.set_title` (OSC 2) and
  :meth:`Runtime.set_cursor_shape` (DECSCUSR): the two host-owned window
  gestures, written through the screen; the library declares (``Input`` /
  ``Editor`` carry ``cursor_shape="beam"``), the host decides;
* a **pump** (``tick``/``clock``/``_wake_up``/``_pump``) that repaints on a
  throttle and runs cancellable periodic callbacks, with the clock as a seam
  tests can inject -- the library itself never builds an event loop, never
  sleeps, and never touches a sink outside the painter;
* :meth:`Runtime.run_session` / :meth:`Runtime.run_async` / :meth:`Runtime.run`, which
  bracket ``enter``/``leave`` around the body (even on exceptions and
  ``exit()``), stay completely silent on a non-live screen, and dump the
  final screen as plain text when piped.

:meth:`Runtime.read_event` is a **pure read**: it returns the next event or
``None`` and owns no scroll or focus policy.  The default orchestration
(wheel routing, focus-on-press, modal/toast/gesture/pointer/focus tiers)
lives one level up in :class:`~motui.app.application.App`; a host driving ``Runtime``
directly keeps its own loop.

**The dispatch order**, one rule everywhere: a composition paints each
pane's chrome budget first, then that pane's content rows, then the granted
granted chrome strips over them, then the docks, then the overlay registry over everything
(:mod:`motui.kernel.frame`); a host routes an event the same way --
chrome, then overlays, then the panes' content, then its own dispatch
(:mod:`motui.app.overlays`).
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable

from ..terminal.ansi import cursor_shape, set_window_title
from ..kernel.document import Placement, Section, Component, Document, Sizing, descend_chain
from ..kernel.geom import Axis, Pos
from ..kernel.frame import Separator
from ..kernel.events import Event, EventSource
from ..kernel.frame import Frame, Pane, Rect
from ..kernel.hit import Hit, RowRange
from ..kernel.cell import Line
from ..widgets.text import Text
from ..terminal.paint import Painter
from ..terminal.screen import MouseMode, Screen
from ..terminal.terminal import Terminal
from ..kernel.selection import Selection, highlight
from ..kernel.theme import DEFAULT_THEME, Theme
from ..kernel.layout import ScreenLayout, Viewport
from ..terminal import RawTerminalKeys
from ..kernel.layout import Constraints
from .workspace import Workspace

__all__ = ["Runtime"]


class Timer:
    """One periodic callback scheduled on the driver's clock.

    ``next_run`` is an **absolute deadline**, not a delay: each firing adds
    exactly one ``period`` to it, so a callback that takes time to run does
    not push the schedule out.  When a tick arrives late, ``catch_up`` picks
    the posture -- ``"skip"`` runs the callback once and realigns the next
    deadline to ``now + period`` when the deadline already passed, while
    ``"coalesce"`` runs once and advances the deadline by whole periods until
    it is in the future, preserving the phase.  Either way one tick invokes a
    callback at most once.

    The value is its own cancellable handle: ``cancelled`` answers whether
    :meth:`cancel` has run, and a cancelled timer never fires again.  The
    1.x separate handle class is gone; ``every`` is the only constructor a
    host needs.
    """

    __slots__ = ("_cancelled", "catch_up", "fn", "next_run", "period")

    def __init__(
        self,
        period: float,
        fn: Callable[[], object],
        next_run: float = 0.0,
        *,
        catch_up: str = "skip",
    ) -> None:
        if period <= 0:
            raise ValueError(f"timer period must be positive, got {period!r}")
        if catch_up not in ("skip", "coalesce"):
            raise ValueError(
                f"catch_up must be 'skip' or 'coalesce', got {catch_up!r}"
            )
        self._cancelled = False
        self.period = period
        self.fn = fn
        self.next_run = next_run
        self.catch_up = catch_up

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def cancel(self) -> None:
        """Stop future invocations (a callback already running finishes)."""
        self._cancelled = True

    def __repr__(self) -> str:
        return (
            f"Timer(period={self.period!r}, next_run={self.next_run!r}, "
            f"catch_up={self.catch_up!r}, cancelled={self.cancelled})"
        )


def _stdin_isatty() -> bool:
    """Whether stdin is a TTY right now (never raises)."""
    try:
        stream = sys.stdin
        return stream is not None and bool(stream.isatty())
    except Exception:
        return False


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


class _SelectionOverlay:
    """The driver's selection screen: overlay #1 of the frame's registry.

    Wraps the kernel's :func:`~motui.kernel.selection.highlight` in the
    overlay protocol -- the frame hands it the composed rows, it marks the
    layout of the pane the selection lives in and the marked rows are spliced
    back where that pane's came from.  The stored selection is read off the
    driver at paint time, so :meth:`Runtime.set_selection` stays the one write on
    that surface and a ``None`` paints the rows exactly as they were composed.

    The pane matters more than it looks: block ids are numbered per document,
    so a split's second child holds a ``b0`` exactly as the first does, and an
    overlay that guessed a pane from the focus would mark a *neighbour's* rows
    at those colliding addresses.  :meth:`Runtime.set_selection` therefore records
    the pane alongside the range, and a pane the frame no longer holds paints
    nothing -- its document went with it (D8's vanished addresses).
    """

    def __init__(self, tui: Runtime) -> None:
        self._tui = tui

    def paint(self, frame: Frame) -> ScreenLayout:
        selection = self._tui._selection
        if selection is None:
            return frame.layout
        pane_id = self._tui._selection_pane_id
        if pane_id is None or frame.pane(pane_id) is None:
            return frame.layout
        marked = highlight(
            frame.pane_layout(pane_id),
            selection,
            style=self._tui.theme.text.selection,
        )
        return frame.with_pane_rows(pane_id, marked.rows)


def _body_address(viewport: Viewport, block: Section, row: int, width: int) -> int:
    """The body-row index of ``(block, row)`` in the viewport's document.

    The document order walks the blocks and sums what the unpinned ones
    occupy before ``block`` -- each measured at ``width``, the width the
    pane was last laid out at, exactly as the viewport counts its own body
    (fixed-region rows are not body rows) -- and ``row`` lands on that
    prefix, clamped into the block's own rendered rows (an empty block
    answers its first row).  The counts come from each block's count gate
    (:meth:`~motui.kernel.document.Section.row_count`): the layout just filled
    the same cache, so the walk reads counts instead of re-wrapping rows,
    and a block whose content moved carries a moved revision, so no count
    is stale.  The half of :meth:`Runtime.reveal` that is pure arithmetic over
    the document; the caller has already resolved the block out of the
    document, so the walk is total.
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


class Runtime:
    """A full-screen application driver.

    ``terminal`` is the one configuration door: a
    :class:`~motui.terminal.terminal.Terminal` brings its own screen (with
    the mouse mode already mapped), input source and clipboard, and the
    driver enters, leaves and reads through it.  The input source defaults
    to none (``read_event`` then returns ``None``); a screen's tracking
    switches live on its :class:`~motui.terminal.screen.TerminalOptions`,
    never here.

    ``interactive`` says whether :meth:`run` may attach a
    :class:`RawTerminalKeys` source when the session is live and no source
    was supplied; it is off by default, so a test-driven runtime never
    touches the real input.  ``throttle`` is the pump's flush interval.
    ``theme`` is the driver's own theme (default
    :data:`~motui.kernel.theme.DEFAULT_THEME`), read by the chrome the
    driver composes -- the split's divider
    (:class:`~motui.kernel.frame.Separator`); widgets are never themed
    from here, they each take ``theme=`` themselves.

    Internally the driver holds one
    :class:`~motui.kernel.frame.Frame` whose primary pane is
    :attr:`document` / :attr:`viewport`: every frame composes through it
    (a single-pane frame composes to its pane's own layout), :meth:`hit`
    routes through its ownership table, the scroll facades move its
    focused pane's viewport, and the selection highlight is the frame's
    first overlay.  :meth:`split` divides a pane of that tiling in place --
    the frame keeps its identity, its overlays and its focus across the
    division, and every pane keeps its viewport, its chrome and its scroll
    state -- so a split adds panes without any new plumbing, and a resize
    re-divides the same tree instead of rebuilding panes.
    """

    def __init__(
        self,
        terminal: Terminal,
        *,
        throttle: float = 0.030,
        interactive: bool = False,
        theme: Theme | None = None,
    ) -> None:
        self._terminal = terminal
        self._screen = terminal.screen
        #: The event source the runtime reads; :meth:`run` may replace it with
        #: a server-owned raw source when the session is interactive.
        self.keys = terminal.input
        #: The hover switch the attached raw source opens: the terminal's
        #: mouse mode is the one configuration point.
        self._hover = terminal.options.mouse is MouseMode.MOVE
        self._document = Document()
        self._viewport = Viewport(self._document)
        #: The theme the driver's own chrome reads (the split's divider);
        #: widgets take their own ``theme=`` and are never themed from here.
        self.theme = DEFAULT_THEME if theme is None else theme
        # The initial tiling: one pane, the primary, its whole rectangle the
        # screen -- held by the frame every composition routes through.  The
        # rectangle is a placeholder until the first paint retiles it to the
        # live screen; the selection highlight rides the frame as overlay #1.
        self._frame = Frame([Pane("primary", Rect(x=0, y=0, width=0, height=0), self._viewport)])
        self._frame.add_overlay(_SelectionOverlay(self), layer="selection")
        # Structural frame changes (split/close/chrome/dock/overlay) mark the
        # driver dirty by themselves: a host never follows them with refresh().
        self._frame.on_change = self.refresh
        self.painter = Painter(self._screen, sync=terminal.options.sync)
        self.throttle = throttle
        self.interactive = interactive
        self._dirty = True
        self._stopped = False
        self._last_paint = float("-inf")
        self._selection: Selection | None = None
        #: The pane the stored selection's addresses live in (its id), the
        #: document half of the range's identity: ``None`` with no selection,
        #: and a pane that leaves the frame takes the selection's meaning with
        #: it (the overlay then paints nothing).  Written only through
        #: :meth:`_set_selection`, alongside :attr:`_selection`.
        self._selection_pane_id: str | None = None
        self._layout_width: int | None = None
        self._timers: list[Timer] = []
        #: The cached Workspace facade (created on first access); it delegates
        #: every member back here and holds no state of its own.
        self._workspace: Workspace | None = None
        #: The clock the driver adds its virtual offset to.  A test may swap
        #: this (or replace ``clock`` outright) to control time.
        self._clock: Callable[[], float] = time.monotonic
        #: The virtual time :meth:`advance` has added to the clock.
        self._clock_offset = 0.0
        self._wake_event: asyncio.Event | None = None
        self._wake_loop: asyncio.AbstractEventLoop | None = None
        #: The source this driver attached itself (never one the caller handed
        #: in): teardown closes exactly this, whatever ``self.keys`` says then.
        self._owned_source: EventSource | None = None
        #: Set by :meth:`exit` and awaited by :meth:`read_event`: a pending
        #: read returns ``None`` the moment the session ends.
        self._exit_event: asyncio.Event | None = None
        #: The explicit dock heights, per edge; ``None`` means content-derived.
        self._dock_sizes: dict[str, int | None] = {"top": None, "bottom": None}
        #: The rectangles the last retile laid out (pane area, top dock,
        #: bottom dock) and the frame revision it ran at, so a same-size paint
        #: with an unchanged tree retiles nothing.
        self._tiling: tuple[Rect, Rect | None, Rect | None] | None = None
        self._tiling_revision: int | None = None

    # -- read-only views ---------------------------------------------------------

    @property
    def screen(self) -> Screen:
        """The driver's screen; a host never replaces it mid-run."""
        return self._screen

    @property
    def terminal(self) -> Terminal:
        """The terminal endpoint this runtime enters, leaves and reads through.

        The one configuration door: the terminal owns the screen, its input
        source and its clipboard, so the runtime never builds or replaces a
        screen by itself.
        """
        return self._terminal

    @property
    def workspace(self) -> Workspace:
        """The cached :class:`~motui.app.workspace.Workspace` facade over self.

        One facade per runtime: it holds no state of its own, so every read
        and write answers from this object and the two views can never drift.
        """
        if self._workspace is None:
            self._workspace = Workspace(self)
        return self._workspace

    # -- clipboard ---------------------------------------------------------------

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard through the terminal (OSC 52).

        The terminal's :class:`~motui.terminal.clipboard.ScreenClipboard`
        writes the bytes; a non-live screen answers ``False`` without
        touching the stream, exactly as :meth:`Screen.copy_to_clipboard
        <motui.terminal.screen.Screen.copy_to_clipboard>` does.
        """
        return self._terminal.clipboard.copy(text)

    @property
    def document(self) -> Document:
        """The primary pane's document (a read-only view of it)."""
        return self._document

    @property
    def viewport(self) -> Viewport:
        """The primary pane's viewport (a read-only view of it)."""
        return self._viewport

    # -- document facade ------------------------------------------------------

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
    ) -> str:
        """Append a block to a pane's document; answer its id.

        ``pane`` scopes the operation: an explicit pane (or pane id) wins,
        and with none named the **main** pane (``primary``, else the first
        content pane in paint order) is the target.  Focus routes input, not
        content ownership, so a click on another pane never changes where a
        producer's blocks land; pass ``pane=tui.frame.focused_pane`` when a
        focused-pane write is really what is meant.  ``placement``/``sizing``
        forward to :meth:`~motui.kernel.document.Document.add` (which owns
        the fill rules).  Section ids are unique across the whole frame: an
        automatic id is the first free ``bN`` over every pane's document,
        and an explicit id another pane already holds raises ``ValueError``.
        The id is the handle a host keeps: :meth:`get` and :meth:`remove`
        speak components, so the block value itself never has to cross the
        facade.
        """
        target = self._content_pane(pane)
        if id is None:
            id = self._next_block_id()
        elif self._panes_holding(id):
            raise ValueError(f"duplicate block id: {id!r}")
        target.viewport.document.add(
            component, id=id, placement=placement, sizing=sizing
        )
        self.refresh()
        return id

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

    def get(self, id: str) -> Component:
        """The component with ``id`` from any pane's document (``KeyError`` when missing).

        The search spans every content pane and dock.  An id two panes hold
        is not silently resolved to the first: it raises ``ValueError`` and
        names the panes, because frame-wide uniqueness is the contract.
        """
        return self._holder(id).viewport.document.get(id).widget

    def remove(self, id: str) -> Component:
        """Detach the block with ``id`` and answer its component.

        The same frame-wide resolution :meth:`get` performs; an ambiguous id
        raises ``ValueError`` listing the panes instead of picking one.
        """
        component = self._holder(id).viewport.document.remove(id).widget
        self.refresh()
        return component

    def system(self, text: str, *, pane: Pane | str | None = None) -> str:
        """Append a system block to a pane's document; default the main pane.

        The text is added as a muted :class:`~motui.kernel.text.Text`
        block, so a full-screen application never writes to stdout behind the
        painter's back.  ``pane`` follows :meth:`add`'s rule: explicit wins,
        and with none named the main document is the target -- system output
        is content, not input, so focus never chooses where it lands.
        Answer is the block id (:meth:`add`'s contract).
        """
        return self.add(Text(text, style=self.theme.text.muted), pane=pane)

    # -- protocol surface ---------------------------------------------------------

    def set_title(self, text: str) -> None:
        """Set the terminal window title (OSC 2), control bytes scrubbed.

        A host-owned gesture -- the driver never titles a window by itself
        (the demo titles one per page in its ``show``).  The bytes go
        through ``screen.write`` and a flush, and they are **not** gated on
        liveness: a headless screen or a test double records them, so the
        call is assertable without a terminal (only the session bracket and
        :meth:`Screen.copy` are live-gated).
        """
        self.screen.write(set_window_title(text))
        self.screen.flush()

    def set_cursor_shape(self, shape: str) -> None:
        """Ask the terminal for a cursor shape (DECSCUSR).

        ``block`` / ``beam`` / ``underline`` / ``default``; an unknown shape
        raises ``KeyError``.  The library only *declares* which shape a
        component wants -- ``Input`` and ``Editor`` carry
        ``cursor_shape="beam"`` -- and the host reads the focused leaf
        (``getattr(leaf, "cursor_shape", "block")``) and calls this; written
        like :meth:`set_title`, non-live screens included.
        """
        self.screen.write(cursor_shape(shape))
        self.screen.flush()

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

    @property
    def frame(self) -> Frame:
        """The driver's frame: its tiling, its docks, its overlays, its focus.

        The public seam the assembly tier reads -- a scrollbar resolves its
        pane's rectangle and layout through it, a toast its corner, and the
        gesture tier the pane a drag lives in.
        """
        return self._frame

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
        convention, drawn in the driver's :attr:`theme` -- ``accent``
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
                before.add_chrome(
                    Separator(self, before.id, after.id, edge).chrome
                )
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

    def visible_range(self, pane: Pane | str | None = None) -> RowRange | None:
        """A pane's visible body rows as screen rows (the focused pane by default).

        ``first``/``last`` are *screen* rows and include the pane's top pin
        offset (``ScreenLayout.viewport_start``): the range a drag-to-edge
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
        return RowRange(first, first + len(layout.body_rows) - 1)

    # -- the docks -----------------------------------------------------------------

    def dock(
        self,
        component: Component,
        *,
        placement: Placement = Placement.BOTTOM,
        size: int | None = None,
    ) -> Pane:
        """Pin ``component`` against a dock placement; return its pane.

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
        dock = Pane(self._frame.next_pane_id(), Rect(x=0, y=0, width=0, height=0), Viewport(document))
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
            Rect(x=0, y=height - bottom_h, width=width, height=bottom_h) if bottom_h > 0 else None
        )
        pane_rect = Rect(x=0, y=top_h, width=width, height=max(0, height - top_h - bottom_h))
        tiling = (pane_rect, top, bottom)
        if self._tiling == tiling and self._tiling_revision == self._frame.revision:
            return
        self._tiling = tiling
        self._tiling_revision = self._frame.revision
        self._frame.retile(pane_rect, docks={"top": top, "bottom": bottom})

    # -- frames ---------------------------------------------------------------

    def refresh(self) -> None:
        """Mark the frame dirty; the pump repaints once the throttle allows."""
        self._dirty = True
        self._wake()

    def paint(self) -> None:
        """Paint one frame right now, bypassing the throttle."""
        self._paint_at(self.clock())

    @property
    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows."""
        return self.painter.rows

    @property
    def selection(self) -> Selection | None:
        """The document-space selection overlay, ``None`` when there is none.

        The read half of the driver's selection surface (D3): the value is
        the kernel's :class:`~motui.kernel.selection.Selection`, written
        here whole by :meth:`set_selection` -- the driver stores it and owns
        no anchor or head arithmetic of its own (that is gesture policy).
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

    def set_selection(
        self, selection: Selection | None, *, pane: Pane | str | None = None
    ) -> None:
        """Replace the selection and repaint; ``None`` clears it.

        The one write on that surface: the stored overlay is applied by
        :func:`~motui.kernel.selection.highlight` between layout and
        paint (D2), so the next frame -- and everything that reads the
        presented frame, from ``tui.rows`` to headless assertions on the
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
        """The one write on the driver's selection surface.

        Both halves of a selection's identity change together -- the stored
        range and the pane its addresses live in -- and the frame is marked
        dirty, so every writer lands here: :meth:`set_selection` and the
        reflow clear :meth:`_paint_at` runs.
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

    def every(
        self,
        period: float,
        fn: Callable[[], object],
        *,
        catch_up: str = "skip",
    ) -> Timer:
        """Call ``fn`` every ``period`` seconds until the timer is cancelled.

        The schedule is deadline-based: the first run is one ``period``
        after registration and every run adds exactly one ``period`` to
        ``next_run`` (see :class:`Timer`).  ``fn`` takes no arguments and
        decides for itself whether to invalidate the frame; the pump invokes
        it from :meth:`tick`.  ``catch_up`` selects the missed-deadline
        posture (``"skip"`` or ``"coalesce"``).
        """
        timer = Timer(period, fn, self.clock() + period, catch_up=catch_up)
        self._timers.append(timer)
        self._wake()
        return timer

    def animation(self, hz: float, draw: Callable[[], object]) -> Timer:
        """Call ``draw`` at ``hz`` frames per second, deadline-based.

        The convenience over :meth:`every` an animated host wants: one
        callback per frame, with the same cancellation handle and catch-up
        policy.  A non-positive rate raises ``ValueError``.
        """
        if hz <= 0:
            raise ValueError(f"animation rate must be positive, got {hz!r}")
        return self.every(1.0 / hz, draw)

    def invalidate(self) -> None:
        """Mark the frame dirty (the 2.0 name for :meth:`refresh`)."""
        self.refresh()

    def paint_now(self) -> None:
        """Paint one frame right now, bypassing the throttle (see :meth:`paint`)."""
        self.paint()

    async def read_event(self) -> Event | None:
        """Read the next event, or ``None``.

        A **pure read**: the event comes back exactly as the source
        reported it -- a wheel report, a page key and a button press are
        all the host's to route.  The driver runs no scroll or focus policy
        here (the default orchestration is
        :class:`~motui.app.application.App`'s; a host driving ``Runtime`` directly owns
        its loop).  The result is ``None`` when there is no key source,
        when the source reports EOF, and -- per the toolkit's non-live
        contract -- always on a non-live screen, even when a source is
        attached.

        Escape hatch: ``await tui.keys.read()`` reads the raw source
        directly, bypassing the non-live guard.  A pending read returns
        ``None`` immediately when :meth:`exit` runs: the read task is
        cancelled and the source itself is closed by teardown.
        """
        if not self.screen.live:
            return None
        if self._terminal.input is None:
            return None
        read = self._terminal.read_event
        exit_event = self._exit_event
        if exit_event is None:
            self._exit_event = exit_event = asyncio.Event()
        while True:
            if self._stopped or exit_event.is_set():
                return None
            read_task = asyncio.ensure_future(read())
            exit_task = asyncio.ensure_future(exit_event.wait())
            try:
                done, _ = await asyncio.wait(
                    (read_task, exit_task), return_when=asyncio.FIRST_COMPLETED
                )
            except asyncio.CancelledError:
                read_task.cancel()
                exit_task.cancel()
                await asyncio.gather(read_task, exit_task, return_exceptions=True)
                raise
            if exit_task in done:
                read_task.cancel()
                await asyncio.gather(read_task, return_exceptions=True)
                return None
            exit_task.cancel()
            await asyncio.gather(exit_task, return_exceptions=True)
            return read_task.result()

    def exit(self) -> None:
        """End the session now: unblock reads, stop the pump, let teardown run.

        Safe from any task: :meth:`read_event` returns ``None`` immediately,
        the pump wakes and leaves, and the run's teardown closes an owned
        source and leaves the screen.
        """
        self._stopped = True
        if self._exit_event is None:
            self._exit_event = asyncio.Event()
        self._exit_event.set()
        self._wake()

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
        (:func:`~motui.kernel.document.descend_chain`).  The driver never
        dispatches clicks itself: the host
        reads the :class:`~motui.kernel.events.MouseEvent` from
        :meth:`read_event`, resolves it here, and calls the leaf itself::

            event = await tui.read_event()
            if isinstance(event, MouseEvent):
                hit = tui.hit(event.x, event.y)
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

    # -- pump -----------------------------------------------------------------

    def clock(self) -> float:
        """The driver's monotonic clock: the one seam time enters through.

        It answers ``_clock() + offset``: ``_clock`` is
        :func:`time.monotonic` unless a host replaces it, and the offset is
        the virtual time :meth:`advance` has added, so a replay script can
        move time without touching the system clock.  Timestamps (``every``
        schedules, toast expiries, double-click windows) read it, and a host
        or a test may also replace this method with its own reading.
        """
        return self._clock() + self._clock_offset

    def advance(self, dt: float) -> None:
        """Move the virtual clock by ``dt`` and run every deadline it crosses.

        The driver steps from due deadline to due deadline, running
        :meth:`tick` at each one -- timers fire exactly as they would have
        under a pump that never slept -- and lands on the target time with a
        final tick.  No real time is sampled between the steps and nothing
        sleeps, so a scripted interval replays deterministically.  A
        non-positive ``dt`` does nothing.
        """
        if dt <= 0:
            return
        target = self.clock() + dt
        while True:
            deadline = self._next_deadline()
            if deadline is None or deadline > target:
                break
            now = self.clock()
            if deadline > now:
                self._clock_offset += deadline - now
            self.tick(self.clock())
        now = self.clock()
        if target > now:
            self._clock_offset += target - now
        self.tick(self.clock())

    def _next_deadline(self) -> float | None:
        """The earliest scheduled deadline, ``None`` when no live timer exists."""
        deadlines = [
            timer.next_run for timer in self._timers if not timer.cancelled
        ]
        return min(deadlines) if deadlines else None

    def _paint_at(self, now: float) -> None:
        """Paint one frame and record ``now`` as the last flush time.

        Sample the screen size, retile the tiling to it (the pane area
        minus the docks' rows, the docks at their edges), compose the frame, run
        the frame's overlay pipeline over the composition (the selection
        highlight is overlay #1), and paint the diff.  A retile re-divides
        the recorded split tree instead of rebuilding the panes, so every
        pane keeps its viewport, its chrome registry and its scroll state,
        the frame keeps its overlays and its focus, and nothing has to be
        carried across.  A single-pane frame with no dock composes to its
        pane's own layout, so the row stream is the one the viewport laid
        out -- not a re-derivation of it.  A new width clears the selection
        (reflow), a new height does not.

        The sampling here is the driver's own: the retile and the reflow
        test both need the size *before* the composition runs, while
        :meth:`~motui.terminal.paint.Painter.paint` samples again for
        its full-repaint test, per the :class:`~motui.terminal.screen.Screen`
        protocol's "the painter calls it before every frame".  Neither
        sample can move to the other side without composing one frame at a
        stale size.
        """
        self.screen.refresh_size()
        width, height = self.screen.width, self.screen.height
        self._retile()
        if width != self._layout_width:
            self._layout_width = width
            # reflow: the columns of one width address other glyphs (D8)
            self._set_selection(None, None)
        layout = self._frame.compose(width, height)
        layout = self._frame.apply_overlays(layout)
        self.painter.paint(layout.surface)
        self._last_paint = now
        self._dirty = False

    def _wake(self) -> None:
        """Wake the pump, from the loop thread or (safely) from another one."""
        event, loop = self._wake_event, self._wake_loop
        if event is None or loop is None:
            return  # no pump is waiting yet; the next tick sees the flags
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            event.set()
        elif not loop.is_closed():
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                pass  # the loop closed between the check and the call

    def _wake_up(self) -> asyncio.Event:
        """The pump's wake event, created lazily and bound to the running loop."""
        loop = asyncio.get_running_loop()
        if self._wake_event is None or self._wake_loop is not loop:
            self._wake_event = asyncio.Event()
            self._wake_loop = loop
        return self._wake_event

    def tick(self, now: float) -> float | None:
        """Advance the pump one step; return the seconds until the next wake.

        The pump's manual seam: due timers run first (they may invalidate the
        frame), then at most one frame is painted -- only when the document
        is dirty *and* the throttle has elapsed since the last flush.  Each
        due timer fires at most once and reschedules from its own deadline
        (see :class:`Timer`), so a late tick never shifts the phase.  The
        return value is the delay until the pump next needs to run, or
        ``None`` when nothing is pending and the pump should sleep until
        woken.
        """
        if self._timers:
            alive: list[Timer] = []
            for timer in self._timers:
                if timer.cancelled:
                    continue
                if now >= timer.next_run:
                    timer.fn()
                    if timer.cancelled:
                        continue
                    self._reschedule(timer, now)
                alive.append(timer)
            self._timers = alive
        if self._dirty and now - self._last_paint >= self.throttle:
            self._paint_at(now)
        wake_at: float | None = None
        if self._dirty:
            wake_at = self._last_paint + self.throttle
        for timer in self._timers:
            wake_at = timer.next_run if wake_at is None else min(wake_at, timer.next_run)
        if wake_at is None:
            return None
        return max(0.0, wake_at - now)

    @staticmethod
    def _reschedule(timer: Timer, now: float) -> None:
        """Move ``timer`` past ``now`` according to its catch-up posture.

        The deadline advances by whole periods in both postures.  ``skip``
        gives up on the missed ones and realigns to ``now + period`` as soon
        as the next deadline is still in the past; ``coalesce`` keeps
        stepping by periods until the deadline is in the future, so the
        schedule's phase survives a late tick.
        """
        timer.next_run += timer.period
        if timer.catch_up == "skip":
            if timer.next_run <= now:
                timer.next_run = now + timer.period
        else:
            while timer.next_run <= now:
                timer.next_run += timer.period

    async def _pump(self) -> None:
        """Repaint on the throttle and run periodic callbacks until stopped."""
        while not self._stopped:
            # Clear before ticking: a refresh() that lands during tick() sets
            # the event, and the wait below then returns instead of sleeping
            # through the change (the lost-wakeup this order fixes).
            event = self._wake_up()
            event.clear()
            delay = self.tick(self.clock())
            if self._stopped:
                break
            if delay is None:
                if self._dirty:
                    continue  # never leave a dirty frame waiting forever
                await event.wait()
            else:
                try:
                    await asyncio.wait_for(event.wait(), delay)
                except asyncio.TimeoutError:
                    pass

    # -- lifecycle ------------------------------------------------------------

    def _reset_run(self) -> None:
        """Reset per-run state, keeping timers registered before the run.

        A host builds its shell before it calls ``run_session`` -- the demo
        registers its animation beat there -- so ``every`` callbacks made
        before entering survive the reset and are rescheduled from this
        run's clock.  Only cancelled timers are dropped; a timer lasts
        until its handle is cancelled, across runs.
        """
        self._stopped = False
        self._exit_event = asyncio.Event()
        now = self.clock()
        self._timers = [timer for timer in self._timers if not timer.cancelled]
        for timer in self._timers:
            timer.next_run = now + timer.period
        self._selection = None
        self._selection_pane_id = None
        self._tiling = None
        self._tiling_revision = None
        self._dirty = True

    def _enter_run(self) -> None:
        """Reset the run, attach an owned key source, enter and clear the diff base."""
        self._reset_run()
        if self.interactive and self.screen.live and self.keys is None:
            source = RawTerminalKeys(hover=self._hover)
            source.start()
            self.keys = source
            self._owned_source = source
            self._terminal.attach(source)
        if self.screen.live:
            self._terminal.enter()
        # Every run starts from a blank screen: the alternate screen starts
        # blank, and a non-live run still paints its final frame from scratch.
        self.painter.reset()

    async def _run(self, body: Callable[[], Awaitable[None]]) -> None:
        """Enter, pump, await ``body``, and tear down exactly once.

        The one lifecycle both public entries share: ``_enter_run`` resets the
        per-run state and enters the screen, the pump task starts, and
        ``body`` runs inside the bracket.  ``KeyboardInterrupt`` from the body
        is a session end (:meth:`exit`), any other ``BaseException`` is
        recorded and re-raised **after** teardown, and a pump error is
        re-raised only when the body finished cleanly -- teardown runs once,
        whatever path ended the session.
        """
        pump_task: asyncio.Task[None] | None = None
        body_error: BaseException | None = None
        try:
            try:
                self._enter_run()
                pump_task = asyncio.create_task(self._pump(), name="motui-pump")
                await body()
            except KeyboardInterrupt:
                self.exit()
            except BaseException as exc:  # noqa: BLE001 - re-raised after teardown
                body_error = exc
        finally:
            pump_error = await self._teardown(pump_task)
        if body_error is not None:
            raise body_error
        if pump_error is not None:
            raise pump_error

    async def run_session(self, body: Callable[["Runtime"], Awaitable[None]]) -> None:
        """Run ``body(self)`` inside a full-screen session.

        The body is an ordinary coroutine function -- the library never
        builds an event loop of its own, so the caller owns ``asyncio.run``
        (or any other driver).  ``enter``/``leave`` bracket the session on a
        live screen (an exception or :meth:`exit` still leaves), a non-live
        screen sees neither and stays silent for the whole run, and a
        non-live run ends by dumping the final screen as plain text -- on the
        exception path too, before the error is re-raised.  A
        ``KeyboardInterrupt`` raised by the body is treated as :meth:`exit`.

        Entering **resets the painter's diff base**: the alternate screen
        starts blank, so a host that painted before the session (the demo
        builds its shell, then runs it) would otherwise see the first frames
        diffed against rows that are no longer anywhere -- an empty screen
        until some row happens to change.
        """
        await self._run(lambda: body(self))

    async def run_async(self) -> None:
        """Run until :meth:`exit`: enter, pump, wait for the exit signal, teardown."""
        await self._run(lambda: self._exit_event.wait())

    def run(self) -> None:
        """The synchronous entry: own an event loop around :meth:`run_async`."""
        asyncio.run(self.run_async())

    async def _teardown(self, pump_task: asyncio.Task[None] | None) -> BaseException | None:
        """Stop the pump and the keyboard, bracket the screen, dump if piped.

        Returns the pump's exception, if any, so the run methods can re-raise
        it when the body itself finished cleanly.
        """
        self.exit()
        pump_error: BaseException | None = None
        if pump_task is not None:
            try:
                await pump_task
            except BaseException as exc:  # noqa: BLE001 - reported to the run method
                pump_error = exc
        # The pump's loop is history: a post-run refresh must not poke a
        # closed loop when a host detaches its last overlay after the session.
        self._wake_event = None
        self._wake_loop = None
        if self._owned_source is not None:
            self._owned_source.close()
            if self.keys is self._owned_source:
                self.keys = None  # the next run attaches a fresh source
            self._terminal.attach(None)
            self._owned_source = None
        # The final frame: painted rows before the live screen leaves, a
        # zero-write logical frame (the dump reads it) on a piped one.
        self._paint_at(self.clock())
        if self.screen.live:
            self._terminal.leave()
            self.screen.flush()
        else:
            self._dump_final_screen()
        return pump_error

    def _dump_final_screen(self) -> None:
        """Write the final screen as plain text (non-live runs only).

        A frame carries box characters the stream's codepage may not hold --
        a legacy-codepage Windows console, a pipe opened in the locale's
        encoding -- and a run that worked all the way to its last line must
        not fail on the way out.  Such a character degrades to the stream's
        own replacement instead; a host that wants the frames intact puts
        the stream in UTF-8 (the demo does).
        """
        lines = [row.text for row in self.painter.rows]
        while lines and not lines[-1].strip():
            lines.pop()  # trailing all-blank rows are not content
        if not lines:
            return
        text = "\n".join(lines) + "\n"
        try:
            self.screen.write(text)
        except UnicodeEncodeError:
            encoding = getattr(self.screen, "encoding", None) or "utf-8"
            self.screen.write(text.encode(encoding, "replace").decode(encoding))
        self.screen.flush()

    def __repr__(self) -> str:
        return (
            f"Runtime(terminal={self._terminal!r}, blocks={len(self.document)}, "
            f"interactive={self.interactive})"
        )
