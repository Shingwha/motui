"""Hand-built art for the showcase: the pixel logo, gradients and centring.

The showcase paints its splash logo from a tiny 5x7 bitmap font.  Every
glyph is seven strings of five cells, so the art is data, not a font
engine; :func:`big_text` turns the rows into the same immutable
:class:`~motui.kernel.cell.Line` values every component renders.

The helpers here are pure: a phase, a width and a palette in, rows out.
They know nothing about the runtime, so the splash can be rendered by a
headless snapshot and by a live frame through one code path.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..kernel.cell import Line, Segment
from ..kernel.style import NONE, Style
from ..kernel.text import WrapMode

__all__ = ["FONT_5X7", "big_text", "center", "gradient_styles"]

#: The 5x7 pixel glyphs the logo needs.  ``1`` paints a block, ``0`` a space.
FONT_5X7: dict[str, tuple[str, ...]] = {
    "m": (
        "10001",
        "11011",
        "10101",
        "10101",
        "10001",
        "10001",
        "10001",
    ),
    "o": (
        "00000",
        "00000",
        "01110",
        "10001",
        "10001",
        "10001",
        "01110",
    ),
    "t": (
        "00100",
        "00100",
        "11111",
        "00100",
        "00100",
        "00100",
        "01110",
    ),
    "u": (
        "00000",
        "10001",
        "10001",
        "10001",
        "10001",
        "10011",
        "01101",
    ),
    "i": (
        "00100",
        "00000",
        "01100",
        "00100",
        "00100",
        "00100",
        "01110",
    ),
    "M": (
        "10001",
        "11011",
        "10101",
        "10101",
        "10001",
        "10001",
        "10001",
    ),
    "O": (
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ),
    "T": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
    ),
    "U": (
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "10011",
        "01101",
    ),
    "I": (
        "01110",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "01110",
    ),
}

#: The glyphs' height: every entry in :data:`FONT_5X7` has this many rows.
GLYPH_HEIGHT = 7


def _rgb(value: str | tuple[int, int, int]) -> tuple[int, int, int]:
    """The RGB triple a ``#rrggbb`` string or a triple names."""
    if isinstance(value, tuple):
        return value
    text = value.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def gradient_styles(
    start: str | tuple[int, int, int],
    end: str | tuple[int, int, int],
    count: int,
    *,
    bold: bool = False,
) -> list[Style]:
    """``count`` styles interpolating ``start`` -> ``end`` (both included).

    The interpolation runs over the RGB triples, so a two-color ramp reads
    as a smooth fade on a truecolor terminal; ``bold`` is carried on every
    step.  ``count == 0`` answers nothing and ``count == 1`` the start.
    """
    if count <= 0:
        return []
    first = _rgb(start)
    last = _rgb(end)
    if count == 1:
        return [Style(fg=first, bold=bold)]
    steps = count - 1
    out: list[Style] = []
    for index in range(count):
        t = index / steps
        rgb = (
            round(first[0] + (last[0] - first[0]) * t),
            round(first[1] + (last[1] - first[1]) * t),
            round(first[2] + (last[2] - first[2]) * t),
        )
        out.append(Style(fg=rgb, bold=bold))
    return out


def _push(segments: list[Segment], char: str, style: Style) -> None:
    """Append one cell, fusing it onto the previous run when the style matches."""
    if segments and segments[-1].style == style and segments[-1].link is None:
        previous = segments[-1]
        segments[-1] = Segment(previous.text + char, style)
    else:
        segments.append(Segment(char, style))


def big_text(
    text: str,
    *,
    styles: Sequence[Style] = (),
    pixel: str = "\u2588",
    gap: int = 1,
    highlight: int | None = None,
    highlight_style: Style = NONE,
    style_at: Callable[[int, int], Style] | None = None,
) -> list[Line]:
    """``text`` in the 5x7 font, one :class:`Line` per glyph row.

    ``styles`` is a horizontal ramp: column ``x`` uses ``styles[x % len]``
    (one style paints the whole logo, an empty sequence paints plain).  A
    filled cell at column ``highlight`` takes ``highlight_style`` instead --
    the sweep the splash rides across the word.  ``style_at``, when given,
    overrides both: it receives the cell's column and glyph row and answers
    the style for every filled cell (the plasma/glitch packs use it).  ``gap``
    blank columns separate the glyphs; the width is
    ``5 * len(text) + gap * (len - 1)``.  A character the font lacks is
    skipped.
    """
    if not text:
        return []
    if pixel == "":
        raise ValueError("pixel must be a non-empty string")
    rows: list[Line] = []
    for row_index in range(GLYPH_HEIGHT):
        segments: list[Segment] = []
        column = 0
        for index, char in enumerate(text):
            glyph = FONT_5X7.get(char)
            if glyph is None:
                continue
            if index:
                for _ in range(max(0, gap)):
                    _push(segments, " ", NONE)
                    column += 1
            for bit in glyph[row_index]:
                if bit == "1":
                    if style_at is not None:
                        style = style_at(column, row_index)
                    else:
                        style = (
                            highlight_style
                            if column == highlight
                            else (styles[column % len(styles)] if styles else NONE)
                        )
                    _push(segments, pixel, style)
                else:
                    _push(segments, " ", NONE)
                column += 1
        rows.append(Line(segments))
    return rows


def center(width: int, rows: Sequence[Line]) -> list[Line]:
    """Centre every row horizontally in ``width`` columns.

    A row wider than ``width`` is clipped (no ellipsis: art should not grow
    a marker) and a row that already fits keeps its content untouched.
    """
    out: list[Line] = []
    for row in rows:
        pad = max(0, (width - row.width) // 2)
        if pad:
            row = Line((Segment(" " * pad),)) + row
        out.append(row.clip(WrapMode.CLIP, width))
    return out
