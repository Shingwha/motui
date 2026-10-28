"""PixelCanvas: a sub-cell pixel stage answered as one quantized surface.

A :class:`PixelCanvas` is the pixel counterpart of
:class:`~motui.widgets.canvas.Canvas`: instead of whole cells it owns two
:class:`~motui.kernel.pixel.Raster` grids of sub-cell slots -- a ``fill``
layer of background blocks folded at half-cell resolution and an ``art``
layer of lines and sprites drawn at the marker's resolution (``"half"``, a
1x2 grid per cell, or ``"braille"``, 2x4) -- and answers :meth:`render` by
handing both to the kernel's one quantizer,
:func:`~motui.kernel.pixel.quantize`.  Every colour on the canvas comes from
the caller's :class:`~motui.kernel.pixel.PixelPalette`: the widget
contributes the layer organization, the geometry and the draw/erase/fade
verbs, and the kernel contributes the pixels-to-cells semantics.  This is
quantize's single consumer-facing door: no other component calls it.

Like the ``Canvas``, it is one of the toolkit's two components that own
mutable render state: every drawing verb mutates its rasters in place (and
touches the widget), while the surface a render answers is frozen like every
other render result.  Rendering re-quantizes from scratch -- the rasters are
public, so dirtiness is not trackable -- and syncs the buffers to the
constraint's size first: a render at a new size rebuilds them empty, which a
pixel scene refills on its next tick.

Octant resolution (filled 2x4 sub-cells, Unicode 16) is deliberately absent:
the kernel vocabulary has no octant layer and terminal support is uneven
(Windows Terminal 1.22 was the first), so the choice between braille and
octant stays an explicit configuration of the host.  A widget never probes
the terminal -- widgets import the kernel only -- so if the kernel grows an
octant layer this canvas extends its marker vocabulary and the host passes
the capability in; no width probe is issued from here.
"""

from __future__ import annotations

from ..kernel.cell import Surface
from ..kernel.layout import Constraints
from ..kernel.pixel import PixelLayer, PixelPalette, Raster, quantize
from .base import Widget

__all__ = ["PixelCanvas"]

#: The accepted art-layer markers, in increasing sub-cell resolution.  The
#: fill layer is always quantized as ``"half"``, which is what paints blank
#: cells with the palette background.
_MARKERS = ("half", "braille")


