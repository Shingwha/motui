"""The painter: full-screen row-diff rendering onto a :class:`~mocode_tui.screen.Screen`.

The painter owns a resident :class:`~mocode_tui.viewport.Viewport` (so scroll
state survives across frames), lays the document out every frame, and writes
only what changed: a full repaint when the screen size changes (or on the very
first frame, prefixed by an erase), otherwise a per-row cursor-addressed
rewrite of the rows that differ from the previous frame.  An unchanged frame
is zero bytes -- a frame that only moves the pinned cursor anchor
(:meth:`Painter.set_cursor_anchor`) writes that anchor escape alone.  When the
screen is not live the painter stays completely silent but still computes the
logical rows, so :meth:`Painter.rows` can be queried on non-live runs.
"""

from __future__ import annotations

from .ansi import clear_line, clear_screen, cursor_position
from .block import Document
from .lines import Line
from .screen import Screen
from .viewport import Viewport

__all__ = ["Painter"]


def _row_write(index: int, row: Line) -> str:
    """Position at 1-based ``index``, erase the row, paint it.

    A row whose ``styled()`` is empty still gets the positioning and the
    erase: stale content from an earlier frame must be cleared.
    """
    return cursor_position(index + 1, 1) + clear_line() + row.styled()


class Painter:
    """Renders a document onto a screen, one diffed frame at a time."""

    def __init__(self, document: Document, screen: Screen) -> None:
        self._document = document
        self._screen = screen
        self._viewport = Viewport(document)
        self._rows: list[Line] = []
        self._width: int | None = None
        self._height: int | None = None
        # The app-pinned cursor cell (0-based, unclamped) and the last cell
        # actually emitted (clamped, so a screen that cannot show the anchor
        # yet does not repeat it); None until the app pins the cursor.
        self._anchor: tuple[int, int] | None = None
        self._anchor_emitted: tuple[int, int] | None = None

    def set_cursor_anchor(self, row: int, col: int) -> None:
        """Pin the terminal cursor at 0-based ``(row, col)`` (the IME anchor).

        A full-screen application that draws its own input box leaves the
        terminal cursor wherever the last row rewrite ended -- mid-transcript
        while the reply streams -- and the console's IME pops its candidate
        window there.  An application that owns an input box calls this
        whenever the cursor cell may have moved (typically once per frame);
        every live frame then ends with the matching cursor-position escape,
        so the IME follows the input box instead of the streaming text.

        The anchor is the frame epilogue: appended after the diff of a frame
        that wrote anything, and written alone by a frame that wrote nothing
        but moved the anchor.  A non-live screen never receives it (runtime
        output stays zero bytes).  An anchor outside the screen clamps into
        it; a size change neither clears nor re-emits the anchor -- the next
        frame re-clamps it, and the application is expected to recompute it
        (as the demo does after a keypress).
        """
        self._anchor = (row, col)

    def _clamped_anchor(self, width: int, height: int) -> tuple[int, int] | None:
        """The pinned anchor clamped into the screen, or ``None`` when unset."""
        if self._anchor is None:
            return None
        row, col = self._anchor
        return (max(0, min(row, height - 1)), max(0, min(col, width - 1)))

    def flush(self) -> None:
        """Paint one frame: full repaint on (re)size, row diff otherwise."""
        self._screen.refresh_size()
        width, height = self._screen.width, self._screen.height
        full = (width, height) != (self._width, self._height)

        rows = self._viewport.layout(width, height).rows
        if self._screen.live:
            writes: list[str] = []
            if full:
                writes.append(clear_screen())
                writes.extend(_row_write(i, row) for i, row in enumerate(rows))
            else:
                for i, row in enumerate(rows):
                    previous = self._rows[i] if i < len(self._rows) else None
                    if previous is None or previous != row:
                        writes.append(_row_write(i, row))
            anchor = self._clamped_anchor(width, height)
            if writes:
                if anchor is not None:
                    writes.append(cursor_position(anchor[0] + 1, anchor[1] + 1))
                self._screen.write("".join(writes))
                self._screen.flush()
                self._anchor_emitted = anchor
            elif anchor is not None and anchor != self._anchor_emitted:
                # Nothing changed on screen, but the pinned cursor moved.
                self._screen.write(cursor_position(anchor[0] + 1, anchor[1] + 1))
                self._screen.flush()
                self._anchor_emitted = anchor
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
