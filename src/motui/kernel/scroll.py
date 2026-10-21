"""ScrollState: the one scroll geometry every scrolling surface shares.

A scrolling surface holds three numbers -- where its window starts, how many
rows its content has, and how many rows its window shows -- and derives
everything else from them: the furthest legal offset, the clamping rule, the
minimal move that reveals one row, and the thumb a scrollbar paints.  The
values and the arithmetic live here once; :class:`~motui.kernel.viewport.Viewport`,
``ScrollView`` and the pane chrome all fold this state into their own objects
instead of carrying a formula of their own.

``stick_to_bottom`` is the tail-follow mode: while it is set, a layout that
grew its content pins the window to the new bottom, and landing on the bottom
edge (or an explicit :meth:`ScrollState.scroll_to` there) sets it again.
Scrolling up detaches; a state that never follows the tail (the widget-level
scroll view) keeps the flag off.

:class:`Scrollable` is the narrow read/write face the scrollbar and the
driver route wheel input through: a state to read and two verbs to move it.
The pane's viewport, the scroll view and the pane itself all answer it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = ["ScrollState", "Scrollable"]


@dataclass
class ScrollState:
    """One scrolling window's geometry: offset, content and viewport rows.

    The value is mutable -- a scrolling surface owns one and moves it in
    place -- and every verb clamps into the window's own extent, so a caller
    can never park the offset outside ``[0, max_offset()]`` through this
    API.  ``stick_to_bottom`` switches the tail-follow rule on: a
    :meth:`clamp` pins to the bottom while the offset stood at the previous
    extent, which is what makes a fresh viewport show a streaming document's
    tail and a detached one stay put.
    """

    offset: int = 0
    content_height: int = 0
    viewport_height: int = 0
    stick_to_bottom: bool = False
    #: The extent the last :meth:`clamp` derived, ``None`` before one: the
    #: "old max" a stick-to-bottom clamp compares the offset against.  It is
    #: bookkeeping, not part of the value's identity.
    _extent: int | None = field(default=None, repr=False, compare=False)

    def max_offset(self) -> int:
        """The furthest legal window start: the content past the window."""
        return max(0, self.content_height - self.viewport_height)

    def clamp(self) -> bool:
        """Re-derive the offset after a layout; ``True`` when it moved.

        A stick-to-bottom state pins to the new bottom when the offset stood
        at the previous layout's extent -- or when no layout has run yet --
        so content that grew under a followed window carries it along and a
        window the user detached stays where it was.  Every other state
        clamps into ``[0, max_offset()]``.  Either way the current extent is
        remembered for the next comparison.
        """
        previous = self.offset
        limit = self.max_offset()
        at_previous_bottom = self._extent is None or previous >= self._extent
        if self.stick_to_bottom and at_previous_bottom:
            self.offset = limit
        else:
            self.offset = max(0, min(previous, limit))
        self._extent = limit
        return self.offset != previous

    def scroll_to(self, offset: int) -> bool:
        """Move the window's top to ``offset`` (clamped); ``True`` on a move.

        Landing on the bottom edge re-attaches a tail-following state; a
        target above it detaches one, exactly the driver-visible rule that
        scrolling to the tail resumes auto-follow.
        """
        target = max(0, min(int(offset), self.max_offset()))
        moved = target != self.offset
        self.offset = target
        if target >= self.max_offset():
            self.stick_to_bottom = True
        elif self.stick_to_bottom:
            self.stick_to_bottom = False
        return moved

    def scroll_by(self, delta: int) -> bool:
        """Step the window ``delta`` rows (clamped); ``True`` on a move.

        A downward step that lands on the bottom edge re-attaches the tail;
        any upward step detaches it, even when the window was already at the
        top -- the same rule the viewport's :meth:`scroll_up` follows.
        """
        if delta == 0:
            return False
        moved = self.scroll_to(self.offset + delta)
        if delta < 0:
            self.stick_to_bottom = False
        return moved

    def reveal(self, row: int) -> bool:
        """Bring ``row`` into the window, moving as little as possible.

        The row is clamped into the content; a target already visible (or a
        window showing everything) moves nothing, and an empty content or an
        empty window answers ``False``.  A target above the window parks it
        at the target; one below parks it so the target is the last visible
        row.
        """
        if self.content_height <= 0:
            return False
        target = max(0, min(int(row), self.content_height - 1))
        if self.viewport_height <= 0:
            return False
        if target < self.offset:
            return self.scroll_to(target)
        if target >= self.offset + self.viewport_height:
            return self.scroll_to(target - self.viewport_height + 1)
        return False

    def thumb(self, track_height: int, min_length: int = 1) -> tuple[int, int] | None:
        """The thumb's ``(start, length)`` over ``track_height`` cells.

        ``None`` when there is nothing to map -- the content fits the window
        (an empty document included) or ``min_length`` shaved the thumb away
        -- which a scrollbar paints as its plain track.  Otherwise::

            length = min(track, max(min_length, round(viewport * track / content)))
            travel = max(1, track - length)
            span   = max(1, content - viewport)
            start  = min(travel, max(0, round(offset * travel / span)))

        ``round`` is the builtin, so a half goes to the even integer and the
        geometry is reproducible rather than merely approximate.  This is the
        only thumb formula: the pane scrollbar and the scroll view's bar both
        call it.
        """
        if track_height <= 0 or self.content_height <= self.viewport_height:
            return None
        length = min(
            track_height,
            max(min_length, round(self.viewport_height * track_height / self.content_height)),
        )
        if length <= 0:
            return None
        travel = max(1, track_height - length)
        span = max(1, self.content_height - self.viewport_height)
        start = min(travel, max(0, round(self.offset * travel / span)))
        return start, length


@runtime_checkable
class Scrollable(Protocol):
    """Anything a scrollbar or a wheel route can read and move.

    The narrow face the interaction tier needs: the geometry to paint a
    thumb from and the two verbs to move the window.  :class:`Viewport`,
    ``ScrollView`` and ``Pane`` (delegating its viewport) answer it without
    sharing a base class.
    """

    @property
    def scroll_state(self) -> ScrollState: ...

    def scroll_to(self, offset: int) -> bool: ...

    def scroll_by(self, delta: int) -> bool: ...
