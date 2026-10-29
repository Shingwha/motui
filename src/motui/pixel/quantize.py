"""Quantize layered rasters into ordinary kernel cell rows."""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.cell import Line, Segment
from ..kernel.style import Style
from .palette import PixelPalette
from .types import (
    COOL_AT,
    HALF_BOTTOM,
    HALF_FULL,
    HALF_TOP,
    HEAT_LIT,
    Marker,
    PixelLayer,
)

__all__ = ["quantize"]

#: ``chr(0x2800 + bits)`` for every dot pattern, precomputed so the inner
#: loop indexes a tuple instead of calling ``chr`` once per cell.
_BRAILLE_CHARS: tuple[str, ...] = tuple(chr(0x2800 + bits) for bits in range(256))

#: The dot bits of the upper and lower halves; a half cell's glyph follows
#: from two mask tests, so one scan shape serves both markers.
_TOP_MASK = 0x1B
_BOTTOM_MASK = 0xE4


def _majority(stats: dict[int, list[int]]) -> tuple[int, int]:
    """The majority slot's ``(id, peak heat)``; ties break by heat then lower id."""
    slot_id, entry = max(
        stats.items(), key=lambda item: (item[1][0], item[1][1], -item[0])
    )
    return slot_id, entry[1]


def quantize(layers: Sequence[PixelLayer], palette: PixelPalette) -> list[Line]:
    """Quantize layered rasters into one :class:`Line` per cell row.

    Layers share geometry and the first with ink owns a cell.  Braille uses
    the eight dots with the majority slot's fg; half folds four sub-rows and
    carries the palette bg.  Adjacent identical cells fuse by style identity.
    """
    if not layers:
        return []
    first = layers[0].raster
    cols, rows = first.cols, first.rows
    grids: list[tuple[memoryview, memoryview, int]] = []
    for layer in layers:
        raster = layer.raster
        if raster.cols != cols or raster.rows != rows:
            raise ValueError(
                f"quantize layers must share one geometry, got {cols}x{rows}"
                f" and {raster.cols}x{raster.rows}"
            )
        marker = Marker(layer.marker)
        slots, heat = raster.grids()
        grids.append((slots, heat, 0 if marker is Marker.BRAILLE else 1))

    styles, fallback = palette.tables()
    styles_get = styles.get
    width = cols * 2
    lit = HEAT_LIT
    cool_at = COOL_AT
    chars = _BRAILLE_CHARS
    majority = _majority

    # Dot bits paired with sub-cell offsets from the cell's top left corner,
    # upper two sub-rows first: one scan shape serves both markers.
    offsets = (
        (0x01, 0),
        (0x08, 1),
        (0x02, width),
        (0x10, width + 1),
        (0x04, width * 2),
        (0x20, width * 2 + 1),
        (0x40, width * 3),
        (0x80, width * 3 + 1),
    )

    cell_rows: list[Line] = []
    for cy in range(rows):
        row_base = cy * 4 * width
        segments: list[Segment] = []
        run_char: str | None = None
        run_style: Style | None = None
        run_start = 0
        for cx in range(cols + 1):
            char: str | None = None
            style: Style | None = None
            if cx < cols:
                col_base = row_base + cx * 2
                for slot_grid, heat_grid, kind in grids:
                    bits = 0
                    solo = 0  # the only slot seen so far (0 = none yet)
                    solo_n = 0
                    peak = 0
                    stats: dict[int, list[int]] | None = None
                    for bit, off in offsets:
                        cell = col_base + off
                        heat = heat_grid[cell]
                        if heat >= lit:
                            bits |= bit
                            inked = slot_grid[cell]
                            if solo == 0:
                                solo, solo_n, peak = inked, 1, heat
                            elif inked == solo:
                                solo_n += 1
                                if heat > peak:
                                    peak = heat
                            else:
                                if stats is None:
                                    stats = {solo: [solo_n, peak]}
                                entry = stats.get(inked)
                                if entry is None:
                                    stats[inked] = [1, heat]
                                else:
                                    entry[0] += 1
                                    if heat > entry[1]:
                                        entry[1] = heat
                    if not bits:
                        continue
                    if kind == 0:  # braille: fg-only, transparent off dots
                        char = chars[bits]
                        variant = 0
                    else:  # half: the bg rides so an unlit sub-row shows it
                        top_lit = bits & _TOP_MASK
                        bottom_lit = bits & _BOTTOM_MASK
                        char = (
                            HALF_FULL
                            if top_lit and bottom_lit
                            else HALF_TOP
                            if top_lit
                            else HALF_BOTTOM
                        )
                        variant = 2
                    if stats is None:  # single-slot cell: no vote needed
                        quad = styles_get(solo) or fallback
                        style = quad[variant] if peak >= cool_at else quad[variant + 1]
                    else:
                        slot_id, peak = majority(stats)
                        quad = styles_get(slot_id) or fallback
                        style = quad[variant] if peak >= cool_at else quad[variant + 1]
                    break
                if char is None:  # no layer has ink in this cell
                    char = " "
                    style = None
            if char == run_char and style is run_style:
                continue  # same run: fuse by identity, no segment spent
            if run_char is not None:
                count = cx - run_start
                if run_style is None:
                    segments.append(Segment(" " * count))
                else:
                    segments.append(Segment(run_char * count, run_style))
            run_char = char
            run_style = style
            run_start = cx
        cell_rows.append(Line(tuple(segments)))
    return cell_rows
