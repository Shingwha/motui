"""chrome: the pane chrome and the frame overlays -- Scrollbar, Toasts, and
their gestures.

This module is the assembly tier, the peer of :mod:`mocode_tui.selection`
and :mod:`mocode_tui.app`: it imports the driver and the kernel, and
nothing below it imports it.  Everything here is *policy* -- what a
scrollbar looks like, how far its thumb travels, what a click on its track
means -- over mechanisms the kernel owns: the pane's chrome budget
(:meth:`~mocode_tui.core.frame.Pane.add_chrome`), the scroll state a
layout carries (:attr:`~mocode_tui.core.viewport.ScreenLayout.offset` /
``total_rows``), and the pump's :meth:`~mocode_tui.app.TUI.every` handles.

:class:`Scrollbar` is the reference chrome (D2): one budgeted column at
its pane's right edge whose thumb maps the pane's ``offset`` over its
``total_rows``.  Constructing one registers the chrome; ``detach()``
unregisters it.  The bar renders from the pane's last layout alone -- it
never reads live viewport attributes -- and it routes its own input, so a
host dispatches through it.

:class:`Toasts` is the reference overlay (D3): a corner-anchored stack of
transient bands painted over the composed frame.  Constructing one
registers the overlay; ``detach()`` unregisters it and cancels the
ticker.  Its paint is a pure function of the frame's rows and the
live toast list -- time and input live in the controller, never in the
kernel -- and it routes a press that lands inside a toast's own
rectangle, so a host dispatches through it the same way.

**The dispatch order.**  A host routes every event through the bar before
any content gesture and before its own dispatch, with the overlays between
the chrome and the gestures::

    scrollbar = Scrollbar(tui)
    toasts = Toasts(tui)
    gesture = SelectionGesture(tui)
    event = await tui.read_key()
    if not scrollbar.handle(event):        # 1. chrome, first
        if not toasts.handle(event):       # 2. overlays, next
            if not gesture.handle(event):  # 3. content gestures
                ...                        # 4. the host's own dispatch

Three rules make that order exact:

* *Chrome first, and geometrically.*  The bar's strip is derived from its
  pane's rectangle -- the frame knows where the pane sits -- so the bar
  routes before any hit test runs.  It has to: the frame's ownership
  table resolves the strip column as *content* (a pane claims its whole
  rectangle, and a band row rides the row's document address), so a press
  that reached a hit test first would anchor a selection or dispatch a
  click on the text under the chrome.  A press the bar consumes reaches
  neither.
* *Overlays after chrome, before gestures -- geometrically too.*  An
  overlay's band is derived from the frame's rectangle the same way, and
  the frame's ownership table resolves its cells as content as well (an
  overlay claims nothing; it only paints last).  A press inside a toast
  therefore has to be consumed before a hit test runs, or the gesture
  would anchor a selection on the text under the band and the host would
  dispatch a click on it.  Placing the overlays *after* the chrome keeps
  the bar's own columns the bar's: a band that covers a strip column
  paints over it, but a press there still routes to the bar first.
* *Gestures before host dispatch.*  The bar, the overlays and the
  selection gesture speak the same consume-a-key contract
  (``handle(event) -> bool``): a controller that consumed the event leaves
  no trace in the host's own state, and one that passed it through hands
  the host the event exactly as it arrived.
* *The wheel is nobody's chrome.*  :meth:`~mocode_tui.app.TUI.read_key`
  intercepts :attr:`~mocode_tui.app.TUI.scroll_keys` before the host loop
  runs, so a wheel report never reaches :meth:`Scrollbar.handle`; one
  that does (a host that deleted the binding) passes through untouched --
  the scroll keys own the wheel, as they own the page keys.

Two seams this module reads rather than owns, both documented where they
live: the driver's **frame**, through its public
:attr:`~mocode_tui.app.TUI.frame` property -- the tiling, its focus, its
overlay registry and each pane's last layout -- and the driver's **pump**,
through the public :meth:`~mocode_tui.app.TUI.every` handle the
track-repeat and expiry tickers ride.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import NamedTuple

from .app import EveryHandle, TUI
from .core.block import Component
from .core.events import Key, MouseEvent, Paste
from .core.frame import Chrome, Frame, Pane, Rect
from .core.lines import Line, cut_line, overlay
from .core.style import Style
from .core.text import Text
from .core.theme import DEFAULT_THEME, Theme
from .core.viewport import ScreenLayout

__all__ = ["Scrollbar", "Toasts"]

#: The track's cell: a light shade reads as chrome, never as content.
TRACK = "░"

#: The thumb's cell: a full block reads as the strongest cell of its row.
THUMB = "█"


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
    window = len(layout.viewport_rows)
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
    <mocode_tui.core.theme.DEFAULT_THEME>` field -- so
    ``Theme(scrollbar=...)`` restyles the track and
    ``Theme(scrollbar_thumb=...)`` the thumb, while an explicit style wins
    over both.  ``scroll_tick`` is the period a held track click repeats
    its page at.

    Constructing the bar registers it on the pane (the budget is
    negotiated at the next composition, and the pane's viewport re-wraps
    at the reduced width -- content is never hidden under chrome);
    ``detach()`` unregisters it and cancels the ticker.

    The bar's strip is painted by the chrome budget as one row per strip
    cell, each exactly ``size`` columns wide (:data:`TRACK` cells, with
    :data:`THUMB` over the thumb's rows), from the pane's own layout and
    the strip's length alone -- the pure function the
    :class:`~mocode_tui.core.frame.Chrome` protocol asks for.

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
        "_detached",
        "_grab",
        "_handle",
        "_held",
        "_min_thumb",
        "_pane_id",
        "_repeat",
        "_scroll_tick",
        "_size",
        "_style",
        "_theme",
        "_thumb_style",
        "_tui",
    )

    def __init__(
        self,
        tui: TUI,
        *,
        pane: str | None = None,
        size: int = 1,
        min_thumb: int = 1,
        style: Style | None = None,
        thumb_style: Style | None = None,
        theme: Theme | None = None,
        scroll_tick: float = 0.05,
    ) -> None:
        self._tui = tui
        self._size = size
        self._min_thumb = min_thumb
        self._style = style
        self._thumb_style = thumb_style
        self._theme = theme
        self._scroll_tick = scroll_tick
        # The driver's frame seam (module docstring): the bar registers on
        # whichever pane currently holds the id, and a split keeps that id
        # on the first child -- so the registration rides any retile, which
        # rewrites pane rectangles in place rather than rebuilding panes.
        frame = tui.frame
        primary = frame.panes[0] if frame.panes else None
        self._pane_id = (
            pane
            if pane is not None
            else (primary.id if primary is not None else "primary")
        )
        host = frame.pane(self._pane_id)
        if host is None:
            known = [held.id for held in frame.panes]
            raise ValueError(
                f"unknown pane {self._pane_id!r}: the frame holds {known}"
            )
        self._chrome = Chrome("right", size, self._paint)
        host.add_chrome(self._chrome)
        self._detached = False
        self._held = False
        self._grab: tuple[int, int] | None = None  # (strip row, offset) of the grab
        self._repeat = 0  # the held-track page direction: 0, 1 (down), -1 (up)
        self._handle: EveryHandle | None = None

    def __repr__(self) -> str:
        return f"Scrollbar(pane={self._pane_id!r}, size={self._size})"

    # -- the event contract --------------------------------------------------------

    def handle(self, event: Key | Paste | MouseEvent) -> bool:
        """Advance the bar with ``event``; ``True`` when the bar consumed it.

        The consume-a-key contract (``Input.handle_key`` /
        ``Editor.handle_key`` / ``SelectionGesture.handle``), and the
        dispatch position it implies -- chrome before gestures before the
        host's own dispatch -- is written out in the module docstring.
        The bar consumes the left button over its strip: a press there
        grabs the thumb or pages the track, and the motion and release
        that follow that press are the bar's, wherever the pointer then
        travels.  Everything else passes through untouched -- every key,
        every paste, every non-left button, every wheel report
        (``scroll_keys`` owns the wheel) and every report outside the
        strip.
        """
        if self._detached:
            return False
        if not isinstance(event, MouseEvent):
            return False
        if event.name != "left":
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
        paints a track again until a bar registers afresh.
        """
        self._detached = True
        self._release()  # drops the in-flight drag and the held-track ticker
        pane = self._pane()
        if pane is not None and self._chrome in pane.chrome:
            pane.remove_chrome(self._chrome)

    # -- the paint ---------------------------------------------------------------

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip: a track of :data:`TRACK`, :data:`THUMB` over the thumb.

        ``length`` is the strip's length along the pane's other axis -- its
        height for a right-edge band -- and the geometry is read off the
        pane's layout through :func:`_thumb_of`.  Each row is exactly
        ``size`` columns wide; a budget clipped by the kernel is cut by the
        compositor's splice, so the bar never paints past its grant.
        """
        if length <= 0:
            return []
        thumb = _thumb_of(layout, length, self._min_thumb)
        first = thumb.pos if thumb is not None else 0
        last = first + thumb.length if thumb is not None else 0
        track_line = Line.from_text(TRACK * self._size, self._resolve_track())
        thumb_line = Line.from_text(THUMB * self._size, self._resolve_thumb())
        return [
            thumb_line if first <= index < last else track_line
            for index in range(length)
        ]

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

        Derived geometrically from the pane's rectangle -- the frame knows
        where the pane sits, so the routing never touches the ownership
        table (which resolves the strip column as content, because a pane
        claims its whole rectangle and a band row rides the row's document
        address).  A right-edge chrome of ``size`` cells holds the pane's
        outermost columns, and the grant replays the kernel's own clip
        (the pane always keeps one column of viewport), so a bar the pane
        could never host routes nothing.  ``None`` also when the pane left
        the frame.
        """
        pane = self._pane()
        if pane is None:
            return None
        rect = pane.rect
        granted = min(max(0, self._size), max(0, rect.width - 1))
        if granted <= 0:
            return None
        return Rect(rect.right - granted, rect.y, granted, rect.height)

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
        self._tui.invalidate()

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
        page = len(layout.viewport_rows)
        if page <= 0:
            return
        if side > 0:
            pane.viewport.scroll_down(page)
        else:
            pane.viewport.scroll_up(page)
        self._tui.invalidate()

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


