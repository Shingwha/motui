"""The optional pixel medium: sub-cell rasters quantized into cell rows.

``motui.pixel`` depends on the kernel only.  It knows nothing about widgets,
terminals or the demo; :class:`Raster` is a mutable drawing surface, the
verbs are the only way to write it, and :func:`quantize` answers ordinary
:class:`~motui.kernel.cell.Line` values.  ``PixelCanvas`` in
:mod:`motui.widgets` is the thin widget adapter over this engine.

A layer is a :class:`PixelLayer` value -- one raster plus its
:class:`Marker` family.  A cell belongs to the first layer in the sequence
that has ink in it, so a ``"half"`` fill under a ``"braille"`` line layer
is expressed as two layers, never as a mixed marker.
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