class PixelCanvas(Widget):
    """Two raster layers, fill under art, quantized through the palette.

    ``width``/``height`` are cell dimensions; every cell is a 2x4 sub-cell
    grid.  Drawing verbs take sub-cell positions on the layer they draw,
    floats truncated, out-of-range writes clipped.  ``marker`` names the art
    layer's resolution (``"half"`` or ``"braille"``); rendering at a new
    size rebuilds both rasters empty -- a pixel scene redraws every tick, so
    losing the ink is by contract, and :meth:`resize` does the same
    explicitly.
    """

    __slots__ = ("_art", "_cols", "_fill", "_rows", "marker", "palette")

    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        *,
        marker: str = "braille",
        palette: PixelPalette,
        theme=None,
        styles=None,
    ) -> None:
        super().__init__(theme, styles)
        if marker not in _MARKERS:
            raise ValueError(f"marker must be one of {_MARKERS}, got {marker!r}")
        self.marker = marker
        self.palette = palette
        self._cols = max(0, int(width))
        self._rows = max(0, int(height))
        self._art = Raster(self._cols, self._rows)
        self._fill = Raster(self._cols, self._rows)

    # -- geometry ----------------------------------------------------------

    @property
    def width(self) -> int:
        """The canvas width in cells."""
        return self._cols

    @width.setter
    def width(self, value: int) -> None:
        self._resize(max(0, int(value)), self._rows)

    @property
    def height(self) -> int:
        """The canvas height in cells."""
        return self._rows

    @height.setter
    def height(self, value: int) -> None:
        self._resize(self._cols, max(0, int(value)))

    def resize(self, width: int, height: int) -> None:
        """Resize both rasters; the sub-cells of the old size are dropped."""
        self._resize(max(0, int(width)), max(0, int(height)))

    def _resize(self, cols: int, rows: int) -> None:
        if cols == self._cols and rows == self._rows:
            return
        self._cols = cols
        self._rows = rows
        self._art = Raster(cols, rows)
        self._fill = Raster(cols, rows)
        self.touch()

    # -- the layers --------------------------------------------------------

    @property
    def art(self) -> Raster:
        """The line/sprite layer, quantized at ``marker`` resolution."""
        return self._art

    @property
    def fill(self) -> Raster:
        """The background layer, quantized as ``"half"`` (blocks and bg)."""
        return self._fill

    def _layers(self) -> tuple[PixelLayer, ...]:
        """The quantize layers in priority order: art keeps a cell both claim."""
        return ((self._art, self.marker), (self._fill, "half"))

    # -- drawing: the art layer --------------------------------------------

    def set(self, x: float, y: float, slot: int = 1) -> None:
        """Light one art sub-cell in ``slot``; its heat resets to fresh."""
        self._art.set(x, y, slot)
        self.touch()

    def unset(self, x: float, y: float) -> None:
        """Erase one art sub-cell; the kernel raster has no erase verb.

        ``Raster.set`` with ``slot <= 0`` is a no-op by contract, so erasure
        writes the documented public bytearrays directly: the grids are
        row-major (index ``y * width + x``) and ``heat`` is read fresh here
        because ``decay`` replaces the array.
        """
        raster = self._art
        xi, yi = int(x), int(y)
        if not 0 <= xi < raster.width or not 0 <= yi < raster.height:
            return
        index = yi * raster.width + xi
        raster.slot[index] = 0
        raster.heat[index] = 0
        self.touch()

    def line(
        self, x0: float, y0: float, x1: float, y1: float, slot: int = 1
    ) -> None:
        """Draw an art line from ``(x0, y0)`` to ``(x1, y1)`` in ``slot``."""
        self._art.line(x0, y0, x1, y1, slot)
        self.touch()

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
        """Draw an art rectangle; ``fill`` solidifies it."""
        self._art.rect(x0, y0, x1, y1, fill=fill, slot=slot)
        self.touch()

    def disc(self, cx: float, cy: float, r: float, slot: int = 1) -> None:
        """Draw a filled art disc of radius ``r`` at ``(cx, cy)``."""
        self._art.disc(cx, cy, r, slot)
        self.touch()

    def ring(
        self, cx: float, cy: float, r: float, thickness: int = 1, slot: int = 1
    ) -> None:
        """Draw an art ring of radius ``r`` and ``thickness`` at ``(cx, cy)``."""
        self._art.ring(cx, cy, r, thickness, slot)
        self.touch()

    def decay(self, amount: int) -> None:
        """Fade the art layer's heat by ``amount``; the fill layer never does.

        This is the trail effect: aged sub-cells quantize to the palette's
        cool colour and drop out entirely once their heat falls dark.
        """
        self._art.decay(amount)
        self.touch()

    # -- drawing: the fill layer -------------------------------------------

    def fill_set(self, x: float, y: float, slot: int = 1) -> None:
        """Light one fill sub-cell in ``slot``."""
        self._fill.set(x, y, slot)
        self.touch()

    def fill_rect(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        fill: bool = False,
        slot: int = 1,
    ) -> None:
        """Draw a fill-layer rectangle; ``fill=True`` is the usual block."""
        self._fill.rect(x0, y0, x1, y1, fill=fill, slot=slot)
        self.touch()

    def fill_disc(self, cx: float, cy: float, r: float, slot: int = 1) -> None:
        """Draw a filled fill-layer disc of radius ``r`` at ``(cx, cy)``."""
        self._fill.disc(cx, cy, r, slot)
        self.touch()

    def fill_clear(self) -> None:
        """Blank the fill layer; blank cells keep painting the bg colour."""
        self._fill.clear()
        self.touch()

    # -- the whole canvas --------------------------------------------------

    def clear(self) -> None:
        """Blank both layers; the surface is the bare bg colour again."""
        self._art.clear()
        self._fill.clear()
        self.touch()

    def render(self, c: Constraints) -> Surface:
        """The layers quantized at the constraint's size; a frozen surface.

        A natural-height constraint keeps the current row count; a budget
        resizes to exactly that many rows (rebuilding the rasters, per the
        class contract).  The surface width is the constraint's width and
        every row answers it exactly.
        """
        rows = self._rows if c.max_height is None else max(0, int(c.max_height))
        self._resize(max(0, int(c.width)), rows)
        if self._cols == 0 or self._rows == 0:
            return Surface(width=c.width, rows=())
        return Surface.of(quantize(self._layers(), self.palette), c.width)

    def __repr__(self) -> str:
        return (
            f"PixelCanvas({self._cols}x{self._rows}, marker={self.marker!r})"
        )
