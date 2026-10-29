"""Continuous scene choreography for the Signal Lab opening."""

from __future__ import annotations

import math
from collections.abc import Iterable

from ....widgets import LayerName, PixelCanvas
from .stars import paint_stars
from .wordmark import _geometry

__all__ = [
    "ACT_TICKS",
    "EFFECTS",
    "TRANSITION_TICKS",
    "blend",
    "paint_background",
    "paint_wordmark",
]

ACT_TICKS = 720
TRANSITION_TICKS = 180
EFFECTS = ("deep", "ion", "phosphor", "gravity", "warp")


def _noise(x: int, y: int, seed: int = 0) -> float:
    return ((x * 73 + y * 151 + seed * 199 + x * y * 17) % 251) / 251


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def blend(local: int) -> float:
    t = _clamp(local / TRANSITION_TICKS)
    return t * t * (3 - 2 * t)


def _stamp(
    canvas: PixelCanvas,
    points: Iterable[tuple[float, float]],
    slot: int,
    heat: int,
    layer: LayerName = LayerName.FILL,
) -> None:
    if heat > 0:
        canvas.stamp(points, slot, heat=min(255, heat), layer=layer)


def paint_background(
    canvas: PixelCanvas,
    effects: tuple[str, ...],
    previous: tuple[str, ...],
    phase: int,
    act_phase: int,
    sx: int,
    sy: int,
) -> None:
    main, auxiliary = effects
    act = max(0, phase) // ACT_TICKS
    weight = blend(act_phase) if act else 1.0
    paint_stars(canvas, phase, canvas.pixel_width, canvas.pixel_height, sx, sy)
    if previous[0] == "ion" and main != "ion":
        _paint_ion_current(canvas, phase, 1 - weight)
    if main == "ion":
        _paint_ion_current(canvas, phase, weight)
    if auxiliary == "comet":
        _paint_comet(canvas, act_phase)
    elif auxiliary == "wave":
        _paint_wave(canvas, phase, act_phase)
    else:
        _paint_scan(canvas, act_phase)


def _paint_ion_current(canvas: PixelCanvas, phase: int, strength: float) -> None:
    if strength <= 0.001:
        return
    width, height = canvas.pixel_width, canvas.pixel_height
    centre = width / 2
    span = width * strength / 2
    for band in range(2):
        points = []
        for x in range(max(0, round(centre - span)), min(width, round(centre + span)), 3):
            y = height * (0.22 + band * 0.56)
            y += math.sin(x * 0.055 + phase * 0.018 + band * 2) * 3 * strength
            points.append((x, y))
        _stamp(canvas, points, 1 + band, 135, LayerName.ART)


def _paint_comet(canvas: PixelCanvas, act_phase: int) -> None:
    width, height = canvas.pixel_width, canvas.pixel_height
    age, duration = act_phase - 90, 180
    if not 0 <= age < duration:
        return
    x = -16 + age * (width + 32) / duration
    y = height * 0.16 + age * height * 0.22 / duration
    for step in range(12):
        _stamp(
            canvas,
            [(x - step * 1.4, y - step * 0.45)],
            13 if step < 2 else 2,
            205 - step * 9,
        )


def _paint_wave(canvas: PixelCanvas, phase: int, act_phase: int) -> None:
    width, height = canvas.pixel_width, canvas.pixel_height
    age, duration = act_phase - 180, 360
    if not 0 <= age < duration:
        return
    t = age / duration
    wave = max(0, phase) // ACT_TICKS
    cx = width * (0.18 + 0.64 * _noise(wave, 17))
    cy = height * (0.2 + 0.6 * _noise(wave, 31))
    radius = 3 + t * min(width * 0.38, height * 0.46)
    density = math.sin(math.pi * t)
    points = []
    steps = max(36, round(radius * 8))
    for index in range(0, steps, 2):
        if _noise(index, wave, 7) > density:
            continue
        angle = index * math.tau / steps
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    _stamp(canvas, points, 7, 140, LayerName.ART)


def _paint_scan(canvas: PixelCanvas, act_phase: int) -> None:
    width, height = canvas.pixel_width, canvas.pixel_height
    age, duration = act_phase - 120, 240
    if not 0 <= age < duration:
        return
    x = -4 + age * (width + 8) / duration
    points = [(x, y) for y in range(0, height, 2)]
    _stamp(canvas, points, 15, 140, LayerName.ART)


def _transform(
    x: float,
    y: float,
    main: str,
    phase: int,
    local: int,
    cx: float,
    cy: float,
) -> tuple[float, float]:
    if main == "ion":
        return x, y + math.sin(x * 0.085 + phase * 0.025) * 1.25
    if main == "gravity":
        scale = 0.985 + 0.015 * math.sin(phase * 0.018)
        return cx + (x - cx) * scale, cy + (y - cy) * scale
    if main == "warp":
        scale = 1 + 0.055 * math.sin(local / ACT_TICKS * math.pi)
        return cx + (x - cx) * scale, cy + (y - cy) * scale
    if main == "deep":
        return x, y + math.sin(x * 0.075 + phase * 0.012) * 0.35
    return x, y


def paint_wordmark(
    canvas: PixelCanvas,
    phase: int,
    sx: int,
    sy: int,
    main: str,
    previous_main: str,
    act: int,
) -> None:
    width, height = canvas.pixel_width, canvas.pixel_height
    letters, columns, _top, _bottom = _geometry(width, height, sx, sy)
    local = phase % ACT_TICKS
    weight = blend(local) if act else 1.0
    groups: dict[int, list[tuple[float, float]]] = {}
    cx, cy = width / 2, height / 2
    for order, letter in enumerate(letters):
        entrance = _clamp((phase - 24 - order * 11) / 132)
        assembled = 1 - (1 - entrance) ** 3
        for x, y in letter:
            px, py = float(x), float(y)
            if entrance < 1:
                angle = _noise(x, y, order) * math.tau + order
                distance = (1 - assembled) * max(width, height) * 0.55
                px += math.cos(angle + assembled * 3.5) * distance
                py += math.sin(angle + assembled * 3.5) * distance * 0.55
            else:
                current_x, current_y = _transform(px, py, main, phase, local, cx, cy)
                if act:
                    old_x, old_y = _transform(
                        px, py, previous_main, phase, ACT_TICKS + local, cx, cy
                    )
                    px = old_x + (current_x - old_x) * weight
                    py = old_y + (current_y - old_y) * weight
                else:
                    px, py = current_x, current_y
            slot = 1 + x * 12 // max(1, width)
            groups.setdefault(slot, []).append((px, py))
    for slot, points in groups.items():
        _stamp(canvas, points, slot, 255, LayerName.ART)

    if phase >= 156:
        sweep = (phase - 156) % 360
        head = round((sweep / 360) * (width + 28)) - 14
        for offset in range(5):
            points = columns.get(head - offset)
            if points:
                _stamp(canvas, points, 13, 230 - offset * 32, LayerName.ART)
