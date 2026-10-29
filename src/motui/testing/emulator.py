"""A tiny VT emulator for asserting on the frames a painter writes.

Consumes the painter's byte stream into a cell grid.  Supports CUP, EL/ED,
SGR (base/256/RGB colors), CR/LF/BS/tab, immediate autowrap, ``?1049``
(clear+home) and OSC 8 links; unknown escapes are ignored.  The final row's
line feed scrolls; there is no scrollback or input.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass, replace

from wcwidth import wcwidth

from ..kernel import Pos
from ..kernel.style import FG_CODES, Style

__all__ = ["Emulator"]

#: Parser states; :meth:`Emulator.feed` continues from whichever one it is in.
_GROUND = "ground"
_ESC = "esc"
_CSI = "csi"
_OSC = "osc"
_OSC_ESC = "osc_esc"
_ESC_SKIP = "esc_skip"

#: SGR foreground codes 30..37 (and 90..97) in name order; backgrounds add 10.
_BASE_NAMES = tuple(FG_CODES)

#: The xterm 6x6x6 cube's channel levels, for palette indices 16..231.
_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)

#: The unstyled cell: a frozen value shared by every blank cell.
_NONE = Style()


@dataclass(frozen=True, slots=True)
class Cell:
    """One grid cell: glyph, SGR state and OSC 8 link.

    A wide glyph owns a lead cell and a continuation cell with ``char == ""``;
    combining marks append to the cluster.
    """

    char: str = " "
    style: Style = _NONE
    link: str | None = None


def _params(raw: str) -> list[int | None]:
    """A CSI parameter string as values; an empty subparameter stays ``None``."""
    if not raw:
        return []
    values: list[int | None] = []
    for piece in raw.split(";"):
        try:
            values.append(int(piece) if piece else None)
        except ValueError:
            values.append(None)
    return values


def _value(values: list[int | None], index: int, default: int = 0) -> int:
    """``values[index]`` with a missing entry read as ``default``."""
    if index >= len(values):
        return default
    value = values[index]
    return default if value is None else value


def _index_color(index: int) -> str | tuple[int, int, int]:
    """The color a 256-color index names: a base name or an RGB triple."""
    index = max(0, min(255, index))
    if index < 16:
        return _BASE_NAMES[index]
    if index < 232:
        index -= 16
        return (
            _CUBE_LEVELS[index // 36],
            _CUBE_LEVELS[(index // 6) % 6],
            _CUBE_LEVELS[index % 6],
        )
    level = 8 + 10 * (index - 232)
    return (level, level, level)


class Emulator:
    """A cell grid fed by one painter's bytes.

    ``grid`` is row-major and ``cursor`` zero-based; ``resize`` keeps the
    top-left block and blanks new cells.
    """

    def __init__(self, width: int = 80, height: int = 24) -> None:
        self._width = width
        self._height = height
        self.grid: list[list[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]
        self.cursor = Pos()
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._state = _GROUND
        self._param = ""
        self._osc_buf = ""
        self._style = _NONE
        self._link: str | None = None
        self._last: tuple[int, int] | None = None
        #: A zero-width joiner just arrived: the next printable glyph joins
        #: the cluster cell instead of starting a new one.  A ZWJ emoji
        #: sequence is one two-column cell, the kernel's own grapheme rule.
        self._join = False

    @property
    def width(self) -> int:
        """Columns in the grid."""
        return self._width

    @property
    def height(self) -> int:
        """Rows in the grid."""
        return self._height

    # -- feeding -----------------------------------------------------------

    def feed(self, data: str | bytes) -> None:
        """Consume bytes or text, continuing any sequence split across calls.

        Bytes decode incrementally as UTF-8; do not mix ``str`` into a
        partial byte sequence.
        """
        text = self._decoder.decode(data) if isinstance(data, bytes) else data
        for ch in text:
            self._step(ch)

    def _step(self, ch: str) -> None:
        state = self._state
        if state == _GROUND:
            self._ground(ch)
        elif state == _ESC:
            self._escape(ch)
        elif state == _CSI:
            self._csi(ch)
        elif state == _OSC:
            self._osc(ch)
        elif state == _OSC_ESC:
            self._osc_esc(ch)
        else:  # _ESC_SKIP: a charset designation consumes exactly one byte
            self._state = _GROUND

    # -- ground text -------------------------------------------------------

    def _ground(self, ch: str) -> None:
        if ch == "\x1b":
            self._state = _ESC
            self._join = False
        elif ch == "\r":
            self._set_cursor(0, self.cursor.y)
            self._join = False
        elif ch == "\n":
            self._linefeed()
            self._last = None
            self._join = False
        elif ch == "\b":
            self._set_cursor(max(0, self.cursor.x - 1), self.cursor.y)
            self._last = None
            self._join = False
        elif ch == "\t":
            if self._width:
                self._set_cursor(
                    min(self._width - 1, (self.cursor.x // 8 + 1) * 8),
                    self.cursor.y,
                )
                self._last = None
            self._join = False
        elif ch == "\x07" or ord(ch) < 0x20 or ch == "\x7f":
            return
        else:
            self._print(ch)

    def _print(self, ch: str) -> None:
        if self._width <= 0 or self._height <= 0:
            return
        if ch == "\u200d":
            # A zero-width joiner binds the next glyph to the cluster cell.
            # The kernel's width rule measures the joined cluster as the base
            # glyph's two columns, so the grid keeps one cell for it.
            self._combine(ch)
            self._join = self._last is not None
            return
        width = wcwidth(ch)
        if width == 0:
            self._combine(ch)
            return
        if self._join:
            self._join = False
            if self._last is not None:
                y, x = self._last
                cell = self.grid[y][x]
                self.grid[y][x] = Cell(cell.char + ch, cell.style, cell.link)
                return
        if width < 0 or width > self._width:
            return
        if self.cursor.x + width > self._width:
            self._set_cursor(0, self.cursor.y)
            self._linefeed()
        x, y = self.cursor.x, self.cursor.y
        self.grid[y][x] = Cell(ch, self._style, self._link)
        if width == 2:
            self.grid[y][x + 1] = Cell("", self._style, self._link)
        self._last = (y, x)
        x += width
        if x >= self._width:
            self._set_cursor(0, y)
            self._linefeed()
            self._last = None
        else:
            self._set_cursor(x, y)

    def _combine(self, ch: str) -> None:
        """Append a zero-width mark (or joiner) to the glyph cell it follows."""
        if self._last is None:
            return
        y, x = self._last
        cell = self.grid[y][x]
        self.grid[y][x] = Cell(cell.char + ch, cell.style, cell.link)

    def _linefeed(self) -> None:
        """Move down one row; on the last row, scroll the grid up."""
        y = self.cursor.y + 1
        if y < self._height:
            self._set_cursor(self.cursor.x, y)
            return
        if self._height <= 0:
            return
        self.grid.pop(0)
        self.grid.append([Cell() for _ in range(self._width)])
        self._set_cursor(self.cursor.x, self._height - 1)
        self._last = None

    def _set_cursor(self, x: int, y: int) -> None:
        self.cursor = Pos(
            x=max(0, min(x, self._width - 1)),
            y=max(0, min(y, self._height - 1)),
        )

    # -- escape parsing ----------------------------------------------------

    def _escape(self, ch: str) -> None:
        if ch == "[":
            self._param = ""
            self._state = _CSI
        elif ch == "]":
            self._osc_buf = ""
            self._state = _OSC
        elif ch in "()*+":
            self._state = _ESC_SKIP
        else:
            self._state = _GROUND

    def _csi(self, ch: str) -> None:
        if ch == "\x1b":
            self._param = ""
            self._state = _ESC
            return
        if "\x40" <= ch <= "\x7e":
            raw, self._param = self._param, ""
            self._state = _GROUND
            self._dispatch(raw, ch)
            return
        self._param += ch

    def _dispatch(self, raw: str, final: str) -> None:
        private = raw.startswith("?")
        body = raw[1:] if private else raw
        values = _params(body)
        if final in "Hf":
            self._cup(values)
        elif final == "J":
            self._erase_display(_value(values, 0))
        elif final == "K":
            self._erase_line(_value(values, 0))
        elif final == "m":
            self._sgr(body)
        elif final in "hl" and private and 1049 in values:
            self._clear_all()
            self._set_cursor(0, 0)
            self._last = None

    def _cup(self, values: list[int | None]) -> None:
        row = _value(values, 0, 1)
        col = _value(values, 1, 1)
        self._set_cursor(col - 1, row - 1)
        self._last = None

    def _erase_line(self, mode: int) -> None:
        if not self.grid:
            return
        x = self.cursor.x
        row = self.grid[self.cursor.y]
        if mode == 1:
            start, end = 0, x + 1
        elif mode == 2:
            start, end = 0, self._width
        else:
            start, end = x, self._width
        for column in range(max(0, start), min(self._width, end)):
            row[column] = Cell()
        self._last = None

    def _erase_display(self, mode: int) -> None:
        if mode == 1:
            for y in range(self.cursor.y):
                self._blank_row(y)
            row = self.grid[self.cursor.y]
            for x in range(min(self._width, self.cursor.x + 1)):
                row[x] = Cell()
        elif mode in (2, 3):
            self._clear_all()
        else:
            self._erase_line(0)
            for y in range(self.cursor.y + 1, self._height):
                self._blank_row(y)
        self._last = None

    def _blank_row(self, y: int) -> None:
        self.grid[y] = [Cell() for _ in range(self._width)]

    def _clear_all(self) -> None:
        for y in range(self._height):
            self._blank_row(y)
        self._last = None

    def _osc(self, ch: str) -> None:
        if ch == "\x07":
            self._finish_osc()
        elif ch == "\x1b":
            self._state = _OSC_ESC
        else:
            self._osc_buf += ch

    def _osc_esc(self, _ch: str) -> None:
        self._finish_osc()

    def _finish_osc(self) -> None:
        body, self._osc_buf = self._osc_buf, ""
        self._state = _GROUND
        if not body.startswith("8;"):
            return
        parts = body.split(";", 2)
        if len(parts) == 3:
            self._link = parts[2] or None

    # -- SGR ---------------------------------------------------------------

    def _sgr(self, raw: str) -> None:
        values = _params(raw) or [0]
        style = self._style
        index = 0
        while index < len(values):
            value = _value(values, index)
            if value == 0:
                style = _NONE
            elif value == 1:
                style = replace(style, bold=True)
            elif value == 2:
                style = replace(style, dim=True)
            elif value == 3:
                style = replace(style, italic=True)
            elif value == 4:
                style = replace(style, underline=True)
            elif value == 7:
                style = replace(style, reverse=True)
            elif value == 9:
                style = replace(style, strike=True)
            elif value == 22:
                style = replace(style, bold=False, dim=False)
            elif value == 23:
                style = replace(style, italic=False)
            elif value == 24:
                style = replace(style, underline=False)
            elif value == 27:
                style = replace(style, reverse=False)
            elif value == 29:
                style = replace(style, strike=False)
            elif 30 <= value <= 37:
                style = replace(style, fg=_BASE_NAMES[value - 30])
            elif 90 <= value <= 97:
                style = replace(style, fg=_BASE_NAMES[8 + value - 90])
            elif 40 <= value <= 47:
                style = replace(style, bg=_BASE_NAMES[value - 40])
            elif 100 <= value <= 107:
                style = replace(style, bg=_BASE_NAMES[8 + value - 100])
            elif value == 39:
                style = replace(style, fg=None)
            elif value == 49:
                style = replace(style, bg=None)
            elif value in (38, 48):
                style, used = self._extended(style, values, index, background=value == 48)
                index += used
            index += 1
        self._style = style

    def _extended(
        self,
        style: Style,
        values: list[int | None],
        index: int,
        *,
        background: bool,
    ) -> tuple[Style, int]:
        """Parse ``38``/``48``'s selector; return the new style and the extra args."""
        kind = _value(values, index + 1, -1)
        if kind == 5 and index + 2 < len(values):
            color = _index_color(_value(values, index + 2))
            return (
                replace(style, bg=color) if background else replace(style, fg=color)
            ), 2
        if kind == 2 and index + 4 < len(values):
            rgb = (
                max(0, min(255, _value(values, index + 2))),
                max(0, min(255, _value(values, index + 3))),
                max(0, min(255, _value(values, index + 4))),
            )
            return (
                replace(style, bg=rgb) if background else replace(style, fg=rgb)
            ), 4
        return style, 0

    # -- inspection --------------------------------------------------------

    def sgr_at(self, x: int, y: int) -> Style:
        """The SGR state in effect at zero-based ``(x, y)``."""
        return self.cell(x, y).style

    def cell(self, x: int, y: int) -> Cell:
        """The cell at zero-based ``(x, y)``; out-of-range is an ``IndexError``."""
        if not (0 <= x < self._width and 0 <= y < self._height):
            raise IndexError(f"cell ({x}, {y}) outside {self._width}x{self._height}")
        return self.grid[y][x]

    def text(self) -> str:
        """The visible text: rows rstripped, trailing empty rows removed."""
        lines = [
            "".join(cell.char for cell in row if cell.char).rstrip()
            for row in self.grid
        ]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def resize(self, width: int, height: int) -> None:
        """Change the geometry, preserving the top-left block and clamping."""
        if width < 0 or height < 0:
            raise ValueError(f"emulator size must be non-negative, got {width}x{height}")
        grid = [[Cell() for _ in range(width)] for _ in range(height)]
        for y in range(min(height, self._height)):
            for x in range(min(width, self._width)):
                grid[y][x] = self.grid[y][x]
        self._width, self._height = width, height
        self.grid = grid
        self.cursor = Pos(
            x=min(self.cursor.x, max(0, width - 1)),
            y=min(self.cursor.y, max(0, height - 1)),
        )
        self._last = None
