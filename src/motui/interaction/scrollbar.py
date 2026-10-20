"""scrollbar: the pane chrome -- the Scrollbar.

This module is the pane-chrome tier, the peer of
:mod:`motui.interaction.overlays` and the driver: it imports the kernel and
the ``Host`` seam, and nothing below it imports it.  Everything here is
*policy* -- what a scrollbar looks like, how far its thumb travels, what a
click on its track means -- over mechanisms the kernel owns: the pane's
chrome budget (:meth:`~motui.kernel.frame.Pane.add_chrome`), the scroll
state a layout carries (:attr:`~motui.kernel.viewport.ScreenLayout.offset` /
``total_rows``), and the pump's ``every`` handles.

:class:`Scrollbar` is the reference chrome (D2): one budgeted column at its
pane's right edge whose thumb maps the pane's ``offset`` over its
``total_rows``.  Constructing one registers the chrome; ``detach()``
unregisters it.  The bar renders from the pane's last layout alone -- it
never reads live viewport attributes -- and it routes its own input, so a
host dispatches through it.

The split's divider is **not** here: :class:`motui.kernel.chrome.Separator`
is the kernel's own chrome renderer, registered by ``TUI.split`` without a
driver-to-tier import edge.

**The dispatch order** is the one rule every module of this tier writes out:
a host routes an event through the chrome first, then the overlays, then
the content gestures, then its own dispatch.  It is geometric here -- the
bar's strip is derived from the frame's rectangles, while the frame's
ownership table resolves its cells as content, so the bar must see the
event before any hit test runs, or a press would anchor a selection under
the strip.  One fact of the order lives here: a wheel report never reaches
:meth:`Scrollbar.handle` because ``TUI.read_event`` intercepts its
``scroll_keys`` before the host loop runs.

The seam this module reads rather than owns is documented where it lives:
the driver's **frame**, through the ``Host.frame`` protocol member -- the
tiling, its focus and each pane's last layout -- and the driver's **pump**,
through the ``Host.every`` handle the track-repeat ticker rides.
"""

from __future__ import annotations

from typing import NamedTuple

from ..kernel import glyphs
from ..kernel.events import Event, MouseEvent
from ..kernel.frame import Chrome, Pane, Rect
from ..kernel.host import EveryHandle, Host
from ..kernel.lines import Line
from ..kernel.style import Style
from ..kernel.theme import DEFAULT_THEME, Theme
from ..kernel.viewport import ScreenLayout

__all__ = ["Scrollbar"]


class _Thumb(NamedTuple):
    """One thumb's geometry over one laid-out strip.

    ``pos`` is the thumb's first strip row and ``length`` its rows;
    ``track`` is the span the thumb may travel (the strip's height minus
    its own length, at least one) and ``scroll`` the document rows the
    window may move (``total_rows`` minus the window rows, at least one) --
    the two ends of the mapping ``pos = round(offset * track / scroll)``.
    """

    pos: int
    length: int
    track: int
    scroll: int


def _thumb_of(layout: ScreenLayout, height: int, min_thumb: int) -> _Thumb | None:
    """The thumb a laid-out pane maps onto a strip ``height`` rows tall.

    Pure arithmetic over the layout (its ``offset``, its ``total_rows``
    and its window rows), never over live viewport state::

        length = min(height, max(min_thumb, round(window * height / total)))
        pos    = round(offset * (height - length) / max(1, total - window))

    ``length`` is the share of the strip the visible window occupies -- a
    small window over a long document is a short thumb -- and ``pos`` walks
    the thumb across the ``height - length`` cells the track leaves it as
    the offset walks its ``total - window`` span.  ``round`` is the
    builtin, so a half goes to the even integer (``round(4.5) == 4``) and
    the geometry is reproducible rather than merely approximate; ``pos``
    is clamped into the track so a stale layout cannot paint a thumb off
    the strip.

    ``None`` when there is no thumb to map: the document fits the window
    (``total <= window`` -- an empty document, or one shorter than the
    window, included) or ``min_thumb=0`` shaved the thumb away entirely.
    A strip with no thumb paints its plain track, which reads as "nothing
    to scroll here".
    """
    total = layout.total_rows
    window = len(layout.body_rows)
    if height <= 0 or total <= window:
        return None
    length = min(height, max(min_thumb, round(window * height / total)))
    if length <= 0:
        return None
    track = max(1, height - length)
    scroll = max(1, total - window)
    pos = min(track, max(0, round(layout.offset * track / scroll)))
    return _Thumb(pos, length, track, scroll)


