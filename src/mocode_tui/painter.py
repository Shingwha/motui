"""The painter: full-screen row-diff rendering onto a :class:`~mocode_tui.screen.Screen`.

The painter owns a resident :class:`~mocode_tui.viewport.Viewport` (so scroll
state survives across frames), lays the document out every frame, and writes
only what changed: a full repaint when the screen size changes (or on the very
first frame, prefixed by an erase), otherwise a per-row cursor-addressed
rewrite of the rows that differ from the previous frame.  An unchanged frame
is zero bytes.  When the screen is not live the painter stays completely
silent but still computes the logical rows, so :meth:`Painter.rows` can be
queried on non-live runs.
"""

from __future__ import annotations

from .ansi import clear_line
from .block import Document
from .lines import Line
from .screen import Screen
from .viewport import Viewport

__all__ = ["Painter"]

#: Erase the whole screen (a full frame starts with it).  The W2 contract pins
#: these exact bytes and ansi.py (frozen since W1) has no clear-screen helper,
#: so the constant lives here instead of being retyped at every use site.
_CLEAR_SCREEN = "\x1b[2J"


def _row_write(index: int, row: Line) -> str:
    """Position at 1-based ``index``, erase the row, paint it.

    A row whose ``styled()`` is empty still gets the positioning and the
    erase: stale content from an earlier frame must be cleared.
    """
    return f"\x1b[{index + 1};1H" + clear_line() + row.styled()


class Painter:
    """Renders a document onto a screen, one diffed frame at a time."""

    def __init__(self, document: Document, screen: Screen, *, throttle: float = 0.030) -> None:
        self._document = document
        self._screen = screen
        # Accepted for API stability only: the painter never throttles itself,
        # the caller decides when a frame is due.
        self._throttle = throttle
        self._viewport = Viewport(document)
        self._rows: list[Line] = []
        self._width: int | None = None
        self._height: int | None = None

    def flush(self) -> None:
        """Paint one frame: full repaint on (re)size, row diff otherwise."""
        self._screen.refresh_size()
        width, height = self._screen.width, self._screen.height
        full = (width, height) != (self._width, self._height)

        rows = self._viewport.layout(width, height).rows
        if self._screen.live:
            writes: list[str] = []
            if full:
                writes.append(_CLEAR_SCREEN)
                writes.extend(_row_write(i, row) for i, row in enumerate(rows))
            else:
                for i, row in enumerate(rows):
                    previous = self._rows[i] if i < len(self._rows) else None
                    if previous is None or previous != row:
                        writes.append(_row_write(i, row))
            if writes:
                self._screen.write("".join(writes))
                self._screen.flush()
        self._rows = rows
        self._width, self._height = width, height

    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows.

        Empty before the first flush (nothing has been painted yet).
        """
        return list(self._rows)

    # -- scrolling (forwarded to the resident viewport) -----------------------------

    def scroll_up(self, n: int = 1) -> None:
        self._viewport.scroll_up(n)

    def scroll_down(self, n: int = 1) -> None:
        self._viewport.scroll_down(n)

    def scroll_to_bottom(self) -> None:
        self._viewport.scroll_to_bottom()