#: The four corners a toast stack anchors at.
_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")

#: A toast's widest band: the clamp ceiling, beside the frame's half-width.
MAX_TOAST_WIDTH = 40

#: How often the one expiry ticker runs while any toast is live.  A toast's
#: last frame is resolved to a tenth of a second; a finer tick would only
#: burn wakeups.
EXPIRY_TICK = 0.1


@dataclass(frozen=True)
class _Toast:
    """One live toast: the component it shows, its band style, its expiry.

    ``style`` is the toast's own explicit band style, or ``None`` to resolve
    through the charter (the controller's ``style`` > its ``theme`` >
    :data:`DEFAULT_THEME <mocode_tui.core.theme.DEFAULT_THEME>`).
    ``expires_at`` is a ``tui._clock()`` reading taken when the toast was
    shown -- timestamps live in the controller, the layout stays timeless.
    """

    component: Component
    style: Style | None
    expires_at: float


def _stack(
    toasts: Sequence[_Toast], rect: Rect, corner: str
) -> list[tuple[_Toast, Rect, list[Line]]]:
    """Where each live toast paints inside ``rect``: the shared geometry.

    A toast renders at the *ceiling* -- :data:`MAX_TOAST_WIDTH` or the
    frame's half width, whichever is smaller -- and its band is as wide as
    the widest row that render produced, capped at the ceiling: a short
    toast is a short band, a long one wraps at the ceiling and never covers
    more than half the frame.  The rows are the component's own, fit to the
    ceiling, so a component that ignores its width is truncated by the same
    final guard the widgets apply.  A frame too narrow to host even one
    column yields no geometry, and an empty component (no rows, or rows that
    measure nothing) paints no band.

    The stack grows away from ``corner``: the newest toast sits at the
    corner and the older ones follow it, one blank row between neighbours,
    the tail clipped at the frame's far edge (the rows past the frame paint
    nothing).  The rectangle each toast gets is the one the paint splices
    through and the press test routes with -- one derivation, two readers.

    The toasts come back in show order (oldest first), each with its
    rectangle and its content rows.
    """
    ceiling = min(MAX_TOAST_WIDTH, rect.width // 2)
    if ceiling <= 0:
        return []
    measured: list[tuple[_Toast, int, list[Line]]] = []
    for toast in toasts:
        rendered = [row.fit(ceiling) for row in toast.component.render(ceiling)]
        # An empty component renders no rows, which measures to zero width.
        width = min(max((row.width for row in rendered), default=0), ceiling)
        if width <= 0:
            continue  # nothing to show: an empty component paints no band
        measured.append((toast, width, rendered))
    left = corner.endswith("left")
    placed: list[tuple[_Toast, Rect, list[Line]]] = []
    if corner.startswith("top"):
        cursor = rect.y
        for toast, width, rendered in reversed(measured):
            x = rect.x if left else rect.right - width
            placed.append((toast, Rect(x, cursor, width, len(rendered)), rendered))
            cursor += len(rendered) + 1  # one blank row between neighbours
    else:
        cursor = rect.bottom
        for toast, width, rendered in reversed(measured):
            cursor -= len(rendered)
            x = rect.x if left else rect.right - width
            placed.append((toast, Rect(x, cursor, width, len(rendered)), rendered))
            cursor -= 1  # one blank row between neighbours
    placed.reverse()  # show order: oldest first
    return placed


def _band_row(row: Line, width: int, band: Style) -> Line:
    """One toast row: its content over the band's filled background.

    The colored-vs-attribute rule of :func:`~mocode_tui.core.lines.overlay`
    -- the band paints underneath, a segment carrying a color of its own
    keeps it and an attribute-only one shows the band through -- then the
    row is filled out to ``width`` with
    :meth:`~mocode_tui.core.lines.Line.filled`, the band primitive, so a
    blank content row reads as a solid band row.
    """
    content = Line(overlay(band, row.segments))
    return content + Line.filled(width - row.width, band)


def _splice_band(base: Line, band: Line, x: int, width: int, frame_width: int) -> Line:
    """Place one toast row into the frame row beneath it.

    The kernel's column cut -- the compositor splices a pane's rows into the
    frame the same way -- re-expressed with the public primitives: the base's
    columns the band does not cover are kept, the ones it covers are
    replaced, and a base cut short is padded back so the row stays exactly
    ``frame_width`` wide.  A band spanning the frame goes through untouched.
    """
    if x == 0 and width == frame_width:
        return band
    left = cut_line(base, 0, x).pad_to(x)
    right = cut_line(base, x + width, frame_width).pad_to(frame_width - x - width)
    return left + band + right


class Toasts:
    """A corner-anchored stack of transient toasts over the composed frame.

    ``tui`` is the driver whose frame the overlay registers on, whose clock
    stamps each toast's expiry and whose pump the expiry ticker rides.
    ``ttl`` is how long a toast lives (a per-show ``ttl`` overrides it);
    ``max_shown`` the most toasts the stack holds -- a show past it evicts
    the oldest.  ``corner`` anchors the stack
    (one of ``top-left``, ``top-right``, ``bottom-left``,
    ``bottom-right``); the newest toast sits at the corner and the stack
    grows away from it, one blank row between neighbours.  ``style`` /
    ``theme`` are the band's explicit style and the rest, each resolved at
    render time through the charter -- a toast's own ``style`` > the
    controller's ``style`` > the theme's ``toast`` > :data:`DEFAULT_THEME
    <mocode_tui.core.theme.DEFAULT_THEME>` -- so ``Theme(toast=...)``
    restyles every band and an explicit style wins over both.  The ticker's
    period is the module's :data:`EXPIRY_TICK`; a toast's last frame needs
    no finer resolution than that.

    Constructing the controller registers the overlay on the frame, where
    it stays for the frame's life -- a retile rewrites the pane rectangles
    in place rather than rebuilding the frame, and the driver's own
    selection overlay rides the same registry.  A toast is shown with
    :meth:`show`
    -- a plain string (wrapped in a :class:`~mocode_tui.core.text.Text`)
    or any Component, the customizability charter, so a toast can be a
    Notice, a Spinner or a host's own renderable.  ``detach()`` drops the
    stack, unregisters the overlay and cancels the ticker.

    **The paint** is the pure half: the frame's rows and the live toast
    list are its only inputs.  Each toast renders at the clamp ceiling,
    takes a :meth:`~mocode_tui.core.lines.Line.filled` band as wide as its
    widest row, and is spliced into the frame rows at its corner
    rectangle; an empty stack hands the layout back unchanged.  **The
    controller** owns everything time- and input-shaped: one ``tui.every``
    ticker checks expiry against ``tui._clock()`` and drops the due toasts,
    and :meth:`handle` consumes a press inside a toast's rectangle to
    dismiss it -- the selection/autoscroll pattern verbatim, timestamps and
    routing in the controller, mechanism in the kernel.
    """

    __slots__ = (
        "_corner",
        "_detached",
        "_handle",
        "_max_shown",
        "_style",
        "_theme",
        "_toasts",
        "_ttl",
        "_tui",
    )

    def __init__(
        self,
        tui: TUI,
        *,
        ttl: float = 4.0,
        max_shown: int = 3,
        corner: str = "top-right",
        style: Style | None = None,
        theme: Theme | None = None,
    ) -> None:
        if corner not in _CORNERS:
            raise ValueError(
                f"toast corner must be one of {_CORNERS}, got {corner!r}"
            )
        self._tui = tui
        self._ttl = ttl
        self._max_shown = max_shown
        self._corner = corner
        self._style = style
        self._theme = theme
        self._toasts: list[_Toast] = []
        self._detached = False
        self._handle: EveryHandle | None = None
        # The driver's frame seam (module docstring): the overlay registers
        # here for the frame's life -- a retile re-divides the tiling in
        # place, so nothing carries across.
        tui.frame.add_overlay(self)

    def __repr__(self) -> str:
        return f"Toasts(corner={self._corner!r}, shown={len(self._toasts)})"

    # -- the lifecycle -------------------------------------------------------

    def show(
        self,
        content: str | Component,
        *,
        style: Style | None = None,
        ttl: float | None = None,
    ) -> None:
        """Show a toast: ``content`` is a string (wrapped in a Text) or any
        Component.

        ``style`` is the toast's own band style (it wins over the
        controller's) and ``ttl`` its lifetime in seconds (``None`` keeps
        the controller's).  The expiry is stamped from ``tui._clock()`` at
        the show, a show past ``max_shown`` evicts the oldest toasts, the
        one expiry ticker arms on the first show, and the frame is
        invalidated so the pump paints the new stack.  A detached
        controller stays detached: the show is a no-op.
        """
        if self._detached:
            return
        component = Text(content) if isinstance(content, str) else content
        expires_at = self._tui._clock() + (self._ttl if ttl is None else ttl)
        self._toasts.append(_Toast(component, style, expires_at))
        overflow = len(self._toasts) - self._max_shown
        if overflow > 0:
            del self._toasts[:overflow]
        self._tui.invalidate()
        if self._handle is None:
            self._handle = self._tui.every(EXPIRY_TICK, self._tick)

    def detach(self) -> None:
        """Unregister the overlay and cancel the ticker (the EveryHandle
        convention).

        The symmetric of the constructor's registration: the frame drops
        the controller from its overlay registry
        (:meth:`~mocode_tui.core.frame.Frame.remove_overlay`, the chrome
        unregister's mirror), the stack empties, the ticker cancels, and
        the next composition paints as if no toast ever showed.
        ``detach`` is idempotent.
        """
        self._detached = True
        self._cancel()
        self._toasts = []
        # The documented frame seam (module docstring); the identity check
        # keeps a second detach a no-op instead of a ValueError.
        if any(held is self for held in self._tui.frame.overlays):
            self._tui.frame.remove_overlay(self)

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Key | Paste | MouseEvent) -> bool:
        """Dismiss the toast under the pointer; ``True`` when one was
        dismissed.

        The consume-a-key contract, at the dispatch position the module
        docstring gives overlays: after chrome, before the content
        gestures.  A left press inside any live toast's rectangle -- the
        geometry :func:`_stack` derives, the same one the paint splices
        through -- drops that toast and is consumed, so the gesture never
        anchors a selection under the band and the host never dispatches a
        click on the text beneath it.  Every other event passes through
        untouched, a press outside every toast included.
        """
        if self._detached or not self._toasts:
            return False
        if not isinstance(event, MouseEvent) or event.name != "left":
            return False
        if event.kind != "press":
            return False
        rect = self._tui.frame.rect
        if rect is None:
            return False
        for toast, band, _ in _stack(self._toasts, rect, self._corner):
            if band.x <= event.x < band.right and band.y <= event.y < band.bottom:
                self._drop(toast)
                return True
        return False

    # -- the controller -----------------------------------------------------------

    def _tick(self) -> None:
        """One expiry tick (pump callback): drop the due toasts, or stop.

        Reads ``tui._clock()`` -- the one seam time enters through -- and
        keeps the toasts whose expiry is still ahead.  A change invalidates
        the frame; a stack that emptied stands the ticker down, since a
        ticker with nothing to expire is exactly the waste the selection
        gesture's edge ticker stands down for too.
        """
        if self._detached:
            self._cancel()
            return
        now = self._tui._clock()
        kept = [toast for toast in self._toasts if toast.expires_at > now]
        if len(kept) == len(self._toasts):
            return  # nothing came due: no repaint, the ticker keeps its period
        self._toasts = kept
        self._tui.invalidate()
        if not kept:
            self._cancel()

    def _drop(self, toast: _Toast) -> None:
        """Remove one toast (the dismiss path) and stop the ticker when last."""
        self._toasts = [held for held in self._toasts if held is not toast]
        self._tui.invalidate()
        if not self._toasts:
            self._cancel()

    def _cancel(self) -> None:
        """Cancel the expiry ticker (a no-op when none is armed)."""
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None

    # -- the paint ---------------------------------------------------------------

    def paint(self, frame: Frame) -> ScreenLayout:
        """The stack over the composed frame: each live toast's band spliced
        into its rectangle.

        Pure -- the frame's rows and the live toast list are the only inputs,
        and the very layout comes back when the stack is empty (the identity
        an empty overlay registry runs on).  A detached controller hands the
        layout through the same way (the belt-and-braces guard: the
        registry no longer holds it).
        """
        layout = frame.layout
        rect = frame.rect
        if self._detached or rect is None or not self._toasts:
            return layout
        rows = list(layout.rows)
        for toast, band, rendered in _stack(self._toasts, rect, self._corner):
            style = self._resolve_band(toast.style)
            for index, row in enumerate(rendered):
                target = band.y + index
                if not 0 <= target < len(rows):
                    continue  # clipped at the frame's far edge
                rows[target] = _splice_band(
                    rows[target],
                    _band_row(row, band.width, style),
                    band.x,
                    band.width,
                    rect.width,
                )
        return replace(layout, rows=rows)

    def _resolve_band(self, style: Style | None) -> Style:
        """The band's style: a toast's own > the controller's > theme > DEFAULT."""
        if style is not None:
            return style
        if self._style is not None:
            return self._style
        theme = self._theme if self._theme is not None else DEFAULT_THEME
        return theme.toast
