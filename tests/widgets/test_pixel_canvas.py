"""PixelCanvas: layer quantization, marker validation, erase and fade."""

from __future__ import annotations

import pytest

from motui.kernel.layout import Constraints
from motui.pixel import Marker, PixelPalette
from motui.widgets.pixel_canvas import LayerName, PixelCanvas

PALETTE = PixelPalette(
    slots={
        1: ((255, 255, 255), (140, 140, 160)),  # id: (main, cool)
        2: ((255, 130, 190), (150, 70, 110)),
    },
    bg=(12, 12, 16),
)


def test_the_canvas_quantizes_art_over_fill_through_the_pixel_palette():
    canvas = PixelCanvas(2, 2, palette=PALETTE)
    canvas.plot(0, 0, slot=1)  # art dot, cell (0, 0)
    canvas.plot(2, 0, slot=1)  # art dot, cell (1, 0)
    canvas.plot(0, 6, slot=2, layer=LayerName.FILL)  # lower half of cell (0, 1)
    surface = canvas.render(Constraints(width=2, max_height=2))
    assert [row.text for row in surface] == ["\u2801\u2801", "\u2584 "]
    top = surface[0].segments
    assert len(top) == 1  # both art cells share one style object: one run
    assert top[0].style.fg == (255, 255, 255) and top[0].style.bg is None
    bottom = surface[1].segments
    assert [(seg.text, seg.style.fg, seg.style.bg) for seg in bottom] == [
        ("\u2584", (255, 130, 190), (12, 12, 16)),
        (" ", None, None),
    ]


def test_erase_and_decay_cross_the_fresh_cool_and_dark_states():
    canvas = PixelCanvas(1, 1, palette=PALETTE)
    for subrow in range(4):
        canvas.plot(0, subrow, slot=1)  # the cell's whole left braille column
    assert canvas.render(Constraints(width=1, max_height=1))[0].text == "\u2847"
    canvas.erase(0, 0)
    assert canvas.render(Constraints(width=1, max_height=1))[0].text == "\u2846"
    canvas.decay(63)  # heat 255 -> 192: still fresh, the main colour
    fresh = canvas.render(Constraints(width=1, max_height=1))[0].segments[0]
    assert fresh.style.fg == (255, 255, 255)
    canvas.decay(63)  # heat 192 -> 129: aged past COOL_AT, the cool colour
    aged = canvas.render(Constraints(width=1, max_height=1))[0].segments[0]
    assert aged.style.fg == (140, 140, 160)
    canvas.decay(10)  # heat 129 -> 119: below the lit threshold, gone
    assert canvas.render(Constraints(width=1, max_height=1))[0].text == " "


def test_render_rebuilds_the_buffers_at_a_new_size_and_keeps_ink_while_it_holds():
    canvas = PixelCanvas(2, 2, palette=PALETTE)
    canvas.plot(0, 0, slot=1)
    rebuilt = canvas.render(Constraints(width=4, max_height=1))
    assert canvas.width == 4 and canvas.height == 1
    assert rebuilt.width == 4 and rebuilt.height == 1
    assert rebuilt[0].text == "    "  # a resize drops the ink, by contract
    canvas.plot(1, 0, slot=1)
    held = canvas.render(Constraints(width=4))  # natural height: size holds
    assert held.height == 1 and held[0].text == "\u2808   "
    empty = canvas.render(Constraints(width=0))
    assert empty.width == 0 and empty.height == 0


def test_marker_and_layer_names_validate_at_the_widget_door():
    with pytest.raises(ValueError, match="marker must be one of"):
        PixelCanvas(palette=PALETTE, marker="octant")
    canvas = PixelCanvas(palette=PALETTE)
    canvas.marker = "half"
    assert canvas.marker is Marker.HALF
    with pytest.raises(ValueError, match="marker must be one of"):
        canvas.marker = "nope"
    with pytest.raises(ValueError, match="layer must be one of"):
        canvas.plot(0, 0, layer="background")
    assert canvas.pixel_width == 0 and canvas.pixel_height == 0
