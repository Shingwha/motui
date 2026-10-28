"""The pixel core: sub-cell rasters quantized into row-model lines.

A terminal paints characters, so "pixels" are simulated: one :class:`Raster`
holds a ``cols*2 x rows*4`` sub-cell grid (braille geometry, roughly square
on a typical terminal font) of *slots* (which object a sub-cell belongs to)
and *heat* (how freshly it was inked).  :func:`quantize` turns one or more
rasters into :class:`~motui.kernel.cell.Line` values -- the ordinary row
model -- so pixels are just cells and nothing downstream changes.

**The two-color ceiling.**  A character cell carries exactly one glyph
shaped from a single-color template plus one SGR foreground and one
background -- so every quantized cell answers at most two colors, one ``fg``
for its ink and one ``bg`` for what is behind it.  Sub-pixel color within a
cell is a terminal fact, not a feature any quantizer can add; that ceiling
is why the raster stores slot + heat per sub-cell and the quantizer chooses
one slot color per cell (per half-cell for the ``"half"`` marker).

**Layers.**  ``quantize`` consumes a sequence of :class:`PixelLayer` values,
each a ``(raster, marker)`` pair with ``marker`` either ``"braille"`` (dot
matrices: curves, outlines, line art) or ``"half"`` (2x2 block fills: solid
shapes, washes).  A cell belongs to the **first layer in the sequence that
has ink in it** -- upper layers cover lower ones, first come first served by
layer order -- and the caller expresses any "mixed" marker by passing two
layers (a ``"half"`` fill under a ``"braille"`` line layer).  The kernel
never invents a mixed character.

This module is pure values and pure functions: no I/O, no terminal bytes,
stdlib only.  Every product is a row-model value, so pixel frames compose
with text through the ordinary :class:`~motui.kernel.cell.Surface` machinery.

Measured cost of :func:`quantize` on a 76x24 two-layer frame
(headless, CPython 3.12): see the number in :func:`quantize`'s docstring --
inside a 60 fps budget with room to spare.
"""

from __future__ import annotations

import math

__all__ = [
    "BRAILLE_BITS",
    "HALF_BOTTOM",
    "HALF_FULL",
    "HALF_TOP",
    "Raster",
]


#: Braille dot bits by ``(sub-column, sub-row)`` inside one cell, the
#: standard U+2800 encoding: dot 1 sits at the cell's top left, and the
#: column-major pairs read ``(0x01 0x04 / 0x02 0x08 ...)`` down each
#: sub-column.  The glyph for a cell is ``chr(0x2800 + OR of its lit dots)``.
BRAILLE_BITS: tuple[tuple[int, int, int, int], tuple[int, int, int, int]] = (
    (0x01, 0x02, 0x04, 0x40),
    (0x08, 0x10, 0x20, 0x80),
)

#: Upper half block (the ``"half"`` marker with only the top sub-rows lit).
HALF_TOP = "\u2580"

#: Lower half block (the ``"half"`` marker with only the bottom sub-rows lit).
HALF_BOTTOM = "\u2584"

#: Full block (the ``"half"`` marker with both sub-rows lit).
HALF_FULL = "\u2588"

#: Heat at or above which a sub-cell still counts as lit; below it the
#: sub-cell has decayed into emptiness (its slot byte is stale and ignored).
_HEAT_LIT = 128

#: Fresh ink (heat at or above this) quantizes to the slot's main color;
#: cooler ink quantizes to the slot's cool color -- the cooling trail look.
COOL_AT = 192


def _heat_step(amount: int) -> bytes:
    """A 256-entry map subtracting ``amount`` from every heat value."""
    return bytes(v - amount if v > amount else 0 for v in range(256))


