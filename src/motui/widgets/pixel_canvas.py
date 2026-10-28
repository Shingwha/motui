"""PixelCanvas: a sub-cell pixel stage answered as one quantized surface.

A :class:`PixelCanvas` owns two :class:`~motui.pixel.Raster` grids -- a
``fill`` layer of background blocks folded at half-cell resolution and an
``art`` layer of lines and sprites drawn at the marker's resolution -- and
answers :meth:`render` by handing both to the pixel engine's one quantizer.
Every colour comes from the caller's
:class:`~motui.pixel.PixelPalette`; the widget contributes the layer
organization, geometry and draw/erase/fade verbs, and ``motui.pixel``
contributes the pixels-to-cells semantics.

The widget is the only drawing door: the rasters are private, the verbs
take a :class:`LayerName`, and the marker is validated when assigned.  A
render re-quantizes from scratch (the widget cannot see edits made through
a private buffer) and syncs the buffers to the constraint's size first; a
render at a new size rebuilds them empty, which a pixel scene refills on
its next tick.

Octant resolution is deliberately absent: the engine's marker vocabulary
is half and braille, and the choice is an explicit host configuration.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from ..kernel.cell import Surface
from ..kernel.layout import Constraints
from ..pixel import Marker, PixelLayer, PixelPalette, Raster, quantize
from .base import Widget

__all__ = ["LayerName", "PixelCanvas"]


class LayerName(StrEnum):
    """The two layers a canvas exposes, in quantize priority order."""

    ART = "art"
    FILL = "fill"


class PixelCanvas(Widget):
    """Two private rasters, fill under art, quantized through the palette.

    ``width``/``height`` are cell dimensions; every cell is a 2x4 sub-cell
    grid.  Drawing verbs take sub-cell positions on one layer, floats
    truncated and out-of-range writes clipped.  Rendering at a new size
    rebuilds both rasters empty -- a pixel scene redraws every tick, so
    losing the ink is by contract, and :meth:`resize` does the same
    explicitly.
    """

    __slots__ = ("_art", "_cols", "_fill", "_marker", "_rows", "palette")

    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        *,
        marker: Marker | str = Marker.BRAILLE,
        palette: PixelPalette,
        theme=None,
        styles=None,
    ) -> None:
        super().__init__(theme, styles)
        self._marker = _resolve_marker(marker)
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

    @property
    def pixel_width(self) -> int:
        """The sub-cell width of both layers."""
        return self._cols * 2

    @property
    def pixel_height(self) -> int:
        """The sub-cell height of both layers."""
        return self._rows * 4

    @property
    def marker(self) -> Marker:
        """The art layer's marker family; assigning validates the value."""
        return self._marker

    @marker.setter
    def marker(self, value: Marker | str) -> None:
        resolved = _resolve_marker(value)
        if resolved is not self._marker:
            self._marker = resolved
            self.touch()

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

    def _layer(self, layer: LayerName | str) -> Raster:
        try:
            name = LayerName(layer)
        except ValueError:
            raise ValueError(
                f"layer must be one of {tuple(LayerName)}, got {layer!r}"
            ) from None
        return self._art if name is LayerName.ART else self._fill

    def _layers(self) -> tuple[PixelLayer, ...]:
        """The quantize layers in priority order: art keeps a cell both claim."""
        return (
            PixelLayer(self._art, self._marker),
            PixelLayer(self._fill, Marker.HALF),
        )

    # -- drawing -----------------------------------------------------------

    def plot(
        self,
        x: float,
        y: float,
        slot: int = 1,
        *,
        heat: int = 255,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Light one sub-cell in ``slot`` at ``heat``."""
        self._layer(layer).plot(x, y, slot, heat)
        self.touch()

    def erase(
        self,
        x: float,
        y: float,
        *,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Blank one sub-cell on ``layer``."""
        self._layer(layer).erase(x, y)
        self.touch()

    def stamp(
        self,
        points: Iterable[tuple[float, float]],
        slot: int = 1,
        *,
        heat: int = 255,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Ink a batch of sub-cell points with one slot and one heat."""
        self._layer(layer).stamp(points, slot, heat)
        self.touch()

    def line(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        slot: int = 1,
        *,
        heat: int = 255,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Draw a line on ``layer``."""
        self._layer(layer).line(x0, y0, x1, y1, slot, heat)
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
        heat: int = 255,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Draw a rectangle on ``layer``; ``fill`` solidifies it."""
        self._layer(layer).rect(x0, y0, x1, y1, fill=fill, slot=slot, heat=heat)
        self.touch()

    def disc(
        self,
        cx: float,
        cy: float,
        r: float,
        slot: int = 1,
        *,
        heat: int = 255,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Draw a filled disc on ``layer``."""
        self._layer(layer).disc(cx, cy, r, slot, heat)
        self.touch()

    def ring(
        self,
        cx: float,
        cy: float,
        r: float,
        thickness: int = 1,
        slot: int = 1,
        *,
        heat: int = 255,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Draw a ring on ``layer``."""
        self._layer(layer).ring(cx, cy, r, thickness, slot, heat)
        self.touch()

    def decay(self, amount: int, *, layer: LayerName | str = LayerName.ART) -> None:
        """Fade ``layer``'s heat by ``amount``; the fill layer never does by default."""
        self._layer(layer).decay(amount)
        self.touch()

    def clear(self, *, layer: LayerName | str | None = None) -> None:
        """Blank one layer, or both when ``layer`` is ``None``."""
        if layer is None:
            self._art.clear()
            self._fill.clear()
        else:
            self._layer(layer).clear()
        self.touch()

    # -- the whole canvas --------------------------------------------------

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
            f"PixelCanvas({self._cols}x{self._rows}, "
            f"marker={self._marker.value!r})"
        )


def _resolve_marker(value: Marker | str) -> Marker:
    try:
        return Marker(value)
    except ValueError:
        raise ValueError(
            f"marker must be one of {tuple(marker.value for marker in Marker)},"
            f" got {value!r}"
        ) from None
