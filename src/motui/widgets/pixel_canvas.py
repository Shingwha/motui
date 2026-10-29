"""PixelCanvas: a sub-cell pixel stage answered as one quantized surface.

A :class:`PixelCanvas` owns two :class:`~motui.pixel.Raster` grids -- a
``fill`` layer of background blocks folded at half-cell resolution and an
``art`` layer of lines and sprites drawn at the marker's resolution -- and
answers :meth:`surface` by handing both to the pixel engine's one quantizer.
Every colour comes from the widget's
:class:`~motui.pixel.PixelPalette`: a caller-provided palette wins, and the
default is derived from the widget's theme
(:meth:`~motui.pixel.PixelPalette.from_theme`).  The widget contributes the
layer organization, geometry and draw/erase/fade verbs, and ``motui.pixel``
contributes the pixels-to-cells semantics.

The widget is the only drawing door: the rasters are private, the verbs
take a :class:`LayerName`, and the marker is validated when assigned.  A
surface is quantized once per invalidation (any verb, a palette or marker
assignment, or a resize) and cached; :meth:`render` only clips it.  Sizing
is explicit -- a host calls :meth:`resize` or :meth:`fit` before painting --
so rendering at another width probes the image instead of dropping the ink.
A real resize rebuilds both rasters empty, which a pixel scene refills on
its next tick.

Octant resolution is deliberately absent: the engine's marker vocabulary
is half and braille, and the choice is an explicit host configuration.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from ..kernel.cell import Surface
from ..pixel import Marker, PixelLayer, PixelPalette, Raster, quantize
from .drawing import Drawing

__all__ = ["LayerName", "PixelCanvas"]


class LayerName(StrEnum):
    """The two layers a canvas exposes, in quantize priority order."""

    ART = "art"
    FILL = "fill"


class PixelCanvas(Drawing):
    """Two private rasters, fill under art, quantized through the palette.

    ``width``/``height`` are cell dimensions; every cell is a 2x4 sub-cell
    grid.  Drawing verbs take sub-cell positions on one layer, floats
    truncated and out-of-range writes clipped.  A real resize rebuilds both
    rasters empty -- a pixel scene redraws every tick, so losing the ink is
    by contract.  The surface cache is dropped by every verb and by a
    ``palette``/``marker`` assignment, and ``render`` never resizes.
    """

    __slots__ = ("_art", "_fill", "_marker", "_palette")

    def __init__(
        self,
        *,
        width: int = 0,
        height: int = 0,
        marker: Marker | str = Marker.BRAILLE,
        palette: PixelPalette | None = None,
        theme=None,
    ) -> None:
        super().__init__(width=width, height=height, theme=theme)
        self._marker = _resolve_marker(marker)
        self._palette = (
            PixelPalette.from_theme(self._theme) if palette is None else palette
        )
        self._art = Raster(self._width, self._height)
        self._fill = Raster(self._width, self._height)

    # -- geometry ----------------------------------------------------------

    @property
    def pixel_width(self) -> int:
        """The sub-cell width of both layers."""
        return self._width * 2

    @property
    def pixel_height(self) -> int:
        """The sub-cell height of both layers."""
        return self._height * 4

    @property
    def marker(self) -> Marker:
        """The art layer's marker family; assigning validates the value."""
        return self._marker

    @marker.setter
    def marker(self, value: Marker | str) -> None:
        resolved = _resolve_marker(value)
        if resolved is not self._marker:
            self._marker = resolved
            self._invalidate()

    @property
    def palette(self) -> PixelPalette:
        """The quantizer's palette; assigning drops the cached surface."""
        return self._palette

    @palette.setter
    def palette(self, value: PixelPalette) -> None:
        self._palette = value
        self._invalidate()

    def _resize_storage(self, cols: int, rows: int) -> None:
        """Rebuild both rasters at the base's new size; the old ink is gone."""
        self._art = Raster(cols, rows)
        self._fill = Raster(cols, rows)

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
        self._invalidate()

    def erase(
        self,
        x: float,
        y: float,
        *,
        layer: LayerName | str = LayerName.ART,
    ) -> None:
        """Blank one sub-cell on ``layer``."""
        self._layer(layer).erase(x, y)
        self._invalidate()

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
        self._invalidate()

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
        self._invalidate()

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
        self._invalidate()

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
        self._invalidate()

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
        self._invalidate()

    def decay(self, amount: int, *, layer: LayerName | str = LayerName.ART) -> None:
        """Fade ``layer``'s heat by ``amount``; the fill layer never does by default."""
        self._layer(layer).decay(amount)
        self._invalidate()

    def clear(self, *, layer: LayerName | str | None = None) -> None:
        """Blank one layer, or both when ``layer`` is ``None``."""
        if layer is None:
            self._art.clear()
            self._fill.clear()
        else:
            self._layer(layer).clear()
        self._invalidate()

    # -- the whole canvas --------------------------------------------------

    def _build_surface(self) -> Surface:
        """Quantize both layers at the canvas's own size; a frozen surface.

        The base caches the answer until the next invalidation.  A canvas
        with no cells is an empty surface -- the quantizer has no grid to
        walk -- and every other answer is exactly the canvas width.
        """
        if self._width == 0 or self._height == 0:
            return Surface(width=self._width, rows=())
        return Surface.of(quantize(self._layers(), self._palette), self._width)

    def __repr__(self) -> str:
        return (
            f"PixelCanvas({self._width}x{self._height}, "
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
