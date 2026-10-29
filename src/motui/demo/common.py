"""Shared composition helpers for the showcase scenes."""

from __future__ import annotations

from collections.abc import Sequence

from ..kernel.cell import Line, Segment, Surface
from ..kernel.geom import Pos
from ..kernel.layout import Constraints
from ..kernel.style import Style
from ..kernel.text import WrapMode
from ..kernel.theme import Theme
from ..widgets.base import Widget

__all__ = [
    "FixedHeight",
    "LinesView",
    "center",
    "ease_out_back",
    "ends",
    "fit",
    "hit_target",
    "pad_rows",
]

_CLIP = WrapMode.CLIP


class LinesView(Widget):
    """A render-only block of pre-built lines."""

    __slots__ = ("lines",)

    def __init__(
        self,
        theme: Theme,
        lines: Sequence[Line] | None = None,
    ) -> None:
        super().__init__(theme, None)
        self.lines = list(lines or ())

    def render(self, c: Constraints) -> Surface:
        rows = [line.clip(_CLIP, c.width) for line in self.lines]
        return Surface.of(rows, c.width)


class FixedHeight:
    """Render a child under a row budget and pad it to exactly that height."""

    __slots__ = ("child", "height")

    def __init__(self, child: object, height: int = 0) -> None:
        self.child = child
        self.height = height

    def render(self, c: Constraints) -> Surface:
        budget = max(0, self.height)
        rows = list(
            self.child.render(Constraints(width=c.width, max_height=budget))
        )
        del rows[budget:]
        rows.extend(Line() for _ in range(budget - len(rows)))
        return Surface.of(rows, c.width)


def fit(line: Line, width: int) -> Line:
    return line if line.width <= width else line.clip(_CLIP, width)


def ends(
    width: int,
    left: str,
    right: str,
    left_style: Style,
    right_style: Style,
) -> Line:
    gap = max(1, width - len(left) - len(right) - 2)
    line = Line(
        (
            Segment(" "),
            Segment(left, left_style),
            Segment(" " * gap),
            Segment(right, right_style),
            Segment(" "),
        )
    )
    return fit(line, width)


def center(width: int, rows: Sequence[Line]) -> list[Line]:
    out: list[Line] = []
    for row in rows:
        pad = max(0, (width - row.width) // 2)
        if pad:
            row = Line((Segment(" " * pad),)) + row
        out.append(row.clip(_CLIP, width))
    return out


def ease_out_back(t: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1.0
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def hit_target(
    rects: Sequence[tuple[int, int, int, int]], pos: Pos
) -> int | None:
    for index, (row, col, height, width) in enumerate(rects):
        if row <= pos.y < row + height and col <= pos.x < col + width:
            return index
    return None


def pad_rows(rows: list[Line], height: int) -> list[Line]:
    result = rows[:height]
    result.extend(Line() for _ in range(height - len(result)))
    return result
