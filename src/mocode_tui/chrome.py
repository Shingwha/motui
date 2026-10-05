"""chrome: the pane chrome -- the Scrollbar, its geometry and its gesture.

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
host dispatches through it (see :meth:`Scrollbar.handle` for the order).

Two seams this module reads rather than owns, both documented where they
live: the driver's **frame**, through its private ``tui._frame`` -- the
convention :class:`~mocode_tui.selection.SelectionGesture`'s ``_clock``
seam follows, and the frame surface a split wave exposes will replace it
-- and the driver's **pump**, through the public
:meth:`~mocode_tui.app.TUI.every` handle the track-repeat ticker rides.
"""

from __future__ import annotations

from typing import NamedTuple

from .app import TUI
from .core.frame import Chrome, Pane, Rect
from .core.lines import Line
from .core.style import Style
from .core.theme import DEFAULT_THEME, Theme
from .core.viewport import ScreenLayout

__all__ = ["Scrollbar"]

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
    a pane id, or ``None`` (the default) for the driver's primary pane --
    and an id the frame does not hold raises ``ValueError`` at
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
    """

    __slots__ = (
        "_chrome",
        "_detached",
        "_min_thumb",
        "_pane_id",
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
        # whichever pane currently holds the id, and re-registers there
        # whenever the frame is rebuilt underneath it.
        frame = tui._frame
        primary = frame.focused_pane
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

    def __repr__(self) -> str:
        return f"Scrollbar(pane={self._pane_id!r}, size={self._size})"

    # -- lifecycle ---------------------------------------------------------------

    def detach(self) -> None:
        """Unregister the chrome (the ``EveryHandle``/Composer convention).

        The stored selection of a gesture is not ours to clear; the strip
        is: the pane gives the bar's column back to its viewport, which
        re-wraps at the full width on the next composition, and nothing
        paints a track again until a bar registers afresh.
        """
        self._detached = True
        pane = self._pane()
        if pane is not None and self._chrome in pane.chrome:
            # The kernel registers chrome with its own ``object.__setattr__``
            # append (Pane.add_chrome) and lands no symmetric removal this
            # wave -- the W2 registration gap, reported for a later one --
            # so the unregister replays that append's mirror, by identity.
            object.__setattr__(
                pane,
                "chrome",
                tuple(c for c in pane.chrome if c is not self._chrome),
            )

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
        track = Line.from_text(TRACK * self._size, self._resolve_track())
        grab = Line.from_text(THUMB * self._size, self._resolve_thumb())
        return [grab if first <= index < last else track for index in range(length)]

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
        return self._tui._frame.pane(self._pane_id)

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
