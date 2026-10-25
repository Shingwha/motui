"""Geometry values: a size, a position and the rectangle algebra.

The 2.0 kernel keeps geometry in plain frozen values: a rectangle is a
0-based origin plus a non-negative extent, and every operation hands back a
new rectangle instead of editing the one it was asked about.  The split
algebra mirrors ``core.frame.Split`` (floor shares, the last child takes the
remainder, ``min_size`` lifts, an overrun is clipped) while naming the axis
by what it divides rather than by an orientation string: ``Axis.X`` cuts the
width, ``Axis.Y`` cuts the height.  Nothing here touches the terminal or the
1.x core.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

__all__ = ["Axis", "Pos", "Rect", "Size"]


class Axis(Enum):
    """The axis a rectangle is divided along.

    ``X`` cuts the width (left/right children), ``Y`` cuts the height
    (top/bottom children).  The names say what moves, which is the opposite
    of the 1.x ``"vertical"`` orientation string.
    """

    X = "x"
    Y = "y"


@dataclass(frozen=True, slots=True, kw_only=True)
class Size:
    """A width and a height in cells; both default to zero."""

    width: int = 0
    height: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Pos:
    """A cell position: 0-based column ``x`` and row ``y``."""

    x: int = 0
    y: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Rect:
    """A rectangle of the screen: origin plus non-negative extent.

    Width and height may be zero (an empty rectangle is legal) but never
    negative.  The origin may sit anywhere; the right and bottom edges are
    half-open, so a position on them is outside the rectangle.
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(
                f"rect size must be non-negative, got {self.width}x{self.height}"
            )

    @property
    def right(self) -> int:
        """The first column past the rectangle (``x + width``)."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """The first row past the rectangle (``y + height``)."""
        return self.y + self.height

    @property
    def area(self) -> int:
        """The number of cells the rectangle covers."""
        return self.width * self.height

    def contains(self, pos: Pos) -> bool:
        """Whether ``pos`` lies inside: right and bottom are exclusive."""
        return self.x <= pos.x < self.right and self.y <= pos.y < self.bottom

    def intersect(self, other: Rect) -> Rect:
        """The overlap of the two rectangles, or ``Rect()`` when disjoint.

        The result is always contained in both operands, so the operation is
        commutative and idempotent.
        """
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        if left >= right or top >= bottom:
            return Rect()
        return Rect(x=left, y=top, width=right - left, height=bottom - top)

    def split(
        self, axis: Axis, weights: Sequence[float], min_size: int = 0
    ) -> tuple[Rect, ...]:
        """Divide this rectangle along ``axis`` into one child per weight.

        The span is the width for ``Axis.X`` and the height for ``Axis.Y``;
        the cross axis is inherited unchanged.  Each weight's share is its
        fraction of the total, floored, and the last child takes the
        remainder -- the children partition the span, so no cell is left
        unclaimed.  ``min_size`` then lifts every share to that floor, and a
        share that overruns what remains is clipped: children abut, never
        overlap, and the last ones may be empty when the floor takes more
        than the span can host.  This is the 1.x ``Split.rects`` algebra
        with ``Axis.X``/``Axis.Y`` in place of the orientation string.
        """
        if not weights:
            raise ValueError("a split needs at least one weight")
        if any(weight < 0 for weight in weights):
            raise ValueError(f"split weights must not be negative, got {weights!r}")
        total = sum(weights)
        if total <= 0:
            raise ValueError(f"split weights must share some cells, got {weights!r}")
        if min_size < 0:
            raise ValueError(f"min_size must not be negative, got {min_size!r}")

        span = self.width if axis is Axis.X else self.height
        sizes = [int(span * weight // total) for weight in weights]
        remainder = span - sum(sizes)
        if remainder:
            sizes[-1] += remainder
        if min_size:
            sizes = [max(size, min_size) for size in sizes]

        children: list[Rect] = []
        at = 0
        for size in sizes:
            taken = max(0, min(size, span - at))
            if axis is Axis.X:
                children.append(Rect(x=self.x + at, y=self.y, width=taken, height=self.height))
            else:
                children.append(Rect(x=self.x, y=self.y + at, width=self.width, height=taken))
            at += taken
        return tuple(children)
