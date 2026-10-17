"""The painter: full-screen row-diff rendering onto a :class:`~motui.kernel.screen.Screen`.

The painter owns no document and no scroll state: every frame arrives as a
:class:`~motui.kernel.viewport.ScreenLayout` the caller laid out (the
driver owns the :class:`~motui.kernel.viewport.Viewport` that carries the
scroll position), and the painter writes only what changed -- a full repaint
when the screen size changes (or on the very first frame, prefixed by an
erase), otherwise a per-row cursor-addressed rewrite of the rows that differ
from the previous frame.  An unchanged frame is zero bytes -- a frame that
only moves the pinned cursor anchor (:meth:`Painter.set_cursor`) writes that
anchor escape alone.  When the screen is not live the painter stays
completely silent but still keeps the logical rows, so :attr:`Painter.rows`
can be queried on non-live runs.

Every non-empty frame leaves as **one write** -- the joined rows bracketed by
the synchronized-update pair (DECSET 2026) -- followed by **one flush**, so a
terminal that knows the mode swaps the frame in a single repaint instead of
showing it half-painted; ``sync=False`` turns the bracket off for a host
streaming to something that cannot parse it.  The bracket never changes the
zero-byte contract: an empty payload writes nothing at all.

Rows are rendered for the capability the screen declares
(``screen.color_mode``, ``"truecolor"`` for a screen that declares none): the
truecolor path is :meth:`Line.styled`'s cached rendering -- the bytes the
painter has always emitted -- and a downgraded mode renders fresh through
:func:`~motui.kernel.lines.styled_with`, so no cache ever depends on the
terminal.
"""

from __future__ import annotations

from .ansi import (
    CLEAR_LINE,
    begin_sync_update,
    clear_screen,
    cursor_position,
    end_sync_update,
)
from .lines import Line, styled_with
from .screen import Screen
from .viewport import ScreenLayout

__all__ = ["Painter"]


def _styled_row(row: Line, mode: str) -> str:
    """The row's SGR bytes under ``mode``.

    ``"truecolor"`` -- and any screen that declares no mode at all -- takes
    the row's own cached rendering, the bytes the painter has always
    emitted.  A downgraded mode renders fresh through
    :func:`~motui.kernel.lines.styled_with`, because the cached bytes
    must never depend on the terminal's capability (the kernel
    constitution).
    """
    return row.styled() if mode == "truecolor" else styled_with(row, mode)


def _row_write(index: int, styled: str) -> str:
    """Position at 1-based ``index``, erase the row, paint ``styled``.

    A row whose rendering is empty still gets the positioning and the
    erase: stale content from an earlier frame must be cleared.
    """
    return cursor_position(index + 1, 1) + CLEAR_LINE + styled


class Painter:
    """Renders one laid-out frame onto a screen, one diffed frame at a time.

    :attr:`frames` counts every :meth:`paint` call -- including frames that
    wrote no bytes -- so a host can measure its real frame rate off it.
    ``sync`` (the default) brackets each frame's non-empty payload in the
    synchronized-update pair (DECSET 2026, see :meth:`_emit`); the payload is
    still one write and one flush, and a frame with nothing to say stays
    silent either way.
    """

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

    def paint(self, layout: ScreenLayout) -> None:
        """Paint one frame: full repaint on (re)size, row diff otherwise."""
        self.frames += 1
        self._screen.refresh_size()
        width, height = self._screen.width, self._screen.height
        full = (width, height) != (self._width, self._height)

        rows = layout.rows
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
        """Push one frame's bytes: one write, one flush -- and the sync pair.

        With ``sync`` on, a non-empty payload leaves as ``begin + payload +
        end`` (DECSET 2026, still a single write), so the terminal holds the
        frame and swaps it in whole; a terminal that does not know the mode
        ignores both bytes.  An empty payload is not a write at all: the
        zero-byte contract for unchanged frames is a property of the payload,
        never of the switch.
        """
        if not payload:
            return
        if self._sync:
            payload = begin_sync_update() + payload + end_sync_update()
        self._screen.write(payload)
        self._screen.flush()

    @property
    def rows(self) -> list[Line]:
        """The current target screen: exactly ``screen.height`` rows.

        Empty before the first paint (nothing has been painted yet).
        """
        return list(self._rows)
