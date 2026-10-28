"""Quantize: layer order, markers, cool colors and run fusion."""

from __future__ import annotations

import pytest

from motui.kernel.cell import Segment
from motui.kernel.style import Style
from motui.pixel import (
    BRAILLE_BITS,
    Marker,
    PixelLayer,
    PixelPalette,
    Raster,
    quantize,
)

PALETTE = PixelPalette(
    slots={
        1: ((255, 0, 0), (150, 0, 0)),
        2: ((0, 0, 255), (0, 0, 150)),
    },
    bg=(10, 10, 30),
)


def test_quantize_turns_hand_drawn_cells_into_exact_styled_segments():
    assert BRAILLE_BITS[0][0] == 0x01  # dot 1 sits at the cell's top left
    assert BRAILLE_BITS[1][3] == 0x80

    raster = Raster(2, 1)
    raster.plot(0, 0, 1)  # sub-cell (0, 0): bit 0x01
    raster.plot(1, 3, 1)  # sub-cell (1, 3): bit 0x80
    [line] = quantize([PixelLayer(raster, Marker.BRAILLE)], PALETTE)
    assert line.segments == (
        Segment(chr(0x2800 + 0x81), Style(fg=(255, 0, 0))),
        Segment(" "),
    )

    raster.decay(100)
    [line] = quantize([PixelLayer(raster, Marker.BRAILLE)], PALETTE)
    assert line.segments == (
        Segment(chr(0x2800 + 0x81), Style(fg=(150, 0, 0))),
        Segment(" "),
    )

    raster.decay(100)
    [line] = quantize([PixelLayer(raster, Marker.BRAILLE)], PALETTE)
    assert line.segments == (Segment("  "),)

    fill = Raster(2, 1)
    fill.rect(0, 0, 3, 1, fill=True, slot=2)
    [line] = quantize([PixelLayer(fill, Marker.HALF)], PALETTE)
    assert line.segments == (
        Segment("\u2580\u2580", Style(fg=(0, 0, 255), bg=(10, 10, 30))),
    )

    mixed = Raster(1, 1)
    mixed.plot(0, 0, 1)
    mixed.plot(1, 2, 1)
    [line] = quantize([PixelLayer(mixed, Marker.HALF)], PALETTE)
    assert line.segments == (
        Segment("\u2588", Style(fg=(255, 0, 0), bg=(10, 10, 30))),
    )

    sparse = Raster(2, 1)
    sparse.plot(3, 0, 2)  # the second cell's top half
    [line] = quantize([PixelLayer(sparse, Marker.HALF)], PALETTE)
    assert line.segments == (
        Segment(" "),
        Segment("\u2580", Style(fg=(0, 0, 255), bg=(10, 10, 30))),
    )

    stray = Raster(1, 1)
    stray.plot(0, 0, 9)
    [line] = quantize([PixelLayer(stray, Marker.BRAILLE)], PALETTE)
    assert line.segments == (Segment("\u2801", Style(fg=(255, 255, 255))),)


def test_layer_order_gives_the_first_inked_layer_the_cell():
    top = Raster(2, 1)
    top.plot(0, 0, 1)  # the line layer: one dot in cell 0
    under = Raster(2, 1)
    under.rect(0, 0, 3, 1, fill=True, slot=2)  # the fill: both cells' tops

    [line] = quantize(
        [PixelLayer(top, Marker.BRAILLE), PixelLayer(under, Marker.HALF)],
        PALETTE,
    )
    assert line.segments == (
        Segment("\u2801", Style(fg=(255, 0, 0))),
        Segment("\u2580", Style(fg=(0, 0, 255), bg=(10, 10, 30))),
    )

    [line] = quantize(
        [PixelLayer(under, Marker.HALF), PixelLayer(top, Marker.BRAILLE)],
        PALETTE,
    )
    assert line.segments == (
        Segment("\u2580\u2580", Style(fg=(0, 0, 255), bg=(10, 10, 30))),
    )

    with pytest.raises(ValueError, match="share one geometry"):
        quantize(
            [PixelLayer(top, Marker.BRAILLE), PixelLayer(Raster(3, 1), Marker.HALF)],
            PALETTE,
        )
    with pytest.raises(ValueError, match="not a valid Marker"):
        quantize([PixelLayer(top, "mixed")], PALETTE)


def test_same_runs_fuse_by_identity_and_split_when_a_cell_cools():
    raster = Raster(3, 1)
    raster.plot(0, 0, 1)
    raster.plot(2, 0, 1)
    raster.plot(4, 0, 1)
    [line] = quantize([PixelLayer(raster, Marker.BRAILLE)], PALETTE)
    assert [seg.text for seg in line.segments] == ["\u2801\u2801\u2801"]
    fresh = line.segments[0].style
    assert fresh == Style(fg=(255, 0, 0))

    raster.decay(120)
    raster.plot(0, 0, 1)
    raster.plot(4, 0, 1)
    [line] = quantize([PixelLayer(raster, Marker.BRAILLE)], PALETTE)
    assert [seg.text for seg in line.segments] == ["\u2801", "\u2801", "\u2801"]
    cool = line.segments[1].style
    assert cool == Style(fg=(150, 0, 0))
    assert line.segments[0].style is line.segments[2].style
    assert cool is not fresh
    assert line.segments[0].style is fresh
