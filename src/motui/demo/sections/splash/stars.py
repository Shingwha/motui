"""The starfield pack's three parallax layers."""

from __future__ import annotations

import random

from ....widgets import LayerName, PixelCanvas
from .packs import STAR_SLOTS
from .wordmark import _geometry

__all__ = ["paint_stars"]

#: The starfield's parallax: per-layer drift as (numerator, denominator)
#: sub-cells per tick, far to near.
_STAR_DRIFT = ((1, 12), (1, 6), (1, 3))

#: The virtual space the star seeds were dealt in.
_STAR_SPACE_W = 152
_STAR_SPACE_H = 96


def _build_stars() -> tuple[tuple[int, int, int], ...]:
    """The star seeds: ``(x, y, layer)`` dealt once at import."""
    rng = random.Random(20261027)
    stars: list[tuple[int, int, int]] = []
    for layer, count in enumerate((44, 28, 14)):
        for _ in range(count):
            stars.append(
                (rng.randrange(_STAR_SPACE_W), rng.randrange(_STAR_SPACE_H), layer)
            )
    return tuple(stars)


_STARS: tuple[tuple[int, int, int], ...] = _build_stars()


def paint_stars(
    canvas: PixelCanvas,
    phase: int,
    width: int,
    height: int,
    sx: int,
    sy: int,
) -> None:
    """Three parallax depths twinkling in the bands around the word."""
    if width <= 0:
        return
    _letters, _columns, top, bottom = _geometry(width, height, sx, sy)
    half = _STAR_SPACE_H // 2
    lower = height - bottom
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for order, (x, y, layer) in enumerate(_STARS):
        num, den = _STAR_DRIFT[layer]
        px = (x * width // _STAR_SPACE_W - phase * num // den) % width
        if y < half:
            if top <= 0:
                continue
            py = y * top // half
        else:
            if lower <= 0:
                continue
            py = bottom + (y - half) * lower // half
        if layer == 1 and (phase // 6 + order) % 7 == 0:
            continue
        if layer == 2 and (phase // 4 + order) % 5 == 0:
            continue
        slot = STAR_SLOTS[layer]
        groups.setdefault((slot, 255), []).append((px, py))
        if layer == 2 and px + 1 < width:
            groups.setdefault((slot, 200), []).append((px + 1, py))
    for (slot, heat), points in groups.items():
        canvas.stamp(points, slot, heat=heat, layer=LayerName.ART)
