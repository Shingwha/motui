"""The optional pixel medium: sub-cell rasters quantized into cell rows.

Depends on the kernel only.  ``Raster`` is the mutable drawing surface and
``quantize`` answers ``Line`` values; ``PixelCanvas`` is the widget adapter.
A layer is a raster plus its ``Marker``, and the first layer with ink owns a
cell.
"""

from __future__ import annotations

from .palette import PixelPalette
from .quantize import quantize
from .raster import Raster
from .types import (
    BRAILLE_BITS,
    COOL_AT,
    HALF_BOTTOM,
    HALF_FULL,
    HALF_TOP,
    HEAT_LIT,
    RGB,
    Marker,
    PixelLayer,
    SlotColors,
)

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
    "PixelPalette",
    "Raster",
    "SlotColors",
    "quantize",
]
