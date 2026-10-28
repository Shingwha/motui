"""The mutable raster: verbs, clipping, heat and the read probe."""

from __future__ import annotations

import pytest

from motui.pixel import Raster


def test_raster_verbs_ink_clip_erase_and_decay():
    raster = Raster(4, 2)  # an 8x8 sub-cell grid
    assert (raster.width, raster.height) == (8, 8)

    raster.plot(0, 0, 3)
    assert raster.at(0, 0) == (3, 255)
    assert raster.at(-1, 0) == raster.at(8, 0) == raster.at(0, 8) == (0, 0)

    with pytest.raises(ValueError, match=r"slot must be 1\.\.255"):
        raster.plot(0, 0, 0)
    with pytest.raises(ValueError, match=r"slot must be 1\.\.255"):
        raster.plot(0, 0, 256)

    raster.stamp([(1, 1), (2, 1)], 4, heat=999)
    assert raster.at(1, 1) == (4, 255)
    assert raster.at(2, 1) == (4, 255)

    raster.erase(1, 1)
    assert raster.at(1, 1) == (0, 0)

    raster.clear()
    assert not any(raster.at(x, y)[0] for y in range(8) for x in range(8))

    raster.line(1, 1, 3, 1, 2)
    assert [raster.at(x, 1)[0] for x in range(8)] == [0, 2, 2, 2, 0, 0, 0, 0]
    assert all(raster.at(x, 1)[1] == 255 for x in (1, 2, 3))

    raster.clear()
    raster.rect(1, 1, 3, 3, slot=4)
    assert sum(raster.at(x, y)[0] == 4 for y in range(8) for x in range(8)) == 8
    raster.clear()
    raster.rect(1, 1, 3, 3, fill=True, slot=4)
    assert sum(raster.at(x, y)[0] == 4 for y in range(8) for x in range(8)) == 9

    raster.clear()
    raster.disc(4, 4, 2, 5)
    assert sum(raster.at(x, y)[0] == 5 for y in range(8) for x in range(8)) == 15
    assert [x for x in range(8) if raster.at(x, 4)[0]] == [2, 3, 4, 5, 6]

    raster.clear()
    raster.ring(4, 4, 3, 1, 6)
    inked = [raster.at(x, y)[0] for y in range(8) for x in range(8) if raster.at(x, y)[0]]
    assert inked and set(inked) == {6}

    raster.clear()
    raster.plot(5, 5, 1, heat=999)
    assert raster.at(5, 5) == (1, 255)
    raster.decay(100)
    assert raster.at(5, 5) == (1, 155)
    raster.decay(0)
    raster.decay(-5)
    assert raster.at(5, 5) == (1, 155)
    raster.decay(1)
    assert raster.at(5, 5) == (1, 154)

    raster.clear()
    assert raster.at(5, 5) == (0, 0)


def test_raster_rejects_negative_geometry():
    with pytest.raises(ValueError, match="non-negative"):
        Raster(-1, 0)
