"""The painter: full-screen row-diff rendering onto a Screen.

It writes only changed rows (a full repaint on a size change), brackets a
frame in the sync pair and flushes once; an unchanged frame is zero bytes."""

from __future__ import annotations

from ..kernel.cell import Line, Surface, cut_line
from ..kernel.layout import ScreenLayout
from .ansi import (
    CLEAR_LINE,
    begin_sync_update,
    clear_screen,
    cursor_position,
    end_sync_update,
)
from .render import styled_line
from .screen import Screen

__all__ = ["Painter"]


def _styled_row(row: Line, mode: str) -> str:
    """The row's SGR bytes under ``mode``; the render cache is keyed on
    ``(line, mode)``."""
    return styled_line(row, mode)  # type: ignore[arg-type]


def _row_write(index: int, styled: str) -> str:
    """Position at 1-based ``index``, erase the row and paint ``styled``; an
    empty rendering still clears stale content."""
    return cursor_position(index + 1, 1) + CLEAR_LINE + styled


class Painter:
    """Renders one laid-out frame onto a screen, one diffed frame at a time;
    ``frames`` counts every paint call, changed bytes or not."""

    def __init__(self, screen: Screen, *, sync: bool = True) -> None:
        self._screen = screen
        self._sync = sync
        self._rows: list[Line] = []
        self._width: int | None = None
        self._height: int | None = None
        # The app-pinned cursor cell (0-based, unclamped) and the last cell
        # actually emitted (clamped, so a screen that cannot show the anchor
        # yet does not repeat it); None until the app pins the cursor.
        self._anchor: tuple[int, int] | None = None
        self._anchor_emitted: tuple[int, int] | None = None
        #: Frames painted so far: every paint() call counts, changed bytes
        #: or not -- it measures the frame rate, not the diff size.
        self.frames = 0

    def set_cursor(self, row: int, col: int) -> None:
        """Pin the terminal cursor at 0-based ``(row, col)`` -- the IME anchor --
        appended as the frame epilogue or written alone when only it moved."""
        self._anchor = (row, col)

    def reset(self) -> None:
        """Forget what is on screen so the next frame repaints every row; needed
        after a buffer switch clears the screen behind the diff."""
        self._rows = []
        self._width = self._height = None

    def _clamped_anchor(self, width: int, height: int) -> tuple[int, int] | None:
        """The pinned anchor clamped into the screen, or ``None`` when unset."""
        if self._anchor is None:
            return None
        row, col = self._anchor
        return (max(0, min(row, height - 1)), max(0, min(col, width - 1)))

    def paint(self, target: ScreenLayout | Surface) -> None:
        """Paint one frame: full repaint on (re)size, row diff otherwise.

        Rows are truncated or padded to the screen and hard-clipped before any
        bytes: an over-wide row would wrap and corrupt every following row."""
        self.frames += 1
        self._screen.refresh_size()
        width, height = self._screen.width, self._screen.height
        full = (width, height) != (self._width, self._height)

        if isinstance(target, Surface):
            rows = list(target.rows)
            clip_width = target.width
        else:
            rows = list(target.rows)
            clip_width = width
        if len(rows) > height:
            del rows[height:]
        elif len(rows) < height:
            rows.extend(Line() for _ in range(height - len(rows)))
        rows = [
            cut_line(row, 0, clip_width) if row.width > clip_width else row
            for row in rows
        ]
        if self._screen.live:
            # The capability the rows are rendered for: the screen's own, and
            # the full-precision path for a screen that names none (the
            # switch is a screen's, read fresh each frame, never cached).
            mode = getattr(self._screen, "color_mode", "truecolor")
            writes: list[str] = []
            if full:
                writes.append(clear_screen())
                writes.extend(
                    _row_write(i, _styled_row(row, mode))
                    for i, row in enumerate(rows)
                )
            else:
                for i, row in enumerate(rows):
                    previous = self._rows[i] if i < len(self._rows) else None
                    if previous is None or previous != row:
                        writes.append(_row_write(i, _styled_row(row, mode)))
            anchor = self._clamped_anchor(width, height)
            if writes:
                if anchor is not None:
                    writes.append(cursor_position(anchor[0] + 1, anchor[1] + 1))
                self._emit("".join(writes))
                self._anchor_emitted = anchor
            elif anchor is not None and anchor != self._anchor_emitted:
                # Nothing changed on screen, but the pinned cursor moved.
                self._emit(cursor_position(anchor[0] + 1, anchor[1] + 1))
                self._anchor_emitted = anchor
        self._rows = rows
        self._width, self._height = width, height

    def _emit(self, payload: str) -> None:
        """Push one frame's bytes as one write and one flush, bracketed by the sync
        pair when enabled; an empty payload writes nothing."""
        if not payload:
            return
        if self._sync:
            payload = begin_sync_update() + payload + end_sync_update()
        self._screen.write(payload)
        self._screen.flush()

    @property
    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows, empty before
        the first paint."""
        return list(self._rows)
