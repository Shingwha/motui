"""The pixel raster: sub-cell primitives, heat decay, and quantization."""

from __future__ import annotations

from motui.kernel.cell import Segment
from motui.kernel.pixel import BRAILLE_BITS, PixelPalette, Raster, quantize
from motui.kernel.style import Style


def test_a_raster_inks_its_primitives_and_decays_heat_without_touching_slots():
    """Known drawing sequences land exact slot/heat grid values."""
    assert BRAILLE_BITS[0][0] == 0x01  # dot 1 sits at the cell's top left
    assert BRAILLE_BITS[1][3] == 0x80

    raster = Raster(4, 2)  # an 8x8 sub-cell grid
    assert (raster.width, raster.height) == (8, 8)

    # set stores the slot and re-freshens heat; off-grid writes clip.
    raster.set(0, 0, 3)
    assert raster.slot[0] == 3
    assert raster.heat[0] == 255
    raster.set(-1, 0, 7)
    raster.set(8, 0, 7)
    raster.set(0, 8, 7)
    assert sum(1 for value in raster.slot if value) == 1
    raster.set(0, 0, 0)  # slot 0 is empty: no ink, no error
    assert raster.slot[0] == 3 and raster.heat[0] == 255

    raster.clear()

    # A horizontal Bresenham line covers exactly its three points.
    raster.line(1, 1, 3, 1, 2)
    assert [raster.slot[8 + x] for x in range(8)] == [0, 2, 2, 2, 0, 0, 0, 0]
    assert all(raster.heat[8 + x] == 255 for x in (1, 2, 3))

    raster.clear()

    # A rect outline is its edge cells; fill is every cell.
    raster.rect(1, 1, 3, 3, slot=4)
    assert sum(1 for value in raster.slot if value) == 8  # 3+3 edge, 2 sides
    raster.clear()
    raster.rect(1, 1, 3, 3, fill=True, slot=4)
    assert sum(1 for value in raster.slot if value) == 9

    raster.clear()

    # A disc fills one span per sub-row: rows 2..6 of an r=2 circle at (4,4).
    raster.disc(4, 4, 2, 5)
    assert sum(1 for value in raster.slot if value) == 15
    assert [x for x in range(8) if raster.slot[4 * 8 + x]] == [2, 3, 4, 5, 6]

    # A ring marks only its band, always with its own slot id.
    raster.clear()
    raster.ring(4, 4, 3, 1, 6)
    inked = [value for value in raster.slot if value]
    assert inked and set(inked) == {6}

    # Decay cools heat through one translate; slot bytes survive as stale.
    raster.decay(100)
    assert raster.heat[0] == 0 and all(heat < 255 for heat in raster.heat)
    assert set(raster.slot) <= {0, 6}
    raster.decay(0)
    raster.decay(-5)
    hot = raster.heat[8 * 4 + 7]  # angle 0 is deterministically on the ring
    raster.decay(1)
    assert raster.heat[8 * 4 + 7] == hot - 1

    # clear() empties both grids in one step.
    raster.clear()
    assert not any(raster.slot) and not any(raster.heat)


def test_quantize_turns_a_hand_drawn_raster_into_exact_styled_segments():
    """Small hand-computed grids answer exact Segment runs and styles."""
    palette = PixelPalette(
        slots={
            1: ((255, 0, 0), (150, 0, 0)),
            2: ((0, 0, 255), (0, 0, 150)),
        },
        bg=(10, 10, 30),
    )

    # One braille cell with dots 1 and 8 lit (slot 1, fresh), one empty.
    raster = Raster(2, 1)
    raster.set(0, 0, 1)  # sub-cell (0, 0): bit 0x01
    raster.set(1, 3, 1)  # sub-cell (1, 3): bit 0x80
    [line] = quantize([(raster, "braille")], palette)
    assert line.segments == (
        Segment(chr(0x2800 + 0x81), Style(fg=(255, 0, 0))),
        Segment(" "),
    )

    # Decayed below COOL_AT but still lit: the same dots in the cool color.
    raster.decay(100)
    [line] = quantize([(raster, "braille")], palette)
    assert line.segments == (
        Segment(chr(0x2800 + 0x81), Style(fg=(150, 0, 0))),
        Segment(" "),
    )

    # Decayed below the lit floor: the cell is empty, braille rows stay
    # transparent (unstyled spaces).
    raster.decay(100)
    [line] = quantize([(raster, "braille")], palette)
    assert line.segments == (Segment("  "),)

    # A half fill over both cells' top sub-rows (sub-columns 0..3): two
    # identical cells fuse into one segment.
    fill = Raster(2, 1)
    fill.rect(0, 0, 3, 1, fill=True, slot=2)
    [line] = quantize([(fill, "half")], palette)
    assert line.segments == (Segment("\u2580\u2580", Style(fg=(0, 0, 255), bg=(10, 10, 30))),)

    # One top dot plus one bottom dot in one cell: the full block.
    mixed = Raster(1, 1)
    mixed.set(0, 0, 1)
    mixed.set(1, 2, 1)
    [line] = quantize([(mixed, "half")], palette)
    assert line.segments == (Segment("\u2588", Style(fg=(255, 0, 0), bg=(10, 10, 30))),)

    # A half layer paints its empty cells with the palette background.
    sparse = Raster(2, 1)
    sparse.set(3, 0, 2)  # the second cell's top half
    [line] = quantize([(sparse, "half")], palette)
    assert line.segments == (
        Segment(" ", Style(bg=(10, 10, 30))),
        Segment("\u2580", Style(fg=(0, 0, 255), bg=(10, 10, 30))),
    )

    # A slot with no palette entry quantizes to white, not to a crash.
    stray = Raster(1, 1)
    stray.set(0, 0, 9)
    [line] = quantize([(stray, "braille")], palette)
    assert line.segments == (Segment("\u2801", Style(fg=(255, 255, 255))),)
