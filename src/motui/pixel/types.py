"""Shared pixel values: colors, markers, layers and the raster constants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .raster import Raster

__all__ = [
    "BRAILLE_BITS",
    "COOL_AT",
    "HALF_BOTTOM",
    "HALF_FULL",
    "HALF_TOP",
    "HEAT_LIT",
    "RGB",
    "Marker",
    "PixelLayer",
    "SlotColors",
]

#: One display color as an RGB triple.
RGB = tuple[int, int, int]

#: A slot's ``(main, cool)`` color pair.
SlotColors = tuple[RGB, RGB]


class Marker(StrEnum):
    """The glyph family a raster layer quantizes to.

    ``HALF`` folds four sub-rows into two half blocks; ``BRAILLE`` spends
    eight dots.  A new marker is a member, not a new quantizer.
    """

    HALF = "half"
    BRAILLE = "braille"


@dataclass(frozen=True, slots=True)
class PixelLayer:
    """One raster and the marker family it quantizes to."""

    raster: Raster
    marker: Marker


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
HEAT_LIT = 128

#: Fresh ink (heat at or above this) quantizes to the slot's main color;
#: cooler ink quantizes to the slot's cool color -- the cooling trail look.
COOL_AT = 192
