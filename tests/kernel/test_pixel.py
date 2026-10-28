"""The pixel raster: sub-cell primitives, heat decay, and quantization."""

from __future__ import annotations

from motui.kernel.pixel import BRAILLE_BITS, Raster


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
