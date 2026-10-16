"""The TUI driver: full-screen lifecycle, document facade, pump, and dump.

:class:`TUI` ties the kernel together -- a
:class:`~mocode_tui.core.block.Document`, the
:class:`~mocode_tui.core.viewport.Viewport` over it, a
:class:`~mocode_tui.core.painter.Painter` and a
:class:`~mocode_tui.core.screen.Screen` -- and adds the runtime behaviour a
full-screen application needs:

* a **document facade** (``add``/``get``/``remove``/``system``) where every
  mutation invalidates the frame;
* **scroll facades** and the ``scroll_keys`` table -- the page keys and
  the mouse wheel intercepted into viewport scrolling in
  :meth:`TUI.read_key`;
* a **mouse hit test** (:meth:`TUI.hit_test`) that resolves a report's
  coordinates to the block and cell under them -- routed through the
  frame's ownership table, and the host dispatches the click, never the
  driver (:meth:`TUI.hit_component` descends further, to the deepest
  interactive leaf the cell lands on);
* one optional **document-space selection** (:attr:`TUI.selection` /
  :meth:`TUI.set_selection`) painted by the frame's first overlay between
  layout and paint, so the highlight follows its text through scrolls
  (D1-D2) -- the range carries the pane its addresses live in
  (:attr:`TUI.selection_pane`), since block ids are numbered per document;
* the **split and focus surface** -- :meth:`TUI.split` (one code path with
  :meth:`~mocode_tui.core.frame.Pane.split`), the pane a press focuses
  through the replaceable :attr:`TUI.focus_policy`, and the scroll keys
  routed by pointer position or to the focused pane (D4-D5);
* one optional **bottom band** (:meth:`TUI.add_band`) -- a frame-level
  region beneath the pane area, holding its own viewport, where the
  assembly tier parks a footer (D6);
* a **pump** (``tick``/``clock``/``_wake_up``/``_pump``) that repaints on a
  throttle and runs cancellable periodic callbacks, with the clock as a seam
  tests can inject -- the library itself never builds an event loop, never
  sleeps, and never touches a sink outside the painter;
* :meth:`TUI.run`, which brackets ``enter``/``leave`` around the body (even
  on exceptions and ``stop()``), stays completely silent on a non-live
  screen, and dumps the final screen as plain text when piped.

**The dispatch order**, one rule everywhere: a composition paints each
pane's chrome budget first, then that pane's content rows, then the granted
bands over them, then the band, then the overlay registry over everything
(:mod:`mocode_tui.core.frame`); a host routes an event the same way --
chrome, then overlays, then the panes' content, then its own dispatch
(:mod:`mocode_tui.chrome`).
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from .core.block import Block, Component, Document, descend
from .core.events import Key, KeySource, MouseEvent, Paste
from .core.frame import Frame, Pane, Rect
from .core.lines import Line
from .core.painter import Painter
from .core.screen import Screen, TerminalScreen
from .core.selection import Selection, highlight
from .core.style import MUTED
from .core.lines import Text
from .core.theme import DEFAULT_THEME, Theme
from .core.viewport import ScreenLayout, Viewport
from .keys import RawTerminalKeys

__all__ = ["EveryHandle", "Hit", "TUI"]

#: The report names a focus policy recognises as a button press.  A wheel
#: report is ``kind="press"`` too, and a wheel notch over a pane scrolls it
#: without stealing focus.
_BUTTONS = ("left", "middle", "right")


class EveryHandle:
    """Cancellable handle returned by :meth:`TUI.every`."""

    __slots__ = ("_cancelled",)

    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def cancel(self) -> None:
        """Stop future invocations (a callback already running finishes)."""
        self._cancelled = True

    def __repr__(self) -> str:
        return f"EveryHandle(cancelled={self._cancelled})"


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


@dataclass(frozen=True)
class Hit:
    """One hit-test result: the block under the cell, and the cell in it.

    ``row``/``col`` are 0-based *within the block's own rows*; ``col`` is the
    screen column mapped into ``[0, width-1]``.  ``pane_id`` names the pane
    the cell belongs to -- the frame's own name for it.  It is what lets a
    drag stay in one document: block ids are numbered per document, so a
    split's second child holds a ``b0`` exactly as the first does, and the
    pane rather than the id is the document an address lives in.
    """

    block: Block
    row: int
    col: int
    pane_id: str


class _SelectionOverlay:
    """The driver's selection screen: overlay #1 of the frame's registry.

    Wraps the kernel's :func:`~mocode_tui.core.selection.highlight` in the
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
        marked = highlight(frame.pane_layout(pane_id), selection)
        return frame.with_pane_rows(pane_id, marked.rows)


