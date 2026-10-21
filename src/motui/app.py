"""The TUI driver: full-screen lifecycle, document facade, pump, and dump.

:class:`TUI` ties the kernel together -- a
:class:`~motui.kernel.block.Document`, the
:class:`~motui.kernel.viewport.Viewport` over it, a
:class:`~motui.kernel.painter.Painter` and a
:class:`~motui.kernel.screen.Screen` -- and adds the runtime behaviour a
full-screen application needs:

* a **document facade** (``add``/``get``/``remove``/``system``) where every
  mutation invalidates the frame;
* **scroll facades** and the ``scroll_keys`` table -- the page keys and
  the mouse wheel intercepted into viewport scrolling in
  :meth:`TUI.read_event`, the directed moves in :meth:`TUI.scroll_up` /
  :meth:`TUI.scroll_down` / :meth:`TUI.scroll_to_bottom`, and
  :meth:`TUI.reveal`, which brings a document address on screen
  (centered, clamped at the edges) on the same focused-pane rule;
* a **mouse hit test** (:meth:`TUI.hit`) that resolves a report's
  coordinates to the block and cell under them -- routed through the
  frame's ownership table, and the host dispatches the click, never the
  driver (:meth:`TUI.hit_leaf` descends further, to the deepest
  interactive leaf the cell lands on);
* one optional **document-space selection** (:attr:`TUI.selection` /
  :meth:`TUI.set_selection`) painted by the frame's first overlay between
  layout and paint, so the highlight follows its text through scrolls
  (D1-D2) -- the range carries the pane its addresses live in
  (:attr:`TUI.selection_pane`), since block ids are numbered per document;
* the **split and focus surface** -- :meth:`TUI.split` (one code path with
  :meth:`~motui.kernel.frame.Pane.split`), the pane a press focuses
  through the replaceable :attr:`TUI.focus_policy`, and the scroll keys
  routed by pointer position or to the focused pane (D4-D5);
* one optional **dock pair** (:meth:`TUI.dock`) -- frame-level regions
  above and below the pane area, each holding its own viewport, where the
  assembly tier parks a header and a footer (D6);
* a small **protocol surface** -- :meth:`TUI.set_title` (OSC 2) and
  :meth:`TUI.set_cursor_shape` (DECSCUSR): the two host-owned window
  gestures, written through the screen; the library declares (``Input`` /
  ``Editor`` carry ``cursor_shape="beam"``), the host decides;
* a **pump** (``tick``/``clock``/``_wake_up``/``_pump``) that repaints on a
  throttle and runs cancellable periodic callbacks, with the clock as a seam
  tests can inject -- the library itself never builds an event loop, never
  sleeps, and never touches a sink outside the painter;
* :meth:`TUI.run_session` / :meth:`TUI.run_async` / :meth:`TUI.run`, which
  bracket ``enter``/``leave`` around the body (even on exceptions and
  ``exit()``), stay completely silent on a non-live screen, and dump the
  final screen as plain text when piped.

**The dispatch order**, one rule everywhere: a composition paints each
pane's chrome budget first, then that pane's content rows, then the granted
granted chrome strips over them, then the docks, then the overlay registry over everything
(:mod:`motui.kernel.frame`); a host routes an event the same way --
chrome, then overlays, then the panes' content, then its own dispatch
(:mod:`motui.interaction.overlays`).
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from .kernel.ansi import cursor_shape, set_window_title
from .kernel.block import Block, Component, Document, descend
from .kernel.chrome import Separator
from .kernel.events import Event, EventSource, KeyEvent, MouseEvent
from .kernel.frame import Frame, Pane, Rect
from .kernel.host import EveryHandle, Hit, RowRange
from .kernel.lines import Line
from .kernel.painter import Painter
from .kernel.screen import Screen, TerminalScreen
from .kernel.selection import Selection, highlight
from .kernel.style import MUTED, ColorMode
from .kernel.lines import Text
from .kernel.theme import DEFAULT_THEME, Theme
from .kernel.viewport import ScreenLayout, Viewport
from .keys import RawTerminalKeys

__all__ = ["TUI"]

#: The report names a focus policy recognises as a button press.  A wheel
#: report is ``kind="press"`` too, and a wheel notch over a pane scrolls it
#: without stealing focus.
_BUTTONS = ("left", "middle", "right")

#: The frame edges a dock may pin against.
_DOCK_EDGES = ("top", "bottom")


@dataclass
class _Every:
    """One periodic callback: period, next due time, and its handle."""

    period: float
    next_run: float
    fn: Callable[[], object]
    handle: EveryHandle


def _stdin_isatty() -> bool:
    """Whether stdin is a TTY right now (never raises)."""
    try:
        stream = sys.stdin
        return stream is not None and bool(stream.isatty())
    except Exception:
        return False


class _SelectionOverlay:
    """The driver's selection screen: overlay #1 of the frame's registry.

    Wraps the kernel's :func:`~motui.kernel.selection.highlight` in the
    overlay protocol -- the frame hands it the composed rows, it marks the
    layout of the pane the selection lives in and the marked rows are spliced
    back where that pane's came from.  The stored selection is read off the
    driver at paint time, so :meth:`TUI.set_selection` stays the one write on
    that surface and a ``None`` paints the rows exactly as they were composed.

    The pane matters more than it looks: block ids are numbered per document,
    so a split's second child holds a ``b0`` exactly as the first does, and an
    overlay that guessed a pane from the focus would mark a *neighbour's* rows
    at those colliding addresses.  :meth:`TUI.set_selection` therefore records
    the pane alongside the range, and a pane the frame no longer holds paints
    nothing -- its document went with it (D8's vanished addresses).
    """

    def __init__(self, tui: TUI) -> None:
        self._tui = tui

    def paint(self, frame: Frame) -> ScreenLayout:
        selection = self._tui._selection
        if selection is None:
            return frame.layout
        pane_id = self._tui._selection_pane_id
        if pane_id is None or frame.pane(pane_id) is None:
            return frame.layout
        marked = highlight(
            frame.pane_layout(pane_id), selection, style=self._tui.theme.selection
        )
        return frame.with_pane_rows(pane_id, marked.rows)


def _press_focuses_a_pane(tui: "TUI", event: Event) -> Pane | None:
    """The default focus policy: a button press focuses the pane under it.

    The policy the driver runs on every event :meth:`TUI.read_event` hands
    back, before the host's own dispatch: a button press (never a wheel
    notch, never a key) resolves its 0-based report through the frame's
    ownership table and focuses the pane it lands in -- the mouse side of
    D4.  A host wanting different behavior assigns its own callable to
    :attr:`TUI.focus_policy`, with the same ``(tui, event) -> Pane | None``
    signature; the return is the pane it focused, or ``None``.
    """
    if not isinstance(event, MouseEvent) or event.kind != "press":
        return None
    if event.button not in _BUTTONS:
        return None
    pane = tui.pane_at(event.x, event.y)
    if pane is None or tui.frame.is_dock(pane):
        return None
    focused = tui.frame.focused_pane
    if focused is None or focused.id != pane.id:
        tui.frame.focus(pane)
        tui.refresh()
    return pane


def _body_address(viewport: Viewport, block: Block, row: int, width: int) -> int:
    """The body-row index of ``(block, row)`` in the viewport's document.

    The document order walks the blocks and sums what the unpinned ones
    occupy before ``block`` -- each measured at ``width``, the width the
    pane was last laid out at, exactly as the viewport counts its own body
    (fixed-region rows are not body rows) -- and ``row`` lands on that
    prefix, clamped into the block's own rendered rows (an empty block
    answers its first row).  The counts come from each block's own cache
    (:meth:`~motui.kernel.block.Block.rows`): the layout just filled it, so
    the walk reads rows instead of re-wrapping them, and a block whose
    content moved carries a moved revision, so no count is stale.  The half
    of :meth:`TUI.reveal` that is pure arithmetic over the document; the
    caller has already resolved the block out of the document, so the walk
    is total.
    """
    address = 0
    for held in viewport.document.blocks():
        if held is block:
            break
        if held.pin is None:
            address += len(held.rows(width))
    count = len(block.rows(width))
    row = max(0, min(row, count - 1)) if count else 0
    return address + row


class TUI:
    """A full-screen application driver.

    ``screen`` defaults to a :class:`~motui.kernel.screen.TerminalScreen`
    (pass ``mouse=False`` to leave mouse tracking off), ``keys`` to no
    source at all (``read_event`` then returns ``None``).
    :attr:`scroll_keys` is the public table :meth:`read_event` intercepts
    on -- event name to signed row count, negative scrolling up -- copied
    from ``_DEFAULT_SCROLL_KEYS`` into each instance; a host may rebind a
    count or ``del`` an entry to hand that event back (``del
    tui.scroll_keys["wheel_up"]``).  ``mouse`` and ``hover`` apply only to
    the default screen and the :class:`RawTerminalKeys` source
    :meth:`run` attaches: a custom ``screen`` brings its own tracking
    settings (a host driving hover passes ``HeadlessScreen(hover=True)`` /
    ``TerminalScreen(hover=True)`` itself -- the default screen is built
    with the switches here, ``hover`` opening DECSET 1003 for a
    :class:`~motui.interaction.pointer.Pointer`), and the attached source's
    Windows console-record path opens its button-free motion under the same
    switch (its 1003 counterpart; an explicit ``keys=`` source is the
    caller's own contract).
    ``focus_events`` (off by default) adds DECSET 1004 to the default
    screen's enter/leave bracket, so a live session is told when its window
    gains or loses focus and the decoder reports it as a
    :class:`~motui.kernel.events.FocusEvent`; the reports are the **host's**
    to interpret -- the
    :class:`~motui.interaction.pointer.Pointer` tier still watches mouse reports
    only, and scrubbing a hover or pausing an animation on a lost focus is
    the host's own loop.
    ``sync`` (the default) hands the painter the synchronized-update bracket
    (DECSET 2026): every non-empty frame leaves as one write wrapped in the
    pair, so a terminal that knows the mode swaps the frame in whole and one
    that does not ignores the bytes; an unchanged frame still writes zero
    bytes, switch or no switch.
    ``color_mode`` is forwarded to the default screen only when set: left
    ``None`` the screen's own ``"auto"`` stands (the environment probe --
    ``NO_COLOR``/``TERM=dumb`` mean no color, ``COLORTERM`` truecolor and a
    ``256color`` ``TERM`` pick their modes, anything else stays truecolor),
    and an explicit :data:`~motui.kernel.style.ColorMode` overrides the
    probe.  The painter reads the mode off the screen and renders its rows
    for that capability.
    ``theme`` is the driver's own theme (default
    :data:`~motui.kernel.theme.DEFAULT_THEME`), read by the chrome the
    driver composes -- the split's divider
    (:class:`~motui.kernel.chrome.Separator`); widgets are never themed
    from here, they each take ``theme=`` themselves.
    ``interactive`` overrides the derived value; when left ``None`` it is
    ``screen.live and sys.stdin.isatty()``.  An interactive live session
    without an explicit key source gets a :class:`RawTerminalKeys` attached
    (and closed) by :meth:`run`; an explicit ``keys=`` source is always used
    as given.

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

    #: What :meth:`read_event` scrolls on: event name to signed row count
    #: (negative scrolls up).  Each instance copies it into its public
    #: ``scroll_keys`` attribute, which hosts may edit.
    _DEFAULT_SCROLL_KEYS = {
        "page_up": -1,
        "page_down": 1,
        "wheel_up": -3,
        "wheel_down": 3,
    }

    def __init__(
        self,
        *,
        screen: Screen | None = None,
        keys: EventSource | None = None,
        throttle: float = 0.030,
        interactive: bool | None = None,
        mouse: bool = True,
        hover: bool = False,
        focus_events: bool = False,
        sync: bool = True,
        color_mode: ColorMode | None = None,
        focus_policy: Callable[
            ["TUI", Event], Pane | None
        ] = _press_focuses_a_pane,
        theme: Theme | None = None,
    ) -> None:
        if screen is not None:
            self._screen = screen
        else:
            # A switch left at its default is not forwarded: the screen's own
            # default (color_mode="auto" -> the env probe) is the contract.
            extra = {} if color_mode is None else {"color_mode": color_mode}
            self._screen = TerminalScreen(
                mouse=mouse,
                hover=hover,
                focus_events=focus_events,
                **extra,
            )
        #: The hover switch :meth:`run` hands the default key source: it
        #: gates the record path's button-free motion (see the class
        #: docstring).  An explicit ``keys=`` source is used as given.
        self._hover = hover
        self._document = Document()
        self._viewport = Viewport(self._document)
        #: The theme the driver's own chrome reads (the split's divider);
        #: widgets take their own ``theme=`` and are never themed from here.
        self.theme = DEFAULT_THEME if theme is None else theme
        # The initial tiling: one pane, the primary, its whole rectangle the
        # screen -- held by the frame every composition routes through.  The
        # rectangle is a placeholder until the first paint retiles it to the
        # live screen; the selection highlight rides the frame as overlay #1.
        self._frame = Frame([Pane("primary", Rect(0, 0, 0, 0), self._viewport)])
        self._frame.add_overlay(_SelectionOverlay(self), layer="selection")
        # Structural frame changes (split/close/chrome/dock/overlay) mark the
        # driver dirty by themselves: a host never follows them with refresh().
        self._frame.on_change = self.refresh
        self.painter = Painter(self._screen, sync=sync)
        self.keys = keys
        self.throttle = throttle
        self.scroll_keys = dict(self._DEFAULT_SCROLL_KEYS)
        #: Which pane an event focuses.  The driver
        #: runs it on every event :meth:`read_event` hands back (before the
        #: host's dispatch), with the ``(tui, event) -> Pane | None``
        #: signature of :func:`_press_focuses_a_pane`; swapping it is a host's
        #: one-line replacement (D4: the policy is replaceable, the
        #: mechanism is not), and a run that moved the focus marks the frame
        #: dirty.
        self.focus_policy = focus_policy
        self.interactive = bool(
            self.screen.live and _stdin_isatty() if interactive is None else interactive
        )
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
        self._every: list[_Every] = []
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

    # -- the Host factories -------------------------------------------------------

    def copy_to_clipboard(self, text: str) -> bool:
        """Put ``text`` on the terminal's clipboard through the screen (OSC 52).

        The driver's half of the :class:`~motui.kernel.host.Host` clipboard
        seam: a non-live screen answers ``False`` without touching the
        stream, exactly as :meth:`Screen.copy_to_clipboard
        <motui.kernel.screen.Screen.copy_to_clipboard>` does.
        """
        return self._screen.copy_to_clipboard(text)

    def make_input(self, **kwargs: object) -> object:
        """Build the interaction tier's own query row (an ``Input``).

        The composition root keeps the one ``widgets`` import; a tier that
        needs a field receives it through the :class:`Host
        <motui.kernel.host.Host>` seam instead of importing the widget layer
        itself.  The returned object is a ``widgets.textfield.Input``; the
        narrow protocol types it as ``object``.
        """
        from .widgets.textfield import Input

        return Input(**kwargs)

    def make_autocomplete(
        self, options: Sequence[object], **kwargs: object
    ) -> object:
        """Build the interaction tier's filtered list (an ``Autocomplete``).

        The same composition-root rule as :meth:`make_input`; the returned
        object is a ``widgets.autocomplete.Autocomplete``.
        """
        from .widgets.autocomplete import Autocomplete

        return Autocomplete(options, **kwargs)

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

    def _target_pane(self, pane: Pane | str | None) -> Pane:
        """Resolve an explicit pane, or the focused one when none is named."""
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
        pin: str | None = None,
        pane: Pane | str | None = None,
    ) -> Block:
        """Append a block to a pane's document and refresh the frame.

        ``pane`` scopes the operation: an explicit pane (or pane id) wins,
        and with none named the focused pane is the target.  ``pin``
        forwards to :meth:`~motui.kernel.block.Document.add`: ``"top"``/
        ``"bottom"`` place the block in the matching fixed region, ``None``
        leaves it in the scrollable body.  Block ids are unique across the
        whole frame: an automatic id is the first free ``bN`` over every
        pane's document, and an explicit id another pane already holds
        raises ``ValueError``.
        """
        target = self._target_pane(pane)
        if id is None:
            id = self._next_block_id()
        elif self._panes_holding(id):
            raise ValueError(f"duplicate block id: {id!r}")
        block = target.viewport.document.add(component, id=id, pin=pin)
        self.refresh()
        return block

    def get(self, id: str) -> Block:
        """The block with ``id`` from any pane's document (``KeyError`` when missing).

        The search spans every content pane and dock.  An id two panes hold
        is not silently resolved to the first: it raises ``ValueError`` and
        names the panes, because frame-wide uniqueness is the contract.
        """
        holders = self._panes_holding(id)
        if not holders:
            raise KeyError(f"no block with id {id!r}")
        if len(holders) > 1:
            raise ValueError(
                f"block id {id!r} is held by multiple panes: "
                f"{[pane.id for pane in holders]}"
            )
        return holders[0].viewport.document.get(id)

    def remove(self, id: str) -> Block:
        """Detach the block with ``id`` from the pane that holds it.

        The same frame-wide resolution :meth:`get` performs; an ambiguous id
        raises ``ValueError`` listing the panes instead of picking one.
        """
        holders = self._panes_holding(id)
        if not holders:
            raise KeyError(f"no block with id {id!r}")
        if len(holders) > 1:
            raise ValueError(
                f"block id {id!r} is held by multiple panes: "
                f"{[pane.id for pane in holders]}"
            )
        block = holders[0].viewport.document.remove(id)
        self.refresh()
        return block

    def system(self, text: str) -> Block:
        """Append a system block: external output becomes document content.

        The text is added as a muted :class:`~motui.kernel.text.Text`
        block, so a full-screen application never writes to stdout behind the
        painter's back.
        """
        return self.add(Text(text, style=MUTED))

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
        viewport moved is the focused pane's, the same one the scroll
        facades move (:meth:`scroll_up` and friends carry the rule), and a
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
        viewport = self._focused_viewport()
        try:
            block = viewport.document.get(bid)
        except KeyError:
            return False  # an unknown address reveals nothing
        if block.pin is not None:
            return True  # a fixed-region block is always on screen (D3's pin)
        pane = self._frame.focused_pane
        layout = None if pane is None else self._frame.pane_layout(pane.id)
        placement = None if pane is None else self._frame.region(pane.id)
        if layout is None or placement is None or not layout.body_rows:
            return False  # no composition has run, or no window to show it in
        count = len(block.rows(placement.width))
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
        orientation: str,
        *,
        ratios: tuple[float, ...] = (1, 1),
        min_size: int = 1,
        separator: bool = True,
        pane: Pane | str | None = None,
    ) -> tuple[Pane, ...]:
        """Split a pane; return the panes it became, in paint order.

        ``pane`` names the target: an explicit pane (or id) wins, and with
        none named the focused pane splits.  ``"vertical"`` tiles side by
        side (a vertical divider between them), ``"horizontal"`` stacks them
        (a horizontal divider); ``ratios`` are the children's weights --
        ``(2, 1)`` gives the first twice the cells of the second, ``(1, 1)``
        halves it -- and ``min_size`` the floor each child is raised to.  Two
        ratios give the ``(left, right)`` or ``(top, bottom)`` pair; more give
        one pane per ratio.  The same code path
        :meth:`~motui.kernel.frame.Pane.split` runs, so a pane splits itself
        identically.

        The first child keeps the split pane's document, so the transcript
        stays put; every child after it opens over a fresh, empty document
        -- ``right.document.add(markdown)`` is the preview side of a
        transcript | preview split.  A split leaves focus where it was (the
        first child) and re-divides the tiling immediately, so the returned
        panes already hold their rectangles.

        ``separator=True`` divides the panes with a 1-cell inter-pane
        divider (:class:`~motui.kernel.chrome.Separator`): the tmux
        convention, drawn in the driver's :attr:`theme` -- ``accent``
        beside the focused pane and ``border`` otherwise -- and registered
        as chrome on the pane before each gap so it is budgeted rather than
        overlapping content.  ``False`` leaves the panes abutting, no
        divider and no cell spent on one.
        """
        target = self._target_pane(pane)
        children = target.split(orientation, ratios=ratios, min_size=min_size)
        if separator:
            edge = "right" if orientation == "vertical" else "bottom"
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
        viewport: Viewport,
        *,
        edge: str = "bottom",
        size: int | None = None,
    ) -> Pane:
        """Pin ``viewport`` against ``edge`` (``"top"``/``"bottom"``); return its pane.

        A dock is a frame-level region outside the pane area, holding its own
        viewport: its rows span the full frame width, join the ownership
        table (a footer block under the pointer resolves through :meth:`hit`
        exactly as a pane's rows do), but it takes neither focus nor splits,
        and a wheel over it scrolls the focused pane instead.  ``size=None``
        derives the height from the content
        (:meth:`~motui.kernel.viewport.Viewport.natural_height`); an
        explicit size is used as given, clamped to the screen.  An empty
        dock claims no rows and paints nothing.  One dock per edge; a second
        :meth:`dock` on the same edge raises ``RuntimeError``.
        """
        if edge not in _DOCK_EDGES:
            raise ValueError(f"dock edge must be one of {_DOCK_EDGES}, got {edge!r}")
        if self._frame.dock(edge) is not None:
            raise RuntimeError(f"the frame already holds a {edge} dock")
        dock = Pane(self._frame.next_pane_id(), Rect(0, 0, 0, 0), viewport)
        self._dock_sizes[edge] = size
        self._frame.set_dock(edge, dock)
        self._retile()
        self.refresh()
        return dock

    def undock(self, edge: str = "bottom") -> Pane | None:
        """Release the dock on ``edge``; return its pane (``None`` when empty)."""
        pane = self._frame.dock(edge)
        if pane is None:
            return None
        self._frame.set_dock(edge, None)
        self._dock_sizes[edge] = None
        self._retile()
        self.refresh()
        return pane

    def dock_region(self, edge: str = "bottom") -> Rect | None:
        """The rectangle the last composition laid the dock on ``edge`` in."""
        pane = self._frame.dock(edge)
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
        :meth:`~motui.kernel.viewport.Viewport.natural_height`, read off the
        document it shows).  A zero-height dock is released (an empty
        rectangle), so it paints nothing and owns no row: no ghost line.
        """
        width, height = self.screen.width, self.screen.height
        top_h = self._dock_height("top", width, height)
        bottom_h = min(
            self._dock_height("bottom", width, height), max(0, height - top_h)
        )
        top = Rect(0, 0, width, top_h) if top_h > 0 else None
        bottom = (
            Rect(0, height - bottom_h, width, bottom_h) if bottom_h > 0 else None
        )
        pane_rect = Rect(0, top_h, width, max(0, height - top_h - bottom_h))
        tiling = (pane_rect, top, bottom)
        if self._tiling == tiling and self._tiling_revision == self._frame.revision:
            return
        self._tiling = tiling
        self._tiling_revision = self._frame.revision
        self._frame.retile(pane_rect, docks={"top": top, "bottom": bottom})

    def _scroll_viewport(self, event: Event) -> Viewport:
        """The viewport a scroll-key event moves (D5).

        A wheel report scrolls the pane under the pointer -- resolved
        through the frame's ownership table, chrome columns and all -- and
        falls back to the focused pane when the report names no pane.  The
        dock holds no scroll state of its own, so a wheel over the footer
        scrolls the focused pane too.  A key (``page_up``/``page_down``)
        carries no pointer at all and always scrolls the focused pane --
        which, on a one-pane frame, is the same viewport either way.
        """
        if isinstance(event, MouseEvent):
            pane = self.pane_at(event.x, event.y)
            if pane is not None and not self._frame.is_dock(pane):
                return pane.viewport
        return self._focused_viewport()

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

    def every(self, seconds: float, fn: Callable[[], object]) -> EveryHandle:
        """Call ``fn`` every ``seconds`` until the returned handle is cancelled.

        ``fn`` takes no arguments and decides for itself whether to
        invalidate the frame; the pump invokes it from :meth:`tick`.
        """
        handle = EveryHandle()
        self._every.append(
            _Every(period=seconds, next_run=self.clock() + seconds, fn=fn, handle=handle)
        )
        self._wake()
        return handle

    async def read_event(self) -> Event | None:
        """Read the next event, with the scroll keys bound to scrolling.

        A :class:`~motui.kernel.events.KeyEvent` whose ``key``, or a
        :class:`~motui.kernel.events.MouseEvent` wheel report whose
        ``button``, is in :attr:`scroll_keys` (by default
        ``page_up``/``page_down``/``wheel_up``/``wheel_down``) is
        intercepted: it scrolls a viewport by the table's row count --
        negative up -- and the read continues, so the caller never sees it.
        The viewport is the one D5 names: a wheel report scrolls the pane
        under the pointer (falling back to the focused pane when it names
        none), a page key the focused pane.  Every other event is returned
        untouched -- a :class:`~motui.kernel.events.MouseEvent` whose
        binding was deleted included, after :attr:`focus_policy` has run on
        it, and a policy run that moved the focus marks the frame dirty so
        the next frame repaints.  The result is ``None`` when there is no
        key source, when the source reports EOF, and -- per the toolkit's
        non-live contract -- always on a non-live screen, even when a
        source is attached.

        Escape hatch: ``await tui.keys.read()`` reads the raw source
        directly, bypassing both the scroll-key interception and the
        non-live guard.  A pending read returns ``None`` immediately when
        :meth:`exit` runs: the read task is cancelled and the source itself
        is closed by teardown.
        """
        if not self.screen.live:
            return None
        source = self.keys
        if source is None:
            return None
        exit_event = self._exit_event
        if exit_event is None:
            self._exit_event = exit_event = asyncio.Event()
        while True:
            if self._stopped or exit_event.is_set():
                return None
            read_task = asyncio.ensure_future(source.read())
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
            event = read_task.result()
            if event is None:
                return None
            if isinstance(event, KeyEvent):
                rows = self.scroll_keys.get(event.key)
            elif isinstance(event, MouseEvent) and event.kind == "wheel":
                rows = self.scroll_keys.get(event.button)
            else:
                rows = None
            if rows is not None:
                viewport = self._scroll_viewport(event)
                if rows < 0:
                    viewport.scroll_up(-rows)
                else:
                    viewport.scroll_down(rows)
                self.refresh()
                continue
            focused = self._frame.focused_pane
            self.focus_policy(self, event)
            if self._frame.focused_pane is not focused:
                self.refresh()  # the policy moved the focus: repaint
            return event

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
        coordinates and the deepest leaf the cell descends to
        (:func:`~motui.kernel.block.descend`).  The driver never dispatches
        clicks itself: the host reads the
        :class:`~motui.kernel.events.MouseEvent` from :meth:`read_event`
        (button presses are not in :attr:`scroll_keys`), resolves it here,
        and calls the leaf itself::

            event = await tui.read_event()
            if isinstance(event, MouseEvent):
                hit = tui.hit(event.x, event.y)
                if hit is not None and hit.leaf is not None:
                    hit.leaf.click(hit.leaf_row, hit.leaf_col)

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
        leaf, leaf_row, leaf_col = descend(block.component, row, col)
        return Hit(pane, block, row, col, leaf, leaf_row, leaf_col)

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

        Timestamps (``every`` schedules, toast expiries, double-click
        windows) read it, and a host or a test replaces the method with its
        own reading to drive time.
        """
        return time.monotonic()

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
        :meth:`~motui.kernel.painter.Painter.paint` samples again for
        its full-repaint test, per the :class:`~motui.kernel.screen.Screen`
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
        self.painter.paint(layout)
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

        The pump's manual seam: due ``every`` callbacks run first (they may
        invalidate the frame), then at most one frame is painted -- only
        when the document is dirty *and* the throttle has elapsed since the
        last flush.  The return value is the delay until the pump next needs
        to run, or ``None`` when nothing is pending and the pump should
        sleep until woken.
        """
        if self._every:
            alive: list[_Every] = []
            for entry in self._every:
                if entry.handle.cancelled:
                    continue
                if entry.next_run <= now:
                    entry.fn()
                    if entry.handle.cancelled:
                        continue
                    entry.next_run = now + entry.period
                alive.append(entry)
            self._every = alive
        if self._dirty and now - self._last_paint >= self.throttle:
            self._paint_at(now)
        wake_at: float | None = None
        if self._dirty:
            wake_at = self._last_paint + self.throttle
        for entry in self._every:
            wake_at = entry.next_run if wake_at is None else min(wake_at, entry.next_run)
        if wake_at is None:
            return None
        return max(0.0, wake_at - now)

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
        """Reset every per-run state: timers, selection, tiling and lifecycle."""
        self._stopped = False
        self._exit_event = asyncio.Event()
        self._every = []
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
        if self.screen.live:
            self.screen.enter()
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

    async def run_session(self, body: Callable[["TUI"], Awaitable[None]]) -> None:
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
            self._owned_source = None
        # The final frame: painted rows before the live screen leaves, a
        # zero-write logical frame (the dump reads it) on a piped one.
        self._paint_at(self.clock())
        if self.screen.live:
            self.screen.leave()
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
            f"TUI(screen={self.screen!r}, blocks={len(self.document)}, "
            f"interactive={self.interactive})"
        )