class Scrollbar:
    """A right-edge scrollbar chrome: a budgeted strip that maps the scroll.

    ``tui`` is the driver whose frame the bar registers on and whose pump
    the track-repeat rides.  ``pane`` names the pane the bar belongs to --
    a pane id, or ``None`` (the default) for the frame's first pane, the
    one the driver's document lives in -- and an id the frame does not hold
    raises ``ValueError`` at
    construction.  ``size`` is the column budget the bar asks its pane
    for; the kernel clips a budget that would squeeze the pane's viewport
    out, and a bar clipped to nothing routes nothing.  ``min_thumb`` is
    the shortest thumb the geometry may shave a long document down to.
    ``style`` / ``thumb_style`` are explicit style overrides and ``theme``
    the rest, each resolved at render time through the charter --
    explicit > ``theme`` field > :data:`DEFAULT_THEME
    <motui.kernel.theme.DEFAULT_THEME>` field -- so
    ``Theme(scrollbar=...)`` restyles the track and
    ``Theme(scrollbar_thumb=...)`` the thumb, while an explicit style wins
    over both.  ``track`` / ``thumb`` are the two cells the strip paints
    (defaults :data:`~motui.kernel.glyphs.TRACK` /
    :data:`~motui.kernel.glyphs.THUMB`): a glyph is content, so a host
    picks its own, and ``""`` paints the cell's budget empty -- the
    closest semantics to ``size=0`` for a glyph the strip cannot draw.
    ``scroll_tick`` is the period a held track click repeats its page at.

    Constructing the bar registers it on the pane (the budget is
    negotiated at the next composition, and the pane's viewport re-wraps
    at the reduced width -- content is never hidden under chrome);
    ``detach()`` unregisters it and cancels the ticker.

    The bar's strip is painted by the chrome budget as one row per strip
    cell, each exactly ``size`` columns wide (:attr:`track` cells, with
    :attr:`thumb` over the thumb's rows), from the pane's own layout and
    the strip's length alone -- the pure function the
    :class:`~motui.kernel.frame.Chrome` protocol asks for, and one whose
    strip is remembered under the very state it reads, so a frame that
    repaints without moving the window re-uses it (see :meth:`_paint`).

    **The gesture** (``handle``, the consume-a-key contract) is the bar's
    own, resolved geometrically (module docstring): a left press in the
    strip is consumed.  On the thumb it is a grab-and-drag -- the motion
    maps the thumb's centre row to the offset through the geometry's own
    scale, anchored at the grab so the thumb never jumps (see
    :meth:`_drag` for the arithmetic).  On the track it pages one viewport
    page toward the pointer's side and repeats on a ``tui.every`` ticker
    while the button is held -- the selection gesture's autoscroll
    pattern, standing down on release, on the pointer leaving the strip,
    on detach, and at the document end.  Every other event passes through.
    """

    __slots__ = (
        "_chrome",
        "_grab",
        "_handle",
        "_held",
        "_min_thumb",
        "_pane_id",
        "_repeat",
        "_scroll_tick",
        "_size",
        "_strip_cache",
        "_style",
        "_theme",
        "_thumb",
        "_thumb_style",
        "_track",
        "_tui",
    )

    def __init__(
        self,
        tui: Host,
        *,
        pane: str | None = None,
        size: int = 1,
        min_thumb: int = 1,
        style: Style | None = None,
        thumb_style: Style | None = None,
        track: str = glyphs.TRACK,
        thumb: str = glyphs.THUMB,
        theme: Theme | None = None,
        scroll_tick: float = 0.05,
    ) -> None:
        self._tui = tui
        self._size = size
        self._min_thumb = min_thumb
        self._style = style
        self._thumb_style = thumb_style
        self._track = track
        self._thumb = thumb
        self._theme = theme
        self._scroll_tick = scroll_tick
        # The driver's frame seam (module docstring): the bar registers on
        # whichever pane currently holds the id, and a split keeps that id
        # on the first child -- so the registration rides any retile, which
        # rewrites pane rectangles in place rather than rebuilding panes.
        frame = tui.frame
        if pane is None:
            first = frame.panes[0] if frame.panes else None
            host = first
        else:
            host = frame.pane(pane)
        if host is None:
            known = [held.id for held in frame.panes]
            raise ValueError(f"no pane named {pane!r}: the frame holds {known}")
        self._pane_id = host.id
        self._chrome = Chrome("right", size, self._paint)
        host.add_chrome(self._chrome)
        self._held = False
        self._grab: tuple[int, int] | None = None  # (strip row, offset) of the grab
        self._repeat = 0  # the held-track page direction: 0, 1 (down), -1 (up)
        self._handle: EveryHandle | None = None
        # The last strip painted and the state it was painted from: the memo
        # of :meth:`_paint`, keyed by everything that paint reads.
        self._strip_cache: tuple[tuple, tuple[Line, ...]] | None = None

    def __repr__(self) -> str:
        return f"Scrollbar(pane={self._pane_id!r}, size={self._size})"

    # -- the event contract --------------------------------------------------------

    def handle(self, event: Event) -> bool:
        """Advance the bar with ``event``; ``True`` when the bar consumed it.

        The consume-a-key contract
        (:meth:`~motui.widgets.textfield.Input.handle` /
        :meth:`~motui.widgets.textfield.Editor.handle` /
        :meth:`~motui.interaction.gesture.SelectionGesture.handle`), and the
        dispatch position it implies -- chrome before gestures before the
        host's own dispatch -- is written out in the module docstring.
        The bar consumes the left button over its strip: a press there
        grabs the thumb or pages the track, and the motion and release
        that follow that press are the bar's, wherever the pointer then
        travels.  Everything else passes through untouched -- every key,
        every paste, every non-left button, every wheel report
        (``scroll_keys`` owns the wheel) and every report outside the
        strip.  A detached bar's strip is no chrome of the pane's any more,
        so nothing under the pointer resolves as the bar's and every event
        passes through.
        """
        if not isinstance(event, MouseEvent):
            return False
        if event.button != "left":
            return False  # the wheel reports and the other buttons stay the host's
        if event.kind == "press":
            if not self._covers(event.x, event.y):
                return False  # outside the strip: the content is under the pointer
            self._held = True
            self._press(event.y)
            return True
        if not self._held:
            return False  # the press was never ours: nothing to drag or repeat
        if event.kind == "release":
            self._release()
            return True
        if event.kind == "motion":
            self._motion(event.x, event.y)
            return True
        return False

    # -- lifecycle ---------------------------------------------------------------

    def detach(self) -> None:
        """Unregister the chrome and cancel the ticker (the EveryHandle convention).

        The stored selection of a gesture is not ours to clear; the strip
        is: the pane gives the bar's column back to its viewport, which
        re-wraps at the full width on the next composition, and nothing
        paints a track again until a bar registers afresh.  Detaching is
        idempotent, and the pane's registry is the identity that makes it
        so: the membership test comes first because
        :meth:`~motui.kernel.frame.Pane.remove_chrome` raises on a miss,
        and a pane that left the frame took the registration with it.
        """
        self._release()  # drops the in-flight drag and the held-track ticker
        pane = self._pane()
        if pane is not None and self._chrome in pane.chrome:
            pane.remove_chrome(self._chrome)

    # -- the paint ---------------------------------------------------------------

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip: a track of ``track``, ``thumb`` over the thumb.

        ``length`` is the strip's length along the pane's other axis -- its
        height for a right-edge band -- and the geometry is read off the
        pane's layout through :func:`_thumb_of`.  Each row is exactly
        ``size`` columns wide; a budget clipped by the kernel is cut by the
        compositor's splice, so the bar never paints past its grant.  An
        empty glyph paints an empty row answer for its ``size`` budget --
        the column stays reserved (the pane's re-wrap does not move), the
        closest semantics to ``size=0`` for a glyph there is nothing to
        draw with.

        The strip is a pure function of what it reads -- the layout's
        offset, total rows and window, the strip's length, the bar's own
        size, shortest thumb, **the two glyphs** and **resolved** styles --
        so it is remembered under exactly those: a frame that comes back
        with the same layout hands the strip back instead of rebuilding it,
        while any scroll, retile, re-skin or re-glyphed bar is a different
        key and paints afresh.  The gesture's ``refresh()`` calls need no
        signal of their own here: the state they move (the pane's offset) is
        the state this key carries.  A fresh list comes back every call, as
        it always has -- a caller owns the rows it is handed.
        """
        if length <= 0:
            return []
        track_style, thumb_style = self._resolve_track(), self._resolve_thumb()
        key = (
            layout.offset,
            layout.total_rows,
            len(layout.body_rows),
            length,
            self._size,
            self._min_thumb,
            self._track,
            self._thumb,
            track_style,
            thumb_style,
        )
        cached = self._strip_cache
        if cached is not None and cached[0] == key:
            return list(cached[1])
        thumb = _thumb_of(layout, length, self._min_thumb)
        first = thumb.pos if thumb is not None else 0
        last = first + thumb.length if thumb is not None else 0
        track_line = Line.from_text(self._track * self._size, track_style)
        thumb_line = Line.from_text(self._thumb * self._size, thumb_style)
        strip = tuple(
            thumb_line if first <= index < last else track_line
            for index in range(length)
        )
        self._strip_cache = (key, strip)
        return list(strip)

    def _resolve_track(self) -> Style:
        """The track's style: explicit ``style`` > theme > DEFAULT (charter)."""
        if self._style is not None:
            return self._style
        theme = self._theme if self._theme is not None else DEFAULT_THEME
        return theme.scrollbar

    def _resolve_thumb(self) -> Style:
        """The thumb's style: explicit ``thumb_style`` > theme > DEFAULT."""
        if self._thumb_style is not None:
            return self._thumb_style
        theme = self._theme if self._theme is not None else DEFAULT_THEME
        return theme.scrollbar_thumb

    # -- the pane, geometrically ---------------------------------------------------

    def _pane(self) -> Pane | None:
        """The bar's pane as the driver's frame holds it right now."""
        return self._tui.frame.pane(self._pane_id)

    def _strip(self) -> Rect | None:
        """The bar's strip as a rectangle of the screen, ``None`` when none.

        The band the kernel granted the bar's own chrome
        (:meth:`~motui.kernel.frame.Pane.band`) -- the very cells the
        compositor paints the strip into, so routing and painting are one
        derivation and can never disagree about the column, whatever else
        the pane stacked on that edge (the split's separator stacks
        outermost, one column outside the bar).  ``None`` also when the
        pane left the frame, and when the grant was clipped away -- a bar
        the pane could never host routes nothing.
        """
        pane = self._pane()
        if pane is None:
            return None
        return pane.band(self._chrome)

    def _covers(self, x: int, y: int) -> bool:
        """Whether the cell sits inside the bar's strip (the routing test)."""
        strip = self._strip()
        return strip is not None and (
            strip.x <= x < strip.right and strip.y <= y < strip.bottom
        )

    def _geometry(self) -> _Thumb | None:
        """The thumb over the pane's last laid-out strip, ``None`` without one.

        Read off the composed layout (``frame.pane_layout``) -- the same
        pure state the bar paints from, so a gesture and a paint that read
        in the same instant agree by construction.
        """
        layout = self._tui.frame.pane_layout(self._pane_id)
        strip = self._strip()
        if layout is None or strip is None:
            return None
        return _thumb_of(layout, strip.height, self._min_thumb)

    # -- the gesture ---------------------------------------------------------------

    def _press(self, y: int) -> None:
        """Grab the thumb under the pointer, or page the track it missed.

        A press inside the thumb records the grab -- the strip row it
        landed on and the offset the pane held -- and the motions that
        follow drag from there.  A press on the track pages one viewport
        page toward the pointer's side (the thumb's midpoint divides the
        two sides; an unthumbed strip divides at its own) and arms the
        ticker, which repeats the page while the button is held.
        """
        self._cancel_repeat()
        strip = self._strip()
        if strip is None:
            return
        thumb = self._geometry()
        row = y - strip.y
        pane = self._pane()
        if (
            thumb is not None
            and pane is not None
            and thumb.pos <= row < thumb.pos + thumb.length
        ):
            self._grab = (row, pane.viewport.offset)
            return
        divider = (
            thumb.pos + thumb.length // 2 if thumb is not None else strip.height // 2
        )
        self._repeat = -1 if row < divider else 1
        self._page(self._repeat)
        self._handle = self._tui.every(self._scroll_tick, self._tick)

    def _motion(self, x: int, y: int) -> None:
        """Drag the grabbed thumb, or stand a held track page down.

        Called only while the bar holds the button.  A drag maps the
        pointer's strip row through the geometry whatever column the
        pointer is at -- a scrollbar drag follows the pointer past its own
        strip, clamped at the document's ends by the offset itself.  A
        held track page stands down the moment the pointer leaves the
        strip: the page it repeats was aimed at the side the press landed.
        """
        strip = self._strip()
        if strip is None:
            self._cancel_repeat()
            return
        if self._grab is not None:
            self._drag(y - strip.y)
            return
        if not (strip.x <= x < strip.right and strip.y <= y < strip.bottom):
            self._cancel_repeat()  # edge-exit

    def _drag(self, row: int) -> None:
        """Scroll the pane so the grabbed thumb point rides at strip ``row``.

        The mapping, anchored at the grab.  The geometry paints
        ``pos = round(offset * track / scroll)``, so one strip row is
        ``scroll / track`` document rows; a pointer that has moved ``d``
        strip rows since the grab therefore moves the window
        ``round(d * scroll / track)`` document rows from the offset the
        grab was taken at::

            target = grab_offset + round((row - grab_row) * scroll / track)

        clamped to the document's ``[0, scroll]`` span.  The anchor --
        rather than re-projecting the pointer through the rounded forward
        map -- is what keeps the thumb from jumping on grab: several
        offsets share one thumb row (``round``), and the anchor resolves
        that ambiguity at the cell the user pressed.  The thumb's centre
        row, ``pos + length // 2``, is the forward map's reference for
        the offset, so a grab taken at the centre is this mapping run
        forwards with no correction.  ``grab_offset`` is the pane's live
        offset at the press, which keeps the drag exact even when several
        motions land inside one painted frame.
        """
        grab = self._grab
        thumb = self._geometry()
        pane = self._pane()
        if grab is None or thumb is None or pane is None:
            return
        target = grab[1] + round((row - grab[0]) * thumb.scroll / thumb.track)
        target = max(0, min(thumb.scroll, target))
        delta = target - pane.viewport.offset
        if delta == 0:
            return
        if delta > 0:
            pane.viewport.scroll_down(delta)
        else:
            pane.viewport.scroll_up(-delta)
        self._tui.refresh()

    def _release(self) -> None:
        """End the drag or the held page: the bar stops with the button."""
        self._held = False
        self._grab = None
        self._cancel_repeat()

    def _page(self, side: int) -> None:
        """Scroll one viewport page toward ``side`` (``1`` down, ``-1`` up).

        A page is the window's own height, read off the composed layout so
        it is the window as it was last laid out.  The bar scrolls its own
        pane's viewport -- not the focused pane's, since a bar on an
        unfocused pane still scrolls its own content -- and invalidates
        the frame so the pump repaints.
        """
        layout = self._tui.frame.pane_layout(self._pane_id)
        pane = self._pane()
        if layout is None or pane is None:
            return
        page = len(layout.body_rows)
        if page <= 0:
            return
        if side > 0:
            pane.viewport.scroll_down(page)
        else:
            pane.viewport.scroll_up(page)
        self._tui.refresh()

    def _tick(self) -> None:
        """One held-track tick (pump callback): page again, or stand down.

        The tick stands down at the document end the way the selection
        gesture's edge ticker does -- a page that could not move the
        window freezes the content under the held pointer, so repeating it
        would burn the pump for nothing.
        """
        if self._repeat == 0:
            self._cancel_repeat()
            return
        pane = self._pane()
        if pane is None:
            self._cancel_repeat()
            return
        before = pane.viewport.offset
        self._page(self._repeat)
        if pane.viewport.offset == before:
            self._cancel_repeat()  # pinned at the document's end

    def _cancel_repeat(self) -> None:
        """Cancel the held-track ticker (a no-op when none is armed)."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._repeat = 0

