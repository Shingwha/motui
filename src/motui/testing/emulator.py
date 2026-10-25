"""A tiny VT emulator for asserting on the frames a painter writes.

The emulator consumes the byte stream a :class:`~motui.core.painter.Painter`
produces and maintains the cell grid a terminal would show.  It is a test
instrument, not a terminal: it implements the escapes this toolkit emits and
the few modes a full-screen session turns on, and it deliberately has no
scrollback, no image protocols and no input side.

The state is incremental: :meth:`Emulator.feed` may be called with arbitrarily
split chunks (bytes or text) and a sequence that straddles a split is
completed by the next call.  The parser is a small state machine over the
ground text, ESC, CSI and OSC states; one emulator owns one grid.

Unsupported input is ignored rather than raised: a terminal faced with an
escape it does not know must keep showing a coherent screen, and a test
asserting on one frame should not fail because the frame also carried a mode
byte the assertion does not care about.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass

from ..core.style import Style
from ..kernel import Pos

__all__ = ["Emulator"]

#: Parser states; :meth:`Emulator.feed` continues from whichever one it is in.
_GROUND = "ground"


@dataclass(frozen=True, slots=True)
class Cell:
    """One grid cell: its glyph, the SGR state over it and its OSC 8 link.

    A double-width glyph owns two cells: the glyph itself and a placeholder
    whose ``char`` is empty.  Combining marks are appended to the glyph cell
    they follow, so the cell text is the full grapheme cluster.
    """

    char: str = " "
    style: Style = Style()
    link: str | None = None


class Emulator:
    """A cell grid fed by one painter's bytes.

    ``width``/``height`` are the screen geometry the bytes were rendered for.
    :attr:`grid` is row-major, :attr:`cursor` is zero-based, and
    :meth:`resize` keeps the top-left block (the region a real resize
    preserves) while filling the new cells with blanks.
    """

    def __init__(self, width: int = 80, height: int = 24) -> None:
        self._width = width
        self._height = height
        self.grid: list[list[Cell]] = [
            [Cell() for _ in range(width)] for _ in range(height)
        ]
        self.cursor = Pos()
        self._pending = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._state = _GROUND
        self._param = ""
        self._style = Style()
        self._link: str | None = None
        self._last: tuple[int, int] | None = None

    @property
    def width(self) -> int:
        """Columns in the grid."""
        return self._width

    @property
    def height(self) -> int:
        """Rows in the grid."""
        return self._height

    def feed(self, data: str | bytes) -> None:
        """Consume bytes or text, continuing any sequence split across calls."""
        raise NotImplementedError("the parser lands with the emulator ticket")

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
