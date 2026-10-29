"""The mutable sub-cell raster and its drawing verbs.

A ``Raster`` owns parallel slot and heat byte grids over ``cols*2 x rows*4``
sub-cells.  Drawing sets slot+full heat, ``decay`` cools in one translate,
and the quantizer reads ``(slot, heat)``.  Grids are private; ``at`` and
``grids`` are the read doors.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from functools import lru_cache

__all__ = ["Raster"]

type Point = tuple[float, float]


@lru_cache(maxsize=256)
def _heat_step(amount: int) -> bytes:
    """A 256-entry map subtracting ``amount`` from every heat value."""
    return bytes(value - amount if value > amount else 0 for value in range(256))


class Raster:
    """A ``cols x rows`` cell grid of ``cols*2 x rows*4`` sub-cells.

    Fractions truncate, out-of-range writes clip, slots are ``1..255`` and
    heat clamps to ``0..255``.
    """

    __slots__ = ("_heat", "_slot", "cols", "height", "rows", "width")

    def __init__(self, cols: int, rows: int) -> None:
        if cols < 0 or rows < 0:
            raise ValueError(f"raster size must be non-negative, got {cols}x{rows}")
        self.cols = cols
        self.rows = rows
        self.width = cols * 2
        self.height = rows * 4
        size = self.width * self.height
        self._slot = bytearray(size)
        self._heat = bytearray(size)

    # -- the read door -----------------------------------------------------

    def at(self, x: float, y: float) -> tuple[int, int]:
        """The ``(slot, heat)`` at a sub-cell; out of range answers ``(0, 0)``."""
        ix, iy = int(x), int(y)
        if not 0 <= ix < self.width or not 0 <= iy < self.height:
            return (0, 0)
        index = iy * self.width + ix
        return (self._slot[index], self._heat[index])

    def grids(self) -> tuple[memoryview, memoryview]:
        """Read-only ``(slot, heat)`` views for the quantizer; cheap wrappers."""
        return (memoryview(self._slot).toreadonly(), memoryview(self._heat).toreadonly())

    # -- the verbs ---------------------------------------------------------

    def clear(self) -> None:
        """Every sub-cell's slot and heat to zero, in place."""
        self._slot[:] = bytes(len(self._slot))
        self._heat[:] = bytes(len(self._heat))

    def decay(self, amount: int) -> None:
        """Subtract ``amount`` from every heat value in place through one cached translate."""
        if amount <= 0:
            return
        amount = min(255, amount)
        self._heat[:] = self._heat.translate(_heat_step(amount))

    def plot(self, x: float, y: float, slot: int = 1, heat: int = 255) -> None:
        """Ink one sub-cell in ``slot`` at ``heat``."""
        slot = self._check_slot(slot)
        heat = _clamp_heat(heat)
        self._ink(int(x), int(y), slot, heat)

    def erase(self, x: float, y: float) -> None:
        """Blank one sub-cell."""
        self._erase(int(x), int(y))

    def stamp(self, points: Iterable[Point], slot: int = 1, heat: int = 255) -> None:
        """Ink a batch of sub-cell points with one slot and one heat."""
        slot = self._check_slot(slot)
        heat = _clamp_heat(heat)
        for x, y in points:
            self._ink(int(x), int(y), slot, heat)

    def line(
        self, x0: float, y0: float, x1: float, y1: float, slot: int = 1, heat: int = 255
    ) -> None:
        """Bresenham line between two sub-cell points."""
        slot = self._check_slot(slot)
        heat = _clamp_heat(heat)
        ix0, iy0, ix1, iy1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(ix1 - ix0), -abs(iy1 - iy0)
        sx = 1 if ix0 < ix1 else -1
        sy = 1 if iy0 < iy1 else -1
        err = dx + dy
        while True:
            self._ink(ix0, iy0, slot, heat)
            if ix0 == ix1 and iy0 == iy1:
                return
            step = 2 * err
            if step >= dy:
                err += dy
                ix0 += sx
            if step <= dx:
                err += dx
                iy0 += sy

    def rect(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        fill: bool = False,
        slot: int = 1,
        heat: int = 255,
    ) -> None:
        """Axis-aligned rectangle; outline by default, every cell when filled."""
        slot = self._check_slot(slot)
        heat = _clamp_heat(heat)
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        left, right = max(0, x0), min(self.width - 1, x1)
        top, bottom = max(0, y0), min(self.height - 1, y1)
        if left > right or top > bottom:
            return
        if fill:
            for y in range(top, bottom + 1):
                self._fill_span(y, left, right, slot, heat)
            return
        for x in range(left, right + 1):
            self._ink(x, top, slot, heat)
            self._ink(x, bottom, slot, heat)
        for y in range(top + 1, bottom):
            self._ink(left, y, slot, heat)
            self._ink(right, y, slot, heat)

    def disc(
        self, cx: float, cy: float, r: float, slot: int = 1, heat: int = 255
    ) -> None:
        """Filled circle: one horizontal span per sub-row."""
        slot = self._check_slot(slot)
        heat = _clamp_heat(heat)
        if r <= 0:
            self._ink(int(cx), int(cy), slot, heat)
            return
        top, bottom = max(0, int(cy - r)), min(self.height - 1, int(cy + r))
        for y in range(top, bottom + 1):
            dy = y - cy
            span = r * r - dy * dy
            if span < 0:
                continue
            half = math.sqrt(span)
            left, right = max(0, int(cx - half)), min(self.width - 1, int(cx + half))
            if left <= right:
                self._fill_span(y, left, right, slot, heat)

    def ring(
        self,
        cx: float,
        cy: float,
        r: float,
        thickness: int = 1,
        slot: int = 1,
        heat: int = 255,
    ) -> None:
        """Circle outline of ``thickness`` sub-cells, parametric."""
        slot = self._check_slot(slot)
        heat = _clamp_heat(heat)
        if r <= 0:
            return
        steps = max(32, int(2 * math.pi * r * 2))
        for index in range(steps):
            angle = 2 * math.pi * index / steps
            cos, sin = math.cos(angle), math.sin(angle)
            for offset in range(thickness):
                radius = r + offset - (thickness - 1) / 2
                self._ink(int(cx + radius * cos), int(cy + radius * sin), slot, heat)

    # -- internals ---------------------------------------------------------

    def _check_slot(self, slot: int) -> int:
        if not 1 <= slot <= 255:
            raise ValueError(f"slot must be 1..255, got {slot}")
        return slot

    def _ink(self, x: int, y: int, slot: int, heat: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self._slot[index] = slot
            self._heat[index] = heat

    def _erase(self, x: int, y: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = y * self.width + x
            self._slot[index] = 0
            self._heat[index] = 0

    def _fill_span(self, y: int, left: int, right: int, slot: int, heat: int) -> None:
        base = y * self.width
        count = right - left + 1
        self._slot[base + left : base + right + 1] = bytes([slot]) * count
        self._heat[base + left : base + right + 1] = bytes([heat]) * count

    def __repr__(self) -> str:
        return f"Raster({self.cols}x{self.rows})"


def _clamp_heat(heat: int) -> int:
    return 0 if heat < 0 else 255 if heat > 255 else heat