class Raster:
    """A ``cols x rows`` cell grid of ``cols*2 x rows*4`` sub-cells.

    Two parallel ``bytearray`` grids, both indexed ``y * width + x`` over
    sub-cell coordinates (``width == cols * 2``, ``height == rows * 4``):

    - ``slot`` -- which object a sub-cell belongs to: ``0`` is empty,
      ``1..255`` are caller-chosen slot ids (a palette maps ids to colors).
    - ``heat`` -- freshness ``0..255``; :meth:`set` re-freshens to 255 and
      :meth:`decay` cools the whole grid in one C-speed pass.  A sub-cell
      with heat below ``_HEAT_LIT`` is dead regardless of its slot byte.

    The dual grid is what makes trails cheap: drawing is "slot now, heat
    full", decay is one translate, and the quantizer reads ``(slot, heat)``
    to pick both the owning color and how cooled it is.
    """

    __slots__ = ("cols", "heat", "height", "rows", "slot", "width")

    def __init__(self, cols: int, rows: int) -> None:
        if cols < 0 or rows < 0:
            raise ValueError(f"raster size must be non-negative, got {cols}x{rows}")
        self.cols = cols
        self.rows = rows
        self.width = cols * 2
        self.height = rows * 4
        size = self.width * self.height
        self.slot = bytearray(size)
        self.heat = bytearray(size)

    def clear(self) -> None:
        """Every sub-cell's slot and heat to zero, two C-speed fills."""
        self.slot[:] = bytes(len(self.slot))
        self.heat[:] = bytes(len(self.heat))

    def decay(self, amount: int) -> None:
        """Subtract ``amount`` from every heat value (the trail primitive).

        Slot bytes are untouched -- objects keep their identity while their
        ink cools -- and a non-positive ``amount`` does nothing.  The whole
        grid decays through one ``bytes.translate`` table, so the cost is a
        single C-speed copy, never a Python loop over sub-cells.
        """
        if amount <= 0:
            return
        self.heat = self.heat.translate(_heat_step(amount))

    def set(self, x: float, y: float, slot: int = 1) -> None:
        """Ink one sub-cell: its slot id stored, its heat reset to full.

        Coordinates are sub-cell positions; fractional values truncate.
        Out-of-range coordinates clip silently (drawing never checks).  A
        slot id of ``0`` (empty) or less does nothing -- only ``1..255``
        carry ink.
        """
        if slot <= 0:
            return
        ix, iy = int(x), int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            index = iy * self.width + ix
            self.slot[index] = slot
            self.heat[index] = 255

    # -- primitives (sub-cell coordinates, silent clipping, slot-colored) --

    def line(self, x0: float, y0: float, x1: float, y1: float, slot: int = 1) -> None:
        """Bresenham line between two sub-cell points."""
        ix0, iy0, ix1, iy1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(ix1 - ix0), -abs(iy1 - iy0)
        sx = 1 if ix0 < ix1 else -1
        sy = 1 if iy0 < iy1 else -1
        err = dx + dy
        while True:
            self.set(ix0, iy0, slot)
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
    ) -> None:
        """Axis-aligned rectangle, outline by default or filled."""
        ix0, ix1 = sorted((int(x0), int(x1)))
        iy0, iy1 = sorted((int(y0), int(y1)))
        for y in range(max(0, iy0), min(self.height - 1, iy1) + 1):
            edge = y in (iy0, iy1)
            for x in range(max(0, ix0), min(self.width - 1, ix1) + 1):
                if fill or edge or x in (ix0, ix1):
                    self.set(x, y, slot)

    def disc(self, cx: float, cy: float, r: float, slot: int = 1) -> None:
        """Filled circle: one horizontal span of sub-cells per sub-row."""
        if r <= 0:
            self.set(cx, cy, slot)
            return
        top, bottom = int(cy - r), int(cy + r)
        for y in range(top, bottom + 1):
            dy = y - cy
            span = r * r - dy * dy
            if span < 0:
                continue
            half = math.sqrt(span)
            for x in range(int(cx - half), int(cx + half) + 1):
                self.set(x, y, slot)

    def ring(self, cx: float, cy: float, r: float, thickness: int = 1, slot: int = 1) -> None:
        """Circle outline of ``thickness`` sub-cells, parametric."""
        if r <= 0:
            return
        steps = max(32, int(2 * math.pi * r * 2))
        for index in range(steps):
            angle = 2 * math.pi * index / steps
            cos, sin = math.cos(angle), math.sin(angle)
            for offset in range(thickness):
                radius = r + offset - (thickness - 1) / 2
                self.set(cx + radius * cos, cy + radius * sin, slot)
