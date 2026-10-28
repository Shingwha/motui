"""Draw the rings model onto a PixelCanvas."""

from __future__ import annotations

import math

from ....widgets import LayerName, PixelCanvas
from ...common import ease_out_back
from .rings import (
    APPROACH,
    BLINK_TICKS,
    BURST,
    BURST_OVERSHOOT,
    MISS_FADE,
    OUTER_RADIUS,
    POP,
    TARGET_RADIUS,
    WINDOW_GOOD,
    Ring,
)

__all__ = ["paint"]

_BURST_SLOTS = {"perfect": 5, "good": 6}


def paint(canvas: PixelCanvas, rings: list[Ring], now: float, phase: int) -> None:
    """Paint one frame of rings: approach, target, burst and miss fade."""
    for ring in rings:
        if ring.state == "live":
            _paint_live(canvas, ring, now, phase)
        elif ring.state == "burst":
            t = (now - ring.at) / BURST
            radius = TARGET_RADIUS + BURST_OVERSHOOT * ease_out_back(min(1.0, t))
            _fading_ring(
                canvas,
                ring.cx,
                ring.cy,
                radius,
                _BURST_SLOTS.get(ring.verdict or "", 7),
                max(0, round(255 * (1.0 - t))),
            )
        else:
            t = (now - ring.at) / MISS_FADE
            _fading_ring(
                canvas,
                ring.cx,
                ring.cy,
                TARGET_RADIUS,
                7,
                max(0, round(255 * (1.0 - t))),
            )


def _paint_live(canvas: PixelCanvas, ring: Ring, now: float, phase: int) -> None:
    age = now - ring.born
    if age <= APPROACH:
        t = age / APPROACH
        radius = OUTER_RADIUS + (TARGET_RADIUS - OUTER_RADIUS) * t
        error = abs(now - (ring.born + APPROACH))
        flash = error <= WINDOW_GOOD and (phase // BLINK_TICKS) % 2 == 0
        canvas.ring(ring.cx, ring.cy, radius, 2, 5 if flash else ring.slot)
    pop = min(1.0, age / POP)
    canvas.disc(
        ring.cx,
        ring.cy,
        TARGET_RADIUS * ease_out_back(pop),
        ring.slot,
        layer=LayerName.FILL,
    )


def _fading_ring(
    canvas: PixelCanvas,
    cx: float,
    cy: float,
    r: float,
    slot: int,
    heat: int,
) -> None:
    """A ring whose ink carries an explicit heat (the fade), not 255."""
    steps = max(32, int(2 * math.pi * r * 2))
    points: list[tuple[float, float]] = []
    for index in range(steps):
        angle = 2 * math.pi * index / steps
        for radius in (r - 0.5, r + 0.5):
            points.append(
                (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            )
    canvas.stamp(points, slot, heat=heat, layer=LayerName.ART)
