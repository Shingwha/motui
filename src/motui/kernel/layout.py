"""Layout values: render constraints and the two-axis scroll geometry.

``Constraints`` is the input a component renders against.  ``ScrollAxis`` is
one axis of a scroll window as an immutable value -- the furthest legal
offset, the clamp after a layout, the minimal move that reveals a row and the
scrollbar thumb are pure functions returning a new value, so two axes can
share one implementation and a caller can never park an offset out of range.
``Scroll`` pairs the axes, with the vertical axis followed by default.

The thumb formula is copied verbatim from the 1.x ``ScrollState`` (including
the builtin ``round`` half-to-even rule).  The 1.x clamp remembers the
previous extent so a tail-following window can pin to a bottom that moved;
this wave does not carry that bookkeeping -- the ``sticky`` branch compares
the offset against this value's own extent, which is the equivalent test the
W0a work order asks for.  W2.6 restores the previous-extent behavior when
``ScrollState`` is retired.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

__all__ = ["Constraints", "Scroll", "ScrollAxis"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Constraints:
    """What a component is asked to render into.

    ``width`` is required and non-negative; ``max_height`` is ``None`` for a
    natural height or a non-negative row budget for a filled one.
    """

    width: int = 0
    max_height: int | None = None

    def __post_init__(self) -> None:
        if self.width < 0:
            raise ValueError(f"constraints width must not be negative, got {self.width}")
        if self.max_height is not None and self.max_height < 0:
            raise ValueError(
                f"constraints max_height must not be negative, got {self.max_height}"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScrollAxis:
    """One axis of a scrolling window: offset, content, viewport and follow.

    Every verb returns a new value; the receiver is never mutated.  ``sticky``
    marks the value as tail-following (the vertical axis of :class:`Scroll`
    starts sticky), so a clamp lands on the bottom rather than keeping a
    detached offset.
    """

    offset: int = 0
    content: int = 0
    viewport: int = 0
    sticky: bool = False

    @property
    def max_offset(self) -> int:
        """The furthest legal window start: the content past the window."""
        return max(0, self.content - self.viewport)

    def clamp(self) -> ScrollAxis:
        """Re-derive the offset for this extent.

        A sticky axis whose offset stood at the extent pins to the bottom;
        every other axis clamps into ``[0, max_offset]``.  With no previous
        extent stored on the value, ``max_offset`` is the equivalent test
        (see the module docstring), so the two branches coincide until W2.6.
        """
        limit = self.max_offset
        if self.sticky and self.offset >= limit:
            return replace(self, offset=limit)
        return replace(self, offset=max(0, min(self.offset, limit)))

    def reveal(self, row: int) -> ScrollAxis:
        """Bring ``row`` into the window, moving as little as possible.

        The row is clamped into the content; an already visible row (or an
        empty content or viewport) moves nothing, and the returned offset is
        clamped into the legal range.  ``sticky`` is carried through
        unchanged: revealing is an explicit move, not a tail follow.
        """
        if self.content <= 0:
            return self
        target = max(0, min(int(row), self.content - 1))
        if self.viewport <= 0:
            return self
        if target < self.offset:
            return replace(self, offset=max(0, min(target, self.max_offset)))
        if target >= self.offset + self.viewport:
            return replace(
                self,
                offset=max(0, min(target - self.viewport + 1, self.max_offset)),
            )
        return self

    def thumb(self, track: int, min_length: int = 1) -> tuple[int, int] | None:
        """The thumb's ``(start, length)`` over ``track`` cells.

        ``None`` when there is nothing to map -- the content fits the window
        (an empty document included) or ``min_length`` shaved the thumb away.
        The formula is the 1.x one, including the builtin ``round`` (half to
        even), so the geometry is reproducible rather than approximate.
        """
        if track <= 0 or self.content <= self.viewport:
            return None
        length = min(
            track,
            max(
                min_length,
                round(self.viewport * track / self.content),
            ),
        )
        if length <= 0:
            return None
        travel = max(1, track - length)
        span = max(1, self.content - self.viewport)
        start = min(travel, max(0, round(self.offset * travel / span)))
        return start, length


@dataclass(frozen=True, slots=True, kw_only=True)
class Scroll:
    """A two-axis scroll state; the vertical axis follows the tail by default."""

    x: ScrollAxis = ScrollAxis()
    y: ScrollAxis = field(default_factory=lambda: ScrollAxis(sticky=True))

    def with_x(self, axis: ScrollAxis) -> Scroll:
        """A copy of this scroll with its horizontal axis replaced."""
        return replace(self, x=axis)

    def with_y(self, axis: ScrollAxis) -> Scroll:
        """A copy of this scroll with its vertical axis replaced."""
        return replace(self, y=axis)
