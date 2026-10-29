"""Geometry values: sizes, positions and the rectangle algebra.

Frozen values; every operation returns a new rectangle. ``Axis.X`` cuts
the width, ``Axis.Y`` the height."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

__all__ = ["Axis", "Pos", "Rect", "Size"]


class Axis(Enum):
    """The axis a rectangle is divided along: ``X`` cuts width, ``Y`` cuts height."""

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
    """A rectangle of the screen: origin plus non-negative extent; the right and
    bottom edges are half-open."""

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
        """The overlap of the two rectangles, or ``Rect()`` when disjoint."""
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
        """Divide along ``axis`` into one child per weight: shares floor, the last
        takes the remainder, ``min_size`` lifts, and an overrun is clipped."""
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