def _press_focuses_a_pane(tui: "TUI", event: Key | Paste) -> Pane | None:
    """The default focus policy: a button press focuses the pane under it.

    The policy the driver runs on every event :meth:`TUI.read_key` hands
    back, before the host's own dispatch: a button press (never a wheel
    notch, never a key) resolves its 0-based report through the frame's
    ownership table and focuses the pane it lands in -- the mouse side of
    D4.  A host wanting different behavior assigns its own callable to
    :attr:`TUI.focus_policy`, with the same ``(tui, event) -> Pane | None``
    signature; the return is the pane it focused, or ``None``.
    """
    if not isinstance(event, MouseEvent) or event.kind != "press":
        return None
    if event.name not in _BUTTONS:
        return None
    return tui.focus_at(event.x, event.y)


class TUI:
    """A full-screen application driver.

    ``screen`` defaults to a :class:`~mocode_tui.core.screen.TerminalScreen`
    (pass ``mouse=False`` to leave mouse tracking off), ``keys`` to no
    source at all (``read_key`` then returns ``None``).
    :attr:`scroll_keys` is the public table :meth:`read_key` intercepts
    on -- event name to signed row count, negative scrolling up -- copied
    from ``_DEFAULT_SCROLL_KEYS`` into each instance; a host may rebind a
    count or ``del`` an entry to hand that event back (``del
    tui.scroll_keys["wheel_up"]``).  ``mouse`` and ``hover`` apply only to
    the default screen and the :class:`RawTerminalKeys` source
    :meth:`run` attaches: a custom ``screen`` brings its own tracking
    settings (a host driving hover passes ``HeadlessScreen(hover=True)`` /
    ``TerminalScreen(hover=True)`` itself -- the default screen is built
    with the switches here, ``hover`` opening DECSET 1003 for a
    :class:`~mocode_tui.pointer.Pointer`), and the attached source's
    Windows console-record path opens its button-free motion under the same
    switch (its 1003 counterpart; an explicit ``keys=`` source is the
    caller's own contract).
    ``sync`` (the default) hands the painter the synchronized-update bracket
    (DECSET 2026): every non-empty frame leaves as one write wrapped in the
    pair, so a terminal that knows the mode swaps the frame in whole and one
    that does not ignores the bytes; an unchanged frame still writes zero
    bytes, switch or no switch.
    ``theme`` is the driver's own theme (default
    :data:`~mocode_tui.core.theme.DEFAULT_THEME`), read by the chrome the
    driver composes -- the split's divider
    (:class:`~mocode_tui.chrome._Separator`); widgets are never themed
    from here, they each take ``theme=`` themselves.
    ``interactive`` overrides the derived value; when left ``None`` it is
    ``screen.live and sys.stdin.isatty()``.  An interactive live session
    without an explicit key source gets a :class:`RawTerminalKeys` attached
    (and closed) by :meth:`run`; an explicit ``keys=`` source is always used
    as given.

    Internally the driver holds one
    :class:`~mocode_tui.core.frame.Frame` whose primary pane is
    :attr:`document` / :attr:`viewport`: every frame composes through it
    (a single-pane frame composes to its pane's own layout), :meth:`hit_test`
    routes through its ownership table, the scroll facades move its
    focused pane's viewport, and the selection highlight is the frame's
    first overlay.  :meth:`split` divides a pane of that tiling in place --
    the frame keeps its identity, its overlays and its focus across the
    division, and every pane keeps its viewport, its chrome and its scroll
    state -- so a split adds panes without any new plumbing, and a resize
    re-divides the same tree instead of rebuilding panes.
    """

    #: What :meth:`read_key` scrolls on: event name to signed row count
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
        keys: KeySource | None = None,
        throttle: float = 0.030,
        interactive: bool | None = None,
        mouse: bool = True,
        hover: bool = False,
        sync: bool = True,
        focus_policy: Callable[
            ["TUI", Key | Paste], Pane | None
        ] = _press_focuses_a_pane,
        theme: Theme | None = None,
    ) -> None:
        self.screen = (
            screen if screen is not None else TerminalScreen(mouse=mouse, hover=hover)
        )
        #: The hover switch :meth:`run` hands the default key source: it
        #: gates the record path's button-free motion (see the class
        #: docstring).  An explicit ``keys=`` source is used as given.
        self._hover = hover
        self.document = Document()
        self.viewport = Viewport(self.document)
        #: The theme the driver's own chrome reads (the split's divider);
        #: widgets take their own ``theme=`` and are never themed from here.
        self.theme = DEFAULT_THEME if theme is None else theme
        # The initial tiling: one pane, the primary, its whole rectangle the
        # screen -- held by the frame every composition routes through.  The
        # rectangle is a placeholder until the first paint retiles it to the
        # live screen; the selection highlight rides the frame as overlay #1.
        self._frame = Frame([Pane("primary", Rect(0, 0, 0, 0), self.viewport)])
        self._frame.add_overlay(_SelectionOverlay(self))
        self.painter = Painter(self.screen, sync=sync)
        self.keys = keys
        self.throttle = throttle
        self.scroll_keys = dict(self._DEFAULT_SCROLL_KEYS)
        #: Which pane an event focuses.  The driver
        #: runs it on every event :meth:`read_key` hands back (before the
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
        self._owns_keys = False
        #: The rectangles the last retile laid out (pane area, band) and the
        #: frame revision it ran at, so a same-size paint with an unchanged
        #: tree retiles nothing.
        self._tiling: tuple[Rect, Rect | None] | None = None
        self._tiling_revision: int | None = None

    # -- document facade ------------------------------------------------------

    def add(
        self,
        component: Component,
        *,
        id: str | None = None,
        pin: str | None = None,
    ) -> Block:
        """Append a block and invalidate the frame.

        ``pin`` forwards to :meth:`~mocode_tui.core.block.Document.add`:
        ``"top"``/``"bottom"`` place the block in the matching fixed
        region, ``None`` (the default) leaves it in the scrollable body.
        """
        block = self.document.add(component, id=id, pin=pin)
        self.invalidate()
        return block

    def _documents(self) -> tuple[Document, ...]:
        """The documents the frame holds blocks in: the primary, then the band."""
        band = self._frame.band
        if band is None:
            return (self.document,)
        return (self.document, band.viewport.document)

    def _document_holding(self, id: str) -> Document:
        """The document that holds the block ``id`` (``KeyError`` when none does).

        The one resolution :meth:`get` and :meth:`remove` share: the primary
        document first, then the frame's band.
        """
        for document in self._documents():
            try:
                document.get(id)
            except KeyError:
                continue
            return document
        raise KeyError(f"no block with id {id!r}")

    def get(self, id: str) -> Block:
        """The block with ``id`` (KeyError when missing).

        Resolved in the primary document first, then in the frame's band
        (the footer an assembly-tier controller parks there), so a host
        keeps addressing a footer block by its id.
        """
        return self._document_holding(id).get(id)

    def remove(self, id: str) -> Block:
        """Detach the block with ``id`` and invalidate the frame.

        The same resolution :meth:`get` performs -- the primary document
        first, then the band -- so a footer block a host detaches leaves the
        frame it was painted in.
        """
        block = self._document_holding(id).remove(id)
        self.invalidate()
        return block

    def system(self, text: str) -> Block:
        """Append a system block: external output becomes document content.

        The text is added as a muted :class:`~mocode_tui.core.text.Text`
        block, so a full-screen application never writes to stdout behind the
        painter's back.
        """
        return self.add(Text(text, style=MUTED))

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
        self.invalidate()

    def scroll_down(self, n: int = 1) -> None:
        """Scroll the viewport ``n`` rows toward the bottom."""
        self._focused_viewport().scroll_down(n)
        self.invalidate()

    def scroll_to_bottom(self) -> None:
        """Re-attach the viewport to the bottom of the document."""
        self._focused_viewport().scroll_to_bottom()
        self.invalidate()

    # -- the split and focus surface ----------------------------------------------

    @property
    def frame(self) -> Frame:
        """The driver's frame: its tiling, its band, its overlays, its focus.

        The public seam the assembly tier reads -- a scrollbar resolves its
        pane's rectangle and layout through it, a toast its corner, and the
        gesture tier the pane a drag lives in.
        """
        return self._frame

    @property
    def band(self) -> Pane | None:
        """The frame's bottom band pane, or ``None`` when none is attached."""
        return self._frame.band

    def split(
        self,
        orientation: str,
        *,
        ratios: tuple[float, ...] = (1, 1),
        min_size: int = 1,
        separator: bool = True,
    ) -> tuple[Pane, ...]:
        """Split the focused pane; return the panes it became, in paint order.

        ``"vertical"`` tiles side by side (a vertical divider between them),
        ``"horizontal"`` stacks them (a horizontal divider); ``ratios`` are
        the children's weights -- ``(2, 1)`` gives the first twice the cells
        of the second, ``(1, 1)`` halves it -- and ``min_size`` the floor
        each child is raised to.  Two ratios give the ``(left, right)`` or
        ``(top, bottom)`` pair; more give one pane per ratio.  The same code
        path :meth:`~mocode_tui.core.frame.Pane.split` runs, so a pane
        splits itself identically.

        The first child keeps the split pane's document, so the transcript
        stays put; every child after it opens over a fresh, empty document
        -- ``right.document.add(markdown)`` is the preview side of a
        transcript | preview split.  A split leaves focus where it was (the
        first child) and re-divides the tiling immediately, so the returned
        panes already hold their rectangles.

        ``separator=True`` divides the panes with a 1-cell inter-pane
        divider (:class:`~mocode_tui.chrome._Separator`): the tmux
        convention, drawn in the driver's :attr:`theme` -- ``accent``
        beside the focused pane and ``border`` otherwise -- and registered
        as chrome on the pane before each gap so it is budgeted rather than
        overlapping content.  ``False`` leaves the panes abutting, no
        divider and no cell spent on one.
        """
        pane = self._frame.focused_pane
        if pane is None:
            raise RuntimeError("the frame holds no pane to split")
        children = pane.split(orientation, ratios=ratios, min_size=min_size)
        if separator:
            # chrome.py is the assembly tier over this module (it imports
            # the driver), so the divider chrome is imported where the split
            # needs it rather than at module import time.
            from .chrome import _Separator

            edge = "right" if orientation == "vertical" else "bottom"
            for before, after in zip(children, children[1:]):
                before.add_chrome(
                    _Separator(self, before.id, after.id, edge).chrome
                )
        self._retile()
        self.invalidate()
        return children

    def focus_at(self, x: int, y: int) -> Pane | None:
        """Focus the pane a 0-based cell falls in; return it, or ``None``.

        The geometric half of the default focus policy, over
        :meth:`_pane_at`'s resolution: the cell resolves through the frame's
        ownership table (a chrome column and a band row included, since a
        pane claims its whole rectangle and the band joins the table), and
        the pane it names takes focus.  A cell no pane claims, and the band,
        leave focus where it is.
        """
        pane = self._pane_at(x, y)
        if pane is None or pane is self._frame.band:
            return None
        focused = self._frame.focused_pane
        if focused is None or focused.id != pane.id:
            self._frame.focus(pane)
            self.invalidate()  # a divider accent follows its focus
        return pane

    def viewport_rows(self, pane_id: str | None = None) -> tuple[int, int] | None:
        """A pane's window as ``(first, last)`` screen rows (the focused one
        by default).

        The rows the window occupies in the *frame* -- chrome subtracted,
        the band and any fixed region excluded -- which is what a
        drag-to-edge gesture must not scroll past, and what a host drawing
        over the window needs.  ``None`` before the first composition, for a
        pane the frame does not hold, or for a screen the fixed regions fill.
        """
        if pane_id is None:
            pane = self._frame.focused_pane
        else:
            pane = self._frame.pane(pane_id)
        if pane is None:
            return None
        placement = self._frame.region(pane.id)
        layout = self._frame.pane_layout(pane.id)
        if placement is None or layout is None or not layout.viewport_rows:
            return None
        return (placement.y, placement.y + len(layout.viewport_rows) - 1)

    # -- the band ------------------------------------------------------------------

    def add_band(self, viewport: Viewport) -> Pane:
        """Reserve the frame's bottom band over ``viewport``; return its pane.

        The band is a frame-level region beneath the pane area, holding its
        own viewport (D6): its rows paint below every pane, span the full
        frame width, and join the ownership table -- a footer block under
        the pointer resolves through :meth:`hit_test` exactly as a pane's
        rows do -- but it takes neither focus nor splits, and a wheel over
        it scrolls the focused pane instead.  One band per driver; a second
        :meth:`add_band` raises ``RuntimeError``.
        """
        if self._frame.band is not None:
            raise RuntimeError("the frame already holds a band")
        self._frame.set_band(Pane("band", Rect(0, 0, 0, 0), viewport))
        self._retile()
        self.invalidate()
        return self._frame.band

    def remove_band(self) -> None:
        """Release the frame's bottom band; the pane area takes its rows back."""
        if self._frame.band is None:
            return
        self._frame.set_band(None)
        self._retile()
        self.invalidate()

    def _band_rect(self, width: int) -> Rect | None:
        """The band's rectangle at ``width``, or ``None`` when none is attached.

        Its height is the rows its own content needs
        (:meth:`~mocode_tui.core.viewport.Viewport.natural_height`), so the
        band hugs the screen's bottom edge and grows only when its content
        does -- an opening palette pushes the pane area up, exactly as the
        pinned blocks it replaced did.
        """
        band = self._frame.band
        if band is None:
            return None
        height = min(band.viewport.natural_height(width), self.screen.height)
        if height <= 0:
            return None
        return Rect(0, self.screen.height - height, width, height)

    def _retile(self) -> None:
        """Lay the tiling out for the screen as it stands right now.

        The pane area is the whole screen minus the band's rows, and the
        band takes them at the bottom.  A same-size retile is a no-op, so
        the tree is re-divided only when something it lays out actually
        moved: the frame's structure changed since the last retile
        (:attr:`~mocode_tui.core.frame.Frame.revision` -- a split, a close,
        a chrome or overlay registration, the band), or the computed tiling
        differs from the recorded one, which the band's own content can
        move without any frame mutation (its height is
        :meth:`~mocode_tui.core.viewport.Viewport.natural_height`, read
        off the document it shows).
        """
        width, height = self.screen.width, self.screen.height
        band = self._band_rect(width)
        band_height = band.height if band is not None else 0
        pane_rect = Rect(0, 0, width, max(0, height - band_height))
        if (
            self._tiling == (pane_rect, band)
            and self._tiling_revision == self._frame.revision
        ):
            return
        self._tiling = (pane_rect, band)
        self._tiling_revision = self._frame.revision
        self._frame.retile(pane_rect, band=band)

    def _pane_at(self, x: int, y: int) -> Pane | None:
        """The pane a 0-based cell falls in, or ``None`` outside every pane.

        :meth:`focus_at`'s resolution and
        :meth:`_scroll_viewport`'s: the cell routes through the frame's
        ownership table -- the band included, which each caller excludes for
        itself.
        """
        table = self._frame.table
        if table is None:
            return None  # no composition has run yet
        span = table.resolve(y, x)
        return None if span is None else self._frame.pane(span.pane_id)

    def _scroll_viewport(self, event: Key | Paste) -> Viewport:
        """The viewport a scroll-key event moves (D5).

        A wheel report scrolls the pane under the pointer -- resolved
        through the frame's ownership table, chrome columns and all -- and
        falls back to the focused pane when the report names no pane.  The
        band holds no scroll state of its own, so a wheel over the footer
        scrolls the focused pane too.  A key (``page_up``/``page_down``)
        carries no pointer at all and always scrolls the focused pane --
        which, on a one-pane frame, is the same viewport either way.
        """
        if isinstance(event, MouseEvent):
            pane = self._pane_at(event.x, event.y)
            if pane is not None and pane is not self._frame.band:
                return pane.viewport
        return self._focused_viewport()

    # -- frames ---------------------------------------------------------------

    def invalidate(self) -> None:
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
        the kernel's :class:`~mocode_tui.core.selection.Selection`, written
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
        :func:`~mocode_tui.core.selection.highlight` between layout and
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
        ``ValueError``, the same answer :meth:`~mocode_tui.core.frame.Frame.focus`
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
        self.invalidate()

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

    async def read_key(self) -> Key | Paste | None:
        """Read the next key, with the scroll keys bound to scrolling.

        An event whose name is in :attr:`scroll_keys` (by default
        ``page_up``/``page_down``/``wheel_up``/``wheel_down``) is
        intercepted: it scrolls a viewport by the table's row count --
        negative up -- and the read continues, so the caller never sees it.
        The viewport is the one D5 names: a wheel report scrolls the pane
        under the pointer (falling back to the focused pane when it names
        none), a page key the focused pane.  Every other key and every
        :class:`~mocode_tui.core.events.Paste` is returned untouched, a
        :class:`~mocode_tui.core.events.MouseEvent` whose binding was deleted
        included -- after :attr:`focus_policy` has run on it, and a policy
        run that moved the focus marks the frame dirty so the next frame
        repaints.  The result is
        ``None`` when there is no key source, when the source reports EOF,
        and -- per the toolkit's non-live contract -- always on a non-live
        screen, even when a source is attached.

        Escape hatch: ``await tui.keys.read()`` reads the raw source
        directly, bypassing both the scroll-key interception and the
        non-live guard.
        """
        if not self.screen.live:
            return None
        source = self.keys
        if source is None:
            return None
        while True:
            event = await source.read()
            if event is None:
                return None
            if isinstance(event, Key):
                rows = self.scroll_keys.get(event.name)
                if rows is not None:
                    viewport = self._scroll_viewport(event)
                    if rows < 0:
                        viewport.scroll_up(-rows)
                    else:
                        viewport.scroll_down(rows)
                    self.invalidate()
                    continue
            focused = self._frame.focused_pane
            self.focus_policy(self, event)
            if self._frame.focused_pane is not focused:
                self.invalidate()  # the policy moved the focus: repaint
            return event

    def stop(self) -> None:
        """Ask :meth:`run` to finish: the pump exits and the session ends."""
        self._stopped = True
        self._wake()

    # -- mouse hit test ------------------------------------------------------------

    def hit_test(self, x: int, y: int) -> Hit | None:
        """Resolve a 0-based terminal cell to a block and a cell inside it.

        ``x``/``y`` are 0-based, exactly as a
        :class:`~mocode_tui.core.events.MouseEvent` reports them (the decoder
        subtracts 1 from the terminal's 1-based report fields), so an event's
        own ``x``/``y`` go straight in.  The result's ``row``/``col`` are
        0-based within the block's own rows, and ``pane_id`` names the pane
        the cell belongs to -- the document half of a hit, which is what lets
        a drag stay inside one document when a split holds several.  The cell
        routes through the frame's ownership table -- which pane claims it,
        and the document address inside that pane -- so a split frame
        resolves exactly as its panes compose.  A row no block owns (the
        blank fill below short content), a cell outside the last layout, and
        a block removed since that layout all resolve to ``None``.

        The driver never dispatches clicks itself: the host reads the
        :class:`~mocode_tui.core.events.MouseEvent` from :meth:`read_key`
        (button presses are not in :attr:`scroll_keys`), resolves it here,
        and calls the component itself with both block-internal coordinates
        -- e.g. a :class:`~mocode_tui.widgets.choice.Select` takes them and
        ignores the column::

            event = await tui.read_key()
            if isinstance(event, MouseEvent):
                hit = tui.hit_test(event.x, event.y)
                if hit is not None:
                    hit.block.component.click(hit.row, hit.col)

        The result stops at the **block**, not the widget: use
        :meth:`hit_component` when the cell should descend through the
        component's containers to the deepest leaf.
        """
        # The frame's ownership table is rebuilt by every composition; the
        # pane it names is the one whose viewport holds the scroll state.
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
        try:
            block = pane.viewport.document.get(span.block_id)
        except KeyError:
            return None  # removed since the last layout
        rect = pane.rect
        col = max(0, min(x - rect.x, rect.width - 1))
        return Hit(block, span.row_in_block, col, pane.id)

    def hit_component(self, x: int, y: int) -> tuple[Component, int, int] | None:
        """The deepest interactive component owning a cell, with its own coords.

        :meth:`hit_test` resolved to the block; this descends through every
        :class:`~mocode_tui.core.block.Container.child_at`
        (:func:`~mocode_tui.core.block.descend`) and returns the leaf -- the
        component a host dispatches a click to, with the coordinates of its
        own ``render`` output.  ``None`` for a cell no block owns, exactly
        as :meth:`hit_test` answers it.  The containers answer from their
        last render, so a component that has not painted yet declines every
        cell and the walk stops at the outermost component.
        """
        hit = self.hit_test(x, y)
        if hit is None:
            return None
        return descend(hit.block.component, hit.row, hit.col)

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
        minus the band's rows, the band beneath it), compose the frame, run
        the frame's overlay pipeline over the composition (the selection
        highlight is overlay #1), and paint the diff.  A retile re-divides
        the recorded split tree instead of rebuilding the panes, so every
        pane keeps its viewport, its chrome registry and its scroll state,
        the frame keeps its overlays and its focus, and nothing has to be
        carried across.  A single-pane frame with no band composes to its
        pane's own layout, so the row stream is the one the viewport laid
        out -- not a re-derivation of it.  A new width clears the selection
        (reflow), a new height does not.

        The sampling here is the driver's own: the retile and the reflow
        test both need the size *before* the composition runs, while
        :meth:`~mocode_tui.core.painter.Painter.paint` samples again for
        its full-repaint test, per the :class:`~mocode_tui.core.screen.Screen`
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
        else:
            loop.call_soon_threadsafe(event.set)

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
            delay = self.tick(self.clock())
            if self._stopped:
                break
            event = self._wake_up()
            event.clear()
            if delay is None:
                await event.wait()
            else:
                try:
                    await asyncio.wait_for(event.wait(), delay)
                except asyncio.TimeoutError:
                    pass

    # -- lifecycle ------------------------------------------------------------

    async def run(self, body: Callable[["TUI"], object]) -> None:
        """Run ``body(self)`` inside a full-screen session.

        The body is an ordinary coroutine function -- the library never
        builds an event loop of its own, so the caller owns ``asyncio.run``
        (or any other driver).  ``enter``/``leave`` bracket the session on a
        live screen (an exception or :meth:`stop` still leaves), a non-live
        screen sees neither and stays silent for the whole run, and a
        non-live run ends by dumping the final screen as plain text -- on the
        exception path too, before the error is re-raised.  A
        ``KeyboardInterrupt`` raised by the body is treated as :meth:`stop`.
        """
        self._stopped = False
        pump_task: asyncio.Task[None] | None = None
        body_error: BaseException | None = None
        try:
            try:
                if self.interactive and self.screen.live and self.keys is None:
                    source = RawTerminalKeys(hover=self._hover)
                    source.start()
                    self.keys = source
                    self._owns_keys = True
                if self.screen.live:
                    self.screen.enter()
                self._dirty = True
                pump_task = asyncio.create_task(self._pump(), name="mocode-tui-pump")
                await body(self)
            except KeyboardInterrupt:
                self.stop()
            except BaseException as exc:  # noqa: BLE001 - re-raised after teardown
                body_error = exc
        finally:
            pump_error = await self._teardown(pump_task)
        if body_error is not None:
            raise body_error
        if pump_error is not None:
            raise pump_error

    async def _teardown(self, pump_task: asyncio.Task[None] | None) -> BaseException | None:
        """Stop the pump and the keyboard, bracket the screen, dump if piped.

        Returns the pump's exception, if any, so :meth:`run` can re-raise it
        when the body itself finished cleanly.
        """
        self.stop()
        pump_error: BaseException | None = None
        if pump_task is not None:
            try:
                await pump_task
            except BaseException as exc:  # noqa: BLE001 - reported to run()
                pump_error = exc
        if self._owns_keys and self.keys is not None:
            self.keys.close()
            self._owns_keys = False
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
        """Write the final screen as plain text (non-live runs only)."""
        lines = [row.text for row in self.painter.rows]
        while lines and not lines[-1].strip():
            lines.pop()  # trailing all-blank rows are not content
        if not lines:
            return
        self.screen.write("\n".join(lines) + "\n")
        self.screen.flush()

    def __repr__(self) -> str:
        return (
            f"TUI(screen={self.screen!r}, blocks={len(self.document)}, "
            f"interactive={self.interactive})"
        )
