"""The splash's scaled 5x7 wordmark: geometry, assembly and sweep."""

from __future__ import annotations

from ....widgets import LayerName, PixelCanvas
from ...common import ease_out_back
from .font import FONT_5X7
from .packs import BANDS, GLITCH_CYAN, GLITCH_RED, SPLASH_ROTATE_TICKS

__all__ = ["ENTRANCE_TICKS", "paint_sweep", "paint_wordmark", "pick_scale"]

#: The letters the wordmark spells (all present in :data:`FONT_5X7`).
_WORD_CHARS = "MOTUI"

#: Integer scales for the 5x7 skeleton: sub-cells per font cell, largest
#: first; the biggest one that fits the canvas with margin wins.
_FONT_SCALES = ((3, 4), (2, 3), (1, 2), (1, 1))

#: Font cells between letters (scaled like the glyphs are).
_LETTER_GAP = 2

#: The entrance: letter ``i`` starts ``i * stagger`` ticks in and rises
#: for ``dur`` ticks, from ``drop`` sub-cells below its slot.
_ENTRANCE_STAGGER = 9
_ENTRANCE_DUR = 30
ENTRANCE_TICKS = 4 * _ENTRANCE_STAGGER + _ENTRANCE_DUR
_ENTRANCE_DROP = 20

#: The neon sweep: a white head flowing left-to-right, its decay trail
#: burning out behind it (one heat step per sub-cell of trail).
_SWEEP_PERIOD = 150
_SWEEP_PAD = 12
_SWEEP_TRAIL = 12
_SWEEP_STEP = 10


def _build_letters(sx: int, sy: int) -> tuple[list[list[tuple[int, int]]], int, int]:
    """The word's letters at one integer scale: one point list per letter."""
    letters: list[list[tuple[int, int]]] = []
    for char in _WORD_CHARS:
        glyph = FONT_5X7[char]
        inked = {
            (col, row)
            for row, cells in enumerate(glyph)
            for col, bit in enumerate(cells)
            if bit == "1"
        }
        points: list[tuple[int, int]] = []
        for col, row in sorted(inked):
            top = (col, row - 1) in inked
            bottom = (col, row + 1) in inked
            left = (col - 1, row) in inked
            right = (col + 1, row) in inked
            for i in range(sx):
                for j in range(sy):
                    if i == 0 and j == 0 and not left and not top:
                        continue
                    if i == sx - 1 and j == 0 and not right and not top:
                        continue
                    if i == 0 and j == sy - 1 and not left and not bottom:
                        continue
                    if i == sx - 1 and j == sy - 1 and not right and not bottom:
                        continue
                    points.append((col * sx + i, row * sy + j))
        letters.append(points)
    width = (5 * sx + _LETTER_GAP * sx) * len(_WORD_CHARS) - _LETTER_GAP * sx
    return letters, width, 7 * sy


_LETTERS_CACHE: dict[
    tuple[int, int],
    tuple[list[list[tuple[int, int]]], int, int],
] = {}


def _letters(sx: int, sy: int) -> tuple[list[list[tuple[int, int]]], int, int]:
    """The scaled letters for one scale, built once."""
    cached = _LETTERS_CACHE.get((sx, sy))
    if cached is None:
        cached = _build_letters(sx, sy)
        _LETTERS_CACHE[(sx, sy)] = cached
    return cached


def pick_scale(width: int, height: int) -> tuple[int, int]:
    """The largest integer scale whose word fits the canvas with margin."""
    for sx, sy in _FONT_SCALES:
        if 33 * sx <= width - 4 and 7 * sy <= height - 4:
            return sx, sy
    return (1, 1)


_GEOM_CACHE: dict[
    tuple[int, int, int, int],
    tuple[
        list[list[tuple[int, int]]],
        dict[int, list[tuple[int, int]]],
        int,
        int,
    ],
] = {}


