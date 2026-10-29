"""The scaled 5x7 wordmark geometry shared by the opening effects."""

from __future__ import annotations

from .font import FONT_5X7

__all__ = ["pick_scale"]

_WORD_CHARS = "MOTUI"
_FONT_SCALES = ((3, 4), (2, 3), (1, 2), (1, 1))
_LETTER_GAP = 2


def _build_letters(sx: int, sy: int) -> tuple[list[list[tuple[int, int]]], int, int]:
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
    tuple[int, int], tuple[list[list[tuple[int, int]]], int, int]
] = {}


def _letters(sx: int, sy: int) -> tuple[list[list[tuple[int, int]]], int, int]:
    cached = _LETTERS_CACHE.get((sx, sy))
    if cached is None:
        cached = _build_letters(sx, sy)
        _LETTERS_CACHE[(sx, sy)] = cached
    return cached


def pick_scale(width: int, height: int) -> tuple[int, int]:
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
