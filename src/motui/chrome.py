"""chrome: the pane chrome and the frame overlays -- Scrollbar, Toasts, the
Tooltip, and the dev Stats box.

This module is the assembly tier, the peer of :mod:`motui.interaction.gesture`
and :mod:`motui.app`: it imports the driver and the kernel, and
nothing below it imports it.  Everything here is *policy* -- what a
scrollbar looks like, how far its thumb travels, what a click on its track
means -- over mechanisms the kernel owns: the pane's chrome budget
(:meth:`~motui.kernel.frame.Pane.add_chrome`), the scroll state a
layout carries (:attr:`~motui.kernel.viewport.ScreenLayout.offset` /
``total_rows``), and the pump's :meth:`~motui.app.TUI.every` handles.

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

:class:`Tooltip` is the pointer's own overlay (D9): a one-row hint band
painted beside the cell the :class:`~motui.interaction.pointer.Pointer` last
hovered, read from the hovered leaf's ``hint`` attribute.  Constructing one
registers the overlay; ``detach()`` unregisters it.  Its paint is a pure
function of the pointer's live state and the frame's rows, and an untriggered
paint -- no pointer, no ``hint`` -- hands the layout back unchanged: the
zero-byte case.

:class:`Stats` is the developer's overlay (D14): a small band stack in the
frame's top-right corner reading ``painter.frames``, the frame rate over
its last window (``tui.clock()`` -- the session's own sample rule, no new
timing mechanism), the events the host fed through :meth:`Stats.handle` and
the last one's name, and the leaf the pointer hovers with the cell it last
moved over.  Same registration contract as the tooltip: constructed
mounted, ``detach()`` unmounts.

:class:`_Separator` is the split's divider: the 1-cell band
:meth:`~motui.app.TUI.split` registers on the pane before each gap,
reading the driver's :attr:`~motui.app.TUI.theme` -- ``accent`` beside
the focused pane, ``border`` otherwise.  It is the one divider
implementation; the kernel keeps the mark it registers under and the
geometry that budgets it, and a close tears it down by that mark.

**The dispatch order** is the one rule :mod:`motui.app`'s module
docstring writes out: a host routes an event through the chrome first, then
the overlays, then the content gestures, then its own dispatch.  It is
geometric here -- the bar's strip and a toast's band are derived from the
frame's rectangles, while the frame's ownership table resolves their cells
as content, so each controller must see the event before any hit test runs,
or a press would anchor a selection under the band.  One fact of the order
lives here: a wheel report never reaches :meth:`Scrollbar.handle` because
:meth:`~motui.app.TUI.read_key` intercepts
:attr:`~motui.app.TUI.scroll_keys` before the host loop runs.

Two seams this module reads rather than owns, both documented where they
live: the driver's **frame**, through its public
:attr:`~motui.app.TUI.frame` property -- the tiling, its focus, its
overlay registry and each pane's last layout -- and the driver's **pump**,
through the public :meth:`~motui.app.TUI.every` handle the
track-repeat and expiry tickers ride.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, NamedTuple

from .app import EveryHandle, TUI
from .kernel.block import Component
from .kernel.events import Key, MouseEvent, Paste
from .kernel.frame import Chrome, Frame, Pane, Rect, SEPARATOR_CHROME_NAME, splice_row
from .kernel.lines import Line, overlay
from .kernel.style import Style
from .kernel.lines import Text
from .kernel.theme import DEFAULT_THEME, Theme, Themed
from .kernel.viewport import ScreenLayout

if TYPE_CHECKING:
    from .interaction.pointer import Pointer

__all__ = ["Scrollbar", "Stats", "Toasts", "Tooltip"]

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
    <motui.kernel.theme.DEFAULT_THEME>` field -- so
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
    :class:`~motui.kernel.frame.Chrome` protocol asks for.

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

    def __repr__(self) -> str:
        return f"Scrollbar(pane={self._pane_id!r}, size={self._size})"

    # -- the event contract --------------------------------------------------------

    def handle(self, event: Key | Paste) -> bool:
        """Advance the bar with ``event``; ``True`` when the bar consumed it.

        The consume-a-key contract
        (:meth:`~motui.widgets.input.Input.handle` /
        :meth:`~motui.widgets.editor.Editor.handle` /
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
    :data:`DEFAULT_THEME <motui.kernel.theme.DEFAULT_THEME>`).
    ``expires_at`` is a ``tui.clock()`` reading taken when the toast was
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

    The colored-vs-attribute rule of :func:`~motui.kernel.lines.overlay`
    -- the band paints underneath, a segment carrying a color of its own
    keeps it and an attribute-only one shows the band through -- then the
    row is filled out to ``width`` with
    :meth:`~motui.kernel.lines.Line.filled`, the band primitive, so a
    blank content row reads as a solid band row.
    """
    content = Line(overlay(band, row.segments))
    return content + Line.filled(width - row.width, band)


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
    <motui.kernel.theme.DEFAULT_THEME>` -- so ``Theme(toast=...)``
    restyles every band and an explicit style wins over both.  The ticker's
    period is the module's :data:`EXPIRY_TICK`; a toast's last frame needs
    no finer resolution than that.

    Constructing the controller registers the overlay on the frame, where
    it stays for the frame's life -- a retile rewrites the pane rectangles
    in place rather than rebuilding the frame, and the driver's own
    selection overlay rides the same registry.  A toast is shown with
    :meth:`show`
    -- a plain string (wrapped in a :class:`~motui.kernel.text.Text`)
    or any Component, the customizability charter, so a toast can be a
    Notice, a Spinner or a host's own renderable.  ``detach()`` drops the
    stack, unregisters the overlay and cancels the ticker.

    **The paint** is the pure half: the frame's rows and the live toast
    list are its only inputs.  Each toast renders at the clamp ceiling,
    takes a :meth:`~motui.kernel.lines.Line.filled` band as wide as its
    widest row, and is spliced into the frame rows at its corner
    rectangle; an empty stack hands the layout back unchanged.  **The
    controller** owns everything time- and input-shaped: one ``tui.every``
    ticker checks expiry against ``tui.clock()`` and drops the due toasts,
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
        the controller's).  The expiry is stamped from ``tui.clock()`` at
        the show, a show past ``max_shown`` evicts the oldest toasts, the
        one expiry ticker arms on the first show, and the frame is
        invalidated so the pump paints the new stack.  A detached
        controller stays detached: the show is a no-op.
        """
        if self._detached:
            return
        component = Text(content) if isinstance(content, str) else content
        expires_at = self._tui.clock() + (self._ttl if ttl is None else ttl)
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
        (:meth:`~motui.kernel.frame.Frame.remove_overlay`, the chrome
        unregister's mirror), the stack empties, the ticker cancels, and
        the next composition paints as if no toast ever showed.
        ``detach`` is idempotent: :attr:`_detached` is the one identity
        that makes it so -- a second detach returns before it could claim
        an unregister the registry no longer owes -- and :meth:`show` reads
        the same flag, so a detached controller stays detached.
        """
        if self._detached:
            return
        self._detached = True
        self._cancel()
        self._toasts = []
        self._tui.frame.remove_overlay(self)

    # -- the event contract -----------------------------------------------------

    def handle(self, event: Key | Paste) -> bool:
        """Dismiss the toast under the pointer; ``True`` when one was
        dismissed.

        The consume-a-key contract
        (:meth:`~motui.widgets.input.Input.handle` /
        :meth:`~motui.widgets.editor.Editor.handle` /
        :meth:`~motui.interaction.gesture.SelectionGesture.handle`), at the dispatch
        position the module docstring gives overlays: after chrome, before the
        content gestures.  A left press inside any live toast's rectangle --
        the geometry :func:`_stack` derives, the same one the paint splices
        through -- drops that toast and is consumed, so the gesture never
        anchors a selection under the band and the host never dispatches a
        click on the text beneath it.  Every other event passes through
        untouched, a press outside every toast included; a detached
        controller's stack is empty, so it dismisses nothing.
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

        Reads ``tui.clock()`` -- the one seam time enters through -- and
        keeps the toasts whose expiry is still ahead.  A change invalidates
        the frame; a stack that emptied stands the ticker down, since a
        ticker with nothing to expire is exactly the waste the selection
        gesture's edge ticker stands down for too.
        """
        if self._detached:
            self._cancel()
            return
        now = self._tui.clock()
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
        an empty overlay registry runs on).  A detached controller is never
        painted: :meth:`detach` unregisters it, and the registry is what
        calls this.
        """
        layout = frame.layout
        rect = frame.rect
        if rect is None or not self._toasts:
            return layout
        rows = list(layout.rows)
        for toast, band, rendered in _stack(self._toasts, rect, self._corner):
            style = self._resolve_band(toast.style)
            for index, row in enumerate(rendered):
                target = band.y + index
                if not 0 <= target < len(rows):
                    continue  # clipped at the frame's far edge
                rows[target] = splice_row(
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


class Tooltip(Themed):
    """A one-row hint band beside the pointer, driven by the leaf's ``hint``.

    ``tui`` is the driver whose frame the overlay registers on; ``pointer``
    the :class:`~motui.interaction.pointer.Pointer` whose tracked cell and hovered
    leaf the band reads.  ``theme`` is the style source: the band paints with
    the theme's :attr:`~motui.kernel.theme.Theme.toast`, the same band the
    toasts use, so ``Theme(toast=...)`` restyles both at once.

    Constructing the controller registers the overlay on the frame, where it
    stays for the frame's life (the :class:`Toasts` shape: a retile rewrites
    the pane rectangles in place, and the driver's own selection overlay rides
    the same registry); ``detach()`` unregisters it by identity and is
    idempotent.

    **The paint is the whole controller.**  It reads live state -- the
    pointer's last button-free motion (``pointer.position``) and the leaf it
    hovers (``pointer.hovered``) -- plus that leaf's ``hint`` attribute
    (``getattr``; only a non-empty :class:`str` counts).  A pointer that never
    moved, a leaf without a hint, or a frame too narrow to host one column
    hands the layout back unchanged, which is the zero-byte case.  Otherwise
    the band is one row high and as wide as the hint, fit to the frame, and
    it paints **under** the pointer's cell -- flipping above it on the last
    row, clamped into the frame on both axes.  Nothing is cached and no event
    is consumed: a leaf that changes its ``hint``, or a pointer that moves to
    another leaf, shows on the next composition (the host's repaint cue is
    the pointer's own answer), and the tooltip has no ``handle`` because it
    owns no input.
    """

    __slots__ = ("_detached", "_pointer", "_tui")

    def __init__(
        self,
        tui: TUI,
        pointer: Pointer,
        *,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self._tui = tui
        self._pointer = pointer
        self._detached = False
        # The driver's frame seam: the overlay registers here for the frame's
        # life, exactly as the toasts' controller does.
        tui.frame.add_overlay(self)

    def __repr__(self) -> str:
        return f"Tooltip(hovered={self._pointer.hovered!r}, detached={self._detached})"

    # -- the lifecycle -------------------------------------------------------

    def detach(self) -> None:
        """Unregister the overlay (the ``EveryHandle`` convention).

        The symmetric of the constructor's registration: the frame drops the
        controller from its overlay registry, and the next composition paints
        as if no tooltip were ever mounted.  Idempotent -- :attr:`_detached`
        is the one identity that makes it so, so a second detach never claims
        an unregister the registry no longer owes.
        """
        if self._detached:
            return
        self._detached = True
        self._tui.frame.remove_overlay(self)

    # -- the paint -----------------------------------------------------------

    def paint(self, frame: Frame) -> ScreenLayout:
        """The hint band over the composed frame; the layout itself when idle.

        Pure: the frame's rows, its rectangle and the pointer's live state are
        the only inputs, and the very layout comes back when there is nothing
        to show.  A detached controller is never painted: :meth:`detach`
        unregisters it, and the registry is what calls this.
        """
        layout = frame.layout
        rect = frame.rect
        position = self._pointer.position
        hovered = self._pointer.hovered
        hint = getattr(hovered, "hint", None) if hovered is not None else None
        if rect is None or position is None or not isinstance(hint, str) or not hint:
            return layout  # no pointer, no hint: zero bytes
        row = Line.from_text(hint).fit(rect.width)
        width = row.width
        if width <= 0:
            return layout  # a frame with no column to host the band
        x, y = _tip_origin(position, width, rect)
        rows = list(layout.rows)
        if not 0 <= y < len(rows):
            return layout  # a frame whose rectangle lies outside the rows
        rows[y] = splice_row(
            rows[y], _band_row(row, width, self._theme.toast), x, width, rect.width
        )
        return replace(layout, rows=rows)


def _tip_origin(pointer: tuple[int, int], width: int, rect: Rect) -> tuple[int, int]:
    """Where a one-row band of ``width`` sits for a pointer at ``pointer``.

    Pure arithmetic over the frame's rectangle: the band goes on the row
    **under** the pointer's cell when the frame has one, flips above it on the
    last row, and both coordinates are clamped into ``rect`` -- the geometry
    the paint splices through, so a tip can never paint outside the frame.  A
    one-row frame has neither room below nor above: the band lands on the
    pointer's own row, clamped.
    """
    x, y = pointer
    x = min(max(x, rect.x), max(rect.x, rect.right - width))
    if y + 1 < rect.bottom:
        return x, y + 1
    if y - 1 >= rect.y:
        return x, y - 1
    return x, min(max(y, rect.y), rect.bottom - 1)


class Stats(Themed):
    """The dev overlay: frames, the frame rate, events, the last key, the hover.

    ``Stats(tui, *, pointer=None, theme=None)`` is the readout a developer
    mounts while building a session (D14) -- the gallery toggles it with
    ``c-g``.  It paints a small band stack in the frame's **top-right
    corner**, three rows wide as their content:

    * ``frames``: :attr:`~motui.kernel.painter.Painter.frames`, every
      painted frame (read at composition time, so the frame being painted
      is not counted yet), beside the frame rate;
    * the **frame rate** over the last window of at least a second -- the
      session's own sample rule (``gallery.session``'s ``_fps_tick``), read
      off ``tui.clock()`` and the same frame counter and taken once per
      window of at least a second, because a rate off a 10 ms window is
      noise.  No timer is armed: both readings are existing fields;
    * ``events``: how many events the host fed through :meth:`handle`, and
      the last one's name (``paste`` for a paste, which carries none);
    * ``hover``: the hovered leaf's class name and the pointer's last
      button-free motion, ``--`` while the pointer hovers nothing.

    Constructing the controller registers the overlay on the frame (where
    it stays for the frame's life, the :class:`Tooltip` rule); ``detach()``
    unregisters it and is idempotent -- the gallery's ``c-g`` is one
    construction per mount and one detach per unmount.  ``pointer`` is the
    tier whose live state the box reads and it is a plain attribute on
    purpose: a host that rebuilds its pointer (the gallery does, per page)
    points the overlay at the new one.  ``theme`` is the band's style
    source -- the box paints with the theme's :attr:`Theme.toast`, the band
    toasts and the tooltip share, so one theme field restyles all three --
    and :meth:`set_theme` follows a re-skin.

    **The host feeds every event.**  :meth:`handle` counts one event and
    answers ``True`` as a **repaint cue** (the :class:`~motui.interaction.pointer.Pointer`
    reading): the overlay consumes nothing, so route it beside the other
    tiers -- never in a ``consumed`` chain -- and repaint when it answers.
    The paint itself is otherwise pure: the frame's rows, its rectangle and
    the controller's readings are the only inputs, and a frame with no room
    for the box hands the layout back unchanged (the zero-byte case).
    """

    __slots__ = (
        "_detached",
        "_events",
        "_fps",
        "_last",
        "_sample_at",
        "_sample_frames",
        "_tui",
        "pointer",
    )

    #: The shortest window a frame-rate reading may cover, in seconds: the
    #: reading is taken at paint time, once the window has grown this wide.
    SAMPLE_WINDOW = 1.0

    def __init__(
        self,
        tui: TUI,
        *,
        pointer: Pointer | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(theme)
        self._tui = tui
        self.pointer = pointer
        self._detached = False
        self._events = 0
        self._last = ""
        self._fps = 0.0
        self._sample_frames = tui.painter.frames
        self._sample_at = tui.clock()
        # The driver's frame seam: the overlay registers here for the frame's
        # life, exactly as the tooltip's controller does.
        tui.frame.add_overlay(self)

    def __repr__(self) -> str:
        return (
            f"Stats(frames={self._tui.painter.frames}, fps={self._fps:.1f}, "
            f"events={self._events}, detached={self._detached})"
        )

    # -- the readings ------------------------------------------------------

    @property
    def events(self) -> int:
        """How many events :meth:`handle` has counted."""
        return self._events

    @property
    def last(self) -> str:
        """The last counted event's name (``""`` before the first, ``paste``
        for a paste)."""
        return self._last

    @property
    def fps(self) -> float:
        """The frame rate of the last sampled window (``0.0`` until one is)."""
        return self._fps

    # -- the lifecycle -------------------------------------------------------

    def detach(self) -> None:
        """Unregister the overlay (the ``EveryHandle`` convention).

        The symmetric of the constructor's registration; idempotent --
        :attr:`_detached` is the one identity that makes it so, so a second
        detach never claims an unregister the registry no longer owes.
        """
        if self._detached:
            return
        self._detached = True
        self._tui.frame.remove_overlay(self)

    def set_theme(self, theme: Theme) -> None:
        """Repaint the box on ``theme`` (the :class:`Find` tier's re-skin road).

        Only the band is themed and it is resolved at paint time, so this is
        the stored theme, one line -- the registration rides untouched.
        """
        self._theme = theme

    # -- the event contract --------------------------------------------------

    def handle(self, event: Key | Paste) -> bool:
        """Count ``event``; ``True`` is a repaint cue, not a dispatch claim.

        The host feeds every event of its round through here -- the box's
        counters are its own, the driver keeps none.  Every event counts,
        whatever its tier: a key, a paste, a mouse report.  ``True`` always
        (the count moved), read the way the pointer's answer is read::

            if stats.handle(event):
                tui.invalidate()
        """
        self._events += 1
        self._last = "paste" if isinstance(event, Paste) else event.name
        return True

    # -- the paint -----------------------------------------------------------

    def _lines(self) -> list[str]:
        """The box's rows, read off the live state (four readings, three rows)."""
        lines = [
            f"frames {self._tui.painter.frames}  {self._fps:5.1f} fps",
            f"events {self._events}  last {self._last or '--'}",
        ]
        pointer = self.pointer
        hovered = None if pointer is None else pointer.hovered
        position = None if pointer is None else pointer.position
        if hovered is None or position is None:
            lines.append("hover --")
        else:
            lines.append(f"hover {type(hovered).__name__} ({position[0]}, {position[1]})")
        return lines

    def _sample(self) -> None:
        """Take a frame-rate reading when the window is at least a second wide.

        The session's own rule (``gallery.session``'s ``_fps_tick``):
        frames since the window opened over the wall time since then.  The
        window only narrows on a reading, so the number a frame shows is the
        rate over a real second of painting.
        """
        now, frames = self._tui.clock(), self._tui.painter.frames
        elapsed = now - self._sample_at
        if elapsed < self.SAMPLE_WINDOW:
            return
        self._fps = (frames - self._sample_frames) / elapsed
        self._sample_frames, self._sample_at = frames, now

    def paint(self, frame: Frame) -> ScreenLayout:
        """The box in the frame's top-right corner; the layout when there is none.

        The band stack is as wide as its widest row and pinned to the
        frame's right edge (top-right: ``x = rect.right - width``), each row
        filled to that width with the theme's ``toast`` band -- the same
        band primitive the toasts and the tooltip paint with.  A frame too
        narrow for one column, or a rectangle outside the composed rows,
        hands the layout back unchanged.  A detached controller is never
        painted: :meth:`detach` unregisters it, and the registry is what
        calls this.
        """
        layout = frame.layout
        rect = frame.rect
        if rect is None or rect.width <= 0 or rect.height <= 0:
            return layout
        self._sample()  # the one write, and it only reads the clock and the counter
        rows = [Line.from_text(text).fit(rect.width) for text in self._lines()]
        width = min(max((row.width for row in rows), default=0), rect.width)
        if width <= 0:
            return layout
        band = self._theme.toast
        out = list(layout.rows)
        x = rect.right - width
        for index, row in enumerate(rows):
            y = rect.y + index
            if not 0 <= y < len(out):
                break  # a frame whose rectangle lies outside the rows
            out[y] = splice_row(out[y], _band_row(row, width, band), x, width, rect.width)
        return replace(layout, rows=out)


class _Separator:
    """The 1-cell divider between two split panes: chrome, themed by focus.

    The tmux convention (D4): the divider cell belongs to the pane before
    it -- registered as that pane's right-edge (vertical split) or
    bottom-edge (horizontal) chrome, so it is budgeted, never a gap -- and
    it reads in the driver's :attr:`~motui.app.TUI.theme`: ``accent``
    while either pane it divides is the focused one, ``border`` otherwise.
    The style is read at paint time from the frame's focus and the driver's
    theme, so one chrome object serves every focus change and follows a
    re-themed driver, and it rides a retile without re-registration.  The
    chrome registers under
    :data:`~motui.kernel.frame.SEPARATOR_CHROME_NAME`, the mark a
    :meth:`~motui.kernel.frame.Pane.close` strips it by when the
    adjacency it divides goes.  :meth:`~motui.app.TUI.split` is the
    one registration path -- this is the driver's divider, the kernel keeps
    the mark and the geometry -- and a host wanting a different look
    registers its own chrome on the pane instead (``split(separator=False)``,
    then ``pane.add_chrome(...)``).
    """

    __slots__ = ("_after_id", "_before_id", "chrome", "_tui")

    def __init__(self, tui: TUI, before_id: str, after_id: str, edge: str) -> None:
        self._tui = tui
        self._before_id = before_id
        self._after_id = after_id
        self.chrome = Chrome(edge, 1, self._paint, name=SEPARATOR_CHROME_NAME)

    def _accent(self) -> bool:
        """Whether either pane this divider separates is the focused one."""
        focused = self._tui.frame.focused_pane
        return focused is not None and focused.id in (self._before_id, self._after_id)

    def _paint(self, layout: ScreenLayout, length: int) -> list[Line]:
        """The strip: one accent or border cell per cell of the pane's edge.

        Edge-aware the way the paint protocol needs: a left/right divider is
        the pane's height in one-column rows, a bottom one one row of the
        pane's width -- either way the strip fills its band's own cells, so a
        horizontal split's divider never paints a one-column row over the
        content it was budgeted beside.
        """
        style = self._resolve()
        if self.chrome.edge in ("left", "right"):
            return [Line.filled(1, style) for _ in range(length)]
        return [Line.filled(length, style)]

    def _resolve(self) -> Style:
        """The cell's style: the driver's theme accent beside focus, else its border."""
        theme = self._tui.theme
        return theme.accent if self._accent() else theme.border

    def __repr__(self) -> str:
        return f"_Separator({self._before_id!r}|{self._after_id!r})"
