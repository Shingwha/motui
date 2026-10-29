"""Draw approach telegraphs, judgment windows and hit feedback."""

from __future__ import annotations

import math

from ....widgets import LayerName, PixelCanvas
from ...common import ease_out_back
from .rings import (
    APPROACH,
    BURST,
    BURST_OVERSHOOT,
    MISS_FADE,
    OUTER_RADIUS,
    POP,
    TARGET_RADIUS,
    WINDOW_FORCE,
    WINDOW_PERFECT,
    Ring,
    window_stage,
)

__all__ = ["paint"]

_BURST_SLOTS = {"perfect": 6, "good": 3, "force": 4}


def paint(canvas: PixelCanvas, rings: list[Ring], now: float, phase: int) -> None:
    for ring in rings:
        if ring.state == "live":
            _paint_live(canvas, ring, now)
        elif ring.state == "burst":
            t = (now - ring.at) / BURST
            radius = TARGET_RADIUS + BURST_OVERSHOOT * ease_out_back(min(1.0, t))
            slot = _BURST_SLOTS.get(ring.verdict or "", 7)
            _fading_ring(
                canvas,
                ring.cx,
                ring.cy,
                radius,
                slot,
                max(0, round(255 * (1.0 - t))),
            )
            _paint_burst(canvas, ring, t, slot)
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


def _paint_live(canvas: PixelCanvas, ring: Ring, now: float) -> None:
    age = now - ring.born
    deadline = ring.born + APPROACH
    until = deadline - now
    error = abs(until)
    stage = window_stage(error)
    radius = TARGET_RADIUS
    if age <= APPROACH:
        radius = OUTER_RADIUS + (TARGET_RADIUS - OUTER_RADIUS) * age / APPROACH
    slot = ring.slot
    if stage == "close":
        slot = 2
    elif stage == "good":
        slot = 3
    elif stage == "perfect":
        slot = 6
    canvas.ring(ring.cx, ring.cy, radius, 2, slot)
    pop = min(1.0, age / POP)
    canvas.disc(
        ring.cx,
        ring.cy,
        TARGET_RADIUS * ease_out_back(pop),
        ring.slot,
        layer=LayerName.FILL,
    )
    if stage == "approach":
        return
    _paint_close(canvas, ring, radius, WINDOW_FORCE - until)
    if stage in ("good", "perfect"):
        canvas.ring(ring.cx, ring.cy, radius + 3, 1, 3, heat=185)
        _paint_brackets(canvas, ring, TARGET_RADIUS + 4, 3)
    if stage == "perfect":
        _paint_brackets(canvas, ring, TARGET_RADIUS + 2, 6)
        _paint_lock(canvas, ring, WINDOW_PERFECT - until)


def _paint_close(canvas: PixelCanvas, ring: Ring, radius: float, age: float) -> None:
    points = []
    for index in range(8):
        angle = index * math.tau / 8
        points.append(
            (
                ring.cx + math.cos(angle) * (radius + 5),
                ring.cy + math.sin(angle) * (radius + 5),
            )
        )
    canvas.stamp(points, 2, heat=150, layer=LayerName.ART)
    if 0 <= age < 0.25:
        t = age / 0.25
        _fading_ring(
            canvas,
            ring.cx,
            ring.cy,
            radius + 5 + t * 8,
            2,
            round(170 * (1 - t)),
        )


def _paint_brackets(canvas: PixelCanvas, ring: Ring, radius: float, slot: int) -> None:
    cx, cy = ring.cx, ring.cy
    canvas.line(cx - radius, cy - 2, cx - radius, cy + 2, slot, heat=210)
    canvas.line(cx - radius, cy, cx - radius + 2, cy, slot, heat=210)
    canvas.line(cx + radius, cy - 2, cx + radius, cy + 2, slot, heat=210)
    canvas.line(cx + radius - 2, cy, cx + radius, cy, slot, heat=210)
    canvas.line(cx - 2, cy - radius, cx + 2, cy - radius, slot, heat=210)
    canvas.line(cx, cy - radius, cx, cy - radius + 2, slot, heat=210)
    canvas.line(cx - 2, cy + radius, cx + 2, cy + radius, slot, heat=210)
    canvas.line(cx, cy + radius - 2, cx, cy + radius, slot, heat=210)


def _paint_lock(canvas: PixelCanvas, ring: Ring, age: float) -> None:
    cx, cy = ring.cx, ring.cy
    points = [
        (cx, cy - 2),
        (cx, cy + 2),
        (cx - 2, cy),
        (cx + 2, cy),
        (cx - 1, cy - 1),
        (cx + 1, cy - 1),
        (cx - 1, cy + 1),
        (cx + 1, cy + 1),
    ]
    canvas.stamp(points, 6, heat=255, layer=LayerName.ART)
    if 0 <= age < 0.2:
        t = age / 0.2
        _fading_ring(
            canvas,
            cx,
            cy,
            TARGET_RADIUS + 4 + t * 10,
            6,
            round(220 * (1 - t)),
        )


def _paint_burst(canvas: PixelCanvas, ring: Ring, t: float, slot: int) -> None:
    points = []
    for index in range(12):
        angle = index * math.tau / 12 + ring.slot * 0.17
        radius = TARGET_RADIUS + 3 + t * 24
        x = ring.cx + math.cos(angle) * radius
        y = ring.cy + math.sin(angle) * radius
        points.append((x, y))
        if index % 2 == 0:
            points.append((x + math.cos(angle), y + math.sin(angle)))
    canvas.stamp(points, slot, heat=max(0, round(220 * (1 - t))), layer=LayerName.ART)


def _fading_ring(
    canvas: PixelCanvas,
    cx: float,
    cy: float,
    r: float,
    slot: int,
    heat: int,
) -> None:
    steps = max(32, int(2 * math.pi * r * 2))
    points: list[tuple[float, float]] = []
    for index in range(steps):
        angle = 2 * math.pi * index / steps
        for radius in (r - 0.5, r + 0.5):
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    canvas.stamp(points, slot, heat=heat, layer=LayerName.ART)