def _geometry(
    width: int, height: int, sx: int, sy: int
) -> tuple[
    list[list[tuple[int, int]]],
    dict[int, list[tuple[int, int]]],
    int,
    int,
]:
    """The centred wordmark on one canvas, plus the star bands."""
    key = (width, height, sx, sy)
    cached = _GEOM_CACHE.get(key)
    if cached is not None:
        return cached
    letter_points, mark_w, mark_h = _letters(sx, sy)
    ox = max(0, (width - mark_w) // 2)
    oy = max(0, (height - mark_h) // 2)
    pitch = (5 + _LETTER_GAP) * sx
    letters: list[list[tuple[int, int]]] = []
    columns: dict[int, list[tuple[int, int]]] = {}
    for order, points in enumerate(letter_points):
        lx = order * pitch
        placed: list[tuple[int, int]] = []
        for px, py in points:
            x, y = ox + lx + px, oy + py
            if not 0 <= x < width or not 0 <= y < height:
                continue
            placed.append((x, y))
            columns.setdefault(x, []).append((x, y))
        letters.append(placed)
    top = max(0, oy - 2)
    bottom = min(height, oy + mark_h + 2)
    cached = (letters, columns, top, bottom)
    _GEOM_CACHE[key] = cached
    return cached


def paint_wordmark(
    canvas: PixelCanvas,
    pack: str,
    phase: int,
    width: int,
    height: int,
    sx: int,
    sy: int,
) -> None:
    """The letters on the fill layer, one slot per pack's recipe."""
    letters, _columns, _top, _bottom = _geometry(width, height, sx, sy)
    glitch = pack == "starfield" and (phase // 37) % 4 == 0
    shift = phase // 2  # the plasma hue wheel's step
    amber = (phase // SPLASH_ROTATE_TICKS) % 2 == 1
    if width:
        if pack == "plasma":
            slot_by_x = [
                1 + ((min(BANDS - 1, x * BANDS // width) + shift) % BANDS)
                for x in range(width)
            ]
        else:
            slot_by_x = [1 + min(BANDS - 1, x * BANDS // width) for x in range(width)]
    else:
        slot_by_x = []
    retro_slots = (1 if amber else 3, 2 if amber else 4)
    for order, letter in enumerate(letters):
        t = (phase - order * _ENTRANCE_STAGGER) / _ENTRANCE_DUR
        if t <= 0:
            continue
        drop = 0 if t >= 1 else round((1.0 - ease_out_back(t)) * _ENTRANCE_DROP)
        heat = 255 if t >= 1 else 128 + int(127.0 * t)
        groups: dict[int, list[tuple[int, int]]] = {}
        for x, y in letter:
            if drop:
                y += drop
                if y >= height:
                    continue
            if pack == "retro":
                slot = retro_slots[(y // 4) % 2]
            else:
                slot = slot_by_x[x]
                if glitch and (x * 7 + y * 13 + phase) % 19 < 2:
                    slot = GLITCH_RED if (x + y) % 2 == 0 else GLITCH_CYAN
            groups.setdefault(slot, []).append((x, y))
        for slot, points in groups.items():
            canvas.stamp(points, slot, heat=heat, layer=LayerName.FILL)


def paint_sweep(
    canvas: PixelCanvas,
    phase: int,
    width: int,
    sx: int,
    sy: int,
) -> None:
    """The white sweep: a head column flowing across the assembled word."""
    _letters, columns, _top, _bottom = _geometry(
        width, canvas.pixel_height, sx, sy
    )
    span = width + 2 * _SWEEP_PAD
    tick = phase - ENTRANCE_TICKS
    head = tick % _SWEEP_PERIOD * span // _SWEEP_PERIOD - _SWEEP_PAD
    for step in range(_SWEEP_TRAIL):
        heat = 255 - step * _SWEEP_STEP
        if heat <= 0:
            break
        points = columns.get(head - step)
        if points:
            canvas.stamp(points, 13, heat=heat, layer=LayerName.ART)
